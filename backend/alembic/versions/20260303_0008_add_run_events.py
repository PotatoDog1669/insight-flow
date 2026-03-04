"""add run_id to collect_tasks and create task_events

Revision ID: 20260303_0008
Revises: 20260303_0007
Create Date: 2026-03-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260303_0008"
down_revision = "20260303_0007"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "collect_tasks") and not _has_column(inspector, "collect_tasks", "run_id"):
        op.add_column("collect_tasks", sa.Column("run_id", sa.Uuid(), nullable=True))
        op.execute(sa.text("UPDATE collect_tasks SET run_id = id WHERE run_id IS NULL"))
        op.create_index("ix_collect_tasks_run_id", "collect_tasks", ["run_id"], unique=False)
        inspector = sa.inspect(bind)

    if not _has_table(inspector, "task_events"):
        op.create_table(
            "task_events",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("run_id", sa.Uuid(), nullable=False),
            sa.Column("monitor_id", sa.Uuid(), nullable=True),
            sa.Column("task_id", sa.Uuid(), nullable=True),
            sa.Column("source_id", sa.Uuid(), nullable=True),
            sa.Column("stage", sa.String(length=48), nullable=False),
            sa.Column("level", sa.String(length=16), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["monitor_id"], ["monitors.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["task_id"], ["collect_tasks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_task_events_monitor_created_at", "task_events", ["monitor_id", "created_at"], unique=False)
        op.create_index("ix_task_events_run_created_at", "task_events", ["run_id", "created_at"], unique=False)
        op.create_index("ix_task_events_task_created_at", "task_events", ["task_id", "created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "task_events"):
        op.drop_index("ix_task_events_task_created_at", table_name="task_events")
        op.drop_index("ix_task_events_run_created_at", table_name="task_events")
        op.drop_index("ix_task_events_monitor_created_at", table_name="task_events")
        op.drop_table("task_events")
        inspector = sa.inspect(bind)

    if _has_table(inspector, "collect_tasks") and _has_column(inspector, "collect_tasks", "run_id"):
        op.drop_index("ix_collect_tasks_run_id", table_name="collect_tasks")
        op.drop_column("collect_tasks", "run_id")
