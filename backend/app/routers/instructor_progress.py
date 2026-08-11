"""Instructor read-only student-progress endpoint."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import require_instructor
from app.db.session import get_db
from app.models import Enrollment, MonthlyResult, SimulationSession, User
from app.schemas.instructor_progress import (
    StudentProgressListResponse,
    StudentProgressResponse,
)
from app.services.instructor_enrollments import find_owned_course

router = APIRouter(prefix="/instructor/courses", tags=["Instructor Progress"])


@router.get(
    "/{course_id}/progress",
    response_model=StudentProgressListResponse,
)
def list_course_progress(
    course_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    instructor: Annotated[User, Depends(require_instructor)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> StudentProgressListResponse:
    course = find_owned_course(db, course_id, instructor.id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    total = db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .where(Enrollment.course_id == course.id)
    )
    rows = db.execute(
        select(
            Enrollment.id.label("enrollment_id"),
            User.berkeley_username,
            Enrollment.nickname,
            Enrollment.status.label("enrollment_status"),
            User.is_active.label("user_is_active"),
            func.coalesce(SimulationSession.completed_months, 0).label(
                "completed_months"
            ),
            func.coalesce(func.sum(MonthlyResult.total_revenue), 0).label(
                "cumulative_revenue"
            ),
            SimulationSession.last_completed_at.label("last_activity"),
            func.coalesce(
                func.sum(func.jsonb_array_length(MonthlyResult.warnings)),
                0,
            ).label("warnings_count"),
        )
        .join(User, Enrollment.user_id == User.id)
        .outerjoin(
            SimulationSession,
            SimulationSession.enrollment_id == Enrollment.id,
        )
        .outerjoin(
            MonthlyResult,
            MonthlyResult.session_id == SimulationSession.id,
        )
        .where(Enrollment.course_id == course.id)
        .group_by(
            Enrollment.id,
            User.berkeley_username,
            Enrollment.nickname,
            Enrollment.status,
            User.is_active,
            SimulationSession.completed_months,
            SimulationSession.last_completed_at,
        )
        .order_by(User.berkeley_username.asc(), Enrollment.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()

    items: list[StudentProgressResponse] = []
    for row in rows:
        completed_months = int(row.completed_months)
        simulation_status = (
            "not_started"
            if completed_months == 0
            else "completed"
            if completed_months == 12
            else "in_progress"
        )
        items.append(
            StudentProgressResponse(
                enrollment_id=row.enrollment_id,
                berkeley_username=row.berkeley_username,
                nickname=row.nickname,
                enrollment_status=row.enrollment_status,
                user_is_active=row.user_is_active,
                completed_months=completed_months,
                cumulative_revenue=float(row.cumulative_revenue),
                last_activity=row.last_activity,
                simulation_status=simulation_status,
                warnings_count=int(row.warnings_count),
            )
        )
    return StudentProgressListResponse(
        items=items,
        total=total or 0,
        offset=offset,
        limit=limit,
    )
