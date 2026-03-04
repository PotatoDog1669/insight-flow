from __future__ import annotations

import pytest

from app.collectors.base import RawArticle
from app.processors.pipeline import ProcessingPipeline


def _mock_codex_json_factory():
    async def _mock(prompt: str, config: dict | None = None) -> dict:
        lowered = prompt.lower()
        if "keep_indices" in lowered:
            return {"keep_indices": [0]}
        if '"keywords"' in prompt or "extract 5-8 high-signal keywords" in lowered:
            return {
                "keywords": ["openai", "agent", "reasoning"],
                "summary": "AI model update with meaningful impact.",
                "importance": "high",
                "detail": "OpenAI 发布了一款全新的推理模型，在数学推理基准测试中表现提升 12%，推理延迟降低 30%。这标志着大模型推理能力进入新阶段。",
            }
        return {}

    return _mock


@pytest.mark.asyncio
async def test_pipeline_filters_dedups_and_enriches(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_codex_json = _mock_codex_json_factory()
    monkeypatch.setattr("app.providers.filter.run_codex_json", mock_codex_json)
    monkeypatch.setattr("app.providers.keywords.run_codex_json", mock_codex_json)

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

    pipeline = ProcessingPipeline(score_threshold=0.3, routing_profile="codex_mvp_v1")
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
    assert pipeline.last_stage_trace["filter"]["provider"] == "agent_codex"
    assert pipeline.last_stage_trace["keywords"]["provider"] == "agent_codex"
    assert pipeline.last_stage_trace["summarizer"]["provider"] == "agent_codex"


@pytest.mark.asyncio
async def test_keywords_stage_does_not_fallback_to_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}

    class _FailingKeywordProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            attempts["count"] += 1
            raise RuntimeError("primary provider failed")

    calls: list[str] = []

    def fake_get_provider(stage: str, name: str):  # noqa: ANN201
        assert stage == "keywords"
        calls.append(name)
        assert name == "llm_openai"
        return _FailingKeywordProvider()

    monkeypatch.setattr("app.processors.pipeline.get_provider", fake_get_provider)

    pipeline = ProcessingPipeline(score_threshold=0.1, routing_profile="stable_v1")
    pipeline.routing_profile.providers["llm_openai"] = {"max_retry": 1}
    articles = [RawArticle(external_id="k1", title="a", url="https://example.com/1", content="text")]

    with pytest.raises(RuntimeError):
        await pipeline._extract_keywords_and_summaries_with_routing(articles)

    assert calls == ["llm_openai"]
    assert attempts["count"] == 2


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
        assert name == "agent_codex"
        return _FlakyFilterProvider()

    monkeypatch.setattr("app.processors.pipeline.get_provider", fake_get_provider)

    pipeline = ProcessingPipeline(score_threshold=0.1, routing_profile="codex_mvp_v1")
    pipeline.routing_profile.providers["agent_codex"] = {"max_retry": 2}

    output, provider_name = await pipeline._run_stage_with_retry(
        stage="filter",
        provider_name="agent_codex",
        payload={"articles": []},
    )

    assert provider_name == "agent_codex"
    assert output["articles"] == []
    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_run_stage_with_retry_raises_after_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}

    class _AlwaysFailProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            attempts["count"] += 1
            raise RuntimeError("still failing")

    def fake_get_provider(stage: str, name: str):  # noqa: ANN201
        assert stage == "filter"
        assert name == "agent_codex"
        return _AlwaysFailProvider()

    monkeypatch.setattr("app.processors.pipeline.get_provider", fake_get_provider)

    pipeline = ProcessingPipeline(score_threshold=0.1, routing_profile="codex_mvp_v1")
    pipeline.routing_profile.providers["agent_codex"] = {"max_retry": 1}

    with pytest.raises(RuntimeError, match="still failing"):
        await pipeline._run_stage_with_retry(
            stage="filter",
            provider_name="agent_codex",
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
        assert name == "agent_codex"
        return _CaptureFilterProvider()

    monkeypatch.setattr("app.processors.pipeline.get_provider", fake_get_provider)

    pipeline = ProcessingPipeline(score_threshold=0.1, routing_profile="codex_mvp_v1")
    pipeline.routing_profile.providers["agent_codex"] = {"auth_mode": "oauth", "oauth_token": "token-value"}

    output, provider_name = await pipeline._run_stage_with_retry(
        stage="filter",
        provider_name="agent_codex",
        payload={"articles": []},
    )

    assert provider_name == "agent_codex"
    assert output["articles"] == []
    assert captured_config["auth_mode"] == "oauth"
    assert captured_config["oauth_token"] == "token-value"
