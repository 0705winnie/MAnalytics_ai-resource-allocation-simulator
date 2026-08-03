"""Student activation verification and completion API schemas."""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MAX_RAW_NICKNAME_LENGTH = 128


class PasswordMode(StrEnum):
    CREATE = "create"
    CONFIRM = "confirm"


class ActivationVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_code: str = Field(min_length=1, max_length=64)
    berkeley_username: str = Field(min_length=1, max_length=64)
    activation_code: str = Field(min_length=1, max_length=32)

    @field_validator("course_code", "activation_code", mode="before")
    @classmethod
    def trim_credential_fields(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("berkeley_username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class ActivationVerificationResponse(BaseModel):
    verified: bool
    expires_in_seconds: int
    password_mode: PasswordMode


class ActivationCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=12, max_length=128)
    password_confirmation: str = Field(min_length=12, max_length=128)
    nickname: str

    @field_validator("nickname", mode="before")
    @classmethod
    def normalize_nickname(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        if len(value) > MAX_RAW_NICKNAME_LENGTH:
            raise ValueError("Nickname exceeds the input length limit")
        if any(
            character in {"\r", "\n", "\t"}
            or unicodedata.category(character).startswith("C")
            for character in value
        ):
            raise ValueError("Nickname contains invalid characters")
        return re.sub(r" +", " ", value.strip())

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, value: str) -> str:
        if not 3 <= len(value) <= 30:
            raise ValueError("Nickname must be between 3 and 30 characters")
        if (
            not value[0].isalnum()
            or not value[-1].isalnum()
            or any(
                not (character.isalnum() or character in {" ", "-", "_"})
                for character in value
            )
        ):
            raise ValueError("Nickname contains invalid characters")
        return value

    @model_validator(mode="after")
    def require_matching_passwords(self) -> ActivationCompleteRequest:
        if self.password != self.password_confirmation:
            raise ValueError("Passwords must match")
        return self
