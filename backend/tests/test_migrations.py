from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from alembic import command
from alembic.migration import MigrationContext
from sqlalchemy import Engine, Integer, Numeric, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError

from tests.conftest import validate_test_database_url


HEAD_REVISION = "0005_llm_daily_usage"
EXPECTED_TABLES = {
    "users",
    "course_instances",
    "enrollments",
    "submissions",
    "simulation_sessions",
    "monthly_results",
    "llm_daily_usage",
}


def _current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _table_names(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def _seed_account(
    engine: Engine,
    suffix: str,
    *,
    with_submission: bool = False,
) -> dict[str, uuid.UUID]:
    ids = {
        "instructor_id": uuid.uuid4(),
        "student_id": uuid.uuid4(),
        "course_id": uuid.uuid4(),
        "enrollment_id": uuid.uuid4(),
        "submission_id": uuid.uuid4(),
    }
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, berkeley_username, role) "
                "VALUES (:id, :username, 'instructor')"
            ),
            {
                "id": ids["instructor_id"],
                "username": f"migration-instructor-{suffix}",
            },
        )
        connection.execute(
            text(
                "INSERT INTO users (id, berkeley_username, role) "
                "VALUES (:id, :username, 'student')"
            ),
            {
                "id": ids["student_id"],
                "username": f"migration-student-{suffix}",
            },
        )
        connection.execute(
            text(
                "INSERT INTO course_instances "
                "(id, course_code, course_name, semester, created_by) "
                "VALUES (:id, :code, 'Migration Test', 'Fall 2026', :owner)"
            ),
            {
                "id": ids["course_id"],
                "code": f"MIG-{suffix}",
                "owner": ids["instructor_id"],
            },
        )
        connection.execute(
            text(
                "INSERT INTO enrollments "
                "(id, course_id, user_id, nickname, status) "
                "VALUES (:id, :course_id, :user_id, :nickname, 'active')"
            ),
            {
                "id": ids["enrollment_id"],
                "course_id": ids["course_id"],
                "user_id": ids["student_id"],
                "nickname": f"Student {suffix}",
            },
        )
        if with_submission:
            connection.execute(
                text(
                    "INSERT INTO submissions "
                    "(id, enrollment_id, total_revenue, "
                    "total_unfinished_requests, total_unfinished_value, warnings_count) "
                    "VALUES (:id, :enrollment_id, 1234.5, 2, 75.25, 1)"
                ),
                {
                    "id": ids["submission_id"],
                    "enrollment_id": ids["enrollment_id"],
                },
            )
    return ids


def _insert_session(
    engine: Engine,
    enrollment_id: uuid.UUID,
    *,
    completed_months: int = 0,
) -> uuid.UUID:
    session_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO simulation_sessions "
                "(id, enrollment_id, completed_months) "
                "VALUES (:id, :enrollment_id, :completed_months)"
            ),
            {
                "id": session_id,
                "enrollment_id": enrollment_id,
                "completed_months": completed_months,
            },
        )
    return session_id


def _monthly_result_values(
    session_id: uuid.UUID,
    *,
    month: int = 1,
    idempotency_key: uuid.UUID | None = None,
) -> dict[str, object]:
    return {
        "id": uuid.uuid4(),
        "session_id": session_id,
        "month": month,
        "idempotency_key": idempotency_key or uuid.uuid4(),
        "policy_code": "def admission_policy(request, clusters, params, history): return None",
        "policy_params": "{}",
        "policy_hash": "a" * 64,
        "total_requests": 10,
        "admitted_requests": 7,
        "completed_requests": 5,
        "rejected_requests": 3,
        "total_revenue": Decimal("100.25"),
        "unfinished_requests": 2,
        "unfinished_value": Decimal("25.50"),
        "avg_utilization": "{}",
        "peak_utilization": "{}",
        "remaining_capacity": "{}",
        "by_type": "[]",
        "warnings": "[]",
        "benchmark_comparison": "[]",
    }


