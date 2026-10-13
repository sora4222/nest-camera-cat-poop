"""A throwaway PostgreSQL schema per test, when CATPOOP_TEST_DATABASE_URL is set."""

import os
import uuid
from collections.abc import Generator

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

TEST_URL = os.environ.get("CATPOOP_TEST_DATABASE_URL")
needs_postgres = pytest.mark.skipif(not TEST_URL, reason="CATPOOP_TEST_DATABASE_URL is not set")


def empty_schema() -> Generator[str]:
    """A connection string whose tables go in a new, empty schema, dropped afterwards."""
    assert TEST_URL
    schema = f"test_{uuid.uuid4().hex}"
    with psycopg.connect(TEST_URL, autocommit=True) as db:
        db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    try:
        yield make_conninfo(TEST_URL, options=f"-c search_path={schema}")
    finally:
        with psycopg.connect(TEST_URL, autocommit=True) as db:
            db.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
