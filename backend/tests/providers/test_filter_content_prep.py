from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.providers.filter import LLMFilterProvider, _prepare_filter_snippet


def test_prepare_filter_snippet_removes_markdown_noise_and_keeps_intro() -> None:
    article = SimpleNamespace(
        title="QwenLM/Qwen-Agent",
        content="""
![badge](https://img.shields.io/badge/test-green.svg)
<picture>
  <source srcset="banner-dark.avif" media="(prefers-color-scheme: dark)" />
</picture>
# Qwen-Agent

Qwen-Agent is a framework for developing LLM applications with instruction following,
tool use, planning, and memory.
""",
        metadata={
            "description": "Agent framework for building LLM applications.",
            "language": "Python",
            "stars_today": 1280,
        },
    )

    snippet = _prepare_filter_snippet(article)

    assert "img.shields.io" not in snippet
    assert "<picture>" not in snippet
    assert "framework for developing LLM applications" in snippet


@pytest.mark.asyncio
async def test_llm_filter_prompt_includes_source_context_and_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        captured["prompt"] = prompt
        return {"keep_indices": [0]}

    monkeypatch.setattr("app.providers.filter.run_llm_json", _fake_llm)
    monkeypatch.setattr("app.providers.filter.run_llm_json", _fake_llm)

    provider = LLMFilterProvider()
    article = SimpleNamespace(
        title="QwenLM/Qwen-Agent",
        content="""
![badge](https://img.shields.io/badge/test-green.svg)
Qwen-Agent is a framework for developing LLM applications with tool use.
""",
        metadata={
            "source_name": "GitHub Trending Daily",
            "source_category": "social",
            "author_username": "OpenAIDevs",
            "author_name": "OpenAI Devs",
            "description": "Agent framework for building LLM applications.",
            "language": "Python",
            "stars_today": 1280,
            "snapshot_date": "2026-03-07",
        },
        published_at=None,
    )

    output = await provider.run(payload={"articles": [article]}, config={"model": "qwen3.5-397b-a17b"})

    assert len(output["articles"]) == 1
    assert '"source_name": "GitHub Trending Daily"' in captured["prompt"]
    assert '"source_category": "social"' in captured["prompt"]
    assert '"author_username": "OpenAIDevs"' in captured["prompt"]
    assert '"author_name": "OpenAI Devs"' in captured["prompt"]
    assert '"description": "Agent framework for building LLM applications."' in captured["prompt"]
    assert '"stars_today": 1280' in captured["prompt"]
    assert "img.shields.io" not in captured["prompt"]
