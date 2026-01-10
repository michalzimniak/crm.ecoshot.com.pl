"""add promotion voucher pdf layout fields

Revision ID: 8c1f2a3b4d5e
Revises: 7a9c1d2e3f45
Create Date: 2026-01-10

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8c1f2a3b4d5e"
down_revision = "7a9c1d2e3f45"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("promotions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("voucher_text_x_mm", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column("voucher_text_y_mm", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column("voucher_qr_x_mm", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column("voucher_qr_y_mm", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column("voucher_text_font_family", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("voucher_text_font_size_pt", sa.Numeric(10, 2), nullable=True))


def downgrade():
    with op.batch_alter_table("promotions", schema=None) as batch_op:
        batch_op.drop_column("voucher_text_font_size_pt")
        batch_op.drop_column("voucher_text_font_family")
        batch_op.drop_column("voucher_qr_y_mm")
        batch_op.drop_column("voucher_qr_x_mm")
        batch_op.drop_column("voucher_text_y_mm")
        batch_op.drop_column("voucher_text_x_mm")
