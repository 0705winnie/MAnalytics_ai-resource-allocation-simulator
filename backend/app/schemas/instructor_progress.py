"""Instructor-facing student-progress schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Sequence

from pydantic import BaseModel

from app.models import Enrollment, Submission


class StudentProgressResponse(BaseModel):
    enrollment_id: uuid.UUID
    berkeley_username: str
    nickname: str | None
    submission_count: int
    latest_result_revenue: float | None
    latest_submitted_at: datetime | None
    best_result_revenue: float | None

    @classmethod
    def from_enrollment(
        cls,
        enrollment: Enrollment,
        submissions: Sequence[Submission],
    ) -> StudentProgressResponse:
        # `submissions` is expected pre-sorted oldest-first, so the last
        # entry is the latest submission.
        latest = submissions[-1] if submissions else None
        best = max(submissions, key=lambda s: s.total_revenue) if submissions else None
        return cls(
            enrollment_id=enrollment.id,
            berkeley_username=enrollment.user.berkeley_username,
            nickname=enrollment.nickname,
            submission_count=len(submissions),
            latest_result_revenue=latest.total_revenue if latest else None,
            latest_submitted_at=latest.submitted_at if latest else None,
            best_result_revenue=best.total_revenue if best else None,
        )


class StudentProgressListResponse(BaseModel):
    items: list[StudentProgressResponse]
    total: int
    offset: int
    limit: int
