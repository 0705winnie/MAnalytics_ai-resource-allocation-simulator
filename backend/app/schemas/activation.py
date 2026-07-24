"""Student activation verification API schemas."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
