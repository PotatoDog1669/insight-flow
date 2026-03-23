"""信息源模型"""

import uuid
from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy import Boolean, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class Source(Base):
    """信息源表"""

    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="信息源名称")
    category: Mapped[str] = mapped_column(String(32), nullable=False, comment="类别: open_source / blog / academic / social")
    collect_method: Mapped[str] = mapped_column(String(32), nullable=False, comment="获取方式: api / rss / scraper / deepbrowse")
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="采集配置")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="healthy", server_default="healthy", comment="状态: healthy / error / running")
    last_collected: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
