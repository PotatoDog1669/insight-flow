"""add trace fields for routing and publish

Revision ID: 20260301_0002
Revises: 20260301_0001
Create Date: 2026-03-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260301_0002"
down_revision = "20260301_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("collect_tasks", sa.Column("stage_trace", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.alter_column("collect_tasks", "status", existing_type=sa.String(length=16), type_=sa.String(length=32))

    op.add_column("reports", sa.Column("publish_trace", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("articles", sa.Column("processing_trace", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade() -> None:
    op.drop_column("articles", "processing_trace")
    op.drop_column("reports", "publish_trace")
    op.alter_column("collect_tasks", "status", existing_type=sa.String(length=32), type_=sa.String(length=16))
    op.drop_column("collect_tasks", "stage_trace")
