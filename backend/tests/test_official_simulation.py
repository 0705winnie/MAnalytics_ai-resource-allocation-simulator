from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from alembic import command
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import ACCESS_COOKIE_NAME, create_access_token
from app.core.config import AuthSettings, get_auth_settings
from app.db.session import get_db
from app.main import create_app
from app.models import (
    CourseInstance,
    Enrollment,
    MonthlyResult,
    SimulationSession,
    Submission,
    User,
)
from app.models.enums import EnrollmentStatus, UserRole
from app.services import simulation_persistence


TEST_JWT_SECRET = "test-only-official-simulation-secret-32-characters"
POLICY_A = """
def admission_policy(request, state, history, params):
    return 0
"""
POLICY_B = """
def admission_policy(request, state, history, params):
    for cluster_id, remaining in state["remaining_capacity"].items():
        if remaining >= request["required_units"]:
            return cluster_id
    return 0
"""


def _settings() -> AuthSettings:
    return AuthSettings(
        _env_file=None,
        jwt_secret=SecretStr(TEST_JWT_SECRET),
        auth_cookie_secure=False,
        access_token_minutes=30,
        frontend_origin="http://frontend.test",
    )


def _clear_tables(
    factory: sessionmaker[Session],
    test_database_url: URL,
) -> None:
    assert test_database_url.database is not None
    assert test_database_url.database.endswith("_test")
    with factory() as session:
        session.execute(delete(MonthlyResult))
        session.execute(delete(SimulationSession))
        session.execute(delete(Submission))
        session.execute(delete(Enrollment))
        session.execute(delete(CourseInstance))
        session.execute(delete(User))
        session.commit()


@pytest.fixture(scope="module", autouse=True)
def official_schema(test_alembic_config):
    command.upgrade(test_alembic_config, "head")


@pytest.fixture
def official_session_factory(
    test_engine: Engine,
    test_database_url: URL,
) -> Generator[sessionmaker[Session], None, None]:
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    _clear_tables(factory, test_database_url)
    yield factory
    _clear_tables(factory, test_database_url)


@pytest.fixture
def app_factory(
    official_session_factory: sessionmaker[Session],
) -> Callable[[AuthSettings], object]:
    def build(settings: AuthSettings):
        api = create_app(settings)

        def override_get_db() -> Generator[Session, None, None]:
            with official_session_factory() as session:
                yield session

        api.dependency_overrides[get_db] = override_get_db
        api.dependency_overrides[get_auth_settings] = lambda: settings
        return api

    return build


@pytest.fixture
def client(app_factory) -> Generator[TestClient, None, None]:
    with TestClient(app_factory(_settings())) as test_client:
        yield test_client


def _create_student(
    factory: sessionmaker[Session],
    *,
    suffix: str = "primary",
    with_session: bool = True,
) -> tuple[User, CourseInstance, Enrollment, SimulationSession | None]:
    owner = User(
        berkeley_username=f"official-owner-{suffix}",
        role=UserRole.INSTRUCTOR,
    )
    student = User(
        berkeley_username=f"official-student-{suffix}",
        role=UserRole.STUDENT,
    )
    course = CourseInstance(
        course_code=f"OFFICIAL-{suffix}",
        course_name="Official Simulation Test",
        semester="Fall 2026",
        creator=owner,
    )
    official_session = SimulationSession() if with_session else None
    enrollment = Enrollment(
        course=course,
        user=student,
        nickname=f"Student {suffix}",
        status=EnrollmentStatus.ACTIVE,
        activation_used_at=datetime.now(UTC),
        simulation_session=official_session,
    )
    with factory() as session:
        session.add(enrollment)
        session.commit()
    return student, course, enrollment, official_session


def _create_instructor(factory: sessionmaker[Session]) -> User:
    instructor = User(
        berkeley_username="official-instructor-login",
        role=UserRole.INSTRUCTOR,
    )
    with factory() as session:
        session.add(instructor)
        session.commit()
    return instructor


def _authenticate_student(
    client: TestClient,
    student: User,
    course: CourseInstance,
    enrollment: Enrollment,
) -> None:
    client.cookies.set(
        ACCESS_COOKIE_NAME,
        create_access_token(
            student.id,
            student.role,
            _settings(),
            course_id=course.id,
            enrollment_id=enrollment.id,
        ),
    )


