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
from app.services.llm_client import AzureLLMClient, LLMResult
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


def test_route_uses_safety_ceiling_and_returns_structured_usage(monkeypatch):
    user = User(id=uuid.uuid4(), berkeley_username="quota-route")
    context = AuthContext(user=user)
    db = SimpleNamespace()
    settings = _settings()
    captured = {}
    reconciled = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content=" answer "),
                    finish_reason="length",
                )],
                usage=SimpleNamespace(prompt_tokens=12, completion_tokens=5),
            )

    client = AzureLLMClient.__new__(AzureLLMClient)
    client._endpoint = "https://example.invalid/openai/v1"
    client._deployment = "test-deployment"
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions())
    )

    reservation = UsageReservation(
        user_id=user.id,
        usage_date=datetime.now(UTC).date(),
        estimated_input_tokens=10,
        reserved_cost=Decimal("0.001"),
        resets_at=datetime.now(UTC) + timedelta(days=1),
    )
    monkeypatch.setattr(ai_assistant, "get_llm_client", lambda: client)
    monkeypatch.setattr(
        ai_assistant,
        "StudentAIContextAssembler",
        lambda db: SimpleNamespace(build=lambda *args, **kwargs: {"scope": "own"}),
    )
    monkeypatch.setattr(ai_assistant, "estimate_messages_tokens", lambda *args: 10)
    monkeypatch.setattr(ai_assistant, "reserve_llm_call", lambda *args, **kwargs: reservation)
    monkeypatch.setattr(
        ai_assistant,
        "reconcile_llm_call",
        lambda *args, **kwargs: reconciled.update(kwargs),
    )
    monkeypatch.setattr(
        ai_assistant,
        "get_usage_status",
        lambda *args, **kwargs: UsageStatus(1, 50, reservation.resets_at, True),
    )

    response = ai_assistant.chat(
        ai_assistant.AssistantRequest(
            message="help",
            draft_policy_code="def admission_policy(*args): return 0",
        ),
        db,
        context,
        settings,
    )
    assert captured["max_completion_tokens"] == 4_000
    assert captured["model"] == "test-deployment"
    assert response.content == "answer"
    assert response.provider == "azure"
    assert response.response_limited is True
    assert reconciled["actual_input_tokens"] == 12
    assert reconciled["actual_output_tokens"] == 5
    assert response.usage.calls_used == 1


def test_daily_quota_defaults_remain_unchanged_with_generous_output_safety_ceiling():
    settings = _settings()

    assert settings.max_llm_calls_per_day == 50
    assert settings.max_llm_input_tokens_per_day == 100_000
    assert settings.max_llm_estimated_cost_per_day == Decimal("0.25")
    assert settings.llm_output_token_safety_ceiling == 4_000


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
    monkeypatch.setattr(
        ai_assistant,
        "StudentAIContextAssembler",
        lambda db: SimpleNamespace(build=lambda *args, **kwargs: {"scope": "own"}),
    )
    monkeypatch.setattr(ai_assistant, "estimate_messages_tokens", lambda *args: 10)
    monkeypatch.setattr(
        ai_assistant,
        "reserve_llm_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(LLMQuotaExceeded("calls", resets_at)),
    )

    with pytest.raises(HTTPException) as exc_info:
        ai_assistant.chat(
            ai_assistant.AssistantRequest(
                message="help",
                draft_policy_code="def admission_policy(*args): return 0",
            ),
            SimpleNamespace(),
            context,
            settings,
        )
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["code"] == "daily_ai_limit_reached"
    assert exc_info.value.detail["limit_type"] == "calls"
    assert called is False


def test_adapter_contract_error_is_detected_before_quota_reservation(monkeypatch):
    user = User(id=uuid.uuid4(), berkeley_username="quota-preflight")
    context = AuthContext(user=user)

    class InvalidAdapter:
        def generate_response(self, message):
            return LLMResult("unexpected", "azure")

    monkeypatch.setattr(ai_assistant, "get_llm_client", lambda: InvalidAdapter())
    monkeypatch.setattr(
        ai_assistant,
        "StudentAIContextAssembler",
        lambda db: SimpleNamespace(build=lambda *args, **kwargs: {"scope": "own"}),
    )
    monkeypatch.setattr(ai_assistant, "estimate_messages_tokens", lambda *args: 10)
    monkeypatch.setattr(
        ai_assistant,
        "reserve_llm_call",
        lambda *args, **kwargs: pytest.fail("pre-dispatch failure must not reserve quota"),
    )

    with pytest.raises(HTTPException) as exc_info:
        ai_assistant.chat(
            ai_assistant.AssistantRequest(
                message="help",
                draft_policy_code="def admission_policy(*args): return 0",
            ),
            SimpleNamespace(rollback=lambda: None),
            context,
            _settings(),
        )
    assert exc_info.value.status_code == 502


def test_conversation_history_keeps_only_latest_six_complete_turns():
    history = []
    for number in range(1, 9):
        history.extend(
            [
                ai_assistant.ChatMessage(role="user", content=f"user-{number}"),
                ai_assistant.ChatMessage(role="assistant", content=f"assistant-{number}"),
            ]
        )
    history.append(ai_assistant.ChatMessage(role="user", content="unanswered"))

    bounded = ai_assistant.bounded_complete_history(history)

    assert len(bounded) == 12
    assert bounded[0] == {"role": "user", "content": "user-3"}
    assert bounded[-1] == {"role": "assistant", "content": "assistant-8"}
    assert all(item["content"] != "unanswered" for item in bounded)
