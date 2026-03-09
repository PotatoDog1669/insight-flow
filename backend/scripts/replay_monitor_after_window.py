"""Replay exported monitor after_window data through processing + rendering.

Usage example:
uv run python backend/scripts/replay_monitor_after_window.py \
  --export-dir test_data/monitor_xxx/20260304T022614Z
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from app.collectors.base import RawArticle
from app.config import settings
from app.models.database import async_session
from app.models.monitor import Monitor
from app.models.user import User
from app.processors.event_models import CandidateCluster, GlobalSummary, ProcessedEvent
from app.processors.global_summary import run_global_summary_stage, run_global_summary_with_retry
from app.processors.pipeline import ProcessedArticle, ProcessingPipeline
from app.processors.report_stage import run_report_with_retry
from app.processors.window_filter import filter_raw_articles_by_window
from app.renderers.base import RenderContext
from app.renderers.daily import build_daily_events, render_daily_report
from app.routing.loader import load_routing_profile

FULL_CONTENT_MARKER = "----- FULL CONTENT -----"
DEFAULT_OUTPUT_NAME = "_replay"
DEFAULT_REPLAY_LLM_TIMEOUT_SEC = 120
DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
STAGE_ARTIFACTS = {
    "raw": "01_raw_articles.json",
    "window": "02_window_filtered.json",
    "filter": "03_filter_output.json",
    "keywords": "04_keywords_output.json",
    "aggregate": "05_aggregated_events.json",
    "global_summary": "06_global_summary.json",
    "render": "07_rendered_report.md",
    "report": "08_report_rewrite.json",
}
STAGE_ORDER = ("raw", "window", "filter", "keywords", "aggregate", "global_summary", "render", "report")
SUPPLEMENTAL_ARTIFACTS = {
    "candidate_cluster": "03_candidate_clusters.json",
    "event_extract": "04_event_extract_output.json",
}


def _none_if_nullish(raw: object) -> str | None:
    text = str(raw or "").strip()
    if not text or text.lower() in {"none", "null"}:
        return None
    return text


def _parse_iso_datetime(raw: object) -> datetime | None:
    text = _none_if_nullish(raw)
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_article_file(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if FULL_CONTENT_MARKER not in text:
        return {}, text.strip()

    head, _, tail = text.partition(FULL_CONTENT_MARKER)
    headers: dict[str, str] = {}
    for raw_line in head.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    content = tail.strip()
    return headers, content


def _article_key(*, source_id: str, external_id: str | None, url: str | None, title: str) -> str:
    stable = external_id or url or title
    return f"{source_id}::{stable}"


def _normalize_provider_overrides(raw: object) -> dict[str, dict]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        result[key] = value
    return result


def _load_provider_overrides(raw: str | None) -> dict[str, dict]:
    if not raw:
        return {}
    maybe_path = Path(raw)
    if maybe_path.exists():
        return _normalize_provider_overrides(_load_json(maybe_path))
    return _normalize_provider_overrides(json.loads(raw))


def _apply_replay_provider_defaults(provider_overrides: dict[str, dict]) -> dict[str, dict]:
    normalized = _normalize_provider_overrides(provider_overrides)
    llm_config = normalized.get("llm_openai")
    if not isinstance(llm_config, dict):
        return normalized

    updated_llm_config = dict(llm_config)
    timeout_raw = updated_llm_config.get("timeout_sec")
    try:
        timeout_sec = int(timeout_raw)
    except Exception:
        timeout_sec = 0
    if timeout_sec < DEFAULT_REPLAY_LLM_TIMEOUT_SEC:
        updated_llm_config["timeout_sec"] = DEFAULT_REPLAY_LLM_TIMEOUT_SEC
    normalized["llm_openai"] = updated_llm_config
    return normalized


def _provider_overrides_from_user_settings(settings_data: dict | None) -> dict[str, dict]:
    raw = (settings_data or {}).get("providers", {})
    if not isinstance(raw, dict):
        return {}

    result: dict[str, dict] = {}
    for provider_id, payload in raw.items():
        if not isinstance(provider_id, str) or not isinstance(payload, dict):
            continue
        if not bool(payload.get("enabled")):
            continue
        config = payload.get("config")
        if not isinstance(config, dict):
            continue
        result[provider_id] = dict(config)
    return _apply_replay_provider_defaults(result)


async def _load_provider_overrides_from_db(monitor_id: str | None) -> dict[str, dict]:
    normalized_monitor_id = _none_if_nullish(monitor_id)
    async with async_session() as session:
        user: User | None = None
        if normalized_monitor_id:
            try:
                monitor_uuid = uuid.UUID(normalized_monitor_id)
            except ValueError:
                monitor_uuid = None
            if monitor_uuid is not None:
                monitor = await session.get(Monitor, monitor_uuid)
                if monitor is not None:
                    user = await session.get(User, monitor.user_id)
        if user is None:
            user = await session.get(User, DEFAULT_USER_ID)
        if user is None:
            return {}
        return _provider_overrides_from_user_settings(user.settings)


async def _resolve_provider_overrides(provider_overrides_json: str | None, run_summary: dict) -> dict[str, dict]:
    explicit = _load_provider_overrides(provider_overrides_json)
    if explicit:
        return _apply_replay_provider_defaults(explicit)
    loaded = await _load_provider_overrides_from_db(_safe_str(run_summary.get("monitor_id")))
    return _apply_replay_provider_defaults(loaded)


def _fallback_category(collect_method: str) -> str:
    method = str(collect_method or "").strip().lower()
    if method in {"github_trending"}:
        return "open_source"
    if method in {"huggingface"}:
        return "academic"
    return "blog"


def _iter_source_dirs(export_dir: Path) -> list[Path]:
    dirs = [
        item
        for item in export_dir.iterdir()
        if item.is_dir() and (item / "_summary.json").exists() and (item / "raw").exists()
    ]
    return sorted(dirs, key=lambda item: item.name)


def _safe_str(value: object) -> str:
    return str(value or "").strip()


async def _collect_after_window_articles(
    *,
    export_dir: Path,
    run_summary: dict,
) -> tuple[list[RawArticle], dict[str, dict], dict[str, dict]]:
    source_dirs = _iter_source_dirs(export_dir)
    source_summaries: list[tuple[Path, dict]] = []
    for source_dir in source_dirs:
        summary = _load_json(source_dir / "_summary.json")
        source_id_text = _safe_str(summary.get("source_id"))
        if not source_id_text:
            continue
        source_summaries.append((source_dir, summary))

    snapshot_fallback = _none_if_nullish(run_summary.get("window_end")) or datetime.now(timezone.utc).isoformat()
    raw_articles: list[RawArticle] = []
    per_source_stats: dict[str, dict] = {}
    source_settings: dict[str, dict] = {}

    for source_dir, summary in source_summaries:
        source_id_text = _safe_str(summary.get("source_id"))
        source_name = _safe_str(summary.get("source_name")) or source_dir.name
        collect_method = _safe_str(summary.get("collect_method"))
        source_category = _safe_str(summary.get("source_category")) or _fallback_category(collect_method)
        source_config = summary.get("source_config") if isinstance(summary.get("source_config"), dict) else {}

        per_source_stats[source_id_text] = {
            "source_id": source_id_text,
            "source_name": source_name,
            "collect_method": collect_method,
            "source_category": source_category,
            "raw_total": 0,
            "raw_after_window": 0,
            "processed": 0,
        }
        source_settings[source_id_text] = {
            "source_name": source_name,
            "collect_method": collect_method,
            "source_category": source_category,
            "source_config": source_config,
        }

        entries = summary.get("raw_articles")
        files: list[Path] = []
        if isinstance(entries, list) and entries:
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                rel_file = _safe_str(entry.get("file"))
                if not rel_file:
                    continue
                path = export_dir / rel_file
                if path.exists() and path.is_file():
                    files.append(path)
        if not files:
            files = sorted((source_dir / "raw").glob("*.txt"))

        for idx, file_path in enumerate(files, start=1):
            headers, content = _parse_article_file(file_path)
            title = _none_if_nullish(headers.get("title")) or file_path.stem
            url = _none_if_nullish(headers.get("url"))
            external_id = _none_if_nullish(headers.get("external_id")) or url or f"{source_id_text}:{idx}"
            published_at = _parse_iso_datetime(headers.get("published_at"))
            extractor = _none_if_nullish(headers.get("extractor"))
            metadata = {
                "source_name": source_name,
                "source_id": source_id_text,
                "source_category": source_category,
                "collect_method": collect_method,
                "extractor": extractor,
                "snapshot_at": snapshot_fallback if published_at is None else None,
                "debug_file": str(file_path.relative_to(export_dir)),
            }
            raw_articles.append(
                RawArticle(
                    external_id=external_id,
                    title=title,
                    url=url,
                    content=content,
                    published_at=published_at,
                    metadata=metadata,
                )
            )
            per_source_stats[source_id_text]["raw_total"] += 1

    return raw_articles, per_source_stats, source_settings


def _raw_article_to_dict(raw: RawArticle) -> dict:
    return {
        "external_id": raw.external_id,
        "title": raw.title,
        "url": raw.url,
        "content": raw.content,
        "published_at": raw.published_at.isoformat() if raw.published_at else None,
        "metadata": raw.metadata if isinstance(raw.metadata, dict) else {},
    }


def _raw_article_from_dict(data: dict) -> RawArticle:
    return RawArticle(
        external_id=_none_if_nullish(data.get("external_id")),
        title=_safe_str(data.get("title")),
        url=_none_if_nullish(data.get("url")),
        content=_safe_str(data.get("content")),
        published_at=_parse_iso_datetime(data.get("published_at")),
        metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
    )


def _processed_article_to_dict(item: ProcessedArticle) -> dict:
    return {
        "raw": _raw_article_to_dict(item.raw),
        "event_title": item.event_title,
        "summary": item.summary,
        "keywords": item.keywords,
        "score": item.score,
        "importance": item.importance,
        "detail": item.detail,
        "category": item.category,
        "who": item.who,
        "what": item.what,
        "when": item.when,
        "metrics": item.metrics,
        "availability": item.availability,
        "unknowns": item.unknowns,
        "evidence": item.evidence,
        "detail_mode": item.detail_mode,
    }


def _processed_article_from_dict(data: dict) -> ProcessedArticle:
    return ProcessedArticle(
        raw=_raw_article_from_dict(data.get("raw") if isinstance(data.get("raw"), dict) else {}),
        event_title=_safe_str(data.get("event_title")),
        summary=_safe_str(data.get("summary")),
        keywords=data.get("keywords") if isinstance(data.get("keywords"), list) else [],
        score=float(data.get("score", 1.0) or 1.0),
        importance=_safe_str(data.get("importance")) or "normal",
        detail=_safe_str(data.get("detail")),
        category=_none_if_nullish(data.get("category")),
        who=_safe_str(data.get("who")),
        what=_safe_str(data.get("what")),
        when=_safe_str(data.get("when")),
        metrics=data.get("metrics") if isinstance(data.get("metrics"), list) else [],
        availability=_safe_str(data.get("availability")),
        unknowns=_safe_str(data.get("unknowns")),
        evidence=_safe_str(data.get("evidence")),
        detail_mode=_safe_str(data.get("detail_mode")) or "full",
    )


def _candidate_cluster_to_dict(cluster: CandidateCluster) -> dict:
    return {
        "cluster_id": cluster.cluster_id,
        "articles": [_raw_article_to_dict(item) for item in cluster.articles],
        "source_ids": list(cluster.source_ids),
        "source_names": list(cluster.source_names),
    }


def _candidate_cluster_from_dict(data: dict) -> CandidateCluster:
    return CandidateCluster(
        cluster_id=_safe_str(data.get("cluster_id")) or "cluster-1",
        articles=[_raw_article_from_dict(item) for item in data.get("articles", []) if isinstance(item, dict)],
        source_ids=data.get("source_ids") if isinstance(data.get("source_ids"), list) else [],
        source_names=data.get("source_names") if isinstance(data.get("source_names"), list) else [],
    )


def _processed_event_to_dict(item: ProcessedEvent) -> dict:
    return {
        "event_id": item.event_id,
        "title": item.title,
        "summary": item.summary,
        "detail": item.detail,
        "article_ids": list(item.article_ids),
        "source_links": list(item.source_links),
        "category": item.category,
        "keywords": list(item.keywords),
        "importance": item.importance,
        "source_count": item.source_count,
        "source_name": item.source_name,
        "published_at": item.published_at,
        "who": item.who,
        "what": item.what,
        "when": item.when,
        "metrics": list(item.metrics),
        "availability": item.availability,
        "unknowns": item.unknowns,
        "evidence": item.evidence,
        "detail_mode": item.detail_mode,
    }


def _processed_event_from_dict(data: dict) -> ProcessedEvent:
    return ProcessedEvent(
        event_id=_safe_str(data.get("event_id")),
        title=_safe_str(data.get("title")),
        summary=_safe_str(data.get("summary")),
        detail=_safe_str(data.get("detail")),
        article_ids=data.get("article_ids") if isinstance(data.get("article_ids"), list) else [],
        source_links=data.get("source_links") if isinstance(data.get("source_links"), list) else [],
        category=_none_if_nullish(data.get("category")),
        keywords=data.get("keywords") if isinstance(data.get("keywords"), list) else [],
        importance=_safe_str(data.get("importance")) or "normal",
        source_count=int(data.get("source_count", 0) or 0),
        source_name=_safe_str(data.get("source_name")),
        published_at=_none_if_nullish(data.get("published_at")),
        who=_safe_str(data.get("who")),
        what=_safe_str(data.get("what")),
        when=_safe_str(data.get("when")),
        metrics=data.get("metrics") if isinstance(data.get("metrics"), list) else [],
        availability=_safe_str(data.get("availability")),
        unknowns=_safe_str(data.get("unknowns")),
        evidence=_safe_str(data.get("evidence")),
        detail_mode=_safe_str(data.get("detail_mode")) or "full",
    )


def _global_summary_to_dict(item: GlobalSummary) -> dict:
    return {
        "global_tldr": item.global_tldr,
        "provider": item.provider,
        "fallback_used": item.fallback_used,
        "prompt_metrics": item.prompt_metrics,
    }


def _global_summary_from_dict(data: dict) -> GlobalSummary:
    return GlobalSummary(
        global_tldr=_safe_str(data.get("global_tldr")),
        provider=_safe_str(data.get("provider")),
        fallback_used=bool(data.get("fallback_used", False)),
        prompt_metrics=data.get("prompt_metrics") if isinstance(data.get("prompt_metrics"), dict) else {},
    )


def _write_json_artifact(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json_artifact(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _avg(numbers: list[int]) -> float:
    if not numbers:
        return 0.0
    return round(sum(numbers) / len(numbers), 2)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _build_diagnostics(
    *,
    raw_articles: list[RawArticle],
    processed_articles: list[ProcessedArticle],
    rendered_events: list[dict] | None = None,
) -> tuple[list[dict], dict]:
    processed_map: dict[str, list[ProcessedArticle]] = {}
    for item in processed_articles:
        key = _article_key(
            source_id=_safe_str(item.raw.metadata.get("source_id")),
            external_id=item.raw.external_id,
            url=item.raw.url,
            title=item.raw.title,
        )
        processed_map.setdefault(key, []).append(item)

    rows: list[dict] = []
    summary_lens: list[int] = []
    stage_detail_lens: list[int] = []
    keywords_lens: list[int] = []
    rendered_detail_lens: list[int] = []
    processed_total = 0
    stage_detailed_enough = 0
    rendered_detailed_enough = 0
    compact_details = 0

    rendered_event_map: dict[str, list[dict]] = {}
    for event in rendered_events or []:
        event_id = _safe_str(event.get("event_id"))
        if not event_id:
            continue
        rendered_event_map.setdefault(event_id, []).append(event)

    for raw in raw_articles:
        key = _article_key(
            source_id=_safe_str(raw.metadata.get("source_id")),
            external_id=raw.external_id,
            url=raw.url,
            title=raw.title,
        )
        bucket = processed_map.get(key, [])
        matched = bucket.pop(0) if bucket else None
        kept = matched is not None

        summary = matched.summary if matched else ""
        detail = matched.detail if matched else ""
        keywords = matched.keywords if matched else []

        summary_len = len(summary or "")
        detail_len = len(detail or "")
        keywords_len = len(keywords or [])
        content_len = len(raw.content or "")
        importance = getattr(matched, "importance", None) if matched else None
        detail_mode = str(getattr(matched, "detail_mode", "") or "").strip() if matched else ""
        event_bucket = rendered_event_map.get(raw.external_id or "", [])
        rendered_event = event_bucket.pop(0) if event_bucket else None
        rendered_detail = _safe_str((rendered_event or {}).get("detail"))
        rendered_detail_len = len(rendered_detail)
        rendered_metrics = (rendered_event or {}).get("metrics")
        rendered_keywords = (rendered_event or {}).get("keywords")

        if kept:
            processed_total += 1
            summary_lens.append(summary_len)
            stage_detail_lens.append(detail_len)
            keywords_lens.append(keywords_len)
            if detail_len >= 200:
                stage_detailed_enough += 1
            rendered_detail_lens.append(rendered_detail_len)
            if rendered_detail_len >= 200:
                rendered_detailed_enough += 1
            if detail_mode == "compact":
                compact_details += 1

        rows.append(
            {
                "source_id": _safe_str(raw.metadata.get("source_id")),
                "source_name": _safe_str(raw.metadata.get("source_name")),
                "external_id": raw.external_id,
                "title": raw.title,
                "url": raw.url,
                "published_at": raw.published_at.isoformat() if raw.published_at else None,
                "snapshot_at": _none_if_nullish(raw.metadata.get("snapshot_at")),
                "kept_after_filter": kept,
                "content_chars": content_len,
                "summary_chars": summary_len,
                "detail_chars": detail_len,
                "rendered_detail_chars": rendered_detail_len,
                "keywords_count": keywords_len,
                "rendered_keywords_count": len(rendered_keywords) if isinstance(rendered_keywords, list) else 0,
                "rendered_metrics_count": len(rendered_metrics) if isinstance(rendered_metrics, list) else 0,
                "rendered_category": _safe_str((rendered_event or {}).get("category")),
                "importance": _none_if_nullish(importance),
                "detail_mode": detail_mode,
                "debug_file": _safe_str(raw.metadata.get("debug_file")),
            }
        )

    metrics = {
        "raw_after_window_total": len(raw_articles),
        "processed_total": processed_total,
        "dropped_total": max(len(raw_articles) - processed_total, 0),
        "keep_ratio": _ratio(processed_total, len(raw_articles)),
        "avg_content_chars": _avg([len(item.content or "") for item in raw_articles]),
        "avg_summary_chars": _avg(summary_lens),
        "avg_stage_detail_chars": _avg(stage_detail_lens),
        "avg_rendered_detail_chars": _avg(rendered_detail_lens),
        "avg_keywords_count": _avg(keywords_lens),
        "stage_detail_ge_200_ratio": _ratio(stage_detailed_enough, processed_total),
        "rendered_detail_ge_200_ratio": _ratio(rendered_detailed_enough, processed_total),
        "compact_detail_ratio": _ratio(compact_details, processed_total),
    }
    return rows, metrics


def _merge_provider_config(
    *,
    provider_name: str,
    profile_config: dict,
    provider_overrides: dict[str, dict],
) -> dict:
    merged = dict(profile_config if isinstance(profile_config, dict) else {})
    overrides = provider_overrides.get(provider_name)
    if isinstance(overrides, dict):
        merged.update(overrides)
    return merged


def _max_retry(config: dict) -> int:
    raw = config.get("max_retry", 0) if isinstance(config, dict) else 0
    try:
        return max(int(raw), 0)
    except Exception:
        return 0


async def _run_report_with_retry(
    *,
    route,
    providers: dict[str, dict],
    provider_overrides: dict[str, dict],
    payload: dict,
) -> tuple[dict, str]:
    return await run_report_with_retry(
        route=route,
        providers=providers,
        provider_overrides=provider_overrides,
        payload=payload,
    )


def _event_metrics(events: list[dict]) -> dict:
    with_published = 0
    with_keywords = 0
    with_metrics = 0
    with_links = 0
    category_counts: dict[str, int] = {}
    for event in events:
        if _none_if_nullish(event.get("published_at")):
            with_published += 1
        if isinstance(event.get("keywords"), list) and len(event.get("keywords")) >= 3:
            with_keywords += 1
        if isinstance(event.get("metrics"), list) and len(event.get("metrics")) >= 1:
            with_metrics += 1
        if isinstance(event.get("source_links"), list) and len(event.get("source_links")) >= 1:
            with_links += 1
        category = _safe_str(event.get("category")) or "unknown"
        category_counts[category] = category_counts.get(category, 0) + 1

    total = len(events)
    return {
        "events_total": total,
        "events_with_published_at": with_published,
        "events_with_keywords_ge_3": with_keywords,
        "events_with_metrics": with_metrics,
        "events_with_links": with_links,
        "published_coverage": _ratio(with_published, total),
        "keywords_coverage": _ratio(with_keywords, total),
        "metrics_coverage": _ratio(with_metrics, total),
        "links_coverage": _ratio(with_links, total),
        "category_counts": category_counts,
    }


def _artifact_path(output_dir: Path, stage: str) -> Path:
    return output_dir / STAGE_ARTIFACTS[stage]


def _stage_index(stage: str | None) -> int:
    if stage is None:
        return -1
    try:
        return STAGE_ORDER.index(stage)
    except ValueError as exc:
        raise ValueError(f"Unsupported stage: {stage}") from exc


def _should_stop_now(*, stage: str, stop_after: str | None) -> bool:
    if stop_after is None:
        return False
    return _stage_index(stage) >= _stage_index(stop_after)


def _raw_articles_from_artifact(path: Path) -> list[RawArticle]:
    payload = _read_json_artifact(path)
    if not isinstance(payload, list):
        return []
    return [_raw_article_from_dict(item) for item in payload if isinstance(item, dict)]


def _processed_articles_from_artifact(path: Path) -> list[ProcessedArticle]:
    payload = _read_json_artifact(path)
    if not isinstance(payload, list):
        return []
    return [_processed_article_from_dict(item) for item in payload if isinstance(item, dict)]


def _events_from_artifact(path: Path) -> list[dict]:
    payload = _read_json_artifact(path)
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _candidate_clusters_from_artifact(path: Path) -> list[CandidateCluster]:
    payload = _read_json_artifact(path)
    if not isinstance(payload, list):
        return []
    return [_candidate_cluster_from_dict(item) for item in payload if isinstance(item, dict)]


def _processed_events_from_artifact(path: Path) -> list[ProcessedEvent]:
    payload = _read_json_artifact(path)
    if not isinstance(payload, list):
        return []
    return [_processed_event_from_dict(item) for item in payload if isinstance(item, dict)]


def _global_summary_from_artifact(path: Path) -> GlobalSummary | None:
    payload = _read_json_artifact(path)
    if not isinstance(payload, dict):
        return None
    return _global_summary_from_dict(payload)


def _report_date_from_summary(run_summary: dict) -> str:
    window_end = _parse_iso_datetime(run_summary.get("window_end"))
    if window_end is not None:
        return window_end.date().isoformat()
    return datetime.now(timezone.utc).date().isoformat()


async def _run_window_stage(
    *,
    raw_articles: list[RawArticle],
    run_summary: dict,
    source_settings: dict[str, dict],
) -> tuple[list[RawArticle], dict[str, dict]]:
    window_hours = int(run_summary.get("window_hours") or 24)
    window_start = _parse_iso_datetime(run_summary.get("window_start")) or datetime.now(timezone.utc)
    window_end = _parse_iso_datetime(run_summary.get("window_end")) or datetime.now(timezone.utc)
    grouped: dict[str, list[RawArticle]] = {}
    for item in raw_articles:
        source_id = _safe_str((item.metadata or {}).get("source_id"))
        grouped.setdefault(source_id, []).append(item)

    kept: list[RawArticle] = []
    traces: dict[str, dict] = {}
    for source_id, items in grouped.items():
        config = source_settings.get(source_id, {}).get("source_config")
        allow_first_seen_fallback = bool(config.get("window_allow_first_seen_fallback", False)) if isinstance(config, dict) else False
        filtered, trace = await filter_raw_articles_by_window(
            raw_articles=items,
            window_start=window_start,
            window_end=window_end,
            window_hours=window_hours,
            allow_first_seen_fallback=allow_first_seen_fallback,
        )
        kept.extend(filtered)
        traces[source_id] = trace
    return kept, traces


async def _run_replay(
    *,
    export_dir: Path,
    output_dir: Path,
    routing_profile: str,
    provider_overrides: dict[str, dict],
    run_report_rewrite: bool,
    max_articles: int | None,
    pipeline_mode: str,
    fallback_rule_on_auth_error: bool,
    stage_concurrency: int = 1,
    stop_after: str | None = None,
    resume_from: str | None = None,
) -> dict:
    run_summary = _load_json(export_dir / "_run_summary.json")
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_articles: list[RawArticle]
    window_articles: list[RawArticle] = []
    filtered_articles: list[RawArticle] = []
    processed_articles: list[ProcessedArticle] = []
    candidate_clusters: list[CandidateCluster] = []
    processed_events: list[ProcessedEvent] = []
    aggregated_events: list[dict] = []
    global_summary: GlobalSummary | None = None
    rendered_events: list[dict] = []
    report = None
    last_completed_stage = "raw"
    report_provider_used = "not_run"
    report_stage_error: str | None = None

    raw_artifact = _artifact_path(output_dir, "raw")
    if resume_from and _stage_index(resume_from) >= _stage_index("raw") and raw_artifact.exists():
        raw_articles = _raw_articles_from_artifact(raw_artifact)
        source_stats = _read_json_artifact(output_dir / "source_breakdown.json")
        source_stats = {item["source_id"]: item for item in source_stats if isinstance(item, dict) and item.get("source_id")}
        source_settings = _read_json_artifact(output_dir / "source_settings.json")
        source_settings = source_settings if isinstance(source_settings, dict) else {}
    else:
        raw_articles, source_stats, source_settings = await _collect_after_window_articles(export_dir=export_dir, run_summary=run_summary)
        _write_json_artifact(raw_artifact, [_raw_article_to_dict(item) for item in raw_articles])
        _write_json_artifact(output_dir / "source_breakdown.json", list(source_stats.values()))
        _write_json_artifact(output_dir / "source_settings.json", source_settings)
    if _should_stop_now(stage="raw", stop_after=stop_after):
        return {"output_dir": str(output_dir), "last_completed_stage": last_completed_stage}

    window_artifact = _artifact_path(output_dir, "window")
    if resume_from and _stage_index(resume_from) >= _stage_index("window") and window_artifact.exists():
        window_articles = _raw_articles_from_artifact(window_artifact)
    else:
        window_articles, window_traces = await _run_window_stage(
            raw_articles=raw_articles,
            run_summary=run_summary,
            source_settings=source_settings,
        )
        if max_articles is not None and max_articles > 0:
            window_articles = window_articles[:max_articles]
        _write_json_artifact(window_artifact, [_raw_article_to_dict(item) for item in window_articles])
        _write_json_artifact(output_dir / "window_stage_trace.json", window_traces)
    last_completed_stage = "window"
    if _should_stop_now(stage="window", stop_after=stop_after):
        return {"output_dir": str(output_dir), "last_completed_stage": last_completed_stage}

    def _build_pipeline() -> ProcessingPipeline:
        pipeline = ProcessingPipeline(routing_profile=routing_profile)
        pipeline.set_provider_overrides(provider_overrides)
        pipeline.set_stage_concurrency(stage_concurrency)
        return pipeline

    pipeline = _build_pipeline()
    pipeline_mode_used = pipeline_mode
    if pipeline_mode == "rule":
        _force_pipeline_rule_mode(pipeline)

    filter_artifact = _artifact_path(output_dir, "filter")
    if resume_from and _stage_index(resume_from) >= _stage_index("filter") and filter_artifact.exists():
        filtered_articles = _raw_articles_from_artifact(filter_artifact)
    else:
        try:
            filtered_articles, _ = await pipeline.run_filter_stage(window_articles)
        except Exception as exc:
            message = str(exc)
            if fallback_rule_on_auth_error and pipeline_mode != "rule" and "401" in message and "Unauthorized" in message:
                pipeline = _build_pipeline()
                _force_pipeline_rule_mode(pipeline)
                pipeline_mode_used = "rule_fallback"
                filtered_articles, _ = await pipeline.run_filter_stage(window_articles)
            else:
                raise
        _write_json_artifact(filter_artifact, [_raw_article_to_dict(item) for item in filtered_articles])
    last_completed_stage = "filter"
    if _should_stop_now(stage="filter", stop_after=stop_after):
        return {"output_dir": str(output_dir), "last_completed_stage": last_completed_stage}

    candidate_cluster_artifact = output_dir / SUPPLEMENTAL_ARTIFACTS["candidate_cluster"]
    if resume_from and _stage_index(resume_from) > _stage_index("filter") and candidate_cluster_artifact.exists():
        candidate_clusters = _candidate_clusters_from_artifact(candidate_cluster_artifact)
    else:
        candidate_clusters, _ = await pipeline.run_candidate_cluster_stage(filtered_articles)
        _write_json_artifact(
            candidate_cluster_artifact,
            [_candidate_cluster_to_dict(item) for item in candidate_clusters],
        )

    keywords_artifact = _artifact_path(output_dir, "keywords")
    if resume_from and _stage_index(resume_from) >= _stage_index("keywords") and keywords_artifact.exists():
        processed_articles = _processed_articles_from_artifact(keywords_artifact)
    else:
        try:
            processed_articles, _ = await pipeline.run_keywords_stage(filtered_articles)
        except Exception as exc:
            message = str(exc)
            if fallback_rule_on_auth_error and pipeline_mode != "rule" and "401" in message and "Unauthorized" in message:
                pipeline = _build_pipeline()
                _force_pipeline_rule_mode(pipeline)
                pipeline_mode_used = "rule_fallback"
                processed_articles, _ = await pipeline.run_keywords_stage(filtered_articles)
            else:
                raise
        _write_json_artifact(keywords_artifact, [_processed_article_to_dict(item) for item in processed_articles])
    event_extract_artifact = output_dir / SUPPLEMENTAL_ARTIFACTS["event_extract"]
    if resume_from and _stage_index(resume_from) >= _stage_index("keywords") and event_extract_artifact.exists():
        processed_events = _processed_events_from_artifact(event_extract_artifact)
    else:
        processed_events, _ = await pipeline.run_event_extract_stage(candidate_clusters)
        _write_json_artifact(
            event_extract_artifact,
            [_processed_event_to_dict(item) for item in processed_events],
        )
    last_completed_stage = "keywords"

    diagnostics, processing_metrics = _build_diagnostics(
        raw_articles=window_articles,
        processed_articles=processed_articles,
        rendered_events=[],
    )
    if _should_stop_now(stage="keywords", stop_after=stop_after):
        metrics = {
            "routing_profile": routing_profile,
            "pipeline_mode_used": pipeline_mode_used,
            "report_provider_used": report_provider_used,
            "report_stage_error": report_stage_error,
            "processing": processing_metrics,
            "events": {
                **_event_metrics([]),
                "candidate_cluster_count": len(candidate_clusters),
                "event_extract_count": len(processed_events),
            },
            "source_breakdown": list(source_stats.values()),
            "top_low_detail_items": [],
        }
        _write_json_artifact(output_dir / "run_summary.json", run_summary)
        _write_json_artifact(output_dir / "metrics.json", metrics)
        _write_json_artifact(output_dir / "diagnostics.json", diagnostics)
        _write_json_artifact(output_dir / "pipeline_stage_trace.json", pipeline.last_stage_trace)
        return {"output_dir": str(output_dir), "last_completed_stage": last_completed_stage}

    report_date = _report_date_from_summary(run_summary)
    aggregate_artifact = _artifact_path(output_dir, "aggregate")
    if resume_from and _stage_index(resume_from) >= _stage_index("aggregate") and aggregate_artifact.exists():
        aggregated_events = _events_from_artifact(aggregate_artifact)
    else:
        aggregated_events = build_daily_events(processed_events or processed_articles)
        _write_json_artifact(aggregate_artifact, aggregated_events)
    last_completed_stage = "aggregate"
    if _should_stop_now(stage="aggregate", stop_after=stop_after):
        metrics = {
            "routing_profile": routing_profile,
            "pipeline_mode_used": pipeline_mode_used,
            "report_provider_used": report_provider_used,
            "report_stage_error": report_stage_error,
            "processing": processing_metrics,
            "global_summary_provider_used": "not_run",
            "global_summary_chars": 0,
            "global_summary_fallback_used": False,
            "events": {
                **_event_metrics(aggregated_events),
                "candidate_cluster_count": len(candidate_clusters),
                "event_extract_count": len(processed_events),
                "aggregated_event_count": len(aggregated_events),
            },
            "source_breakdown": list(source_stats.values()),
            "top_low_detail_items": [],
        }
        _write_json_artifact(output_dir / "run_summary.json", run_summary)
        _write_json_artifact(output_dir / "metrics.json", metrics)
        _write_json_artifact(output_dir / "diagnostics.json", diagnostics)
        _write_json_artifact(output_dir / "pipeline_stage_trace.json", pipeline.last_stage_trace)
        return {"output_dir": str(output_dir), "last_completed_stage": last_completed_stage}

    global_summary_artifact = _artifact_path(output_dir, "global_summary")
    if resume_from and _stage_index(resume_from) >= _stage_index("global_summary") and global_summary_artifact.exists():
        global_summary = _global_summary_from_artifact(global_summary_artifact)
    else:
        profile = load_routing_profile(routing_profile)
        summary_route = profile.stages.global_summary or profile.stages.report

        async def _summary_runner(payload: dict) -> tuple[dict, str]:
            return await run_global_summary_with_retry(
                route=summary_route,
                providers=profile.providers,
                provider_overrides=provider_overrides,
                payload=payload,
            )

        global_summary = await run_global_summary_stage(
            events=aggregated_events,
            runner=_summary_runner,
        )
        _write_json_artifact(global_summary_artifact, _global_summary_to_dict(global_summary))
    last_completed_stage = "global_summary"
    if _should_stop_now(stage="global_summary", stop_after=stop_after):
        metrics = {
            "routing_profile": routing_profile,
            "pipeline_mode_used": pipeline_mode_used,
            "report_provider_used": report_provider_used,
            "report_stage_error": report_stage_error,
            "processing": processing_metrics,
            "global_summary_provider_used": global_summary.provider if global_summary is not None else "not_run",
            "global_summary_chars": len(global_summary.global_tldr) if global_summary is not None else 0,
            "global_summary_fallback_used": bool(global_summary.fallback_used) if global_summary is not None else False,
            "events": {
                **_event_metrics(aggregated_events),
                "candidate_cluster_count": len(candidate_clusters),
                "event_extract_count": len(processed_events),
                "aggregated_event_count": len(aggregated_events),
            },
            "source_breakdown": list(source_stats.values()),
            "top_low_detail_items": [],
        }
        _write_json_artifact(output_dir / "run_summary.json", run_summary)
        _write_json_artifact(output_dir / "metrics.json", metrics)
        _write_json_artifact(output_dir / "diagnostics.json", diagnostics)
        _write_json_artifact(output_dir / "pipeline_stage_trace.json", pipeline.last_stage_trace)
        return {"output_dir": str(output_dir), "last_completed_stage": last_completed_stage}

    report = render_daily_report(
        events=aggregated_events,
        context=RenderContext(date=report_date),
        global_summary=global_summary.global_tldr if global_summary is not None else None,
    )
    (output_dir / STAGE_ARTIFACTS["render"]).write_text(report.content, encoding="utf-8")
    _write_json_artifact(
        output_dir / "report_meta.json",
        {
            "title": report.title,
            "global_tldr": report.metadata.get("global_tldr"),
            "metadata": report.metadata,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    last_completed_stage = "render"
    if _should_stop_now(stage="render", stop_after=stop_after):
        report_provider_used = "daily_renderer"
    elif run_report_rewrite:
        profile = load_routing_profile(routing_profile)
        metadata = dict(report.metadata or {})
        payload = {
            "title": report.title,
            "content": report.content,
            "events": metadata.get("events", []),
            "global_tldr": _safe_str(metadata.get("global_tldr")),
            "date": report_date,
        }
        try:
            report_output, report_provider_used = await _run_report_with_retry(
                route=profile.stages.report,
                providers=profile.providers,
                provider_overrides=provider_overrides,
                payload=payload,
            )
            _write_json_artifact(output_dir / STAGE_ARTIFACTS["report"], report_output)
            title = _none_if_nullish(report_output.get("title"))
            content = _none_if_nullish(report_output.get("content"))
            global_tldr = _none_if_nullish(report_output.get("global_tldr"))
            if title:
                report.title = title
            if content:
                report.content = content
            if global_tldr:
                report.metadata["global_tldr"] = global_tldr
                report.metadata["tldr"] = [global_tldr]
            (output_dir / "report.md").write_text(report.content, encoding="utf-8")
            _write_json_artifact(
                output_dir / "report_meta.json",
                {
                    "title": report.title,
                    "global_tldr": report.metadata.get("global_tldr"),
                    "metadata": report.metadata,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            last_completed_stage = "report"
        except Exception as exc:  # pragma: no cover - runtime fallback
            report_provider_used = "daily_renderer"
            report_stage_error = str(exc)
    else:
        report_provider_used = "daily_renderer"

    rendered_events = list((report.metadata or {}).get("events") or []) if report is not None else []
    diagnostics, processing_metrics = _build_diagnostics(
        raw_articles=window_articles,
        processed_articles=processed_articles,
        rendered_events=rendered_events,
    )
    event_metrics = _event_metrics(rendered_events)

    processed_per_source: dict[str, int] = {}
    for item in processed_articles:
        source_id = _safe_str(item.raw.metadata.get("source_id"))
        if not source_id:
            continue
        processed_per_source[source_id] = processed_per_source.get(source_id, 0) + 1

    for source_id, stats in source_stats.items():
        stats["raw_after_window"] = len([item for item in window_articles if _safe_str(item.metadata.get("source_id")) == source_id])
        stats["processed"] = processed_per_source.get(source_id, 0)
        stats["keep_ratio"] = _ratio(stats["processed"], stats["raw_after_window"])

    top_low_detail = sorted(
        [row for row in diagnostics if row["kept_after_filter"]],
        key=lambda row: row["rendered_detail_chars"],
    )[:5]

    metrics = {
        "routing_profile": routing_profile,
        "pipeline_mode_used": pipeline_mode_used,
        "report_provider_used": report_provider_used,
        "report_stage_error": report_stage_error,
        "processing": processing_metrics,
        "global_summary_provider_used": global_summary.provider if global_summary is not None else "not_run",
        "global_summary_chars": len(global_summary.global_tldr) if global_summary is not None else 0,
        "global_summary_fallback_used": bool(global_summary.fallback_used) if global_summary is not None else False,
        "events": {
            **event_metrics,
            "candidate_cluster_count": len(candidate_clusters),
            "event_extract_count": len(processed_events),
            "aggregated_event_count": len(aggregated_events),
        },
        "source_breakdown": list(source_stats.values()),
        "top_low_detail_items": [
            {
                "source_name": row["source_name"],
                "title": row["title"],
                "stage_detail_chars": row["detail_chars"],
                "rendered_detail_chars": row["rendered_detail_chars"],
                "summary_chars": row["summary_chars"],
                "debug_file": row["debug_file"],
            }
            for row in top_low_detail
        ],
    }

    _write_json_artifact(output_dir / "run_summary.json", run_summary)
    _write_json_artifact(output_dir / "metrics.json", metrics)
    _write_json_artifact(output_dir / "diagnostics.json", diagnostics)
    _write_json_artifact(output_dir / "pipeline_stage_trace.json", pipeline.last_stage_trace)
    if report is not None and not (output_dir / "report.md").exists():
        (output_dir / "report.md").write_text(report.content, encoding="utf-8")
    if report is not None and not (output_dir / "report_meta.json").exists():
        _write_json_artifact(
            output_dir / "report_meta.json",
            {
                "title": report.title,
                "global_tldr": report.metadata.get("global_tldr"),
                "metadata": report.metadata,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    return {
        "output_dir": str(output_dir),
        "raw_after_window_total": len(window_articles),
        "processed_total": len(processed_articles),
        "report_title": report.title if report is not None else "",
        "pipeline_mode_used": pipeline_mode_used,
        "report_provider_used": report_provider_used,
        "report_stage_error": report_stage_error,
        "last_completed_stage": last_completed_stage,
    }


def _force_pipeline_rule_mode(pipeline: ProcessingPipeline) -> None:
    pipeline.routing_profile.stages.filter.primary = "rule"
    pipeline.routing_profile.stages.filter.fallback = []
    pipeline.routing_profile.stages.keywords.primary = "rule"
    pipeline.routing_profile.stages.keywords.fallback = []


async def _main_async(args: argparse.Namespace) -> int:
    export_dir = Path(args.export_dir).expanduser().resolve()
    if not export_dir.exists():
        raise RuntimeError(f"export_dir not found: {export_dir}")
    run_summary_path = export_dir / "_run_summary.json"
    if not run_summary_path.exists():
        raise RuntimeError(f"missing _run_summary.json under: {export_dir}")

    run_summary = _load_json(run_summary_path)
    provider_overrides = await _resolve_provider_overrides(args.provider_overrides_json, run_summary)
    default_output_dir = export_dir / DEFAULT_OUTPUT_NAME / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else default_output_dir

    result = await _run_replay(
        export_dir=export_dir,
        output_dir=output_dir,
        routing_profile=args.routing_profile,
        provider_overrides=provider_overrides,
        run_report_rewrite=not args.skip_report_rewrite,
        max_articles=args.max_articles,
        pipeline_mode=args.pipeline_mode,
        fallback_rule_on_auth_error=bool(args.fallback_rule_on_auth_error),
        stage_concurrency=args.stage_concurrency,
        stop_after=args.stop_after,
        resume_from=args.resume_from,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay monitor after_window export through processing/report pipeline.")
    parser.add_argument("--export-dir", required=True, help="Path to exported monitor directory containing _run_summary.json")
    parser.add_argument(
        "--routing-profile",
        default=settings.routing_default_profile,
        help="Routing profile name (default: settings.routing_default_profile)",
    )
    parser.add_argument(
        "--provider-overrides-json",
        default=None,
        help="Provider overrides JSON string or JSON file path",
    )
    parser.add_argument(
        "--skip-report-rewrite",
        action="store_true",
        help="Skip report provider stage and keep renderer output",
    )
    parser.add_argument("--output-dir", default=None, help="Output directory (default: <export-dir>/_replay/<timestamp>)")
    parser.add_argument("--max-articles", type=int, default=None, help="Optional cap on replayed article count")
    parser.add_argument(
        "--stage-concurrency",
        type=int,
        default=1,
        help="Max concurrent items for replay keywords/event_extract stages (default: 1)",
    )
    parser.add_argument(
        "--pipeline-mode",
        choices=["routing", "rule"],
        default="routing",
        help="Pipeline provider mode: routing (default) or rule (offline/no-auth)",
    )
    parser.add_argument(
        "--fallback-rule-on-auth-error",
        action="store_true",
        help="When routing mode hits 401 auth error, retry once in rule mode",
    )
    parser.add_argument(
        "--stop-after",
        choices=["raw", "window", "filter", "keywords", "aggregate", "global_summary", "render", "report"],
        default=None,
        help="Stop replay after the selected stage and persist intermediate artifacts",
    )
    parser.add_argument(
        "--resume-from",
        choices=["raw", "window", "filter", "keywords", "aggregate", "global_summary", "render"],
        default=None,
        help="Resume replay from a previously persisted stage artifact under output-dir",
    )
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
