"""监控任务（Monitors）API"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from pydantic import ValidationError
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import async_session, get_db
from app.models.monitor import Monitor
from app.models.task import CollectTask
from app.models.task_event import TaskEvent
from app.routing.loader import load_routing_profile
from app.scheduler.monitor_runner import execute_monitor_pipeline
from app.scheduler.monitor_runner import prepare_monitor_run
from app.scheduler.task_events import append_task_event
from app.schemas.monitor import MonitorAIRouting
from app.schemas.monitor import MonitorAIRoutingDefaultsResponse
from app.schemas.monitor import MonitorCreate
from app.schemas.monitor import MonitorRunCancelResponse
from app.schemas.monitor import MonitorRunRequest
from app.schemas.monitor import MonitorResponse
from app.schemas.monitor import MonitorRunResponse
from app.schemas.monitor import MonitorUpdate

logger = logging.getLogger(__name__)

async def _background_execute_monitor(
    monitor_id: uuid.UUID,
    task_id: uuid.UUID,
    trigger_type: str,
    window_hours_override: int | None,
):
    try:
        async with async_session() as db:
            monitor = await db.get(Monitor, monitor_id)
            task = await db.get(CollectTask, task_id)
            if not monitor or not task:
                logger.error("Monitor %s or Task %s not found for background execution.", monitor_id, task_id)
                return
            await execute_monitor_pipeline(
                db=db,
                monitor=monitor,
                task=task,
                trigger_type=trigger_type,
                window_hours_override=window_hours_override,
            )
    except Exception as exc:
        logger.exception("Failed background monitor execution for %s: %s", monitor_id, exc)

router = APIRouter()

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


@router.get("", response_model=list[MonitorResponse])
async def list_monitors(db: AsyncSession = Depends(get_db)):
    """获取当前用户监控任务列表（P0）"""
    result = await db.execute(select(Monitor).where(Monitor.user_id == DEFAULT_USER_ID).order_by(Monitor.created_at.desc()))
    monitors = result.scalars().all()
    return [_to_monitor_response(monitor) for monitor in monitors]


@router.post("", response_model=MonitorResponse, status_code=status.HTTP_201_CREATED)
async def create_monitor(payload: MonitorCreate, db: AsyncSession = Depends(get_db)):
    """创建监控任务（P0）"""
    now = datetime.now(timezone.utc)
    normalized_source_ids = [str(item) for item in payload.source_ids]
    monitor = Monitor(
        id=uuid.uuid4(),
        user_id=DEFAULT_USER_ID,
        name=payload.name,
        time_period=payload.time_period,
        report_type=_resolve_report_type(
            time_period=payload.time_period,
            requested_report_type=payload.report_type,
        ),
        source_ids=normalized_source_ids,
        source_overrides=_filter_source_overrides_by_source_ids(
            _normalize_source_overrides(payload.source_overrides),
            normalized_source_ids,
        ),
        ai_routing=_normalize_ai_routing(payload.ai_routing),
        destination_ids=payload.destination_ids or [],
        window_hours=payload.window_hours,
        custom_schedule=payload.custom_schedule,
        enabled=payload.enabled,
        last_run=None,
        created_at=now,
        updated_at=now,
    )
    db.add(monitor)
    await db.commit()
    await db.refresh(monitor)
    return _to_monitor_response(monitor)


@router.get("/ai-routing/defaults", response_model=MonitorAIRoutingDefaultsResponse)
async def get_monitor_ai_routing_defaults():
    profile = load_routing_profile(settings.routing_default_profile)
    return MonitorAIRoutingDefaultsResponse(
        profile_name=profile.name,
        stages={
            "filter": _resolve_default_stage_provider(
                candidate=profile.stages.filter.primary,
                allowed={"rule", "llm_openai", "llm_codex"},
                fallback="rule",
            ),
            "keywords": _resolve_default_stage_provider(
                candidate=profile.stages.keywords.primary,
                allowed={"rule", "llm_openai", "llm_codex"},
                fallback="rule",
            ),
            "global_summary": _resolve_default_stage_provider(
                candidate=(
                    profile.stages.global_summary.primary
                    if profile.stages.global_summary is not None
                    else profile.stages.report.primary
                ),
                allowed={"llm_openai", "llm_codex"},
                fallback="llm_openai",
            ),
            "report": _resolve_default_stage_provider(
                candidate=profile.stages.report.primary,
                allowed={"llm_openai", "llm_codex"},
                fallback="llm_openai",
            ),
        },
    )


@router.post("/{monitor_id}/run", response_model=MonitorRunResponse)
async def run_monitor(
    monitor_id: str,
    background_tasks: BackgroundTasks,
    payload: MonitorRunRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """手动触发指定监控任务（P0）"""
    monitor_uuid = _parse_uuid(monitor_id)
    monitor = await db.get(Monitor, monitor_uuid)
    if not monitor or monitor.user_id != DEFAULT_USER_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitor not found")

    try:
        task = await prepare_monitor_run(
            db=db,
            monitor=monitor,
            trigger_type="manual",
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Monitor prepare failed") from exc

    background_tasks.add_task(
        _background_execute_monitor,
        monitor_uuid,
        task.id,
        "manual",
        payload.window_hours if payload else None,
    )

    return MonitorRunResponse(task_id=task.id, run_id=task.run_id or task.id, status="running", monitor_id=monitor_uuid)


@router.get("/{monitor_id}/logs", response_model=list[dict])
async def get_monitor_logs(monitor_id: str, db: AsyncSession = Depends(get_db)):
    """获取监控任务的运行历史（P1 预留）"""
    monitor_uuid = _parse_uuid(monitor_id)
    monitor = await db.get(Monitor, monitor_uuid)
    if not monitor or monitor.user_id != DEFAULT_USER_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitor not found")

    stmt = (
        select(CollectTask)
        .where(CollectTask.monitor_id == monitor_uuid)
        .order_by(CollectTask.created_at.desc())
    )
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    # Reuse the TaskResponse structure from tasks.py conceptually
    logs: list[dict] = []
    for t in tasks:
        logs.append({
            "id": str(t.id),
            "run_id": str(t.run_id) if t.run_id else str(t.id),
            "source_id": str(t.source_id) if t.source_id else None,
            "trigger_type": t.trigger_type,
            "status": t.status,
            "articles_count": t.articles_count or 0,
            "stage_trace": t.stage_trace or [],
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "finished_at": t.finished_at.isoformat() if t.finished_at else None,
            "error_message": t.error_message,
        })
    return logs


@router.get("/{monitor_id}/runs", response_model=list[dict])
async def get_monitor_runs(monitor_id: str, limit: int = 30, db: AsyncSession = Depends(get_db)):
    """按时间倒序返回 monitor 的 run 摘要。"""
    monitor_uuid = _parse_uuid(monitor_id)
    monitor = await db.get(Monitor, monitor_uuid)
    if not monitor or monitor.user_id != DEFAULT_USER_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitor not found")

    normalized_limit = max(1, min(int(limit), 200))
    run_stmt = (
        select(CollectTask)
        .where(CollectTask.monitor_id == monitor_uuid, CollectTask.source_id.is_(None))
        .order_by(CollectTask.created_at.desc())
        .limit(normalized_limit)
    )
    run_rows = (await db.execute(run_stmt)).scalars().all()
    if not run_rows:
        return []

    run_ids = [row.run_id or row.id for row in run_rows]
    source_stmt = select(CollectTask).where(
        CollectTask.monitor_id == monitor_uuid,
        CollectTask.source_id.is_not(None),
        CollectTask.run_id.in_(run_ids),
    )
    source_rows = (await db.execute(source_stmt)).scalars().all()
    by_run: dict[uuid.UUID, list[CollectTask]] = {}
    for item in source_rows:
        if not item.run_id:
            continue
        by_run.setdefault(item.run_id, []).append(item)

    runs: list[dict] = []
    for run_task in run_rows:
        current_run_id = run_task.run_id or run_task.id
        source_tasks = by_run.get(current_run_id, [])
        total_sources = len(source_tasks)
        done_sources = sum(1 for task in source_tasks if task.status in {"success", "failed", "partial_success", "cancelled"})
        failed_sources = sum(1 for task in source_tasks if task.status == "failed")
        runs.append(
            {
                "run_id": str(current_run_id),
                "task_id": str(run_task.id),
                "trigger_type": run_task.trigger_type,
                "status": run_task.status,
                "articles_count": int(run_task.articles_count or 0),
                "source_total": total_sources,
                "source_done": done_sources,
                "source_failed": failed_sources,
                "created_at": run_task.created_at.isoformat() if run_task.created_at else None,
                "started_at": run_task.started_at.isoformat() if run_task.started_at else None,
                "finished_at": run_task.finished_at.isoformat() if run_task.finished_at else None,
                "error_message": run_task.error_message,
            }
        )
    return runs


@router.post("/{monitor_id}/runs/{run_id}/cancel", response_model=MonitorRunCancelResponse)
async def cancel_monitor_run(monitor_id: str, run_id: str, db: AsyncSession = Depends(get_db)):
    """请求取消单次 run。"""
    monitor_uuid = _parse_uuid(monitor_id)
    run_uuid = _parse_uuid(run_id)
    monitor = await db.get(Monitor, monitor_uuid)
    if not monitor or monitor.user_id != DEFAULT_USER_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitor not found")

    task_stmt = (
        select(CollectTask)
        .where(
            CollectTask.monitor_id == monitor_uuid,
            CollectTask.source_id.is_(None),
            or_(CollectTask.run_id == run_uuid, CollectTask.id == run_uuid),
        )
        .limit(1)
    )
    run_task = (await db.execute(task_stmt)).scalar_one_or_none()
    if run_task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    effective_run_id = run_task.run_id or run_task.id
    terminal_statuses = {"success", "failed", "partial_success", "cancelled"}
    if run_task.status not in terminal_statuses and run_task.status != "cancelling":
        previous_status = run_task.status
        run_task.status = "cancelling"
        db.add(run_task)
        await append_task_event(
            db,
            run_id=effective_run_id,
            monitor_id=monitor_uuid,
            task_id=run_task.id,
            source_id=None,
            stage="monitor_run",
            event_type="run_cancel_requested",
            message="Run cancellation requested by user",
            payload={"previous_status": previous_status},
        )
        await db.commit()
    elif run_task.status == "cancelling":
        await db.commit()

    return MonitorRunCancelResponse(run_id=effective_run_id, monitor_id=monitor_uuid, status=run_task.status)


@router.get("/{monitor_id}/runs/{run_id}/events", response_model=list[dict])
async def get_monitor_run_events(monitor_id: str, run_id: str, db: AsyncSession = Depends(get_db)):
    """返回单次 run 的完整事件流（时间升序）。"""
    monitor_uuid = _parse_uuid(monitor_id)
    run_uuid = _parse_uuid(run_id)
    monitor = await db.get(Monitor, monitor_uuid)
    if not monitor or monitor.user_id != DEFAULT_USER_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitor not found")

    task_stmt = (
        select(CollectTask)
        .where(
            CollectTask.monitor_id == monitor_uuid,
            CollectTask.source_id.is_(None),
            or_(CollectTask.run_id == run_uuid, CollectTask.id == run_uuid),
        )
        .limit(1)
    )
    run_task = (await db.execute(task_stmt)).scalar_one_or_none()
    if run_task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    effective_run_id = run_task.run_id or run_task.id
    event_stmt = (
        select(TaskEvent)
        .where(and_(TaskEvent.monitor_id == monitor_uuid, TaskEvent.run_id == effective_run_id))
        .order_by(TaskEvent.created_at.asc(), TaskEvent.id.asc())
    )
    events = (await db.execute(event_stmt)).scalars().all()
    return [
        {
            "id": str(item.id),
            "run_id": str(item.run_id),
            "task_id": str(item.task_id) if item.task_id else None,
            "source_id": str(item.source_id) if item.source_id else None,
            "stage": item.stage,
            "level": item.level,
            "event_type": item.event_type,
            "message": item.message,
            "payload": item.payload or {},
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in events
    ]


@router.patch("/{monitor_id}", response_model=MonitorResponse)
async def update_monitor(monitor_id: str, payload: MonitorUpdate, db: AsyncSession = Depends(get_db)):
    """更新监控任务（P1 预留）"""
    monitor_uuid = _parse_uuid(monitor_id)
    monitor = await db.get(Monitor, monitor_uuid)
    if not monitor or monitor.user_id != DEFAULT_USER_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitor not found")

    if payload.name is not None:
        monitor.name = payload.name
    if payload.time_period is not None:
        monitor.time_period = payload.time_period
    if payload.source_ids is not None:
        monitor.source_ids = [str(item) for item in payload.source_ids]
        monitor.source_overrides = _filter_source_overrides_by_source_ids(
            _normalize_source_overrides(monitor.source_overrides),
            monitor.source_ids or [],
        )
    if payload.source_overrides is not None:
        active_source_ids = monitor.source_ids or []
        monitor.source_overrides = _filter_source_overrides_by_source_ids(
            _normalize_source_overrides(payload.source_overrides),
            active_source_ids,
        )
    if "ai_routing" in payload.model_fields_set:
        monitor.ai_routing = _normalize_ai_routing(payload.ai_routing)
    if payload.destination_ids is not None:
        monitor.destination_ids = payload.destination_ids
    if payload.window_hours is not None:
        monitor.window_hours = payload.window_hours
    if payload.custom_schedule is not None:
        monitor.custom_schedule = payload.custom_schedule
    if payload.enabled is not None:
        monitor.enabled = payload.enabled
    monitor.report_type = _resolve_report_type(
        time_period=monitor.time_period,
        requested_report_type=payload.report_type,
        existing_report_type=monitor.report_type,
    )
    monitor.updated_at = datetime.now(timezone.utc)

    db.add(monitor)
    await db.commit()
    await db.refresh(monitor)
    return _to_monitor_response(monitor)


@router.delete("/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitor(monitor_id: str, db: AsyncSession = Depends(get_db)):
    """删除监控任务（P1 预留）"""
    monitor_uuid = _parse_uuid(monitor_id)
    monitor = await db.get(Monitor, monitor_uuid)
    if not monitor or monitor.user_id != DEFAULT_USER_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitor not found")
    await db.delete(monitor)
    await db.commit()


def _parse_uuid(raw_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid UUID") from exc


def _to_monitor_response(monitor: Monitor) -> MonitorResponse:
    return MonitorResponse(
        id=monitor.id,
        name=monitor.name,
        time_period=monitor.time_period,  # type: ignore[arg-type]
        report_type=monitor.report_type,  # type: ignore[arg-type]
        source_ids=[uuid.UUID(item) for item in (monitor.source_ids or [])],
        source_overrides=_normalize_source_overrides(monitor.source_overrides),
        ai_routing=_safe_ai_routing(monitor.ai_routing),
        destination_ids=[str(item) for item in (monitor.destination_ids or [])],
        window_hours=monitor.window_hours,
        custom_schedule=monitor.custom_schedule,
        enabled=monitor.enabled,
        status="active" if monitor.enabled else "paused",
        last_run=monitor.last_run,
        created_at=monitor.created_at,
        updated_at=monitor.updated_at,
    )


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

        if cleaned:
            normalized[source_id] = cleaned
    return normalized


def _filter_source_overrides_by_source_ids(payload: dict[str, dict], source_ids: list[str]) -> dict[str, dict]:
    if not payload:
        return {}
    allowed_ids = set(source_ids)
    return {source_id: config for source_id, config in payload.items() if source_id in allowed_ids}


def _normalize_ai_routing(payload: MonitorAIRouting | dict | None) -> dict:
    if payload is None:
        return {}
    if isinstance(payload, MonitorAIRouting):
        return payload.model_dump(exclude_none=True)
    if not isinstance(payload, dict):
        return {}
    try:
        return MonitorAIRouting.model_validate(payload).model_dump(exclude_none=True)
    except ValidationError:
        return {}


def _safe_ai_routing(payload: dict | None) -> MonitorAIRouting:
    if not isinstance(payload, dict):
        return MonitorAIRouting()
    try:
        return MonitorAIRouting.model_validate(payload)
    except ValidationError:
        return MonitorAIRouting()


def _resolve_report_type(
    *,
    time_period: str,
    requested_report_type: str | None,
    existing_report_type: str | None = None,
) -> str:
    if time_period == "daily":
        return "daily"
    if time_period == "weekly":
        return "weekly"

    if requested_report_type:
        return requested_report_type
    if existing_report_type:
        return existing_report_type

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="report_type is required when time_period is custom",
    )


def _resolve_default_stage_provider(*, candidate: str, allowed: set[str], fallback: str) -> str:
    normalized = str(candidate or "").strip()
    if normalized in allowed:
        return normalized
    return fallback
