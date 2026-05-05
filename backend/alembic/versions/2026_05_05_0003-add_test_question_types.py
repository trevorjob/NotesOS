"""add question_types column to tests

Revision ID: g3h4i5j6k7l8
Revises: f2a3b4c5d6e7
Create Date: 2026-05-05 00:03:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'g3h4i5j6k7l8'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tests', sa.Column('question_types', JSONB, nullable=True))
    # Backfill existing tests with the default mixed type
    op.execute("UPDATE tests SET question_types = '[\"mcq\", \"short_answer\"]'::jsonb WHERE question_types IS NULL")


def downgrade() -> None:
    op.drop_column('tests', 'question_types')
