"""Short-lived, database-bound JWT context for first-time activation."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from jwt import PyJWTError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.auth import (
    JWT_ALGORITHM,
    JWT_ISSUER,
    AuthConfigurationError,
    auth_utc_now,
    get_jwt_secret,
)
from app.core.config import AuthSettings, get_auth_settings
from app.db.session import get_db
from app.models import CourseInstance, Enrollment, User
from app.models.enums import EnrollmentStatus, UserRole


ACTIVATION_COOKIE_NAME = "ra_activation_token"
ACTIVATION_TOKEN_TYPE = "activation"
ACTIVATION_TOKEN_AUDIENCE = "resource-allocation-activation"
ACTIVATION_CONTEXT_REQUIRED_MESSAGE = "Invalid or expired activation session"


@dataclass(frozen=True)
class ActivationTokenClaims:
    user_id: uuid.UUID
    enrollment_id: uuid.UUID
    course_id: uuid.UUID
    issued_at: int
    expires_at: int
    token_id: uuid.UUID
    activation_version: str


@dataclass(frozen=True)
class ActivationContext:
    user: User
    course: CourseInstance
    enrollment: Enrollment


class InvalidActivationTokenError(RuntimeError):
    """A uniform error for invalid activation JWTs."""


def activation_hash_fingerprint(
    activation_code_hash: str,
    settings: AuthSettings,
) -> str:
    """Bind a token to the current stored hash with a secret HMAC."""

    secret = get_jwt_secret(settings).encode()
    return hmac.new(
        secret,
        activation_code_hash.encode(),
        hashlib.sha256,
    ).hexdigest()


def create_activation_token(
    *,
    user_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    course_id: uuid.UUID,
    activation_code_hash: str,
    settings: AuthSettings,
    now: datetime | None = None,
) -> str:
    secret = get_jwt_secret(settings)
    issued_at = auth_utc_now(now)
    expires_at = issued_at + timedelta(
        minutes=settings.activation_token_minutes
    )
    payload = {
        "sub": str(user_id),
        "enrollment_id": str(enrollment_id),
        "course_id": str(course_id),
        "role": UserRole.STUDENT.value,
        "type": ACTIVATION_TOKEN_TYPE,
        "iat": issued_at,
        "exp": expires_at,
        "jti": str(uuid.uuid4()),
        "iss": JWT_ISSUER,
        "aud": ACTIVATION_TOKEN_AUDIENCE,
        "activation_version": activation_hash_fingerprint(
            activation_code_hash,
            settings,
        ),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_activation_token(
    token: str,
    settings: AuthSettings,
) -> ActivationTokenClaims:
    try:
        payload = jwt.decode(
            token,
            get_jwt_secret(settings),
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=ACTIVATION_TOKEN_AUDIENCE,
            options={
                "require": [
                    "sub",
                    "enrollment_id",
                    "course_id",
                    "role",
                    "type",
                    "iat",
                    "exp",
                    "jti",
                    "iss",
                    "aud",
                    "activation_version",
                ]
            },
        )
        activation_version = payload["activation_version"]
        if (
            payload["type"] != ACTIVATION_TOKEN_TYPE
            or payload["role"] != UserRole.STUDENT.value
            or not isinstance(activation_version, str)
            or len(activation_version) != hashlib.sha256().digest_size * 2
        ):
            raise ValueError
        return ActivationTokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            enrollment_id=uuid.UUID(payload["enrollment_id"]),
            course_id=uuid.UUID(payload["course_id"]),
            issued_at=int(payload["iat"]),
            expires_at=int(payload["exp"]),
            token_id=uuid.UUID(payload["jti"]),
            activation_version=activation_version,
        )
    except AuthConfigurationError:
        raise
    except (PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise InvalidActivationTokenError(
            ACTIVATION_CONTEXT_REQUIRED_MESSAGE
        ) from exc


def _activation_context_required() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ACTIVATION_CONTEXT_REQUIRED_MESSAGE,
    )


def get_activation_context(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
    activation_token: Annotated[
        str | None,
        Cookie(alias=ACTIVATION_COOKIE_NAME),
    ] = None,
) -> ActivationContext:
    """Resolve an activation session exclusively from its HttpOnly cookie."""

    if activation_token is None:
        raise _activation_context_required()
    try:
        claims = decode_activation_token(activation_token, settings)
    except (AuthConfigurationError, InvalidActivationTokenError):
        raise _activation_context_required() from None

    enrollment = db.scalar(
        select(Enrollment)
        .join(User, Enrollment.user_id == User.id)
        .join(CourseInstance, Enrollment.course_id == CourseInstance.id)
        .where(
            Enrollment.id == claims.enrollment_id,
            Enrollment.user_id == claims.user_id,
            Enrollment.course_id == claims.course_id,
            User.id == claims.user_id,
            CourseInstance.id == claims.course_id,
        )
        .options(
            joinedload(Enrollment.user),
            joinedload(Enrollment.course),
        )
    )
    if enrollment is None or enrollment.activation_code_hash is None:
        raise _activation_context_required()

    expiration = enrollment.activation_expires_at
    state_is_valid = (
        enrollment.course.is_active
        and enrollment.user.role == UserRole.STUDENT
        and enrollment.user.is_active
        and enrollment.status == EnrollmentStatus.PENDING
        and enrollment.activation_used_at is None
        and expiration is not None
        and expiration.tzinfo is not None
        and expiration.utcoffset() is not None
        and datetime.now(UTC) < expiration.astimezone(UTC)
    )
    try:
        current_version = activation_hash_fingerprint(
            enrollment.activation_code_hash,
            settings,
        )
    except AuthConfigurationError:
        raise _activation_context_required() from None
    if not state_is_valid or not hmac.compare_digest(
        claims.activation_version,
        current_version,
    ):
        raise _activation_context_required()
    return ActivationContext(
        user=enrollment.user,
        course=enrollment.course,
        enrollment=enrollment,
    )
