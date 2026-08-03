"""Shared fixtures that isolate destructive database tests."""

from collections.abc import Generator
from pathlib import Path

import pytest
from alembic.config import Config
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
PROTECTED_DATABASES = {
    "resource_allocation",
    "postgres",
    "template0",
    "template1",
}


class _TestDatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    test_database_url: str


def validate_test_database_url(value: str | URL) -> URL:
    """Parse and reject any URL that cannot safely host destructive tests."""

    try:
        url = value if isinstance(value, URL) else make_url(value)
    except ArgumentError as exc:
        raise pytest.UsageError(
            "TEST_DATABASE_URL must be a valid SQLAlchemy database URL"
        ) from exc

    database_name = url.database or ""
    if (
        url.drivername != "postgresql+psycopg"
        or database_name in PROTECTED_DATABASES
        or not database_name.endswith("_test")
    ):
        raise pytest.UsageError(
            "Refusing destructive database tests: TEST_DATABASE_URL must use "
            "postgresql+psycopg and a database name ending exactly in '_test'; "
            f"received database name {database_name!r}"
        )
    return url


@pytest.fixture(scope="session")
def test_database_url() -> URL:
    """Return the independently configured and safety-checked test URL."""

    try:
        settings = _TestDatabaseSettings()
    except ValidationError as exc:
        raise pytest.UsageError(
            "TEST_DATABASE_URL is required for database integration tests"
        ) from exc
    return validate_test_database_url(settings.test_database_url)


@pytest.fixture(scope="session")
def test_engine(test_database_url: URL) -> Generator[Engine, None, None]:
    """Create an engine only after the destructive-test guard passes."""

    engine = create_engine(test_database_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def test_alembic_config(test_database_url: URL) -> Config:
    """Point Alembic at the guarded test URL without changing app settings."""

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.attributes["database_url"] = test_database_url
    return config
