"""
004_ux_enhancements - Add UX enhancement models

Revision ID: 004_ux_enhancements
Revises: 003_add_hybrid_ocr
Create Date: 2026-02-09

This migration adds:
1. classes table (global invites)
2. classmates table (users who joined via global invite)
3. note_files table (multi-file uploads)
4. Makes notes.title nullable
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "004_ux_enhancements"
down_revision: Union[str, None] = "003_add_hybrid_ocr"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add UX enhancement tables and columns."""

    # 1. Create classes table (global invites)
    op.create_table(
        "classes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("invite_code", sa.String(20), unique=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_classes_owner_id", "classes", ["owner_id"])
    op.create_index("ix_classes_invite_code", "classes", ["invite_code"])

    # 2. Create classmates table
    op.create_table(
        "classmates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id"), nullable=False
        ),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_classmates_class_id", "classmates", ["class_id"])
    op.create_index("ix_classmates_user_id", "classmates", ["user_id"])

    # 3. Create note_files table (multi-file uploads)
    op.create_table(
        "note_files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "note_id", UUID(as_uuid=True), sa.ForeignKey("notes.id"), nullable=False
        ),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("file_order", sa.Integer(), default=0, nullable=False),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("ocr_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("ocr_provider", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_note_files_note_id", "note_files", ["note_id"])

    # 4. Make notes.title nullable
    op.alter_column(
        "notes",
        "title",
        existing_type=sa.String(255),
        nullable=True,
    )


def downgrade() -> None:
    """Remove UX enhancement tables and columns."""

    # 1. Make notes.title non-nullable again
    op.alter_column(
        "notes",
        "title",
        existing_type=sa.String(255),
        nullable=False,
    )

    # 2. Drop note_files table
    op.drop_index("ix_note_files_note_id", table_name="note_files")
    op.drop_table("note_files")

    # 3. Drop classmates table
    op.drop_index("ix_classmates_user_id", table_name="classmates")
    op.drop_index("ix_classmates_class_id", table_name="classmates")
    op.drop_table("classmates")

    # 4. Drop classes table
    op.drop_index("ix_classes_invite_code", table_name="classes")
    op.drop_index("ix_classes_owner_id", table_name="classes")
    op.drop_table("classes")
