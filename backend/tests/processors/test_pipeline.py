from __future__ import annotations

import asyncio

import pytest

from app.collectors.base import RawArticle
from app.processors.event_models import CandidateCluster, PipelineOutput, ProcessedEvent
from app.processors.pipeline import ProcessingPipeline


def _mock_codex_json_factory():
    async def _mock(prompt: str, config: dict | None = None) -> dict:
        lowered = prompt.lower()
        if "keep_indices" in lowered:
            return {"keep_indices": [0]}
        if '"keywords"' in prompt or "extract 5-8 high-signal keywords" in lowered:
            return {
                "event_title": "OpenAI 发布新推理模型",
                "keywords": ["openai", "agent", "reasoning"],
                "summary": "AI model update with meaningful impact.",
                "importance": "high",
                "category": "模型发布",
                "detail": "OpenAI 发布了一款全新的推理模型，在数学推理基准测试中表现提升 12%，推理延迟降低 30%。这标志着大模型推理能力进入新阶段。",
                "who": "OpenAI",
                "what": "发布新推理模型",
                "when": "2026-03-05",
                "metrics": ["12%", "30%"],
                "availability": "公开可用",
                "unknowns": "暂无模型参数规模",
                "evidence": "官方公告披露 benchmark 提升",
            }
        return {}

    return _mock


def _make_raw_article(index: int) -> RawArticle:
    return RawArticle(
        external_id=f"article-{index}",
        title=f"Article {index}",
        url=f"https://example.com/{index}",
        content=f"content-{index}",
        metadata={"source_name": "Replay Source"},
    )


@pytest.mark.asyncio
async def test_pipeline_filters_dedups_and_enriches(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_codex_json = _mock_codex_json_factory()
    monkeypatch.setattr("app.providers.filter.run_llm_json", mock_codex_json)
    monkeypatch.setattr("app.providers.keywords.run_llm_json", mock_codex_json)

    raw_items = [
        RawArticle(
            external_id="1",
            title="OpenAI 发布新模型",
            url="https://example.com/a1",
            content="This AI model improves reasoning and coding performance significantly.",
        ),
        RawArticle(
            external_id="2",
            title="OpenAI 发布新模型",
            url="https://example.com/a1-dup",
            content="Duplicate entry with similar information.",
        ),
        RawArticle(
            external_id="3",
            title="Cooking recipe of the day",
            url="https://example.com/other",
            content="How to cook pasta with tomato sauce.",
        ),
    ]

    pipeline = ProcessingPipeline(score_threshold=0.3, routing_profile="stable_v1")
    processed = await pipeline.process(raw_items)

    assert len(processed) == 1
    item = processed[0]
    assert item.raw.external_id == "1"
    assert item.summary
    assert item.keywords
    assert item.score == 1.0
    assert item.importance == "high"
    assert item.detail
    assert len(item.detail) >= 50
    assert item.event_title == "OpenAI 发布新推理模型"
    assert item.category == "模型发布"
    assert item.who == "OpenAI"
    assert item.metrics == ["12%", "30%"]
    assert pipeline.last_stage_trace["filter"]["provider"] == "llm_openai"
    assert pipeline.last_stage_trace["keywords"]["provider"] == "llm_openai"
    assert pipeline.last_stage_trace["summarizer"]["provider"] == "llm_openai"


@pytest.mark.asyncio
async def test_keywords_stage_falls_back_to_rule_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"primary": 0, "fallback": 0}
    calls: list[str] = []

    class _FailingKeywordProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            attempts["primary"] += 1
            raise RuntimeError("primary provider failed")

    class _FallbackKeywordProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            attempts["fallback"] += 1
            return {
                "event_title": "规则回退命中",
                "keywords": ["fallback"],
                "summary": "回退成功。",
                "importance": "normal",
                "category": "行业动态",
                "detail": "规则回退输出了可用摘要。",
                "who": "Fallback",
                "what": "关键词提取回退",
                "when": "",
                "metrics": [],
                "availability": "",
                "unknowns": "",
                "evidence": "fallback",
            }

    def fake_get_provider(stage: str, name: str):  # noqa: ANN201
        assert stage == "keywords"
        calls.append(name)
        if name == "llm_openai":
            return _FailingKeywordProvider()
        if name == "rule":
            return _FallbackKeywordProvider()
        raise KeyError(name)

    monkeypatch.setattr("app.processors.pipeline.get_provider", fake_get_provider)

    pipeline = ProcessingPipeline(score_threshold=0.1, routing_profile="stable_v1")
    pipeline.routing_profile.providers["llm_openai"] = {"max_retry": 1}
    pipeline.routing_profile.providers["rule"] = {"max_retry": 0}
    articles = [RawArticle(external_id="k1", title="a", url="https://example.com/1", content="text")]

    (
        keywords_list,
        summaries,
        _importances,
        _details,
        _categories,
        _event_titles,
        _whos,
        _whats,
        _whens,
        _metrics,
        _availabilities,
        _unknowns,
        _evidences,
    ) = await pipeline._extract_keywords_and_summaries_with_routing(articles)

    assert keywords_list == [["fallback"]]
    assert summaries == ["回退成功。"]
    assert calls == ["llm_openai", "rule"]
    assert attempts["primary"] == 2
    assert attempts["fallback"] == 1


