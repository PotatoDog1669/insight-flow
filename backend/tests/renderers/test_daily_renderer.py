from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.collectors.base import RawArticle
from app.processors.pipeline import ProcessedArticle
from app.renderers.base import RenderContext
from app.renderers.daily import DailyRenderer


@pytest.mark.asyncio
async def test_daily_renderer_outputs_dynamic_events_and_metadata() -> None:
    renderer = DailyRenderer()
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-1",
                title="OpenAI released a new reasoning model",
                url="https://example.com/openai-model",
                content="The model improves math benchmark by 12% and reduces latency by 30%.",
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "OpenAI", "source_category": "blog"},
            ),
            summary="OpenAI 发布新推理模型，性能与时延双提升。",
            keywords=["OpenAI", "reasoning", "benchmark"],
            score=0.92,
            importance="high",
            detail="OpenAI 正式发布最新推理模型，该模型在数学基准测试中提升 12%，推理延迟降低 30%。这是继 GPT-4o 之后的又一重大更新，标志着推理能力进入新阶段。",
        ),
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-2",
                title="GitHub Trending: New agent framework gains stars",
                url="https://github.com/example/agent",
                content="The repository gained 2800 stars today and published a new README.",
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "GitHub Trending", "source_category": "open_source"},
            ),
            summary="Agent 框架单日增星显著，生态关注度上升。",
            keywords=["agent", "github", "stars"],
            score=0.81,
            importance="normal",
            detail="一款新型 Agent 框架今日在 GitHub Trending 上强势登顶，单日新增 2800 星标。该框架提供了模块化的工具调用接口和多模型适配层，受到开发者社区广泛关注。",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))

    assert "## 概览" in report.content
    assert "#1" in report.content
    assert "#2" in report.content

    metadata = report.metadata or {}
    assert metadata.get("global_tldr")
    assert isinstance(metadata.get("events"), list)
    assert len(metadata["events"]) == 2
    first_event = metadata["events"][0]
    assert first_event["one_line_tldr"]
    assert first_event["detail"]
    assert first_event["source_links"]


@pytest.mark.asyncio
async def test_daily_renderer_limits_events_to_20() -> None:
    renderer = DailyRenderer()
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id=f"evt-{idx}",
                title=f"Event {idx}",
                url=f"https://example.com/{idx}",
                content=f"Content for event {idx}",
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "Test Source", "source_category": "blog"},
            ),
            summary=f"Summary {idx}",
            keywords=[f"kw-{idx}"],
            score=0.8,
        )
        for idx in range(1, 26)
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    metadata = report.metadata or {}
    events = metadata.get("events", [])

    assert len(events) == 20
    assert events[-1]["index"] == 20
    assert "#20" in report.content
    assert "#21" not in report.content


@pytest.mark.asyncio
async def test_importance_high_classifies_as_headline() -> None:
    renderer = DailyRenderer()
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-headline",
                title="Major AI company announces breakthrough",
                url="https://example.com/headline",
                content="A major AI breakthrough was announced today.",
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "TechCrunch", "source_category": "blog"},
            ),
            summary="AI 领域重大突破。",
            keywords=["AI", "breakthrough"],
            score=0.95,
            importance="high",
            detail="今日一家顶级 AI 公司宣布了重大技术突破，这一进展有望改变整个行业格局。详细的技术评测和竞品对比将在后续报告中呈现。",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    metadata = report.metadata or {}
    events = metadata.get("events", [])

    assert len(events) == 1
    assert events[0]["category"] == "要闻"
    assert events[0]["importance"] == "high"


@pytest.mark.asyncio
async def test_open_source_defaults_to_dev_ecosystem() -> None:
    renderer = DailyRenderer()
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-oss",
                title="Popular data library gains traction",
                url="https://github.com/example/oss",
                content="A popular data library gained 500 stars this week.",
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "GitHub", "source_category": "open_source"},
            ),
            summary="数据处理库增长迅速。",
            keywords=["data", "library"],
            score=0.7,
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    metadata = report.metadata or {}
    events = metadata.get("events", [])

    assert len(events) == 1
    assert events[0]["category"] == "开发生态"


@pytest.mark.asyncio
async def test_llm_detail_preferred_over_raw_content() -> None:
    renderer = DailyRenderer()
    llm_detail = "这是一段由 LLM 生成的详细分析，包含技术细节、性能指标和行业上下文。长度超过五十个字符以确保被优先使用而不是被 fallback 到原文截断逻辑。"
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-detail",
                title="Test event with LLM detail",
                url="https://example.com/detail",
                content="This is the raw content that should NOT be used when LLM detail is available.",
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "Test", "source_category": "blog"},
            ),
            summary="测试事件。",
            keywords=["test"],
            score=0.8,
            detail=llm_detail,
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    metadata = report.metadata or {}
    events = metadata.get("events", [])

    assert len(events) == 1
    assert events[0]["detail"] == llm_detail


