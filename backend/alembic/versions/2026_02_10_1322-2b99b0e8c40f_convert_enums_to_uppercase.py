"""add_uppercase_enum_values

Revision ID: 2b99b0e8c40f
Revises: 005_note_to_resource
Create Date: 2026-02-10 13:22:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2b99b0e8c40f"
down_revision: Union[str, None] = "005_note_to_resource"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Step 1: Add uppercase values to resourcetype enum ──
    # Each ALTER TYPE must be a separate statement for PostgreSQL
    op.execute("ALTER TYPE resourcetype ADD VALUE IF NOT EXISTS 'TEXT'")
    op.execute("ALTER TYPE resourcetype ADD VALUE IF NOT EXISTS 'PDF'")
    op.execute("ALTER TYPE resourcetype ADD VALUE IF NOT EXISTS 'DOCX'")
    op.execute("ALTER TYPE resourcetype ADD VALUE IF NOT EXISTS 'IMAGE'")

    # ── Step 2: Add uppercase values to sourcetype enum ──
    op.execute("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'TEXT'")
    op.execute("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'PDF'")
    op.execute("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'DOCX'")
    op.execute("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'HANDWRITTEN'")
    op.execute("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'PRINTED'")


def downgrade() -> None:
    # Cannot remove enum values in PostgreSQL without recreating the type
    pass
