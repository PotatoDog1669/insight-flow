"""add destination instances

Revision ID: 20260320_0011
Revises: 20260319_0010
Create Date: 2026-03-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260320_0011"
down_revision = "20260319_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "destination_instances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_destination_instances_user_type",
        "destination_instances",
        ["user_id", "type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_destination_instances_user_type", table_name="destination_instances")
    op.drop_table("destination_instances")
