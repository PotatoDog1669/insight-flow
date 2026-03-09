from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.collectors.base import RawArticle
from app.processors.event_models import ProcessedEvent
from app.processors.pipeline import ProcessedArticle
from app.renderers.base import RenderContext
from app.renderers.daily import DailyRenderer, render_daily_report


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
async def test_global_tldr_uses_natural_summary_style_without_labels_or_counts() -> None:
    renderer = DailyRenderer()
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-style-1",
                title="Gemini 3.1 Flash-Lite: Built for intelligence at scale",
                url="https://example.com/gemini",
                content="Gemini 3.1 Flash-Lite introduces lower latency with strong quality retention.",
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "Google DeepMind", "source_category": "blog"},
            ),
            summary="Google 发布 Gemini 3.1 Flash-Lite，强调成本与速度平衡。",
            keywords=["Gemini", "Flash-Lite", "Google"],
            score=0.9,
            detail="官方披露了价格与性能细节，并开放 API 预览。",
        ),
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-style-2",
                title="GPT-5.3 Instant System Card",
                url="https://example.com/gpt53",
                content="OpenAI shares system card updates for GPT-5.3 Instant.",
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "OpenAI", "source_category": "blog"},
            ),
            summary="OpenAI 发布 GPT-5.3 Instant 系统卡，强调对话体验优化。",
            keywords=["GPT-5.3", "OpenAI", "System Card"],
            score=0.88,
            detail="更新重点放在响应流畅度与搜索可用性改进。",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    metadata = report.metadata or {}
    global_tldr = str(metadata.get("global_tldr") or "")

    assert global_tldr
    assert "总结：" not in global_tldr
    assert "锐评：" not in global_tldr
    assert "今日共整理" not in global_tldr
    assert "按主题分布为" not in global_tldr


@pytest.mark.asyncio
async def test_global_tldr_is_concise_daily_brief_style() -> None:
    renderer = DailyRenderer()
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-brief-1",
                title="OpenAI 发布新推理模型并更新系统卡",
                url="https://example.com/openai-brief",
                content="OpenAI announced model updates with improved latency and reasoning quality.",
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "OpenAI", "source_category": "blog"},
            ),
            summary="OpenAI 新推理模型发布，性能与可用性同步提升。",
            keywords=["OpenAI", "reasoning", "system card"],
            score=0.93,
            detail="模型在速度和稳定性方面有明显提升。",
        ),
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-brief-2",
                title="MUSE 评测显示多模态模型在多轮攻击下存在高成功率风险",
                url="https://example.com/muse-brief",
                content="MUSE shows high attack success rates under multi-turn adversarial settings.",
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "Hugging Face Daily Papers", "source_category": "academic"},
            ),
            summary="MUSE 提示多模态模型在多轮攻击场景仍有明显安全短板。",
            keywords=["MUSE", "multimodal", "safety"],
            score=0.9,
            detail="多轮对抗策略可显著提高攻击成功率。",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    metadata = report.metadata or {}
    global_tldr = str(metadata.get("global_tldr") or "")

    assert global_tldr
    assert "从具体动向看" not in global_tldr
    assert "分水岭不会只看 benchmark" not in global_tldr
    assert len(global_tldr) <= 150


@pytest.mark.asyncio
async def test_daily_renderer_prefers_explicit_event_title() -> None:
    renderer = DailyRenderer()
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-cn-title",
                title="GPT-5.3 Instant System Card",
                url="https://example.com/system-card",
                content="System card update content.",
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "OpenAI", "source_category": "blog"},
            ),
            summary="OpenAI发布GPT-5.3 Instant系统卡，优化对话体验。",
            event_title="OpenAI 发布 GPT-5.3 Instant 系统卡",
            keywords=["OpenAI", "GPT-5.3", "system card"],
            score=0.9,
            detail="> OpenAI 发布系统卡更新。\\n\\n详细内容。",
            who="OpenAI",
            what="发布系统卡",
            when="2026-03-03",
            metrics=["26.8%"],
            availability="全量可用",
            unknowns="暂无训练数据截止日期",
            evidence="OpenAI 官方系统卡说明",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    metadata = report.metadata or {}
    events = metadata.get("events", [])

    assert len(events) == 1
    assert events[0]["title"] == "OpenAI 发布 GPT-5.3 Instant 系统卡"
    assert events[0]["event_title"] == "OpenAI 发布 GPT-5.3 Instant 系统卡"
    assert events[0]["who"] == "OpenAI"
    assert events[0]["metrics"] == ["26.8%"]
    assert "## [OpenAI 发布 GPT-5.3 Instant 系统卡]" in report.content


