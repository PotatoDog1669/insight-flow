"""Run-time debug payload helpers for transparent monitor logs."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import uuid

from app.collectors.base import RawArticle
from app.config import PROJECT_ROOT
from app.processors.event_models import CandidateCluster
from app.processors.pipeline import ProcessedArticle

RUN_ARTIFACT_DIR = PROJECT_ROOT / "output" / "run_artifacts"


def build_article_log_items(articles: list[RawArticle], *, reason: str | None = None) -> list[dict]:
    return [_build_article_log_item(article, reason=reason) for article in articles]


def build_processed_article_log_items(items: list[ProcessedArticle]) -> list[dict]:
    output: list[dict] = []
    for item in items:
        raw = item.raw
        metadata = raw.metadata if isinstance(raw.metadata, dict) else {}
        output.append(
            {
                "title": str(raw.title or "").strip(),
                "source_name": str(metadata.get("source_name") or "").strip(),
                "source_id": str(metadata.get("source_id") or "").strip(),
                "url": str(raw.url or "").strip(),
                "external_id": str(raw.external_id or "").strip(),
                "published_at": raw.published_at.isoformat() if raw.published_at else None,
                "debug_file": str(metadata.get("debug_file") or "").strip(),
                "event_title": str(item.event_title or "").strip(),
                "summary": str(item.summary or "").strip(),
                "category": str(item.category or "").strip(),
                "keywords": [keyword for keyword in item.keywords[:6] if str(keyword or "").strip()],
            }
        )
    return output


def build_candidate_cluster_log_items(clusters: list[CandidateCluster]) -> list[dict]:
    output: list[dict] = []
    for cluster in clusters:
        output.append(
            {
                "cluster_id": cluster.cluster_id,
                "item_count": len(cluster.articles),
                "source_names": list(cluster.source_names),
                "items": build_article_log_items(cluster.articles),
            }
        )
    return output


def build_report_event_log_items(events: list[dict]) -> list[dict]:
    output: list[dict] = []
    for event in events:
        output.append(
            {
                "index": int(event.get("index") or 0),
                "title": str(event.get("title") or "").strip(),
                "category": str(event.get("category") or "").strip(),
                "source_name": str(event.get("source_name") or "").strip(),
                "source_count": int(event.get("source_count") or 0),
                "summary": str(event.get("one_line_tldr") or "").strip(),
                "keywords": [str(item or "").strip() for item in (event.get("keywords") or []) if str(item or "").strip()],
                "article_ids": [str(item or "").strip() for item in (event.get("article_ids") or []) if str(item or "").strip()],
            }
        )
    return output


def partition_article_log_items(
    before: list[RawArticle],
    kept: list[RawArticle],
    *,
    dropped_reason: str | None = None,
) -> tuple[list[dict], list[dict]]:
    kept_signatures = Counter(_article_signature(article) for article in kept)
    kept_items: list[dict] = []
    dropped_items: list[dict] = []
    for article in before:
        signature = _article_signature(article)
        if kept_signatures[signature] > 0:
            kept_signatures[signature] -= 1
            kept_items.append(_build_article_log_item(article))
            continue
        dropped_items.append(_build_article_log_item(article, reason=dropped_reason))
    return kept_items, dropped_items


def build_section(*, title: str, section_type: str, items: list[dict], artifact_path: str | None = None) -> dict:
    section = {
        "title": title,
        "type": section_type,
        "count": len(items),
        "items": items,
    }
    if artifact_path:
        section["artifact_path"] = artifact_path
    return section


def build_transparent_log_payload(*, summary: dict, sections: list[dict]) -> dict:
    return {
        "kind": "transparent_log",
        "summary": summary,
        "sections": sections,
    }


def write_run_debug_artifact(
    *,
    run_id: uuid.UUID,
    source_id: uuid.UUID | None,
    filename: str,
    payload: list[dict] | dict,
) -> str:
    relative_dir = Path("output") / "run_artifacts" / str(run_id)
    relative_dir = relative_dir / (f"source_{source_id}" if source_id else "monitor")
    target = RUN_ARTIFACT_DIR / str(run_id) / (f"source_{source_id}" if source_id else "monitor") / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(relative_dir / filename)


def _build_article_log_item(article: RawArticle, *, reason: str | None = None) -> dict:
    metadata = article.metadata if isinstance(article.metadata, dict) else {}
    item = {
        "title": str(article.title or "").strip(),
        "source_name": str(metadata.get("source_name") or "").strip(),
        "source_id": str(metadata.get("source_id") or "").strip(),
        "url": str(article.url or "").strip(),
        "external_id": str(article.external_id or "").strip(),
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "debug_file": str(metadata.get("debug_file") or "").strip(),
    }
    if reason:
        item["reason"] = reason
    return item


def _article_signature(article: RawArticle) -> tuple[str, str, str, str | None]:
    metadata = article.metadata if isinstance(article.metadata, dict) else {}
    return (
        str(article.external_id or "").strip(),
        str(article.url or "").strip(),
        str(article.title or "").strip(),
        str(metadata.get("debug_file") or "").strip() or None,
    )
