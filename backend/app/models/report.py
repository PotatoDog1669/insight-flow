"""报告模型"""

import uuid
from datetime import date, datetime

from sqlalchemy import JSON
from sqlalchemy import Date, DateTime, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class Report(Base):
    """生成的报告（用户级别）"""

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, comment="归属用户")
    time_period: Mapped[str] = mapped_column(String(16), nullable=False, comment="daily / weekly / custom")
    report_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="daily / weekly / research / paper")
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="渲染后的 Markdown / HTML")
    article_ids: Mapped[list] = mapped_column(JSON, default=list, comment="关联文章 ID")
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    published_to: Mapped[list] = mapped_column(JSON, default=list, comment="已落盘到哪些目标")
    publish_trace: Mapped[list] = mapped_column(JSON, default=list, comment="落盘执行轨迹")
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_reports_user_date", "user_id", "report_date"),
        Index("idx_reports_dimensions", "time_period", "report_type"),
    )
