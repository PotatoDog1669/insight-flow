"""Task event append + retention helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_event import TaskEvent


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
            message=message[:2000],
            payload=payload or {},
        )
    )


async def cleanup_expired_task_events(db: AsyncSession, *, retention_days: int = 7) -> int:
    days = max(int(retention_days), 1)
    threshold = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = delete(TaskEvent).where(TaskEvent.created_at < threshold)
    result = await db.execute(stmt)
    await db.commit()
    return int(result.rowcount or 0)
