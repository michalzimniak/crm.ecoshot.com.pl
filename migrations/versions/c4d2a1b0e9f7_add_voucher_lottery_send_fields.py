"""add voucher lottery send fields

Revision ID: c4d2a1b0e9f7
Revises: d3e4f5a6b7c8
Create Date: 2026-01-10

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4d2a1b0e9f7"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("vouchers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("lottery_reserved_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("lottery_sent_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("lottery_customer_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("lottery_sent_email", sa.String(length=150), nullable=True))

        batch_op.create_foreign_key(
            "fk_vouchers_lottery_customer_id_customers",
            "customers",
            ["lottery_customer_id"],
            ["id"],
        )

    op.create_index("ix_vouchers_lottery_reserved_at", "vouchers", ["lottery_reserved_at"], unique=False)
    op.create_index("ix_vouchers_lottery_sent_at", "vouchers", ["lottery_sent_at"], unique=False)
    op.create_index("ix_vouchers_lottery_customer_id", "vouchers", ["lottery_customer_id"], unique=False)


def downgrade():
    op.drop_index("ix_vouchers_lottery_customer_id", table_name="vouchers")
    op.drop_index("ix_vouchers_lottery_sent_at", table_name="vouchers")
    op.drop_index("ix_vouchers_lottery_reserved_at", table_name="vouchers")

    with op.batch_alter_table("vouchers", schema=None) as batch_op:
        batch_op.drop_constraint("fk_vouchers_lottery_customer_id_customers", type_="foreignkey")
        batch_op.drop_column("lottery_sent_email")
        batch_op.drop_column("lottery_customer_id")
        batch_op.drop_column("lottery_sent_at")
        batch_op.drop_column("lottery_reserved_at")
