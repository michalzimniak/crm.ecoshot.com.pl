"""convert promotion voucher layout mm to px

Revision ID: 0a1b2c3d4e5f
Revises: 8c1f2a3b4d5e
Create Date: 2026-01-10

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0a1b2c3d4e5f"
down_revision = "8c1f2a3b4d5e"
branch_labels = None
depends_on = None


_MM_TO_PX = 96.0 / 25.4
_PX_TO_MM = 25.4 / 96.0


def upgrade():
    # 1) Add px columns
    with op.batch_alter_table("promotions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("voucher_text_x_px", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column("voucher_text_y_px", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column("voucher_qr_x_px", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column("voucher_qr_y_px", sa.Numeric(10, 2), nullable=True))

    # 2) Migrate existing values (best-effort)
    op.execute(
        f"""
        UPDATE promotions
        SET
            voucher_text_x_px = CASE WHEN voucher_text_x_mm IS NULL THEN NULL ELSE voucher_text_x_mm * {_MM_TO_PX} END,
            voucher_text_y_px = CASE WHEN voucher_text_y_mm IS NULL THEN NULL ELSE voucher_text_y_mm * {_MM_TO_PX} END,
            voucher_qr_x_px = CASE WHEN voucher_qr_x_mm IS NULL THEN NULL ELSE voucher_qr_x_mm * {_MM_TO_PX} END,
            voucher_qr_y_px = CASE WHEN voucher_qr_y_mm IS NULL THEN NULL ELSE voucher_qr_y_mm * {_MM_TO_PX} END
        """
    )

    # 3) Drop mm columns
    with op.batch_alter_table("promotions", schema=None) as batch_op:
        batch_op.drop_column("voucher_text_x_mm")
        batch_op.drop_column("voucher_text_y_mm")
        batch_op.drop_column("voucher_qr_x_mm")
        batch_op.drop_column("voucher_qr_y_mm")


def downgrade():
    # 1) Re-add mm columns
    with op.batch_alter_table("promotions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("voucher_text_x_mm", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column("voucher_text_y_mm", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column("voucher_qr_x_mm", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column("voucher_qr_y_mm", sa.Numeric(10, 2), nullable=True))

    # 2) Convert back px -> mm
    op.execute(
        f"""
        UPDATE promotions
        SET
            voucher_text_x_mm = CASE WHEN voucher_text_x_px IS NULL THEN NULL ELSE voucher_text_x_px * {_PX_TO_MM} END,
            voucher_text_y_mm = CASE WHEN voucher_text_y_px IS NULL THEN NULL ELSE voucher_text_y_px * {_PX_TO_MM} END,
            voucher_qr_x_mm = CASE WHEN voucher_qr_x_px IS NULL THEN NULL ELSE voucher_qr_x_px * {_PX_TO_MM} END,
            voucher_qr_y_mm = CASE WHEN voucher_qr_y_px IS NULL THEN NULL ELSE voucher_qr_y_px * {_PX_TO_MM} END
        """
    )

    # 3) Drop px columns
    with op.batch_alter_table("promotions", schema=None) as batch_op:
        batch_op.drop_column("voucher_text_x_px")
        batch_op.drop_column("voucher_text_y_px")
        batch_op.drop_column("voucher_qr_x_px")
        batch_op.drop_column("voucher_qr_y_px")
