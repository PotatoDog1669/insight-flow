from __future__ import annotations

from app.processors.event_aggregator import aggregate_events


def _make_event(
    *,
    event_id: str,
    title: str,
    category: str,
    summary: str,
    keywords: list[str],
    source_name: str,
    source_link: str,
    published_at: str,
) -> dict:
    return {
        "event_id": event_id,
        "article_ids": [event_id],
        "index": 1,
        "title": title,
        "event_title": title,
        "category": category,
        "one_line_tldr": summary,
        "detail": f"{title} detail",
        "keywords": keywords,
        "entities": [source_name, *keywords[:2]],
        "metrics": [],
        "source_links": [source_link],
        "source_count": 1,
        "source_name": source_name,
        "published_at": published_at,
        "importance": "normal",
        "who": "",
        "what": "",
        "when": "",
        "availability": "",
        "unknowns": "",
        "evidence": "",
    }


def test_aggregate_events_merges_cross_source_same_event_even_when_category_differs() -> None:
    events = [
        _make_event(
            event_id="official-codex-security",
            title="OpenAI 推出 Codex Security 应用安全代理进入研究预览",
            category="开发生态",
            summary="OpenAI 推出 Codex Security 研究预览，结合前沿模型与自动验证提升代码安全扫描精度。",
            keywords=["Codex Security", "应用安全", "OpenAI", "代码扫描"],
            source_name="OpenAI",
            source_link="https://openai.com/index/codex-security-now-in-research-preview",
            published_at="2026-03-06T10:00:00+00:00",
        ),
        _make_event(
            event_id="x-codex-security",
            title="OpenAI 推出 Codex Security 安全代理研究预览",
            category="产品应用",
            summary="OpenAI 推出 Codex Security 应用安全代理，目前已进入研究预览阶段，旨在增强应用程序安全性。",
            keywords=["Codex Security", "应用安全", "研究预览", "AI 代理"],
            source_name="X",
            source_link="https://x.com/OpenAI/status/2029985250512920743",
            published_at="2026-03-06T18:19:33+00:00",
        ),
    ]

    aggregated = aggregate_events(events)

    assert len(aggregated) == 1
    assert aggregated[0]["source_count"] == 2
    assert set(aggregated[0]["source_links"]) == {
        "https://openai.com/index/codex-security-now-in-research-preview",
        "https://x.com/OpenAI/status/2029985250512920743",
    }


def test_aggregate_events_does_not_merge_same_source_distinct_papers() -> None:
    events = [
        _make_event(
            event_id="hf-interactive-benchmarks",
            title="交互式基准测试框架提出评估模型主动获取信息能力",
            category="技术与洞察",
            summary="研究团队提出交互式基准测试新范式，旨在通过互动过程评估模型推理能力与智能水平。",
            keywords=["交互式基准", "模型评估", "推理能力", "Interactive Benchmarks"],
            source_name="Hugging Face Daily Papers",
            source_link="https://huggingface.co/papers/2603.03942",
            published_at="2026-03-07T04:30:40+00:00",
        ),
        _make_event(
            event_id="hf-lightweight-visual-reasoning",
            title="轻量级视觉反馈模块提升机器人社交感知能力",
            category="技术与洞察",
            summary="新模块通过语言到视觉反馈闭环，显著提升 VLM 在机器人任务中的表现。",
            keywords=["视觉推理", "机器人", "VLM", "多模态交互"],
            source_name="Hugging Face Daily Papers",
            source_link="https://huggingface.co/papers/2602.23440",
            published_at="2026-03-07T04:30:40+00:00",
        ),
    ]

    aggregated = aggregate_events(events)

    assert len(aggregated) == 2
    assert {item["event_id"] for item in aggregated} == {
        "hf-interactive-benchmarks",
        "hf-lightweight-visual-reasoning",
    }


