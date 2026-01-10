"""add contract deposit fields

Revision ID: e2c3a8f0d1aa
Revises: b7a1e9f4c2ab
Create Date: 2026-01-06

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e2c3a8f0d1aa"
down_revision = "b7a1e9f4c2ab"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("contracts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("deposit_percent", sa.Numeric(5, 2), nullable=False, server_default="10"))
        batch_op.add_column(sa.Column("deposit_amount", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(
            sa.Column(
                "deposit_status",
                sa.Enum("unpaid", "paid", "waived", name="deposit_status_enum"),
                nullable=False,
                server_default="unpaid",
            )
        )
        batch_op.add_column(sa.Column("deposit_paid_amount", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column("deposit_paid_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("deposit_notes", sa.Text(), nullable=True))

    # Add index separately (safe across engines)
    op.create_index("ix_contracts_deposit_status", "contracts", ["deposit_status"], unique=False)


def downgrade():
    op.drop_index("ix_contracts_deposit_status", table_name="contracts")

    with op.batch_alter_table("contracts", schema=None) as batch_op:
        batch_op.drop_column("deposit_notes")
        batch_op.drop_column("deposit_paid_at")
        batch_op.drop_column("deposit_paid_amount")
        batch_op.drop_column("deposit_status")
        batch_op.drop_column("deposit_amount")
        batch_op.drop_column("deposit_percent")
