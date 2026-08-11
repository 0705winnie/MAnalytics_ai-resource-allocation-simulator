"""An immutable official result for one completed simulation month."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.simulation_session import SimulationSession


class MonthlyResult(Base):
    __tablename__ = "monthly_results"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "month",
            name="uq_monthly_results_session_month",
        ),
        UniqueConstraint(
            "session_id",
            "idempotency_key",
            name="uq_monthly_results_session_idempotency_key",
        ),
        CheckConstraint(
            "month BETWEEN 1 AND 12",
            name="ck_monthly_results_month_range",
        ),
        CheckConstraint(
            "total_requests >= 0 "
            "AND admitted_requests >= 0 "
            "AND completed_requests >= 0 "
            "AND rejected_requests >= 0 "
            "AND unfinished_requests >= 0",
            name="ck_monthly_results_nonnegative_counts",
        ),
        CheckConstraint(
            "total_revenue >= 0 AND unfinished_value >= 0",
            name="ck_monthly_results_nonnegative_values",
        ),
        CheckConstraint(
            "admitted_requests <= total_requests",
            name="ck_monthly_results_admitted_within_total",
        ),
        CheckConstraint(
            "completed_requests <= admitted_requests",
            name="ck_monthly_results_completed_within_admitted",
        ),
        CheckConstraint(
            "rejected_requests = total_requests - admitted_requests",
            name="ck_monthly_results_rejected_consistent",
        ),
        CheckConstraint(
            "unfinished_requests = admitted_requests - completed_requests",
            name="ck_monthly_results_unfinished_consistent",
        ),
        CheckConstraint(
            "jsonb_typeof(policy_params) = 'object'",
            name="ck_monthly_results_policy_params_object",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("simulation_sessions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    policy_code: Mapped[str] = mapped_column(Text, nullable=False)
    policy_params: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False)
    policy_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    total_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    admitted_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    total_revenue: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    unfinished_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    unfinished_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )
    avg_utilization: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False)
    peak_utilization: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False)
    remaining_capacity: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False)
    by_type: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    benchmark_comparison: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    session: Mapped[SimulationSession] = relationship(
        back_populates="monthly_results",
    )
