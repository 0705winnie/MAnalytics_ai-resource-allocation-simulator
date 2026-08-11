"""Global Instructor and course-scoped Student account model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, String,
    UniqueConstraint, Uuid, func, text, true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.course_instance import CourseInstance
    from app.models.enrollment import Enrollment
    from app.models.llm_daily_usage import LLMDailyUsage


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('student', 'instructor')",
            name="user_role",
        ),
        CheckConstraint(
            "char_length(berkeley_username) BETWEEN 1 AND 64",
            name="ck_users_berkeley_username_length",
        ),
        CheckConstraint(
            "berkeley_username = lower(btrim(berkeley_username))",
            name="ck_users_berkeley_username_normalized",
        ),
        CheckConstraint(
            "(role = 'student' AND course_id IS NOT NULL) OR "
            "(role = 'instructor' AND course_id IS NULL)",
            name="ck_users_role_course_scope",
        ),
        UniqueConstraint("id", "course_id", name="uq_users_id_course_id"),
        Index(
            "uq_users_student_course_username",
            "course_id",
            "berkeley_username",
            unique=True,
            postgresql_where=text("role = 'student'"),
        ),
        Index(
            "uq_users_instructor_username",
            "berkeley_username",
            unique=True,
            postgresql_where=text("role = 'instructor'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    berkeley_username: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("course_instances.id", ondelete="RESTRICT", use_alter=True),
        nullable=True,
    )
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            values_callable=lambda enum_type: [member.value for member in enum_type],
        ),
        nullable=False,
        default=UserRole.STUDENT,
        server_default=UserRole.STUDENT.value,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    created_courses: Mapped[list[CourseInstance]] = relationship(
        back_populates="creator",
        foreign_keys="CourseInstance.created_by",
    )
    enrollments: Mapped[list[Enrollment]] = relationship(
        back_populates="user",
        foreign_keys="Enrollment.user_id",
    )
    llm_daily_usage: Mapped[list[LLMDailyUsage]] = relationship(
        back_populates="user",
    )