def _authenticate_instructor(client: TestClient, instructor: User) -> None:
    client.cookies.set(
        ACCESS_COOKIE_NAME,
        create_access_token(instructor.id, instructor.role, _settings()),
    )


def _request(
    expected_month: int,
    *,
    key: uuid.UUID | None = None,
    policy_code: str = POLICY_A,
    params: dict[str, float] | None = None,
) -> dict[str, object]:
    return {
        "expected_month": expected_month,
        "idempotency_key": str(key or uuid.uuid4()),
        "policy_code": policy_code,
        "params": params or {},
    }


def _fake_month_result(month: int) -> dict[str, object]:
    total_requests = 10 + month
    admitted_requests = 7
    completed_requests = 5
    return {
        "month": month,
        "total_requests": total_requests,
        "admitted_requests": admitted_requests,
        "completed_requests": completed_requests,
        "rejected_requests": total_requests - admitted_requests,
        "total_revenue": round(100.25 * month, 2),
        "unfinished_requests": admitted_requests - completed_requests,
        "unfinished_value": round(25.50 * month, 2),
        "avg_utilization": {1: 0.1 * month},
        "peak_utilization": {1: 0.2 * month},
        "remaining_capacity": {1: 90 - month},
        "by_type": [
            {
                "type": "VIP",
                "total_requests": total_requests,
                "admitted_requests": admitted_requests,
                "completed_requests": completed_requests,
                "total_revenue": round(100.25 * month, 2),
            }
        ],
        "warnings": [f"month-{month}-warning"] if month % 2 == 0 else [],
    }


def _install_fake_engine(monkeypatch, calls: list[dict[str, object]] | None = None):
    def fake_simulate_month(
        month,
        policy_fn,
        params,
        *,
        seed,
        previous_months,
    ):
        if calls is not None:
            calls.append(
                {
                    "month": month,
                    "params": dict(params),
                    "seed": seed,
                    "previous_months": previous_months,
                }
            )
        return _fake_month_result(month)

    monkeypatch.setattr(simulation_persistence, "simulate_month", fake_simulate_month)


def _stored_benchmark(month: int) -> list[dict[str, object]]:
    result = _fake_month_result(month)
    return [
        {
            "policy": "student_policy",
            "total_revenue": result["total_revenue"],
            "total_unfinished_requests": result["unfinished_requests"],
            "total_unfinished_value": result["unfinished_value"],
            "admitted_requests": result["admitted_requests"],
            "completed_requests": result["completed_requests"],
            "rejected_requests": result["rejected_requests"],
            "warnings_count": len(result["warnings"]),
        }
    ]


def _store_months(
    factory: sessionmaker[Session],
    official_session: SimulationSession,
    count: int,
) -> None:
    with factory() as session:
        stored_session = session.get(SimulationSession, official_session.id)
        assert stored_session is not None
        for month in range(1, count + 1):
            result = _fake_month_result(month)
            policy_code = POLICY_A if month == 1 else POLICY_B
            params = {"threshold": float(month)}
            session.add(
                MonthlyResult(
                    session_id=stored_session.id,
                    month=month,
                    idempotency_key=uuid.uuid4(),
                    policy_code=policy_code,
                    policy_params=params,
                    policy_hash=simulation_persistence.calculate_policy_hash(
                        policy_code,
                        params,
                    ),
                    total_requests=result["total_requests"],
                    admitted_requests=result["admitted_requests"],
                    completed_requests=result["completed_requests"],
                    rejected_requests=result["rejected_requests"],
                    total_revenue=Decimal(str(result["total_revenue"])),
                    unfinished_requests=result["unfinished_requests"],
                    unfinished_value=Decimal(str(result["unfinished_value"])),
                    avg_utilization=result["avg_utilization"],
                    peak_utilization=result["peak_utilization"],
                    remaining_capacity=result["remaining_capacity"],
                    by_type=result["by_type"],
                    warnings=result["warnings"],
                    benchmark_comparison=_stored_benchmark(month),
                    completed_at=datetime.now(UTC),
                )
            )
        stored_session.completed_months = count
        stored_session.last_completed_at = datetime.now(UTC) if count else None
        session.commit()


def _student_fixture_and_login(
    client: TestClient,
    factory: sessionmaker[Session],
    *,
    suffix: str = "primary",
) -> tuple[User, CourseInstance, Enrollment, SimulationSession]:
    student, course, enrollment, official_session = _create_student(
        factory,
        suffix=suffix,
    )
    assert official_session is not None
    _authenticate_student(client, student, course, enrollment)
    return student, course, enrollment, official_session


