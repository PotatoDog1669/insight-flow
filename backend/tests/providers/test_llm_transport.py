from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.providers.filter import LLMFilterProvider
from app.providers.filter import CodexFilterProvider
from app.providers.global_summary import CodexGlobalSummaryProvider
from app.providers.keywords import LLMKeywordProvider
from app.providers.keywords import CodexKeywordProvider
from app.providers.report import LLMReportProvider
from app.providers.report import CodexReportProvider


@pytest.mark.asyncio
async def test_llm_filter_provider_uses_llm_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"llm": 0}

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        calls["llm"] += 1
        return {"keep_indices": [0]}

    monkeypatch.setattr("app.providers.filter.run_llm_json", _fake_llm)

    provider = LLMFilterProvider()
    articles = [SimpleNamespace(title="OpenAI model update", content="AI release details")]
    output = await provider.run(payload={"articles": articles}, config={"model": "qwen3.5-397b-a17b", "api_key": "sk-demo"})

    assert len(output["articles"]) == 1
    assert calls["llm"] == 1


@pytest.mark.asyncio
async def test_llm_keywords_provider_uses_llm_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"llm": 0}

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        calls["llm"] += 1
        return {
            "event_title": "Qwen 3.5 发布更新",
            "keywords": ["qwen", "llm"],
            "summary": "第三方网关模型总结测试",
            "importance": "normal",
            "category": "模型发布",
            "detail": "detail",
            "who": "阿里云",
            "what": "发布模型更新",
            "when": "2026-03-05",
            "metrics": ["12%", "$0.25/M"],
            "availability": "逐步开放",
            "unknowns": "暂无公开参数规模",
            "evidence": "官方博客更新说明",
        }

    monkeypatch.setattr("app.providers.keywords.run_llm_json", _fake_llm)

    provider = LLMKeywordProvider()
    article = SimpleNamespace(title="Qwen 3.5 发布", content="支持 chat completions")
    output = await provider.run(payload={"article": article}, config={"model": "qwen3.5-397b-a17b", "api_key": "sk-demo"})

    assert output["keywords"] == ["qwen", "llm"]
    assert output["event_title"] == "Qwen 3.5 发布更新"
    assert output["summary"] == "第三方网关模型总结测试"
    assert output["category"] == "模型发布"
    assert output["who"] == "阿里云"
    assert output["metrics"] == ["12%", "$0.25/M"]
    assert calls["llm"] == 1


@pytest.mark.asyncio
async def test_llm_report_provider_uses_llm_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"llm": 0}

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        calls["llm"] += 1
        return {"title": "LLM report", "content": "LLM summary content", "global_tldr": "LLM TLDR"}

    monkeypatch.setattr("app.providers.report.run_llm_json", _fake_llm)

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
    assert output["content"] == "raw markdown"
    assert output["global_tldr"] == "LLM TLDR"
    assert calls["llm"] == 1


@pytest.mark.asyncio
async def test_llm_report_provider_builds_prompt_from_event_payload_not_full_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_prompt: dict[str, str] = {}

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        captured_prompt["text"] = prompt
        return {"title": "LLM report", "content": "LLM summary content", "global_tldr": "LLM TLDR"}

    monkeypatch.setattr("app.providers.report.run_llm_json", _fake_llm)

    provider = LLMReportProvider()
    tail_marker = "TAIL_MARKER_SHOULD_EXIST"
    long_content = ("long report content " * 450) + tail_marker
    await provider.run(
        payload={
            "title": "Daily Report",
            "content": long_content,
            "global_tldr": "raw tldr",
            "events": [{"title": "event one", "category": "模型发布", "one_line_tldr": "summary"}],
        },
        config={"model": "qwen3.5-397b-a17b", "api_key": "sk-demo"},
    )

    assert tail_marker not in captured_prompt["text"]
    assert "event one" in captured_prompt["text"]