@pytest.mark.asyncio
async def test_run_stage_with_retry_retries_same_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}

    class _FlakyFilterProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise RuntimeError("transient")
            return {"articles": payload.get("articles", [])}

    def fake_get_provider(stage: str, name: str):  # noqa: ANN201
        assert stage == "filter"
        assert name == "llm_openai"
        return _FlakyFilterProvider()

    monkeypatch.setattr("app.processors.pipeline.get_provider", fake_get_provider)

    pipeline = ProcessingPipeline(score_threshold=0.1, routing_profile="stable_v1")
    pipeline.routing_profile.providers["llm_openai"] = {"max_retry": 2}

    output, provider_name = await pipeline._run_stage_with_retry(
        stage="filter",
        provider_name="llm_openai",
        payload={"articles": []},
    )

    assert provider_name == "llm_openai"
    assert output["articles"] == []
    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_run_stage_with_retry_falls_back_to_secondary_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"primary": 0, "fallback": 0}
    calls: list[str] = []

    class _AlwaysFailProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            attempts["primary"] += 1
            raise RuntimeError("still failing")

    class _FallbackFilterProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            attempts["fallback"] += 1
            return {"articles": payload.get("articles", [])}

    def fake_get_provider(stage: str, name: str):  # noqa: ANN201
        assert stage == "filter"
        calls.append(name)
        if name == "llm_openai":
            return _AlwaysFailProvider()
        if name == "rule":
            return _FallbackFilterProvider()
        raise KeyError(name)

    monkeypatch.setattr("app.processors.pipeline.get_provider", fake_get_provider)

    pipeline = ProcessingPipeline(score_threshold=0.1, routing_profile="stable_v1")
    pipeline.routing_profile.providers["llm_openai"] = {"max_retry": 1}
    pipeline.routing_profile.providers["rule"] = {"max_retry": 0}

    output, provider_name = await pipeline._run_stage_with_retry(
        stage="filter",
        provider_name="llm_openai",
        payload={"articles": []},
        fallback_providers=["rule"],
    )

    assert provider_name == "rule"
    assert output["articles"] == []
    assert calls == ["llm_openai", "rule"]
    assert attempts["primary"] == 2
    assert attempts["fallback"] == 1


