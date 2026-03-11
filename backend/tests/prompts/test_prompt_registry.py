from __future__ import annotations

import pytest

from app.prompts.registry import load_prompt, render_prompt


def test_load_prompt_from_agent_and_llm_scopes() -> None:
    agent_text = load_prompt(scope="agent", name="filter")
    llm_text = load_prompt(scope="llm", name="filter")

    assert "keep_indices" in agent_text
    assert "keep_indices" in llm_text


def test_render_prompt_substitutes_variables() -> None:
    rendered = render_prompt(
        scope="agent",
        name="keywords",
        variables={"title": "t", "content": "c"},
    )

    assert "t" in rendered
    assert "c" in rendered
    assert "$title" not in rendered
    assert "$content" not in rendered


def test_render_prompt_raises_for_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt(scope="agent", name="not_exists")


def test_filter_prompts_exclude_static_pages_and_require_eventfulness() -> None:
    agent_text = load_prompt(scope="agent", name="filter")
    llm_text = load_prompt(scope="llm", name="filter")

    assert agent_text == llm_text
    assert "career pages" in llm_text
    assert "landing pages" in llm_text
    assert "time-bounded event" in llm_text


def test_filter_prompts_allow_snapshot_sources_with_clear_technical_signal() -> None:
    agent_text = load_prompt(scope="agent", name="filter")
    llm_text = load_prompt(scope="llm", name="filter")

    assert agent_text == llm_text
    assert "GitHub Trending" in llm_text
    assert "daily snapshot" in llm_text


@pytest.mark.parametrize("name", ["filter", "keywords", "report", "global_summary"])
def test_agent_and_llm_processing_prompts_share_same_template(name: str) -> None:
    assert load_prompt(scope="agent", name=name) == load_prompt(scope="llm", name=name)
