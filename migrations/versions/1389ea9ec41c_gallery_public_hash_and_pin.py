"""Gallery public hash and PIN

Revision ID: 1389ea9ec41c
Revises: 4014f4131026
Create Date: 2026-01-10 19:49:07.822429

"""
from alembic import op
import sqlalchemy as sa


def _mysql_now():
    # MySQL compatible NOW() default for server-side timestamps when needed.
    return sa.text('CURRENT_TIMESTAMP')


# revision identifiers, used by Alembic.
revision = '1389ea9ec41c'
down_revision = '4014f4131026'
branch_labels = None
depends_on = None


def upgrade():
    # Add public hash + PIN hash fields
    with op.batch_alter_table('galleries') as batch_op:
        batch_op.add_column(sa.Column('public_hash', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('access_pin_hash', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('expiration_days', sa.Integer(), nullable=True))
        batch_op.create_index('ix_galleries_public_hash', ['public_hash'], unique=True)

    # Backfill public_hash for existing galleries (best-effort).
    # We do it in SQL so it works without importing application code.
    # 64 chars hex is fine (>= 32) and URL-safe.
    op.execute(
        "UPDATE galleries SET public_hash = LOWER(REPLACE(UUID(), '-', '')) WHERE public_hash IS NULL"
    )

    # Create PIN attempts table (rate limiting)
    op.create_table(
        'gallery_pin_attempts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('gallery_id', sa.Integer(), sa.ForeignKey('galleries.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('is_success', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('attempted_at', sa.DateTime(), nullable=False, server_default=_mysql_now()),
    )
    op.create_index('ix_gallery_pin_attempts_gallery_time', 'gallery_pin_attempts', ['gallery_id', 'attempted_at'])

    # Create download logs table
    op.create_table(
        'gallery_download_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('gallery_id', sa.Integer(), sa.ForeignKey('galleries.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('downloaded_at', sa.DateTime(), nullable=False, server_default=_mysql_now()),
        sa.Column('bytes_sent', sa.BigInteger(), nullable=True),
    )
    op.create_index('ix_gallery_download_logs_gallery_time', 'gallery_download_logs', ['gallery_id', 'downloaded_at'])


def downgrade():
    op.drop_index('ix_gallery_download_logs_gallery_time', table_name='gallery_download_logs')
    op.drop_table('gallery_download_logs')

    op.drop_index('ix_gallery_pin_attempts_gallery_time', table_name='gallery_pin_attempts')
    op.drop_table('gallery_pin_attempts')

    with op.batch_alter_table('galleries') as batch_op:
        batch_op.drop_index('ix_galleries_public_hash')
        batch_op.drop_column('expiration_days')
        batch_op.drop_column('access_pin_hash')
        batch_op.drop_column('public_hash')
