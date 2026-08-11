"""Nickname-only shared leaderboard responses."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class LeaderboardEntryResponse(BaseModel):
    rank: int
    nickname: str
    completed_months: int
    cumulative_revenue: float
    last_activity: datetime | None
    is_current_user: bool


class LeaderboardResponse(BaseModel):
    stage: int
    current_user_eligible: bool | None
    items: list[LeaderboardEntryResponse]


class RankedEnrollmentRecord(BaseModel):
    """Internal typed record shared by student and instructor routers."""

    enrollment_id: uuid.UUID
    rank: int
    nickname: str
    completed_months: int
    cumulative_revenue: float
    last_activity: datetime | None
