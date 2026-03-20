from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.collectors.base import RawArticle
from app.processors.pipeline import ProcessedArticle
from app.renderers.base import RenderContext
from app.renderers.paper import PaperRenderer
from app.papers.reporting import build_paper_identity, build_paper_note_links, build_paper_note_report


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
        "detail_link": "[返回 2026-03-20 论文推荐](#digest-1)",
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
        digest_identity="digest-1",
        digest_title="2026-03-20 论文推荐",
    )

    assert links == [
        {
            "paper_identity": "2602.23546",
            "paper_slug": "mvista-4d",
            "title": "MVISTA-4D",
            "selected": True,
            "detail_link": "[阅读笔记](#mvista-4d)",
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
