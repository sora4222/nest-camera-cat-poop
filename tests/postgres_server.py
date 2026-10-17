"""PostgreSQL for tests: CATPOOP_TEST_DATABASE_URL if set, else a throwaway Testcontainer.

The container gets a random user, database and password (with characters a URL must escape),
and Docker picks its port, so the tests show the app works with any of them. With neither a
URL nor Docker, the tests that need PostgreSQL skip, except in CI (`CI` set), where they fail.
"""

import os
import secrets
import uuid
from collections.abc import Generator
from contextlib import contextmanager

import psycopg
import pytest
from docker.errors import DockerException
from psycopg import sql
from psycopg.conninfo import make_conninfo
from testcontainers.community.postgres import PostgresContainer

TEST_URL_ENV = "CATPOOP_TEST_DATABASE_URL"
IMAGE = "postgres:16"


@contextmanager
def postgres_server() -> Generator[str]:
    """The URL of a server to make test schemas in; skips the test when there is none."""
    if url := os.environ.get(TEST_URL_ENV):
        yield url
        return
    try:
        container = PostgresContainer(
            IMAGE,
            username=f"user_{secrets.token_hex(4)}",
            password=secrets.token_urlsafe(16) + "@:/%?#",
            dbname=f"db_{secrets.token_hex(4)}",
            driver=None,
        ).start()
    except DockerException as error:
        missing = f"no Docker ({error}), and {TEST_URL_ENV} is not set"
        if os.environ.get("CI"):
            pytest.fail(missing)
        pytest.skip(missing)
    try:
        yield container.get_connection_url()
    finally:
        container.stop()


@contextmanager
def empty_schema(server: str) -> Generator[str]:
    """A connection string whose tables go in a new, empty schema, dropped afterwards."""
    schema = f"test_{uuid.uuid4().hex}"
    with psycopg.connect(server, autocommit=True) as db:
        db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    try:
        yield make_conninfo(server, options=f"-c search_path={schema}")
    finally:
        with psycopg.connect(server, autocommit=True) as db:
            db.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
