"""Typed application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator
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


class AuthSettings(BaseSettings):
    """Authentication and credentialed frontend settings."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    jwt_secret: SecretStr | None = None
    auth_cookie_secure: bool = False
    access_token_minutes: int = Field(default=30, ge=5, le=1440)
    activation_token_minutes: int = Field(default=10, ge=5, le=30)
    frontend_origin: str = "http://localhost:5173"

    @field_validator("frontend_origin")
    @classmethod
    def require_specific_http_origin(cls, value: str) -> str:
        origin = value.strip().rstrip("/")
        parsed = urlparse(origin)
        if (
            origin == "*"
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path not in {"", "/"}
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "FRONTEND_ORIGIN must be one explicit HTTP or HTTPS origin"
            )
        return origin


@lru_cache
def get_database_settings() -> DatabaseSettings:
    """Return one validated settings object per application process."""

    return DatabaseSettings()


def get_development_instructor_settings() -> DevelopmentInstructorSettings:
    """Load optional local instructor seed settings without caching secrets."""

    return DevelopmentInstructorSettings()


@lru_cache
def get_auth_settings() -> AuthSettings:
    """Return authentication settings without exposing secret values."""

    return AuthSettings()
