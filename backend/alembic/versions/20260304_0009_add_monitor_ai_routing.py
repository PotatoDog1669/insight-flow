"""add ai_routing to monitors

Revision ID: 20260304_0009
Revises: 20260303_0008
Create Date: 2026-03-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260304_0009"
down_revision = "20260303_0008"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_column(inspector, "monitors", "ai_routing"):
        op.add_column(
            "monitors",
            sa.Column("ai_routing", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        )
    else:
        op.execute(sa.text("UPDATE monitors SET ai_routing = '{}' WHERE ai_routing IS NULL"))
    op.alter_column("monitors", "ai_routing", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_column(inspector, "monitors", "ai_routing"):
        op.drop_column("monitors", "ai_routing")
