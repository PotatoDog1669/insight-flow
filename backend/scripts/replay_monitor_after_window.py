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

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from app.collectors.base import RawArticle
from app.config import settings
from app.models.database import async_session
from app.models.source import Source
from app.processors.pipeline import ProcessedArticle, ProcessingPipeline
from app.providers.registry import get_provider
from app.renderers.base import RenderContext
from app.renderers.daily import DailyRenderer
from app.routing.loader import load_routing_profile
from app.routing.schema import StageRoute

FULL_CONTENT_MARKER = "----- FULL CONTENT -----"
DEFAULT_OUTPUT_NAME = "_replay"


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


def _fallback_category(collect_method: str) -> str:
    method = str(collect_method or "").strip().lower()
    if method in {"github_trending"}:
        return "open_source"
    if method in {"huggingface"}:
        return "academic"
    return "blog"


async def _load_source_categories(source_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not source_ids:
        return {}
    async with async_session() as session:
        rows = (await session.execute(select(Source.id, Source.category).where(Source.id.in_(source_ids)))).all()
    output: dict[uuid.UUID, str] = {}
    for source_id, category in rows:
        if isinstance(source_id, uuid.UUID) and isinstance(category, str):
            output[source_id] = category
    return output


def _iter_source_dirs(export_dir: Path) -> list[Path]:
    dirs = [
        item
        for item in export_dir.iterdir()
        if item.is_dir() and (item / "_summary.json").exists() and (item / "after_window").exists()
    ]
    return sorted(dirs, key=lambda item: item.name)


def _safe_str(value: object) -> str:
    return str(value or "").strip()


async def _collect_after_window_articles(
    *,
    export_dir: Path,
    run_summary: dict,
) -> tuple[list[RawArticle], dict[str, dict]]:
    source_dirs = _iter_source_dirs(export_dir)
    source_ids: list[uuid.UUID] = []
    source_summaries: list[tuple[Path, dict]] = []
    for source_dir in source_dirs:
        summary = _load_json(source_dir / "_summary.json")
        source_id_text = _safe_str(summary.get("source_id"))
        try:
            source_id = uuid.UUID(source_id_text)
        except ValueError:
            continue
        source_ids.append(source_id)
        source_summaries.append((source_dir, summary))

    try:
        category_map = await _load_source_categories(source_ids)
    except Exception:
        category_map = {}

    snapshot_fallback = _none_if_nullish(run_summary.get("window_end")) or datetime.now(timezone.utc).isoformat()
    raw_articles: list[RawArticle] = []
    per_source_stats: dict[str, dict] = {}

    for source_dir, summary in source_summaries:
        source_id_text = _safe_str(summary.get("source_id"))
        source_name = _safe_str(summary.get("source_name")) or source_dir.name
        collect_method = _safe_str(summary.get("collect_method"))
        source_uuid = uuid.UUID(source_id_text)
        source_category = category_map.get(source_uuid) or _fallback_category(collect_method)

        per_source_stats[source_id_text] = {
            "source_id": source_id_text,
            "source_name": source_name,
            "collect_method": collect_method,
            "source_category": source_category,
            "raw_after_window": 0,
            "processed": 0,
        }

        entries = summary.get("after_window_articles")
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
            files = sorted((source_dir / "after_window").glob("*.txt"))

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
            per_source_stats[source_id_text]["raw_after_window"] += 1

    return raw_articles, per_source_stats


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
    route: StageRoute,
    providers: dict[str, dict],
    provider_overrides: dict[str, dict],
    payload: dict,
) -> tuple[dict, str]:
    provider_chain = [route.primary, *(route.fallback or [])]
    last_exc: Exception | None = None
    for provider_name in provider_chain:
        config = _merge_provider_config(
            provider_name=provider_name,
            profile_config=providers.get(provider_name, {}),
            provider_overrides=provider_overrides,
        )
        max_retry = _max_retry(config)
        provider = get_provider(stage="report", name=provider_name)
        for _ in range(max_retry + 1):
            try:
                output = await provider.run(payload=payload, config=config)
                return output, provider_name
            except Exception as exc:  # pragma: no cover - network/runtime fallback
                last_exc = exc
                continue
    if last_exc:
        raise last_exc
    raise RuntimeError("report stage has no available provider")


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
) -> dict:
    run_summary = _load_json(export_dir / "_run_summary.json")
    raw_articles, source_stats = await _collect_after_window_articles(export_dir=export_dir, run_summary=run_summary)
    if max_articles is not None and max_articles > 0:
        raw_articles = raw_articles[:max_articles]

    pipeline = ProcessingPipeline(routing_profile=routing_profile)
    pipeline.set_provider_overrides(provider_overrides)
    pipeline_mode_used = pipeline_mode
    if pipeline_mode == "rule":
        _force_pipeline_rule_mode(pipeline)

    try:
        processed_articles = await pipeline.process(raw_articles)
    except Exception as exc:
        message = str(exc)
        if fallback_rule_on_auth_error and pipeline_mode != "rule" and "401" in message and "Unauthorized" in message:
            pipeline = ProcessingPipeline(routing_profile=routing_profile)
            pipeline.set_provider_overrides(provider_overrides)
            _force_pipeline_rule_mode(pipeline)
            pipeline_mode_used = "rule_fallback"
            processed_articles = await pipeline.process(raw_articles)
        else:
            raise
    renderer = DailyRenderer()

    report_date = datetime.now(timezone.utc).date().isoformat()
    window_end = _parse_iso_datetime(run_summary.get("window_end"))
    if window_end is not None:
        report_date = window_end.date().isoformat()
    report = await renderer.render(processed_articles, RenderContext(date=report_date))

    profile = load_routing_profile(routing_profile)
    report_provider_used = "daily_renderer"
    report_stage_error: str | None = None
    if run_report_rewrite:
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
        except Exception as exc:  # pragma: no cover - runtime fallback
            report_stage_error = str(exc)

    rendered_events = list(report.metadata.get("events") or [])
    diagnostics, processing_metrics = _build_diagnostics(
        raw_articles=raw_articles,
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
        "events": event_metrics,
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

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run_summary.json").write_text(json.dumps(run_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "diagnostics.json").write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "pipeline_stage_trace.json").write_text(
        json.dumps(pipeline.last_stage_trace, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(report.content, encoding="utf-8")
    (output_dir / "report_meta.json").write_text(
        json.dumps(
            {
                "title": report.title,
                "global_tldr": report.metadata.get("global_tldr"),
                "metadata": report.metadata,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "output_dir": str(output_dir),
        "raw_after_window_total": len(raw_articles),
        "processed_total": len(processed_articles),
        "report_title": report.title,
        "pipeline_mode_used": pipeline_mode_used,
        "report_provider_used": report_provider_used,
        "report_stage_error": report_stage_error,
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

    provider_overrides = _load_provider_overrides(args.provider_overrides_json)
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
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
