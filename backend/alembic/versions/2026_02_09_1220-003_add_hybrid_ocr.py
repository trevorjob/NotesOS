"""Add hybrid OCR columns

Revision ID: 003_add_hybrid_ocr
Revises: 002_add_ocr_metadata
Create Date: 2026-02-09

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003_add_hybrid_ocr"
down_revision: Union[str, None] = "002_add_ocr_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add ocr_confidence column (0.000 - 1.000 confidence score)
    op.add_column("notes", sa.Column("ocr_confidence", sa.Numeric(4, 3), nullable=True))

    # Add ocr_provider column ('tesseract' or 'google_vision')
    op.add_column("notes", sa.Column("ocr_provider", sa.String(50), nullable=True))

    # Add index on ocr_provider for filtering
    op.create_index("idx_notes_ocr_provider", "notes", ["ocr_provider"])


def downgrade() -> None:
    # Drop index
    op.drop_index("idx_notes_ocr_provider", table_name="notes")

    # Drop columns
    op.drop_column("notes", "ocr_provider")
    op.drop_column("notes", "ocr_confidence")
