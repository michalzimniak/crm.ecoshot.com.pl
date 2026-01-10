"""add promotions table

Revision ID: 2a4b6c8d0e12
Revises: 1c2d3e4f5a6b
Create Date: 2026-01-09

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2a4b6c8d0e12"
down_revision = "1c2d3e4f5a6b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "promotions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("promo_type", sa.String(length=50), nullable=False),
        sa.Column("value", sa.Numeric(10, 2), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("active_until", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_promotions_promo_type", "promotions", ["promo_type"], unique=False)
    op.create_index("ix_promotions_active_until", "promotions", ["active_until"], unique=False)


def downgrade():
    op.drop_index("ix_promotions_active_until", table_name="promotions")
    op.drop_index("ix_promotions_promo_type", table_name="promotions")
    op.drop_table("promotions")
