"""文章 Schema"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ArticleResponse(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_name: str | None = None
    category: str | None = None
    title: str
    url: str | None = None
    summary: str | None = None
    keywords: list[str] = Field(default_factory=list)
    ai_score: float | None = None
    status: str
    source_type: str = "unknown"
    report_ids: list[uuid.UUID] = Field(default_factory=list)
    published_at: datetime | None = None
    collected_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class ArticleListParams(BaseModel):
    category: str | None = None
    source_id: uuid.UUID | None = None
    date: str | None = None
    min_score: float | None = None
    keyword: str | None = None
    status: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
