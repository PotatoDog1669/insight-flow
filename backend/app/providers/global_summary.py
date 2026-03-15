"""Global summary stage providers."""

from __future__ import annotations

import json
from typing import Awaitable, Callable

from app.providers.base import BaseStageProvider
from app.providers.codex_transport import run_codex_json
from app.providers.llm_chat import run_llm_json
from app.providers.registry import register
from app.prompts.registry import render_prompt


def _build_events_prompt_payload(events: object) -> str:
    if not isinstance(events, list):
        return "[]"

    compact: list[dict[str, object]] = []
    for index, item in enumerate(events[:20], start=1):
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "index": int(item.get("index") or index),
                "category": str(item.get("category") or ""),
                "title": str(item.get("title") or ""),
                "summary": str(item.get("summary") or item.get("one_line_tldr") or ""),
                "detail": str(item.get("detail") or "")[:800],
                "source_name": str(item.get("source_name") or ""),
                "source_count": int(item.get("source_count") or 0),
                "who": str(item.get("who") or ""),
                "what": str(item.get("what") or ""),
                "when": str(item.get("when") or ""),
            }
        )
    return json.dumps(compact, ensure_ascii=False)


def _sanitize_global_tldr(text: str) -> str:
    raw_text = str(text or "").strip()
    if not raw_text:
        return ""

    segments = [segment.strip() for segment in raw_text.replace("\n", "。").split("。") if segment.strip()]
    cleaned = [segment.removeprefix("核心突破：").removeprefix("趋势洞察：").strip() for segment in segments[:3]]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0] + ("。" if raw_text.endswith("。") else "")
    return "。".join(cleaned) + "。"


JsonRunner = Callable[[str, dict | None], Awaitable[dict]]


async def _run_ai_summary(payload: dict, runner: JsonRunner, config: dict | None = None) -> dict:
    events = payload.get("events", [])
    prompt_content = _build_events_prompt_payload(events)
    prompt = render_prompt(
        scope="llm",
        name="global_summary",
        variables={"events_json": prompt_content},
    )
    run_config = dict(config or {})
    output = await runner(prompt=prompt, config=run_config)
    generated = _sanitize_global_tldr(str(output.get("global_tldr") or "").strip())
    return {
        "global_tldr": generated,
        "summary_metrics": {
            "input_event_count": len(events) if isinstance(events, list) else 0,
            "prompt_content_chars": len(prompt_content),
            "output_chars": len(generated),
        },
    }


@register(stage="global_summary", name="llm_openai")
class LLMGlobalSummaryProvider(BaseStageProvider):
    stage = "global_summary"
    name = "llm_openai"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        return await _run_ai_summary(payload=payload, runner=run_llm_json, config=config)


@register(stage="global_summary", name="llm_codex")
class CodexGlobalSummaryProvider(BaseStageProvider):
    stage = "global_summary"
    name = "llm_codex"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        return await _run_ai_summary(payload=payload, runner=run_codex_json, config=config)
