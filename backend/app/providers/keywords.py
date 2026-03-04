"""Unified keywords stage providers (rule / llm)."""

from __future__ import annotations

import re
from collections import Counter

from app.providers.base import BaseStageProvider
from app.providers.codex_agent import run_codex_json
from app.providers.llm_chat import run_llm_json
from app.providers.registry import register
from app.prompts.registry import render_prompt

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "from",
    "into",
    "about",
    "today",
    "发布",
    "一个",
    "我们",
    "以及",
    "通过",
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
    "x.com",
    "facebook",
    "linkedin",
    "mailto",
    "copy link",
)

_MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*]\([^)]*\)")
_MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_DASH_TRANSLATION = str.maketrans(
    {
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "―": "-",
    }
)


def _extract_keywords(article: object) -> list[str]:
    content = _prepare_content_for_prompt(getattr(article, "content", ""))
    text = _normalize_token_text(f"{getattr(article, 'title', '')} {content}")
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+_.#-]{2,}|[\u4e00-\u9fff]{2,}", text)
    counter: Counter[str] = Counter()
    for token in tokens:
        normalized = token.strip().lower()
        if normalized in STOPWORDS:
            continue
        if normalized.startswith(("http", "www")):
            continue
        if "@" in normalized:
            continue
        if normalized.count(".") >= 2:
            continue
        counter[normalized] += 1
    return [word for word, _ in counter.most_common(5)]


def _normalize_keywords(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    output: list[str] = []
    for item in raw:
        keyword = str(item or "").strip()
        if not keyword:
            continue
        if keyword not in output:
            output.append(keyword)
        if len(output) >= 8:
            break
    return output


def _extract_summary(article: object) -> str:
    content = _prepare_content_for_prompt(getattr(article, "content", ""))
    title = str(getattr(article, "title", "") or "").strip()
    base = content or title
    if not base:
        return ""
    summary = _select_summary_sentence(base, title=title)
    if summary:
        return summary[:220].strip()
    return base[:220].strip()


def _normalize_summary(raw: object) -> str:
    summary = str(raw or "").strip()
    return summary[:400]


async def _run_ai_keywords(article: object, config: dict | None = None, prompt_scope: str = "agent") -> dict:
    title = str(getattr(article, "title", "") or "").strip()
    content = _prepare_content_for_prompt(getattr(article, "content", ""))
    prompt = render_prompt(
        scope=prompt_scope,
        name="keywords",
        variables={
            "title": title[:240],
            "content": content[:4000],
        },
    )
    run_config = dict(config or {})
    if prompt_scope == "llm":
        output = await run_llm_json(prompt=prompt, config=run_config)
    else:
        output = await run_codex_json(prompt=prompt, config=run_config)
    keywords = _normalize_keywords(output.get("keywords"))
    if not keywords:
        raise ValueError("Missing keywords from AI provider")
    summary = _normalize_summary(output.get("summary"))
    if not summary:
        raise ValueError("Missing summary from AI provider")
    result: dict = {"keywords": keywords, "summary": summary}
    importance = str(output.get("importance") or "").strip().lower()
    if importance in ("high", "normal"):
        result["importance"] = importance
    detail = str(output.get("detail") or "").strip()
    if detail:
        result["detail"] = detail[:1400]
    return result


def _prepare_content_for_prompt(raw_content: object, max_chars: int = 4000) -> str:
    text = str(raw_content or "")
    if not text.strip():
        return ""

    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    if "Markdown Content:" in normalized_text:
        normalized_text = normalized_text.split("Markdown Content:", 1)[1]
    normalized_text = _MARKDOWN_IMAGE_PATTERN.sub(" ", normalized_text)
    normalized_text = _MARKDOWN_LINK_PATTERN.sub(r"\1", normalized_text)

    cleaned_lines: list[str] = []
    for raw_line in normalized_text.split("\n"):
        line = _WHITESPACE_PATTERN.sub(" ", raw_line).strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith(("title:", "url source:", "published time:")):
            continue
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

    if not cleaned_lines:
        fallback = _WHITESPACE_PATTERN.sub(" ", normalized_text).strip()
        return fallback[:max_chars]

    combined = _WHITESPACE_PATTERN.sub(" ", " ".join(cleaned_lines)).strip()
    return combined[:max_chars]


def _select_summary_sentence(text: str, title: str = "") -> str:
    candidates = re.split(r"(?<=[。！？.!?])\s+", text)
    title_tokens = _extract_title_tokens(title)
    scored: list[tuple[str, int, int]] = []
    for raw in candidates:
        sentence = _WHITESPACE_PATTERN.sub(" ", str(raw or "")).strip()
        if not sentence:
            continue
        lowered = _normalize_token_text(sentence)
        if any(marker in lowered for marker in _NAVIGATION_MARKERS):
            continue
        if sentence.count("http") >= 1:
            continue
        if len(sentence) < 40:
            continue
        score = 0
        if any(ch.isdigit() for ch in sentence):
            score += 3
        if 60 <= len(sentence) <= 220:
            score += 2
        if "%" in sentence or any(token in lowered for token in ("improved", "reduced", "increase", "decrease", "提升", "降低")):
            score += 4
        if any(token in lowered for token in ("model", "release", "benchmark", "latency", "accuracy", "throughput", "paper", "dataset")):
            score += 1
        overlap = 0
        if title_tokens:
            overlap = sum(1 for token in title_tokens if token in lowered)
            score += min(overlap, 2)
        scored.append((sentence, score, overlap))

    if not scored:
        return ""

    if title_tokens and any(overlap > 0 for _, _, overlap in scored):
        scored = [item for item in scored if item[2] > 0]

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[0][0]


def _extract_title_tokens(title: str) -> set[str]:
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]{2,}", _normalize_token_text(title))
    output: set[str] = set()
    for token in tokens:
        if token in {"the", "and", "with", "for", "from", "update", "news"}:
            continue
        output.add(token)
    return output


def _normalize_token_text(text: str) -> str:
    return str(text or "").translate(_DASH_TRANSLATION).lower()


@register(stage="keywords", name="rule")
class RuleKeywordProvider(BaseStageProvider):
    stage = "keywords"
    name = "rule"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        article = payload.get("article")
        return {"keywords": _extract_keywords(article), "summary": _extract_summary(article)}


@register(stage="keywords", name="llm_openai")
class LLMKeywordProvider(BaseStageProvider):
    stage = "keywords"
    name = "llm_openai"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        article = payload.get("article")
        if article is None:
            return {"keywords": [], "summary": ""}
        return await _run_ai_keywords(article=article, config=config, prompt_scope="llm")


@register(stage="keywords", name="agent_codex")
class AgentKeywordProvider(BaseStageProvider):
    stage = "keywords"
    name = "agent_codex"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        article = payload.get("article")
        if article is None:
            return {"keywords": [], "summary": ""}
        return await _run_ai_keywords(article=article, config=config, prompt_scope="agent")
