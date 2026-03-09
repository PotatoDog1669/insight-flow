"""监控任务（Monitors）Schema"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator


ProviderName = Literal["rule", "llm_openai", "agent_codex"]
ReportProviderName = Literal["llm_openai", "agent_codex"]


class MonitorStageRoute(BaseModel):
    primary: ProviderName


class MonitorReportStageRoute(BaseModel):
    primary: ReportProviderName


class MonitorAIRoutingStages(BaseModel):
    filter: MonitorStageRoute | None = None
    keywords: MonitorStageRoute | None = None
    global_summary: MonitorReportStageRoute | None = None
    report: MonitorReportStageRoute | None = None


class MonitorAIProviderConfig(BaseModel):
    model: str | None = None
    timeout_sec: int | None = Field(default=None, ge=1, le=600)
    max_retry: int | None = Field(default=None, ge=0, le=10)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        model = value.strip()
        if not model:
            raise ValueError("model must not be empty")
        return model


class MonitorAIRouting(BaseModel):
    stages: MonitorAIRoutingStages = Field(default_factory=MonitorAIRoutingStages)
    providers: dict[ProviderName, MonitorAIProviderConfig] = Field(default_factory=dict)


class MonitorAIRoutingDefaultsStages(BaseModel):
    filter: ProviderName
    keywords: ProviderName
    global_summary: ReportProviderName
    report: ReportProviderName


class MonitorAIRoutingDefaultsResponse(BaseModel):
    profile_name: str
    stages: MonitorAIRoutingDefaultsStages


class MonitorBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    time_period: Literal["daily", "weekly", "custom"]
    report_type: Literal["daily", "weekly", "research"] | None = None
    source_ids: list[uuid.UUID] = Field(default_factory=list)
    source_overrides: dict[str, dict] = Field(default_factory=dict)  # dict can contain max_items, limit, max_results, keywords, usernames
    ai_routing: MonitorAIRouting = Field(default_factory=MonitorAIRouting)
    destination_ids: list[str] = Field(default_factory=list)
    window_hours: int = Field(default=24, ge=1, le=168)
    custom_schedule: str | None = None
    enabled: bool = True


class MonitorCreate(MonitorBase):
    @model_validator(mode="after")
    def validate_custom_requires_report_type(self) -> "MonitorCreate":
        if self.time_period == "custom" and self.report_type is None:
            raise ValueError("report_type is required when time_period is custom")
        return self


class MonitorUpdate(BaseModel):
    name: str | None = None
    time_period: Literal["daily", "weekly", "custom"] | None = None
    report_type: Literal["daily", "weekly", "research"] | None = None
    source_ids: list[uuid.UUID] | None = None
    source_overrides: dict[str, dict] | None = None
    ai_routing: MonitorAIRouting | None = None
    destination_ids: list[str] | None = None
    window_hours: int | None = Field(default=None, ge=1, le=168)
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
    run_id: uuid.UUID
    status: Literal["pending", "running"]
    monitor_id: uuid.UUID


class MonitorRunCancelResponse(BaseModel):
    run_id: uuid.UUID
    monitor_id: uuid.UUID
    status: Literal["pending", "running", "cancelling", "cancelled", "success", "failed", "partial_success"]


class MonitorRunRequest(BaseModel):
    window_hours: int | None = Field(default=None, ge=1, le=168)
