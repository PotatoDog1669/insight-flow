"""Provider schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ProviderId = Literal["agent_codex", "llm_openai"]
ProviderType = Literal["agent", "llm"]


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
