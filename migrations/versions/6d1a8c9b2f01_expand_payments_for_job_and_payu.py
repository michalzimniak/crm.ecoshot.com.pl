"""expand payments for job and PayU

Revision ID: 6d1a8c9b2f01
Revises: c9b8a7d6e5f4
Create Date: 2026-01-06

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6d1a8c9b2f01"
down_revision = "c9b8a7d6e5f4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments", schema=None) as batch_op:
        # Allow job-level payments and provider-backed payments
        batch_op.add_column(sa.Column("job_id", sa.Integer(), nullable=True))

        # Older schema likely required invoice_id; make it optional
        batch_op.alter_column(
            "invoice_id",
            existing_type=sa.Integer(),
            nullable=True,
        )

        batch_op.add_column(
            sa.Column(
                "kind",
                sa.Enum("invoice", "deposit", "prepayment", name="payment_kind_enum"),
                nullable=False,
                server_default="invoice",
            )
        )
        batch_op.add_column(
            sa.Column(
                "source",
                sa.Enum("manual", "payu", name="payment_source_enum"),
                nullable=False,
                server_default="manual",
            )
        )
        batch_op.add_column(
            sa.Column(
                "currency",
                sa.String(length=3),
                nullable=False,
                server_default="PLN",
            )
        )

        # Convert existing string columns to enums (keeps same stored values)
        batch_op.alter_column(
            "payment_method",
            existing_type=sa.String(length=50),
            type_=sa.Enum("transfer", "cash", "card", "paypal", "other", name="payment_method_enum"),
            existing_nullable=True,
            nullable=False,
            server_default="transfer",
        )
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=50),
            type_=sa.Enum("pending", "completed", "failed", "refunded", name="payment_status_enum"),
            existing_nullable=True,
            nullable=False,
            server_default="pending",
        )

        # Provider metadata for PayU
        batch_op.add_column(sa.Column("provider_order_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("provider_ext_order_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("provider_status", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("provider_payload", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("redirect_url", sa.String(length=500), nullable=True))

        batch_op.create_foreign_key(
            "fk_payments_job_id_jobs",
            "jobs",
            ["job_id"],
            ["id"],
        )

    op.create_index("ix_payments_job_id", "payments", ["job_id"], unique=False)
    op.create_index("ix_payments_provider_order_id", "payments", ["provider_order_id"], unique=False)
    op.create_index(
        "ix_payments_provider_ext_order_id",
        "payments",
        ["provider_ext_order_id"],
        unique=True,
    )


def downgrade():
    op.drop_index("ix_payments_provider_ext_order_id", table_name="payments")
    op.drop_index("ix_payments_provider_order_id", table_name="payments")
    op.drop_index("ix_payments_job_id", table_name="payments")

    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_constraint("fk_payments_job_id_jobs", type_="foreignkey")

        batch_op.drop_column("redirect_url")
        batch_op.drop_column("provider_payload")
        batch_op.drop_column("provider_status")
        batch_op.drop_column("provider_ext_order_id")
        batch_op.drop_column("provider_order_id")

        batch_op.drop_column("currency")
        batch_op.drop_column("source")
        batch_op.drop_column("kind")

        batch_op.drop_column("job_id")

        batch_op.alter_column(
            "invoice_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

        batch_op.alter_column(
            "payment_method",
            existing_type=sa.Enum("transfer", "cash", "card", "paypal", "other", name="payment_method_enum"),
            type_=sa.String(length=50),
            existing_nullable=False,
            nullable=True,
        )
        batch_op.alter_column(
            "status",
            existing_type=sa.Enum("pending", "completed", "failed", "refunded", name="payment_status_enum"),
            type_=sa.String(length=50),
            existing_nullable=False,
            nullable=True,
        )
