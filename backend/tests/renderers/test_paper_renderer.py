from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.collectors.base import RawArticle
from app.processors.event_models import ProcessedEvent
from app.processors.pipeline import ProcessedArticle
from app.renderers.base import RenderContext
from app.renderers.paper import PaperRenderer
from app.papers.reporting import (
    build_paper_digest_entries,
    build_paper_identity,
    build_paper_note_links,
    build_paper_note_report,
    select_paper_note_candidates,
)


def _article(
    *,
    external_id: str,
    title: str,
    score: float,
    importance: str,
    paper_id: str,
    authors: list[str],
    affiliations: str,
    figure_url: str = "",
) -> ProcessedArticle:
    return ProcessedArticle(
        raw=RawArticle(
            external_id=external_id,
            title=title,
            url=f"https://example.com/{external_id}",
            content=f"{title} abstract and details.",
            published_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
            metadata={
                "paper_id": paper_id,
                "authors": authors,
                "affiliations": affiliations,
                "figure_url": figure_url,
            },
        ),
        summary=f"{title} summary",
        keywords=["paper", "research"],
        score=score,
        importance=importance,
        detail=f"{title} detailed reading notes.",
        category="academic",
        metrics=["+12%"],
        evidence=f"{title} official abstract.",
    )


@pytest.mark.asyncio
async def test_paper_renderer_builds_digest_and_marks_note_candidates() -> None:
    renderer = PaperRenderer()
    articles = [
        _article(
            external_id="paper-1",
            title="MVISTA-4D",
            score=0.96,
            importance="high",
            paper_id="2602.23546",
            authors=["Jiaxu Wang", "Yicheng Jiang"],
            affiliations="The Chinese University of Hong Kong",
            figure_url="https://example.com/figure-1.png",
        ),
        _article(
            external_id="paper-2",
            title="World Model Baselines",
            score=0.89,
            importance="high",
            paper_id="2602.11111",
            authors=["Alice"],
            affiliations="Example Lab",
        ),
        _article(
            external_id="paper-3",
            title="Auxiliary Paper",
            score=0.42,
            importance="normal",
            paper_id="2602.22222",
            authors=["Bob"],
            affiliations="Example Lab",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-20"))
    metadata = report.metadata or {}

    assert report.title == "2026-03-20 论文推荐"
    assert metadata["paper_mode"] == "digest"
    assert "本期导读" in report.content
    assert "推荐论文" in report.content

    paper_note_links = metadata["paper_note_links"]
    assert len(paper_note_links) == 2
    assert paper_note_links[0]["selected"] is True
    assert paper_note_links[0]["paper_slug"] == "mvista-4d"
    assert paper_note_links[0]["paper_identity"] == "2602.23546"
    assert "detail_link" not in paper_note_links[0]
    assert paper_note_links[1]["selected"] is True
    assert paper_note_links[1]["paper_identity"] == "2602.11111"
    assert "paper_parent_link" not in metadata
    assert report.article_ids == ["paper-1", "paper-2", "paper-3"]
    assert "核心图" in report.content
    assert "详细笔记" in report.content


@pytest.mark.asyncio
async def test_paper_note_report_uses_independent_note_metadata() -> None:
    article = _article(
        external_id="paper-note-1",
        title="MVISTA-4D",
        score=0.96,
        importance="high",
        paper_id="2602.23546",
        authors=["Jiaxu Wang", "Yicheng Jiang"],
        affiliations="The Chinese University of Hong Kong",
    )

    report = build_paper_note_report(
        article,
        context=RenderContext(date="2026-03-20"),
        parent_report_id="digest-1",
        digest_title="2026-03-20 论文推荐",
    )
    metadata = report.metadata or {}

    assert report.title == "MVISTA-4D"
    assert metadata["paper_mode"] == "note"
    assert metadata["parent_report_id"] == "digest-1"
    assert metadata["paper_slug"] == "mvista-4d"
    assert metadata["paper_identity"] == "2602.23546"
    assert metadata["paper_note_links"] == []
    assert metadata["paper_parent_link"] == {
        "report_id": "digest-1",
        "title": "2026-03-20 论文推荐",
    }
    assert report.article_ids == ["paper-note-1"]
    assert "论文定位" in report.content
    assert "回到推荐页" in report.content
    assert "2026-03-20 论文推荐" in report.content


def test_paper_note_links_helper_returns_only_related_note_candidates() -> None:
    articles = [
        _article(
            external_id="paper-a",
            title="MVISTA-4D",
            score=0.96,
            importance="high",
            paper_id="2602.23546",
            authors=["Jiaxu Wang", "Yicheng Jiang"],
            affiliations="The Chinese University of Hong Kong",
        ),
        _article(
            external_id="paper-b",
            title="World Model Baselines",
            score=0.89,
            importance="high",
            paper_id="2602.11111",
            authors=["Alice"],
            affiliations="Example Lab",
        ),
    ]

    links = build_paper_note_links(
        articles,
        selected_identities={"2602.23546"},
    )

    assert links == [
        {
            "paper_identity": "2602.23546",
            "paper_slug": "mvista-4d",
            "title": "MVISTA-4D",
            "selected": True,
        }
    ]


def test_paper_identity_is_stable_from_metadata_and_title() -> None:
    article = _article(
        external_id="paper-identity-1",
        title="MVISTA-4D: View-Consistent 4D World Model",
        score=0.91,
        importance="high",
        paper_id="2602.23546",
        authors=["Jiaxu Wang"],
        affiliations="The Chinese University of Hong Kong",
    )

    assert build_paper_identity(article) == "2602.23546"


def test_select_paper_note_candidates_deduplicates_by_identity_before_limit() -> None:
    duplicate = _article(
        external_id="paper-1-duplicate",
        title="MVISTA-4D (mirror)",
        score=0.95,
        importance="high",
        paper_id="arXiv:2602.23546",
        authors=["Mirror Author"],
        affiliations="Mirror Lab",
    )
    second = _article(
        external_id="paper-2",
        title="World Model Baselines",
        score=0.89,
        importance="high",
        paper_id="2602.11111",
        authors=["Alice"],
        affiliations="Example Lab",
    )
    third = _article(
        external_id="paper-3",
        title="Auxiliary Paper",
        score=0.60,
        importance="normal",
        paper_id="2602.22222",
        authors=["Bob"],
        affiliations="Example Lab",
    )

    selected = select_paper_note_candidates(
        [
            _article(
                external_id="paper-1",
                title="MVISTA-4D",
                score=0.96,
                importance="high",
                paper_id="2602.23546",
                authors=["Jiaxu Wang", "Yicheng Jiang"],
                affiliations="The Chinese University of Hong Kong",
            ),
            duplicate,
            second,
            third,
        ],
        limit=2,
    )

    assert [build_paper_identity(article) for article in selected] == [
        "2602.23546",
        "2602.11111",
    ]


def test_paper_note_links_helper_is_empty_when_no_papers_are_selected() -> None:
    links = build_paper_note_links(
        [
            _article(
                external_id="paper-a",
                title="MVISTA-4D",
                score=0.96,
                importance="high",
                paper_id="2602.23546",
                authors=["Jiaxu Wang", "Yicheng Jiang"],
                affiliations="The Chinese University of Hong Kong",
            )
        ],
        selected_identities=set(),
    )

    assert links == []


def test_paper_digest_entries_use_best_representative_per_identity() -> None:
    stale_article = _article(
        external_id="paper-stale",
        title="MVISTA-4D (mirror)",
        score=0.40,
        importance="normal",
        paper_id="2602.23546",
        authors=["Mirror Author"],
        affiliations="Mirror Lab",
    )
    stale_article.summary = "过时摘要"
    canonical_article = _article(
        external_id="paper-canonical",
        title="MVISTA-4D",
        score=0.96,
        importance="high",
        paper_id="arXiv:2602.23546",
        authors=["Jiaxu Wang", "Yicheng Jiang"],
        affiliations="The Chinese University of Hong Kong",
    )
    canonical_article.summary = "推荐阅读的权威摘要"

    entries, note_links = build_paper_digest_entries(
        [stale_article, canonical_article],
        selected_identities={"2602.23546"},
    )

    assert len(entries) == 1
    assert entries[0]["title"] == "MVISTA-4D"
    assert entries[0]["authors"] == "Jiaxu Wang，Yicheng Jiang"
    assert entries[0]["affiliations"] == "The Chinese University of Hong Kong"
    assert entries[0]["one_line"] == "推荐阅读的权威摘要"
    assert entries[0]["paper_identity"] == "2602.23546"
    assert entries[0]["paper_slug"] == "mvista-4d"
    assert entries[0]["reading_level"] == "必读"
    assert note_links == [
        {
            "paper_identity": "2602.23546",
            "paper_slug": "mvista-4d",
            "title": "MVISTA-4D",
            "selected": True,
        }
    ]


def test_paper_identity_normalizes_arxiv_and_doi_variants() -> None:
    arxiv_article = _article(
        external_id="paper-arxiv",
        title="ARXIV Variant",
        score=0.90,
        importance="high",
        paper_id="arXiv:2602.23546",
        authors=["Author"],
        affiliations="Example Lab",
    )
    doi_article = ProcessedArticle(
        raw=RawArticle(
            external_id="paper-doi",
            title="DOI Variant",
            url="https://example.com/paper-doi",
            content="DOI Variant abstract and details.",
            published_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
            metadata={
                "doi": "https://doi.org/10.1000/182",
                "authors": ["Author"],
                "affiliations": "Example Lab",
            },
        ),
        summary="DOI Variant summary",
        keywords=["paper"],
        score=0.85,
        importance="normal",
        detail="DOI Variant detailed reading notes.",
        category="academic",
    )

    assert build_paper_identity(arxiv_article) == "2602.23546"
    assert build_paper_identity(doi_article) == "10.1000/182"


@pytest.mark.asyncio
async def test_paper_renderer_rejects_non_article_inputs() -> None:
    renderer = PaperRenderer()

    with pytest.raises(TypeError, match="ProcessedArticle"):
        await renderer.render(
            [
                ProcessedEvent(
                    event_id="event-1",
                    title="Event",
                    summary="summary",
                    detail="detail",
                )
            ],
            RenderContext(date="2026-03-20"),
        )
