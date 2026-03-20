"""Persistence helpers for converted paper contents."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper, PaperContent


async def create_paper_content(
    session: AsyncSession,
    *,
    paper_id: uuid.UUID,
    asset_id: uuid.UUID | None,
    content_tier: str,
    markdown_content: str | None,
    plain_text: str | None,
    converter_name: str | None,
    quality_score: float | None,
    extraction_status: str,
) -> PaperContent:
    content = PaperContent(
        id=uuid.uuid4(),
        paper_id=paper_id,
        asset_id=asset_id,
        content_tier=content_tier,
        markdown_content=markdown_content,
        plain_text=plain_text,
        converter_name=converter_name,
        quality_score=quality_score,
        extraction_status=extraction_status,
    )
    session.add(content)
    await session.flush()
    return content


async def refresh_best_content(session: AsyncSession, paper_id: uuid.UUID) -> Paper | None:
    paper = await session.get(Paper, paper_id)
    if paper is None:
        return None

    stmt = select(PaperContent).where(PaperContent.paper_id == paper_id, PaperContent.extraction_status == "success")
    contents = (await session.execute(stmt)).scalars().all()
    if not contents:
        return paper

    best = max(contents, key=_content_rank)
    paper.best_content_id = best.id
    paper.fulltext_status = "converted"
    await session.flush()
    return paper


def _content_rank(content: PaperContent) -> tuple[int, float]:
    tier_rank = {"abstract": 0, "partial_fulltext": 1, "fulltext": 2}
    return (tier_rank.get(content.content_tier, -1), float(content.quality_score or 0.0))