@pytest.mark.asyncio
async def test_run_stage_with_retry_raises_after_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}

    class _AlwaysFailProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            attempts["count"] += 1
            raise RuntimeError("still failing")

    def fake_get_provider(stage: str, name: str):  # noqa: ANN201
        assert stage == "filter"
        assert name == "llm_openai"
        return _AlwaysFailProvider()

    monkeypatch.setattr("app.processors.pipeline.get_provider", fake_get_provider)

    pipeline = ProcessingPipeline(score_threshold=0.1, routing_profile="stable_v1")
    pipeline.routing_profile.providers["llm_openai"] = {"max_retry": 1}

    with pytest.raises(RuntimeError, match="still failing"):
        await pipeline._run_stage_with_retry(
            stage="filter",
            provider_name="llm_openai",
            payload={"articles": []},
        )

    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_run_stage_with_retry_passes_provider_config(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_config: dict = {}

    class _CaptureFilterProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            captured_config.update(config or {})
            return {"articles": payload.get("articles", [])}

    def fake_get_provider(stage: str, name: str):  # noqa: ANN201
        assert stage == "filter"
        assert name == "llm_openai"
        return _CaptureFilterProvider()

    monkeypatch.setattr("app.processors.pipeline.get_provider", fake_get_provider)

    pipeline = ProcessingPipeline(score_threshold=0.1, routing_profile="stable_v1")
    pipeline.routing_profile.providers["llm_openai"] = {"auth_mode": "oauth", "oauth_token": "token-value"}

    output, provider_name = await pipeline._run_stage_with_retry(
        stage="filter",
        provider_name="llm_openai",
        payload={"articles": []},
    )

    assert provider_name == "llm_openai"
    assert output["articles"] == []
    assert captured_config["auth_mode"] == "oauth"
    assert captured_config["oauth_token"] == "token-value"


@pytest.mark.asyncio
async def test_pipeline_downgrades_weak_social_input_to_compact_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    class _KeepAllFilterProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            return {"articles": payload.get("articles", [])}

    class _WeakKeywordsProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            return {
                "event_title": "Anthropic CEO 发布声明",
                "keywords": ["Anthropic", "Dario Amodei"],
                "summary": "Anthropic CEO 发布一则声明链接。",
                "importance": "normal",
                "category": "行业动态",
                "detail": "具体内容：未知。影响范围：待定。暂无信息，需等待更多信源。",
                "who": "Anthropic",
                "what": "发布声明",
                "when": "",
                "metrics": [],
                "availability": "暂无信息",
                "unknowns": "无明显信息缺口",
                "evidence": "原始输入只有一句话和链接",
            }

    def fake_get_provider(stage: str, name: str):  # noqa: ANN201
        if stage == "filter":
            return _KeepAllFilterProvider()
        if stage == "keywords":
            return _WeakKeywordsProvider()
        raise KeyError(name)

    monkeypatch.setattr("app.processors.pipeline.get_provider", fake_get_provider)

    pipeline = ProcessingPipeline(score_threshold=0.1, routing_profile="stable_v1")
    processed = await pipeline.process(
        [
            RawArticle(
                external_id="weak-social",
                title="A statement from Anthropic CEO Dario Amodei: https://t.co/test",
                url="https://x.com/example/status/1",
                content="A statement from Anthropic CEO Dario Amodei: https://t.co/test",
                metadata={"source_category": "social", "source_name": "X"},
            )
        ]
    )

    assert len(processed) == 1
    assert processed[0].detail_mode == "compact"
    assert "未知" not in processed[0].detail
    assert "待定" not in processed[0].detail
    assert len(processed[0].detail) < 80


@pytest.mark.asyncio
async def test_pipeline_records_candidate_cluster_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    class _KeepAllFilterProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            return {"articles": payload.get("articles", [])}

    class _KeywordsProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            return {
                "event_title": "OpenAI 发布 GPT-5",
                "keywords": ["OpenAI", "GPT-5"],
                "summary": "OpenAI 发布 GPT-5。",
                "importance": "high",
                "category": "模型发布",
                "detail": "OpenAI 发布 GPT-5，并说明其推理与代码能力进一步提升。",
                "who": "OpenAI",
                "what": "发布 GPT-5",
                "when": "2026-03-06",
                "metrics": ["30%"],
                "availability": "公开可用",
                "unknowns": "",
                "evidence": "博客与媒体报道",
            }

    def fake_get_provider(stage: str, name: str):  # noqa: ANN201
        if stage == "filter":
            return _KeepAllFilterProvider()
        if stage == "keywords":
            return _KeywordsProvider()
        raise KeyError(name)

    monkeypatch.setattr("app.processors.pipeline.get_provider", fake_get_provider)

    pipeline = ProcessingPipeline(score_threshold=0.1, routing_profile="stable_v1")
    await pipeline.process(
        [
            RawArticle(
                external_id="a1",
                title="OpenAI 发布 GPT-5 reasoning 模型",
                url="https://openai.com/blog/gpt-5",
                content="GPT-5 reasoning improves coding quality and latency.",
                metadata={"source_id": "openai-blog", "source_name": "OpenAI", "source_category": "blog"},
            ),
            RawArticle(
                external_id="a2",
                title="GPT-5 launch: OpenAI ships new reasoning model",
                url="https://news.example.com/openai-gpt5",
                content="OpenAI ships GPT-5 with stronger reasoning and lower latency.",
                metadata={"source_id": "news-site", "source_name": "News Site", "source_category": "blog"},
            ),
        ]
    )

    assert pipeline.last_stage_trace["candidate_cluster"]["provider"] == "candidate_rule"
    assert pipeline.last_stage_trace["candidate_cluster"]["input"] == 2
    assert pipeline.last_stage_trace["candidate_cluster"]["output"] == 1


def test_processed_event_keeps_article_lineage() -> None:
    event = ProcessedEvent(
        event_id="openai-gpt5",
        title="OpenAI 发布 GPT-5",
        summary="OpenAI 发布 GPT-5。",
        detail="OpenAI 发布 GPT-5，并公开系统卡与能力边界。",
        article_ids=["a1", "a2"],
        source_links=["https://openai.com/blog/gpt-5", "https://x.com/openai/status/1"],
    )

    assert event.article_ids == ["a1", "a2"]
    assert event.source_links == ["https://openai.com/blog/gpt-5", "https://x.com/openai/status/1"]
    assert event.normalized_source_count() == 2


def test_pipeline_output_defaults_empty_stage_traces() -> None:
    output = PipelineOutput(events=[])

    assert output.events == []
    assert output.article_stage_trace == {}
    assert output.event_stage_trace == {}


@pytest.mark.asyncio
async def test_run_keywords_stage_respects_stage_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    class _TrackingKeywordProvider:
        def __init__(self) -> None:
            self.active = 0
            self.max_active = 0

        async def run(self, payload: dict, config: dict | None = None) -> dict:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.02)
            article = payload["article"]
            self.active -= 1
            return {
                "event_title": article.title,
                "keywords": [article.external_id],
                "summary": f"{article.external_id} summary",
                "importance": "normal",
                "category": "技术与洞察",
                "detail": f"{article.external_id} detail",
                "who": "provider",
                "what": article.title,
                "when": "2026-03-07",
                "metrics": [],
                "availability": "public",
                "unknowns": "",
                "evidence": "tracking",
            }

    provider = _TrackingKeywordProvider()

    def fake_get_provider(stage: str, name: str):  # noqa: ANN201
        assert stage == "keywords"
        assert name == "llm_openai"
        return provider

    monkeypatch.setattr("app.processors.pipeline.get_provider", fake_get_provider)

    pipeline = ProcessingPipeline(score_threshold=0.1, routing_profile="stable_v1")
    pipeline.set_stage_concurrency(3)
    articles = [_make_raw_article(index) for index in range(4)]

    processed, trace = await pipeline.run_keywords_stage(articles)

    assert len(processed) == 4
    assert provider.max_active >= 2
    assert trace["stage_concurrency"] == 3
    assert pipeline.last_stage_trace["keywords"]["stage_concurrency"] == 3


