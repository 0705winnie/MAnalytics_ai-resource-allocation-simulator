from collections.abc import Generator

import pytest
from alembic import command
from pydantic import SecretStr
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DevelopmentInstructorSettings
from app.core.security import hash_password, verify_password
from app.models import User
from app.models.enums import UserRole
from scripts.seed_instructor import (
    InstructorSeedError,
    main,
    require_seed_credentials,
    seed_instructor,
)


TEST_USERNAMES = {
    "phase1c-instructor",
    "phase1c-disabled",
    "phase1c-student",
    "phase1c-output",
}


@pytest.fixture(scope="module", autouse=True)
def account_schema(test_alembic_config):
    command.upgrade(test_alembic_config, "head")


@pytest.fixture
def db_session(
    test_engine: Engine,
    test_database_url,
) -> Generator[Session, None, None]:
    assert test_database_url.database is not None
    assert test_database_url.database.endswith("_test")

    with Session(test_engine) as session:
        session.execute(
            delete(User).where(User.berkeley_username.in_(TEST_USERNAMES))
        )
        session.commit()
        yield session
        session.rollback()
        session.execute(
            delete(User).where(User.berkeley_username.in_(TEST_USERNAMES))
        )
        session.commit()


def test_seed_creates_active_instructor_with_normalized_username(db_session):
    result = seed_instructor(
        db_session,
        "  PHASE1C-INSTRUCTOR  ",
        "instructor-test-password",
    )
    db_session.commit()

    assert result.created is True
    assert result.user.berkeley_username == "phase1c-instructor"
    assert result.user.role == UserRole.INSTRUCTOR
    assert result.user.is_active is True
    assert result.user.password_hash is not None
    assert verify_password("instructor-test-password", result.user.password_hash)


def test_repeated_seed_is_idempotent_and_preserves_password_hash(db_session):
    first = seed_instructor(
        db_session,
        "phase1c-instructor",
        "original-password",
    )
    db_session.commit()
    original_hash = first.user.password_hash

    second = seed_instructor(
        db_session,
        "PHASE1C-INSTRUCTOR",
        "different-password",
    )
    db_session.commit()

    count = db_session.scalar(
        select(func.count())
        .select_from(User)
        .where(User.berkeley_username == "phase1c-instructor")
    )
    assert second.created is False
    assert count == 1
    assert second.user.password_hash == original_hash


def test_seed_rejects_username_owned_by_student(db_session):
    student = User(
        berkeley_username="phase1c-student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(student)
    db_session.commit()

    with pytest.raises(InstructorSeedError, match="non-instructor"):
        seed_instructor(db_session, "PHASE1C-STUDENT", "unused-password")

    assert student.role == UserRole.STUDENT
    assert student.password_hash is None


def test_seed_rejects_disabled_instructor_without_changing_hash(db_session):
    original_hash = hash_password("disabled-password")
    instructor = User(
        berkeley_username="phase1c-disabled",
        password_hash=original_hash,
        role=UserRole.INSTRUCTOR,
        is_active=False,
    )
    db_session.add(instructor)
    db_session.commit()

    with pytest.raises(InstructorSeedError, match="instructor is disabled"):
        seed_instructor(
            db_session,
            "PHASE1C-DISABLED",
            "replacement-password",
        )

    db_session.refresh(instructor)
    assert instructor.is_active is False
    assert instructor.password_hash == original_hash


def test_missing_seed_configuration_fails_without_opening_database(capsys):
    settings = DevelopmentInstructorSettings(
        _env_file=None,
        dev_instructor_username=None,
        dev_instructor_password=None,
    )

    def unexpected_session():
        raise AssertionError("database session should not be opened")

    assert main(settings=settings, session_factory=unexpected_session) == 1
    captured = capsys.readouterr()
    assert "DEV_INSTRUCTOR_USERNAME" in captured.err


def test_missing_password_fails_without_opening_database(capsys):
    settings = DevelopmentInstructorSettings(
        _env_file=None,
        dev_instructor_username="phase1c-instructor",
        dev_instructor_password=None,
    )

    def unexpected_session():
        raise AssertionError("database session should not be opened")

    assert main(settings=settings, session_factory=unexpected_session) == 1
    captured = capsys.readouterr()
    assert "DEV_INSTRUCTOR_PASSWORD" in captured.err


def test_short_password_is_rejected_by_settings_and_core(db_session):
    settings = DevelopmentInstructorSettings(
        _env_file=None,
        dev_instructor_username="phase1c-instructor",
        dev_instructor_password=SecretStr("too-short"),
    )

    with pytest.raises(InstructorSeedError, match="at least 12 characters"):
        require_seed_credentials(settings)
    with pytest.raises(InstructorSeedError, match="at least 12 characters"):
        seed_instructor(db_session, "phase1c-instructor", "too-short")


def test_development_settings_normalize_username():
    settings = DevelopmentInstructorSettings(
        _env_file=None,
        dev_instructor_username="  PHASE1C-INSTRUCTOR  ",
        dev_instructor_password=SecretStr("settings-test-password"),
    )

    assert settings.dev_instructor_username == "phase1c-instructor"


def test_seed_output_does_not_expose_password_or_hash(
    test_engine: Engine,
    test_database_url,
    db_session,
    capsys,
):
    assert test_database_url.database is not None
    assert test_database_url.database.endswith("_test")
    password = "output-test-password"
    settings = DevelopmentInstructorSettings(
        _env_file=None,
        dev_instructor_username="phase1c-output",
        dev_instructor_password=SecretStr(password),
    )
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)

    assert main(settings=settings, session_factory=factory) == 0
    captured = capsys.readouterr()
    output = captured.out + captured.err

    assert password not in output
    assert "password_hash" not in output
    assert "$argon2" not in output
