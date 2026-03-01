"""文章/信息条目模型"""

import uuid
from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy import DateTime, Float, Index, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class Article(Base):
    """采集到的原始文章/信息条目（全局共享，与用户无关）"""

    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="外部唯一标识")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True, comment="原文链接")
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="原始内容")
    summary: Mapped[str | None] = mapped_column(String(256), nullable=True, comment="AI 生成摘要")
    keywords: Mapped[list] = mapped_column(JSON, default=list, comment="关键词数组")
    ai_score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="AI 打分 (0.0~1.0)")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="raw", comment="raw|filtered|processed|published"
    )
    source_type: Mapped[str] = mapped_column(
        String(16), default="unknown", comment="P1 预留: primary / secondary / unknown"
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, comment="扩展字段")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="原文发布时间")
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="idx_articles_external_id"),
        Index("idx_articles_status_time", "status", "collected_at"),
    )
