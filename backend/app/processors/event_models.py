"""Shared event-centric processor models."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.collectors.base import RawArticle


@dataclass(slots=True)
class CandidateCluster:
    """A weakly grouped set of articles that may describe one event."""

    cluster_id: str
    articles: list[RawArticle]
    source_ids: list[str] = field(default_factory=list)
    source_names: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EventExtractionInput:
    """Cluster payload prepared for event-level extraction."""

    cluster: CandidateCluster
    primary_article: RawArticle
    supporting_articles: list[RawArticle] = field(default_factory=list)


@dataclass(slots=True)
class ProcessedEvent:
    """Structured event object consumed by render/report stages."""

    event_id: str
    title: str
    summary: str
    detail: str
    article_ids: list[str] = field(default_factory=list)
    source_links: list[str] = field(default_factory=list)
    category: str | None = None
    keywords: list[str] = field(default_factory=list)
    importance: str = "normal"
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
    detail_mode: str = "full"

    def normalized_source_count(self) -> int:
        return self.source_count or len(self.source_links)


@dataclass(slots=True)
class GlobalSummary:
    """Structured global summary emitted after event aggregation."""

    global_tldr: str
    provider: str = ""
    fallback_used: bool = False
    prompt_metrics: dict[str, int | bool] = field(default_factory=dict)


@dataclass(slots=True)
class PipelineOutput:
    """Top-level event-centric pipeline output."""

    events: list[ProcessedEvent]
    article_stage_trace: dict[str, dict] = field(default_factory=dict)
    event_stage_trace: dict[str, dict] = field(default_factory=dict)
