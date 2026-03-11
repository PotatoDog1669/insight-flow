"""Prompt loading and rendering utilities."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template

from app.config import PROJECT_ROOT

PROMPT_ROOT = PROJECT_ROOT / "backend" / "app" / "prompts"
VALID_SCOPES = {"agent", "llm"}
SHARED_LLM_PROMPTS = {"filter", "keywords", "report", "global_summary"}


def _resolve_scope(scope: str, name: str) -> str:
    normalized_scope = str(scope or "").strip().lower()
    if normalized_scope not in VALID_SCOPES:
        raise ValueError(f"Invalid prompt scope: {scope}")
    normalized_name = str(name or "").strip().lower()
    if not normalized_name:
        raise ValueError("Prompt name is required")
    if normalized_scope == "agent" and normalized_name in SHARED_LLM_PROMPTS:
        return "llm"
    return normalized_scope


def _prompt_path(scope: str, name: str) -> Path:
    normalized_name = str(name or "").strip().lower()
    if not normalized_name:
        raise ValueError("Prompt name is required")
    normalized_scope = _resolve_scope(scope=scope, name=name)
    return PROMPT_ROOT / normalized_scope / f"{normalized_name}.md"


@lru_cache(maxsize=128)
def load_prompt(scope: str, name: str) -> str:
    path = _prompt_path(scope=scope, name=name)
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def render_prompt(scope: str, name: str, variables: dict[str, object] | None = None) -> str:
    template_text = load_prompt(scope=scope, name=name)
    template = Template(template_text)
    mapping = {key: str(value) for key, value in (variables or {}).items()}
    return template.substitute(mapping)
