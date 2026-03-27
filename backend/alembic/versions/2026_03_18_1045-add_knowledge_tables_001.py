"""add knowledge tables

Revision ID: add_knowledge_tables_001
Revises: cefbe12b1a0a
Create Date: 2026-03-18 10:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "add_knowledge_tables_001"
down_revision: Union[str, None] = "cefbe12b1a0a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- KnowledgeStatus enum ---
    knowledge_status_enum = postgresql.ENUM(
        "pending", "processing", "completed", "failed",
        name="knowledgestatus",
        create_type=True,
    )
    knowledge_status_enum.create(op.get_bind(), checkfirst=True)

    # --- topic_knowledge table (one per topic) ---
    op.create_table(
        "topic_knowledge",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("consolidated_note", sa.Text(), nullable=True),
        sa.Column(
            "key_points",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "concepts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "completed", "failed", name="knowledgestatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("topic_id", name="uq_topic_knowledge_topic_id"),
    )
    op.create_index("ix_topic_knowledge_topic_id", "topic_knowledge", ["topic_id"], unique=True)

    # --- audio_lessons table ---
    op.create_table(
        "audio_lessons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "knowledge_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("topic_knowledge.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("script", sa.Text(), nullable=True),
        sa.Column("audio_url", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("voice", sa.String(50), nullable=False, server_default="nova"),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "completed", "failed", name="knowledgestatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_audio_lessons_topic_id", "audio_lessons", ["topic_id"], unique=False)
    op.create_index("ix_audio_lessons_knowledge_id", "audio_lessons", ["knowledge_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audio_lessons_knowledge_id", table_name="audio_lessons")
    op.drop_index("ix_audio_lessons_topic_id", table_name="audio_lessons")
    op.drop_table("audio_lessons")

    op.drop_index("ix_topic_knowledge_topic_id", table_name="topic_knowledge")
    op.drop_table("topic_knowledge")

    op.execute("DROP TYPE IF EXISTS knowledgestatus")
