"""采集任务管理 API"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.source import Source
from app.models.task import CollectTask

router = APIRouter()


class TaskResponse(BaseModel):
    id: str
    source_id: str | None = None
    trigger_type: str
    status: str
    articles_count: int = 0

    model_config = {"from_attributes": True}


class TriggerRequest(BaseModel):
    source_id: str | None = None
    category: str | None = None


@router.get("", response_model=list[TaskResponse])
async def list_tasks(category: str | None = None, db: AsyncSession = Depends(get_db)):
    """查看采集任务历史"""
    if category:
        stmt = (
            select(CollectTask)
            .join(Source, Source.id == CollectTask.source_id)
            .where(Source.category == category)
            .order_by(CollectTask.created_at.desc())
        )
    else:
        stmt = select(CollectTask).order_by(CollectTask.created_at.desc())
    result = await db.execute(stmt)
    return [_to_task_response(task) for task in result.scalars().all()]


@router.post("/trigger", response_model=TaskResponse)
async def trigger_collect(request: TriggerRequest, db: AsyncSession = Depends(get_db)):
    """手动触发采集"""
    source_uuid: uuid.UUID | None = None
    if request.source_id:
        source_uuid = _parse_uuid(request.source_id)
        source = await db.get(Source, source_uuid)
        if not source:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    elif request.category:
        source_stmt = (
            select(Source)
            .where(Source.category == request.category, Source.enabled.is_(True))
            .order_by(Source.updated_at.desc())
            .limit(1)
        )
        source_result = await db.execute(source_stmt)
        source = source_result.scalar_one_or_none()
        if source:
            source_uuid = source.id

    task = CollectTask(
        id=uuid.uuid4(),
        source_id=source_uuid,
        trigger_type="manual",
        status="pending",
        started_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return _to_task_response(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """查看单个任务状态"""
    task = await db.get(CollectTask, _parse_uuid(task_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return _to_task_response(task)


def _parse_uuid(raw_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid UUID") from exc


def _to_task_response(task: CollectTask) -> TaskResponse:
    return TaskResponse(
        id=str(task.id),
        source_id=str(task.source_id) if task.source_id else None,
        trigger_type=task.trigger_type,
        status=task.status,
        articles_count=task.articles_count or 0,
    )
