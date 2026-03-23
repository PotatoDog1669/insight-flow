from __future__ import annotations

import pytest

from app.providers.paper_note import CodexPaperNoteProvider, LLMPaperNoteProvider


@pytest.mark.asyncio
async def test_llm_paper_note_provider_uses_llm_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"llm": 0}

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        calls["llm"] += 1
        return {
            "title": "World Model Policy",
            "summary": "这篇工作把 world model 和 policy 学习的接口真正打通了。",
            "core_contributions": ["统一了训练目标"],
            "problem_background": ["现有方法推理开销高"],
            "method_breakdown": ["分层建模"],
            "figure_notes": ["图 1 展示了整体训练流程"],
            "experiments": ["在多个控制任务上优于 baseline"],
            "strengths": ["结构完整"],
            "limitations": ["真实世界验证有限"],
            "related_reading": ["DreamerV3"],
            "next_steps": ["关注真实机器人迁移"],
        }

    monkeypatch.setattr("app.providers.paper_note.run_llm_json", _fake_llm)
    provider = LLMPaperNoteProvider()
    output = await provider.run(
        payload={"paper": {"paper_identity": "2603.12345", "paper_slug": "world-model-policy", "title": "World Model Policy"}},
        config={"model": "gpt-4o-mini", "api_key": "sk-demo"},
    )

    assert output["title"] == "World Model Policy"
    assert calls["llm"] == 1


@pytest.mark.asyncio
async def test_codex_paper_note_provider_uses_codex_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"codex": 0}

    async def _fake_codex(prompt: str, config: dict | None = None) -> dict:
        calls["codex"] += 1
        return {
            "title": "World Model Policy",
            "summary": "本期值得关注它如何把方法接口做得更统一。",
            "core_contributions": ["统一了训练目标"],
            "problem_background": ["现有方法推理开销高"],
            "method_breakdown": ["分层建模"],
            "figure_notes": ["图 1 展示了整体训练流程"],
            "experiments": ["在多个控制任务上优于 baseline"],
            "strengths": ["结构完整"],
            "limitations": ["真实世界验证有限"],
            "related_reading": ["DreamerV3"],
            "next_steps": ["关注真实机器人迁移"],
        }

    monkeypatch.setattr("app.providers.paper_note.run_codex_json", _fake_codex)
    provider = CodexPaperNoteProvider()
    output = await provider.run(
        payload={"paper": {"paper_identity": "2603.12345", "paper_slug": "world-model-policy", "title": "World Model Policy"}},
        config={"model": "gpt-5-codex", "api_key": "sk-demo"},
    )

    assert output["paper_identity"] == "2603.12345"
    assert calls["codex"] == 1
