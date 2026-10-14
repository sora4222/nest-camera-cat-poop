"""PostgreSQL for tests: CATPOOP_TEST_DATABASE_URL if set, else a throwaway Testcontainer.

The container gets a random user, database and password (with characters a URL must escape),
and Docker picks its port, so the tests show the app works with any of them. With neither a
URL nor Docker, the tests that need PostgreSQL skip, except in CI (`CI` set), where they fail.
"""

import os
import secrets
import uuid
from collections.abc import Generator

import docker
import psycopg
import pytest
from docker.errors import DockerException
from psycopg import sql
from psycopg.conninfo import make_conninfo
from testcontainers.community.postgres import PostgresContainer

URL_ENV = "CATPOOP_TEST_DATABASE_URL"
IMAGE = "postgres:16"


def _docker_running() -> bool:
    try:
        docker.from_env().ping()
    except DockerException:
        return False
    return True


def postgres_server() -> Generator[str]:
    """The URL of a server to make test schemas in; skips the test when there is none."""
    if url := os.environ.get(URL_ENV):
        yield url
        return
    if not _docker_running():
        missing = f"no Docker, and {URL_ENV} is not set"
        if os.environ.get("CI"):
            pytest.fail(missing)
        pytest.skip(missing)
    with PostgresContainer(
        IMAGE,
        username=f"user_{secrets.token_hex(4)}",
        password=secrets.token_urlsafe(16) + "@:/%?#",
        dbname=f"db_{secrets.token_hex(4)}",
        driver=None,
    ) as server:
        yield server.get_connection_url()


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
