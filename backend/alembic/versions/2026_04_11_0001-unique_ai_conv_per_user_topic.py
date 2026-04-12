"""unique ai conversation per user per topic

Revision ID: a1b2c3d4e5f6
Revises: cf4852760187
Create Date: 2026-04-11 00:01:00.000000

Collapses any duplicate (user_id, topic_id) conversations by re-parenting
their messages to the oldest conversation, then drops the duplicates.
Finally adds a partial unique index to enforce the constraint going forward.
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "cf4852760187"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Collapse duplicate conversations — keep the oldest per (user_id, topic_id),
    #    re-parent all messages from newer duplicates, then delete the duplicates.
    op.execute("""
        WITH ranked AS (
            SELECT
                id,
                user_id,
                topic_id,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id, topic_id
                    ORDER BY created_at ASC
                ) AS rn
            FROM ai_conversations
            WHERE topic_id IS NOT NULL
        ),
        keeper AS (
            SELECT id AS keep_id, user_id, topic_id
            FROM ranked WHERE rn = 1
        ),
        duplicate AS (
            SELECT r.id AS dup_id, k.keep_id
            FROM ranked r
            JOIN keeper k ON r.user_id = k.user_id AND r.topic_id = k.topic_id
            WHERE r.rn > 1
        )
        UPDATE ai_messages
        SET conversation_id = d.keep_id
        FROM duplicate d
        WHERE ai_messages.conversation_id = d.dup_id
    """)

    op.execute("""
        DELETE FROM ai_conversations
        WHERE topic_id IS NOT NULL
          AND id NOT IN (
              SELECT DISTINCT ON (user_id, topic_id) id
              FROM ai_conversations
              WHERE topic_id IS NOT NULL
              ORDER BY user_id, topic_id, created_at ASC
          )
    """)

    # 2. Add partial unique index — one conversation per user per topic.
    op.execute("""
        CREATE UNIQUE INDEX uq_ai_conv_user_topic
        ON ai_conversations (user_id, topic_id)
        WHERE topic_id IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_ai_conv_user_topic")
