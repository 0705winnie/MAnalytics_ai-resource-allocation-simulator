import re
from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from sqlalchemy import Engine, delete
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.models import CourseInstance, Enrollment, User
from app.models.enums import EnrollmentStatus, UserRole
from app.services import activation_codes
from app.services.activation_codes import (
    ACTIVATION_CODE_ALPHABET,
    ACTIVATION_CODE_TTL,
    ActivationCodeError,
    generate_activation_code,
    issue_activation_code,
    mark_activation_used,
    regenerate_activation_code,
    verify_activation_code,
)


FIXED_NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def _clear_account_tables(session: Session, test_database_url: URL) -> None:
    assert test_database_url.database is not None
    assert test_database_url.database.endswith("_test")
    session.execute(delete(Enrollment))
    session.execute(delete(CourseInstance))
    session.execute(delete(User))
    session.commit()


@pytest.fixture(scope="module", autouse=True)
def account_schema(test_alembic_config):
    command.upgrade(test_alembic_config, "head")


@pytest.fixture
def db_session(
    test_engine: Engine,
    test_database_url: URL,
) -> Generator[Session, None, None]:
    with Session(test_engine) as session:
        _clear_account_tables(session, test_database_url)
        yield session
        session.rollback()
        _clear_account_tables(session, test_database_url)


@pytest.fixture
def enrollment_factory(
    db_session: Session,
) -> Callable[..., Enrollment]:
    def create_enrollment(
        status: EnrollmentStatus = EnrollmentStatus.PENDING,
    ) -> Enrollment:
        instructor = User(
            berkeley_username="activation-instructor",
            role=UserRole.INSTRUCTOR,
        )
        student = User(
            berkeley_username="activation-student",
            role=UserRole.STUDENT,
        )
        course = CourseInstance(
            course_code="IEOR150-Activation",
            course_name="Resource Allocation",
            semester="Fall 2026",
            creator=instructor,
        )
        enrollment = Enrollment(
            course=course,
            user=student,
            status=status,
        )
        db_session.add(enrollment)
        db_session.commit()
        db_session.refresh(enrollment)
        return enrollment

    return create_enrollment


def test_generated_code_has_required_format_and_alphabet():
    activation_code = generate_activation_code()

    assert re.fullmatch(r"[A-Z2-9]{4}(?:-[A-Z2-9]{4}){2}", activation_code)
    assert set(activation_code.replace("-", "")).issubset(
        set(ACTIVATION_CODE_ALPHABET)
    )


def test_consecutive_codes_are_distinct():
    assert generate_activation_code() != generate_activation_code()


def test_issue_stores_only_hash_and_sets_aware_fourteen_day_expiration(
    db_session,
    enrollment_factory,
):
    enrollment = enrollment_factory()

    activation_code = issue_activation_code(enrollment, now=FIXED_NOW)
    db_session.commit()
    db_session.refresh(enrollment)

    assert enrollment.activation_code_hash is not None
    assert enrollment.activation_code_hash != activation_code
    assert enrollment.activation_code_hash != activation_code.replace("-", "")
    assert "activation_code" not in enrollment.__dict__
    assert enrollment.activation_expires_at == FIXED_NOW + ACTIVATION_CODE_TTL
    assert enrollment.activation_expires_at.utcoffset() == timedelta(0)
    assert enrollment.activation_used_at is None


def test_correct_code_and_supported_input_variants_verify(enrollment_factory):
    enrollment = enrollment_factory()
    activation_code = issue_activation_code(enrollment, now=FIXED_NOW)

    assert verify_activation_code(enrollment, activation_code, now=FIXED_NOW)
    assert verify_activation_code(enrollment, activation_code.lower(), now=FIXED_NOW)
    assert verify_activation_code(
        enrollment,
        activation_code.replace("-", ""),
        now=FIXED_NOW,
    )
    assert verify_activation_code(
        enrollment,
        f"  {activation_code.lower()}  ",
        now=FIXED_NOW,
    )


def test_second_issue_fails_without_changing_current_code(enrollment_factory):
    enrollment = enrollment_factory()
    activation_code = issue_activation_code(enrollment, now=FIXED_NOW)
    original_hash = enrollment.activation_code_hash
    original_expiration = enrollment.activation_expires_at

    with pytest.raises(ActivationCodeError, match="use regeneration") as error:
        issue_activation_code(
            enrollment,
            now=FIXED_NOW + timedelta(hours=1),
        )

    assert enrollment.activation_code_hash == original_hash
    assert enrollment.activation_expires_at == original_expiration
    assert verify_activation_code(enrollment, activation_code, now=FIXED_NOW)
    assert activation_code not in str(error.value)
    assert original_hash is not None
    assert original_hash not in str(error.value)


def test_wrong_or_malformed_code_fails(enrollment_factory):
    enrollment = enrollment_factory()
    issue_activation_code(enrollment, now=FIXED_NOW)

    assert not verify_activation_code(
        enrollment,
        "AAAA-AAAA-AAAA",
        now=FIXED_NOW,
    )
    assert not verify_activation_code(enrollment, "not-a-code", now=FIXED_NOW)


