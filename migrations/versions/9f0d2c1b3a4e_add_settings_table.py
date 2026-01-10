"""add settings table

Revision ID: 9f0d2c1b3a4e
Revises: 6d1a8c9b2f01
Create Date: 2026-01-09

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9f0d2c1b3a4e"
down_revision = "6d1a8c9b2f01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_settings_key", "settings", ["key"], unique=True)


def downgrade():
    op.drop_index("ix_settings_key", table_name="settings")
    op.drop_table("settings")
