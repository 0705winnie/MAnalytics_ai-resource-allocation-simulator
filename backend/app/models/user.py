"""Global course-account user model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, String, Uuid, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.course_instance import CourseInstance
    from app.models.enrollment import Enrollment


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
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    berkeley_username: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
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
    )
    enrollments: Mapped[list[Enrollment]] = relationship(
        back_populates="user",
    )
