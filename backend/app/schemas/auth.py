"""Authentication response schemas shared by login and activation."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import UserRole


MAX_LOGIN_COURSE_CODE_LENGTH = 64
MAX_LOGIN_USERNAME_LENGTH = 64
MAX_LOGIN_PASSWORD_LENGTH = 128


class StudentLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_code: str = Field(
        min_length=1,
        max_length=MAX_LOGIN_COURSE_CODE_LENGTH,
    )
    berkeley_username: str = Field(
        min_length=1,
        max_length=MAX_LOGIN_USERNAME_LENGTH,
    )
    password: str = Field(
        min_length=1,
        max_length=MAX_LOGIN_PASSWORD_LENGTH,
    )

    @field_validator("course_code", mode="before")
    @classmethod
    def normalize_course_code(cls, value: object) -> object:
        if isinstance(value, str):
            if len(value) > MAX_LOGIN_COURSE_CODE_LENGTH:
                raise ValueError("Course code exceeds the input length limit")
            return value.strip()
        return value

    @field_validator("berkeley_username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        if isinstance(value, str):
            if len(value) > MAX_LOGIN_USERNAME_LENGTH:
                raise ValueError("Username exceeds the input length limit")
            return value.strip().lower()
        return value

    @field_validator("password", mode="before")
    @classmethod
    def limit_raw_password(cls, value: object) -> object:
        if isinstance(value, str) and len(value) > MAX_LOGIN_PASSWORD_LENGTH:
            raise ValueError("Password exceeds the input length limit")
        return value


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
