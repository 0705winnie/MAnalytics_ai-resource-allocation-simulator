import uuid

import pytest
from alembic import command
from sqlalchemy import DateTime, Engine, Enum, Numeric, Uuid, delete
from sqlalchemy.engine import URL
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import (
    CourseInstance,
    Enrollment,
    MonthlyResult,
    SimulationSession,
    Submission,
    User,
)
from app.models.enums import EnrollmentStatus, UserRole


EXPECTED_COLUMNS = {
    "users": {
        "id",
        "berkeley_username",
        "password_hash",
        "role",
        "is_active",
        "created_at",
        "updated_at",
    },
    "course_instances": {
        "id",
        "course_code",
        "course_code_normalized",
        "course_name",
        "semester",
        "created_by",
        "is_active",
        "created_at",
        "updated_at",
    },
    "enrollments": {
        "id",
        "course_id",
        "user_id",
        "nickname",
        "nickname_normalized",
        "activation_code_hash",
        "activation_expires_at",
        "activation_used_at",
        "status",
        "created_at",
        "updated_at",
    },
    "submissions": {
        "id",
        "enrollment_id",
        "total_revenue",
        "total_unfinished_requests",
        "total_unfinished_value",
        "warnings_count",
        "months_completed",
        "submitted_at",
    },
    "simulation_sessions": {
        "id",
        "enrollment_id",
        "completed_months",
        "created_at",
        "updated_at",
        "last_completed_at",
    },
    "monthly_results": {
        "id",
        "session_id",
        "month",
        "idempotency_key",
        "policy_code",
        "policy_params",
        "policy_hash",
        "total_requests",
        "admitted_requests",
        "completed_requests",
        "rejected_requests",
        "total_revenue",
        "unfinished_requests",
        "unfinished_value",
        "avg_utilization",
        "peak_utilization",
        "remaining_capacity",
        "by_type",
        "warnings",
        "benchmark_comparison",
        "completed_at",
    },
}


def _clear_account_tables(session: Session, test_database_url: URL) -> None:
    assert test_database_url.database is not None
    assert test_database_url.database.endswith("_test")
    session.execute(delete(MonthlyResult))
    session.execute(delete(SimulationSession))
    session.execute(delete(Submission))
    session.execute(delete(Enrollment))
    session.execute(delete(CourseInstance))
    session.execute(delete(User))
    session.commit()


@pytest.fixture(scope="module", autouse=True)
def account_schema(test_alembic_config):
    command.upgrade(test_alembic_config, "head")


@pytest.fixture
def db_session(test_engine: Engine, test_database_url: URL):
    with Session(test_engine) as session:
        _clear_account_tables(session, test_database_url)
        yield session
        session.rollback()
        _clear_account_tables(session, test_database_url)


def _new_user(username: str, role: UserRole = UserRole.STUDENT) -> User:
    return User(berkeley_username=username, role=role)


def _new_course(creator: User, code: str) -> CourseInstance:
    return CourseInstance(
        course_code=code,
        course_name="Resource Allocation",
        semester="Fall 2026",
        creator=creator,
    )


def test_metadata_contains_expected_tables_and_columns():
    assert set(Base.metadata.tables) == set(EXPECTED_COLUMNS)
    for table_name, columns in EXPECTED_COLUMNS.items():
        assert set(Base.metadata.tables[table_name].columns.keys()) == columns


@pytest.mark.parametrize("table_name", EXPECTED_COLUMNS)
def test_primary_keys_use_python_uuid_defaults(table_name):
    id_column = Base.metadata.tables[table_name].c.id

    assert id_column.primary_key
    assert isinstance(id_column.type, Uuid)
    assert id_column.type.as_uuid is True
    assert id_column.default is not None
    assert id_column.default.is_callable


def test_required_and_nullable_columns():
    users = Base.metadata.tables["users"].c
    courses = Base.metadata.tables["course_instances"].c
    enrollments = Base.metadata.tables["enrollments"].c
    submissions = Base.metadata.tables["submissions"].c
    simulation_sessions = Base.metadata.tables["simulation_sessions"].c
    monthly_results = Base.metadata.tables["monthly_results"].c

    assert users.berkeley_username.nullable is False
    assert users.password_hash.nullable is True
    assert users.role.nullable is False
    assert users.is_active.nullable is False

    for name in ("course_code", "course_code_normalized", "course_name", "semester", "created_by"):
        assert courses[name].nullable is False

    assert enrollments.course_id.nullable is False
    assert enrollments.user_id.nullable is False
    for name in (
        "nickname",
        "nickname_normalized",
        "activation_code_hash",
        "activation_expires_at",
        "activation_used_at",
    ):
        assert enrollments[name].nullable is True
    assert enrollments.status.nullable is False
    assert submissions.months_completed.nullable is False
    assert simulation_sessions.enrollment_id.nullable is False
    assert simulation_sessions.completed_months.nullable is False
    assert simulation_sessions.last_completed_at.nullable is True
    assert all(column.nullable is False for column in monthly_results)


def test_simulation_money_columns_use_exact_two_decimal_numeric_type():
    monthly_results = Base.metadata.tables["monthly_results"].c

    for name in ("total_revenue", "unfinished_value"):
        column_type = monthly_results[name].type
        assert isinstance(column_type, Numeric)
        assert column_type.precision == 18
        assert column_type.scale == 2


