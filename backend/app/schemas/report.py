"""报告 Schema"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field


class ReportTopic(BaseModel):
    name: str
    weight: int = Field(ge=1)


class ReportResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    time_period: Literal["daily", "weekly", "custom"]
    depth: Literal["brief", "deep"]
    title: str
    tldr: list[str] = Field(default_factory=list)
    article_count: int = 0
    topics: list[ReportTopic] = Field(default_factory=list)
    content: str = ""
    article_ids: list[uuid.UUID] = Field(default_factory=list)
    published_to: list = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    report_type: str = "standard"
    report_date: date
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportFiltersResponse(BaseModel):
    time_periods: list[str]
    depths: list[str]
    categories: list[str]


class ReportCustomRequest(BaseModel):
    title: str
    prompt: str
    time_period: Literal["daily", "weekly", "custom"] = "custom"
    depth: Literal["brief", "deep"] = "deep"
    category: str | None = None
    report_date: date | None = None
