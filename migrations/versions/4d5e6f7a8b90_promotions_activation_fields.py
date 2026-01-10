"""promotions activation fields

Revision ID: 4d5e6f7a8b90
Revises: 2a4b6c8d0e12
Create Date: 2026-01-09

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4d5e6f7a8b90"
down_revision = "2a4b6c8d0e12"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("promotions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("activated_at", sa.DateTime(), nullable=True))
        batch_op.alter_column(
            "active_until",
            existing_type=sa.DateTime(),
            nullable=True,
        )

    # Existing promotions should not be considered active by default.
    op.execute("UPDATE promotions SET activated_at = NULL, active_until = NULL")


def downgrade():
    # Best-effort: cannot restore previous computed active_until values.
    with op.batch_alter_table("promotions", schema=None) as batch_op:
        batch_op.drop_column("activated_at")
        batch_op.alter_column(
            "active_until",
            existing_type=sa.DateTime(),
            nullable=False,
        )
