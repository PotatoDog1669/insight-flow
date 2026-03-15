"""Schemas shared by research agent runtimes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Frequency = Literal["daily", "weekly", "custom"]
Template = Literal["brief", "research"]


@dataclass(slots=True)
class ResearchEvent:
    event_id: str
    title: str
    summary: str
    detail: str
    category: str
    importance: str
    source_links: list[str] = field(default_factory=list)
    source_count: int = 0
    source_name: str = ""
    published_at: str | None = None
    who: str = ""
    what: str = ""
    when: str = ""
    metrics: list[str] = field(default_factory=list)
    availability: str = ""
    unknowns: str = ""
    evidence: str = ""
    keywords: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ResearchJob:
    job_id: str
    frequency: Frequency
    template: Template
    event: ResearchEvent
    focus_questions: list[str] = field(default_factory=list)
    max_sources: int = 12
    must_verify: bool = True
    include_timeline: bool = True
    include_competitive_context: bool = True
    monitor_id: str | None = None
    user_id: str | None = None
    report_date: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ResearchSource:
    title: str
    url: str
    source_type: str = "unknown"


@dataclass(slots=True)
class ResearchResult:
    title: str
    summary: str
    content_markdown: str
    sources: list[ResearchSource] = field(default_factory=list)
    confidence_level: str = "unknown"
    confidence_reason: str = ""
    artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)
