"""Concurrency-safe reservation and reconciliation for paid LLM calls."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_UP
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import LLMQuotaSettings
from app.models import LLMDailyUsage


COST_QUANTUM = Decimal("0.000001")


class LLMQuotaExceeded(RuntimeError):
    def __init__(self, limit_type: str, resets_at: datetime) -> None:
        super().__init__("Daily AI assistant usage limit reached.")
        self.limit_type = limit_type
        self.resets_at = resets_at


@dataclass(frozen=True)
class UsageStatus:
    calls_used: int
    calls_limit: int
    resets_at: datetime
    metered: bool


@dataclass(frozen=True)
class UsageReservation:
    user_id: uuid.UUID
    usage_date: date
    estimated_input_tokens: int
    reserved_cost: Decimal
    resets_at: datetime


def _usage_window(
    settings: LLMQuotaSettings,
    now: datetime | None = None,
) -> tuple[date, datetime]:
    timezone = ZoneInfo(settings.llm_usage_timezone)
    current = now or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("LLM quota timestamps must be timezone-aware")
    local = current.astimezone(timezone)
    tomorrow = local.date() + timedelta(days=1)
    return local.date(), datetime.combine(tomorrow, time.min, tzinfo=timezone)


def estimated_cost(
    input_tokens: int,
    output_tokens: int,
    settings: LLMQuotaSettings,
) -> Decimal:
    cost = (
        Decimal(input_tokens) * settings.llm_input_cost_per_million_tokens
        + Decimal(output_tokens) * settings.llm_output_cost_per_million_tokens
    ) / Decimal(1_000_000)
    return cost.quantize(COST_QUANTUM, rounding=ROUND_UP)


def get_usage_status(
    db: Session,
    user_id: uuid.UUID,
    settings: LLMQuotaSettings,
    *,
    metered: bool,
    now: datetime | None = None,
) -> UsageStatus:
    usage_date, resets_at = _usage_window(settings, now)
    call_count = db.scalar(
        select(LLMDailyUsage.call_count).where(
            LLMDailyUsage.user_id == user_id,
            LLMDailyUsage.usage_date == usage_date,
        )
    )
    return UsageStatus(
        calls_used=int(call_count or 0),
        calls_limit=settings.max_llm_calls_per_day,
        resets_at=resets_at,
        metered=metered,
    )


def reserve_llm_call(
    db: Session,
    user_id: uuid.UUID,
    input_tokens: int,
    settings: LLMQuotaSettings,
    *,
    now: datetime | None = None,
) -> UsageReservation:
    """Atomically reserve a real call and worst-case output cost."""

    usage_date, resets_at = _usage_window(settings, now)
    db.execute(
        insert(LLMDailyUsage)
        .values(user_id=user_id, usage_date=usage_date)
        .on_conflict_do_nothing(index_elements=["user_id", "usage_date"])
    )
    usage = db.scalar(
        select(LLMDailyUsage)
        .where(
            LLMDailyUsage.user_id == user_id,
            LLMDailyUsage.usage_date == usage_date,
        )
        .with_for_update()
    )
    if usage is None:
        db.rollback()
        raise RuntimeError("Daily LLM usage row could not be locked")

    reserved_cost = estimated_cost(
        input_tokens,
        settings.llm_output_token_safety_ceiling,
        settings,
    )
    if usage.call_count >= settings.max_llm_calls_per_day:
        db.rollback()
        raise LLMQuotaExceeded("calls", resets_at)
    if usage.input_tokens + input_tokens > settings.max_llm_input_tokens_per_day:
        db.rollback()
        raise LLMQuotaExceeded("input_tokens", resets_at)
    if usage.estimated_cost + reserved_cost > settings.max_llm_estimated_cost_per_day:
        db.rollback()
        raise LLMQuotaExceeded("estimated_cost", resets_at)

    usage.call_count += 1
    usage.input_tokens += input_tokens
    usage.estimated_cost += reserved_cost
    db.commit()
    return UsageReservation(
        user_id=user_id,
        usage_date=usage_date,
        estimated_input_tokens=input_tokens,
        reserved_cost=reserved_cost,
        resets_at=resets_at,
    )


def reconcile_llm_call(
    db: Session,
    reservation: UsageReservation,
    *,
    actual_input_tokens: int,
    actual_output_tokens: int,
    settings: LLMQuotaSettings,
) -> None:
    """Replace a worst-case reservation with provider-reported actual usage."""

    usage = db.scalar(
        select(LLMDailyUsage)
        .where(
            LLMDailyUsage.user_id == reservation.user_id,
            LLMDailyUsage.usage_date == reservation.usage_date,
        )
        .with_for_update()
    )
    if usage is None:
        db.rollback()
        return
    final_cost = estimated_cost(actual_input_tokens, actual_output_tokens, settings)
    usage.input_tokens = max(
        0,
        usage.input_tokens
        - reservation.estimated_input_tokens
        + actual_input_tokens,
    )
    usage.output_tokens += actual_output_tokens
    usage.estimated_cost = max(
        Decimal("0"),
        usage.estimated_cost - reservation.reserved_cost + final_cost,
    )
    db.commit()
