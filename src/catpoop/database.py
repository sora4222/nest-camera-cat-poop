"""Bring the PostgreSQL database up to the newest Alembic migration."""

from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

MIGRATIONS = Path(__file__).parent / "migrations"


def upgrade(url: str) -> None:
    """Apply every migration not yet applied to the database at `url` (a psycopg URL)."""
    engine = create_engine("postgresql+psycopg://", creator=lambda: psycopg.connect(url))
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    finally:
        engine.dispose()