@pytest.mark.asyncio
async def test_llm_report_provider_removes_count_and_distribution_style_tldr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        return {
            "title": "LLM report",
            "global_tldr": (
                "今日共收录 10 条 AI 关键进展。"
                "分类分布：要闻 1 条，模型发布 6 条，开发生态 2 条。"
                "核心突破：OpenAI 联合学界推进量子引力计算。"
                "趋势洞察：下一阶段焦点转向工程化成本与真实场景转化率。"
            ),
        }

    monkeypatch.setattr("app.providers.report.run_llm_json", _fake_llm)
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

    assert "共收录" not in output["global_tldr"]
    assert "分类分布" not in output["global_tldr"]
    assert "要闻 1 条" not in output["global_tldr"]
    assert "核心突破" not in output["global_tldr"]
    assert "趋势洞察" not in output["global_tldr"]
    assert "OpenAI 联合学界推进量子引力计算" in output["global_tldr"]


@pytest.mark.asyncio
async def test_codex_filter_provider_uses_codex_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"codex": 0}

    async def _fake_codex(prompt: str, config: dict | None = None) -> dict:
        calls["codex"] += 1
        return {"keep_indices": [0]}

    monkeypatch.setattr("app.providers.filter.run_codex_json", _fake_codex)

    provider = CodexFilterProvider()
    articles = [SimpleNamespace(title="Codex model update", content="AI release details")]
    output = await provider.run(payload={"articles": articles}, config={"model": "gpt-5-codex", "api_key": "sk-demo"})

    assert len(output["articles"]) == 1
    assert calls["codex"] == 1


@pytest.mark.asyncio
async def test_codex_keywords_provider_uses_codex_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"codex": 0}

    async def _fake_codex(prompt: str, config: dict | None = None) -> dict:
        calls["codex"] += 1
        return {
            "event_title": "Codex 发布更新",
            "keywords": ["codex", "coding"],
            "summary": "Codex workflow 测试",
            "importance": "normal",
            "category": "模型发布",
        }

    monkeypatch.setattr("app.providers.keywords.run_codex_json", _fake_codex)

    provider = CodexKeywordProvider()
    article = SimpleNamespace(title="Codex 发布", content="支持 responses workflow")
    output = await provider.run(payload={"article": article}, config={"model": "gpt-5-codex", "api_key": "sk-demo"})

    assert output["keywords"] == ["codex", "coding"]
    assert output["event_title"] == "Codex 发布更新"
    assert calls["codex"] == 1


@pytest.mark.asyncio
async def test_codex_report_provider_uses_codex_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"codex": 0}

    async def _fake_codex(prompt: str, config: dict | None = None) -> dict:
        calls["codex"] += 1
        return {"title": "Codex report", "global_tldr": "Codex TLDR"}

    monkeypatch.setattr("app.providers.report.run_codex_json", _fake_codex)

    provider = CodexReportProvider()
    output = await provider.run(
        payload={
            "title": "Daily Report",
            "content": "raw markdown",
            "global_tldr": "raw tldr",
            "events": [{"title": "event"}],
        },
        config={"model": "gpt-5-codex", "api_key": "sk-demo"},
    )

    assert output["title"] == "Codex report"
    assert output["content"] == "raw markdown"
    assert output["global_tldr"] == "Codex TLDR"
    assert calls["codex"] == 1


@pytest.mark.asyncio
async def test_codex_global_summary_provider_uses_codex_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"codex": 0}

    async def _fake_codex(prompt: str, config: dict | None = None) -> dict:
        calls["codex"] += 1
        return {"global_tldr": "Codex 今日焦点是 workflow 一体化。"}

    monkeypatch.setattr("app.providers.global_summary.run_codex_json", _fake_codex)

    provider = CodexGlobalSummaryProvider()
    output = await provider.run(
        payload={"events": [{"title": "event one", "one_line_tldr": "summary"}]},
        config={"model": "gpt-5-codex", "api_key": "sk-demo"},
    )

    assert "workflow 一体化" in output["global_tldr"]
    assert calls["codex"] == 1
