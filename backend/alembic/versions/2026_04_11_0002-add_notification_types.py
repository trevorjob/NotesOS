"""add RESOURCE_UPLOADED and CLASSMATE_JOINED notification types

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-11 00:02:00.000000
"""

from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'RESOURCE_UPLOADED'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'CLASSMATE_JOINED'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values — downgrade is a no-op.
    pass
