"""Instructor read-only student-progress endpoint."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.auth import require_instructor
from app.db.session import get_db
from app.models import Enrollment, Submission, User
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
    enrollments = db.scalars(
        select(Enrollment)
        .join(User, Enrollment.user_id == User.id)
        .where(Enrollment.course_id == course.id)
        .options(joinedload(Enrollment.user))
        .order_by(User.berkeley_username.asc(), Enrollment.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()

    submissions_by_enrollment: dict[uuid.UUID, list[Submission]] = defaultdict(list)
    enrollment_ids = [enrollment.id for enrollment in enrollments]
    if enrollment_ids:
        submissions = db.scalars(
            select(Submission)
            .where(Submission.enrollment_id.in_(enrollment_ids))
            .order_by(Submission.submitted_at.asc())
        ).all()
        for submission in submissions:
            submissions_by_enrollment[submission.enrollment_id].append(submission)

    items = [
        StudentProgressResponse.from_enrollment(
            enrollment,
            submissions_by_enrollment.get(enrollment.id, []),
        )
        for enrollment in enrollments
    ]
    return StudentProgressListResponse(
        items=items,
        total=total or 0,
        offset=offset,
        limit=limit,
    )
