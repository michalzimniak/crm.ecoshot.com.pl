"""Gallery type proof/archive

Revision ID: 5b21c3d9a8f7
Revises: 1389ea9ec41c
Create Date: 2026-01-10

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = '5b21c3d9a8f7'
down_revision = '1389ea9ec41c'
branch_labels = None
depends_on = None


def upgrade():
    # 1) Expand ENUM to allow both old and new values + archive.
    op.execute(
        "ALTER TABLE galleries MODIFY gallery_type "
        "ENUM('proofing','proof','selection','final','archive') "
        "NOT NULL DEFAULT 'proofing'"
    )

    # 2) Migrate existing rows.
    op.execute("UPDATE galleries SET gallery_type='proof' WHERE gallery_type='proofing'")

    # 3) Narrow ENUM to the new set.
    op.execute(
        "ALTER TABLE galleries MODIFY gallery_type "
        "ENUM('proof','selection','final','archive') "
        "NOT NULL DEFAULT 'proof'"
    )


def downgrade():
    # Map archive back to final (best-effort).
    op.execute("UPDATE galleries SET gallery_type='final' WHERE gallery_type='archive'")

    # Allow both proof and proofing temporarily.
    op.execute(
        "ALTER TABLE galleries MODIFY gallery_type "
        "ENUM('proof','proofing','selection','final') "
        "NOT NULL DEFAULT 'proof'"
    )

    op.execute("UPDATE galleries SET gallery_type='proofing' WHERE gallery_type='proof'")

    op.execute(
        "ALTER TABLE galleries MODIFY gallery_type "
        "ENUM('proofing','selection','final') "
        "NOT NULL DEFAULT 'proofing'"
    )
