"""Instructor-owned enrollment queries and state transitions."""

from __future__ import annotations

import csv
import io
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import CourseInstance, Enrollment, User
from app.models.enums import EnrollmentStatus, UserRole
from app.services.activation_codes import regenerate_activation_code
from app.services.roster_imports import spreadsheet_safe_csv_cell


class EnrollmentOperationError(RuntimeError):
    """A safe enrollment-state error containing no private data."""


def find_owned_course(
    db: Session,
    course_id: uuid.UUID,
    instructor_id: uuid.UUID,
) -> CourseInstance | None:
    return db.scalar(
        select(CourseInstance).where(
            CourseInstance.id == course_id,
            CourseInstance.created_by == instructor_id,
        )
    )


def find_owned_enrollment(
    db: Session,
    course_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    instructor_id: uuid.UUID,
) -> Enrollment | None:
    return db.scalar(
        select(Enrollment)
        .join(CourseInstance, Enrollment.course_id == CourseInstance.id)
        .where(
            Enrollment.id == enrollment_id,
            Enrollment.course_id == course_id,
            CourseInstance.created_by == instructor_id,
        )
        .options(
            joinedload(Enrollment.user),
            joinedload(Enrollment.course),
        )
    )


def regenerate_student_activation(enrollment: Enrollment) -> str:
    """Regenerate one eligible pending student's code without committing."""

    if enrollment.status == EnrollmentStatus.DISABLED:
        raise EnrollmentOperationError(
            "Restore the enrollment before regenerating an activation code"
        )
    if (
        enrollment.status == EnrollmentStatus.ACTIVE
        or enrollment.activation_used_at is not None
    ):
        raise EnrollmentOperationError(
            "Active students must use the future password-reset process"
        )
    if enrollment.status != EnrollmentStatus.PENDING:
        raise EnrollmentOperationError(
            "Activation codes are available only for pending enrollments"
        )
    if enrollment.user.role != UserRole.STUDENT:
        raise EnrollmentOperationError(
            "Activation codes are available only for student enrollments"
        )
    if not enrollment.user.is_active:
        raise EnrollmentOperationError(
            "Activation codes are unavailable for inactive users"
        )
    return regenerate_activation_code(enrollment)


def set_enrollment_enabled(
    enrollment: Enrollment,
    *,
    enabled: bool,
) -> None:
    """Disable or restore one course enrollment without changing its user."""

    if not enabled:
        enrollment.status = EnrollmentStatus.DISABLED
        return
    if not enrollment.user.is_active:
        raise EnrollmentOperationError(
            "An enrollment for an inactive user cannot be restored"
        )
    enrollment.status = (
        EnrollmentStatus.ACTIVE
        if enrollment.activation_used_at is not None
        else EnrollmentStatus.PENDING
    )


def reset_enrollment_nickname(enrollment: Enrollment) -> None:
    enrollment.nickname = None


def render_regenerated_activation_csv(
    enrollment: Enrollment,
    activation_code: str,
) -> str:
    """Render a spreadsheet-safe one-row activation-code download."""

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(
        [
            "berkeley_username",
            "course_code",
            "activation_code",
            "status",
            "message",
        ]
    )
    writer.writerow(
        [
            spreadsheet_safe_csv_cell(enrollment.user.berkeley_username),
            spreadsheet_safe_csv_cell(enrollment.course.course_code),
            spreadsheet_safe_csv_cell(activation_code),
            "regenerated",
            "Activation code regenerated",
        ]
    )
    return output.getvalue()
