"""采集任务记录模型"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class CollectTask(Base):
    """采集任务记录（全局级别）"""

    __tablename__ = "collect_tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="scheduled / manual")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", comment="pending|running|success|failed"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    articles_count: Mapped[int] = mapped_column(Integer, default=0, comment="本次采集到的条目数")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
