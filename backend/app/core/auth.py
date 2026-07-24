"""JWT access tokens and reusable database-backed authentication dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from jwt import PyJWTError
from sqlalchemy.orm import Session

from app.core.config import AuthSettings, get_auth_settings
from app.db.session import get_db
from app.models import User
from app.models.enums import UserRole


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
    issued_at: int
    expires_at: int
    token_id: uuid.UUID


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
) -> str:
    """Create a signed access token containing only authorization claims."""

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
        return AccessTokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            role=UserRole(payload["role"]),
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


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
    access_token: Annotated[
        str | None,
        Cookie(alias=ACCESS_COOKIE_NAME),
    ] = None,
) -> User:
    """Resolve identity exclusively from a verified cookie and current DB row."""

    if access_token is None:
        raise _authentication_required()
    try:
        claims = decode_access_token(access_token, settings)
    except (AuthConfigurationError, InvalidAccessTokenError):
        raise _authentication_required() from None

    user = db.get(User, claims.user_id)
    if (
        user is None
        or not user.is_active
        or user.role != claims.role
    ):
        raise _authentication_required()
    return user


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
