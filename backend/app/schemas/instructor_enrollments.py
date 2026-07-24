"""Safe Instructor-facing enrollment schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, StrictBool

from app.models import Enrollment
from app.models.enums import EnrollmentStatus


class EnrollmentStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool


class InstructorEnrollmentResponse(BaseModel):
    enrollment_id: uuid.UUID
    berkeley_username: str
    nickname: str | None
    status: EnrollmentStatus
    user_is_active: bool
    activated: bool
    activation_expires_at: datetime | None
    activation_used_at: datetime | None
    created_at: datetime

    @classmethod
    def from_enrollment(
        cls,
        enrollment: Enrollment,
    ) -> InstructorEnrollmentResponse:
        return cls(
            enrollment_id=enrollment.id,
            berkeley_username=enrollment.user.berkeley_username,
            nickname=enrollment.nickname,
            status=enrollment.status,
            user_is_active=enrollment.user.is_active,
            activated=enrollment.activation_used_at is not None,
            activation_expires_at=enrollment.activation_expires_at,
            activation_used_at=enrollment.activation_used_at,
            created_at=enrollment.created_at,
        )


class InstructorEnrollmentListResponse(BaseModel):
    items: list[InstructorEnrollmentResponse]
    total: int
    offset: int
    limit: int
