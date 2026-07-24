"""Typed application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class DatabaseSettings(BaseSettings):
    """Database settings shared by SQLAlchemy and future migrations."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str

    @field_validator("database_url")
    @classmethod
    def require_psycopg_driver(cls, value: str) -> str:
        url = make_url(value)
        if url.drivername != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use the postgresql+psycopg driver")
        return value


class DevelopmentInstructorSettings(BaseSettings):
    """Optional local seed settings, required only by the seed command."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    dev_instructor_username: str | None = None
    dev_instructor_password: SecretStr | None = None

    @field_validator("dev_instructor_username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        return normalized or None


@lru_cache
def get_database_settings() -> DatabaseSettings:
    """Return one validated settings object per application process."""

    return DatabaseSettings()


def get_development_instructor_settings() -> DevelopmentInstructorSettings:
    """Load optional local instructor seed settings without caching secrets."""

    return DevelopmentInstructorSettings()