def _insert_monthly_result(engine: Engine, values: dict[str, object]) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO monthly_results "
                "(id, session_id, month, idempotency_key, policy_code, policy_params, "
                "policy_hash, total_requests, admitted_requests, completed_requests, "
                "rejected_requests, total_revenue, unfinished_requests, unfinished_value, "
                "avg_utilization, peak_utilization, remaining_capacity, by_type, warnings, "
                "benchmark_comparison) VALUES "
                "(:id, :session_id, :month, :idempotency_key, :policy_code, "
                "CAST(:policy_params AS jsonb), :policy_hash, :total_requests, "
                ":admitted_requests, :completed_requests, :rejected_requests, "
                ":total_revenue, :unfinished_requests, :unfinished_value, "
                "CAST(:avg_utilization AS jsonb), CAST(:peak_utilization AS jsonb), "
                "CAST(:remaining_capacity AS jsonb), CAST(:by_type AS jsonb), "
                "CAST(:warnings AS jsonb), CAST(:benchmark_comparison AS jsonb))"
            ),
            values,
        )


@pytest.mark.parametrize(
    "database_name",
    ["resource_allocation", "postgres", "template0", "template1", "another_database"],
)
def test_destructive_database_guard_rejects_non_test_names(database_name):
    with pytest.raises(pytest.UsageError, match="ending exactly in '_test'"):
        validate_test_database_url(f"postgresql+psycopg:///{database_name}")


def test_fresh_upgrade_downgrade_and_reupgrade(
    test_alembic_config,
    test_engine: Engine,
    test_database_url: URL,
):
    assert test_database_url.database is not None
    assert test_database_url.database.endswith("_test")

    try:
        command.downgrade(test_alembic_config, "base")
        assert EXPECTED_TABLES.isdisjoint(_table_names(test_engine))
        assert _current_revision(test_engine) is None

        command.upgrade(test_alembic_config, "head")
        assert EXPECTED_TABLES.issubset(_table_names(test_engine))
        assert _current_revision(test_engine) == HEAD_REVISION

        with test_engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM simulation_sessions")) == 0
            assert connection.scalar(text("SELECT count(*) FROM monthly_results")) == 0

        command.downgrade(test_alembic_config, "base")
        assert EXPECTED_TABLES.isdisjoint(_table_names(test_engine))
        assert _current_revision(test_engine) is None
    finally:
        command.upgrade(test_alembic_config, "head")

    assert _current_revision(test_engine) == HEAD_REVISION


def test_0003_backfills_existing_0002_submissions_and_0004_creates_empty_session(
    test_alembic_config,
    test_engine: Engine,
):
    try:
        command.downgrade(test_alembic_config, "base")
        command.upgrade(test_alembic_config, "0002_submissions")
        ids = _seed_account(test_engine, "legacy", with_submission=True)

        command.upgrade(test_alembic_config, "0003_months_completed")

        columns = {column["name"]: column for column in inspect(test_engine).get_columns("submissions")}
        months_completed = columns["months_completed"]
        assert isinstance(months_completed["type"], Integer)
        assert months_completed["nullable"] is False
        assert months_completed["default"] is None
        with test_engine.connect() as connection:
            assert connection.scalar(
                text("SELECT months_completed FROM submissions WHERE id = :id"),
                {"id": ids["submission_id"]},
            ) == 12

        command.upgrade(test_alembic_config, "head")
        with test_engine.connect() as connection:
            session = connection.execute(
                text(
                    "SELECT completed_months FROM simulation_sessions "
                    "WHERE enrollment_id = :enrollment_id"
                ),
                {"enrollment_id": ids["enrollment_id"]},
            ).one()
            assert session.completed_months == 0
            assert connection.scalar(text("SELECT count(*) FROM monthly_results")) == 0
    finally:
        command.downgrade(test_alembic_config, "base")
        command.upgrade(test_alembic_config, "head")


def test_production_shaped_0003_upgrades_only_0004_and_preserves_legacy_row(
    test_alembic_config,
    test_engine: Engine,
):
    try:
        command.downgrade(test_alembic_config, "base")
        command.upgrade(test_alembic_config, "0002_submissions")
        ids = _seed_account(test_engine, "production", with_submission=True)
        command.upgrade(test_alembic_config, "0003_months_completed")
        assert _current_revision(test_engine) == "0003_months_completed"

        with test_engine.connect() as connection:
            before = connection.execute(
                text(
                    "SELECT total_revenue, total_unfinished_requests, "
                    "total_unfinished_value, warnings_count, months_completed "
                    "FROM submissions WHERE id = :id"
                ),
                {"id": ids["submission_id"]},
            ).one()

        command.upgrade(test_alembic_config, "head")
        assert _current_revision(test_engine) == HEAD_REVISION
        with test_engine.connect() as connection:
            after = connection.execute(
                text(
                    "SELECT total_revenue, total_unfinished_requests, "
                    "total_unfinished_value, warnings_count, months_completed "
                    "FROM submissions WHERE id = :id"
                ),
                {"id": ids["submission_id"]},
            ).one()
            assert after == before
            assert connection.scalar(
                text(
                    "SELECT count(*) FROM simulation_sessions "
                    "WHERE enrollment_id = :enrollment_id AND completed_months = 0"
                ),
                {"enrollment_id": ids["enrollment_id"]},
            ) == 1
            assert connection.scalar(text("SELECT count(*) FROM monthly_results")) == 0
    finally:
        command.downgrade(test_alembic_config, "base")
        command.upgrade(test_alembic_config, "head")


