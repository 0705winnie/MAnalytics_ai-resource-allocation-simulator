"""Secure lifecycle operations for student enrollment activation codes."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from pwdlib.exceptions import UnknownHashError

from app.core.security import hash_one_time_secret, verify_one_time_secret
from app.models.enrollment import Enrollment
from app.models.enums import EnrollmentStatus


ACTIVATION_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ACTIVATION_CODE_LENGTH = 12
ACTIVATION_CODE_TTL = timedelta(days=14)


class ActivationCodeError(RuntimeError):
    """A safe activation lifecycle error containing no secret material."""


def _utc_now(now: datetime | None) -> datetime:
    current_time = now if now is not None else datetime.now(UTC)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ActivationCodeError("Activation timestamps must be timezone-aware")
    return current_time.astimezone(UTC)


def normalize_activation_code(submitted_code: str) -> str | None:
    """Normalize accepted user input without weakening the code alphabet."""

    normalized = submitted_code.strip().replace("-", "").upper()
    if (
        len(normalized) != ACTIVATION_CODE_LENGTH
        or any(character not in ACTIVATION_CODE_ALPHABET for character in normalized)
    ):
        return None
    return normalized


def _ensure_pending_enrollment(enrollment: Enrollment) -> None:
    if enrollment.status == EnrollmentStatus.DISABLED:
        raise ActivationCodeError(
            "Activation codes are unavailable for disabled enrollments"
        )
    if (
        enrollment.status == EnrollmentStatus.ACTIVE
        or enrollment.activation_used_at is not None
    ):
        raise ActivationCodeError("The enrollment is already active")


def _stored_expiration_is_valid(
    enrollment: Enrollment,
    current_time: datetime,
) -> bool:
    expiration = enrollment.activation_expires_at
    if expiration is None or expiration.tzinfo is None or expiration.utcoffset() is None:
        return False
    return current_time < expiration.astimezone(UTC)


def generate_activation_code() -> str:
    """Return a cryptographically secure code formatted as XXXX-XXXX-XXXX."""

    unformatted_code = "".join(
        secrets.choice(ACTIVATION_CODE_ALPHABET)
        for _ in range(ACTIVATION_CODE_LENGTH)
    )
    return "-".join(
        unformatted_code[index : index + 4]
        for index in range(0, ACTIVATION_CODE_LENGTH, 4)
    )


def _store_activation_code(
    enrollment: Enrollment,
    activation_code: str,
    current_time: datetime,
) -> str:
    normalized_code = normalize_activation_code(activation_code)
    if normalized_code is None:
        raise ActivationCodeError("Secure activation code generation failed")

    enrollment.activation_code_hash = hash_one_time_secret(normalized_code)
    enrollment.activation_expires_at = current_time + ACTIVATION_CODE_TTL
    enrollment.activation_used_at = None
    return activation_code


def issue_activation_code(
    enrollment: Enrollment,
    now: datetime | None = None,
) -> str:
    """Issue a code for a pending enrollment without committing."""

    _ensure_pending_enrollment(enrollment)
    if enrollment.activation_code_hash is not None:
        raise ActivationCodeError(
            "An activation code already exists; use regeneration to replace it"
        )
    current_time = _utc_now(now)
    activation_code = generate_activation_code()
    return _store_activation_code(enrollment, activation_code, current_time)


def regenerate_activation_code(
    enrollment: Enrollment,
    now: datetime | None = None,
) -> str:
    """Replace a pending enrollment's code without committing."""

    _ensure_pending_enrollment(enrollment)
    current_time = _utc_now(now)
    previous_hash = enrollment.activation_code_hash

    while True:
        activation_code = generate_activation_code()
        normalized_code = normalize_activation_code(activation_code)
        if normalized_code is None:
            raise ActivationCodeError("Secure activation code generation failed")
        if previous_hash is not None:
            try:
                if verify_one_time_secret(normalized_code, previous_hash):
                    continue
            except UnknownHashError:
                pass
        return _store_activation_code(enrollment, activation_code, current_time)


def verify_activation_code(
    enrollment: Enrollment,
    submitted_code: str,
    now: datetime | None = None,
) -> bool:
    """Verify without consuming a valid activation code."""

    if (
        enrollment.status != EnrollmentStatus.PENDING
        or enrollment.activation_code_hash is None
        or enrollment.activation_used_at is not None
    ):
        return False

    current_time = _utc_now(now)
    if not _stored_expiration_is_valid(enrollment, current_time):
        return False

    normalized_code = normalize_activation_code(submitted_code)
    if normalized_code is None:
        return False

    try:
        return verify_one_time_secret(
            normalized_code,
            enrollment.activation_code_hash,
        )
    except UnknownHashError:
        return False


def mark_activation_used(
    enrollment: Enrollment,
    now: datetime | None = None,
) -> None:
    """Consume the current code and activate the enrollment without committing."""

    _ensure_pending_enrollment(enrollment)
    current_time = _utc_now(now)
    if (
        enrollment.activation_code_hash is None
        or enrollment.activation_used_at is not None
        or not _stored_expiration_is_valid(enrollment, current_time)
    ):
        raise ActivationCodeError("No usable activation code is available")

    enrollment.activation_used_at = current_time
    enrollment.activation_code_hash = None
    enrollment.status = EnrollmentStatus.ACTIVE
