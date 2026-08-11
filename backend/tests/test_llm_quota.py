"""Focused per-student daily LLM quota and provider-guard tests."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier
from types import SimpleNamespace

import pytest
from alembic import command
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import AuthContext
from app.core.config import LLMQuotaSettings
from app.models import LLMDailyUsage, User
from app.routers import ai_assistant
from app.services.llm_client import LLMResult
from app.services.llm_quota import (
    LLMQuotaExceeded,
    UsageReservation,
    UsageStatus,
    get_usage_status,
    reserve_llm_call,
)


@pytest.fixture(scope="module", autouse=True)
def schema(test_alembic_config):
    command.upgrade(test_alembic_config, "head")


def _settings(**overrides) -> LLMQuotaSettings:
    return LLMQuotaSettings(_env_file=None, **overrides)


def _clear(factory: sessionmaker[Session]) -> None:
    with factory() as db:
        db.execute(delete(LLMDailyUsage))
        db.execute(delete(User).where(User.berkeley_username.like("quota-%")))
        db.commit()


def _user(factory: sessionmaker[Session], name: str) -> User:
    with factory() as db:
        user = User(berkeley_username=f"quota-{name}")
        db.add(user)
        db.commit()
        return user


def test_call_limit_is_independent_per_student_and_resets_next_day(test_engine):
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    _clear(factory)
    try:
        first = _user(factory, "first")
        second = _user(factory, "second")
        settings = _settings()
        today = datetime(2026, 8, 11, 18, tzinfo=UTC)
        with factory() as db:
            reservation = reserve_llm_call(db, first.id, 1, settings, now=today)
        with factory() as db:
            row = db.query(LLMDailyUsage).filter_by(
                user_id=first.id,
                usage_date=reservation.usage_date,
            ).one()
            row.call_count = 49
            row.input_tokens = 0
            row.estimated_cost = Decimal("0")
            db.commit()
            reserve_llm_call(db, first.id, 1, settings, now=today)
            with pytest.raises(LLMQuotaExceeded, match="Daily AI") as exc_info:
                reserve_llm_call(db, first.id, 1, settings, now=today)
            assert exc_info.value.limit_type == "calls"

            reserve_llm_call(db, second.id, 1, settings, now=today)
            assert get_usage_status(db, second.id, settings, metered=True, now=today).calls_used == 1
            assert get_usage_status(db, first.id, settings, metered=True, now=today + timedelta(days=1)).calls_used == 0
    finally:
        _clear(factory)


def test_input_and_cost_limits_reject_before_provider_budget(test_engine):
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    _clear(factory)
    try:
        user = _user(factory, "guards")
        now = datetime(2026, 8, 11, 18, tzinfo=UTC)
        with factory() as db:
            input_settings = _settings(
                max_llm_input_tokens_per_day=10,
                llm_input_cost_per_million_tokens=Decimal("0"),
                llm_output_cost_per_million_tokens=Decimal("0"),
            )
            first = reserve_llm_call(db, user.id, 9, input_settings, now=now)
            with pytest.raises(LLMQuotaExceeded) as input_error:
                reserve_llm_call(db, user.id, 2, input_settings, now=now)
            assert input_error.value.limit_type == "input_tokens"

            db.execute(delete(LLMDailyUsage).where(LLMDailyUsage.user_id == user.id))
            db.commit()
            cost_settings = _settings(
                max_llm_estimated_cost_per_day=Decimal("0.001"),
                llm_input_cost_per_million_tokens=Decimal("0"),
                llm_output_cost_per_million_tokens=Decimal("10"),
            )
            with pytest.raises(LLMQuotaExceeded) as cost_error:
                reserve_llm_call(db, user.id, 1, cost_settings, now=now)
            assert cost_error.value.limit_type == "estimated_cost"
            assert first.estimated_input_tokens == 9
    finally:
        _clear(factory)


def test_concurrent_requests_cannot_bypass_one_call_limit(test_engine):
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    _clear(factory)
    try:
        user = _user(factory, "concurrent")
        settings = _settings(max_llm_calls_per_day=1)
        now = datetime(2026, 8, 11, 18, tzinfo=UTC)
        barrier = Barrier(2)

        def attempt() -> str:
            with factory() as db:
                barrier.wait()
                try:
                    reserve_llm_call(db, user.id, 1, settings, now=now)
                    return "reserved"
                except LLMQuotaExceeded:
                    return "rejected"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = sorted(executor.map(lambda _: attempt(), range(2)))
        assert outcomes == ["rejected", "reserved"]
    finally:
        _clear(factory)


def test_route_enforces_output_limit_and_returns_structured_usage(monkeypatch):
    user = User(id=uuid.uuid4(), berkeley_username="quota-route")
    context = AuthContext(user=user)
    db = SimpleNamespace()
    settings = _settings()
    captured = {}

    class FakeClient:
        def generate_response(self, **kwargs):
            captured.update(kwargs)
            return LLMResult("answer", "azure", input_tokens=12, output_tokens=5)

    reservation = UsageReservation(
        user_id=user.id,
        usage_date=datetime.now(UTC).date(),
        estimated_input_tokens=10,
        reserved_cost=Decimal("0.001"),
        resets_at=datetime.now(UTC) + timedelta(days=1),
    )
    monkeypatch.setattr(ai_assistant, "get_llm_client", lambda: FakeClient())
    monkeypatch.setattr(ai_assistant, "get_llm_provider_name", lambda: "azure")
    monkeypatch.setattr(ai_assistant, "estimate_input_tokens", lambda *args: 10)
    monkeypatch.setattr(ai_assistant, "reserve_llm_call", lambda *args, **kwargs: reservation)
    monkeypatch.setattr(ai_assistant, "reconcile_llm_call", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        ai_assistant,
        "get_usage_status",
        lambda *args, **kwargs: UsageStatus(1, 50, reservation.resets_at, True),
    )

    response = ai_assistant.chat(
        ai_assistant.AssistantRequest(message="help"),
        db,
        context,
        settings,
    )
    assert captured["max_output_tokens"] == 500
    assert response.usage.calls_used == 1


def test_quota_rejection_is_structured_and_never_calls_provider(monkeypatch):
    user = User(id=uuid.uuid4(), berkeley_username="quota-reject")
    context = AuthContext(user=user)
    settings = _settings()
    called = False

    class FakeClient:
        def generate_response(self, **kwargs):
            nonlocal called
            called = True
            return LLMResult("unexpected", "azure")

    resets_at = datetime.now(UTC) + timedelta(days=1)
    monkeypatch.setattr(ai_assistant, "get_llm_client", lambda: FakeClient())
    monkeypatch.setattr(ai_assistant, "get_llm_provider_name", lambda: "azure")
    monkeypatch.setattr(ai_assistant, "estimate_input_tokens", lambda *args: 10)
    monkeypatch.setattr(
        ai_assistant,
        "reserve_llm_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(LLMQuotaExceeded("calls", resets_at)),
    )

    with pytest.raises(HTTPException) as exc_info:
        ai_assistant.chat(
            ai_assistant.AssistantRequest(message="help"),
            SimpleNamespace(),
            context,
            settings,
        )
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["code"] == "daily_ai_limit_reached"
    assert exc_info.value.detail["limit_type"] == "calls"
    assert called is False


def test_mock_agent_does_not_reserve_paid_usage(monkeypatch):
    user = User(id=uuid.uuid4(), berkeley_username="quota-mock")
    context = AuthContext(user=user)
    settings = _settings()

    class FakeMockClient:
        def generate_response(self, **kwargs):
            return LLMResult("mock answer", "mock")

    monkeypatch.setattr(ai_assistant, "get_llm_client", lambda: FakeMockClient())
    monkeypatch.setattr(ai_assistant, "get_llm_provider_name", lambda: "mock")
    monkeypatch.setattr(
        ai_assistant,
        "reserve_llm_call",
        lambda *args, **kwargs: pytest.fail("mock must not reserve paid quota"),
    )
    monkeypatch.setattr(
        ai_assistant,
        "get_usage_status",
        lambda *args, **kwargs: UsageStatus(0, 50, datetime.now(UTC) + timedelta(days=1), False),
    )

    response = ai_assistant.chat(
        ai_assistant.AssistantRequest(message="help"),
        SimpleNamespace(),
        context,
        settings,
    )
    assert response.provider == "mock"
    assert response.usage.metered is False
