import pytest
from alembic import command
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect
from sqlalchemy.engine import URL

from tests.conftest import validate_test_database_url


HEAD_REVISION = "0001_account_foundation"
ACCOUNT_TABLES = {"users", "course_instances", "enrollments"}


def _current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _table_names(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


@pytest.mark.parametrize(
    "database_name",
    ["resource_allocation", "postgres", "template0", "template1", "another_database"],
)
def test_destructive_database_guard_rejects_non_test_names(database_name):
    with pytest.raises(pytest.UsageError, match="ending exactly in '_test'"):
        validate_test_database_url(f"postgresql+psycopg:///{database_name}")


def test_upgrade_downgrade_and_reupgrade(
    test_alembic_config,
    test_engine: Engine,
    test_database_url: URL,
):
    assert test_database_url.database is not None
    assert test_database_url.database.endswith("_test")

    try:
        command.downgrade(test_alembic_config, "base")
        assert ACCOUNT_TABLES.isdisjoint(_table_names(test_engine))
        assert _current_revision(test_engine) is None

        command.upgrade(test_alembic_config, "head")
        assert ACCOUNT_TABLES.issubset(_table_names(test_engine))
        assert _current_revision(test_engine) == HEAD_REVISION

        command.downgrade(test_alembic_config, "base")
        assert ACCOUNT_TABLES.isdisjoint(_table_names(test_engine))
        assert _current_revision(test_engine) is None
    finally:
        command.upgrade(test_alembic_config, "head")

    assert _current_revision(test_engine) == HEAD_REVISION


def test_alembic_check_reports_no_drift(test_alembic_config):
    command.upgrade(test_alembic_config, "head")

    command.check(test_alembic_config)
