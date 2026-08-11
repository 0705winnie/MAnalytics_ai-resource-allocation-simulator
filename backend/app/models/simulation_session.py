"""One official twelve-month simulation progression per enrollment."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.enrollment import Enrollment
    from app.models.monthly_result import MonthlyResult


class SimulationSession(Base):
    __tablename__ = "simulation_sessions"
    __table_args__ = (
        UniqueConstraint(
            "enrollment_id",
            name="uq_simulation_sessions_enrollment_id",
        ),
        CheckConstraint(
            "completed_months BETWEEN 0 AND 12",
            name="ck_simulation_sessions_completed_months_range",
        ),
        Index(
            "ix_simulation_sessions_completed_months",
            "completed_months",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("enrollments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    completed_months: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
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
    last_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    enrollment: Mapped[Enrollment] = relationship(
        back_populates="simulation_session",
    )
    monthly_results: Mapped[list[MonthlyResult]] = relationship(
        back_populates="session",
        order_by="MonthlyResult.month",
    )
