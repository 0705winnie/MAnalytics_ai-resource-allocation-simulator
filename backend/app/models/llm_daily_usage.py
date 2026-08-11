"""Per-student, per-calendar-day paid LLM usage accounting."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class LLMDailyUsage(Base):
    __tablename__ = "llm_daily_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "usage_date", name="uq_llm_daily_usage_user_date"),
        CheckConstraint(
            "call_count >= 0 AND input_tokens >= 0 AND output_tokens >= 0 AND estimated_cost >= 0",
            name="ck_llm_daily_usage_nonnegative",
        ),
        Index("ix_llm_daily_usage_usage_date", "usage_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"))
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0"), server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="llm_daily_usage")