@pytest.mark.asyncio
async def test_run_event_extract_stage_respects_stage_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    class _TrackingEventProvider:
        def __init__(self) -> None:
            self.active = 0
            self.max_active = 0

        async def run(self, payload: dict, config: dict | None = None) -> dict:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.02)
            event_input = payload["event_input"]
            self.active -= 1
            return {
                "event_title": event_input.primary_article.title,
                "keywords": [event_input.primary_article.external_id],
                "summary": f"{event_input.primary_article.external_id} summary",
                "importance": "high",
                "category": "模型发布",
                "detail": f"{event_input.primary_article.external_id} detail",
                "who": "provider",
                "what": event_input.primary_article.title,
                "when": "2026-03-07",
                "metrics": [],
                "availability": "public",
                "unknowns": "",
                "evidence": "tracking",
            }

    provider = _TrackingEventProvider()

    def fake_get_provider(stage: str, name: str):  # noqa: ANN201
        assert stage == "keywords"
        assert name == "llm_openai"
        return provider

    monkeypatch.setattr("app.processors.pipeline.get_provider", fake_get_provider)

    pipeline = ProcessingPipeline(score_threshold=0.1, routing_profile="stable_v1")
    pipeline.set_stage_concurrency(3)
    candidate_clusters = [
        CandidateCluster(
            cluster_id=f"cluster-{index}",
            articles=[_make_raw_article(index)],
            source_ids=[f"source-{index}"],
            source_names=["Replay Source"],
        )
        for index in range(4)
    ]

    events, trace = await pipeline.run_event_extract_stage(candidate_clusters)

    assert len(events) == 4
    assert provider.max_active >= 2
    assert trace["stage_concurrency"] == 3
    assert pipeline.last_stage_trace["event_extract"]["stage_concurrency"] == 3
