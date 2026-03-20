"""Academic paper-centric models."""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class Paper(Base):
    """Globally deduplicated academic paper."""

    __tablename__ = "papers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(512), nullable=False, comment="规范化标题，用于弱去重")
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    venue: Mapped[str | None] = mapped_column(String(256), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_author: Mapped[str | None] = mapped_column(String(256), nullable=True)
    best_landing_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    best_pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    fulltext_status: Mapped[str] = mapped_column(String(16), nullable=False, default="missing")
    best_content_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("idx_papers_normalized_title", "normalized_title"),)


class PaperIdentifier(Base):
    """External identifiers for canonical papers."""

    __tablename__ = "paper_identifiers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("papers.id"), nullable=False, index=True)
    scheme: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(512), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("scheme", "normalized_value", name="idx_paper_identifiers_scheme_value"),)


class PaperAsset(Base):
    """Downloaded raw assets for papers."""

    __tablename__ = "paper_assets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("papers.id"), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fetch_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_paper_assets_checksum", "checksum"),
        UniqueConstraint("paper_id", "checksum", name="idx_paper_assets_paper_checksum"),
    )


class PaperContent(Base):
    """Normalized extracted content for analysis."""

    __tablename__ = "paper_contents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("papers.id"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("paper_assets.id"), nullable=True, index=True)
    content_tier: Mapped[str] = mapped_column(String(16), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False, default="markdown")
    markdown_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    plain_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sections_json: Mapped[list] = mapped_column(JSON, default=list)
    converter_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
