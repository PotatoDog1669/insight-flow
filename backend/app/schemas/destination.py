"""Destinations schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DestinationId = Literal["notion", "obsidian", "rss"]


class DestinationResponse(BaseModel):
    id: DestinationId
    name: str
    type: DestinationId
    description: str
    config: dict = Field(default_factory=dict)
    enabled: bool = False


class DestinationUpdate(BaseModel):
    enabled: bool | None = None
    config: dict | None = None
