"""报告 Schema"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field


class ReportTopic(BaseModel):
    name: str
    weight: int = Field(ge=1)


class ReportFilterMonitorOption(BaseModel):
    id: uuid.UUID
    name: str


class ReportEvent(BaseModel):
    event_id: str
    index: int = Field(ge=1)
    title: str
    event_title: str = ""
    category: str
    one_line_tldr: str = ""
    detail: str = ""
    who: str = ""
    what: str = ""
    when: str = ""
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    availability: str = ""
    unknowns: str = ""
    evidence: str = ""
    source_links: list[str] = Field(default_factory=list)
    source_count: int = Field(default=0, ge=0)
    source_name: str = ""
    published_at: datetime | None = None


class ReportResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    monitor_id: uuid.UUID | None = None
    monitor_name: str = ""
    time_period: Literal["daily", "weekly", "custom"]
    report_type: Literal["daily", "weekly", "research"]
    title: str
    tldr: list[str] = Field(default_factory=list)
    article_count: int = 0
    topics: list[ReportTopic] = Field(default_factory=list)
    events: list[ReportEvent] = Field(default_factory=list)
    global_tldr: str = ""
    content: str = ""
    article_ids: list[uuid.UUID] = Field(default_factory=list)
    published_to: list = Field(default_factory=list)
    publish_trace: list = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    report_date: date
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportFiltersResponse(BaseModel):
    time_periods: list[str]
    report_types: list[str]
    categories: list[str]
    monitors: list[ReportFilterMonitorOption] = Field(default_factory=list)


class ReportCustomRequest(BaseModel):
    title: str
    prompt: str
    time_period: Literal["daily", "weekly", "custom"] = "custom"
    report_type: Literal["daily", "weekly", "research"] = "research"
    category: str | None = None
    report_date: date | None = None
