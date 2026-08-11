"""A student's server-computed full-year simulation result."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.enrollment import Enrollment


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("enrollments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    total_revenue: Mapped[float] = mapped_column(Float, nullable=False)
    total_unfinished_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    total_unfinished_value: Mapped[float] = mapped_column(Float, nullable=False)
    warnings_count: Mapped[int] = mapped_column(Integer, nullable=False)
    months_completed: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    enrollment: Mapped[Enrollment] = relationship(
        back_populates="submissions",
    )
