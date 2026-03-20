from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.collectors.base import RawArticle
from app.models import Article, Paper, PaperIdentifier, Source
from app.processors.pipeline import ProcessedArticle
from app.scheduler.orchestrator import Orchestrator


def _processed_article(raw: RawArticle, *, summary: str = "summary") -> ProcessedArticle:
    return ProcessedArticle(raw=raw, summary=summary, keywords=["agent"], score=1.0)


@pytest.mark.asyncio
async def test_persist_processed_academic_articles_creates_and_reuses_canonical_paper(db_session_factory) -> None:
    session_factory, _ = db_session_factory
    source_one_id = uuid.uuid4()
    source_two_id = uuid.uuid4()
    now = datetime.now(UTC)

    async with session_factory() as session:
        session.add_all(
            [
                Source(
                    id=source_one_id,
                    name="OpenAlex Source",
                    category="academic",
                    collect_method="openalex",
                    config={},
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                ),
                Source(
                    id=source_two_id,
                    name="PubMed Source",
                    category="academic",
                    collect_method="pubmed",
                    config={},
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        await session.commit()

    orchestrator = Orchestrator(max_concurrency=1)

    async with session_factory() as session:
        source_one = await session.get(Source, source_one_id)
        assert source_one is not None
        article_ids = await orchestrator._persist_processed_articles(
            session,
            source_one,
            [
                _processed_article(
                    RawArticle(
                        external_id="openalex-1",
                        title="Agentified Assessment of Logical Reasoning Agents",
                        url="https://example.com/openalex",
                        content="Short abstract about logical reasoning agents.",
                        published_at=now,
                        metadata={
                            "doi": "10.1000/logic-agents",
                            "authors": ["Alice Smith", "Bob Chen"],
                            "journal": "AI Journal",
                            "publication_year": 2026,
                            "openalex_id": "https://openalex.org/W123",
                        },
                    )
                )
            ],
        )
        assert len(article_ids) == 1

    async with session_factory() as session:
        source_two = await session.get(Source, source_two_id)
        assert source_two is not None
        article_ids = await orchestrator._persist_processed_articles(
            session,
            source_two,
            [
                _processed_article(
                    RawArticle(
                        external_id="pubmed-2",
                        title="Agentified Assessment of Logical Reasoning Agents",
                        url="https://pubmed.ncbi.nlm.nih.gov/123456/",
                        content="L" * 9000,
                        published_at=now,
                        metadata={
                            "doi": "https://doi.org/10.1000/logic-agents",
                            "pmid": "123456",
                            "authors": ["Alice Smith"],
                            "journal": "AI Journal",
                            "publication_year": 2026,
                            "content_tier": "fulltext",
                        },
                    )
                )
            ],
        )
        assert len(article_ids) == 1

    async with session_factory() as session:
        papers = (await session.execute(select(Paper))).scalars().all()
        identifiers = (await session.execute(select(PaperIdentifier))).scalars().all()
        articles = (await session.execute(select(Article).order_by(Article.external_id))).scalars().all()

    assert len(papers) == 1
    assert len(identifiers) >= 2
    assert all(article.paper_id == papers[0].id for article in articles)
    assert articles[0].content_type == "abstract"
    assert articles[1].content_type == "fulltext"


@pytest.mark.asyncio
async def test_non_academic_articles_are_not_linked_to_canonical_papers(db_session_factory) -> None:
    session_factory, _ = db_session_factory
    source_id = uuid.uuid4()
    now = datetime.now(UTC)

    async with session_factory() as session:
        session.add(
            Source(
                id=source_id,
                name="Blog Source",
                category="blog",
                collect_method="rss",
                config={},
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    orchestrator = Orchestrator(max_concurrency=1)

    async with session_factory() as session:
        source = await session.get(Source, source_id)
        assert source is not None
        await orchestrator._persist_processed_articles(
            session,
            source,
            [
                _processed_article(
                    RawArticle(
                        external_id="blog-1",
                        title="A normal blog post",
                        content="blog content",
                        published_at=now,
                    )
                )
            ],
        )

    async with session_factory() as session:
        article = (await session.execute(select(Article).where(Article.external_id == "blog-1"))).scalar_one()
        papers = (await session.execute(select(Paper))).scalars().all()

    assert article.paper_id is None
    assert papers == []
