"""Make customer names nullable

Revision ID: 4014f4131026
Revises: 0a1b2c3d4e5f
Create Date: 2026-01-10 18:29:34.174656

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4014f4131026'
down_revision = '0a1b2c3d4e5f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('customers') as batch_op:
        batch_op.alter_column(
            'first_name',
            existing_type=sa.String(length=100),
            nullable=True,
        )
        batch_op.alter_column(
            'last_name',
            existing_type=sa.String(length=100),
            nullable=True,
        )


def downgrade():
    with op.batch_alter_table('customers') as batch_op:
        batch_op.alter_column(
            'first_name',
            existing_type=sa.String(length=100),
            nullable=False,
        )
        batch_op.alter_column(
            'last_name',
            existing_type=sa.String(length=100),
            nullable=False,
        )
