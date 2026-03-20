from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.models import Article, Paper, PaperContent, Source
from app.papers.evidence import build_evidence_coverage
from app.papers.normalization import normalize_title


@pytest.mark.asyncio
async def test_build_evidence_coverage_prefers_successful_paper_content_over_article_fallback(
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
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            Article(
                id=article_id,
                source_id=source_id,
                paper_id=paper_id,
                external_id="article-1",
                title="Reasoning Agents",
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
                markdown_content="# Fulltext",
                plain_text="Fulltext",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    async with session_factory() as session:
        coverage = await build_evidence_coverage(session, [article_id])

    assert coverage["papers_total"] == 1
    assert coverage["papers_fulltext"] == 1
    assert coverage["papers_abstract_only"] == 0
    assert coverage["fulltext_coverage_ratio"] == 1.0


@pytest.mark.asyncio
async def test_build_evidence_coverage_counts_unresolved_articles_by_content_type(db_session_factory) -> None:
    session_factory, _ = db_session_factory
    source_id = uuid.uuid4()
    abstract_article_id = uuid.uuid4()
    partial_article_id = uuid.uuid4()
    now = datetime.now(UTC)

    async with session_factory() as session:
        session.add(
            Source(
                id=source_id,
                name="Academic Source",
                category="academic",
                collect_method="pubmed",
                config={},
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        session.add_all(
            [
                Article(
                    id=abstract_article_id,
                    source_id=source_id,
                    external_id="article-abstract",
                    title="Abstract Only",
                    content_type="abstract",
                    status="processed",
                    created_at=now,
                    updated_at=now,
                    collected_at=now,
                ),
                Article(
                    id=partial_article_id,
                    source_id=source_id,
                    external_id="article-partial",
                    title="Partial",
                    content_type="snippet",
                    status="processed",
                    created_at=now,
                    updated_at=now,
                    collected_at=now,
                ),
            ]
        )
        await session.commit()

    async with session_factory() as session:
        coverage = await build_evidence_coverage(session, [abstract_article_id, partial_article_id])

    assert coverage["papers_total"] == 2
    assert coverage["papers_partial_fulltext"] == 1
    assert coverage["papers_abstract_only"] == 1
    assert coverage["papers_fulltext"] == 0
    assert coverage["fulltext_coverage_ratio"] == 0.0
