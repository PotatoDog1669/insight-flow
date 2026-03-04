"""Unified report stage providers (llm / agent)."""

from __future__ import annotations

from app.providers.base import BaseStageProvider
from app.providers.codex_agent import run_codex_json
from app.providers.llm_chat import run_llm_json
from app.providers.registry import register
from app.prompts.registry import render_prompt


async def _run_ai_report(payload: dict, config: dict | None = None, prompt_scope: str = "agent") -> dict:
    title = str(payload.get("title", "AI Daily Report"))
    content = str(payload.get("content", ""))
    global_tldr = str(payload.get("global_tldr", ""))
    events = payload.get("events", [])
    events_count = len(events) if isinstance(events, list) else 0
    prompt = render_prompt(
        scope=prompt_scope,
        name="report",
        variables={
            "title": title,
            "events_count": events_count,
            "global_tldr": global_tldr,
            "content": content[:6000],
        },
    )
    run_config = dict(config or {})
    if prompt_scope == "llm":
        output = await run_llm_json(prompt=prompt, config=run_config)
    else:
        output = await run_codex_json(prompt=prompt, config=run_config)
    generated_title = str(output.get("title") or title).strip() or title
    generated_content = str(output.get("content") or content).strip() or content
    generated_tldr = str(output.get("global_tldr") or global_tldr).strip()
    return {"title": generated_title, "content": generated_content, "global_tldr": generated_tldr}


@register(stage="report", name="llm_openai")
class LLMReportProvider(BaseStageProvider):
    stage = "report"
    name = "llm_openai"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        return await _run_ai_report(payload=payload, config=config, prompt_scope="llm")


@register(stage="report", name="agent_codex")
class AgentReportProvider(BaseStageProvider):
    stage = "report"
    name = "agent_codex"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        return await _run_ai_report(payload=payload, config=config, prompt_scope="agent")
