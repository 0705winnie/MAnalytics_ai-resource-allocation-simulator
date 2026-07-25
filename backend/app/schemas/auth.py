"""Authentication response schemas shared by login and activation."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.models.enums import UserRole


class AuthenticatedUserResponse(BaseModel):
    id: uuid.UUID
    username: str
    role: UserRole


class AuthenticatedCourseResponse(BaseModel):
    id: uuid.UUID
    course_code: str


class AuthenticationResponse(BaseModel):
    authenticated: bool
    user: AuthenticatedUserResponse
    course: AuthenticatedCourseResponse | None = None
    nickname: str | None = None
