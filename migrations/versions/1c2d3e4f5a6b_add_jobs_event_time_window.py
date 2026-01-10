"""add jobs event time window

Revision ID: 1c2d3e4f5a6b
Revises: 9f0d2c1b3a4e
Create Date: 2026-01-09

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1c2d3e4f5a6b"
down_revision = "9f0d2c1b3a4e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("event_start", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("event_end", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_jobs_event_start", ["event_start"], unique=False)
        batch_op.create_index("ix_jobs_event_end", ["event_end"], unique=False)


def downgrade():
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_index("ix_jobs_event_end")
        batch_op.drop_index("ix_jobs_event_start")
        batch_op.drop_column("event_end")
        batch_op.drop_column("event_start")
