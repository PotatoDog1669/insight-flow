"""Schemas for the monitor agent draft workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.monitor import MonitorCreate


DraftSectionKind = Literal["source_list", "schedule", "unsupported"]
DraftItemStatus = Literal["ready", "suggested", "unavailable", "unsupported"]


class DraftItem(BaseModel):
    key: str
    type: str
    label: str
    status: DraftItemStatus
    reason: str | None = None
    source_id: str | None = None
    time_period: Literal["daily", "weekly", "custom"] | None = None
    custom_schedule: str | None = None


class DraftSection(BaseModel):
    kind: DraftSectionKind
    title: str
    summary: str | None = None
    items: list[DraftItem] = Field(default_factory=list)


class MonitorDraft(BaseModel):
    name: str
    summary: str | None = None
    sections: list[DraftSection] = Field(default_factory=list)
    editable: Literal[True] = True


class MonitorAgentRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None


class MonitorAgentClarifyResponse(BaseModel):
    mode: Literal["clarify"]
    conversation_id: str
    message: str
    missing_or_conflicting_fields: list[str] = Field(default_factory=list)


class MonitorAgentDraftResponse(BaseModel):
    mode: Literal["draft"]
    conversation_id: str
    message: str | None = None
    draft: MonitorDraft
    monitor_payload: MonitorCreate
    inferred_fields: list[str] = Field(default_factory=list)


class MonitorAgentStatusEvent(BaseModel):
    type: Literal["status"] = "status"
    key: str
    label: str
    status: Literal["running", "completed"]


class MonitorAgentMessageDeltaEvent(BaseModel):
    type: Literal["message_delta"] = "message_delta"
    delta: str


class MonitorAgentFinalEvent(BaseModel):
    type: Literal["final"] = "final"
    response: MonitorAgentClarifyResponse | MonitorAgentDraftResponse


class MonitorConversationState(BaseModel):
    conversation_id: str
    clarify_turn_count: int = 0
    intent_summary: str | None = None
    inferred_fields: list[str] = Field(default_factory=list)
    expires_at: datetime
