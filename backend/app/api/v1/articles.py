"""文章查询 API"""

import uuid
from datetime import date

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.database import get_db
from app.models.report import Report
from app.models.source import Source
from app.schemas.article import ArticleResponse

router = APIRouter()


@router.get("", response_model=list[ArticleResponse])
async def list_articles(
    category: str | None = None,
    source_id: str | None = None,
    report_date: str | None = Query(default=None, alias="date"),
    min_score: float | None = None,
    keyword: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """查询文章，支持按分类/日期/评分等过滤"""
    stmt = select(Article, Source).join(Source, Article.source_id == Source.id).order_by(Article.collected_at.desc())
    if category:
        stmt = stmt.where(Source.category == category)
    if source_id:
        stmt = stmt.where(Article.source_id == _parse_uuid(source_id))
    if min_score is not None:
        stmt = stmt.where(Article.ai_score.is_not(None), Article.ai_score >= min_score)
    if status:
        stmt = stmt.where(Article.status == status)
    result = await db.execute(stmt)
    rows = result.all()
    items: list[tuple[Article, Source]] = []
    parsed_date = _parse_date(report_date) if report_date else None
    for article, source in rows:
        article_keywords = [str(item) for item in (article.keywords or [])]
        if keyword and keyword not in article_keywords:
            continue
        if parsed_date and article.collected_at.date() != parsed_date:
            continue
        items.append((article, source))

    start = (page - 1) * page_size
    end = start + page_size
    paged = items[start:end]
    report_map = await _build_report_map(db, [article.id for article, _ in paged])
    return [
        _to_article_response(article=article, source=source, report_ids=report_map.get(article.id, []))
        for article, source in paged
    ]


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: str, db: AsyncSession = Depends(get_db)):
    """查看单篇文章详情以及关联报告"""
    article_uuid = _parse_uuid(article_id)
    result = await db.execute(select(Article, Source).join(Source, Article.source_id == Source.id).where(Article.id == article_uuid))
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    article, source = row
    report_map = await _build_report_map(db, [article.id])
    return _to_article_response(article=article, source=source, report_ids=report_map.get(article.id, []))


async def _build_report_map(db: AsyncSession, article_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[uuid.UUID]]:
    if not article_ids:
        return {}
    result = await db.execute(select(Report.id, Report.article_ids))
    mapping: dict[uuid.UUID, list[uuid.UUID]] = {article_id: [] for article_id in article_ids}
    for report_id, report_article_ids in result.all():
        for raw_article_id in report_article_ids or []:
            normalized = raw_article_id if isinstance(raw_article_id, uuid.UUID) else _try_uuid(str(raw_article_id))
            if normalized and normalized in mapping:
                mapping[normalized].append(report_id)
    return mapping


def _to_article_response(article: Article, source: Source, report_ids: list[uuid.UUID]) -> ArticleResponse:
    return ArticleResponse(
        id=article.id,
        source_id=article.source_id,
        source_name=source.name,
        category=source.category,
        title=article.title,
        url=article.url,
        summary=article.summary,
        keywords=[str(item) for item in (article.keywords or [])],
        ai_score=article.ai_score,
        status=article.status,
        source_type=article.source_type,
        report_ids=report_ids,
        published_at=article.published_at,
        collected_at=article.collected_at,
        created_at=article.created_at,
    )


def _parse_uuid(raw_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid UUID") from exc


def _try_uuid(raw_id: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(raw_id)
    except ValueError:
        return None


def _parse_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid date, expected YYYY-MM-DD") from exc
