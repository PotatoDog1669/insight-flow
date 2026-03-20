"""add destination instance refs to monitors and reports

Revision ID: 20260320_0012
Revises: 20260320_0011
Create Date: 2026-03-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260320_0012"
down_revision = "20260320_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "monitors",
        sa.Column("destination_instance_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "reports",
        sa.Column("published_destination_instance_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("reports", "published_destination_instance_ids")
    op.drop_column("monitors", "destination_instance_ids")
