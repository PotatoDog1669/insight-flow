from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models import Paper, PaperAsset, PaperContent, PaperIdentifier
from app.papers.asset_service import upsert_paper_asset
from app.papers.content_service import create_paper_content, refresh_best_content
from app.papers.fulltext_locator import locate_fulltext_candidates
from app.papers.normalization import normalize_identifier, normalize_title


@pytest.mark.asyncio
async def test_fulltext_locator_and_asset_content_services_cover_minimal_lifecycle(db_session_factory) -> None:
    session_factory, _ = db_session_factory
    paper_id = uuid.uuid4()
    now = datetime.now(UTC)

    async with session_factory() as session:
        session.add(
            Paper(
                id=paper_id,
                title="Reasoning Agents",
                normalized_title=normalize_title("Reasoning Agents"),
                best_landing_url="https://doi.org/10.1000/reasoning-agents",
                created_at=now,
                updated_at=now,
            )
        )
        session.add_all(
            [
                PaperIdentifier(
                    paper_id=paper_id,
                    scheme="pmcid",
                    value="PMC123456",
                    normalized_value=normalize_identifier("pmcid", "PMC123456") or "",
                    source="europe_pmc",
                    created_at=now,
                ),
                PaperIdentifier(
                    paper_id=paper_id,
                    scheme="arxiv",
                    value="2501.00001",
                    normalized_value=normalize_identifier("arxiv", "2501.00001") or "",
                    source="arxiv",
                    created_at=now,
                ),
            ]
        )
        await session.commit()

    async with session_factory() as session:
        paper = await session.get(Paper, paper_id)
        assert paper is not None
        identifiers = (
            await session.execute(select(PaperIdentifier).where(PaperIdentifier.paper_id == paper_id))
        ).scalars().all()
        candidates = locate_fulltext_candidates(paper, identifiers)

        asset_one = await upsert_paper_asset(
            session,
            paper_id=paper_id,
            asset_type="pdf",
            source_kind="arxiv",
            source_url="https://arxiv.org/pdf/2501.00001.pdf",
            resolved_url="https://arxiv.org/pdf/2501.00001.pdf",
            checksum="sha256:abc",
            fetch_status="success",
            mime_type="application/pdf",
        )
        asset_two = await upsert_paper_asset(
            session,
            paper_id=paper_id,
            asset_type="pdf",
            source_kind="arxiv",
            source_url="https://arxiv.org/pdf/2501.00001.pdf",
            resolved_url="https://arxiv.org/pdf/2501.00001.pdf",
            checksum="sha256:abc",
            fetch_status="success",
            mime_type="application/pdf",
        )
        content = await create_paper_content(
            session,
            paper_id=paper_id,
            asset_id=asset_one.id,
            content_tier="fulltext",
            markdown_content="# Reasoning Agents\n\nFull markdown body",
            plain_text="Reasoning Agents Full markdown body",
            converter_name="test-converter",
            quality_score=0.95,
            extraction_status="success",
        )
        await refresh_best_content(session, paper_id)
        await session.commit()

    async with session_factory() as session:
        refreshed_paper = await session.get(Paper, paper_id)
        assets = (
            await session.execute(select(PaperAsset).where(PaperAsset.paper_id == paper_id))
        ).scalars().all()
        contents = (
            await session.execute(select(PaperContent).where(PaperContent.paper_id == paper_id))
        ).scalars().all()

    assert any(candidate.url == "https://pmc.ncbi.nlm.nih.gov/articles/PMC123456/?page=1" for candidate in candidates)
    assert any(candidate.url == "https://arxiv.org/pdf/2501.00001.pdf" for candidate in candidates)
    assert asset_one.id == asset_two.id
    assert len(assets) == 1
    assert len(contents) == 1
    assert contents[0].id == content.id
    assert refreshed_paper is not None
    assert refreshed_paper.best_content_id == content.id
    assert refreshed_paper.fulltext_status == "converted"
