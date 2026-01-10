"""Seed invoice deposit prefix setting

Revision ID: aa12bb34cc56
Revises: 5b21c3d9a8f7, f1b2c3d4e5f6
Create Date: 2026-01-10

"""

from alembic import op
import sqlalchemy as sa


def _mysql_now():
    return sa.text("CURRENT_TIMESTAMP")


# revision identifiers, used by Alembic.
revision = "aa12bb34cc56"
down_revision = ("5b21c3d9a8f7", "f1b2c3d4e5f6")
branch_labels = None
depends_on = None


def upgrade():
    # Seed default invoice deposit prefix into DB-backed settings.
    # Idempotent for repeated runs.
    op.execute(
        """
        INSERT INTO settings (`key`, `value`, created_at, updated_at)
        SELECT 'INVOICE_DEPOSIT_PREFIX', 'FZV', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        WHERE NOT EXISTS (
            SELECT 1 FROM settings WHERE `key` = 'INVOICE_DEPOSIT_PREFIX'
        )
        """.strip()
    )


def downgrade():
    op.execute("DELETE FROM settings WHERE `key` = 'INVOICE_DEPOSIT_PREFIX'")