@pytest.mark.asyncio
async def test_detail_fallback_skips_navigation_noise() -> None:
    renderer = DailyRenderer()
    noisy_content = """
Skip to main content
Share
[Home](https://example.com)
[See all](https://example.com/all)
Gemini 3.1 Flash-Lite introduces a more efficient serving stack with lower latency.
In internal evaluations, median latency dropped by 28% while holding quality steady.
The post also explains pricing and deployment constraints for production traffic.
"""
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-noise",
                title="Noisy source content",
                url="https://example.com/noise",
                content=noisy_content,
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "Google DeepMind", "source_category": "blog"},
            ),
            summary="测试摘要",
            keywords=["Gemini", "latency"],
            score=0.8,
            detail="",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    metadata = report.metadata or {}
    events = metadata.get("events", [])

    assert len(events) == 1
    detail = str(events[0]["detail"])
    assert "Skip to main content" not in detail
    assert "Share" not in detail
    assert "latency dropped by 28%" in detail


@pytest.mark.asyncio
async def test_daily_report_content_contains_structured_metadata() -> None:
    renderer = DailyRenderer()
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-meta",
                title="OpenAI released an API update",
                url="https://example.com/meta",
                content="The update includes a 20% throughput improvement for batch inference.",
                published_at=datetime(2026, 3, 2, 3, 4, 5, tzinfo=timezone.utc),
                metadata={"source_name": "OpenAI", "source_category": "blog"},
            ),
            summary="OpenAI 发布 API 更新并提升吞吐表现。",
            keywords=["OpenAI", "API", "throughput"],
            score=0.9,
            importance="high",
            detail="详细说明了吞吐提升方式、适用场景与上线节奏。",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    content = report.content

    assert "来源：" in content
    assert "发布时间：" in content
    assert "关键词：" in content
    assert "关键指标：" in content


@pytest.mark.asyncio
async def test_detail_fallback_removes_html_and_image_noise() -> None:
    renderer = DailyRenderer()
    noisy_content = """
<img src="https://example.com/banner.png" alt="banner" />
![badge](https://img.shields.io/badge/test-green.svg)
Project AIRI introduces a modular memory runtime for AI agents.
In benchmark tests, response quality improved by 42% on long sessions.
"""
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-html",
                title="HTML noise cleanup",
                url="https://example.com/html",
                content=noisy_content,
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "Test", "source_category": "blog"},
            ),
            summary="测试",
            keywords=["AIRI", "memory"],
            score=0.8,
            detail="",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    metadata = report.metadata or {}
    events = metadata.get("events", [])

    assert len(events) == 1
    detail = str(events[0]["detail"])
    assert "<img" not in detail
    assert "![badge]" not in detail
    assert "improved by 42%" in detail


@pytest.mark.asyncio
async def test_official_release_with_preview_word_is_not_rumor() -> None:
    renderer = DailyRenderer()
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-preview",
                title="Gemini 3.1 Flash-Lite now available in preview",
                url="https://deepmind.google/blog/gemini",
                content="Google announced the model and made it available to developers in preview via API.",
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "Google DeepMind", "source_category": "blog"},
            ),
            summary="Google 发布 Gemini 3.1 Flash-Lite 并开放预览接入。",
            keywords=["gemini", "release", "preview", "api"],
            score=0.9,
            importance="normal",
            detail="官方公告明确了可用性与接入渠道。",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    metadata = report.metadata or {}
    events = metadata.get("events", [])

    assert len(events) == 1
    assert events[0]["category"] == "模型发布"


@pytest.mark.asyncio
async def test_model_name_signal_defaults_to_model_release() -> None:
    renderer = DailyRenderer()
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-gpt",
                title="GPT-5.3 Instant: Smoother, more useful everyday conversations",
                url="https://openai.com/index/gpt-5-3-instant",
                content="OpenAI introduced GPT-5.3 Instant for daily ChatGPT usage.",
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "OpenAI", "source_category": "blog"},
            ),
            summary="GPT‑5.3 Instant directly reflects user feedback in these areas.",
            keywords=["gpt-5.3", "instant", "chatgpt"],
            score=0.85,
            importance="normal",
            detail="官方介绍了模型定位、交互体验优化方向与使用场景。",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    metadata = report.metadata or {}
    events = metadata.get("events", [])

    assert len(events) == 1
    assert events[0]["category"] == "模型发布"
