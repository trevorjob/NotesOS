"""update_enum_values_to_uppercase

Revision ID: 012ca46d48b7
Revises: 2b99b0e8c40f
Create Date: 2026-02-10 13:25:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "012ca46d48b7"
down_revision: Union[str, None] = "2b99b0e8c40f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Now that uppercase values are committed, update existing data
    # Update resources.resource_type
    op.execute("""
        UPDATE resources 
        SET resource_type = UPPER(resource_type::text)::resourcetype;
    """)

    # Update resources.source_type
    op.execute("""
        UPDATE resources 
        SET source_type = UPPER(source_type::text)::sourcetype;
    """)


def downgrade() -> None:
    # Revert to lowercase values
    op.execute("""
        UPDATE resources 
        SET resource_type = LOWER(resource_type::text)::resourcetype
        WHERE resource_type::text IN ('TEXT', 'PDF', 'DOCX', 'IMAGE');
    """)

    op.execute("""
        UPDATE resources 
        SET source_type = LOWER(source_type::text)::sourcetype
        WHERE source_type::text IN ('TEXT', 'PDF', 'DOCX', 'HANDWRITTEN', 'PRINTED');
    """)
