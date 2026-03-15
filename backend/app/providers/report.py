"""Unified report stage providers."""

from __future__ import annotations

import json
import re
from typing import Awaitable, Callable

from app.providers.base import BaseStageProvider
from app.providers.codex_transport import run_codex_json
from app.providers.llm_chat import run_llm_json
from app.providers.registry import register
from app.prompts.registry import render_prompt


_TLDR_LABEL_PREFIX_PATTERN = re.compile(r"^(?:核心突破|趋势洞察|总结|锐评|概览)[:：]\s*")
_CATEGORY_COUNT_PATTERN = re.compile(
    r"(要闻|模型发布|开发生态|产品应用|技术与洞察|行业动态|前瞻与传闻|其他)\s*\d+\s*条"
)
_COUNT_STYLE_PATTERN = re.compile(r"(共收录|共整理|共计|收录了|整理了).{0,20}\d+\s*条")


def _build_events_prompt_payload(events: object) -> str:
    if not isinstance(events, list):
        return "[]"

    compact: list[dict[str, object]] = []
    for index, item in enumerate(events[:25], start=1):
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "index": int(item.get("index") or index),
                "category": str(item.get("category") or ""),
                "title": str(item.get("title") or ""),
                "one_line_tldr": str(item.get("one_line_tldr") or ""),
                "detail": str(item.get("detail") or "")[:800],
                "source_name": str(item.get("source_name") or ""),
            }
        )

    return json.dumps(compact, ensure_ascii=False)


JsonRunner = Callable[[str, dict | None], Awaitable[dict]]


async def _run_ai_report(payload: dict, runner: JsonRunner, config: dict | None = None) -> dict:
    title = str(payload.get("title", "AI Daily Report"))
    content = str(payload.get("content", ""))
    global_tldr = str(payload.get("global_tldr", ""))
    events = payload.get("events", [])
    report_date = str(payload.get("date", "")).strip()
    prompt_content = _build_events_prompt_payload(events)
    prompt = render_prompt(
        scope="llm",
        name="report",
        variables={
            "title": title,
            "date": report_date,
            "global_tldr": global_tldr,
            "events_json": prompt_content,
        },
    )
    run_config = dict(config or {})
    output = await runner(prompt=prompt, config=run_config)
    generated_title = str(output.get("title") or title).strip() or title
    generated_tldr = _sanitize_global_tldr(str(output.get("global_tldr") or global_tldr).strip())
    return {
        "title": generated_title,
        "content": content,
        "global_tldr": generated_tldr,
        "report_metrics": {
            "input_content_chars": len(content),
            "prompt_content_chars": len(prompt_content),
            "prompt_content_truncated": False,
            "output_content_chars": len(content),
        },
    }


def _sanitize_global_tldr(text: str) -> str:
    raw_text = str(text or "").strip()
    if not raw_text:
        return ""

    segments = [part.strip() for part in re.split(r"[。！？!?]\s*|\n+", raw_text) if part.strip()]
    cleaned: list[str] = []
    for segment in segments:
        sentence = _TLDR_LABEL_PREFIX_PATTERN.sub("", segment).strip()
        if not sentence:
            continue
        if _is_count_style_sentence(sentence):
            continue
        cleaned.append(sentence)
        if len(cleaned) >= 3:
            break

    if not cleaned:
        return raw_text
    if len(cleaned) == 1:
        return cleaned[0]
    return "。".join(cleaned) + "。"


def _is_count_style_sentence(sentence: str) -> bool:
    if "分类分布" in sentence:
        return True
    if _COUNT_STYLE_PATTERN.search(sentence):
        return True
    if _CATEGORY_COUNT_PATTERN.search(sentence):
        return True
    if "条" in sentence and any(token in sentence for token in ("收录", "整理", "分类", "分布")):
        return True
    return False


@register(stage="report", name="llm_openai")
class LLMReportProvider(BaseStageProvider):
    stage = "report"
    name = "llm_openai"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        return await _run_ai_report(payload=payload, runner=run_llm_json, config=config)


@register(stage="report", name="llm_codex")
class CodexReportProvider(BaseStageProvider):
    stage = "report"
    name = "llm_codex"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        return await _run_ai_report(payload=payload, runner=run_codex_json, config=config)
