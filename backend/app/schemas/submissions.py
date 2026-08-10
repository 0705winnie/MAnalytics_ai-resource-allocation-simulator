"""Student-facing submission schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict

from pydantic import BaseModel, ConfigDict, Field

from app.models import Submission


class SubmitResultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_code: str = Field(..., min_length=1, description="The student's admission_policy source")
    params: Dict[str, float] = Field(default_factory=dict, description="Student-tunable parameters")


class SubmitResultResponse(BaseModel):
    id: uuid.UUID
    total_revenue: float
    total_unfinished_requests: int
    total_unfinished_value: float
    warnings_count: int
    submitted_at: datetime

    @classmethod
    def from_submission(cls, submission: Submission) -> SubmitResultResponse:
        return cls(
            id=submission.id,
            total_revenue=submission.total_revenue,
            total_unfinished_requests=submission.total_unfinished_requests,
            total_unfinished_value=submission.total_unfinished_value,
            warnings_count=submission.warnings_count,
            submitted_at=submission.submitted_at,
        )
