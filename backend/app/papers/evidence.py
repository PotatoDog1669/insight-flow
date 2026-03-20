"""Evidence coverage helpers for paper-centric analysis logs."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.paper import PaperContent


async def build_evidence_coverage(
    session: AsyncSession,
    article_ids: list[uuid.UUID] | list[str],
) -> dict[str, int | float]:
    normalized_ids = [_coerce_uuid(item) for item in article_ids]
    normalized_ids = [item for item in normalized_ids if item is not None]
    if not normalized_ids:
        return _empty_coverage()

    stmt = select(Article).where(Article.id.in_(normalized_ids))
    articles = (await session.execute(stmt)).scalars().all()
    if not articles:
        return _empty_coverage()

    paper_ids = sorted({article.paper_id for article in articles if article.paper_id is not None}, key=str)
    content_by_paper: dict[uuid.UUID, list[PaperContent]] = {}
    if paper_ids:
        content_stmt = select(PaperContent).where(
            PaperContent.paper_id.in_(paper_ids),
            PaperContent.extraction_status == "success",
        )
        contents = (await session.execute(content_stmt)).scalars().all()
        for content in contents:
            content_by_paper.setdefault(content.paper_id, []).append(content)

    buckets = {
        "papers_fulltext": 0,
        "papers_partial_fulltext": 0,
        "papers_abstract_only": 0,
        "papers_metadata_only": 0,
    }

    seen_papers: set[uuid.UUID] = set()
    for article in articles:
        if article.paper_id is None:
            bucket = _bucket_from_article(article.content_type)
            buckets[bucket] += 1
            continue
        if article.paper_id in seen_papers:
            continue
        seen_papers.add(article.paper_id)
        bucket = _bucket_from_paper_content(
            contents=content_by_paper.get(article.paper_id, []),
            fallback_content_type=article.content_type,
        )
        buckets[bucket] += 1

    total = sum(int(value) for value in buckets.values())
    return {
        "papers_total": total,
        **buckets,
        "fulltext_coverage_ratio": round((buckets["papers_fulltext"] / total) if total else 0.0, 4),
    }


def _bucket_from_paper_content(*, contents: list[PaperContent], fallback_content_type: str) -> str:
    best_rank = -1
    best_bucket = _bucket_from_article(fallback_content_type)
    for content in contents:
        bucket = _bucket_from_content_tier(content.content_tier)
        rank = _bucket_rank(bucket)
        if rank > best_rank:
            best_rank = rank
            best_bucket = bucket
    return best_bucket


def _bucket_from_content_tier(content_tier: str) -> str:
    mapping = {
        "fulltext": "papers_fulltext",
        "partial_fulltext": "papers_partial_fulltext",
        "abstract": "papers_abstract_only",
    }
    return mapping.get(str(content_tier or "").strip(), "papers_metadata_only")


def _bucket_from_article(content_type: str) -> str:
    mapping = {
        "fulltext": "papers_fulltext",
        "snippet": "papers_partial_fulltext",
        "abstract": "papers_abstract_only",
        "metadata": "papers_metadata_only",
    }
    return mapping.get(str(content_type or "").strip(), "papers_metadata_only")


def _bucket_rank(bucket: str) -> int:
    return {
        "papers_metadata_only": 0,
        "papers_abstract_only": 1,
        "papers_partial_fulltext": 2,
        "papers_fulltext": 3,
    }.get(bucket, -1)


def _coerce_uuid(value: uuid.UUID | str) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _empty_coverage() -> dict[str, int | float]:
    return {
        "papers_total": 0,
        "papers_fulltext": 0,
        "papers_partial_fulltext": 0,
        "papers_abstract_only": 0,
        "papers_metadata_only": 0,
        "fulltext_coverage_ratio": 0.0,
    }
