"""Helpers for event-level extraction built on weak candidate clusters."""

from __future__ import annotations

from datetime import datetime

from app.processors.candidate_cluster import select_primary_article
from app.processors.event_models import CandidateCluster, EventExtractionInput, ProcessedEvent


def build_event_extraction_inputs(clusters: list[CandidateCluster]) -> list[EventExtractionInput]:
    inputs: list[EventExtractionInput] = []
    for cluster in clusters:
        if not cluster.articles:
            continue
        primary_article = select_primary_article(cluster)
        supporting_articles = [article for article in cluster.articles if article is not primary_article]
        inputs.append(
            EventExtractionInput(
                cluster=cluster,
                primary_article=primary_article,
                supporting_articles=supporting_articles,
            )
        )
    return inputs


def build_processed_event(event_input: EventExtractionInput, payload: dict) -> ProcessedEvent:
    primary = event_input.primary_article
    article_ids = _unique_nonempty(article.external_id for article in event_input.cluster.articles)
    source_links = _unique_nonempty(article.url for article in event_input.cluster.articles)
    source_names = _unique_nonempty(
        str((article.metadata or {}).get("source_name") or "").strip()
        for article in event_input.cluster.articles
    )
    event_id = article_ids[0] if article_ids else event_input.cluster.cluster_id
    title = str(payload.get("event_title") or primary.title or "").strip()[:96]
    summary = str(payload.get("summary") or "").strip()
    detail = str(payload.get("detail") or summary).strip()
    return ProcessedEvent(
        event_id=event_id,
        title=title or event_id,
        summary=summary,
        detail=detail,
        article_ids=article_ids,
        source_links=source_links,
        category=str(payload.get("category") or "").strip() or None,
        keywords=[str(item).strip() for item in payload.get("keywords", []) if str(item).strip()],
        importance=str(payload.get("importance") or "normal").strip() or "normal",
        source_count=len(source_links) or len(source_names),
        source_name=" / ".join(source_names[:3]),
        published_at=_to_iso(primary.published_at),
        who=str(payload.get("who") or "").strip(),
        what=str(payload.get("what") or "").strip(),
        when=str(payload.get("when") or "").strip(),
        metrics=[str(item).strip() for item in payload.get("metrics", []) if str(item).strip()],
        availability=str(payload.get("availability") or "").strip(),
        unknowns=str(payload.get("unknowns") or "").strip(),
        evidence=str(payload.get("evidence") or "").strip(),
    )


def _unique_nonempty(values: object) -> list[str]:
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in output:
            continue
        output.append(text)
    return output


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.isoformat() + "+00:00"
    return value.isoformat()
