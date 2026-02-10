"""note_to_resource_refactor

Revision ID: 005_note_to_resource
Revises: 3a78a54f8912
Create Date: 2026-02-10 11:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "005_note_to_resource"
down_revision: Union[str, None] = "3a78a54f8912"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Create resourcetype enum ──
    op.execute("""
        DO $$
        BEGIN
            CREATE TYPE resourcetype AS ENUM ('text', 'pdf', 'docx', 'image');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # ── 2. Rename tables ──
    op.rename_table("notes", "resources")
    op.rename_table("note_chunks", "resource_chunks")
    op.rename_table("note_files", "resource_files")

    # ── 3. Rename FK columns ──
    # resource_chunks: note_id → resource_id
    op.alter_column("resource_chunks", "note_id", new_column_name="resource_id")

    # resource_files: note_id → resource_id
    op.alter_column("resource_files", "note_id", new_column_name="resource_id")

    # fact_checks: note_id → resource_id
    op.alter_column("fact_checks", "note_id", new_column_name="resource_id")

    # ── 4. Add resource_type column and migrate data from content_type ──
    op.add_column(
        "resources",
        sa.Column(
            "resource_type",
            sa.Enum("text", "pdf", "docx", "image", name="resourcetype"),
            nullable=True,
        ),
    )

    # Map content_type values to resource_type
    op.execute("""
        UPDATE resources SET resource_type = 
            CASE content_type::text
                WHEN 'text' THEN 'text'::resourcetype
                WHEN 'TEXT' THEN 'text'::resourcetype
                WHEN 'pdf' THEN 'pdf'::resourcetype
                WHEN 'PDF' THEN 'pdf'::resourcetype
                WHEN 'docx' THEN 'docx'::resourcetype
                WHEN 'DOCX' THEN 'docx'::resourcetype
                WHEN 'image' THEN 'image'::resourcetype
                WHEN 'IMAGE' THEN 'image'::resourcetype
                WHEN 'file' THEN 'pdf'::resourcetype
                WHEN 'FILE' THEN 'pdf'::resourcetype
                ELSE 'text'::resourcetype
            END
    """)

    # Set NOT NULL and default
    op.alter_column("resources", "resource_type", nullable=False, server_default="text")

    # Drop content_type column
    op.drop_column("resources", "content_type")

    # ── 5. Add file_name column to resources ──
    op.add_column(
        "resources",
        sa.Column("file_name", sa.String(255), nullable=True),
    )

    # ── 6. Drop note_versions table (unused) ──
    op.drop_table("note_versions")

    # ── 7. Rename FK constraints (update index names for clarity) ──
    # The foreign key constraints will still work with renamed tables,
    # but we clean up index names where possible
    # This is optional - PostgreSQL handles renamed tables transparently

    # ── 8. Rename sourcetype enum values if needed ──
    # sourcetype enum already has correct values (text, pdf, docx, handwritten, printed)
    # No changes needed


def downgrade() -> None:
    # ── Reverse: recreate note_versions ──
    op.create_table(
        "note_versions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("note_id", sa.UUID(), sa.ForeignKey("resources.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("edited_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # Drop file_name column
    op.drop_column("resources", "file_name")

    # Add content_type back, migrate from resource_type
    op.add_column(
        "resources",
        sa.Column(
            "content_type",
            sa.Enum("text", "pdf", "docx", "image", "file", name="contenttype"),
            nullable=True,
        ),
    )
    op.execute("""
        UPDATE resources SET content_type = resource_type::text::contenttype
    """)
    op.alter_column("resources", "content_type", nullable=False, server_default="text")
    op.drop_column("resources", "resource_type")

    # Rename FK columns back
    op.alter_column("fact_checks", "resource_id", new_column_name="note_id")
    op.alter_column("resource_files", "resource_id", new_column_name="note_id")
    op.alter_column("resource_chunks", "resource_id", new_column_name="note_id")

    # Rename tables back
    op.rename_table("resource_files", "note_files")
    op.rename_table("resource_chunks", "note_chunks")
    op.rename_table("resources", "notes")

    # Drop resourcetype enum
    op.execute("DROP TYPE IF EXISTS resourcetype")
