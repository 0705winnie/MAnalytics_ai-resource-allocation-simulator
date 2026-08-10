"""JWT access tokens and reusable database-backed authentication dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from jwt import PyJWTError
from sqlalchemy import select
from sqlalchemy.orm import Session, contains_eager

from app.core.config import AuthSettings, get_auth_settings
from app.db.session import get_db
from app.models import CourseInstance, Enrollment, User
from app.models.enums import EnrollmentStatus, UserRole


ACCESS_COOKIE_NAME = "ra_access_token"
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "resource-allocation-api"
JWT_AUDIENCE = "resource-allocation-dashboard"
ACCESS_TOKEN_TYPE = "access"
AUTHENTICATION_REQUIRED_MESSAGE = "Authentication required"


class AuthConfigurationError(RuntimeError):
    """Authentication is unavailable because secure configuration is absent."""


class InvalidAccessTokenError(RuntimeError):
    """A uniform error for invalid, expired, or malformed access tokens."""


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    role: UserRole
    course_id: uuid.UUID | None
    enrollment_id: uuid.UUID | None
    issued_at: int
    expires_at: int
    token_id: uuid.UUID


@dataclass(frozen=True)
class AuthContext:
    user: User
    course: CourseInstance | None = None
    enrollment: Enrollment | None = None


def get_jwt_secret(settings: AuthSettings) -> str:
    """Return a validated signing secret without exposing it."""

    secret_setting = settings.jwt_secret
    secret = secret_setting.get_secret_value() if secret_setting else ""
    if len(secret) < 32:
        raise AuthConfigurationError(
            "JWT authentication is not configured securely"
        )
    return secret


def auth_utc_now(now: datetime | None) -> datetime:
    """Return one timezone-aware UTC authentication timestamp."""

    current_time = now if now is not None else datetime.now(UTC)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise AuthConfigurationError("Authentication timestamps must be timezone-aware")
    return current_time.astimezone(UTC)


def create_access_token(
    user_id: uuid.UUID,
    role: UserRole,
    settings: AuthSettings,
    now: datetime | None = None,
    *,
    course_id: uuid.UUID | None = None,
    enrollment_id: uuid.UUID | None = None,
) -> str:
    """Create a signed access token containing only authorization claims."""

    if role == UserRole.INSTRUCTOR:
        if course_id is not None or enrollment_id is not None:
            raise ValueError("Instructor access tokens cannot be course-scoped")
    elif role == UserRole.STUDENT:
        if course_id is None or enrollment_id is None:
            raise ValueError("Student access tokens must be course-scoped")
    else:
        raise ValueError("Unsupported access token role")

    secret = get_jwt_secret(settings)
    issued_at = auth_utc_now(now)
    expires_at = issued_at + timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "type": ACCESS_TOKEN_TYPE,
        "iat": issued_at,
        "exp": expires_at,
        "jti": str(uuid.uuid4()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    if role == UserRole.STUDENT:
        payload["course_id"] = str(course_id)
        payload["enrollment_id"] = str(enrollment_id)
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(
    token: str,
    settings: AuthSettings,
) -> AccessTokenClaims:
    """Validate an access token using a fixed algorithm and required claims."""

    try:
        payload = jwt.decode(
            token,
            get_jwt_secret(settings),
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={
                "require": [
                    "sub",
                    "role",
                    "type",
                    "iat",
                    "exp",
                    "jti",
                    "iss",
                    "aud",
                ]
            },
        )
        if payload["type"] != ACCESS_TOKEN_TYPE:
            raise ValueError
        role = UserRole(payload["role"])
        raw_course_id = payload.get("course_id")
        raw_enrollment_id = payload.get("enrollment_id")
        if role == UserRole.INSTRUCTOR:
            if raw_course_id is not None or raw_enrollment_id is not None:
                raise ValueError
            course_id = None
            enrollment_id = None
        elif role == UserRole.STUDENT:
            if raw_course_id is None or raw_enrollment_id is None:
                raise ValueError
            course_id = uuid.UUID(raw_course_id)
            enrollment_id = uuid.UUID(raw_enrollment_id)
        else:
            raise ValueError
        return AccessTokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            role=role,
            course_id=course_id,
            enrollment_id=enrollment_id,
            issued_at=int(payload["iat"]),
            expires_at=int(payload["exp"]),
            token_id=uuid.UUID(payload["jti"]),
        )
    except AuthConfigurationError:
        raise
    except (PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise InvalidAccessTokenError("Invalid or expired access token") from exc


def _authentication_required() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=AUTHENTICATION_REQUIRED_MESSAGE,
    )


def get_auth_context(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
    access_token: Annotated[
        str | None,
        Cookie(alias=ACCESS_COOKIE_NAME),
    ] = None,
) -> AuthContext:
    """Resolve one database-backed Instructor or course-scoped Student."""

    if access_token is None:
        raise _authentication_required()
    try:
        claims = decode_access_token(access_token, settings)
    except (AuthConfigurationError, InvalidAccessTokenError):
        raise _authentication_required() from None

    if claims.role == UserRole.INSTRUCTOR:
        user = db.get(User, claims.user_id)
        if (
            user is None
            or not user.is_active
            or user.role != UserRole.INSTRUCTOR
        ):
            raise _authentication_required()
        return AuthContext(user=user)

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
            contains_eager(Enrollment.user),
            contains_eager(Enrollment.course),
        )
    )
    if (
        enrollment is None
        or not enrollment.user.is_active
        or enrollment.user.role != UserRole.STUDENT
        or not enrollment.course.is_active
        or enrollment.status != EnrollmentStatus.ACTIVE
        or enrollment.nickname is None
        or enrollment.activation_used_at is None
        or enrollment.activation_code_hash is not None
    ):
        raise _authentication_required()
    return AuthContext(
        user=enrollment.user,
        course=enrollment.course,
        enrollment=enrollment,
    )


def get_current_user(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> User:
    """Return the user from a fully validated authentication context."""

    return context.user


def require_instructor(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require an authenticated, active instructor."""

    if current_user.role != UserRole.INSTRUCTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Instructor access required",
        )
    return current_user


def require_student(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AuthContext:
    """Require an authenticated, course-scoped student."""

    if (
        context.user.role != UserRole.STUDENT
        or context.enrollment is None
        or context.course is None
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required",
        )
    return context