def test_restore_zero_month_session(client, official_session_factory):
    _student_fixture_and_login(client, official_session_factory)

    response = client.get("/api/simulation/session")

    assert response.status_code == 200
    body = response.json()
    assert body["completed_months"] == 0
    assert body["next_month"] == 1
    assert body["status"] == "not_started"
    assert body["monthly_results"] == []
    assert body["latest_policy"] is None
    assert body["cumulative"] == {
        "total_requests": 0,
        "admitted_requests": 0,
        "completed_requests": 0,
        "rejected_requests": 0,
        "total_revenue": 0.0,
        "total_unfinished_requests": 0,
        "total_unfinished_value": 0.0,
        "warnings_count": 0,
        "by_type": [],
        "benchmark_comparison": [],
    }


def test_restore_ordered_months_cumulative_and_latest_policy(
    client,
    official_session_factory,
):
    _, _, _, official_session = _student_fixture_and_login(
        client,
        official_session_factory,
    )
    _store_months(official_session_factory, official_session, 2)

    response = client.get("/api/simulation/session")

    assert response.status_code == 200
    body = response.json()
    assert body["completed_months"] == 2
    assert body["next_month"] == 3
    assert body["status"] == "in_progress"
    assert [row["month"] for row in body["monthly_results"]] == [1, 2]
    assert body["cumulative"]["total_requests"] == 23
    assert body["cumulative"]["admitted_requests"] == 14
    assert body["cumulative"]["total_revenue"] == 300.75
    assert body["cumulative"]["total_unfinished_value"] == 76.5
    assert body["cumulative"]["warnings_count"] == 1
    assert body["latest_policy"]["policy_code"] == POLICY_B
    assert body["latest_policy"]["params"] == {"threshold": 2.0}
    assert body["latest_policy"]["policy_hash"] == body["monthly_results"][1]["policy_hash"]
    assert isinstance(body["monthly_results"][0]["total_revenue"], float)


def test_restore_completed_twelve_month_session(client, official_session_factory):
    _, _, _, official_session = _student_fixture_and_login(
        client,
        official_session_factory,
    )
    _store_months(official_session_factory, official_session, 12)

    body = client.get("/api/simulation/session").json()

    assert body["completed_months"] == 12
    assert body["next_month"] is None
    assert body["status"] == "completed"
    assert len(body["monthly_results"]) == 12


