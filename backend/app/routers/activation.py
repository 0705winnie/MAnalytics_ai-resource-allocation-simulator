"""First-time student activation credential verification."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.activation_auth import (
    ACTIVATION_COOKIE_NAME,
    create_activation_token,
)
from app.core.auth import AuthConfigurationError
from app.core.config import AuthSettings, get_auth_settings
from app.db.session import get_db
from app.schemas.activation import (
    ActivationVerificationResponse,
    ActivationVerifyRequest,
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
        course_code=request.course_code,
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
