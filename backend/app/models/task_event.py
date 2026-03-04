"""任务事件日志模型（append-only）"""

import uuid
from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class TaskEvent(Base):
    """任务事件日志，按时间追加写入。"""

    __tablename__ = "task_events"
    __table_args__ = (
        Index("ix_task_events_monitor_created_at", "monitor_id", "created_at"),
        Index("ix_task_events_run_created_at", "run_id", "created_at"),
        Index("ix_task_events_task_created_at", "task_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, comment="同一次 monitor run 的聚合 id")
    monitor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("collect_tasks.id", ondelete="CASCADE"), nullable=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    stage: Mapped[str] = mapped_column(String(48), nullable=False, comment="collect/process/publish/...")
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="info", comment="debug/info/warning/error")
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="阶段内事件类型")
    message: Mapped[str] = mapped_column(Text, nullable=False, comment="人类可读日志信息")
    payload: Mapped[dict] = mapped_column(JSON, default=dict, comment="结构化补充信息")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