def test_aggregate_events_does_not_merge_same_feed_posts_about_related_anthropic_topics() -> None:
    events = [
        _make_event(
            event_id="x-anthropic-browsecomp",
            title="Anthropic 发现 Claude Opus 4.6 评估作弊",
            category="技术与洞察",
            summary="Anthropic 发现 Claude Opus 4.6 在评估中识别测试并解密答案，引发评估完整性担忧。",
            keywords=["Anthropic", "Claude Opus 4.6", "BrowseComp", "评估完整性"],
            source_name="X",
            source_link="https://x.com/AnthropicAI/status/2029999833717838016",
            published_at="2026-03-06T19:17:30+00:00",
        ),
        _make_event(
            event_id="x-anthropic-mozilla",
            title="Anthropic 联手 Mozilla 测试 Claude 发现漏洞",
            category="产品应用",
            summary="Anthropic 联合 Mozilla 测试 Claude，Opus 4.6 两周内发现 22 个 Firefox 漏洞。",
            keywords=["Anthropic", "Mozilla", "Claude", "Firefox", "安全漏洞", "Opus 4.6"],
            source_name="X",
            source_link="https://x.com/AnthropicAI/status/2029978909207617634",
            published_at="2026-03-06T17:54:21+00:00",
        ),
    ]

    aggregated = aggregate_events(events)

    assert len(aggregated) == 2


def test_aggregate_events_does_not_merge_cross_source_claude_stories_without_shared_topic() -> None:
    events = [
        _make_event(
            event_id="anthropic-browsecomp",
            title="Anthropic 披露 Claude Opus 4.6 评估作弊",
            category="技术与洞察",
            summary="Anthropic 披露 Claude Opus 4.6 在 BrowseComp 评估中识别测试并解密答案，引发完整性质疑。",
            keywords=["Anthropic", "Claude Opus 4.6", "BrowseComp", "评估完整性"],
            source_name="X",
            source_link="https://x.com/AnthropicAI/status/2029999833717838016",
            published_at="2026-03-06T19:17:30+00:00",
        ),
        _make_event(
            event_id="anthropic-firefox",
            title="Anthropic 携手 Mozilla 共修 Firefox 安全漏洞",
            category="产品应用",
            summary="Anthropic 联手 Mozilla 测试显示，Claude Opus 4.6 两周内发现 22 个 Firefox 漏洞。",
            keywords=["Anthropic", "Mozilla", "Claude Opus 4.6", "Firefox", "安全漏洞"],
            source_name="Anthropic",
            source_link="https://anthropic.com/news/mozilla-firefox-security",
            published_at="2026-03-07T03:00:00+00:00",
        ),
    ]

    aggregated = aggregate_events(events)

    assert len(aggregated) == 2
    assert {item["event_id"] for item in aggregated} == {
        "anthropic-browsecomp",
        "anthropic-firefox",
    }


def test_aggregate_events_does_not_merge_github_project_with_claude_news() -> None:
    events = [
        _make_event(
            event_id="github-webnovel-writer",
            title="基于 Claude Code 的 Webnovel Writer 系统",
            category="开发生态",
            summary="开发者发布基于 Claude Code 的长篇网文创作系统 Webnovel Writer，支持长周期连载。",
            keywords=["Webnovel Writer", "Claude Code", "AI 写作", "RAG"],
            source_name="GitHub Trending Daily",
            source_link="https://github.com/lingfengQAQ/webnovel-writer",
            published_at="2026-03-07T08:00:00+00:00",
        ),
        _make_event(
            event_id="anthropic-browsecomp",
            title="Anthropic 披露 Claude Opus 4.6 评估作弊",
            category="技术与洞察",
            summary="Anthropic 披露 Claude Opus 4.6 在 BrowseComp 评估中作弊，引发对评估完整性的质疑。",
            keywords=["Anthropic", "Claude Opus 4.6", "BrowseComp", "评估完整性"],
            source_name="X",
            source_link="https://x.com/AnthropicAI/status/2029999833717838016",
            published_at="2026-03-06T19:17:30+00:00",
        ),
    ]

    aggregated = aggregate_events(events)

    assert len(aggregated) == 2
    assert {item["event_id"] for item in aggregated} == {
        "github-webnovel-writer",
        "anthropic-browsecomp",
    }
