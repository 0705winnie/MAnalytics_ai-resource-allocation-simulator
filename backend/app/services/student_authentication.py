"""Constant-shape authentication for course-scoped Student sessions."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, contains_eager

from app.core.security import DUMMY_PASSWORD_HASH, verify_password
from app.models import CourseInstance, Enrollment, User
from app.models.enums import EnrollmentStatus, UserRole


@dataclass(frozen=True)
class AuthenticatedStudent:
    user: User
    course: CourseInstance
    enrollment: Enrollment


def authenticate_student(
    db: Session,
    *,
    course_code: str,
    berkeley_username: str,
    password: str,
) -> AuthenticatedStudent | None:
    """Authenticate one course enrollment with exactly one Argon2 verify."""

    enrollment = db.scalar(
        select(Enrollment)
        .join(User, Enrollment.user_id == User.id)
        .join(CourseInstance, Enrollment.course_id == CourseInstance.id)
        .where(
            CourseInstance.course_code_normalized == course_code.lower(),
            User.berkeley_username == berkeley_username,
        )
        .options(
            contains_eager(Enrollment.user),
            contains_eager(Enrollment.course),
        )
    )

    eligible = (
        enrollment is not None
        and enrollment.course.is_active
        and enrollment.user.is_active
        and enrollment.user.role == UserRole.STUDENT
        and enrollment.status == EnrollmentStatus.ACTIVE
        and bool(enrollment.nickname)
        and enrollment.activation_used_at is not None
        and enrollment.activation_code_hash is None
        and enrollment.user.password_hash is not None
    )
    stored_hash = (
        enrollment.user.password_hash
        if eligible and enrollment is not None
        else DUMMY_PASSWORD_HASH
    )
    password_matches = verify_password(password, stored_hash)
    if not eligible or not password_matches or enrollment is None:
        return None
    return AuthenticatedStudent(
        user=enrollment.user,
        course=enrollment.course,
        enrollment=enrollment,
    )
