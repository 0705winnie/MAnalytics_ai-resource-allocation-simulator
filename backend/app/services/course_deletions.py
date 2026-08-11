"""Explicit, course-scoped destructive operations for instructor corrections."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    CourseInstance,
    Enrollment,
    MonthlyResult,
    SimulationSession,
    Submission,
)


def remove_owned_enrollment(
    db: Session,
    *,
    course_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    instructor_id: uuid.UUID,
) -> bool:
    """Delete one owned course enrollment's data without committing."""

    owned_enrollment_id = db.scalar(
        select(Enrollment.id)
        .join(CourseInstance, Enrollment.course_id == CourseInstance.id)
        .where(
            Enrollment.id == enrollment_id,
            Enrollment.course_id == course_id,
            CourseInstance.created_by == instructor_id,
        )
        .with_for_update()
    )
    if owned_enrollment_id is None:
        return False

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

    enrollment_ids = select(Enrollment.id).where(
        Enrollment.course_id == owned_course_id
    )
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
    db.execute(delete(CourseInstance).where(CourseInstance.id == owned_course_id))
    return True