def test_run_month_one_persists_owned_result_and_advances_session(
    monkeypatch,
    client,
    official_session_factory,
):
    _, _, enrollment, official_session = _student_fixture_and_login(
        client,
        official_session_factory,
    )
    _install_fake_engine(monkeypatch)

    response = client.post(
        "/api/simulation/session/months/next",
        json=_request(1),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["replayed"] is False
    assert body["executed_month"] == 1
    assert body["session"]["completed_months"] == 1
    assert body["session"]["next_month"] == 2
    assert body["session"]["monthly_results"][0]["total_revenue"] == 100.25
    with official_session_factory() as session:
        stored = session.get(SimulationSession, official_session.id)
        assert stored is not None
        assert stored.enrollment_id == enrollment.id
        assert stored.completed_months == 1
        assert stored.last_completed_at is not None
        results = session.scalars(
            select(MonthlyResult).where(MonthlyResult.session_id == stored.id)
        ).all()
        assert len(results) == 1


def test_official_month_endpoint_runs_the_real_engine(
    client,
    official_session_factory,
):
    _student_fixture_and_login(client, official_session_factory)

    response = client.post(
        "/api/simulation/session/months/next",
        json=_request(1, policy_code=POLICY_A),
    )

    assert response.status_code == 201
    result = response.json()["session"]["monthly_results"][0]
    assert result["month"] == 1
    assert result["total_requests"] > 0
    assert result["admitted_requests"] == 0
    assert result["rejected_requests"] == result["total_requests"]
    assert {row["policy"] for row in result["benchmark_comparison"]}.issuperset(
        {"student_policy", "greedy_first_fit", "least_loaded", "best_fit", "vip_only"}
    )


def test_sequential_months_use_only_persisted_public_history(
    monkeypatch,
    client,
    official_session_factory,
):
    _student_fixture_and_login(client, official_session_factory)
    calls: list[dict[str, object]] = []
    _install_fake_engine(monkeypatch, calls)

    first = client.post(
        "/api/simulation/session/months/next",
        json=_request(1, policy_code=POLICY_A, params={"threshold": 1}),
    )
    second = client.post(
        "/api/simulation/session/months/next",
        json=_request(2, policy_code=POLICY_B, params={"threshold": 2}),
    )

    assert first.status_code == second.status_code == 201
    month_two_calls = [call for call in calls if call["month"] == 2]
    assert month_two_calls
    history = month_two_calls[0]["previous_months"]
    assert isinstance(history, list)
    assert len(history) == 1
    assert set(history[0]) == {
        "month",
        "total_requests",
        "admitted_requests",
        "completed_requests",
        "rejected_requests",
        "total_revenue",
        "unfinished_requests",
        "unfinished_value",
        "avg_utilization",
        "peak_utilization",
    }
    assert history[0]["month"] == 1
    assert "policy_code" not in history[0]
    assert "idempotency_key" not in history[0]


def test_different_month_policy_snapshots_are_preserved(
    monkeypatch,
    client,
    official_session_factory,
):
    _student_fixture_and_login(client, official_session_factory)
    _install_fake_engine(monkeypatch)

    client.post(
        "/api/simulation/session/months/next",
        json=_request(1, policy_code=POLICY_A, params={"threshold": 1}),
    )
    response = client.post(
        "/api/simulation/session/months/next",
        json=_request(2, policy_code=POLICY_B, params={"threshold": 2}),
    )

    rows = response.json()["session"]["monthly_results"]
    assert rows[0]["policy_code"] == POLICY_A
    assert rows[0]["params"] == {"threshold": 1.0}
    assert rows[1]["policy_code"] == POLICY_B
    assert rows[1]["params"] == {"threshold": 2.0}
    assert rows[0]["policy_hash"] != rows[1]["policy_hash"]


def test_cannot_skip_or_rerun_a_month(
    monkeypatch,
    client,
    official_session_factory,
):
    _, _, _, official_session = _student_fixture_and_login(
        client,
        official_session_factory,
    )
    _install_fake_engine(monkeypatch)

    skipped = client.post(
        "/api/simulation/session/months/next",
        json=_request(2),
    )
    first = client.post(
        "/api/simulation/session/months/next",
        json=_request(1),
    )
    rerun = client.post(
        "/api/simulation/session/months/next",
        json=_request(1),
    )

    assert skipped.status_code == 409
    assert skipped.json()["detail"]["code"] == "wrong_expected_month"
    assert first.status_code == 201
    assert rerun.status_code == 409
    assert rerun.json()["detail"]["code"] == "wrong_expected_month"
    with official_session_factory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(MonthlyResult)
            .where(MonthlyResult.session_id == official_session.id)
        ) == 1


