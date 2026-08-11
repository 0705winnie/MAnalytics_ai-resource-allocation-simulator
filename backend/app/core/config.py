"""Typed application settings loaded from environment variables."""

from functools import lru_cache
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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
    # The bare (no "/api" prefix) routers exist only so Vite's local dev
    # proxy - which strips "/api" before forwarding - can reach them; see
    # main.py. They are unused when the backend serves the built frontend
    # itself, and collide with SPA page paths like /instructor/courses.
    # Default False keeps local dev and tests unchanged; set true only for
    # a single-origin production deployment.
    disable_legacy_proxy_routes: bool = False

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


class LLMQuotaSettings(BaseSettings):
    """Non-secret paid-model guardrails and centralized pricing assumptions."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    max_llm_calls_per_day: int = Field(default=50, ge=1)
    max_llm_input_tokens_per_day: int = Field(default=100_000, ge=1)
    max_llm_output_tokens_per_call: int = Field(default=500, ge=1)
    max_llm_estimated_cost_per_day: Decimal = Field(default=Decimal("0.25"), gt=0)
    llm_usage_timezone: str = "America/Los_Angeles"
    # Conservative defaults match the documented gpt-4.1-mini deployment in
    # .env.example. Override centrally if the Azure deployment uses another model.
    llm_input_cost_per_million_tokens: Decimal = Field(default=Decimal("0.40"), ge=0)
    llm_output_cost_per_million_tokens: Decimal = Field(default=Decimal("1.60"), ge=0)

    @field_validator("llm_usage_timezone")
    @classmethod
    def require_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("LLM_USAGE_TIMEZONE must be an IANA timezone") from exc
        return value


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


@lru_cache
def get_llm_quota_settings() -> LLMQuotaSettings:
    return LLMQuotaSettings()
