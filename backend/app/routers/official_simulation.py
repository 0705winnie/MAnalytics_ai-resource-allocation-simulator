"""Authenticated official simulation restoration and next-month routes."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_student
from app.db.session import get_db
from app.schemas.simulation_sessions import (
    OfficialSessionResponse,
    RunNextMonthRequest,
    RunNextMonthResponse,
)
from app.services.policy_sandbox import PolicyError
from app.services.simulation_persistence import (
    OfficialSimulationConflictError,
    OfficialSimulationIntegrityError,
    get_official_session_response,
    run_next_official_month,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/simulation/session", tags=["Official Simulation"])


def _server_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "code": "official_simulation_unavailable",
            "message": "Official simulation state is temporarily unavailable",
        },
    )


@router.get("", response_model=OfficialSessionResponse)
def get_current_simulation_session(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[AuthContext, Depends(require_student)],
) -> OfficialSessionResponse:
    assert context.enrollment is not None
    try:
        return get_official_session_response(db, context.enrollment.id)
    except OfficialSimulationIntegrityError:
        db.rollback()
        logger.exception(
            "Official simulation restoration failed integrity validation",
            extra={"enrollment_id": str(context.enrollment.id)},
        )
        raise _server_error() from None
    except Exception:
        db.rollback()
        logger.exception(
            "Official simulation restoration failed unexpectedly",
            extra={"enrollment_id": str(context.enrollment.id)},
        )
        raise _server_error() from None


@router.post(
    "/months/next",
    response_model=RunNextMonthResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_next_simulation_month(
    request: RunNextMonthRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[AuthContext, Depends(require_student)],
) -> RunNextMonthResponse:
    assert context.enrollment is not None
    try:
        result = run_next_official_month(db, context.enrollment.id, request)
        db.commit()
    except OfficialSimulationConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.as_detail(),
        ) from None
    except PolicyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_policy",
                "message": str(exc),
            },
        ) from None
    except OfficialSimulationIntegrityError:
        db.rollback()
        logger.exception(
            "Official simulation execution failed integrity validation",
            extra={"enrollment_id": str(context.enrollment.id)},
        )
        raise _server_error() from None
    except Exception:
        db.rollback()
        logger.exception(
            "Official simulation execution failed unexpectedly",
            extra={"enrollment_id": str(context.enrollment.id)},
        )
        raise _server_error() from None

    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return result
