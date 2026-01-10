"""add reminder logs

Revision ID: f1b2c3d4e5f6
Revises: 0a1b2c3d4e5f
Create Date: 2026-01-10

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1b2c3d4e5f6"
down_revision = "0a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reminder_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("to_email", sa.String(length=150), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.UniqueConstraint("kind", "entity_type", "entity_id", name="uq_reminder_logs_kind_entity"),
    )

    op.create_index(op.f("ix_reminder_logs_kind"), "reminder_logs", ["kind"], unique=False)
    op.create_index(op.f("ix_reminder_logs_entity_type"), "reminder_logs", ["entity_type"], unique=False)
    op.create_index(op.f("ix_reminder_logs_entity_id"), "reminder_logs", ["entity_id"], unique=False)
    op.create_index(op.f("ix_reminder_logs_job_id"), "reminder_logs", ["job_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_reminder_logs_job_id"), table_name="reminder_logs")
    op.drop_index(op.f("ix_reminder_logs_entity_id"), table_name="reminder_logs")
    op.drop_index(op.f("ix_reminder_logs_entity_type"), table_name="reminder_logs")
    op.drop_index(op.f("ix_reminder_logs_kind"), table_name="reminder_logs")
    op.drop_table("reminder_logs")
