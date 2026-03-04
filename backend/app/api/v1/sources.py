"""信息源 API"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.source import Source
from app.models.task import CollectTask
from app.schemas.source import CategoryStats
from app.schemas.source import SampleArticle
from app.schemas.source import SourceCreate
from app.schemas.source import SourceResponse
from app.schemas.source import SourceTestResponse
from app.schemas.source import SourceUpdate
from app.collectors.registry import get_collector

router = APIRouter()


@router.get("", response_model=list[SourceResponse])
async def list_sources(category: str | None = None, db: AsyncSession = Depends(get_db)):
    """获取信息源列表，支持按分类筛选"""
    stmt = select(Source).order_by(Source.created_at.desc())
    if category:
        stmt = stmt.where(Source.category == category)
    result = await db.execute(stmt)
    sources = result.scalars().all()
    latest_tasks = await _latest_tasks_by_source(db, [item.id for item in sources])
    return [_to_source_response(source, latest_tasks.get(source.id)) for source in sources]


@router.get("/categories", response_model=list[CategoryStats])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """获取所有分类及其下信息源数量统计"""
    result = await db.execute(select(Source.category))
    counts: dict[str, int] = {}
    for (category,) in result.all():
        counts[category] = counts.get(category, 0) + 1
    return [CategoryStats(category=category, count=count) for category, count in sorted(counts.items())]


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: str, db: AsyncSession = Depends(get_db)):
    """获取单个信息源详情"""
    source = await db.get(Source, _parse_uuid(source_id))
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    latest_tasks = await _latest_tasks_by_source(db, [source.id])
    return _to_source_response(source, latest_tasks.get(source.id))


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(payload: SourceCreate, db: AsyncSession = Depends(get_db)):
    """新增信息源"""
    now = datetime.now(timezone.utc)
    source = Source(
        id=uuid.uuid4(),
        name=payload.name,
        category=payload.category,
        collect_method=payload.collect_method,
        config=payload.config,
        enabled=payload.enabled,
        created_at=now,
        updated_at=now,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return _to_source_response(source, None)


@router.post("/{source_id}/test", response_model=SourceTestResponse)
async def test_source(source_id: str, db: AsyncSession = Depends(get_db)):
    """测试信息源连接"""
    source = await db.get(Source, _parse_uuid(source_id))
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    try:
        collector = get_collector(source.collect_method)
        raw_articles = await collector.collect(source.config or {})
        
        sample = raw_articles[:3]
        sample_articles = [
            SampleArticle(
                title=a.title,
                url=a.url,
                published_at=a.published_at
            ) for a in sample
        ]
        
        return SourceTestResponse(
            success=True,
            message=f"Connection successful. Retrieved {len(raw_articles)} items.",
            sample_articles=sample_articles
        )
    except Exception as e:
        return SourceTestResponse(
            success=False,
            message=f"Test failed: {str(e)}",
            sample_articles=[]
        )


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(source_id: str, payload: SourceUpdate, db: AsyncSession = Depends(get_db)):
    """更新信息源"""
    source = await db.get(Source, _parse_uuid(source_id))
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    if payload.name is not None:
        source.name = payload.name
    if payload.config is not None:
        source.config = payload.config
    if payload.enabled is not None:
        source.enabled = payload.enabled
    source.updated_at = datetime.now(timezone.utc)

    db.add(source)
    await db.commit()
    await db.refresh(source)
    latest_tasks = await _latest_tasks_by_source(db, [source.id])
    return _to_source_response(source, latest_tasks.get(source.id))


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: str, db: AsyncSession = Depends(get_db)):
    """删除信息源"""
    source = await db.get(Source, _parse_uuid(source_id))
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    await db.delete(source)
    await db.commit()


def _status_from_task(task: CollectTask | None) -> str:
    if not task:
        return "healthy"
    if task.status == "running":
        return "running"
    if task.status == "failed":
        return "error"
    return "healthy"


async def _latest_tasks_by_source(
    db: AsyncSession, source_ids: list[uuid.UUID]
) -> dict[uuid.UUID, CollectTask]:
    if not source_ids:
        return {}
    stmt = (
        select(CollectTask)
        .where(CollectTask.source_id.is_not(None), CollectTask.source_id.in_(source_ids))
        .order_by(CollectTask.created_at.desc())
    )
    result = await db.execute(stmt)
    latest: dict[uuid.UUID, CollectTask] = {}
    for task in result.scalars().all():
        if task.source_id and task.source_id not in latest:
            latest[task.source_id] = task
    return latest


def _to_source_response(source: Source, latest_task: CollectTask | None) -> SourceResponse:
    return SourceResponse(
        id=source.id,
        name=source.name,
        category=source.category,
        collect_method=source.collect_method,
        config=source.config or {},
        enabled=source.enabled,
        status=_status_from_task(latest_task),  # type: ignore[arg-type]
        last_run=(
            latest_task.started_at
            if latest_task and latest_task.started_at
            else latest_task.created_at if latest_task else None
        ),
        last_collected=source.last_collected,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _parse_uuid(raw_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid UUID") from exc
