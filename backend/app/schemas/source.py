"""信息源 Schema"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SourceBase(BaseModel):
    name: str = Field(..., max_length=128, description="信息源名称")
    category: str = Field(..., description="类别: open_source / blog / academic / social")
    collect_method: str = Field(..., description="获取方式: api / rss / scraper / deepbrowse")
    config: dict = Field(default_factory=dict, description="采集配置")
    enabled: bool = True


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    enabled: bool | None = None


class SourceResponse(SourceBase):
    id: uuid.UUID
    target_url: str | None = None
    status: Literal["healthy", "error", "running"] = "healthy"
    last_run: datetime | None = Field(default=None, description="最近一次任务运行时间（可为空）")
    last_collected: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CategoryStats(BaseModel):
    category: str
    count: int


class SampleArticle(BaseModel):
    title: str
    url: str | None = None
    published_at: datetime | None = None


class SourceTestRequest(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    max_results: int | None = Field(default=None, ge=1, le=200)
    start_at: datetime | None = None
    end_at: datetime | None = None


class SourceTestResponse(BaseModel):
    success: bool
    message: str | None = None
    fetched_count: int | None = None
    matched_count: int | None = None
    effective_keywords: list[str] = Field(default_factory=list)
    effective_max_results: int | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    sample_articles: list[SampleArticle] = Field(default_factory=list)
