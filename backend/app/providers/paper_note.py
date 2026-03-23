"""Paper note stage providers."""

from __future__ import annotations

import json
import re
from typing import Awaitable, Callable

from app.providers.base import BaseStageProvider
from app.providers.codex_transport import run_codex_json
from app.providers.llm_chat import run_llm_json
from app.providers.registry import register
from app.prompts.registry import render_prompt

_SLUG_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")

JsonRunner = Callable[[str, dict | None], Awaitable[dict]]


def _normalize_text(raw: object, *, max_len: int = 280) -> str:
    return re.sub(r"\s+", " ", str(raw or "").strip())[:max_len]


def _normalize_string_list(raw: object, *, max_items: int = 10, max_len: int = 200) -> list[str]:
    items = raw if isinstance(raw, list) else [raw]
    normalized: list[str] = []
    for item in items:
        value = _normalize_text(item, max_len=max_len)
        if not value or value in normalized:
            continue
        normalized.append(value)
        if len(normalized) >= max_items:
            break
    return normalized


def _normalize_links(raw: object) -> list[str]:
    links = _normalize_string_list(raw, max_items=6, max_len=400)
    return [link for link in links if link.startswith(("http://", "https://"))]


def _slugify(text: str) -> str:
    lowered = str(text or "").strip().lower()
    slug = _SLUG_RE.sub("-", lowered).strip("-")
    return slug or "paper"


def _build_paper_prompt_payload(raw: object) -> str:
    if not isinstance(raw, dict):
        return "{}"
    compact = {
        "paper_identity": _normalize_text(raw.get("paper_identity"), max_len=96),
        "paper_slug": _normalize_text(raw.get("paper_slug"), max_len=120),
        "title": _normalize_text(raw.get("title"), max_len=240),
        "summary": _normalize_text(raw.get("summary"), max_len=500),
        "detail": _normalize_text(raw.get("detail"), max_len=700),
        "authors": _normalize_string_list(raw.get("authors"), max_items=8, max_len=80),
        "affiliations": _normalize_string_list(raw.get("affiliations"), max_items=6, max_len=120),
        "links": _normalize_links(raw.get("links")),
    }
    return json.dumps(compact, ensure_ascii=False)


def _require_list_field(output: dict, key: str, *, max_items: int = 10, max_len: int = 200) -> list[str]:
    values = _normalize_string_list(output.get(key), max_items=max_items, max_len=max_len)
    if not values:
        raise ValueError(f"Missing {key} from paper_note output")
    return values


async def _run_ai_paper_note(payload: dict, runner: JsonRunner, config: dict | None = None) -> dict:
    paper = payload.get("paper") if isinstance(payload.get("paper"), dict) else {}
    paper_identity = _normalize_text(paper.get("paper_identity"), max_len=96)
    title = _normalize_text(paper.get("title"), max_len=240)
    if not paper_identity:
        raise ValueError("Missing paper_identity from paper_note payload")
    if not title:
        raise ValueError("Missing title from paper_note payload")

    paper_slug = _normalize_text(paper.get("paper_slug"), max_len=120) or _slugify(title)
    prompt = render_prompt(
        scope="llm",
        name="paper_note",
        variables={
            "title": title,
            "paper_json": _build_paper_prompt_payload({**paper, "paper_slug": paper_slug}),
        },
    )
    output = await runner(prompt=prompt, config=dict(config or {}))

    summary = _normalize_text(output.get("summary"), max_len=500)
    if not summary:
        raise ValueError("Missing summary from paper_note output")

    normalized_title = _normalize_text(output.get("title") or title, max_len=240) or title
    return {
        "paper_identity": paper_identity,
        "paper_slug": paper_slug,
        "title": normalized_title,
        "authors": _normalize_string_list(paper.get("authors"), max_items=8, max_len=80),
        "affiliations": _normalize_string_list(paper.get("affiliations"), max_items=6, max_len=120),
        "links": _normalize_links(paper.get("links")),
        "summary": summary,
        "core_contributions": _require_list_field(output, "core_contributions", max_items=6, max_len=220),
        "problem_background": _require_list_field(output, "problem_background", max_items=4, max_len=220),
        "method_breakdown": _require_list_field(output, "method_breakdown", max_items=8, max_len=220),
        "figure_notes": _require_list_field(output, "figure_notes", max_items=6, max_len=220),
        "experiments": _require_list_field(output, "experiments", max_items=8, max_len=220),
        "strengths": _require_list_field(output, "strengths", max_items=6, max_len=220),
        "limitations": _require_list_field(output, "limitations", max_items=6, max_len=220),
        "related_reading": _require_list_field(output, "related_reading", max_items=8, max_len=160),
        "next_steps": _require_list_field(output, "next_steps", max_items=6, max_len=180),
    }


@register(stage="paper_note", name="llm_openai")
class LLMPaperNoteProvider(BaseStageProvider):
    stage = "paper_note"
    name = "llm_openai"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        return await _run_ai_paper_note(payload=payload, runner=run_llm_json, config=config)


@register(stage="paper_note", name="llm_codex")
class CodexPaperNoteProvider(BaseStageProvider):
    stage = "paper_note"
    name = "llm_codex"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        return await _run_ai_paper_note(payload=payload, runner=run_codex_json, config=config)
