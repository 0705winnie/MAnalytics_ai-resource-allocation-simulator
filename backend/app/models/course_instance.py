"""Course and semester model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Computed, DateTime, ForeignKey, String, UniqueConstraint, Uuid, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.enrollment import Enrollment
    from app.models.user import User


class CourseInstance(Base):
    __tablename__ = "course_instances"
    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(course_code)) BETWEEN 1 AND 64",
            name="ck_course_instances_course_code_length",
        ),
        CheckConstraint(
            "char_length(btrim(semester)) BETWEEN 1 AND 64",
            name="ck_course_instances_semester_length",
        ),
        UniqueConstraint(
            "course_code_normalized", "semester_normalized",
            name="uq_course_instances_code_semester_normalized",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    course_code: Mapped[str] = mapped_column(String(64), nullable=False)
    course_code_normalized: Mapped[str] = mapped_column(
        String(64),
        Computed("lower(btrim(course_code))", persisted=True),
        nullable=False,
    )
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    semester: Mapped[str] = mapped_column(String(64), nullable=False)
    semester_normalized: Mapped[str] = mapped_column(
        String(64),
        Computed("lower(btrim(semester))", persisted=True),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
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

    creator: Mapped[User] = relationship(
        back_populates="created_courses",
        foreign_keys=[created_by],
    )
    enrollments: Mapped[list[Enrollment]] = relationship(
        back_populates="course",
    )

    @property
    def course_identifier(self) -> str:
        from app.services.course_identity import course_identifier

        return course_identifier(self.course_code, self.semester)
