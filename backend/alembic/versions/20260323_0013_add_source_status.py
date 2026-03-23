"""add status to source

Revision ID: 20260323_0013
Revises: 20260320_0012
Create Date: 2026-03-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260323_0013"
down_revision = "20260320_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'healthy'")),
    )


def downgrade() -> None:
    op.drop_column("sources", "status")
