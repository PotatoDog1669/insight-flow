from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.providers.filter import LLMFilterProvider
from app.providers.keywords import LLMKeywordProvider
from app.providers.report import LLMReportProvider


@pytest.mark.asyncio
async def test_llm_filter_provider_uses_llm_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"llm": 0, "codex": 0}

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        calls["llm"] += 1
        return {"keep_indices": [0]}

    async def _fake_codex(prompt: str, config: dict | None = None) -> dict:
        calls["codex"] += 1
        return {"keep_indices": [0]}

    monkeypatch.setattr("app.providers.filter.run_llm_json", _fake_llm)
    monkeypatch.setattr("app.providers.filter.run_codex_json", _fake_codex)

    provider = LLMFilterProvider()
    articles = [SimpleNamespace(title="OpenAI model update", content="AI release details")]
    output = await provider.run(payload={"articles": articles}, config={"model": "qwen3.5-397b-a17b", "api_key": "sk-demo"})

    assert len(output["articles"]) == 1
    assert calls["llm"] == 1
    assert calls["codex"] == 0


@pytest.mark.asyncio
async def test_llm_keywords_provider_uses_llm_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"llm": 0, "codex": 0}

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        calls["llm"] += 1
        return {"keywords": ["qwen", "llm"], "summary": "第三方网关模型总结测试", "importance": "normal", "detail": "detail"}

    async def _fake_codex(prompt: str, config: dict | None = None) -> dict:
        calls["codex"] += 1
        return {"keywords": ["codex"], "summary": "should not be used"}

    monkeypatch.setattr("app.providers.keywords.run_llm_json", _fake_llm)
    monkeypatch.setattr("app.providers.keywords.run_codex_json", _fake_codex)

    provider = LLMKeywordProvider()
    article = SimpleNamespace(title="Qwen 3.5 发布", content="支持 chat completions")
    output = await provider.run(payload={"article": article}, config={"model": "qwen3.5-397b-a17b", "api_key": "sk-demo"})

    assert output["keywords"] == ["qwen", "llm"]
    assert output["summary"] == "第三方网关模型总结测试"
    assert calls["llm"] == 1
    assert calls["codex"] == 0


@pytest.mark.asyncio
async def test_llm_report_provider_uses_llm_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"llm": 0, "codex": 0}

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        calls["llm"] += 1
        return {"title": "LLM report", "content": "LLM summary content", "global_tldr": "LLM TLDR"}

    async def _fake_codex(prompt: str, config: dict | None = None) -> dict:
        calls["codex"] += 1
        return {"title": "codex report", "content": "should not be used"}

    monkeypatch.setattr("app.providers.report.run_llm_json", _fake_llm)
    monkeypatch.setattr("app.providers.report.run_codex_json", _fake_codex)

    provider = LLMReportProvider()
    output = await provider.run(
        payload={
            "title": "Daily Report",
            "content": "raw markdown",
            "global_tldr": "raw tldr",
            "events": [{"title": "event"}],
        },
        config={"model": "qwen3.5-397b-a17b", "api_key": "sk-demo"},
    )

    assert output["title"] == "LLM report"
    assert output["content"] == "LLM summary content"
    assert output["global_tldr"] == "LLM TLDR"
    assert calls["llm"] == 1
    assert calls["codex"] == 0
