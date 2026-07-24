"""Instructor roster viewing and course-enrollment management endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.core.auth import require_instructor
from app.db.session import get_db
from app.models import Enrollment, User
from app.schemas.instructor_enrollments import (
    EnrollmentStatusRequest,
    InstructorEnrollmentListResponse,
    InstructorEnrollmentResponse,
)
from app.services.instructor_enrollments import (
    EnrollmentOperationError,
    find_owned_course,
    find_owned_enrollment,
    regenerate_student_activation,
    render_regenerated_activation_csv,
    reset_enrollment_nickname,
    set_enrollment_enabled,
)


router = APIRouter(prefix="/instructor/courses", tags=["Instructor Enrollments"])
NOT_FOUND_MESSAGE = "Course or enrollment not found"
INACTIVE_COURSE_MESSAGE = "Inactive courses cannot modify enrollments"
WRITE_CONFLICT_MESSAGE = "The enrollment could not be updated"
WRITE_FAILURE_MESSAGE = "The enrollment update could not be completed"


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=NOT_FOUND_MESSAGE,
    )


def _require_active_course(is_active: bool) -> None:
    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=INACTIVE_COURSE_MESSAGE,
        )


def _commit_enrollment_change(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=WRITE_CONFLICT_MESSAGE,
        ) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=WRITE_FAILURE_MESSAGE,
        ) from None


@router.get(
    "/{course_id}/students",
    response_model=InstructorEnrollmentListResponse,
)
def list_course_students(
    course_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    instructor: Annotated[User, Depends(require_instructor)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> InstructorEnrollmentListResponse:
    course = find_owned_course(db, course_id, instructor.id)
    if course is None:
        raise _not_found()

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
    return InstructorEnrollmentListResponse(
        items=[
            InstructorEnrollmentResponse.from_enrollment(enrollment)
            for enrollment in enrollments
        ],
        total=total or 0,
        offset=offset,
        limit=limit,
    )


@router.post(
    "/{course_id}/enrollments/{enrollment_id}/activation/regenerate"
)
def regenerate_enrollment_activation(
    course_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    instructor: Annotated[User, Depends(require_instructor)],
) -> Response:
    enrollment = find_owned_enrollment(
        db,
        course_id,
        enrollment_id,
        instructor.id,
    )
    if enrollment is None:
        raise _not_found()
    _require_active_course(enrollment.course.is_active)

    try:
        activation_code = regenerate_student_activation(enrollment)
        csv_content = render_regenerated_activation_csv(
            enrollment,
            activation_code,
        )
        db.commit()
    except EnrollmentOperationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from None
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=WRITE_CONFLICT_MESSAGE,
        ) from None
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=WRITE_FAILURE_MESSAGE,
        ) from None

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                'attachment; filename="regenerated-activation-code.csv"'
            ),
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
        },
    )


@router.patch(
    "/{course_id}/enrollments/{enrollment_id}/status",
    response_model=InstructorEnrollmentResponse,
)
def update_enrollment_status(
    course_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    request: EnrollmentStatusRequest,
    db: Annotated[Session, Depends(get_db)],
    instructor: Annotated[User, Depends(require_instructor)],
) -> InstructorEnrollmentResponse:
    enrollment = find_owned_enrollment(
        db,
        course_id,
        enrollment_id,
        instructor.id,
    )
    if enrollment is None:
        raise _not_found()
    _require_active_course(enrollment.course.is_active)

    try:
        set_enrollment_enabled(enrollment, enabled=request.enabled)
    except EnrollmentOperationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from None
    _commit_enrollment_change(db)
    return InstructorEnrollmentResponse.from_enrollment(enrollment)


@router.delete(
    "/{course_id}/enrollments/{enrollment_id}/nickname",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_enrollment_nickname(
    course_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    instructor: Annotated[User, Depends(require_instructor)],
) -> Response:
    enrollment = find_owned_enrollment(
        db,
        course_id,
        enrollment_id,
        instructor.id,
    )
    if enrollment is None:
        raise _not_found()
    _require_active_course(enrollment.course.is_active)

    reset_enrollment_nickname(enrollment)
    _commit_enrollment_change(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
