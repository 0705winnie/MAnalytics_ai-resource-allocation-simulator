"""Instructor-facing student-progress schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.enums import EnrollmentStatus


class StudentProgressResponse(BaseModel):
    enrollment_id: uuid.UUID
    berkeley_username: str
    nickname: str | None
    enrollment_status: EnrollmentStatus
    user_is_active: bool
    completed_months: int
    cumulative_revenue: float
    last_activity: datetime | None
    simulation_status: Literal["not_started", "in_progress", "completed"]
    warnings_count: int


class StudentProgressListResponse(BaseModel):
    items: list[StudentProgressResponse]
    total: int
    offset: int
    limit: int
