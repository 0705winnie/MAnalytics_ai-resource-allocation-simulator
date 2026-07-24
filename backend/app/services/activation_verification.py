"""Constant-shape verification of first-time student activation credentials."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from pwdlib.exceptions import UnknownHashError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.security import hash_one_time_secret, verify_one_time_secret
from app.models import CourseInstance, Enrollment, User
from app.models.enums import EnrollmentStatus, UserRole
from app.services.activation_codes import normalize_activation_code


_DUMMY_ACTIVATION_HASH = hash_one_time_secret(secrets.token_urlsafe(32))
_INVALID_NORMALIZED_CODE = "INVALID-ACTIVATION-CREDENTIAL"


@dataclass(frozen=True)
class VerifiedActivationCredentials:
    user: User
    course: CourseInstance
    enrollment: Enrollment


def verify_activation_credentials(
    db: Session,
    *,
    course_code: str,
    berkeley_username: str,
    submitted_code: str,
    now: datetime | None = None,
) -> VerifiedActivationCredentials | None:
    """Verify one credential tuple with exactly one Argon2 verification."""

    enrollment = db.scalar(
        select(Enrollment)
        .join(CourseInstance, Enrollment.course_id == CourseInstance.id)
        .join(User, Enrollment.user_id == User.id)
        .where(
            CourseInstance.course_code_normalized == course_code.strip().lower(),
            User.berkeley_username == berkeley_username.strip().lower(),
        )
        .options(
            joinedload(Enrollment.course),
            joinedload(Enrollment.user),
        )
    )

    stored_hash = (
        enrollment.activation_code_hash
        if enrollment is not None and enrollment.activation_code_hash
        else _DUMMY_ACTIVATION_HASH
    )
    normalized_code = normalize_activation_code(submitted_code)
    verification_input = normalized_code or _INVALID_NORMALIZED_CODE
    try:
        code_matches = verify_one_time_secret(verification_input, stored_hash)
    except UnknownHashError:
        code_matches = False

    current_time = now if now is not None else datetime.now(UTC)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        return None
    current_time = current_time.astimezone(UTC)

    if enrollment is None:
        return None
    expiration = enrollment.activation_expires_at
    credentials_are_eligible = (
        enrollment.course.is_active
        and enrollment.user.role == UserRole.STUDENT
        and enrollment.user.is_active
        and enrollment.status == EnrollmentStatus.PENDING
        and enrollment.activation_used_at is None
        and enrollment.activation_code_hash is not None
        and expiration is not None
        and expiration.tzinfo is not None
        and expiration.utcoffset() is not None
        and current_time < expiration.astimezone(UTC)
    )
    if not code_matches or not credentials_are_eligible:
        return None
    return VerifiedActivationCredentials(
        user=enrollment.user,
        course=enrollment.course,
        enrollment=enrollment,
    )
