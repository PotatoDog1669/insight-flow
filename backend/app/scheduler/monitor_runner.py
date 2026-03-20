"""Monitor run execution helpers shared by API and scheduler."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.reddit_config import normalize_reddit_subreddits
from app.config import settings
from app.models.monitor import Monitor
from app.models.task import CollectTask
from app.scheduler.orchestrator import Orchestrator
from app.scheduler.task_events import append_task_event
from app.scheduler.task_events import cleanup_expired_task_events


def _format_error(exc: Exception, *, limit: int = 1000) -> str:
    message = str(exc).strip()
    if not message:
        message = type(exc).__name__
    return message[:limit]


async def prepare_monitor_run(
    *,
    db: AsyncSession,
    monitor: Monitor,
    trigger_type: str,
) -> CollectTask:
    """Prepare a monitor run and persist a monitor-level task record."""
    await cleanup_expired_task_events(db, retention_days=7)

    now = datetime.now(timezone.utc)
    monitor.last_run = now
    monitor.updated_at = now
    run_id = uuid.uuid4()
    normalized_trigger_type = "scheduled" if trigger_type == "scheduled" else "manual"

    task = CollectTask(
        id=uuid.uuid4(),
        run_id=run_id,
        monitor_id=monitor.id,
        source_id=None,
        trigger_type=normalized_trigger_type,
        status="running",
        started_at=now,
        created_at=now,
    )
    db.add(monitor)
    db.add(task)
    await db.commit()
    await append_task_event(
        db,
        run_id=run_id,
        monitor_id=monitor.id,
        task_id=task.id,
        source_id=None,
        stage="monitor_run",
        event_type="run_started",
        message=f"Monitor run started ({normalized_trigger_type})",
        payload={"trigger_type": normalized_trigger_type},
    )
    await db.commit()
    return task

async def execute_monitor_pipeline(
    *,
    db: AsyncSession,
    monitor: Monitor,
    task: CollectTask,
    trigger_type: str,
    window_hours_override: int | None = None,
) -> CollectTask:
    """Execute the pipeline of a prepared monitor run task."""
    normalized_trigger_type = "scheduled" if trigger_type == "scheduled" else "manual"
    run_id = task.run_id or task.id

    source_ids: list[uuid.UUID] = []
    for raw_source_id in monitor.source_ids or []:
        try:
            source_ids.append(uuid.UUID(str(raw_source_id)))
        except ValueError:
            continue

    destination_ids = _normalize_destination_ids(
        monitor.destination_instance_ids,
        monitor.destination_ids,
    )
    window_hours = _resolve_window_hours(monitor_window_hours=monitor.window_hours, override=window_hours_override)
    default_source_max_items = _resolve_default_source_max_items(monitor.time_period)
    source_overrides = _filter_source_overrides_by_source_ids(
        _normalize_source_overrides(monitor.source_overrides),
        [str(item) for item in source_ids],
    )

    orchestrator = Orchestrator(max_concurrency=settings.collector_max_concurrency)
    try:
        result = await orchestrator.run_daily_pipeline(
            db=db,
            user_id=monitor.user_id,
            trigger_type=normalized_trigger_type,
            run_id=run_id,
            monitor_id=monitor.id,
            monitor_task_id=task.id,
            source_ids=source_ids,
            destination_ids=destination_ids,
            source_overrides=source_overrides,
            default_source_max_items=default_source_max_items,
            report_type=monitor.report_type,
            window_hours=window_hours,
            monitor_ai_routing=monitor.ai_routing or {},
        )
        pipeline_status = str(result.get("status", "success"))
        if pipeline_status == "partial_success":
            task.status = "partial_success"
        elif pipeline_status == "cancelled":
            task.status = "cancelled"
        else:
            task.status = "success"
        task.articles_count = int(result.get("processed_articles", 0))
        task.finished_at = datetime.now(timezone.utc)
        task.stage_trace = _build_monitor_stage_trace(result)
        db.add(task)
        if task.status != "cancelled":
            await append_task_event(
                db,
                run_id=run_id,
                monitor_id=monitor.id,
                task_id=task.id,
                source_id=None,
                stage="monitor_run",
                event_type="run_completed",
                message="Monitor run completed",
                payload={
                    "status": task.status,
                    "processed_articles": int(result.get("processed_articles", 0)),
                    "reports_created": int(result.get("reports_created", 0)),
                },
            )
        await db.commit()
        return task
    except Exception as exc:
        error_text = _format_error(exc, limit=1000)
        task.status = "failed"
        task.finished_at = datetime.now(timezone.utc)
        task.error_message = error_text
        task.stage_trace = [
            {
                "stage": "monitor_run",
                "provider": "orchestrator",
                "status": "failed",
                "error": _format_error(exc, limit=300),
            }
        ]
        db.add(task)
        await append_task_event(
            db,
            run_id=run_id,
            monitor_id=monitor.id,
            task_id=task.id,
            source_id=None,
            stage="monitor_run",
            level="error",
            event_type="run_failed",
            message="Monitor run failed",
            payload={"error": error_text},
        )
        await db.commit()
        raise

async def run_monitor_once(
    *,
    db: AsyncSession,
    monitor: Monitor,
    trigger_type: str,
    window_hours_override: int | None = None,
) -> CollectTask:
    """Execute one monitor run and persist a monitor-level task record."""
    task = await prepare_monitor_run(db=db, monitor=monitor, trigger_type=trigger_type)
    return await execute_monitor_pipeline(
        db=db,
        monitor=monitor,
        task=task,
        trigger_type=trigger_type,
        window_hours_override=window_hours_override,
    )


def _normalize_destination_ids(destination_instance_ids: list | None, destination_ids: list | None) -> list[str]:
    normalized: list[str] = []
    raw_targets = destination_instance_ids or destination_ids or []
    for target in raw_targets:
        if isinstance(target, str) and target.strip():
            normalized.append(target.strip())
    if "database" not in normalized:
        normalized.insert(0, "database")
    return normalized


def _resolve_window_hours(*, monitor_window_hours: int | None, override: int | None) -> int:
    for candidate in (override, monitor_window_hours):
        if isinstance(candidate, int) and 1 <= candidate <= 168:
            return candidate
    return 24


def _resolve_default_source_max_items(time_period: str | None) -> int:
    return 5 if str(time_period or "").strip().lower() == "daily" else 20


def _build_monitor_stage_trace(result: dict) -> list[dict]:
    source_tasks = result.get("source_tasks", [])
    publish_reports = result.get("publish_reports", [])

    trace: list[dict] = [
        {
            "stage": "monitor_run",
            "provider": "orchestrator",
            "status": str(result.get("status", "success")),
            "sources": int(result.get("sources", 0)),
            "reports_created": int(result.get("reports_created", 0)),
            "articles": int(result.get("processed_articles", 0)),
            "window_hours": int(result.get("window_hours", 24)),
            "window_start": result.get("window_start"),
            "window_end": result.get("window_end"),
        }
    ]

    if isinstance(source_tasks, list):
        for source_task in source_tasks:
            if not isinstance(source_task, dict):
                continue
            source_id = source_task.get("source_id")
            source_trace = source_task.get("stage_trace") or []
            if not isinstance(source_trace, list):
                continue
            for event in source_trace:
                if not isinstance(event, dict):
                    continue
                trace.append({"scope": "source", "source_id": source_id, **event})

    if isinstance(publish_reports, list):
        for report in publish_reports:
            if not isinstance(report, dict):
                continue
            report_type = report.get("report_type")
            report_id = report.get("report_id")
            publish_trace = report.get("publish_trace") or []
            if not isinstance(publish_trace, list):
                continue
            for event in publish_trace:
                if not isinstance(event, dict):
                    continue
                trace.append({"scope": "report", "report_type": report_type, "report_id": report_id, **event})

    return trace


def _normalize_source_overrides(payload: dict | None) -> dict[str, dict]:
    if not isinstance(payload, dict):
        return {}

    normalized: dict[str, dict] = {}
    for raw_source_id, raw_config in payload.items():
        try:
            source_id = str(uuid.UUID(str(raw_source_id)))
        except ValueError:
            continue
        if not isinstance(raw_config, dict):
            continue

        cleaned: dict[str, object] = {}
        raw_max_items = raw_config.get("max_items")
        if isinstance(raw_max_items, str):
            raw_max_items = raw_max_items.strip()
            if raw_max_items.isdigit():
                raw_max_items = int(raw_max_items)
        if isinstance(raw_max_items, int) and 1 <= raw_max_items <= 200:
            cleaned["max_items"] = raw_max_items

        raw_limit = raw_config.get("limit")
        if isinstance(raw_limit, str):
            raw_limit = raw_limit.strip()
            if raw_limit.isdigit():
                raw_limit = int(raw_limit)
        if isinstance(raw_limit, int) and 1 <= raw_limit <= 200:
            cleaned["limit"] = raw_limit

        raw_max_results = raw_config.get("max_results")
        if isinstance(raw_max_results, str):
            raw_max_results = raw_max_results.strip()
            if raw_max_results.isdigit():
                raw_max_results = int(raw_max_results)
        if isinstance(raw_max_results, int) and 1 <= raw_max_results <= 200:
            cleaned["max_results"] = raw_max_results

        raw_keywords = raw_config.get("keywords")
        keywords: list[str] = []
        if isinstance(raw_keywords, str):
            keywords = [item.strip() for item in raw_keywords.split(",") if item.strip()]
        elif isinstance(raw_keywords, list):
            for item in raw_keywords:
                if not isinstance(item, str):
                    continue
                value = item.strip()
                if value:
                    keywords.append(value)
        if keywords:
            deduped = list(dict.fromkeys(keywords))
            cleaned["keywords"] = deduped[:20]

        usernames: list[str] = []
        raw_usernames = raw_config.get("usernames")
        if isinstance(raw_usernames, str):
            usernames = [item.strip() for item in raw_usernames.split(",") if item.strip()]
        elif isinstance(raw_usernames, list):
            for item in raw_usernames:
                if not isinstance(item, str):
                    continue
                value = item.strip()
                if value:
                    usernames.append(value)
        if usernames:
            cleaned["usernames"] = list(dict.fromkeys(usernames))

        subreddits = normalize_reddit_subreddits(raw_config.get("subreddits"))
        if subreddits:
            cleaned["subreddits"] = subreddits

        if cleaned:
            normalized[source_id] = cleaned
    return normalized


def _filter_source_overrides_by_source_ids(payload: dict[str, dict], source_ids: list[str]) -> dict[str, dict]:
    if not payload:
        return {}
    allowed_ids = set(source_ids)
    return {source_id: config for source_id, config in payload.items() if source_id in allowed_ids}
