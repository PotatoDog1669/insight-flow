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

    assert "标题：t" in rendered
    assert "内容：c" in rendered


def test_render_prompt_raises_for_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt(scope="agent", name="not_exists")
