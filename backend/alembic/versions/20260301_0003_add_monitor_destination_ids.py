"""add destination_ids to monitors

Revision ID: 20260301_0003
Revises: 20260301_0002
Create Date: 2026-03-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260301_0003"
down_revision = "20260301_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("monitors", sa.Column("destination_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade() -> None:
    op.drop_column("monitors", "destination_ids")
