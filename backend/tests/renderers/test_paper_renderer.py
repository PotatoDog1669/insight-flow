from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.collectors.base import RawArticle
from app.papers.reporting import (
    build_paper_digest_entries,
    build_paper_identity,
    build_paper_note_links,
    build_paper_note_report,
    select_paper_note_candidates,
)
from app.processors.event_models import ProcessedEvent
from app.processors.pipeline import ProcessedArticle
from app.renderers.base import RenderContext
from app.renderers.paper import PaperRenderer


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
            published_at=datetime(2026, 3, 20, tzinfo=UTC),
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
    assert report.content.startswith("---\n")
    assert "date: 2026-03-20" in report.content
    assert "keywords:" in report.content
    assert "tags:" in report.content
    assert "## Properties" not in report.content
    assert "## 总结" in report.content
    assert report.content.count("## 总结") == 1
    assert "## Paper Picks" in report.content
    assert "**核心方法**" in report.content
    assert "**对比方法 / Baselines**" in report.content
    assert "**借鉴意义**" in report.content
    assert "**阅读建议**" in report.content

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
    assert "![MVISTA-4D](https://example.com/figure-1.png)" in report.content
    assert "- 核心图：" not in report.content
    assert "详细笔记" not in report.content


@pytest.mark.asyncio
async def test_paper_renderer_prefers_review_payload_for_digest_structure() -> None:
    renderer = PaperRenderer()
    article = _article(
        external_id="paper-1",
        title="World Model Policy",
        score=0.96,
        importance="high",
        paper_id="2603.12345",
        authors=["Alice"],
        affiliations="Example Lab",
    )

    report = await renderer.render(
        [article],
        RenderContext(
            date="2026-03-20",
            extra={
                "paper_review_payload": {
                    "digest_title": "GUI 智能体的评测、安全与长程记忆",
                    "digest_summary": "本期重点不只是新论文数量，而是方法接口开始明显收敛。",
                    "papers": [
                        {
                            "paper_identity": "2603.12345",
                            "paper_slug": "world-model-policy",
                    "title": "World Model Policy",
                    "authors": ["Alice"],
                    "affiliations": ["Example Lab"],
                    "links": ["https://arxiv.org/abs/2603.12345"],
                    "topic_label": "World Model",
                    "recommendation": "必读",
                    "one_line_judgment": "这篇工作终于把方法边界说清楚了。",
                    "core_problem": "现有方法接口割裂。",
                            "core_method": "统一 world model 与 policy 表达。",
                            "key_result": "多任务上超过 baseline。",
                            "why_it_matters": "更接近可复用框架。",
                            "reading_advice": "先看方法定义再看实验。",
                            "note_candidate": True,
                        }
                    ],
                }
            },
        ),
    )
    metadata = report.metadata or {}

    assert report.content.startswith("---\n")
    assert "## Properties" not in report.content
    assert report.title == "2026-03-20 论文推荐"
    assert "# 2026-03-20 论文推荐" in report.content
    assert "## 总结" in report.content
    assert "## 今日锐评" not in report.content
    assert "## World Model" in report.content
    assert "- 详细笔记：" not in report.content
    assert "**核心方法**" in report.content
    assert "**锐评**" not in report.content
    assert "**阅读建议**" in report.content
    assert metadata["selected_paper_identities"] == ["2603.12345"]
    assert metadata["paper_recommendations"] == [{"paper_identity": "2603.12345", "recommendation": "必读"}]


@pytest.mark.asyncio
async def test_paper_renderer_uses_project_teaser_when_primary_figure_missing() -> None:
    renderer = PaperRenderer()
    article = _article(
        external_id="paper-1",
        title="ClawTrap",
        score=0.96,
        importance="high",
        paper_id="2603.18762",
        authors=["Alice"],
        affiliations="Example Lab",
    )
    article.raw.metadata["project_teaser_url"] = "https://demo.example.com/assets/teaser.png"

    report = await renderer.render([article], RenderContext(date="2026-03-20"))

    assert "![ClawTrap](https://demo.example.com/assets/teaser.png)" in report.content


