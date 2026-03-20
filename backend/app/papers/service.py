"""Services for linking source articles to canonical papers."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.paper import Paper, PaperIdentifier
from app.models.source import Source
from app.papers.normalization import (
    extract_identifier_candidates,
    infer_best_pdf_url,
    infer_first_author,
    infer_venue,
    infer_year,
    normalize_title,
    resolve_content_type,
)
from app.papers.resolver import resolve_existing_paper


async def sync_article_paper_link(session: AsyncSession, article: Article, source: Source) -> uuid.UUID | None:
    metadata = dict(article.metadata_ or {})
    article.content_type = resolve_content_type(article.raw_content, metadata)
    if source.category != "academic":
        return None

    title = str(article.title or "").strip()
    normalized_title = normalize_title(title)
    first_author = infer_first_author(metadata)
    year = infer_year(article.published_at, metadata)
    venue = infer_venue(metadata)
    identifiers = extract_identifier_candidates(metadata)

    paper = await resolve_existing_paper(
        session,
        identifiers=identifiers,
        normalized_title=normalized_title,
        first_author=first_author,
        year=year,
    )
    if paper is None:
        paper = Paper(
            id=uuid.uuid4(),
            title=title or "Untitled",
            normalized_title=normalized_title or normalize_title(article.external_id or article.id),
            abstract=article.raw_content if article.content_type == "abstract" else None,
            published_at=article.published_at,
            venue=venue,
            year=year,
            first_author=first_author,
            best_landing_url=article.url,
            best_pdf_url=infer_best_pdf_url(metadata),
            metadata_={"source_ids": [str(source.id)]},
        )
        session.add(paper)
        await session.flush()
    else:
        if not paper.abstract and article.content_type == "abstract":
            paper.abstract = article.raw_content
        if not paper.published_at:
            paper.published_at = article.published_at
        if not paper.venue:
            paper.venue = venue
        if not paper.year:
            paper.year = year
        if not paper.first_author:
            paper.first_author = first_author
        if not paper.best_landing_url:
            paper.best_landing_url = article.url
        if not paper.best_pdf_url:
            paper.best_pdf_url = infer_best_pdf_url(metadata)
        source_ids = list((paper.metadata_ or {}).get("source_ids", []))
        if str(source.id) not in source_ids:
            source_ids.append(str(source.id))
        paper.metadata_ = {**dict(paper.metadata_ or {}), "source_ids": source_ids}
        await session.flush()

    article.paper_id = paper.id

    for scheme, normalized_value in identifiers:
        stmt = select(PaperIdentifier).where(
            PaperIdentifier.scheme == scheme,
            PaperIdentifier.normalized_value == normalized_value,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            session.add(
                PaperIdentifier(
                    paper_id=paper.id,
                    scheme=scheme,
                    value=normalized_value,
                    normalized_value=normalized_value,
                    source=source.collect_method,
                )
            )
        elif existing.paper_id != paper.id:
            continue

    await session.flush()
    return paper.id
