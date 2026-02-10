"""add_file_to_contenttype_enum

Revision ID: c54ab29c2dea
Revises: 004_ux_enhancements
Create Date: 2026-02-09 23:09:23.968870

"""

from typing import Sequence, Union

from alembic import op
# import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c54ab29c2dea"
down_revision: Union[str, None] = "004_ux_enhancements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'file' to the contenttype enum
    op.execute("ALTER TYPE contenttype ADD VALUE 'FILE'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type, which is complex
    # For now, we'll leave this as a no-op
    pass
