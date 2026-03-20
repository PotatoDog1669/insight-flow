"""用户相关 Schema"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field


class UserMeResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None = None
    plan: str = "Free Plan"
    settings: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class UserSettingsUpdate(BaseModel):
    default_time_period: Literal["daily", "weekly", "custom"] | None = None
    default_report_type: Literal["daily", "weekly", "research", "paper"] | None = None
    default_sink: str | None = None


class UserSettingsResponse(BaseModel):
    default_time_period: Literal["daily", "weekly", "custom"] = "daily"
    default_report_type: Literal["daily", "weekly", "research", "paper"] = "daily"
    default_sink: str = "notion"
