"""Canonical paper resolution helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper, PaperIdentifier
from app.papers.normalization import normalize_identifier, normalize_person_name

_IDENTIFIER_PRIORITY = {"doi": 0, "pmcid": 1, "pmid": 2, "arxiv": 3, "openalex": 4}


async def resolve_existing_paper(
    session: AsyncSession,
    *,
    identifiers: list[tuple[str, str]],
    normalized_title: str,
    first_author: str | None,
    year: int | None,
) -> Paper | None:
    for scheme, value in sorted(identifiers, key=lambda item: _IDENTIFIER_PRIORITY.get(item[0], 99)):
        normalized_value = normalize_identifier(scheme, value)
        if not normalized_value:
            continue
        stmt = (
            select(Paper)
            .join(PaperIdentifier, PaperIdentifier.paper_id == Paper.id)
            .where(PaperIdentifier.scheme == scheme, PaperIdentifier.normalized_value == normalized_value)
            .limit(1)
        )
        matched = (await session.execute(stmt)).scalar_one_or_none()
        if matched is not None:
            return matched

    if not normalized_title or not first_author or year is None:
        return None

    stmt = select(Paper).where(Paper.normalized_title == normalized_title, Paper.year == year)
    candidates = (await session.execute(stmt)).scalars().all()
    normalized_author = normalize_person_name(first_author)
    for candidate in candidates:
        if normalize_person_name(candidate.first_author) == normalized_author:
            return candidate
    return None
