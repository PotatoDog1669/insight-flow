from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.models import Article, Paper, PaperContent, PaperIdentifier, Source
from app.papers.literature import build_literature_context
from app.papers.normalization import normalize_identifier, normalize_title


@pytest.mark.asyncio
async def test_build_literature_context_prefers_paper_fulltext_for_academic_articles(
    db_session_factory,
) -> None:
    session_factory, _ = db_session_factory
    source_id = uuid.uuid4()
    paper_id = uuid.uuid4()
    article_id = uuid.uuid4()
    now = datetime.now(UTC)

    async with session_factory() as session:
        session.add(
            Source(
                id=source_id,
                name="Academic Source",
                category="academic",
                collect_method="openalex",
                config={},
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            Paper(
                id=paper_id,
                title="Reasoning Agents",
                normalized_title=normalize_title("Reasoning Agents"),
                abstract="Paper abstract",
                venue="NeurIPS",
                year=2026,
                first_author="Alice",
                best_landing_url="https://example.com/paper",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            PaperIdentifier(
                paper_id=paper_id,
                scheme="doi",
                value="10.1000/reasoning",
                normalized_value=normalize_identifier("doi", "10.1000/reasoning") or "",
                source="openalex",
                created_at=now,
            )
        )
        session.add(
            Article(
                id=article_id,
                source_id=source_id,
                paper_id=paper_id,
                external_id="article-1",
                title="Reasoning Agents",
                url="https://example.com/article",
                raw_content="Short abstract only",
                content_type="abstract",
                status="processed",
                created_at=now,
                updated_at=now,
                collected_at=now,
            )
        )
        session.add(
            PaperContent(
                paper_id=paper_id,
                content_tier="fulltext",
                extraction_status="success",
                markdown_content="# Reasoning Agents\n\nFulltext body for literature analysis.",
                plain_text="Reasoning Agents Fulltext body for literature analysis.",
                quality_score=0.95,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    async with session_factory() as session:
        context = await build_literature_context(session, [article_id])

    assert context["analysis_mode"] == "literature"
    assert context["literature_summary"]["paper_count"] == 1
    item = context["literature_corpus"][0]
    assert item["paper_id"] == str(paper_id)
    assert item["evidence_level"] == "fulltext"
    assert item["identifiers"]["doi"] == "10.1000/reasoning"
    assert "Fulltext body for literature analysis" in item["analysis_text"]
    assert item["source_names"] == ["Academic Source"]


@pytest.mark.asyncio
async def test_build_literature_context_falls_back_to_article_abstract_when_unresolved(db_session_factory) -> None:
    session_factory, _ = db_session_factory
    source_id = uuid.uuid4()
    article_id = uuid.uuid4()
    now = datetime.now(UTC)

    async with session_factory() as session:
        session.add(
            Source(
                id=source_id,
                name="PubMed",
                category="academic",
                collect_method="pubmed",
                config={},
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            Article(
                id=article_id,
                source_id=source_id,
                external_id="pmid-1",
                title="Abstract Only Paper",
                url="https://example.com/abstract-only",
                raw_content="This is only the abstract.",
                content_type="abstract",
                status="processed",
                metadata_={"pmid": "123456"},
                created_at=now,
                updated_at=now,
                collected_at=now,
            )
        )
        await session.commit()

    async with session_factory() as session:
        context = await build_literature_context(session, [article_id])

    assert context["analysis_mode"] == "literature"
    item = context["literature_corpus"][0]
    assert item["paper_id"] is None
    assert item["evidence_level"] == "abstract_only"
    assert item["analysis_text"] == "This is only the abstract."
    assert item["identifiers"]["pmid"] == "123456"
