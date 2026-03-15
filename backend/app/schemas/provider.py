"""Provider schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ProviderId = Literal["llm_openai"]
ProviderType = Literal["llm"]


class ProviderResponse(BaseModel):
    id: ProviderId
    name: str
    type: ProviderType
    description: str
    config: dict = Field(default_factory=dict)
    enabled: bool = False


class ProviderUpdate(BaseModel):
    enabled: bool | None = None
    config: dict | None = None


class ProviderTestRequest(BaseModel):
    config: dict | None = None


class ProviderTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: int | None = None
    model: str | None = None
