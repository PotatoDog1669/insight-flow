"""监控任务（Monitors）Schema"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field


class MonitorBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    time_period: Literal["daily", "weekly", "custom"]
    depth: Literal["brief", "deep"]
    source_ids: list[uuid.UUID] = Field(default_factory=list)
    custom_schedule: str | None = None
    enabled: bool = True


class MonitorCreate(MonitorBase):
    pass


class MonitorUpdate(BaseModel):
    name: str | None = None
    time_period: Literal["daily", "weekly", "custom"] | None = None
    depth: Literal["brief", "deep"] | None = None
    source_ids: list[uuid.UUID] | None = None
    custom_schedule: str | None = None
    enabled: bool | None = None


class MonitorResponse(MonitorBase):
    id: uuid.UUID
    status: Literal["active", "paused"] = "active"
    last_run: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MonitorRunResponse(BaseModel):
    task_id: uuid.UUID
    status: Literal["pending", "running"]
    monitor_id: uuid.UUID
