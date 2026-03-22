"""Paper review stage providers."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable

from app.prompts.registry import render_prompt
from app.providers.base import BaseStageProvider
from app.providers.codex_transport import run_codex_json
from app.providers.llm_chat import run_llm_json
from app.providers.registry import register

_SLUG_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")
_RECOMMENDATION_MAP = {
    "必读": "必读",
    "强推": "必读",
    "推荐": "值得看",
    "值得看": "值得看",
    "可读": "可略读",
    "可略读": "可略读",
    "略读": "可略读",
}

JsonRunner = Callable[[str, dict | None], Awaitable[dict]]


def _normalize_text(raw: object, *, max_len: int = 240) -> str:
    return re.sub(r"\s+", " ", str(raw or "").strip())[:max_len]


def _normalize_string_list(raw: object, *, max_items: int = 8, max_len: int = 200) -> list[str]:
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


def _normalize_recommendation(raw: object) -> str:
    text = _normalize_text(raw, max_len=16)
    return _RECOMMENDATION_MAP.get(text, "值得看")


def _normalize_topic_label(raw: object) -> str:
    return _normalize_text(raw, max_len=48)


def _normalize_note_candidate(raw: object) -> bool:
    if isinstance(raw, bool):
        return raw
    text = _normalize_text(raw, max_len=16).lower()
    return text in {"true", "1", "yes", "y", "selected", "note", "必读"}


def _build_papers_prompt_payload(papers: object) -> str:
    if not isinstance(papers, list):
        return "[]"

    compact: list[dict[str, object]] = []
    for item in papers[:20]:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "paper_identity": _normalize_text(item.get("paper_identity"), max_len=96),
                "title": _normalize_text(item.get("title"), max_len=240),
                "summary": _normalize_text(item.get("summary"), max_len=900),
                "detail": _normalize_text(item.get("detail"), max_len=1400),
                "authors": _normalize_string_list(item.get("authors"), max_items=6, max_len=80),
                "affiliations": _normalize_string_list(item.get("affiliations"), max_items=4, max_len=120),
                "links": _normalize_links(item.get("links")),
                "figure": _normalize_text(item.get("figure"), max_len=400),
            }
        )
    return json.dumps(compact, ensure_ascii=False)


def _normalize_excluded_papers(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in raw[:10]:
        if not isinstance(item, dict):
            continue
        paper_identity = _normalize_text(item.get("paper_identity"), max_len=96)
        title = _normalize_text(item.get("title"), max_len=240)
        reason = _normalize_text(item.get("reason"), max_len=240)
        entry = {k: v for k, v in {"paper_identity": paper_identity, "title": title, "reason": reason}.items() if v}
        if entry:
            normalized.append(entry)
    return normalized


def _normalize_paper_entry(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise ValueError("Invalid paper entry")

    paper_identity = _normalize_text(raw.get("paper_identity"), max_len=96)
    title = _normalize_text(raw.get("title"), max_len=240)
    digest_fields = {
        "one_line_judgment": _normalize_text(raw.get("one_line_judgment"), max_len=220),
        "core_problem": _normalize_text(raw.get("core_problem"), max_len=320),
        "core_method": _normalize_text(raw.get("core_method"), max_len=700),
        "key_result": _normalize_text(raw.get("key_result"), max_len=700),
        "why_it_matters": _normalize_text(raw.get("why_it_matters"), max_len=520),
        "reading_advice": _normalize_text(raw.get("reading_advice"), max_len=520),
    }
    if not paper_identity:
        raise ValueError("Missing paper_identity in paper_review output")
    if not title:
        raise ValueError("Missing title in paper_review output")
    for field_name, value in digest_fields.items():
        if not value:
            raise ValueError(f"Missing {field_name} in paper_review output")

    paper_slug = _normalize_text(raw.get("paper_slug"), max_len=120) or _slugify(title)
    return {
        "paper_identity": paper_identity,
        "paper_slug": paper_slug,
        "title": title,
        "topic_label": _normalize_topic_label(raw.get("topic_label")),
        "authors": _normalize_string_list(raw.get("authors"), max_items=8, max_len=80),
        "affiliations": _normalize_string_list(raw.get("affiliations"), max_items=6, max_len=120),
        "links": _normalize_links(raw.get("links")),
        "figure": _normalize_text(raw.get("figure"), max_len=400),
        "recommendation": _normalize_recommendation(raw.get("recommendation")),
        "one_line_judgment": digest_fields["one_line_judgment"],
        "core_problem": digest_fields["core_problem"],
        "core_method": digest_fields["core_method"],
        "key_result": digest_fields["key_result"],
        "why_it_matters": digest_fields["why_it_matters"],
        "reading_advice": digest_fields["reading_advice"],
        "note_candidate": _normalize_note_candidate(raw.get("note_candidate")),
    }


async def _run_ai_paper_review(payload: dict, runner: JsonRunner, config: dict | None = None) -> dict:
    title = _normalize_text(payload.get("title") or "论文推荐", max_len=120) or "论文推荐"
    prompt_papers = _build_papers_prompt_payload(payload.get("papers"))
    prompt = render_prompt(
        scope="llm",
        name="paper_review",
        variables={
            "title": title,
            "papers_json": prompt_papers,
        },
    )
    output = await runner(prompt=prompt, config=dict(config or {}))

    digest_summary = _normalize_text(output.get("digest_summary"), max_len=1600)
    if not digest_summary:
        raise ValueError("Missing digest_summary from paper_review output")

    raw_papers = output.get("papers")
    if not isinstance(raw_papers, list) or not raw_papers:
        raise ValueError("Missing papers from paper_review output")

    papers = [_normalize_paper_entry(item) for item in raw_papers]
    return {
        "digest_title": title,
        "digest_summary": digest_summary,
        "editorial_observations": _normalize_string_list(
            output.get("editorial_observations"),
            max_items=5,
            max_len=160,
        ),
        "papers": papers,
        "excluded_papers": _normalize_excluded_papers(output.get("excluded_papers")),
    }


@register(stage="paper_review", name="llm_openai")
class LLMPaperReviewProvider(BaseStageProvider):
    stage = "paper_review"
    name = "llm_openai"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        return await _run_ai_paper_review(payload=payload, runner=run_llm_json, config=config)


@register(stage="paper_review", name="llm_codex")
class CodexPaperReviewProvider(BaseStageProvider):
    stage = "paper_review"
    name = "llm_codex"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        return await _run_ai_paper_review(payload=payload, runner=run_codex_json, config=config)
