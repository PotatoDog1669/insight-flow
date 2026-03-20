"""Destinations schema."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

DestinationType = Literal["notion", "obsidian", "rss"]
DestinationTestMode = Literal["rest", "file", "config"]


class DestinationResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: DestinationType
    description: str
    config: dict = Field(default_factory=dict)
    enabled: bool = False


class DestinationCreate(BaseModel):
    type: DestinationType
    name: str = Field(..., min_length=1, max_length=128)
    enabled: bool = True
    config: dict = Field(default_factory=dict)


class DestinationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    enabled: bool | None = None
    config: dict | None = None


class DestinationTestRequest(BaseModel):
    config: dict | None = None


class DestinationTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: int | None = None
    mode: DestinationTestMode | None = None
    checked_target: str | None = None


class ObsidianVaultCandidate(BaseModel):
    path: str
    name: str
    open: bool = False


class ObsidianVaultDiscoveryResponse(BaseModel):
    success: bool
    message: str
    detected_path: str | None = None
    vaults: list[ObsidianVaultCandidate] = Field(default_factory=list)
