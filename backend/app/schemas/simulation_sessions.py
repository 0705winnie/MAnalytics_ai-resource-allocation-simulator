"""Authenticated student schemas for official simulation persistence."""

from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RunNextMonthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_month: int = Field(..., ge=1)
    idempotency_key: uuid.UUID
    policy_code: str = Field(..., min_length=1)
    params: dict[str, float] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def require_finite_params(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not math.isfinite(parameter) for parameter in value.values()):
            raise ValueError("Policy parameters must be finite numbers")
        return value


class RevenueByTypeResponse(BaseModel):
    type: str
    total_revenue: float


class BenchmarkResultResponse(BaseModel):
    policy: str
    total_revenue: float
    total_unfinished_requests: int
    total_unfinished_value: float
    admitted_requests: int
    completed_requests: int
    rejected_requests: int
    warnings_count: int


class OfficialMonthlyResultResponse(BaseModel):
    month: int
    policy_code: str
    params: dict[str, float]
    policy_hash: str
    total_requests: int
    admitted_requests: int
    completed_requests: int
    rejected_requests: int
    total_revenue: float
    unfinished_requests: int
    unfinished_value: float
    avg_utilization: dict[str, float]
    peak_utilization: dict[str, float]
    by_type: list[RevenueByTypeResponse]
    warnings: list[str]
    benchmark_comparison: list[BenchmarkResultResponse]
    completed_at: datetime


class CumulativeResultResponse(BaseModel):
    total_requests: int
    admitted_requests: int
    completed_requests: int
    rejected_requests: int
    total_revenue: float
    total_unfinished_requests: int
    total_unfinished_value: float
    warnings_count: int
    by_type: list[RevenueByTypeResponse]
    benchmark_comparison: list[BenchmarkResultResponse]


class LatestPolicyResponse(BaseModel):
    policy_code: str
    params: dict[str, float]
    policy_hash: str


class OfficialSessionResponse(BaseModel):
    session_id: uuid.UUID
    completed_months: int
    next_month: int | None
    status: Literal["not_started", "in_progress", "completed"]
    cumulative: CumulativeResultResponse
    monthly_results: list[OfficialMonthlyResultResponse]
    latest_policy: LatestPolicyResponse | None


class RunNextMonthResponse(BaseModel):
    replayed: bool
    executed_month: int
    session: OfficialSessionResponse
