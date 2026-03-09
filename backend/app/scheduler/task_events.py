"""Task event append + retention helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import uuid
from zoneinfo import ZoneInfo

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PROJECT_ROOT
from app.models.task_event import TaskEvent

logger = logging.getLogger(__name__)
TASK_EVENT_LOG_DIR = PROJECT_ROOT / "output" / "logs"
BEIJING_TZ = ZoneInfo("Asia/Shanghai")
_RUN_LOG_STEM_CACHE: dict[uuid.UUID, str] = {}
_RUN_LOG_STEM_RESERVED: set[str] = set()


async def append_task_event(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    monitor_id: uuid.UUID | None,
    task_id: uuid.UUID | None,
    source_id: uuid.UUID | None,
    stage: str,
    event_type: str,
    message: str,
    level: str = "info",
    payload: dict | None = None,
) -> None:
    event_record = {
        "created_at": datetime.now(BEIJING_TZ).isoformat(),
        "run_id": str(run_id),
        "monitor_id": str(monitor_id) if monitor_id else None,
        "task_id": str(task_id) if task_id else None,
        "source_id": str(source_id) if source_id else None,
        "stage": stage,
        "level": level,
        "event_type": event_type,
        "message": message[:2000],
        "payload": payload or {},
    }
    db.add(
        TaskEvent(
            id=uuid.uuid4(),
            run_id=run_id,
            monitor_id=monitor_id,
            task_id=task_id,
            source_id=source_id,
            stage=stage,
            level=level,
            event_type=event_type,
            message=event_record["message"],
            payload=event_record["payload"],
        )
    )
    _append_task_event_file(run_id=run_id, event_record=event_record)


async def cleanup_expired_task_events(db: AsyncSession, *, retention_days: int = 7) -> int:
    days = max(int(retention_days), 1)
    threshold = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = delete(TaskEvent).where(TaskEvent.created_at < threshold)
    result = await db.execute(stmt)
    await db.commit()
    return int(result.rowcount or 0)


def _append_task_event_file(*, run_id: uuid.UUID, event_record: dict) -> None:
    try:
        TASK_EVENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("task_event_log_dir_create_failed: run_id=%s error=%s", run_id, exc)
        return
    created_at = str(event_record.get("created_at") or "")
    _append_jsonl_log_line(
        path=_run_log_path(run_id=run_id, created_at=created_at), event_record=event_record, run_id=run_id
    )
    _append_human_log_line(
        path=_run_human_log_path(run_id=run_id, created_at=created_at), event_record=event_record, run_id=run_id
    )


def _append_jsonl_log_line(*, path: Path, event_record: dict, run_id: uuid.UUID) -> None:
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event_record, ensure_ascii=False))
            handle.write("\n")
    except OSError as exc:
        logger.warning("task_event_jsonl_write_failed: run_id=%s error=%s", run_id, exc)


def _append_human_log_line(*, path: Path, event_record: dict, run_id: uuid.UUID) -> None:
    line = _format_human_event_line(event_record=event_record)
    context_line = _format_human_context_line(event_record=event_record)
    try:
        should_write_context = not path.exists() or path.stat().st_size == 0
        with path.open("a", encoding="utf-8") as handle:
            if should_write_context:
                handle.write(context_line)
                handle.write("\n")
            handle.write(line)
            handle.write("\n")
    except OSError as exc:
        logger.warning("task_event_human_log_write_failed: run_id=%s error=%s", run_id, exc)


def _format_human_event_line(*, event_record: dict) -> str:
    created_at = str(event_record.get("created_at") or "-")
    level = str(event_record.get("level") or "info").upper()
    stage = str(event_record.get("stage") or "-")
    event_type = str(event_record.get("event_type") or "-")
    message = _compact_json(value=str(event_record.get("message") or ""))
    payload = event_record.get("payload")
    payload_text = _compact_json(value=payload if isinstance(payload, dict) else {})
    return (
        f"{created_at} {level:<5} stage={stage} event={event_type} "
        f"message={message} payload={payload_text}"
    )


def _compact_json(*, value: object, max_chars: int = 4000) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(serialized) <= max_chars:
        return serialized
    keep = max(max_chars - 14, 16)
    return f"{serialized[:keep]}...(truncated)"


def _format_human_context_line(*, event_record: dict) -> str:
    run_id = str(event_record.get("run_id") or "-")
    monitor_id = str(event_record.get("monitor_id") or "-")
    task_id = str(event_record.get("task_id") or "-")
    source_id = str(event_record.get("source_id") or "-")
    return f"context run={run_id} monitor={monitor_id} task={task_id} source={source_id}"


def _run_human_log_path(*, run_id: uuid.UUID, created_at: str) -> Path:
    return TASK_EVENT_LOG_DIR / f"{_run_log_stem(run_id=run_id, created_at=created_at)}.log"


def _run_log_path(*, run_id: uuid.UUID, created_at: str) -> Path:
    return TASK_EVENT_LOG_DIR / f"{_run_log_stem(run_id=run_id, created_at=created_at)}.jsonl"


def _run_log_stem(*, run_id: uuid.UUID, created_at: str) -> str:
    cached = _RUN_LOG_STEM_CACHE.get(run_id)
    if cached:
        return cached
    base_stem = f"run_{_timestamp_token(created_at=created_at)}"
    stem = base_stem
    suffix = 1
    while stem in _RUN_LOG_STEM_RESERVED:
        suffix += 1
        stem = f"{base_stem}_{suffix}"
    _RUN_LOG_STEM_CACHE[run_id] = stem
    _RUN_LOG_STEM_RESERVED.add(stem)
    return stem


def _timestamp_token(*, created_at: str) -> str:
    try:
        dt = datetime.fromisoformat(created_at)
    except ValueError:
        dt = datetime.now(BEIJING_TZ)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BEIJING_TZ)
    return dt.astimezone(BEIJING_TZ).strftime("%Y%m%d_%H%M%S_%f")
