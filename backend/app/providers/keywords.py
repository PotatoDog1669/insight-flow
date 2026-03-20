"""Unified keywords stage providers (rule / llm)."""

from __future__ import annotations

import re
from collections import Counter
from typing import Awaitable, Callable

from app.providers.base import BaseStageProvider
from app.providers.codex_transport import run_codex_json
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
VALID_EVENT_CATEGORIES = {"要闻", "模型发布", "开发生态", "产品应用", "技术与洞察", "行业动态", "前瞻与传闻", "其他"}


class _PromptArticle:
    def __init__(self, *, title: str, content: str):
        self.title = title
        self.content = content


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


def _normalize_short_text(raw: object, *, max_len: int = 240) -> str:
    text = _WHITESPACE_PATTERN.sub(" ", str(raw or "").strip())
    return text[:max_len]


def _normalize_metrics(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    metrics: list[str] = []
    for item in raw:
        metric = _normalize_short_text(item, max_len=64)
        if not metric:
            continue
        if metric in metrics:
            continue
        metrics.append(metric)
        if len(metrics) >= 12:
            break
    return metrics


JsonRunner = Callable[[str, dict | None], Awaitable[dict]]


async def _run_ai_keywords(article: object, runner: JsonRunner, config: dict | None = None) -> dict:
    title = str(getattr(article, "title", "") or "").strip()
    content = _prepare_content_for_prompt(getattr(article, "content", ""))
    prompt = render_prompt(
        scope="llm",
        name="keywords",
        variables={
            "title": title[:240],
            "content": content[:4000],
        },
    )
    run_config = dict(config or {})
    output = await runner(prompt=prompt, config=run_config)
    keywords = _normalize_keywords(output.get("keywords"))
    if not keywords:
        raise ValueError("Missing keywords from AI provider")
    summary = _normalize_summary(output.get("summary"))
    if not summary:
        raise ValueError("Missing summary from AI provider")
    result: dict = {"keywords": keywords, "summary": summary}
    event_title = _normalize_short_text(output.get("event_title"), max_len=96)
    if event_title:
        result["event_title"] = event_title
    importance = str(output.get("importance") or "").strip().lower()
    if importance in ("high", "normal"):
        result["importance"] = importance
    category = _normalize_short_text(output.get("category"), max_len=24)
    if category in VALID_EVENT_CATEGORIES:
        result["category"] = category
    detail = str(output.get("detail") or "").strip()
    if detail:
        result["detail"] = detail[:1400]
    who = _normalize_short_text(output.get("who"), max_len=120)
    if who:
        result["who"] = who
    what = _normalize_short_text(output.get("what"), max_len=180)
    if what:
        result["what"] = what
    when = _normalize_short_text(output.get("when"), max_len=120)
    if when:
        result["when"] = when
    metrics = _normalize_metrics(output.get("metrics"))
    if metrics:
        result["metrics"] = metrics
    availability = _normalize_short_text(output.get("availability"), max_len=240)
    if availability:
        result["availability"] = availability
    unknowns = _normalize_short_text(output.get("unknowns"), max_len=240)
    if unknowns:
        result["unknowns"] = unknowns
    evidence = _normalize_short_text(output.get("evidence"), max_len=360)
    if evidence:
        result["evidence"] = evidence
    return result


def _resolve_article_from_payload(payload: dict) -> object | None:
    article = payload.get("article")
    if article is not None:
        return article
    event_input = payload.get("event_input")
    if event_input is None:
        return None
    return _event_input_to_prompt_article(event_input)


def _event_input_to_prompt_article(event_input: object) -> _PromptArticle:
    primary = getattr(event_input, "primary_article", None)
    supporting_articles = getattr(event_input, "supporting_articles", []) or []
    title = str(getattr(primary, "title", "") or "").strip()

    blocks: list[str] = []
    primary_block = _format_prompt_article_block("Primary Source", primary)
    if primary_block:
        blocks.append(primary_block)

    for index, article in enumerate(supporting_articles[:3], start=1):
        block = _format_prompt_article_block(f"Supporting Source {index}", article)
        if block:
            blocks.append(block)

    return _PromptArticle(
        title=title[:240],
        content="\n\n".join(blocks)[:5000],
    )


def _format_prompt_article_block(label: str, article: object) -> str:
    if article is None:
        return ""
    metadata = getattr(article, "metadata", {}) or {}
    title = str(getattr(article, "title", "") or "").strip()
    url = str(getattr(article, "url", "") or "").strip()
    content = _prepare_content_for_prompt(getattr(article, "content", ""), max_chars=1600)
    source_name = str(metadata.get("source_name") or "").strip()
    author_name = str(metadata.get("author_name") or "").strip()
    author_username = str(metadata.get("author_username") or "").strip().lstrip("@")
    distribution = _detect_distribution_hint(article)
    lines = [label]
    if source_name:
        lines.append(f"Source: {source_name}")
    if author_name and author_username:
        lines.append(f"Author: {author_name} (@{author_username})")
    elif author_name:
        lines.append(f"Author: {author_name}")
    elif author_username:
        lines.append(f"Author: @{author_username}")
    if title:
        lines.append(f"Title: {title}")
    if url:
        lines.append(f"URL: {url}")
    if distribution:
        lines.append(f"Distribution: {distribution}")
    if content:
        lines.append(f"Content: {content}")
    return "\n".join(lines).strip()


def _detect_distribution_hint(article: object) -> str:
    content = str(getattr(article, "content", "") or "")
    url = str(getattr(article, "url", "") or "")
    combined = f"{content}\n{url}".lower()
    if "apps.apple.com" in combined or "app store" in combined:
        return "App Store"
    if "play.google.com" in combined or "google play" in combined:
        return "Google Play"
    return ""


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
        article = _resolve_article_from_payload(payload)
        title = str(getattr(article, "title", "") or "").strip()
        summary = _extract_summary(article)
        return {
            "keywords": _extract_keywords(article),
            "summary": summary,
            "event_title": title[:96] if title else summary[:96],
        }


@register(stage="keywords", name="llm_openai")
class LLMKeywordProvider(BaseStageProvider):
    stage = "keywords"
    name = "llm_openai"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        article = _resolve_article_from_payload(payload)
        if article is None:
            return {"keywords": [], "summary": ""}
        return await _run_ai_keywords(article=article, runner=run_llm_json, config=config)


@register(stage="keywords", name="llm_codex")
class CodexKeywordProvider(BaseStageProvider):
    stage = "keywords"
    name = "llm_codex"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        article = _resolve_article_from_payload(payload)
        if article is None:
            return {"keywords": [], "summary": ""}
        return await _run_ai_keywords(article=article, runner=run_codex_json, config=config)
