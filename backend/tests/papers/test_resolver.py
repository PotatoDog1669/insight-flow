from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.models.paper import Paper, PaperIdentifier
from app.papers.normalization import normalize_identifier, normalize_title
from app.papers.resolver import resolve_existing_paper


@pytest.mark.asyncio
async def test_resolve_existing_paper_matches_strong_identifiers(db_session_factory) -> None:
    session_factory, _ = db_session_factory
    doi_paper_id = uuid.uuid4()
    pmcid_paper_id = uuid.uuid4()
    now = datetime.now(UTC)

    async with session_factory() as session:
        session.add_all(
            [
                Paper(
                    id=doi_paper_id,
                    title="Reasoning Agents",
                    normalized_title=normalize_title("Reasoning Agents"),
                    year=2025,
                    first_author="Alice Smith",
                    created_at=now,
                    updated_at=now,
                ),
                Paper(
                    id=pmcid_paper_id,
                    title="Spatial Reasoning Agents",
                    normalized_title=normalize_title("Spatial Reasoning Agents"),
                    year=2024,
                    first_author="Bob Chen",
                    created_at=now,
                    updated_at=now,
                ),
                PaperIdentifier(
                    paper_id=doi_paper_id,
                    scheme="doi",
                    value="10.1000/test",
                    normalized_value=normalize_identifier("doi", "10.1000/test") or "",
                    source="openalex",
                    created_at=now,
                ),
                PaperIdentifier(
                    paper_id=pmcid_paper_id,
                    scheme="pmcid",
                    value="PMC123456",
                    normalized_value=normalize_identifier("pmcid", "PMC123456") or "",
                    source="europe_pmc",
                    created_at=now,
                ),
            ]
        )
        await session.commit()

    async with session_factory() as session:
        matched_by_doi = await resolve_existing_paper(
            session,
            identifiers=[("doi", "https://doi.org/10.1000/test")],
            normalized_title=normalize_title("unrelated"),
            first_author="Nobody",
            year=2020,
        )
        matched_by_pmcid = await resolve_existing_paper(
            session,
            identifiers=[("pmcid", "pmc123456")],
            normalized_title=normalize_title("another"),
            first_author="Nobody",
            year=2020,
        )

    assert matched_by_doi is not None
    assert matched_by_doi.id == doi_paper_id
    assert matched_by_pmcid is not None
    assert matched_by_pmcid.id == pmcid_paper_id


@pytest.mark.asyncio
async def test_resolve_existing_paper_falls_back_to_title_author_year(db_session_factory) -> None:
    session_factory, _ = db_session_factory
    paper_id = uuid.uuid4()
    now = datetime.now(UTC)

    async with session_factory() as session:
        session.add(
            Paper(
                id=paper_id,
                title="Reasoning Agents for Science",
                normalized_title=normalize_title("Reasoning Agents for Science"),
                year=2025,
                first_author="Alice Smith",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    async with session_factory() as session:
        matched = await resolve_existing_paper(
            session,
            identifiers=[],
            normalized_title=normalize_title("Reasoning Agents for Science"),
            first_author="Alice Smith",
            year=2025,
        )

    assert matched is not None
    assert matched.id == paper_id


@pytest.mark.asyncio
async def test_resolve_existing_paper_does_not_false_merge_on_title_only(db_session_factory) -> None:
    session_factory, _ = db_session_factory
    now = datetime.now(UTC)

    async with session_factory() as session:
        session.add_all(
            [
                Paper(
                    id=uuid.uuid4(),
                    title="Reasoning Agents for Science",
                    normalized_title=normalize_title("Reasoning Agents for Science"),
                    year=2025,
                    first_author="Alice Smith",
                    created_at=now,
                    updated_at=now,
                ),
                Paper(
                    id=uuid.uuid4(),
                    title="Reasoning Agents for Science",
                    normalized_title=normalize_title("Reasoning Agents for Science"),
                    year=2024,
                    first_author="Bob Chen",
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        await session.commit()

    async with session_factory() as session:
        matched = await resolve_existing_paper(
            session,
            identifiers=[],
            normalized_title=normalize_title("Reasoning Agents for Science"),
            first_author="Carol Zhang",
            year=2025,
        )

    assert matched is None
