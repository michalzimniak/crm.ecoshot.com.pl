"""Add invoice types and correction prefix setting

Revision ID: d3e4f5a6b7c8
Revises: aa12bb34cc56
Create Date: 2026-01-10

"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d3e4f5a6b7c8"
down_revision = "aa12bb34cc56"
branch_labels = None
depends_on = None


def upgrade():
    invoice_type_enum = sa.Enum(
        "standard", "deposit", "final", "correction", name="invoice_type_enum"
    )

    with op.batch_alter_table("invoices") as batch:
        batch.add_column(
            sa.Column(
                "invoice_type",
                invoice_type_enum,
                nullable=False,
                server_default="final",
            )
        )
        batch.add_column(sa.Column("original_invoice_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("correction_reason", sa.Text(), nullable=True))
        batch.create_foreign_key(
            "fk_invoices_original_invoice_id",
            "invoices",
            ["original_invoice_id"],
            ["id"],
        )

    op.create_index(
        "ix_invoices_invoice_type", "invoices", ["invoice_type"], unique=False
    )
    op.create_index(
        "ix_invoices_original_invoice_id",
        "invoices",
        ["original_invoice_id"],
        unique=False,
    )

    # Seed default invoice correction prefix into DB-backed settings (idempotent).
    settings = sa.table(
        "settings",
        sa.column("key", sa.String()),
        sa.column("value", sa.Text()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )

    bind = op.get_bind()
    exists = bind.execute(
        sa.select(sa.literal(1)).select_from(settings).where(settings.c.key == "INVOICE_CORRECTION_PREFIX")
    ).first()
    if not exists:
        now = datetime.utcnow()
        bind.execute(
            settings.insert().values(
                key="INVOICE_CORRECTION_PREFIX",
                value="FKV",
                created_at=now,
                updated_at=now,
            )
        )


def downgrade():
    bind = op.get_bind()
    try:
        bind.execute(sa.text("DELETE FROM settings WHERE `key` = 'INVOICE_CORRECTION_PREFIX'"))
    except Exception:
        bind.execute(sa.text("DELETE FROM settings WHERE key = 'INVOICE_CORRECTION_PREFIX'"))

    op.drop_index("ix_invoices_original_invoice_id", table_name="invoices")
    op.drop_index("ix_invoices_invoice_type", table_name="invoices")

    with op.batch_alter_table("invoices") as batch:
        batch.drop_constraint("fk_invoices_original_invoice_id", type_="foreignkey")
        batch.drop_column("correction_reason")
        batch.drop_column("original_invoice_id")
        batch.drop_column("invoice_type")

    try:
        sa.Enum(name="invoice_type_enum").drop(bind, checkfirst=True)
    except Exception:
        pass