def test_completed_session_rejects_month_thirteen(
    monkeypatch,
    client,
    official_session_factory,
):
    _, _, _, official_session = _student_fixture_and_login(
        client,
        official_session_factory,
    )
    _store_months(official_session_factory, official_session, 12)
    _install_fake_engine(monkeypatch)

    response = client.post(
        "/api/simulation/session/months/next",
        json=_request(13),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "session_completed"


def test_same_idempotency_request_replays_without_second_execution(
    monkeypatch,
    client,
    official_session_factory,
):
    _, _, _, official_session = _student_fixture_and_login(
        client,
        official_session_factory,
    )
    calls: list[dict[str, object]] = []
    _install_fake_engine(monkeypatch, calls)
    key = uuid.uuid4()
    body = _request(1, key=key, params={"b": 2, "a": 1})

    first = client.post("/api/simulation/session/months/next", json=body)
    replay = client.post("/api/simulation/session/months/next", json=body)

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["executed_month"] == 1
    assert len(calls) == 1 + len(simulation_persistence.BASELINE_POLICIES)
    with official_session_factory() as session:
        assert session.get(SimulationSession, official_session.id).completed_months == 1
        assert session.scalar(
            select(func.count()).select_from(MonthlyResult)
        ) == 1


@pytest.mark.parametrize(
    "changed",
    [
        {"expected_month": 1, "policy_code": POLICY_B, "params": {}},
        {"expected_month": 2, "policy_code": POLICY_A, "params": {}},
    ],
)
def test_conflicting_idempotency_reuse_returns_409(
    changed,
    monkeypatch,
    client,
    official_session_factory,
):
    _, _, _, official_session = _student_fixture_and_login(
        client,
        official_session_factory,
    )
    _install_fake_engine(monkeypatch)
    key = uuid.uuid4()
    first = _request(1, key=key)
    client.post("/api/simulation/session/months/next", json=first)
    conflict = _request(
        changed["expected_month"],
        key=key,
        policy_code=changed["policy_code"],
        params=changed["params"],
    )

    response = client.post(
        "/api/simulation/session/months/next",
        json=conflict,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "idempotency_key_conflict"
    with official_session_factory() as session:
        assert session.get(SimulationSession, official_session.id).completed_months == 1
        assert session.scalar(select(func.count()).select_from(MonthlyResult)) == 1


def test_two_concurrent_requests_advance_exactly_one_month(
    monkeypatch,
    app_factory,
    official_session_factory,
):
    student, course, enrollment, official_session = _create_student(
        official_session_factory,
    )
    assert official_session is not None
    started = threading.Event()
    release = threading.Event()
    call_count = 0
    call_count_lock = threading.Lock()

    def controlled_simulate_month(
        month,
        policy_fn,
        params,
        *,
        seed,
        previous_months,
    ):
        nonlocal call_count
        with call_count_lock:
            call_count += 1
            current_call = call_count
        if current_call == 1:
            started.set()
            assert release.wait(timeout=5)
        return _fake_month_result(month)

    monkeypatch.setattr(
        simulation_persistence,
        "simulate_month",
        controlled_simulate_month,
    )
    api = app_factory(_settings())
    with TestClient(api) as first_client, TestClient(api) as second_client:
        _authenticate_student(first_client, student, course, enrollment)
        _authenticate_student(second_client, student, course, enrollment)
        first_body = _request(1)
        second_body = _request(1)
        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(
                first_client.post,
                "/api/simulation/session/months/next",
                json=first_body,
            )
            assert started.wait(timeout=5)
            second_future = executor.submit(
                second_client.post,
                "/api/simulation/session/months/next",
                json=second_body,
            )
            time.sleep(0.2)
            release.set()
            responses = [first_future.result(), second_future.result()]

    assert sorted(response.status_code for response in responses) == [201, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["detail"]["code"] == "wrong_expected_month"
    with official_session_factory() as session:
        stored = session.get(SimulationSession, official_session.id)
        assert stored is not None
        assert stored.completed_months == 1
        assert session.scalar(select(func.count()).select_from(MonthlyResult)) == 1


def test_policy_compile_failure_rolls_back(monkeypatch, client, official_session_factory):
    _, _, _, official_session = _student_fixture_and_login(
        client,
        official_session_factory,
    )
    _install_fake_engine(monkeypatch)

    response = client.post(
        "/api/simulation/session/months/next",
        json=_request(1, policy_code="this is not valid python"),
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_policy"
    with official_session_factory() as session:
        assert session.get(SimulationSession, official_session.id).completed_months == 0
        assert session.scalar(select(func.count()).select_from(MonthlyResult)) == 0


def test_simulation_exception_rolls_back(monkeypatch, client, official_session_factory):
    _, _, _, official_session = _student_fixture_and_login(
        client,
        official_session_factory,
    )

    def fail_simulation(*args, **kwargs):
        raise RuntimeError("forced simulation failure")

    monkeypatch.setattr(simulation_persistence, "simulate_month", fail_simulation)
    response = client.post(
        "/api/simulation/session/months/next",
        json=_request(1),
    )

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "official_simulation_unavailable"
    with official_session_factory() as session:
        assert session.get(SimulationSession, official_session.id).completed_months == 0
        assert session.scalar(select(func.count()).select_from(MonthlyResult)) == 0


def test_constraint_failure_rolls_back(monkeypatch, client, official_session_factory):
    _, _, _, official_session = _student_fixture_and_login(
        client,
        official_session_factory,
    )

    def invalid_result(month, policy_fn, params, *, seed, previous_months):
        result = _fake_month_result(month)
        result["rejected_requests"] = 999
        return result

    monkeypatch.setattr(simulation_persistence, "simulate_month", invalid_result)
    response = client.post(
        "/api/simulation/session/months/next",
        json=_request(1),
    )

    assert response.status_code == 500
    with official_session_factory() as session:
        assert session.get(SimulationSession, official_session.id).completed_months == 0
        assert session.scalar(select(func.count()).select_from(MonthlyResult)) == 0


def test_commit_failure_rolls_back(monkeypatch, client, official_session_factory):
    _, _, _, official_session = _student_fixture_and_login(
        client,
        official_session_factory,
    )
    _install_fake_engine(monkeypatch)
    original_commit = Session.commit

    def fail_commit(session):
        raise SQLAlchemyError("forced commit failure")

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = client.post(
        "/api/simulation/session/months/next",
        json=_request(1),
    )
    monkeypatch.setattr(Session, "commit", original_commit)

    assert response.status_code == 500
    with official_session_factory() as session:
        assert session.get(SimulationSession, official_session.id).completed_months == 0
        assert session.scalar(select(func.count()).select_from(MonthlyResult)) == 0


def test_authentication_and_student_role_are_required(
    client,
    official_session_factory,
):
    unauthenticated_get = client.get("/api/simulation/session")
    unauthenticated_post = client.post(
        "/api/simulation/session/months/next",
        json=_request(1),
    )
    instructor = _create_instructor(official_session_factory)
    _authenticate_instructor(client, instructor)
    instructor_get = client.get("/api/simulation/session")
    instructor_post = client.post(
        "/api/simulation/session/months/next",
        json=_request(1),
    )

    assert unauthenticated_get.status_code == 401
    assert unauthenticated_post.status_code == 401
    assert instructor_get.status_code == 403
    assert instructor_post.status_code == 403


def test_request_forbids_authoritative_or_foreign_state(
    client,
    official_session_factory,
):
    _student_fixture_and_login(client, official_session_factory)
    body = _request(1)
    body.update(
        {
            "month": 1,
            "previous_months": [],
            "course_id": str(uuid.uuid4()),
            "enrollment_id": str(uuid.uuid4()),
            "session_id": str(uuid.uuid4()),
            "seed": 123,
            "total_revenue": 999999,
        }
    )

    response = client.post(
        "/api/simulation/session/months/next",
        json=body,
    )

    assert response.status_code == 422
    locations = {error["loc"][-1] for error in response.json()["detail"]}
    assert {
        "month",
        "previous_months",
        "course_id",
        "enrollment_id",
        "session_id",
        "seed",
        "total_revenue",
    }.issubset(locations)


def test_missing_session_is_server_integrity_error(client, official_session_factory):
    student, course, enrollment, _ = _create_student(
        official_session_factory,
        with_session=False,
    )
    _authenticate_student(client, student, course, enrollment)

    response = client.get("/api/simulation/session")

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "official_simulation_unavailable"


def test_student_restoration_never_exposes_another_students_policy(
    client,
    official_session_factory,
):
    _, _, _, own_session = _student_fixture_and_login(
        client,
        official_session_factory,
        suffix="own",
    )
    _, _, _, other_session = _create_student(
        official_session_factory,
        suffix="other",
    )
    assert other_session is not None
    _store_months(official_session_factory, own_session, 1)
    _store_months(official_session_factory, other_session, 1)
    secret_policy = "def admission_policy(request, state, history, params):\n    return 7\n# OTHER_SECRET"
    with official_session_factory() as session:
        other_result = session.scalar(
            select(MonthlyResult).where(MonthlyResult.session_id == other_session.id)
        )
        assert other_result is not None
        other_result.policy_code = secret_policy
        other_result.policy_hash = simulation_persistence.calculate_policy_hash(
            secret_policy,
            other_result.policy_params,
        )
        session.commit()

    response = client.get("/api/simulation/session")

    assert response.status_code == 200
    assert "OTHER_SECRET" not in response.text
    assert response.json()["session_id"] == str(own_session.id)


def test_policy_hash_is_stable_for_param_order_and_preserves_source_identity():
    first = simulation_persistence.calculate_policy_hash(
        POLICY_A,
        {"beta": 2, "alpha": 1},
    )
    reordered = simulation_persistence.calculate_policy_hash(
        POLICY_A,
        {"alpha": 1.0, "beta": 2.0},
    )
    changed_source = simulation_persistence.calculate_policy_hash(
        POLICY_A + "\n",
        {"alpha": 1, "beta": 2},
    )

    assert first == reordered
    assert first != changed_source
    assert len(first) == 64