def test_expired_code_fails(enrollment_factory):
    enrollment = enrollment_factory()
    activation_code = issue_activation_code(enrollment, now=FIXED_NOW)

    assert not verify_activation_code(
        enrollment,
        activation_code,
        now=FIXED_NOW + ACTIVATION_CODE_TTL,
    )


def test_used_code_fails(enrollment_factory):
    enrollment = enrollment_factory()
    activation_code = issue_activation_code(enrollment, now=FIXED_NOW)
    enrollment.activation_used_at = FIXED_NOW

    assert not verify_activation_code(enrollment, activation_code, now=FIXED_NOW)


def test_disabled_enrollment_cannot_issue_regenerate_or_verify(enrollment_factory):
    enrollment = enrollment_factory(status=EnrollmentStatus.DISABLED)

    with pytest.raises(ActivationCodeError, match="disabled"):
        issue_activation_code(enrollment, now=FIXED_NOW)
    with pytest.raises(ActivationCodeError, match="disabled"):
        regenerate_activation_code(enrollment, now=FIXED_NOW)
    assert not verify_activation_code(
        enrollment,
        "AAAA-AAAA-AAAA",
        now=FIXED_NOW,
    )


def test_active_enrollment_cannot_issue_or_regenerate(enrollment_factory):
    enrollment = enrollment_factory(status=EnrollmentStatus.ACTIVE)

    with pytest.raises(ActivationCodeError, match="already active"):
        issue_activation_code(enrollment, now=FIXED_NOW)
    with pytest.raises(ActivationCodeError, match="already active"):
        regenerate_activation_code(enrollment, now=FIXED_NOW)


def test_regeneration_immediately_invalidates_old_code(
    enrollment_factory,
    monkeypatch,
):
    enrollment = enrollment_factory()
    generated_codes = iter(
        [
            "ABCD-EFGH-JKMN",
            "ABCD-EFGH-JKMN",
            "PQRS-TUVW-XYZ2",
        ]
    )
    monkeypatch.setattr(
        activation_codes,
        "generate_activation_code",
        lambda: next(generated_codes),
    )
    old_code = issue_activation_code(enrollment, now=FIXED_NOW)
    old_hash = enrollment.activation_code_hash

    new_code = regenerate_activation_code(
        enrollment,
        now=FIXED_NOW + timedelta(hours=1),
    )

    assert new_code != old_code
    assert enrollment.activation_code_hash != old_hash
    assert not verify_activation_code(
        enrollment,
        old_code,
        now=FIXED_NOW + timedelta(hours=1),
    )
    assert verify_activation_code(
        enrollment,
        new_code,
        now=FIXED_NOW + timedelta(hours=1),
    )


def test_verification_does_not_consume_code(enrollment_factory):
    enrollment = enrollment_factory()
    activation_code = issue_activation_code(enrollment, now=FIXED_NOW)
    original_hash = enrollment.activation_code_hash

    assert verify_activation_code(enrollment, activation_code, now=FIXED_NOW)
    assert enrollment.activation_used_at is None
    assert enrollment.activation_code_hash == original_hash
    assert enrollment.status == EnrollmentStatus.PENDING


def test_mark_used_consumes_code_and_activates_enrollment(enrollment_factory):
    enrollment = enrollment_factory()
    activation_code = issue_activation_code(enrollment, now=FIXED_NOW)
    used_at = FIXED_NOW + timedelta(minutes=5)

    mark_activation_used(enrollment, now=used_at)

    assert enrollment.activation_used_at == used_at
    assert enrollment.activation_used_at.utcoffset() == timedelta(0)
    assert enrollment.activation_code_hash is None
    assert enrollment.status == EnrollmentStatus.ACTIVE
    assert not verify_activation_code(enrollment, activation_code, now=used_at)


@pytest.mark.parametrize("state", ["missing", "expired", "used"])
def test_mark_used_requires_current_unexpired_unused_code(
    enrollment_factory,
    state,
):
    enrollment = enrollment_factory()
    issue_activation_code(enrollment, now=FIXED_NOW)
    mark_time = FIXED_NOW + timedelta(hours=1)

    if state == "missing":
        enrollment.activation_code_hash = None
    elif state == "expired":
        enrollment.activation_expires_at = mark_time
    else:
        enrollment.activation_used_at = FIXED_NOW

    expected_error = "already active" if state == "used" else "No usable"
    with pytest.raises(ActivationCodeError, match=expected_error):
        mark_activation_used(enrollment, now=mark_time)


def test_naive_now_is_rejected_without_secret_material(enrollment_factory):
    enrollment = enrollment_factory()

    with pytest.raises(ActivationCodeError, match="timezone-aware"):
        issue_activation_code(enrollment, now=datetime(2026, 8, 1, 12, 0))


def test_output_and_errors_do_not_expose_code_or_hash(
    enrollment_factory,
    capsys,
):
    enrollment = enrollment_factory()
    activation_code = issue_activation_code(enrollment, now=FIXED_NOW)
    activation_hash = enrollment.activation_code_hash
    enrollment.status = EnrollmentStatus.ACTIVE

    with pytest.raises(ActivationCodeError) as error:
        regenerate_activation_code(enrollment, now=FIXED_NOW)

    captured = capsys.readouterr()
    output = captured.out + captured.err + str(error.value)
    assert activation_code not in output
    assert activation_hash is not None
    assert activation_hash not in output
