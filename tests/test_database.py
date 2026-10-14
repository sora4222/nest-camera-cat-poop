import psycopg

from catpoop.database import upgrade


def tables(conninfo: str) -> set[str]:
    with psycopg.connect(conninfo) as db:
        rows = db.execute("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")
        return {name for (name,) in rows}


def test_upgrade_makes_the_events_table_and_records_the_version(database_url):
    upgrade(database_url)
    assert tables(database_url) == {"events", "alembic_version"}


def test_upgrade_twice_changes_nothing(database_url):
    upgrade(database_url)
    upgrade(database_url)
    assert tables(database_url) == {"events", "alembic_version"}


def test_a_table_made_before_migrations_is_adopted(database_url):
    with psycopg.connect(database_url, autocommit=True) as db:
        db.execute(
            "CREATE TABLE events (id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, "
            "at TIMESTAMPTZ NOT NULL, kind TEXT NOT NULL, urgency TEXT NOT NULL, "
            "announce BOOLEAN NOT NULL, details JSONB NOT NULL)"
        )
    upgrade(database_url)
    assert tables(database_url) == {"events", "alembic_version"}