@pytest.mark.asyncio
async def test_daily_renderer_aggregates_same_model_release_across_sources() -> None:
    renderer = DailyRenderer()
    published_at = datetime(2026, 3, 6, 10, tzinfo=timezone.utc)
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id="gpt54-blog",
                title="OpenAI 逐步推送 GPT-5.4 Thinking 及 Pro 模型版本",
                url="https://openai.com/blog/gpt-5-4",
                content="Blog post",
                published_at=published_at,
                metadata={"source_name": "OpenAI Blog", "source_category": "blog"},
            ),
            event_title="OpenAI 逐步推送 GPT-5.4 Thinking 及 Pro 模型版本",
            summary="OpenAI 开始向用户推送 GPT-5.4 Thinking 与 Pro。",
            keywords=["OpenAI", "GPT-5.4", "Thinking"],
            importance="high",
            category="模型发布",
            detail="官方博客披露 GPT-5.4 Thinking 与 Pro 已开始面向用户逐步推送，并强调推理体验改进。",
        ),
        ProcessedArticle(
            raw=RawArticle(
                external_id="gpt54-system-card",
                title="OpenAI 宣称发布 GPT-5.4 模型提升效率",
                url="https://openai.com/system-card/gpt-5-4",
                content="System card",
                published_at=published_at,
                metadata={"source_name": "OpenAI System Card", "source_category": "blog"},
            ),
            event_title="OpenAI 宣称发布 GPT-5.4 模型提升效率",
            summary="系统卡补充了 GPT-5.4 的安全与评测边界。",
            keywords=["OpenAI", "GPT-5.4", "System Card"],
            importance="high",
            category="模型发布",
            detail="System card 补充了安全边界、评测方法和上线范围，属于同一轮 GPT-5.4 发布的补充说明。",
        ),
        ProcessedArticle(
            raw=RawArticle(
                external_id="gpt54-x",
                title="GPT-5.4 Thinking 与 Pro 现已在 ChatGPT 推送",
                url="https://x.com/openai/status/123",
                content="X post",
                published_at=published_at,
                metadata={"source_name": "OpenAI on X", "source_category": "social"},
            ),
            event_title="GPT-5.4 Thinking 与 Pro 现已在 ChatGPT 推送",
            summary="官方账号确认 ChatGPT 内已开始灰度开放。",
            keywords=["OpenAI", "GPT-5.4", "ChatGPT"],
            importance="high",
            category="模型发布",
            detail="官方社媒确认 ChatGPT 端已开始灰度推送，可视为同一发布事件的渠道补充。",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-06"))
    metadata = report.metadata or {}
    events = metadata.get("events", [])

    assert len(events) == 1
    assert len(report.article_ids or []) == 3
    assert "GPT-5.4" in events[0]["title"]
    assert events[0]["source_count"] == 3
    assert len(events[0]["source_links"]) == 3


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
async def test_daily_renderer_accepts_processed_events_directly() -> None:
    renderer = DailyRenderer()
    events = [
        ProcessedEvent(
            event_id="openai-gpt5",
            title="OpenAI 发布 GPT-5",
            summary="OpenAI 发布 GPT-5。",
            detail="OpenAI 发布 GPT-5，并公开系统卡与能力边界。",
            article_ids=["a1", "a2"],
            source_links=["https://openai.com/blog/gpt-5", "https://x.com/openai/status/1"],
            category="模型发布",
            keywords=["OpenAI", "GPT-5"],
            importance="high",
            source_count=2,
            source_name="OpenAI / OpenAI X",
            published_at="2026-03-06T10:00:00+00:00",
            who="OpenAI",
            what="发布 GPT-5",
            when="2026-03-06",
            metrics=["30%"],
            availability="公开可用",
            evidence="官方博客与社媒同步确认",
        )
    ]

    report = await renderer.render(events, RenderContext(date="2026-03-06"))
    metadata = report.metadata or {}

    assert report.article_ids == ["a1", "a2"]
    assert metadata["events"][0]["title"] == "OpenAI 发布 GPT-5"
    assert metadata["events"][0]["source_count"] == 2
    assert "OpenAI 发布 GPT-5" in report.content


def test_render_daily_report_prefers_explicit_global_summary() -> None:
    report = render_daily_report(
        events=[
            {
                "event_id": "event-1",
                "article_ids": ["a1"],
                "index": 1,
                "title": "OpenAI 发布 GPT-5",
                "event_title": "OpenAI 发布 GPT-5",
                "category": "模型发布",
                "one_line_tldr": "推理和代码能力继续增强。",
                "detail": "OpenAI 发布 GPT-5，并强调推理和代码能力进一步增强。",
                "keywords": ["OpenAI", "GPT-5"],
                "entities": ["OpenAI", "GPT-5"],
                "metrics": ["30%"],
                "source_links": ["https://openai.com/blog/gpt-5"],
                "source_count": 1,
                "source_name": "OpenAI",
                "published_at": "2026-03-06T10:00:00+00:00",
                "importance": "high",
                "who": "OpenAI",
                "what": "发布 GPT-5",
                "when": "2026-03-06",
                "availability": "公开可用",
                "unknowns": "",
                "evidence": "官方博客",
            }
        ],
        context=RenderContext(date="2026-03-06"),
        global_summary="这是外部生成的全局摘要。",
    )

    metadata = report.metadata or {}
    assert metadata["global_tldr"] == "这是外部生成的全局摘要。"
    assert "这是外部生成的全局摘要。" in report.content


@pytest.mark.asyncio
async def test_llm_category_is_used_even_when_importance_is_high() -> None:
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
            category="行业动态",
            detail="今日一家顶级 AI 公司宣布了重大技术突破，这一进展有望改变整个行业格局。详细的技术评测和竞品对比将在后续报告中呈现。",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    metadata = report.metadata or {}
    events = metadata.get("events", [])

    assert len(events) == 1
    assert events[0]["category"] == "行业动态"
    assert events[0]["importance"] == "high"


@pytest.mark.asyncio
async def test_missing_llm_category_falls_back_to_other() -> None:
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
    assert events[0]["category"] == "其他"


@pytest.mark.asyncio
async def test_open_source_tooling_keeps_llm_category() -> None:
    renderer = DailyRenderer()
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-oss-tooling",
                title='The Agency provides multi-role templates for Claude Code',
                url="https://github.com/example/agency",
                content="Open-source templates for agent workflow and Claude Code integration.",
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "GitHub", "source_category": "open_source"},
            ),
            summary='开源项目"The Agency"提供多角色 AI 智能体模板，支持集成至 Claude Code 优化工作流。',
            keywords=["Claude Code", "templates", "agent"],
            score=0.8,
            category="模型发布",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    metadata = report.metadata or {}
    events = metadata.get("events", [])

    assert len(events) == 1
    assert events[0]["category"] == "模型发布"


