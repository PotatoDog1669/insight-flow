"""信息源 API"""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.reddit_config import build_reddit_feed_url, normalize_reddit_subreddits
from app.models.database import get_db
from app.models.source import Source
from app.models.task import CollectTask
from app.schemas.source import CategoryStats
from app.schemas.source import SampleArticle
from app.schemas.source import SourceCreate
from app.schemas.source import SourceResponse
from app.schemas.source import SourceTestRequest
from app.schemas.source import SourceTestResponse
from app.schemas.source import SourceUpdate
from app.collectors.registry import get_collector
from app.collectors.site_profile_loader import load_site_profile

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
async def test_source(
    source_id: str,
    payload: SourceTestRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """测试信息源连接"""
    source = await db.get(Source, _parse_uuid(source_id))
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    try:
        collector = get_collector(source.collect_method)
        config = _resolve_source_test_config(source)
        is_academic_api_source = _is_academic_api_source(source=source, config=config)
        is_arxiv_source = _is_arxiv_source(source=source, config=config)
        requested_keywords = [item.strip() for item in (payload.keywords if payload else []) if item.strip()]
        if is_academic_api_source and requested_keywords:
            config["keywords"] = list(dict.fromkeys(requested_keywords))[:20]
        effective_max_results = None
        if is_academic_api_source:
            effective_max_results = _resolve_test_limit(config=config, requested_limit=payload.max_results if payload else None)
            config["max_results"] = effective_max_results
            if source.collect_method == "rss":
                config["max_items"] = effective_max_results
        if is_academic_api_source and payload:
            if payload.start_at is not None:
                config["start_at"] = payload.start_at.isoformat()
            if payload.end_at is not None:
                config["end_at"] = payload.end_at.isoformat()

        raw_articles = await collector.collect(config)
        filtered_articles = raw_articles
        fetched_count = None
        matched_count = None
        effective_keywords: list[str] = []
        window_start = None
        window_end = None

        if is_academic_api_source:
            fetched_count = len(raw_articles)
            window_start = payload.start_at if payload else None
            window_end = payload.end_at if payload else None
            effective_keywords = [
                item.strip()
                for item in (config.get("keywords") if isinstance(config.get("keywords"), list) else [])
                if isinstance(item, str) and item.strip()
            ]
            filtered_articles = _filter_articles_for_test_window(
                raw_articles=raw_articles,
                start_at=window_start,
                end_at=window_end,
            )
            matched_count = len(filtered_articles)

        sample_limit = effective_max_results if is_academic_api_source and isinstance(effective_max_results, int) else 3
        sample = filtered_articles[:sample_limit]
        sample_articles = [
            SampleArticle(
                title=a.title,
                url=a.url,
                published_at=a.published_at
            ) for a in sample
        ]

        return SourceTestResponse(
            success=True,
            message=(
                f"Fetched {fetched_count} items, matched {matched_count} items in the requested window."
                if is_academic_api_source
                else f"Connection successful. Retrieved {len(raw_articles)} items."
            ),
            fetched_count=fetched_count,
            matched_count=matched_count,
            effective_keywords=effective_keywords,
            effective_max_results=effective_max_results,
            window_start=window_start,
            window_end=window_end,
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
        target_url=_resolve_target_url(source.collect_method, source.config or {}),
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


def _resolve_target_url(collect_method: str, config: dict[str, Any]) -> str | None:
    if collect_method == "rss":
        for key in ("feed_url", "url", "rss_url"):
            value = config.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None

    if collect_method in {"openalex", "europe_pmc", "pubmed"}:
        base_url = config.get("base_url")
        if isinstance(base_url, str) and base_url.strip():
            return base_url
        return None

    if collect_method not in {"blog_scraper", "deepbrowse"}:
        return None

    profile = config.get("profile")
    if isinstance(profile, dict):
        start_urls = profile.get("start_urls")
        if isinstance(start_urls, list):
            for item in start_urls:
                if isinstance(item, str) and item.strip():
                    return item

    url = config.get("url")
    if isinstance(url, str) and url.strip():
        return url

    site_key = config.get("site_key")
    if not isinstance(site_key, str) or not site_key.strip():
        return None
    try:
        site_profile = load_site_profile(site_key)
    except (FileNotFoundError, ValueError):
        return None
    start_urls = site_profile.get("start_urls")
    if not isinstance(start_urls, list):
        return None
    for item in start_urls:
        if isinstance(item, str) and item.strip():
            return item
    return None


def _resolve_source_test_config(source: Source) -> dict[str, Any]:
    config = dict(source.config or {})
    if source.collect_method == "rss" and isinstance(config.get("subreddits"), list):
        subreddits = normalize_reddit_subreddits(config.get("subreddits"))
        if subreddits:
            config["subreddits"] = subreddits
        config["feed_url"] = build_reddit_feed_url(subreddits or config.get("subreddits"))
    return config


def _is_academic_api_source(*, source: Source, config: dict[str, Any]) -> bool:
    if source.category != "academic":
        return False
    if source.collect_method in {"openalex", "europe_pmc", "pubmed"}:
        return True
    return source.collect_method == "rss" and bool(config.get("arxiv_api"))


def _is_arxiv_source(*, source: Source, config: dict[str, Any]) -> bool:
    return (
        source.category == "academic"
        and source.collect_method == "rss"
        and bool(config.get("arxiv_api"))
    )


def _filter_articles_for_test_window(
    *,
    raw_articles: list[Any],
    start_at: datetime | None,
    end_at: datetime | None,
) -> list[Any]:
    if start_at is None and end_at is None:
        return raw_articles

    filtered: list[Any] = []
    for item in raw_articles:
        published_at = item.published_at
        if not isinstance(published_at, datetime):
            continue
        if start_at is not None and published_at < start_at:
            continue
        if end_at is not None and published_at > end_at:
            continue
        filtered.append(item)
    return filtered


def _resolve_test_limit(*, config: dict[str, Any], requested_limit: int | None) -> int:
    candidates = [
        requested_limit,
        config.get("max_results"),
        config.get("max_items"),
    ]
    for candidate in candidates:
        if isinstance(candidate, int) and 1 <= candidate <= 200:
            return candidate
        if isinstance(candidate, str):
            value = candidate.strip()
            if value.isdigit():
                normalized = int(value)
                if 1 <= normalized <= 200:
                    return normalized
    return 30
