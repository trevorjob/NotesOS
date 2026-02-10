"""fix_enum_case_add_uppercase_FILE_retry

Revision ID: 3a78a54f8912
Revises: c54ab29c2dea
Create Date: 2026-02-09 23:36:33.676854

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3a78a54f8912"
down_revision: Union[str, None] = "c54ab29c2dea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'FILE' (uppercase) to the contenttype enum
    # We use a transaction to ensure atomicity
    # Note: IF NOT EXISTS is not supported for adding enum values in older Postgres versions,
    # but we can wrap it in a try-catch block in PL/pgSQL or just run it.
    # Since this is a migration, we expect it to succeed if 'FILE' is missing.
    # If users already added it manually, it will fail, which is fine (idempotency via failure).
    # But to be nicer, we can use a DO block.
    op.execute("""
        DO $$
        BEGIN
            ALTER TYPE contenttype ADD VALUE 'FILE';
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)


def downgrade() -> None:
    pass
