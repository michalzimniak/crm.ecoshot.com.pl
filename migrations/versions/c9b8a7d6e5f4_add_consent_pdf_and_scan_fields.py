"""add consent pdf and scan fields

Revision ID: c9b8a7d6e5f4
Revises: e2c3a8f0d1aa
Create Date: 2026-01-06

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c9b8a7d6e5f4"
down_revision = "e2c3a8f0d1aa"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("consents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pdf_path", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("signed_scan_path", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("signed_scan_original_filename", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("signed_scan_mime_type", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("signed_scan_size", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("signed_scan_uploaded_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("consents", schema=None) as batch_op:
        batch_op.drop_column("signed_scan_uploaded_at")
        batch_op.drop_column("signed_scan_size")
        batch_op.drop_column("signed_scan_mime_type")
        batch_op.drop_column("signed_scan_original_filename")
        batch_op.drop_column("signed_scan_path")
        batch_op.drop_column("pdf_path")
