"""Student and instructor views over one shared official ranking service."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_instructor, require_student
from app.db.session import get_db
from app.models import User
from app.schemas.leaderboards import (
    LeaderboardEntryResponse,
    LeaderboardResponse,
    RankedEnrollmentRecord,
)
from app.services.instructor_enrollments import find_owned_course
from app.services.leaderboards import (
    completed_months_for_enrollment,
    ranked_course_stage,
)

router = APIRouter(tags=["Leaderboards"])


def _response(
    records: list[RankedEnrollmentRecord],
    *,
    stage: int,
    current_enrollment_id: uuid.UUID | None = None,
    current_user_eligible: bool | None = None,
) -> LeaderboardResponse:
    return LeaderboardResponse(
        stage=stage,
        current_user_eligible=current_user_eligible,
        items=[
            LeaderboardEntryResponse(
                rank=record.rank,
                nickname=record.nickname,
                completed_months=record.completed_months,
                cumulative_revenue=record.cumulative_revenue,
                last_activity=record.last_activity,
                is_current_user=(record.enrollment_id == current_enrollment_id),
            )
            for record in records
        ],
    )


@router.get(
    "/leaderboards/same-stage",
    response_model=LeaderboardResponse,
)
def student_same_stage_leaderboard(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[AuthContext, Depends(require_student)],
) -> LeaderboardResponse:
    stage = completed_months_for_enrollment(db, context.enrollment.id)
    if stage == 0:
        return _response(
            [],
            stage=0,
            current_enrollment_id=context.enrollment.id,
            current_user_eligible=False,
        )
    return _response(
        ranked_course_stage(db, course_id=context.course.id, stage=stage),
        stage=stage,
        current_enrollment_id=context.enrollment.id,
        current_user_eligible=True,
    )


@router.get(
    "/leaderboards/final",
    response_model=LeaderboardResponse,
)
def student_final_leaderboard(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[AuthContext, Depends(require_student)],
) -> LeaderboardResponse:
    current_stage = completed_months_for_enrollment(db, context.enrollment.id)
    return _response(
        ranked_course_stage(db, course_id=context.course.id, stage=12),
        stage=12,
        current_enrollment_id=context.enrollment.id,
        current_user_eligible=current_stage == 12,
    )


def _owned_course_id(
    db: Session,
    course_id: uuid.UUID,
    instructor_id: uuid.UUID,
) -> uuid.UUID:
    course = find_owned_course(db, course_id, instructor_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    return course.id


@router.get(
    "/instructor/courses/{course_id}/leaderboards/same-stage",
    response_model=LeaderboardResponse,
)
def instructor_same_stage_leaderboard(
    course_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    instructor: Annotated[User, Depends(require_instructor)],
    stage: Annotated[int, Query(ge=1, le=12)],
) -> LeaderboardResponse:
    owned_course_id = _owned_course_id(db, course_id, instructor.id)
    return _response(
        ranked_course_stage(db, course_id=owned_course_id, stage=stage),
        stage=stage,
    )


@router.get(
    "/instructor/courses/{course_id}/leaderboards/final",
    response_model=LeaderboardResponse,
)
def instructor_final_leaderboard(
    course_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    instructor: Annotated[User, Depends(require_instructor)],
) -> LeaderboardResponse:
    owned_course_id = _owned_course_id(db, course_id, instructor.id)
    return _response(
        ranked_course_stage(db, course_id=owned_course_id, stage=12),
        stage=12,
    )