@pytest.mark.asyncio
async def test_paper_renderer_prefers_explicit_digest_summary_and_exposes_it_in_metadata() -> None:
    renderer = PaperRenderer()
    articles = [
        _article(
            external_id="paper-1",
            title="Nemotron-Cascade 2",
            score=0.96,
            importance="high",
            paper_id="2603.00001",
            authors=["Alice"],
            affiliations="Example Lab",
        ),
        _article(
            external_id="paper-2",
            title="OS-Themis",
            score=0.89,
            importance="high",
            paper_id="2603.00002",
            authors=["Bob"],
            affiliations="Example Lab",
        ),
    ]

    summary = "本期重点不只是新论文数量，而是后训练强化学习与 GUI 奖励建模两条线开始进入更可复用的工程阶段。"
    report = await renderer.render(
        articles,
        RenderContext(date="2026-03-20", extra={"digest_summary": summary}),
    )
    metadata = report.metadata or {}

    assert summary in report.content
    assert metadata["global_tldr"] == summary
    assert metadata["tldr"] == [summary]
    assert "本期聚焦 Nemotron-Cascade 2" not in report.content


@pytest.mark.asyncio
async def test_paper_renderer_fallback_digest_summary_uses_paper_summaries_with_commentary() -> None:
    renderer = PaperRenderer()
    first = _article(
        external_id="paper-1",
        title="Nemotron-Cascade 2",
        score=0.96,
        importance="high",
        paper_id="2603.00001",
        authors=["Alice"],
        affiliations="Example Lab",
    )
    first.summary = "后训练强化学习开始从单轮技巧堆叠走向更成体系的蒸馏与策略优化。"
    second = _article(
        external_id="paper-2",
        title="OS-Themis",
        score=0.89,
        importance="high",
        paper_id="2603.00002",
        authors=["Bob"],
        affiliations="Example Lab",
    )
    second.summary = "GUI 奖励建模正在从任务特例走向可扩展的通用 critic 框架。"

    report = await renderer.render([first, second], RenderContext(date="2026-03-20"))
    metadata = report.metadata or {}

    assert "后训练强化学习开始从单轮技巧堆叠走向更成体系的蒸馏与策略优化。" in report.content
    assert "GUI 奖励建模正在从任务特例走向可扩展的通用 critic 框架。" in report.content
    assert "整体上，本期更值得关注这些工作是否正在从单点结果走向可复用框架与系统能力。" in report.content
    assert metadata["tldr"] == [metadata["global_tldr"]]


@pytest.mark.asyncio
async def test_paper_renderer_cleans_blockquote_style_digest_fields() -> None:
    renderer = PaperRenderer()
    article = _article(
        external_id="paper-1",
        title="OS-Themis",
        score=0.96,
        importance="high",
        paper_id="2603.19191",
        authors=["Alice"],
        affiliations="Example Lab",
    )
    article.what = "发布论文提出多智能体奖励评审框架。"
    article.detail = "> OS-Themis 通过多智能体评审与里程碑分解，提升 GUI 奖励建模质量。"
    article.metrics = ["AndroidWorld 在线 RL 提升 10.3%"]

    report = await renderer.render([article], RenderContext(date="2026-03-20"))

    assert "核心方法：> " not in report.content
    assert "**核心方法**" in report.content
    assert "OS-Themis 通过多智能体评审与里程碑分解，提升 GUI 奖励建模质量。" in report.content
    assert "**对比方法 / Baselines**" in report.content
    assert "AndroidWorld 在线 RL 提升 10.3%" in report.content


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
    assert "元信息" in report.content
    assert "一句话总结" in report.content
    assert "批判性思考" in report.content
    assert "回到推荐页" in report.content
    assert "[2026-03-20 论文推荐](/reports/digest-1)" in report.content


@pytest.mark.asyncio
async def test_paper_note_report_prefers_note_payload_sections() -> None:
    article = _article(
        external_id="paper-note-stage-1",
        title="World Model Policy",
        score=0.96,
        importance="high",
        paper_id="2603.12345",
        authors=["Alice"],
        affiliations="Example Lab",
    )

    report = build_paper_note_report(
        article,
        context=RenderContext(date="2026-03-20"),
        parent_report_id="digest-1",
        digest_title="2026-03-20 论文推荐",
        note_payload={
            "paper_identity": "2603.12345",
            "paper_slug": "world-model-policy",
            "title": "World Model Policy",
            "authors": ["Alice"],
            "affiliations": ["Example Lab"],
            "links": ["https://arxiv.org/abs/2603.12345"],
            "summary": "这篇工作把 world model 和 policy 学习的接口真正打通了。",
            "core_contributions": ["统一了训练目标", "降低了规划成本"],
            "problem_background": ["现有方法推理开销高"],
            "method_breakdown": ["分层建模", "基于 latent 的规划"],
            "figure_notes": ["图 1 展示了整体训练流程。"],
            "experiments": ["在多个控制任务上优于 baseline"],
            "strengths": ["结构完整"],
            "limitations": ["真实世界验证有限"],
            "related_reading": ["DreamerV3"],
            "next_steps": ["关注真实机器人迁移"],
        },
    )

    assert "统一了训练目标" in report.content
    assert "现有方法推理开销高" in report.content
    assert "分层建模" in report.content
    assert "DreamerV3" in report.content


