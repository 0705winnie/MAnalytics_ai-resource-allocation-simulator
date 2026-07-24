from pathlib import Path
import re

import pytest
from pydantic import ValidationError

from app.core.config import DatabaseSettings
from app.db.base import Base, CONSTRAINT_NAMING_CONVENTION


VALID_DATABASE_URL = (
    "postgresql+psycopg://test_user:test_password@localhost:5432/test_database"
)


def test_database_url_is_loaded_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", VALID_DATABASE_URL)

    settings = DatabaseSettings(_env_file=None)

    assert settings.database_url == VALID_DATABASE_URL


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        DatabaseSettings(_env_file=None)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://test_user:test_password@localhost/test_database",
        "sqlite:///test.db",
    ],
)
def test_database_url_requires_psycopg_driver(monkeypatch, database_url):
    monkeypatch.setenv("DATABASE_URL", database_url)

    with pytest.raises(ValidationError, match=r"postgresql\+psycopg"):
        DatabaseSettings(_env_file=None)


def test_declarative_base_uses_deterministic_constraint_names():
    assert Base.metadata.naming_convention == CONSTRAINT_NAMING_CONVENTION
    assert set(CONSTRAINT_NAMING_CONVENTION) == {"ix", "uq", "ck", "fk", "pk"}


def test_application_code_does_not_hard_code_database_credentials():
    app_root = Path(__file__).resolve().parents[1] / "app"
    credential_url = re.compile(r"postgresql\+psycopg://[^/\s:]+:[^@\s]+@")

    for source_path in app_root.rglob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        assert credential_url.search(source) is None, (
            f"Hard-coded database credentials found in {source_path}"
        )
