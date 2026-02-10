"""Add OCR metadata and update embeddings

Revision ID: 002_add_ocr_metadata
Revises: 001_initial
Create Date: 2026-02-08

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "002_add_ocr_metadata"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create new SourceType enum
    source_type_enum = postgresql.ENUM(
        "text",
        "pdf",
        "docx",
        "handwritten",
        "printed",
        name="sourcetype",
        create_type=False,
    )
    source_type_enum.create(op.get_bind(), checkfirst=True)

    # Update ContentType enum to include docx
    op.execute("ALTER TYPE contenttype ADD VALUE IF NOT EXISTS 'docx'")

    # Add new columns to notes table
    op.add_column(
        "notes",
        sa.Column(
            "source_type", source_type_enum, nullable=False, server_default="text"
        ),
    )
    op.add_column(
        "notes",
        sa.Column("is_processed", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "notes",
        sa.Column("ocr_cleaned", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("notes", sa.Column("original_ocr_text", sa.Text(), nullable=True))

    # Update note_chunks embedding dimension from 1024 to 1536
    # This requires dropping and recreating the column (PostgreSQL doesn't allow ALTER TYPE for vector dimensions)
    op.execute("ALTER TABLE note_chunks DROP COLUMN IF EXISTS embedding")
    op.add_column("note_chunks", sa.Column("embedding", Vector(1536), nullable=True))

    # Drop old index if exists and create new one for 1536-dim embeddings
    op.execute("DROP INDEX IF EXISTS idx_note_chunks_embedding")
    op.execute("""
        CREATE INDEX idx_note_chunks_embedding ON note_chunks 
        USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
    """)

    # Add index on notes.topic_id for faster note listing
    op.create_index("idx_notes_topic_id", "notes", ["topic_id"])

    # Add index on notes.is_processed for filtering unprocessed notes
    op.create_index("idx_notes_is_processed", "notes", ["is_processed"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_notes_is_processed", table_name="notes")
    op.drop_index("idx_notes_topic_id", table_name="notes")
    op.execute("DROP INDEX IF EXISTS idx_note_chunks_embedding")

    # Revert note_chunks embedding back to 1024 dimensions
    op.execute("ALTER TABLE note_chunks DROP COLUMN IF EXISTS embedding")
    op.add_column("note_chunks", sa.Column("embedding", Vector(1024), nullable=True))

    # Recreate old index
    op.execute("""
        CREATE INDEX idx_note_chunks_embedding ON note_chunks 
        USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
    """)

    # Remove columns from notes
    op.drop_column("notes", "original_ocr_text")
    op.drop_column("notes", "ocr_cleaned")
    op.drop_column("notes", "is_processed")
    op.drop_column("notes", "source_type")

    # Drop SourceType enum
    source_type_enum = postgresql.ENUM(name="sourcetype", create_type=False)
    source_type_enum.drop(op.get_bind(), checkfirst=True)
