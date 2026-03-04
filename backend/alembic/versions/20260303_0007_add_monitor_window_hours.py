"""add window_hours to monitors

Revision ID: 20260303_0007
Revises: 20260303_0006
Create Date: 2026-03-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260303_0007"
down_revision = "20260303_0006"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "monitors", "window_hours"):
        op.add_column(
            "monitors",
            sa.Column("window_hours", sa.Integer(), nullable=False, server_default=sa.text("24")),
        )
    else:
        op.execute(sa.text("UPDATE monitors SET window_hours = 24 WHERE window_hours IS NULL"))
    op.alter_column("monitors", "window_hours", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_column(inspector, "monitors", "window_hours"):
        op.drop_column("monitors", "window_hours")
