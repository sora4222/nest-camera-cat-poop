"""${message}.

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""

from alembic import op  # noqa: F401 (most migrations use it)

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply this migration."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Undo this migration."""
    ${downgrades if downgrades else "pass"}
