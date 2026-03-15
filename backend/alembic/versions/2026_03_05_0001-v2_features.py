"""v2 features

Revision ID: v2_features_001
Revises: c9528675791b
Create Date: 2026-03-05 00:00:01.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "v2_features_001"
down_revision: Union[str, None] = "c9528675791b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- User: new columns ---
    op.add_column("users", sa.Column("google_id", sa.String(255), nullable=True))
    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)

    op.add_column(
        "users",
        sa.Column(
            "preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "personality_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "users", sa.Column("password_reset_token", sa.String(255), nullable=True)
    )
    op.add_column(
        "users", sa.Column("password_reset_expires", sa.DateTime(), nullable=True)
    )

    # Make password_hash nullable for OAuth-only users
    op.alter_column("users", "password_hash", nullable=True)

    # --- Semesters table ---
    op.create_table(
        "semesters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("invite_code", sa.String(20), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
    )
    op.create_index("ix_semesters_owner_id", "semesters", ["owner_id"], unique=False)
    op.create_index(
        "ix_semesters_invite_code", "semesters", ["invite_code"], unique=True
    )

    # --- SemesterRole enum ---
    semester_role_enum = postgresql.ENUM(
        "OWNER", "MEMBER", name="semesterrole", create_type=True
    )
    semester_role_enum.create(op.get_bind(), checkfirst=True)

    # --- Semester members table ---
    op.create_table(
        "semester_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "semester_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("semesters.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "joined_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "role", sa.Enum("OWNER", "MEMBER", name="semesterrole"), nullable=False
        ),
        sa.UniqueConstraint("semester_id", "user_id", name="uq_semester_member"),
    )
    op.create_index(
        "ix_semester_members_semester_id",
        "semester_members",
        ["semester_id"],
        unique=False,
    )
    op.create_index(
        "ix_semester_members_user_id", "semester_members", ["user_id"], unique=False
    )

    # --- Courses: add semester_id FK ---
    op.add_column(
        "courses",
        sa.Column("semester_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_courses_semester_id",
        "courses",
        "semesters",
        ["semester_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_courses_semester_id", "courses", ["semester_id"], unique=False)

    # --- TestAnswer: new columns ---
    answer_status_enum = postgresql.ENUM(
        "CORRECT", "PARTIAL", "NEEDS_REVIEW", name="answerstatus", create_type=True
    )
    answer_status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "test_answers",
        sa.Column(
            "status",
            sa.Enum("CORRECT", "PARTIAL", "NEEDS_REVIEW", name="answerstatus"),
            nullable=True,
        ),
    )
    op.add_column(
        "test_answers",
        sa.Column(
            "key_points_covered", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "test_answers",
        sa.Column(
            "key_points_missed", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )

    # --- Notifications table ---
    notification_type_enum = postgresql.ENUM(
        "TEST_GRADED",
        "AI_SUMMARY_READY",
        "INVITE_ACCEPTED",
        "GENERAL",
        name="notificationtype",
        create_type=True,
    )
    notification_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "type",
            sa.Enum(
                "TEST_GRADED",
                "AI_SUMMARY_READY",
                "INVITE_ACCEPTED",
                "GENERAL",
                name="notificationtype",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("meta_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
    )
    op.create_index(
        "ix_notifications_user_id", "notifications", ["user_id"], unique=False
    )


def downgrade() -> None:
    # --- Notifications ---
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
    op.execute("DROP TYPE IF EXISTS notificationtype")

    # --- TestAnswer columns ---
    op.drop_column("test_answers", "key_points_missed")
    op.drop_column("test_answers", "key_points_covered")
    op.drop_column("test_answers", "status")
    op.execute("DROP TYPE IF EXISTS answerstatus")

    # --- Courses: semester_id ---
    op.drop_index("ix_courses_semester_id", table_name="courses")
    op.drop_constraint("fk_courses_semester_id", "courses", type_="foreignkey")
    op.drop_column("courses", "semester_id")

    # --- Semester members ---
    op.drop_index("ix_semester_members_user_id", table_name="semester_members")
    op.drop_index("ix_semester_members_semester_id", table_name="semester_members")
    op.drop_table("semester_members")
    op.execute("DROP TYPE IF EXISTS semesterrole")

    # --- Semesters ---
    op.drop_index("ix_semesters_invite_code", table_name="semesters")
    op.drop_index("ix_semesters_owner_id", table_name="semesters")
    op.drop_table("semesters")

    # --- User columns ---
    op.alter_column("users", "password_hash", nullable=False)
    op.drop_column("users", "password_reset_expires")
    op.drop_column("users", "password_reset_token")
    op.drop_column("users", "personality_tags")
    op.drop_column("users", "preferences")
    op.drop_index("ix_users_google_id", table_name="users")
    op.drop_column("users", "google_id")
