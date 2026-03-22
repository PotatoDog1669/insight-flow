from __future__ import annotations

import pytest

from app.providers.paper_note import LLMPaperNoteProvider


@pytest.mark.asyncio
async def test_llm_paper_note_provider_builds_prompt_from_selected_paper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_prompt: dict[str, str] = {}

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        captured_prompt["text"] = prompt
        return {
            "title": "World Model Policy",
            "summary": "这篇工作把 world model 和 policy 学习的接口真正打通了。",
            "core_contributions": ["统一了训练目标", "降低了规划成本"],
            "problem_background": ["现有方法推理开销高"],
            "method_breakdown": ["分层建模", "基于 latent 的规划"],
            "figure_notes": ["图 1 展示了整体训练流程"],
            "experiments": ["在多个控制任务上优于 baseline"],
            "strengths": ["结构完整"],
            "limitations": ["真实世界验证有限"],
            "related_reading": ["DreamerV3", "TD-MPC2"],
            "next_steps": ["关注真实机器人迁移"],
        }

    monkeypatch.setattr("app.providers.paper_note.run_llm_json", _fake_llm)
    provider = LLMPaperNoteProvider()
    tail_marker = "TAIL_MARKER_SHOULD_NOT_APPEAR"

    await provider.run(
        payload={
            "paper": {
                "paper_identity": "2603.12345",
                "paper_slug": "world-model-policy",
                "title": "World Model Policy",
                "summary": "A paper about world model policy learning.",
                "detail": ("detail " * 300) + tail_marker,
                "authors": ["Alice", "Bob"],
                "affiliations": ["Example Lab"],
                "links": ["https://arxiv.org/abs/2603.12345"],
            }
        },
        config={"model": "gpt-4o-mini", "api_key": "sk-demo"},
    )

    assert "World Model Policy" in captured_prompt["text"]
    assert "2603.12345" in captured_prompt["text"]
    assert tail_marker not in captured_prompt["text"]


@pytest.mark.asyncio
async def test_llm_paper_note_provider_normalizes_note_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        return {
            "title": " World Model Policy ",
            "summary": " 这篇工作把 world model 和 policy 学习的接口真正打通了。 ",
            "core_contributions": ["统一了训练目标", "", "统一了训练目标", "降低了规划成本"],
            "problem_background": "现有方法推理开销高",
            "method_breakdown": ["分层建模", "基于 latent 的规划"],
            "figure_notes": [" 图 1 展示了整体训练流程 "],
            "experiments": [" 在多个控制任务上优于 baseline "],
            "strengths": ["结构完整"],
            "limitations": ["真实世界验证有限"],
            "related_reading": ["DreamerV3", "DreamerV3", "TD-MPC2"],
            "next_steps": ["关注真实机器人迁移"],
        }

    monkeypatch.setattr("app.providers.paper_note.run_llm_json", _fake_llm)
    provider = LLMPaperNoteProvider()
    output = await provider.run(
        payload={
            "paper": {
                "paper_identity": "2603.12345",
                "paper_slug": "world-model-policy",
                "title": "World Model Policy",
                "authors": ["Alice", "Bob"],
                "affiliations": ["Example Lab"],
                "links": ["https://arxiv.org/abs/2603.12345"],
            }
        },
        config={"model": "gpt-4o-mini", "api_key": "sk-demo"},
    )

    assert output["paper_identity"] == "2603.12345"
    assert output["paper_slug"] == "world-model-policy"
    assert output["title"] == "World Model Policy"
    assert output["authors"] == ["Alice", "Bob"]
    assert output["affiliations"] == ["Example Lab"]
    assert output["links"] == ["https://arxiv.org/abs/2603.12345"]
    assert output["summary"].startswith("这篇工作把 world model")
    assert output["core_contributions"] == ["统一了训练目标", "降低了规划成本"]
    assert output["problem_background"] == ["现有方法推理开销高"]
    assert output["related_reading"] == ["DreamerV3", "TD-MPC2"]


@pytest.mark.asyncio
async def test_llm_paper_note_provider_rejects_incomplete_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        return {"title": "World Model Policy"}

    monkeypatch.setattr("app.providers.paper_note.run_llm_json", _fake_llm)
    provider = LLMPaperNoteProvider()

    with pytest.raises(ValueError, match="Missing summary"):
        await provider.run(
            payload={
                "paper": {
                    "paper_identity": "2603.12345",
                    "paper_slug": "world-model-policy",
                    "title": "World Model Policy",
                }
            },
            config={"model": "gpt-4o-mini", "api_key": "sk-demo"},
        )
