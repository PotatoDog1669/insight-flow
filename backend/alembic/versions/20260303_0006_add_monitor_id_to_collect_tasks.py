"""add monitor_id to collect_tasks

Revision ID: 20260303_0006
Revises: 20260302_0005
Create Date: 2026-03-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260303_0006"
down_revision = "20260302_0005"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _monitor_id_foreign_keys(inspector: sa.Inspector) -> list[dict]:
    fks: list[dict] = []
    for fk in inspector.get_foreign_keys("collect_tasks"):
        constrained_columns = fk.get("constrained_columns") or []
        if "monitor_id" in constrained_columns and fk.get("referred_table") == "monitors":
            fks.append(fk)
    return fks


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "collect_tasks", "monitor_id"):
        op.add_column("collect_tasks", sa.Column("monitor_id", sa.Uuid(), nullable=True))
        inspector = sa.inspect(bind)

    if not _monitor_id_foreign_keys(inspector):
        op.create_foreign_key(
            "fk_collect_tasks_monitor_id_monitors",
            "collect_tasks",
            "monitors",
            ["monitor_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for fk in _monitor_id_foreign_keys(inspector):
        name = fk.get("name")
        if name:
            op.drop_constraint(name, "collect_tasks", type_="foreignkey")

    if _has_column(inspector, "collect_tasks", "monitor_id"):
        op.drop_column("collect_tasks", "monitor_id")
