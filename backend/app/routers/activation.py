"""First-time student activation credential verification."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.activation_auth import (
    ACTIVATION_COOKIE_NAME,
    ACTIVATION_CONTEXT_REQUIRED_MESSAGE,
    InvalidActivationTokenError,
    create_activation_token,
)
from app.core.auth import ACCESS_COOKIE_NAME, AuthConfigurationError
from app.core.config import AuthSettings, get_auth_settings
from app.db.session import get_db
from app.schemas.activation import (
    ActivationCompleteRequest,
    ActivationVerificationResponse,
    ActivationVerifyRequest,
)
from app.schemas.auth import (
    AuthenticatedCourseResponse,
    AuthenticatedUserResponse,
    AuthenticationResponse,
)
from app.services.activation_codes import ActivationCodeError
from app.services.activation_completion import (
    InvalidNicknameError,
    prepare_activation_completion,
)
from app.services.activation_verification import verify_activation_credentials


router = APIRouter(prefix="/auth", tags=["Authentication"])
INVALID_ACTIVATION_CREDENTIALS_MESSAGE = (
    "Invalid or expired activation credentials"
)


def _activation_failure_response(
    *,
    status_code: int,
    detail: str,
    settings: AuthSettings,
) -> JSONResponse:
    response = JSONResponse(
        status_code=status_code,
        content={"detail": detail},
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
        },
    )
    response.delete_cookie(
        key=ACTIVATION_COOKIE_NAME,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return response


def _retryable_completion_failure(
    *,
    status_code: int,
    detail: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
        },
    )


@router.post(
    "/activate/verify",
    response_model=ActivationVerificationResponse,
)
def verify_student_activation(
    request: ActivationVerifyRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
) -> ActivationVerificationResponse | Response:
    credentials = verify_activation_credentials(
        db,
        course_id=request.course_id,
        berkeley_username=request.berkeley_username,
        submitted_code=request.activation_code,
    )
    if credentials is None:
        return _activation_failure_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_ACTIVATION_CREDENTIALS_MESSAGE,
            settings=settings,
        )

    activation_hash = credentials.enrollment.activation_code_hash
    if activation_hash is None:
        return _activation_failure_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_ACTIVATION_CREDENTIALS_MESSAGE,
            settings=settings,
        )
    try:
        token = create_activation_token(
            user_id=credentials.user.id,
            enrollment_id=credentials.enrollment.id,
            course_id=credentials.course.id,
            activation_code_hash=activation_hash,
            settings=settings,
        )
    except AuthConfigurationError:
        return _activation_failure_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Activation verification is unavailable",
            settings=settings,
        )

    expires_in_seconds = settings.activation_token_minutes * 60
    response.set_cookie(
        key=ACTIVATION_COOKIE_NAME,
        value=token,
        max_age=expires_in_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return ActivationVerificationResponse(
        verified=True,
        expires_in_seconds=expires_in_seconds,
    )


@router.post(
    "/activate/complete",
    response_model=AuthenticationResponse,
)
def complete_student_activation(
    request: ActivationCompleteRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
    activation_token: Annotated[
        str | None,
        Cookie(alias=ACTIVATION_COOKIE_NAME),
    ] = None,
) -> AuthenticationResponse | Response:
    if activation_token is None:
        return _activation_failure_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ACTIVATION_CONTEXT_REQUIRED_MESSAGE,
            settings=settings,
        )

    try:
        prepared = prepare_activation_completion(
            db,
            activation_token=activation_token,
            password=request.password,
            nickname=request.nickname,
            settings=settings,
        )
        context = prepared.context
        completion_response = AuthenticationResponse(
            authenticated=True,
            user=AuthenticatedUserResponse(
                id=context.user.id,
                username=context.user.berkeley_username,
                role=context.user.role,
            ),
            course=AuthenticatedCourseResponse(
                id=context.course.id,
                course_code=context.course.course_code,
                semester=context.course.semester,
                course_identifier=context.course.course_identifier,
            ),
            nickname=context.enrollment.nickname,
        )
        db.commit()
    except (InvalidActivationTokenError, ActivationCodeError):
        db.rollback()
        return _activation_failure_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ACTIVATION_CONTEXT_REQUIRED_MESSAGE,
            settings=settings,
        )
    except InvalidNicknameError:
        db.rollback()
        return _retryable_completion_failure(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Nickname is invalid",
        )
    except IntegrityError:
        db.rollback()
        return _retryable_completion_failure(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nickname is unavailable",
        )
    except (AuthConfigurationError, SQLAlchemyError):
        db.rollback()
        return _retryable_completion_failure(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Activation could not be completed",
        )

    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=prepared.access_token,
        max_age=settings.access_token_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.delete_cookie(
        key=ACTIVATION_COOKIE_NAME,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return completion_response