def test_enum_columns_use_explicit_check_constraints_and_defaults():
    users = Base.metadata.tables["users"]
    enrollments = Base.metadata.tables["enrollments"]
    role = users.c.role
    status = enrollments.c.status

    assert isinstance(role.type, Enum)
    assert role.type.native_enum is False
    assert role.type.create_constraint is False
    assert role.type.validate_strings is True
    assert role.type.enums == ["student", "instructor"]
    assert str(role.server_default.arg) == UserRole.STUDENT.value
    assert "user_role" in {constraint.name for constraint in users.constraints}

    assert isinstance(status.type, Enum)
    assert status.type.native_enum is False
    assert status.type.create_constraint is False
    assert status.type.validate_strings is True
    assert status.type.enums == ["pending", "active", "disabled"]
    assert str(status.server_default.arg) == EnrollmentStatus.PENDING.value
    assert "enrollment_status" in {
        constraint.name for constraint in enrollments.constraints
    }


def test_timestamp_columns_are_timezone_aware_and_server_defaulted():
    timestamp_columns = {
        "users": ("created_at", "updated_at"),
        "course_instances": ("created_at", "updated_at"),
        "enrollments": (
            "activation_expires_at",
            "activation_used_at",
            "created_at",
            "updated_at",
        ),
        "submissions": ("submitted_at",),
        "simulation_sessions": (
            "created_at",
            "updated_at",
            "last_completed_at",
        ),
        "monthly_results": ("completed_at",),
    }

    for table_name, column_names in timestamp_columns.items():
        columns = Base.metadata.tables[table_name].c
        for column_name in column_names:
            column = columns[column_name]
            assert isinstance(column.type, DateTime)
            assert column.type.timezone is True
            if column_name in {"created_at", "updated_at", "submitted_at", "completed_at"}:
                assert column.server_default is not None


def test_foreign_keys_use_restrict_and_relationships_have_no_delete_cascade():
    courses = Base.metadata.tables["course_instances"].c
    enrollments = Base.metadata.tables["enrollments"].c
    submissions = Base.metadata.tables["submissions"].c
    simulation_sessions = Base.metadata.tables["simulation_sessions"].c
    monthly_results = Base.metadata.tables["monthly_results"].c

    assert next(iter(courses.created_by.foreign_keys)).ondelete == "RESTRICT"
    assert next(iter(enrollments.course_id.foreign_keys)).ondelete == "RESTRICT"
    assert next(iter(enrollments.user_id.foreign_keys)).ondelete == "RESTRICT"
    assert next(iter(submissions.enrollment_id.foreign_keys)).ondelete == "RESTRICT"
    assert next(iter(simulation_sessions.enrollment_id.foreign_keys)).ondelete == "RESTRICT"
    assert next(iter(monthly_results.session_id.foreign_keys)).ondelete == "RESTRICT"

    for relationship in (
        User.created_courses.property,
        User.enrollments.property,
        CourseInstance.enrollments.property,
        Enrollment.simulation_session.property,
        SimulationSession.monthly_results.property,
    ):
        assert "delete" not in relationship.cascade
        assert "delete-orphan" not in relationship.cascade


@pytest.mark.parametrize(
    "username",
    ["", "UPPERCASE", " leading-space", "trailing-space "],
)
def test_invalid_normalized_usernames_are_rejected(db_session, username):
    db_session.add(_new_user(username))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_overlength_username_is_rejected(db_session):
    db_session.add(_new_user("a" * 65))

    with pytest.raises(DataError):
        db_session.commit()


def test_username_is_unique(db_session):
    db_session.add(_new_user("student"))
    db_session.commit()
    db_session.add(_new_user("student"))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_course_code_is_normalized_and_case_insensitively_unique(db_session):
    instructor = _new_user("instructor", UserRole.INSTRUCTOR)
    course = _new_course(instructor, "IEOR150-Fall2026")
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    assert course.course_code == "IEOR150-Fall2026"
    assert course.course_code_normalized == "ieor150-fall2026"

    db_session.add(_new_course(instructor, "  ieor150-fall2026  "))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_user_can_enroll_only_once_per_course(db_session):
    instructor = _new_user("instructor", UserRole.INSTRUCTOR)
    student = _new_user("student")
    course = _new_course(instructor, "IEOR150-Fall2026")
    db_session.add_all([instructor, student, course])
    db_session.flush()
    db_session.add(Enrollment(course=course, user=student, nickname="First Name"))
    db_session.commit()

    db_session.add(Enrollment(course=course, user=student, nickname="Second Name"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_nickname_is_case_insensitively_unique_within_course(db_session):
    instructor = _new_user("instructor", UserRole.INSTRUCTOR)
    first_student = _new_user("firststudent")
    second_student = _new_user("secondstudent")
    course = _new_course(instructor, "IEOR150-Fall2026")
    db_session.add_all([instructor, first_student, second_student, course])
    db_session.flush()

    enrollment = Enrollment(course=course, user=first_student, nickname="Golden Bear")
    db_session.add(enrollment)
    db_session.commit()
    db_session.refresh(enrollment)
    assert enrollment.nickname_normalized == "golden bear"

    db_session.add(Enrollment(course=course, user=second_student, nickname="golden bear"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_same_nickname_may_exist_in_different_courses(db_session):
    instructor = _new_user("instructor", UserRole.INSTRUCTOR)
    student = _new_user("student")
    first_course = _new_course(instructor, "IEOR150-Fall2026")
    second_course = _new_course(instructor, "IEOR150-Spring2027")
    db_session.add_all([instructor, student, first_course, second_course])
    db_session.flush()
    db_session.add_all(
        [
            Enrollment(course=first_course, user=student, nickname="Golden Bear"),
            Enrollment(course=second_course, user=student, nickname="golden bear"),
        ]
    )
    db_session.commit()

    enrollments = db_session.query(Enrollment).all()
    assert len(enrollments) == 2
    assert all(isinstance(enrollment.id, uuid.UUID) for enrollment in enrollments)
