"""add contract signed scan fields

Revision ID: b7a1e9f4c2ab
Revises: 3fb0510f5764
Create Date: 2026-01-06

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7a1e9f4c2ab'
down_revision = '3fb0510f5764'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('contracts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('signed_scan_path', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('signed_scan_original_filename', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('signed_scan_mime_type', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('signed_scan_size', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('signed_scan_uploaded_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('contracts', schema=None) as batch_op:
        batch_op.drop_column('signed_scan_uploaded_at')
        batch_op.drop_column('signed_scan_size')
        batch_op.drop_column('signed_scan_mime_type')
        batch_op.drop_column('signed_scan_original_filename')
        batch_op.drop_column('signed_scan_path')
