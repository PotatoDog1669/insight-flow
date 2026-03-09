from __future__ import annotations

import pytest

from app.processors.global_summary import build_global_summary_fallback, run_global_summary_stage


def _sample_events() -> list[dict]:
    return [
        {
            "index": 1,
            "category": "模型发布",
            "title": "OpenAI 发布 GPT-5",
            "one_line_tldr": "推理和代码能力继续增强。",
            "detail": "OpenAI 发布 GPT-5，并强调推理、代码与速度表现的进一步提升。",
            "source_name": "OpenAI",
            "source_count": 2,
            "who": "OpenAI",
            "what": "发布 GPT-5",
            "when": "2026-03-06",
        }
    ]


def test_build_global_summary_fallback_returns_empty_for_no_events() -> None:
    assert build_global_summary_fallback([]) == ""


@pytest.mark.asyncio
async def test_run_global_summary_stage_uses_provider_output() -> None:
    async def _runner(payload: dict) -> tuple[dict, str]:
        assert payload["events"][0]["title"] == "OpenAI 发布 GPT-5"
        return {"global_tldr": "今日主线是模型能力与交付效率同步升级。"}, "llm_openai"

    summary = await run_global_summary_stage(events=_sample_events(), runner=_runner)

    assert summary.global_tldr == "今日主线是模型能力与交付效率同步升级。"
    assert summary.provider == "llm_openai"
    assert summary.fallback_used is False
    assert summary.prompt_metrics["input_event_count"] == 1


@pytest.mark.asyncio
async def test_run_global_summary_stage_falls_back_when_runner_errors() -> None:
    async def _runner(payload: dict) -> tuple[dict, str]:
        raise RuntimeError("provider failed")

    summary = await run_global_summary_stage(events=_sample_events(), runner=_runner)

    assert "GPT-5" in summary.global_tldr
    assert summary.provider == "fallback"
    assert summary.fallback_used is True
    assert summary.prompt_metrics["input_event_count"] == 1
