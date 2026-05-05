"""add test generation status fields

Revision ID: e1f2a3b4c5d6
Revises: d40050c7c93a
Create Date: 2026-05-05 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd40050c7c93a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE testgenerationstatus AS ENUM ('pending', 'generating', 'ready', 'failed')")

    op.add_column('tests', sa.Column(
        'generation_status',
        sa.Enum('pending', 'generating', 'ready', 'failed', name='testgenerationstatus'),
        nullable=True,
    ))
    op.add_column('tests', sa.Column('batches_total', sa.Integer(), nullable=True))
    op.add_column('tests', sa.Column('batches_done', sa.Integer(), nullable=True))
    op.add_column('tests', sa.Column('started_at', sa.DateTime(), nullable=True))
    op.add_column('tests', sa.Column('failure_reason', sa.Text(), nullable=True))

    # Backfill: all existing tests are already fully generated
    op.execute("UPDATE tests SET generation_status = 'ready', batches_done = 0 WHERE generation_status IS NULL")

    op.alter_column('tests', 'generation_status', nullable=False)
    op.alter_column('tests', 'batches_done', nullable=False, server_default='0')


def downgrade() -> None:
    op.drop_column('tests', 'failure_reason')
    op.drop_column('tests', 'started_at')
    op.drop_column('tests', 'batches_done')
    op.drop_column('tests', 'batches_total')
    op.drop_column('tests', 'generation_status')
    op.execute("DROP TYPE testgenerationstatus")
