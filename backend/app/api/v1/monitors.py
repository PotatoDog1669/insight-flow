"""监控任务（Monitors）API"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.monitor import Monitor
from app.models.task import CollectTask
from app.schemas.monitor import MonitorCreate
from app.schemas.monitor import MonitorResponse
from app.schemas.monitor import MonitorRunResponse
from app.schemas.monitor import MonitorUpdate

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
    monitor = Monitor(
        id=uuid.uuid4(),
        user_id=DEFAULT_USER_ID,
        name=payload.name,
        time_period=payload.time_period,
        depth=payload.depth,
        source_ids=[str(item) for item in payload.source_ids],
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


@router.post("/{monitor_id}/run", response_model=MonitorRunResponse)
async def run_monitor(monitor_id: str, db: AsyncSession = Depends(get_db)):
    """手动触发指定监控任务（P0）"""
    monitor_uuid = _parse_uuid(monitor_id)
    monitor = await db.get(Monitor, monitor_uuid)
    if not monitor or monitor.user_id != DEFAULT_USER_ID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitor not found")

    now = datetime.now(timezone.utc)
    monitor.last_run = now
    monitor.updated_at = now

    task = CollectTask(
        id=uuid.uuid4(),
        source_id=uuid.UUID(monitor.source_ids[0]) if monitor.source_ids else None,
        trigger_type="manual",
        status="pending",
        created_at=now,
    )
    db.add(monitor)
    db.add(task)
    await db.commit()
    return MonitorRunResponse(task_id=task.id, status="pending", monitor_id=monitor_uuid)


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
    if payload.depth is not None:
        monitor.depth = payload.depth
    if payload.source_ids is not None:
        monitor.source_ids = [str(item) for item in payload.source_ids]
    if payload.custom_schedule is not None:
        monitor.custom_schedule = payload.custom_schedule
    if payload.enabled is not None:
        monitor.enabled = payload.enabled
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
        depth=monitor.depth,  # type: ignore[arg-type]
        source_ids=[uuid.UUID(item) for item in (monitor.source_ids or [])],
        custom_schedule=monitor.custom_schedule,
        enabled=monitor.enabled,
        status="active" if monitor.enabled else "paused",
        last_run=monitor.last_run,
        created_at=monitor.created_at,
        updated_at=monitor.updated_at,
    )
