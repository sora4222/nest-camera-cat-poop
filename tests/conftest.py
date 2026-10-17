"""Shared fixtures: one PostgreSQL server per test run, and an empty schema per test."""

from collections.abc import Iterator

import pytest
from postgres_server import empty_schema, postgres_server


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """A PostgreSQL server for the whole run (see `postgres_server`)."""
    with postgres_server() as url:
        yield url


@pytest.fixture
def database_url(postgres_url: str) -> Iterator[str]:
    """A new, empty schema on that server, dropped after the test."""
    with empty_schema(postgres_url) as url:
        yield url
