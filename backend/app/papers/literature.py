"""Academic literature corpus helpers for research jobs."""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.paper import Paper, PaperContent, PaperIdentifier
from app.models.source import Source

_ANALYSIS_TEXT_LIMIT = 12_000
_EXCERPT_LIMIT = 1_200
_IDENTIFIER_KEYS = ("doi", "pmid", "pmcid", "arxiv", "openalex", "openalex_id")


async def build_literature_context(
    session: AsyncSession,
    article_ids: list[uuid.UUID] | list[str],
) -> dict[str, Any]:
    normalized_ids = [_coerce_uuid(item) for item in article_ids]
    normalized_ids = [item for item in normalized_ids if item is not None]
    if not normalized_ids:
        return {}

    article_stmt = select(Article).where(Article.id.in_(normalized_ids))
    articles = (await session.execute(article_stmt)).scalars().all()
    if not articles:
        return {}

    typed_rows: list[tuple[Article, Source]] = []
    for article in articles:
        source = await session.get(Source, article.source_id)
        if source is None:
            return {}
        typed_rows.append((article, source))
    if any(source.category != "academic" for _, source in typed_rows):
        return {}

    paper_ids = sorted({article.paper_id for article, _ in typed_rows if article.paper_id is not None}, key=str)
    papers_by_id = await _load_papers_by_id(session, paper_ids)
    identifiers_by_paper = await _load_identifiers_by_paper(session, paper_ids)
    contents_by_paper = await _load_contents_by_paper(session, paper_ids)

    grouped_rows: dict[uuid.UUID | None, list[tuple[Article, Source]]] = {}
    for article, source in typed_rows:
        grouped_rows.setdefault(article.paper_id, []).append((article, source))

    corpus: list[dict[str, Any]] = []
    for paper_id, group in grouped_rows.items():
        if paper_id is None:
            corpus.extend(_build_unresolved_items(group))
            continue
        paper = papers_by_id.get(paper_id)
        if paper is None:
            corpus.extend(_build_unresolved_items(group))
            continue
        corpus.append(
            _build_resolved_item(
                paper=paper,
                rows=group,
                identifiers=identifiers_by_paper.get(paper_id, []),
                contents=contents_by_paper.get(paper_id, []),
            )
        )

    corpus.sort(
        key=lambda item: (
            _evidence_rank(str(item.get("evidence_level") or "")),
            str(item.get("title") or ""),
        ),
        reverse=True,
    )
    return {
        "analysis_mode": "literature",
        "literature_corpus": corpus,
        "literature_summary": _build_summary(corpus),
    }


async def _load_papers_by_id(session: AsyncSession, paper_ids: list[uuid.UUID]) -> dict[uuid.UUID, Paper]:
    if not paper_ids:
        return {}
    stmt = select(Paper).where(Paper.id.in_(paper_ids))
    papers = (await session.execute(stmt)).scalars().all()
    return {paper.id: paper for paper in papers}


async def _load_identifiers_by_paper(
    session: AsyncSession,
    paper_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[PaperIdentifier]]:
    if not paper_ids:
        return {}
    stmt = select(PaperIdentifier).where(PaperIdentifier.paper_id.in_(paper_ids))
    identifiers = (await session.execute(stmt)).scalars().all()
    grouped: dict[uuid.UUID, list[PaperIdentifier]] = {}
    for identifier in identifiers:
        grouped.setdefault(identifier.paper_id, []).append(identifier)
    return grouped


async def _load_contents_by_paper(
    session: AsyncSession,
    paper_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[PaperContent]]:
    if not paper_ids:
        return {}
    stmt = select(PaperContent).where(
        PaperContent.paper_id.in_(paper_ids),
        PaperContent.extraction_status == "success",
    )
    contents = (await session.execute(stmt)).scalars().all()
    grouped: dict[uuid.UUID, list[PaperContent]] = {}
    for content in contents:
        grouped.setdefault(content.paper_id, []).append(content)
    return grouped


