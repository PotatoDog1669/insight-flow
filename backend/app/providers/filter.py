"""Unified filter stage providers (rule / llm / agent)."""

from __future__ import annotations

import json

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


def _filter_by_terms(articles: list) -> list:
    kept = []
    for article in articles:
        content = f"{getattr(article, 'title', '')}\n{getattr(article, 'content', '')}".lower()
        if any(term in content for term in AI_TERMS):
            kept.append(article)
    return kept


async def _run_ai_filter(articles: list, config: dict | None = None, prompt_scope: str = "agent") -> dict:
    serialized_items = []
    for idx, article in enumerate(articles):
        title = str(getattr(article, "title", "") or "").strip()
        content = str(getattr(article, "content", "") or "").strip().replace("\n", " ")
        serialized_items.append({"index": idx, "title": title[:200], "snippet": content[:420]})

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
