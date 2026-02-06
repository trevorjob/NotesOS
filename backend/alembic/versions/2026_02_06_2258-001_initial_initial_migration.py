"""Initial migration - enable pgvector and create all 18 tables

Revision ID: 001
Revises:
Create Date: 2026-02-06

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column(
            "study_personality", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # Courses table
    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("semester", sa.String(length=50), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("invite_code", sa.String(length=20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invite_code"),
    )
    op.create_index(op.f("ix_courses_code"), "courses", ["code"], unique=False)

    # Course enrollments
    op.create_table(
        "course_enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Topics
    op.create_table(
        "topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("week_number", sa.Integer(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Course outlines
    op.create_table(
        "course_outlines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outline_content", sa.Text(), nullable=False),
        sa.Column("file_url", sa.Text(), nullable=True),
        sa.Column("parsed_topics", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Notes
    op.create_table(
        "notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "content_type",
            sa.Enum("TEXT", "PDF", "IMAGE", name="contenttype"),
            nullable=False,
        ),
        sa.Column("file_url", sa.Text(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Note chunks (with pgvector)
    op.create_table(
        "note_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["note_id"],
            ["notes.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Create vector index
    op.execute(
        "CREATE INDEX idx_note_chunks_embedding ON note_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    # Note versions
    op.create_table(
        "note_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("edited_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["edited_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["note_id"],
            ["notes.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Fact checks
    op.create_table(
        "fact_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column(
            "verification_status",
            sa.Enum("VERIFIED", "DISPUTED", "UNVERIFIED", name="verificationstatus"),
            nullable=False,
        ),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence_score", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("ai_explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["note_id"],
            ["notes.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Pre-class research
    op.create_table(
        "pre_class_research",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("research_content", sa.Text(), nullable=False),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "key_concepts", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Tests
    op.create_table(
        "tests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "test_type",
            sa.Enum("PRACTICE", "MOCK", "SELF_TEST", name="testtype"),
            nullable=False,
        ),
        sa.Column("topics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Test questions
    op.create_table(
        "test_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("test_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column(
            "question_type",
            sa.Enum("MCQ", "SHORT_ANSWER", "ESSAY", name="questiontype"),
            nullable=False,
        ),
        sa.Column("correct_answer", sa.Text(), nullable=True),
        sa.Column(
            "answer_options", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["test_id"],
            ["tests.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Test attempts
    op.create_table(
        "test_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("test_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("total_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("max_score", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["test_id"],
            ["tests.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Test answers
    op.create_table(
        "test_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("answer_audio_url", sa.Text(), nullable=True),
        sa.Column("transcription", sa.Text(), nullable=True),
        sa.Column("score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("encouragement", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["test_attempts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["test_questions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Study sessions
    op.create_table(
        "study_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "session_type",
            sa.Enum("READING", "QUIZ", "PRACTICE", name="sessiontype"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "notes_reviewed", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "concepts_covered", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # User progress
    op.create_table(
        "user_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mastery_level", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("total_study_time", sa.Integer(), nullable=False),
        sa.Column("total_attempts", sa.Integer(), nullable=False),
        sa.Column("avg_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("streak_days", sa.Integer(), nullable=False),
        sa.Column("last_activity", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # AI conversations
    op.create_table(
        "ai_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # AI messages
    op.create_table(
        "ai_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role", sa.Enum("USER", "ASSISTANT", name="messagerole"), nullable=False
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["ai_conversations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
    op.drop_table("user_progress")
    op.drop_table("study_sessions")
    op.drop_table("test_answers")
    op.drop_table("test_attempts")
    op.drop_table("test_questions")
    op.drop_table("tests")
    op.drop_table("pre_class_research")
    op.drop_table("fact_checks")
    op.drop_table("note_versions")
    op.drop_table("note_chunks")
    op.drop_table("notes")
    op.drop_table("course_outlines")
    op.drop_table("topics")
    op.drop_table("course_enrollments")
    op.drop_table("courses")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
