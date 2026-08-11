"""Course enrollment and course-specific public identity model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EnrollmentStatus

if TYPE_CHECKING:
    from app.models.course_instance import CourseInstance
    from app.models.simulation_session import SimulationSession
    from app.models.submission import Submission
    from app.models.user import User


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'disabled')",
            name="enrollment_status",
        ),
        UniqueConstraint("user_id", name="uq_enrollments_user_id"),
        ForeignKeyConstraint(
            ["user_id", "course_id"],
            ["users.id", "users.course_id"],
            name="fk_enrollments_user_course_users",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "course_id",
            "nickname_normalized",
            name="uq_enrollments_course_nickname_normalized",
        ),
        CheckConstraint(
            "nickname IS NULL OR "
            "(nickname = btrim(nickname) AND char_length(nickname) BETWEEN 3 AND 30)",
            name="ck_enrollments_nickname_normalized_length",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("course_instances.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    nickname: Mapped[str | None] = mapped_column(String(30), nullable=True)
    nickname_normalized: Mapped[str | None] = mapped_column(
        String(30),
        Computed("lower(btrim(nickname))", persisted=True),
        nullable=True,
    )
    activation_code_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    activation_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    activation_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[EnrollmentStatus] = mapped_column(
        Enum(
            EnrollmentStatus,
            name="enrollment_status",
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            values_callable=lambda enum_type: [member.value for member in enum_type],
        ),
        nullable=False,
        default=EnrollmentStatus.PENDING,
        server_default=EnrollmentStatus.PENDING.value,
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

    course: Mapped[CourseInstance] = relationship(
        back_populates="enrollments",
    )
    user: Mapped[User] = relationship(
        back_populates="enrollments",
        foreign_keys=[user_id],
    )
    submissions: Mapped[list[Submission]] = relationship(
        back_populates="enrollment",
    )
    simulation_session: Mapped[SimulationSession] = relationship(
        back_populates="enrollment",
        uselist=False,
    )