def _build_resolved_item(
    *,
    paper: Paper,
    rows: list[tuple[Article, Source]],
    identifiers: list[PaperIdentifier],
    contents: list[PaperContent],
) -> dict[str, Any]:
    best_article = max((article for article, _ in rows), key=_article_rank)
    best_content = _select_best_content(contents, preferred_id=paper.best_content_id)
    analysis_text = _pick_analysis_text(best_content=best_content, best_article=best_article, paper=paper)
    source_names = sorted({source.name for _, source in rows if str(source.name or "").strip()})
    source_urls = sorted(
        {
            url
            for url in [
                *(article.url for article, _ in rows),
                paper.best_landing_url,
                paper.best_pdf_url,
            ]
            if str(url or "").strip()
        }
    )

    return {
        "paper_id": str(paper.id),
        "article_ids": [str(article.id) for article, _ in rows],
        "title": paper.title,
        "published_at": paper.published_at.isoformat() if paper.published_at is not None else None,
        "venue": paper.venue,
        "year": paper.year,
        "first_author": paper.first_author,
        "source_names": source_names,
        "source_urls": source_urls,
        "identifiers": {item.scheme: item.value for item in identifiers if str(item.value or "").strip()},
        "evidence_level": _content_evidence_level(best_content, fallback_content_type=best_article.content_type),
        "analysis_text": _truncate(analysis_text, _ANALYSIS_TEXT_LIMIT),
        "content_excerpt": _truncate(analysis_text, _EXCERPT_LIMIT),
        "abstract": paper.abstract or (best_article.raw_content if best_article.content_type == "abstract" else None),
    }


def _build_unresolved_items(rows: list[tuple[Article, Source]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for article, source in rows:
        analysis_text = str(article.raw_content or article.summary or "").strip()
        items.append(
            {
                "paper_id": None,
                "article_ids": [str(article.id)],
                "title": article.title,
                "published_at": article.published_at.isoformat() if article.published_at is not None else None,
                "venue": None,
                "year": None,
                "first_author": None,
                "source_names": [source.name],
                "source_urls": [article.url] if str(article.url or "").strip() else [],
                "identifiers": _extract_article_identifiers(article),
                "evidence_level": _article_evidence_level(article.content_type),
                "analysis_text": _truncate(analysis_text, _ANALYSIS_TEXT_LIMIT),
                "content_excerpt": _truncate(analysis_text, _EXCERPT_LIMIT),
                "abstract": analysis_text if article.content_type == "abstract" else None,
            }
        )
    return items


def _pick_analysis_text(*, best_content: PaperContent | None, best_article: Article, paper: Paper) -> str:
    candidates = [
        best_content.markdown_content if best_content is not None else None,
        best_content.plain_text if best_content is not None else None,
        best_article.raw_content,
        paper.abstract,
        best_article.summary,
    ]
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            return text
    return paper.title


def _select_best_content(contents: list[PaperContent], preferred_id: uuid.UUID | None) -> PaperContent | None:
    if not contents:
        return None
    if preferred_id is not None:
        for content in contents:
            if content.id == preferred_id:
                return content
    return max(contents, key=_content_rank)


def _content_rank(content: PaperContent) -> tuple[int, float]:
    return (_evidence_rank(_article_evidence_level(content.content_tier)), float(content.quality_score or 0.0))


def _article_rank(article: Article) -> tuple[int, int]:
    raw_length = len(str(article.raw_content or ""))
    return (_evidence_rank(_article_evidence_level(article.content_type)), raw_length)


def _content_evidence_level(content: PaperContent | None, *, fallback_content_type: str) -> str:
    if content is None:
        return _article_evidence_level(fallback_content_type)
    return _article_evidence_level(content.content_tier)


def _article_evidence_level(content_type: str) -> str:
    mapping = {
        "fulltext": "fulltext",
        "partial_fulltext": "partial_fulltext",
        "snippet": "partial_fulltext",
        "abstract": "abstract_only",
        "metadata": "metadata_only",
    }
    return mapping.get(str(content_type or "").strip(), "metadata_only")


def _evidence_rank(level: str) -> int:
    return {
        "metadata_only": 0,
        "abstract_only": 1,
        "partial_fulltext": 2,
        "fulltext": 3,
    }.get(level, -1)


def _extract_article_identifiers(article: Article) -> dict[str, str]:
    metadata = dict(article.metadata_ or {})
    identifiers: dict[str, str] = {}
    for key in _IDENTIFIER_KEYS:
        value = str(metadata.get(key) or "").strip()
        if not value:
            continue
        normalized_key = "openalex" if key == "openalex_id" else key
        identifiers[normalized_key] = value
    return identifiers


def _build_summary(corpus: list[dict[str, Any]]) -> dict[str, int]:
    counter = Counter(str(item.get("evidence_level") or "metadata_only") for item in corpus)
    return {
        "paper_count": len(corpus),
        "fulltext_count": counter.get("fulltext", 0),
        "partial_fulltext_count": counter.get("partial_fulltext", 0),
        "abstract_only_count": counter.get("abstract_only", 0),
        "metadata_only_count": counter.get("metadata_only", 0),
    }


def _truncate(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "…"


def _coerce_uuid(value: uuid.UUID | str) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None