@pytest.mark.asyncio
async def test_open_source_model_weights_keeps_llm_category() -> None:
    renderer = DailyRenderer()
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-oss-model",
                title="IQuestLab open-sourced IQuest-Coder-V1 model weights",
                url="https://github.com/example/iquest-coder",
                content="IQuestLab released model weights for IQuest-Coder-V1.",
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "GitHub", "source_category": "open_source"},
            ),
            summary="IQuestLab开源IQuest-Coder-V1系列代码模型权重。",
            keywords=["IQuest-Coder-V1", "model weights", "open source"],
            score=0.8,
            category="开发生态",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    metadata = report.metadata or {}
    events = metadata.get("events", [])

    assert len(events) == 1
    assert events[0]["category"] == "开发生态"


@pytest.mark.asyncio
async def test_open_source_research_keeps_llm_category() -> None:
    renderer = DailyRenderer()
    articles = [
        ProcessedArticle(
            raw=RawArticle(
                external_id="evt-oss-paper",
                title="ProbCOPA: Humans and LLMs Diverge on Probabilistic Inferences",
                url="https://huggingface.co/papers/2602.23546",
                content="A new paper introduces ProbCOPA dataset and benchmark results.",
                published_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                metadata={"source_name": "Hugging Face Daily Papers", "source_category": "open_source"},
            ),
            summary="研究发布 ProbCOPA 数据集，评估概率推断能力。",
            keywords=["ProbCOPA", "dataset", "benchmark"],
            score=0.8,
            category="模型发布",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    metadata = report.metadata or {}
    events = metadata.get("events", [])

    assert len(events) == 1
    assert events[0]["category"] == "模型发布"


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
async def test_daily_report_content_matches_xml_like_event_sections() -> None:
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

    assert "## 概览" in content
    assert "> OpenAI 发布 API 更新并提升吞吐表现。" in content
    assert "相关链接：" in content
    assert "- https://example.com/meta" in content
    assert "来源：" not in content
    assert "发布时间：" not in content


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
async def test_official_release_keeps_llm_category() -> None:
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
            category="模型发布",
            detail="官方公告明确了可用性与接入渠道。",
        ),
    ]

    report = await renderer.render(articles, RenderContext(date="2026-03-02"))
    metadata = report.metadata or {}
    events = metadata.get("events", [])

    assert len(events) == 1
    assert events[0]["category"] == "模型发布"


@pytest.mark.asyncio
async def test_model_name_item_without_llm_category_falls_back_to_other() -> None:
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
    assert events[0]["category"] == "其他"