def test_0004_schema_constraints_indexes_and_money_types(
    test_alembic_config,
    test_engine: Engine,
):
    command.upgrade(test_alembic_config, "head")
    inspector = inspect(test_engine)

    session_uniques = {
        item["name"] for item in inspector.get_unique_constraints("simulation_sessions")
    }
    result_uniques = {
        item["name"] for item in inspector.get_unique_constraints("monthly_results")
    }
    session_checks = {
        item["name"] for item in inspector.get_check_constraints("simulation_sessions")
    }
    result_checks = {
        item["name"] for item in inspector.get_check_constraints("monthly_results")
    }
    assert "uq_simulation_sessions_enrollment_id" in session_uniques
    assert "uq_monthly_results_session_month" in result_uniques
    assert "uq_monthly_results_session_idempotency_key" in result_uniques
    assert "ck_simulation_sessions_completed_months_range" in session_checks
    assert "ck_monthly_results_month_range" in result_checks
    assert "ck_monthly_results_policy_params_object" in result_checks

    session_fks = inspector.get_foreign_keys("simulation_sessions")
    result_fks = inspector.get_foreign_keys("monthly_results")
    assert session_fks[0]["referred_table"] == "enrollments"
    assert session_fks[0]["options"].get("ondelete") == "RESTRICT"
    assert result_fks[0]["referred_table"] == "simulation_sessions"
    assert result_fks[0]["options"].get("ondelete") == "RESTRICT"

    columns = {column["name"]: column for column in inspector.get_columns("monthly_results")}
    for name in ("total_revenue", "unfinished_value"):
        column_type = columns[name]["type"]
        assert isinstance(column_type, Numeric)
        assert column_type.precision == 18
        assert column_type.scale == 2


def test_0004_uniqueness_ranges_and_restrict_fks_are_enforced(
    test_alembic_config,
    test_engine: Engine,
):
    try:
        command.downgrade(test_alembic_config, "base")
        command.upgrade(test_alembic_config, "head")
        first = _seed_account(test_engine, "constraints-a")
        second = _seed_account(test_engine, "constraints-b")
        first_session = _insert_session(test_engine, first["enrollment_id"])

        with pytest.raises(IntegrityError):
            _insert_session(test_engine, first["enrollment_id"])
        with pytest.raises(IntegrityError):
            _insert_session(
                test_engine,
                second["enrollment_id"],
                completed_months=13,
            )

        idempotency_key = uuid.uuid4()
        _insert_monthly_result(
            test_engine,
            _monthly_result_values(
                first_session,
                month=1,
                idempotency_key=idempotency_key,
            ),
        )
        with pytest.raises(IntegrityError):
            _insert_monthly_result(
                test_engine,
                _monthly_result_values(first_session, month=1),
            )
        with pytest.raises(IntegrityError):
            _insert_monthly_result(
                test_engine,
                _monthly_result_values(
                    first_session,
                    month=2,
                    idempotency_key=idempotency_key,
                ),
            )
        with pytest.raises(IntegrityError):
            _insert_monthly_result(
                test_engine,
                _monthly_result_values(first_session, month=13),
            )

        with pytest.raises(IntegrityError), test_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM simulation_sessions WHERE id = :id"),
                {"id": first_session},
            )
        with pytest.raises(IntegrityError), test_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM enrollments WHERE id = :id"),
                {"id": first["enrollment_id"]},
            )
    finally:
        command.downgrade(test_alembic_config, "base")
        command.upgrade(test_alembic_config, "head")


def test_alembic_check_reports_no_drift(test_alembic_config):
    command.upgrade(test_alembic_config, "head")

    command.check(test_alembic_config)
