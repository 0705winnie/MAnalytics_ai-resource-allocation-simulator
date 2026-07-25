"""Instructor login, current identity, and logout endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import (
    ACCESS_COOKIE_NAME,
    AuthContext,
    AuthConfigurationError,
    create_access_token,
    get_auth_context,
)
from app.core.activation_auth import ACTIVATION_COOKIE_NAME
from app.core.config import AuthSettings, get_auth_settings
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models import User
from app.models.enums import UserRole
from app.schemas.auth import (
    AuthenticatedCourseResponse,
    AuthenticatedUserResponse,
    AuthenticationResponse,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])
INVALID_CREDENTIALS_MESSAGE = "Invalid username or password"
_DUMMY_PASSWORD_HASH = hash_password("dummy-authentication-password")


class InstructorLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("username", mode="before")
    @classmethod
    def trim_username(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


def _authentication_response(
    user: User,
    *,
    context: AuthContext | None = None,
) -> AuthenticationResponse:
    course = context.course if context is not None else None
    enrollment = context.enrollment if context is not None else None
    return AuthenticationResponse(
        authenticated=True,
        user=AuthenticatedUserResponse(
            id=user.id,
            username=user.berkeley_username,
            role=user.role,
        ),
        course=(
            AuthenticatedCourseResponse(
                id=course.id,
                course_code=course.course_code,
            )
            if course is not None
            else None
        ),
        nickname=enrollment.nickname if enrollment is not None else None,
    )


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=INVALID_CREDENTIALS_MESSAGE,
    )


@router.post(
    "/instructor/login",
    response_model=AuthenticationResponse,
    response_model_exclude_none=True,
)
def instructor_login(
    request: InstructorLoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
) -> AuthenticationResponse:
    """Authenticate one active instructor and set an HttpOnly access cookie."""

    normalized_username = request.username.strip().lower()
    user = db.scalar(
        select(User).where(User.berkeley_username == normalized_username)
    )
    password_hash = (
        user.password_hash
        if user is not None and user.password_hash is not None
        else _DUMMY_PASSWORD_HASH
    )
    password_is_valid = verify_password(request.password, password_hash)
    if (
        user is None
        or not password_is_valid
        or user.role != UserRole.INSTRUCTOR
        or not user.is_active
        or user.password_hash is None
    ):
        raise _invalid_credentials()

    try:
        access_token = create_access_token(user.id, user.role, settings)
    except AuthConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is unavailable",
        ) from None

    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        max_age=settings.access_token_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    return _authentication_response(user)


@router.get(
    "/me",
    response_model=AuthenticationResponse,
    response_model_exclude_none=True,
)
def current_identity(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AuthenticationResponse:
    """Return the minimal current identity after DB-backed validation."""

    return _authentication_response(context.user, context=context)


@router.post("/logout")
def logout(
    response: Response,
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
) -> dict[str, bool]:
    """Clear the access cookie whether or not the caller is authenticated."""

    response.delete_cookie(
        key=ACCESS_COOKIE_NAME,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key=ACTIVATION_COOKIE_NAME,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return {"authenticated": False}
