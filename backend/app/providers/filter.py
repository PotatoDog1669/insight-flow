"""Unified filter stage providers (rule / llm / agent)."""

from __future__ import annotations

import json
import re

from app.providers.base import BaseStageProvider
from app.providers.codex_agent import run_codex_json
from app.providers.llm_chat import run_llm_json
from app.providers.registry import register
from app.prompts.registry import render_prompt

AI_TERMS = {
    "ai",
    "llm",
    "agent",
    "model",
    "transformer",
    "machine learning",
    "deep learning",
    "openai",
    "anthropic",
    "huggingface",
    "inference",
    "reasoning",
    "智能",
    "模型",
    "大模型",
    "推理",
    "机器学习",
    "深度学习",
}

_NAVIGATION_MARKERS = (
    "skip to main content",
    "share",
    "home",
    "learn more",
    "see all",
    "cookie",
    "privacy",
    "terms",
    "sign in",
    "subscribe",
)
_MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*]\([^)]*\)")
_MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def _filter_by_terms(articles: list) -> list:
    kept = []
    for article in articles:
        content = f"{getattr(article, 'title', '')}\n{getattr(article, 'content', '')}".lower()
        if any(term in content for term in AI_TERMS):
            kept.append(article)
    return kept


def _prepare_filter_content(raw_content: object, *, max_chars: int = 900) -> str:
    text = str(raw_content or "")
    if not text.strip():
        return ""

    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized_text = _MARKDOWN_IMAGE_PATTERN.sub(" ", normalized_text)
    normalized_text = _MARKDOWN_LINK_PATTERN.sub(r"\1", normalized_text)
    normalized_text = _HTML_TAG_PATTERN.sub(" ", normalized_text)

    cleaned_lines: list[str] = []
    for raw_line in normalized_text.split("\n"):
        line = _WHITESPACE_PATTERN.sub(" ", raw_line).strip()
        if not line:
            continue
        lowered = line.lower()
        if any(marker in lowered for marker in _NAVIGATION_MARKERS) and len(line) < 220:
            continue
        if line.count("http") >= 1 and len(line) < 180:
            continue
        if line.startswith("|") and line.endswith("|"):
            continue
        if line.count("|") >= 3:
            continue
        if len(line) < 20 and not any(ch.isdigit() for ch in line):
            continue
        cleaned_lines.append(line)

    combined = " ".join(cleaned_lines) if cleaned_lines else normalized_text
    return _WHITESPACE_PATTERN.sub(" ", combined).strip()[:max_chars]


def _prepare_filter_snippet(article: object, *, max_chars: int = 420) -> str:
    metadata = getattr(article, "metadata", {}) or {}
    description = str(metadata.get("description") or "").strip()
    content = _prepare_filter_content(getattr(article, "content", ""), max_chars=900)

    parts: list[str] = []
    if description:
        parts.append(description)
    if content:
        normalized_content = content.lower()
        if not description or description.lower() not in normalized_content:
            parts.append(content)

    combined = _WHITESPACE_PATTERN.sub(" ", " ".join(parts)).strip()
    return combined[:max_chars]


async def _run_ai_filter(articles: list, config: dict | None = None, prompt_scope: str = "agent") -> dict:
    serialized_items = []
    for idx, article in enumerate(articles):
        metadata = getattr(article, "metadata", {}) or {}
        title = str(getattr(article, "title", "") or "").strip()
        published_at = getattr(article, "published_at", None)
        published_text = published_at.isoformat() if hasattr(published_at, "isoformat") else str(published_at or "")
        serialized_items.append(
            {
                "index": idx,
                "source_name": str(metadata.get("source_name") or "")[:80],
                "title": title[:200],
                "published_at": published_text[:40],
                "description": str(metadata.get("description") or "")[:240],
                "language": str(metadata.get("language") or "")[:32],
                "stars_today": metadata.get("stars_today"),
                "snapshot_date": str(metadata.get("snapshot_date") or "")[:32],
                "snippet": _prepare_filter_snippet(article),
            }
        )

    prompt = render_prompt(
        scope=prompt_scope,
        name="filter",
        variables={"items_json": json.dumps(serialized_items, ensure_ascii=False)},
    )
    run_config = dict(config or {})
    if prompt_scope == "llm":
        output = await run_llm_json(prompt=prompt, config=run_config)
    else:
        output = await run_codex_json(prompt=prompt, config=run_config)
    raw_indices = output.get("keep_indices", [])
    if not isinstance(raw_indices, list):
        raise ValueError("keep_indices must be a list")
    keep_indices = [int(item) for item in raw_indices if isinstance(item, (int, float, str)) and str(item).isdigit()]
    deduped = []
    for idx in keep_indices:
        if 0 <= idx < len(articles) and idx not in deduped:
            deduped.append(idx)
    return {"articles": [articles[idx] for idx in deduped]}


@register(stage="filter", name="rule")
class RuleFilterProvider(BaseStageProvider):
    stage = "filter"
    name = "rule"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        articles = payload.get("articles", [])
        return {"articles": _filter_by_terms(articles)}


@register(stage="filter", name="llm_openai")
class LLMFilterProvider(BaseStageProvider):
    stage = "filter"
    name = "llm_openai"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        articles = payload.get("articles", [])
        if not articles:
            return {"articles": []}
        return await _run_ai_filter(articles=articles, config=config, prompt_scope="llm")


@register(stage="filter", name="agent_codex")
class AgentFilterProvider(BaseStageProvider):
    stage = "filter"
    name = "agent_codex"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        articles = payload.get("articles", [])
        if not articles:
            return {"articles": []}
        return await _run_ai_filter(articles=articles, config=config, prompt_scope="agent")
