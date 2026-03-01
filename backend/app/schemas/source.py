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
    status: Literal["healthy", "error", "running"] = "healthy"
    last_run: datetime | None = Field(default=None, description="最近一次任务运行时间（可为空）")
    last_collected: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CategoryStats(BaseModel):
    category: str
    count: int
