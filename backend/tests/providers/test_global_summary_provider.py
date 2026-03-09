from __future__ import annotations

import pytest

from app.providers.global_summary import LLMGlobalSummaryProvider


@pytest.mark.asyncio
async def test_llm_global_summary_provider_uses_llm_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"llm": 0, "codex": 0}

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        calls["llm"] += 1
        return {"global_tldr": "今日主线是模型能力与交付效率同步升级。"}

    async def _fake_codex(prompt: str, config: dict | None = None) -> dict:
        calls["codex"] += 1
        return {"global_tldr": "should not be used"}

    monkeypatch.setattr("app.providers.global_summary.run_llm_json", _fake_llm)
    monkeypatch.setattr("app.providers.global_summary.run_codex_json", _fake_codex)

    provider = LLMGlobalSummaryProvider()
    output = await provider.run(
        payload={
            "events": [
                {
                    "title": "OpenAI 发布 GPT-5",
                    "category": "模型发布",
                    "summary": "推理和代码能力继续增强。",
                }
            ]
        },
        config={"model": "qwen3.5-397b-a17b", "api_key": "sk-demo"},
    )

    assert output["global_tldr"] == "今日主线是模型能力与交付效率同步升级。"
    assert calls["llm"] == 1
    assert calls["codex"] == 0


@pytest.mark.asyncio
async def test_llm_global_summary_provider_builds_prompt_from_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_prompt: dict[str, str] = {}

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        captured_prompt["text"] = prompt
        return {"global_tldr": "今日主线是模型能力与交付效率同步升级。"}

    monkeypatch.setattr("app.providers.global_summary.run_llm_json", _fake_llm)
    monkeypatch.setattr("app.providers.global_summary.run_codex_json", _fake_llm)

    provider = LLMGlobalSummaryProvider()
    await provider.run(
        payload={
            "events": [
                {
                    "title": "OpenAI 发布 GPT-5",
                    "category": "模型发布",
                    "summary": "推理和代码能力继续增强。",
                    "detail": ("detail " * 300) + "TAIL_MARKER",
                }
            ]
        },
        config={"model": "qwen3.5-397b-a17b", "api_key": "sk-demo"},
    )

    assert "OpenAI 发布 GPT-5" in captured_prompt["text"]
    assert "TAIL_MARKER" not in captured_prompt["text"]

