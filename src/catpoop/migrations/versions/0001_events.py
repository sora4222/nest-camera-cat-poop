"""The events table of the event log.

IF NOT EXISTS adopts a table made before migrations existed.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Make the events table."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            at TIMESTAMPTZ NOT NULL,
            kind TEXT NOT NULL,
            urgency TEXT NOT NULL,
            announce BOOLEAN NOT NULL,
            details JSONB NOT NULL
        )
        """
    )


def downgrade() -> None:
    """Drop the events table."""
    op.execute("DROP TABLE events")
