"""add vouchers and promotion voucher templates

Revision ID: 7a9c1d2e3f45
Revises: 4d5e6f7a8b90
Create Date: 2026-01-10

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7a9c1d2e3f45"
down_revision = "4d5e6f7a8b90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vouchers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("promotion_id", sa.Integer(), sa.ForeignKey("promotions.id"), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("code", name="uq_vouchers_code"),
    )

    op.create_index("ix_vouchers_code", "vouchers", ["code"], unique=True)
    op.create_index("ix_vouchers_promotion_id", "vouchers", ["promotion_id"], unique=False)
    op.create_index("ix_vouchers_expires_at", "vouchers", ["expires_at"], unique=False)
    op.create_index("ix_vouchers_used_at", "vouchers", ["used_at"], unique=False)
    op.create_index("ix_vouchers_issued_at", "vouchers", ["issued_at"], unique=False)

    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("voucher_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_jobs_voucher_id", "vouchers", ["voucher_id"], ["id"])
        batch_op.create_index("ix_jobs_voucher_id", ["voucher_id"], unique=True)

        batch_op.add_column(sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default="0"))

    with op.batch_alter_table("promotions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("canva_project_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("voucher_bg_front_path", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("voucher_bg_back_path", sa.String(length=500), nullable=True))

    # Best-effort: remove server default after backfill.
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.alter_column("discount_amount", server_default=None)


def downgrade():
    with op.batch_alter_table("promotions", schema=None) as batch_op:
        batch_op.drop_column("voucher_bg_back_path")
        batch_op.drop_column("voucher_bg_front_path")
        batch_op.drop_column("canva_project_url")

    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_index("ix_jobs_voucher_id")
        batch_op.drop_constraint("fk_jobs_voucher_id", type_="foreignkey")
        batch_op.drop_column("voucher_id")
        batch_op.drop_column("discount_amount")

    op.drop_index("ix_vouchers_issued_at", table_name="vouchers")
    op.drop_index("ix_vouchers_used_at", table_name="vouchers")
    op.drop_index("ix_vouchers_expires_at", table_name="vouchers")
    op.drop_index("ix_vouchers_promotion_id", table_name="vouchers")
    op.drop_index("ix_vouchers_code", table_name="vouchers")
    op.drop_table("vouchers")
