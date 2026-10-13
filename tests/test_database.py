import psycopg
import pytest
from postgres_schema import empty_schema, needs_postgres

from catpoop.database import upgrade


@pytest.fixture
def conninfo():
    yield from empty_schema()


def tables(conninfo: str) -> set[str]:
    with psycopg.connect(conninfo) as db:
        rows = db.execute("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")
        return {name for (name,) in rows}


@needs_postgres
def test_upgrade_makes_the_events_table_and_records_the_version(conninfo):
    upgrade(conninfo)
    assert tables(conninfo) == {"events", "alembic_version"}


@needs_postgres
def test_upgrade_twice_changes_nothing(conninfo):
    upgrade(conninfo)
    upgrade(conninfo)
    assert tables(conninfo) == {"events", "alembic_version"}


@needs_postgres
def test_a_table_made_before_migrations_is_adopted(conninfo):
    with psycopg.connect(conninfo, autocommit=True) as db:
        db.execute(
            "CREATE TABLE events (id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, "
            "at TIMESTAMPTZ NOT NULL, kind TEXT NOT NULL, urgency TEXT NOT NULL, "
            "announce BOOLEAN NOT NULL, details JSONB NOT NULL)"
        )
    upgrade(conninfo)
    assert tables(conninfo) == {"events", "alembic_version"}