@pytest.mark.asyncio
async def test_paper_note_report_renders_visual_blocks_from_enriched_metadata() -> None:
    article = _article(
        external_id="paper-note-visuals",
        title="OS-Themis",
        score=0.96,
        importance="high",
        paper_id="2603.19191",
        authors=["Zehao Li"],
        affiliations="Example Lab",
        figure_url="https://arxiv.org/html/2603.19191v1/x1.png",
    )
    article.raw.metadata.update(
        {
            "figure_caption": "Figure 1: Pipeline overview",
            "project_teaser_url": "https://demo.example.com/assets/teaser.png",
        }
    )

    report = build_paper_note_report(
        article,
        context=RenderContext(date="2026-03-20"),
    )

    assert "### Figure 1: Pipeline overview" in report.content
    assert "![Figure 1: Pipeline overview](https://arxiv.org/html/2603.19191v1/x1.png)" in report.content
    assert "https://demo.example.com/assets/teaser.png" in report.content


@pytest.mark.asyncio
async def test_paper_note_report_sanitizes_stringified_list_fields() -> None:
    article = _article(
        external_id="paper-note-sanitized",
        title="Structured Paper",
        score=0.95,
        importance="high",
        paper_id="2603.19999",
        authors=["Alice"],
        affiliations="Example Lab",
    )
    article.detail = "['方法分为编码器与时序建模两部分。', '作者强调多视角一致性。']"
    article.evidence = "['实验显示在公开视频基准上有提升。', '摘要提到真实世界泛化更稳定。']"
    article.unknowns = "['未披露完整训练成本。', '代码是否开源未说明。']"

    report = build_paper_note_report(article, context=RenderContext(date="2026-03-20"))

    assert "['" not in report.content
    assert "方法分为编码器与时序建模两部分。" in report.content
    assert "实验显示在公开视频基准上有提升。" in report.content
    assert "未披露完整训练成本。" in report.content


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


def test_paper_digest_entries_extract_author_names_and_first_author_institution_from_author_objects() -> None:
    article = ProcessedArticle(
        raw=RawArticle(
            external_id="paper-rich-metadata",
            title="Rich Metadata Paper",
            url="https://example.com/paper-rich-metadata",
            content="Rich Metadata Paper abstract and details.",
            published_at=datetime(2026, 3, 20, tzinfo=UTC),
            metadata={
                "paper_id": "2603.13045",
                "authors": [
                    {
                        "name": "Yifeng Liu",
                        "affiliations": ["Tsinghua University", "Institute A"],
                    },
                    {
                        "name": "Siqi Ouyang",
                        "affiliations": ["Institute B"],
                    },
                ],
            },
        ),
        summary="Rich Metadata Paper summary",
        keywords=["paper"],
        score=0.91,
        importance="high",
        detail="Rich Metadata Paper detailed reading notes.",
        category="academic",
    )

    entries, _ = build_paper_digest_entries([article], selected_identities=set())

    assert entries[0]["authors"] == "Yifeng Liu，Siqi Ouyang"
    assert entries[0]["affiliations"] == "Tsinghua University"


def test_paper_digest_entries_fall_back_to_source_organization_when_institution_missing() -> None:
    article = ProcessedArticle(
        raw=RawArticle(
            external_id="paper-organization-fallback",
            title="Organization Fallback Paper",
            url="https://example.com/paper-organization-fallback",
            content="Organization Fallback Paper abstract and details.",
            published_at=datetime(2026, 3, 20, tzinfo=UTC),
            metadata={
                "paper_id": "2603.19224",
                "authors": [
                    {"name": "Yang Fu"},
                    {"name": "Yike Zheng"},
                ],
                "organization": {"fullname": "FudanCVL"},
            },
        ),
        summary="Organization Fallback Paper summary",
        keywords=["paper"],
        score=0.88,
        importance="high",
        detail="Organization Fallback Paper detailed reading notes.",
        category="academic",
    )

    entries, _ = build_paper_digest_entries([article], selected_identities=set())

    assert entries[0]["authors"] == "Yang Fu，Yike Zheng"
    assert entries[0]["affiliations"] == "FudanCVL"


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
            published_at=datetime(2026, 3, 20, tzinfo=UTC),
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
