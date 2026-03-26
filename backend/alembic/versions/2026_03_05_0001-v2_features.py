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
    conn = op.get_bind()

    # --- User: new columns ---
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR(255)"))
    conn.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_id ON users (google_id)"))
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSONB"))
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS personality_tags JSONB"))
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(255)"))
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_expires TIMESTAMP"))

    # Make password_hash nullable for OAuth-only users
    conn.execute(sa.text("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL"))

    # --- SemesterRole enum ---
    conn.execute(sa.text("CREATE TYPE IF NOT EXISTS semesterrole AS ENUM ('OWNER', 'MEMBER')"))

    # --- Semesters table ---
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS semesters (
            id UUID PRIMARY KEY,
            owner_id UUID NOT NULL REFERENCES users(id),
            name VARCHAR(255) NOT NULL,
            start_date DATE,
            end_date DATE,
            invite_code VARCHAR(20) NOT NULL UNIQUE,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_semesters_owner_id ON semesters (owner_id)"))
    conn.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_semesters_invite_code ON semesters (invite_code)"))

    # --- Semester members table ---
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS semester_members (
            id UUID PRIMARY KEY,
            semester_id UUID NOT NULL REFERENCES semesters(id),
            user_id UUID NOT NULL REFERENCES users(id),
            joined_at TIMESTAMP NOT NULL DEFAULT now(),
            role semesterrole NOT NULL,
            CONSTRAINT uq_semester_member UNIQUE (semester_id, user_id)
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_semester_members_semester_id ON semester_members (semester_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_semester_members_user_id ON semester_members (user_id)"))

    # --- Courses: add semester_id FK ---
    conn.execute(sa.text("ALTER TABLE courses ADD COLUMN IF NOT EXISTS semester_id UUID"))
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_courses_semester_id'
            ) THEN
                ALTER TABLE courses ADD CONSTRAINT fk_courses_semester_id
                    FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE SET NULL;
            END IF;
        END $$
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_courses_semester_id ON courses (semester_id)"))

    # --- AnswerStatus enum ---
    conn.execute(sa.text("CREATE TYPE IF NOT EXISTS answerstatus AS ENUM ('CORRECT', 'PARTIAL', 'NEEDS_REVIEW')"))

    # --- TestAnswer: new columns ---
    conn.execute(sa.text("ALTER TABLE test_answers ADD COLUMN IF NOT EXISTS status answerstatus"))
    conn.execute(sa.text("ALTER TABLE test_answers ADD COLUMN IF NOT EXISTS key_points_covered JSONB"))
    conn.execute(sa.text("ALTER TABLE test_answers ADD COLUMN IF NOT EXISTS key_points_missed JSONB"))

    # --- NotificationType enum ---
    conn.execute(sa.text("CREATE TYPE IF NOT EXISTS notificationtype AS ENUM ('TEST_GRADED', 'AI_SUMMARY_READY', 'INVITE_ACCEPTED', 'GENERAL')"))

    # --- Notifications table ---
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS notifications (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id),
            type notificationtype NOT NULL,
            title VARCHAR(255) NOT NULL,
            body TEXT NOT NULL,
            is_read BOOLEAN NOT NULL DEFAULT false,
            meta_data JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id)"))


def downgrade() -> None:
    conn = op.get_bind()

    # --- Notifications ---
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_notifications_user_id"))
    conn.execute(sa.text("DROP TABLE IF EXISTS notifications"))
    conn.execute(sa.text("DROP TYPE IF EXISTS notificationtype"))

    # --- TestAnswer columns ---
    conn.execute(sa.text("ALTER TABLE test_answers DROP COLUMN IF EXISTS key_points_missed"))
    conn.execute(sa.text("ALTER TABLE test_answers DROP COLUMN IF EXISTS key_points_covered"))
    conn.execute(sa.text("ALTER TABLE test_answers DROP COLUMN IF EXISTS status"))
    conn.execute(sa.text("DROP TYPE IF EXISTS answerstatus"))

    # --- Courses: semester_id ---
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_courses_semester_id"))
    conn.execute(sa.text("ALTER TABLE courses DROP CONSTRAINT IF EXISTS fk_courses_semester_id"))
    conn.execute(sa.text("ALTER TABLE courses DROP COLUMN IF EXISTS semester_id"))

    # --- Semester members ---
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_semester_members_user_id"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_semester_members_semester_id"))
    conn.execute(sa.text("DROP TABLE IF EXISTS semester_members"))
    conn.execute(sa.text("DROP TYPE IF EXISTS semesterrole"))

    # --- Semesters ---
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_semesters_invite_code"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_semesters_owner_id"))
    conn.execute(sa.text("DROP TABLE IF EXISTS semesters"))

    # --- User columns ---
    conn.execute(sa.text("ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS password_reset_expires"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS password_reset_token"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS personality_tags"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS preferences"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_users_google_id"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS google_id"))
