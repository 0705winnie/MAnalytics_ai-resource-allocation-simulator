"""Explicit, course-scoped destructive operations for instructor corrections."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    CourseInstance,
    Enrollment,
    LLMDailyUsage,
    MonthlyResult,
    SimulationSession,
    Submission,
    User,
)
from app.models.enums import UserRole


def remove_owned_enrollment(
    db: Session,
    *,
    course_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    instructor_id: uuid.UUID,
) -> bool:
    """Delete one owned course enrollment's data without committing."""

    owned_enrollment = db.execute(
        select(Enrollment.id, Enrollment.user_id)
        .join(CourseInstance, Enrollment.course_id == CourseInstance.id)
        .where(
            Enrollment.id == enrollment_id,
            Enrollment.course_id == course_id,
            CourseInstance.created_by == instructor_id,
        )
        .with_for_update()
    ).one_or_none()
    if owned_enrollment is None:
        return False
    owned_enrollment_id, student_user_id = owned_enrollment

    session_ids = select(SimulationSession.id).where(
        SimulationSession.enrollment_id == owned_enrollment_id
    )
    db.execute(delete(MonthlyResult).where(MonthlyResult.session_id.in_(session_ids)))
    db.execute(
        delete(SimulationSession).where(
            SimulationSession.enrollment_id == owned_enrollment_id
        )
    )
    # Legacy rows must be removed explicitly until the separately approved
    # future migration drops the submissions table.
    db.execute(delete(Submission).where(Submission.enrollment_id == owned_enrollment_id))
    db.execute(delete(Enrollment).where(Enrollment.id == owned_enrollment_id))
    db.execute(delete(LLMDailyUsage).where(LLMDailyUsage.user_id == student_user_id))
    db.execute(
        delete(User).where(
            User.id == student_user_id,
            User.course_id == course_id,
            User.role == UserRole.STUDENT,
        )
    )
    return True


def remove_owned_course(
    db: Session,
    *,
    course_id: uuid.UUID,
    instructor_id: uuid.UUID,
) -> bool:
    """Delete one owned course and all course-scoped data without committing."""

    owned_course_id = db.scalar(
        select(CourseInstance.id)
        .where(
            CourseInstance.id == course_id,
            CourseInstance.created_by == instructor_id,
        )
        .with_for_update()
    )
    if owned_course_id is None:
        return False

    enrollment_rows = db.execute(
        select(Enrollment.id, Enrollment.user_id).where(
            Enrollment.course_id == owned_course_id
        )
    ).all()
    enrollment_ids = [row.id for row in enrollment_rows]
    student_user_ids = list(db.scalars(
        select(User.id).where(
            User.course_id == owned_course_id,
            User.role == UserRole.STUDENT,
        )
    ))
    session_ids = select(SimulationSession.id).where(
        SimulationSession.enrollment_id.in_(enrollment_ids)
    )
    db.execute(delete(MonthlyResult).where(MonthlyResult.session_id.in_(session_ids)))
    db.execute(
        delete(SimulationSession).where(
            SimulationSession.enrollment_id.in_(enrollment_ids)
        )
    )
    db.execute(delete(Submission).where(Submission.enrollment_id.in_(enrollment_ids)))
    db.execute(delete(Enrollment).where(Enrollment.course_id == owned_course_id))
    if student_user_ids:
        db.execute(delete(LLMDailyUsage).where(LLMDailyUsage.user_id.in_(student_user_ids)))
        db.execute(
            delete(User).where(
                User.id.in_(student_user_ids),
                User.course_id == owned_course_id,
                User.role == UserRole.STUDENT,
            )
        )
    db.execute(delete(CourseInstance).where(CourseInstance.id == owned_course_id))
    return True
