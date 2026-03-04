"""Export monitor source data to test_data with raw/after_window splits."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
import uuid

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DEFAULT_OUTPUT_BASE = REPO_ROOT / "test_data"

sys.path.insert(0, str(ROOT))

from app.models.database import async_session
from app.models.monitor import Monitor
from app.models.source import Source
from app.models.task import CollectTask
from app.scheduler.monitor_runner import (
    _filter_source_overrides_by_source_ids,
    _normalize_source_overrides,
    run_monitor_once,
)
from app.scheduler.orchestrator import Orchestrator


def _slug(value: str, max_len: int = 80) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9._-]+", "_", text)
    text = text.strip("._-")
    if not text:
        return "item"
    return text[:max_len]


def _to_iso(value: object) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _write_article_file(
    *,
    target_file: Path,
    title: str,
    url: str | None,
    external_id: str | None,
    published_at: object,
    source_name: str,
    source_id: uuid.UUID,
    extractor: str | None,
    content: str | None,
) -> None:
    header = [
        f"title: {title}",
        f"url: {url}",
        f"external_id: {external_id}",
        f"published_at: {_to_iso(published_at)}",
        f"source_name: {source_name}",
        f"source_id: {source_id}",
        f"extractor: {extractor}",
        "",
        "----- FULL CONTENT -----",
        "",
    ]
    target_file.write_text("\n".join(header) + (content or ""), encoding="utf-8")


async def _run_export(
    *,
    monitor_id: uuid.UUID,
    window_hours: int,
    output_base: Path,
    run_monitor: bool,
    trigger_type: str,
) -> dict:
    if window_hours < 1 or window_hours > 168:
        raise ValueError("window_hours must be in [1, 168]")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = output_base / f"monitor_{monitor_id}" / ts
    output_dir.mkdir(parents=True, exist_ok=True)

    async with async_session() as db:
        monitor = await db.get(Monitor, monitor_id)
        if monitor is None:
            raise RuntimeError(f"monitor not found: {monitor_id}")

        run_task: CollectTask | None = None
        if run_monitor:
            run_task = await run_monitor_once(
                db=db,
                monitor=monitor,
                trigger_type=trigger_type,
                window_hours_override=window_hours,
            )

        monitor_source_ids: list[uuid.UUID] = []
        for raw_id in monitor.source_ids or []:
            try:
                monitor_source_ids.append(uuid.UUID(str(raw_id)))
            except ValueError:
                continue

        source_rows = (
            await db.execute(select(Source).where(Source.id.in_(monitor_source_ids), Source.enabled.is_(True)))
        ).scalars().all()
        source_by_id = {row.id: row for row in source_rows}
        ordered_sources = [source_by_id[sid] for sid in monitor_source_ids if sid in source_by_id]

        source_overrides = _filter_source_overrides_by_source_ids(
            _normalize_source_overrides(monitor.source_overrides),
            [str(item.id) for item in ordered_sources],
        )

        orchestrator = Orchestrator(max_concurrency=5)
        window_end = datetime.now(timezone.utc)
        window_start = window_end - timedelta(hours=window_hours)

        collect_specs: list[tuple[Source, dict]] = []
        for source in ordered_sources:
            collect_config = orchestrator._resolve_source_config(source=source, source_overrides=source_overrides)
            collect_specs.append((source, collect_config))

        # Export phase should not duplicate serial bottlenecks:
        # collect all sources concurrently, then window-filter/write sequentially.
        collect_results = await asyncio.gather(
            *[
                orchestrator.collect_source(
                    source_id=str(source.id),
                    method=source.collect_method,
                    config=collect_config,
                )
                for source, collect_config in collect_specs
            ]
        )

        collected_by_source: dict[uuid.UUID, tuple[dict, list, list[dict]]] = {}
        for (source, collect_config), (raw_articles, collect_trace) in zip(collect_specs, collect_results):
            collected_by_source[source.id] = (collect_config, raw_articles, collect_trace)

        exported_sources: list[dict] = []
        for idx, source in enumerate(ordered_sources, start=1):
            source_dir = output_dir / f"{idx:02d}_{_slug(source.name)}_{str(source.id)[:8]}"
            raw_dir = source_dir / "raw"
            after_window_dir = source_dir / "after_window"
            raw_dir.mkdir(parents=True, exist_ok=True)
            after_window_dir.mkdir(parents=True, exist_ok=True)

            collect_config, raw_articles, collect_trace = collected_by_source[source.id]
            filtered_articles, filter_trace = await orchestrator._filter_raw_articles_by_window(
                db=db,
                source=source,
                raw_articles=raw_articles,
                window_start=window_start,
                window_end=window_end,
                window_hours=window_hours,
            )

            raw_manifest: list[dict] = []
            for j, raw in enumerate(raw_articles, start=1):
                title = raw.title or f"article_{j}"
                filename = f"{j:03d}_{_slug(title)}.txt"
                file_path = raw_dir / filename
                _write_article_file(
                    target_file=file_path,
                    title=title,
                    url=raw.url,
                    external_id=raw.external_id,
                    published_at=raw.published_at,
                    source_name=source.name,
                    source_id=source.id,
                    extractor=(raw.metadata or {}).get("extractor"),
                    content=raw.content,
                )
                raw_manifest.append(
                    {
                        "file": str(file_path.relative_to(output_dir)),
                        "title": title,
                        "url": raw.url,
                        "external_id": raw.external_id,
                        "published_at": _to_iso(raw.published_at),
                        "extractor": (raw.metadata or {}).get("extractor"),
                        "content_chars": len(raw.content or ""),
                    }
                )

            filtered_manifest: list[dict] = []
            for j, raw in enumerate(filtered_articles, start=1):
                title = raw.title or f"article_{j}"
                filename = f"{j:03d}_{_slug(title)}.txt"
                file_path = after_window_dir / filename
                _write_article_file(
                    target_file=file_path,
                    title=title,
                    url=raw.url,
                    external_id=raw.external_id,
                    published_at=raw.published_at,
                    source_name=source.name,
                    source_id=source.id,
                    extractor=(raw.metadata or {}).get("extractor"),
                    content=raw.content,
                )
                filtered_manifest.append(
                    {
                        "file": str(file_path.relative_to(output_dir)),
                        "title": title,
                        "url": raw.url,
                        "external_id": raw.external_id,
                        "published_at": _to_iso(raw.published_at),
                        "extractor": (raw.metadata or {}).get("extractor"),
                        "content_chars": len(raw.content or ""),
                    }
                )

            source_summary = {
                "source_id": str(source.id),
                "source_name": source.name,
                "collect_method": source.collect_method,
                "collect_config": collect_config,
                "collect_trace": collect_trace,
                "window_filter_trace": filter_trace,
                "raw_count": len(raw_articles),
                "after_window_count": len(filtered_articles),
                "raw_articles": raw_manifest,
                "after_window_articles": filtered_manifest,
            }
            (source_dir / "_summary.json").write_text(json.dumps(source_summary, ensure_ascii=False, indent=2), encoding="utf-8")
            exported_sources.append(
                {
                    "source_id": str(source.id),
                    "source_name": source.name,
                    "collect_method": source.collect_method,
                    "raw_count": len(raw_articles),
                    "after_window_count": len(filtered_articles),
                }
            )

        run_summary = {
            "monitor_id": str(monitor.id),
            "monitor_name": monitor.name,
            "window_hours": window_hours,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "trigger_type": trigger_type,
            "run_monitor": run_monitor,
            "run_task_id": str(run_task.id) if run_task else None,
            "run_id": str(run_task.run_id) if run_task else None,
            "run_status": run_task.status if run_task else None,
            "run_articles_count": int(run_task.articles_count or 0) if run_task else None,
            "output_dir": str(output_dir),
            "sources": exported_sources,
            "raw_total": sum(item["raw_count"] for item in exported_sources),
            "after_window_total": sum(item["after_window_count"] for item in exported_sources),
        }
        (output_dir / "_run_summary.json").write_text(json.dumps(run_summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return run_summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export monitor test data as raw + after_window sets.")
    parser.add_argument("--monitor-id", required=True, help="Monitor UUID")
    parser.add_argument("--window-hours", type=int, default=168, help="Window size in hours (1..168)")
    parser.add_argument("--output-base", default=str(DEFAULT_OUTPUT_BASE), help="Base output directory")
    parser.add_argument("--trigger-type", default="test", choices=["test", "manual"], help="Trigger type for run")
    parser.add_argument("--skip-run", action="store_true", help="Do not execute run_monitor_once before export")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    monitor_id = uuid.UUID(args.monitor_id)
    output_base = Path(args.output_base)
    summary = asyncio.run(
        _run_export(
            monitor_id=monitor_id,
            window_hours=args.window_hours,
            output_base=output_base,
            run_monitor=not args.skip_run,
            trigger_type=args.trigger_type,
        )
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
