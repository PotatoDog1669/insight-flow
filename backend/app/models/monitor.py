"""监控任务模型（Monitors）"""

import uuid
from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class Monitor(Base):
    """用户监控任务配置"""

    __tablename__ = "monitors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    time_period: Mapped[str] = mapped_column(String(16), nullable=False, comment="daily / weekly / custom")
    report_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="daily / weekly / research")
    source_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_overrides: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ai_routing: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    destination_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    window_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24, comment="rolling window in hours")
    custom_schedule: Mapped[str | None] = mapped_column(String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
