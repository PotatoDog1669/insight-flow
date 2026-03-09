"""日报渲染器（事件字段化 + 模板化输出）。"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import re

from app.processors.content_quality_gate import apply_event_content_quality_gate
from app.processors.event_aggregator import aggregate_events
from app.processors.event_models import ProcessedEvent
from app.processors.pipeline import ProcessedArticle
from app.renderers.base import BaseRenderer, RenderContext, Report
from app.template_engine.renderer import render_report_template

CATEGORY_ORDER = ["要闻", "模型发布", "开发生态", "产品应用", "技术与洞察", "行业动态", "前瞻与传闻", "其他"]

_CATEGORY_KEYWORDS = {
    "前瞻与传闻": (
        "rumor",
        "leak",
        "preview",
        "coming soon",
        "传闻",
        "爆料",
        "预告",
        "即将",
    ),
    "模型发布": (
        "model",
        "release",
        "launch",
        "checkpoint",
        "weights",
        "api model",
        "发布",
        "推出",
        "开源模型",
        "基座",
    ),
    "开发生态": (
        "sdk",
        "framework",
        "library",
        "tool",
        "plugin",
        "extension",
        "version",
        "update",
        "course",
        "tutorial",
        "框架",
        "工具",
        "插件",
        "版本",
        "教程",
        "课程",
        "开发者",
    ),
    "产品应用": (
        "agent",
        "assistant",
        "copilot",
        "workflow",
        "feature",
        "product",
        "应用",
        "产品",
        "上线",
        "平台",
    ),
    "技术与洞察": (
        "paper",
        "research",
        "benchmark",
        "evaluation",
        "method",
        "arxiv",
        "论文",
        "研究",
        "评测",
        "基准",
        "技术",
    ),
    "行业动态": (
        "funding",
        "acquisition",
        "partnership",
        "policy",
        "regulation",
        "市场",
        "融资",
        "收购",
        "合作",
        "监管",
    ),
}

_METRIC_PATTERN = re.compile(r"\b\d+(?:\.\d+)?(?:%|x|k|m|b|亿|万)?\b", re.IGNORECASE)
_MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_TITLE_END_PUNCT_PATTERN = re.compile(r"[。！？!?；;:：、，,.…]+$")
_TITLE_SPLIT_PATTERN = re.compile(r"[，,；;。!?！？]")
_MODEL_SIGNAL_PATTERN = re.compile(r"\b(gpt|gemini|claude|llama|qwen|mistral|deepseek)\b", re.IGNORECASE)
_MODEL_VERSION_PATTERN = re.compile(r"\b(?:v\d+(?:\.\d+){0,2}|\d+\.\d+(?:\.\d+)?|\d+[bk])\b", re.IGNORECASE)
_DETAIL_NOISE_MARKERS = (
    "skip to main content",
    "share",
    "learn more",
    "see all",
    "cookie",
    "privacy",
    "terms",
    "subscribe",
)
_MODEL_RELEASE_TOKENS = (
    "模型",
    "system card",
    "checkpoint",
    "weights",
    "weight",
    "base model",
    "基座",
    "权重",
    "参数量",
)
_MODEL_RELEASE_ACTION_TOKENS = (
    "release",
    "launch",
    "introduce",
    "introduced",
    "shipping",
    "推出",
    "发布",
    "上线",
    "开源",
)
_MODEL_VARIANT_TOKENS = (
    "instant",
    "flash",
    "flash-lite",
    "sonnet",
    "haiku",
    "opus",
    "turbo",
    "mini",
    "nano",
    "reasoner",
    "coder",
    "codex",
)
_DEV_ECOSYSTEM_SIGNALS = (
    "sdk",
    "framework",
    "library",
    "tool",
    "plugin",
    "extension",
    "github",
    "repo",
    "template",
    "open source",
    "开源",
    "框架",
    "工具",
    "插件",
    "技能",
    "课程",
    "教程",
    "agent",
    "claude code",
    "cursor",
    "cli",
)
_RESEARCH_PRIMARY_SIGNALS = (
    "paper",
    "arxiv",
    "dataset",
    "study",
    "research",
    "preprint",
    "论文",
    "研究",
    "数据集",
)
_RESEARCH_SECONDARY_SIGNALS = (
    "benchmark",
    "evaluation",
    "基准",
    "评测",
    "实验",
)
MAX_DAILY_EVENTS = 20


class DailyRenderer(BaseRenderer):
    @property
    def level(self) -> str:
        return "L2"

    async def render(self, articles: list[ProcessedArticle] | list[ProcessedEvent], context: RenderContext) -> Report:
        """渲染日报（按事件动态输出，最多 15 条）。"""
        events = build_daily_events(articles)
        return render_daily_report(events=events, context=context)


def build_daily_events(articles: list[ProcessedArticle] | list[ProcessedEvent]) -> list[dict]:
    raw_events = [_build_event(item=item, index=idx) for idx, item in enumerate(articles, start=1)]
    return aggregate_events(raw_events)[:MAX_DAILY_EVENTS]


def render_daily_report(*, events: list[dict], context: RenderContext, global_summary: str | None = None) -> Report:
    global_tldr = str(global_summary or "").strip() or _build_global_tldr(events)
    overview = _build_overview(events)
    content = render_report_template(
        report_type="daily",
        version="v1",
        context={
            "date": context.date,
            "summary": global_tldr,
            "overview": overview,
            "events": events,
        },
    )
    category_counts = Counter(event["category"] for event in events)
    categories = [category for category in CATEGORY_ORDER if category_counts.get(category)]
    return Report(
        level="L2",
        title=f"AI 早报 {context.date}",
        content=content,
        article_ids=_flatten_article_ids(events),
        metadata={
            "events": events,
            "categories": categories,
            "global_tldr": global_tldr,
            "tldr": [global_tldr] if global_tldr else [],
            "global_tldr_source": "stage" if str(global_summary or "").strip() else "renderer_fallback",
            "time_period": "daily",
            "report_type": "daily",
        },
    )


def _build_overview(events: list[dict]) -> list[dict]:
    overview: list[dict] = []
    for category in CATEGORY_ORDER:
        in_category = [event for event in events if event["category"] == category]
        if not in_category:
            continue
        overview.append(
            {
                "category": category,
                "events": [
                    {
                        "title": str(event["title"]),
                        "index": int(event["index"]),
                        "first_link": event["source_links"][0] if event["source_links"] else "",
                    }
                    for event in in_category
                ],
            }
        )
    return overview


def _build_event(item: ProcessedArticle | ProcessedEvent, index: int) -> dict:
    if isinstance(item, ProcessedEvent):
        return _build_event_from_processed_event(item=item, index=index)

    source_name = str(item.raw.metadata.get("source_name") or "Unknown Source")
    source_category = str(item.raw.metadata.get("source_category") or "").strip().lower()
    one_line_tldr = (item.summary or item.raw.title or "N/A").strip()
    event_title = _build_event_title(
        raw_title=item.raw.title,
        one_line_tldr=one_line_tldr,
        explicit_title=getattr(item, "event_title", ""),
    )
    detail = _build_detail(item)
    keywords = [str(keyword).strip() for keyword in item.keywords if str(keyword).strip()]
    entities = _extract_entities(source_name=source_name, title=item.raw.title, keywords=keywords)
    llm_metrics = [str(metric).strip() for metric in getattr(item, "metrics", []) if str(metric).strip()]
    metrics = llm_metrics if llm_metrics else _extract_metrics(f"{item.raw.title}\n{item.summary}\n{item.raw.content or ''}")
    links = _extract_links(item)
    published_at = _event_time_to_iso(
        item.raw.published_at
        if isinstance(item.raw.published_at, datetime)
        else item.raw.metadata.get("snapshot_at")
    )
    importance = getattr(item, "importance", "normal") or "normal"

    return {
        "event_id": item.raw.external_id,
        "article_ids": [item.raw.external_id] if item.raw.external_id else [],
        "index": index,
        "title": event_title,
        "event_title": event_title,
        "category": _classify_event(item=item, source_category=source_category),
        "one_line_tldr": one_line_tldr,
        "detail": detail,
        "keywords": keywords[:12],
        "entities": entities,
        "metrics": metrics,
        "source_links": links,
        "source_count": len(links),
        "source_name": source_name,
        "published_at": published_at,
        "importance": importance,
        "who": str(getattr(item, "who", "") or "").strip(),
        "what": str(getattr(item, "what", "") or "").strip(),
        "when": str(getattr(item, "when", "") or "").strip(),
        "availability": str(getattr(item, "availability", "") or "").strip(),
        "unknowns": str(getattr(item, "unknowns", "") or "").strip(),
        "evidence": str(getattr(item, "evidence", "") or "").strip(),
    }


def _build_event_from_processed_event(item: ProcessedEvent, index: int) -> dict:
    gated = apply_event_content_quality_gate(item)
    title = _build_event_title(
        raw_title=gated.title,
        one_line_tldr=gated.summary,
        explicit_title=gated.title,
    )
    entities = [value for value in [gated.source_name, gated.who, *gated.keywords[:4]] if str(value or "").strip()][:8]
    return {
        "event_id": gated.event_id,
        "article_ids": list(gated.article_ids),
        "index": index,
        "title": title,
        "event_title": title,
        "category": gated.category or "其他",
        "one_line_tldr": gated.summary,
        "detail": gated.detail,
        "keywords": list(gated.keywords[:12]),
        "entities": entities,
        "metrics": list(gated.metrics[:12]),
        "source_links": list(gated.source_links),
        "source_count": gated.normalized_source_count(),
        "source_name": gated.source_name or "Unknown Source",
        "published_at": gated.published_at,
        "importance": gated.importance or "normal",
        "who": gated.who,
        "what": gated.what,
        "when": gated.when,
        "availability": gated.availability,
        "unknowns": gated.unknowns,
        "evidence": gated.evidence,
    }


def _flatten_article_ids(events: list[dict]) -> list[str]:
    article_ids: list[str] = []
    for event in events:
        values = event.get("article_ids")
        if not isinstance(values, list):
            values = [event.get("event_id")]
        for value in values:
            article_id = str(value or "").strip()
            if not article_id or article_id in article_ids:
                continue
            article_ids.append(article_id)
    return article_ids


def _build_event_title(raw_title: str, one_line_tldr: str, explicit_title: str = "") -> str:
    explicit = _WHITESPACE_PATTERN.sub(" ", str(explicit_title or "").strip())
    if explicit:
        explicit = _TITLE_END_PUNCT_PATTERN.sub("", explicit).strip()
        if explicit:
            return explicit[:96].rstrip()

    # Fallback to concise TL;DR-derived title.
    tldr = _WHITESPACE_PATTERN.sub(" ", str(one_line_tldr or "").strip())
    if tldr:
        compact = _TITLE_END_PUNCT_PATTERN.sub("", tldr).strip()
        if compact:
            first_clause = _TITLE_SPLIT_PATTERN.split(compact, maxsplit=1)[0].strip()
            if 8 <= len(first_clause) <= 72:
                return first_clause
            return compact[:90].rstrip()

    fallback = _WHITESPACE_PATTERN.sub(" ", str(raw_title or "").strip())
    if fallback:
        return fallback[:160].rstrip()
    return "未命名事件"


def _classify_event(item: ProcessedArticle, source_category: str) -> str:
    # Pure LLM category mode: use the keywords-stage category directly.
    _ = source_category
    llm_cat = str(getattr(item, "category", "") or "").strip()
    if llm_cat in CATEGORY_ORDER:
        return llm_cat
    return "其他"


def _build_detail(item: ProcessedArticle) -> str:
    # Prefer LLM-generated detail from keywords stage
    llm_detail = getattr(item, "detail", "") or ""
    llm_detail = llm_detail.strip()
    detail_mode = str(getattr(item, "detail_mode", "full") or "full").strip().lower()
    if llm_detail and (len(llm_detail) >= 50 or detail_mode == "compact"):
        return llm_detail

    # Fallback: use cleaned raw content truncated
    content = _clean_raw_content_for_detail(item.raw.content or "")
    if content:
        if len(content) > 900:
            return f"{content[:900].rstrip()}..."
        return content
    summary = (item.summary or "").strip()
    if summary:
        return f"{summary}（原文未采集到完整正文，已保留关键信息）"
    return "原文正文未采集到可用内容。"


def _clean_raw_content_for_detail(raw_content: str) -> str:
    text = str(raw_content or "")
    if not text.strip():
        return ""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if "Markdown Content:" in normalized:
        normalized = normalized.split("Markdown Content:", 1)[1]
    normalized = _MARKDOWN_LINK_PATTERN.sub(r"\1", normalized)

    kept_lines: list[str] = []
    for raw_line in normalized.split("\n"):
        line = _WHITESPACE_PATTERN.sub(" ", raw_line).strip()
        if not line:
            continue
        lowered = line.lower()
        if any(marker in lowered for marker in _DETAIL_NOISE_MARKERS) and len(line) < 140:
            continue
        if line.count("http") >= 1 and len(line) < 200:
            continue
        if len(line) < 24 and not any(ch.isdigit() for ch in line):
            continue
        kept_lines.append(line)

    if not kept_lines:
        return _WHITESPACE_PATTERN.sub(" ", normalized).strip()
    return _WHITESPACE_PATTERN.sub(" ", " ".join(kept_lines)).strip()


def _extract_links(item: ProcessedArticle) -> list[str]:
    links: list[str] = []

    def add_link(raw: str | None) -> None:
        if not raw:
            return
        link = str(raw).strip()
        if not link:
            return
        if not link.startswith("http"):
            return
        if link not in links:
            links.append(link)

    add_link(item.raw.url)
    maybe_links = item.raw.metadata.get("links")
    if isinstance(maybe_links, list):
        for value in maybe_links:
            add_link(str(value))
    return links


def _extract_entities(source_name: str, title: str, keywords: list[str]) -> list[str]:
    entities: list[str] = []
    seeds = [source_name, *keywords, title]
    for seed in seeds:
        token = str(seed).strip()
        if not token:
            continue
        if len(token) > 64:
            continue
        if token in entities:
            continue
        if any(ch.isupper() for ch in token) or any(ch.isdigit() for ch in token):
            entities.append(token)
        if len(entities) >= 8:
            break
    if not entities and source_name:
        entities.append(source_name)
    return entities


def _extract_metrics(text: str) -> list[str]:
    seen: set[str] = set()
    metrics: list[str] = []
    for match in _METRIC_PATTERN.findall(text or ""):
        metric = str(match).strip()
        if not metric or metric in seen:
            continue
        seen.add(metric)
        metrics.append(metric)
        if len(metrics) >= 6:
            break
    return metrics


def _build_global_tldr(events: list[dict]) -> str:
    if not events:
        return ""

    category_counts = Counter(str(event.get("category", "行业动态")) for event in events)
    dominant = category_counts.most_common(1)[0][0]
    lead_map = {
        "模型发布": "今日 AI 主线是模型能力与交付效率同步升级。",
        "产品应用": "今日 AI 主线是产品化落地继续提速。",
        "技术与洞察": "今日 AI 主线是评测与方法论并行演进。",
        "开发生态": "今日 AI 主线是开发工具链进一步完善。",
        "前瞻与传闻": "今日 AI 主线是前瞻信号增多但仍需证据验证。",
        "要闻": "今日 AI 主线是头部事件密集释放。",
        "行业动态": "今日 AI 主线是平台与生态位变化持续放大。",
    }
    lead = lead_map.get(dominant, lead_map["行业动态"])

    key_titles = [str(event.get("title", "")).strip() for event in events if str(event.get("title", "")).strip()]
    compact_titles: list[str] = []
    for title in key_titles[:2]:
        cleaned = _TITLE_END_PUNCT_PATTERN.sub("", title).strip()
        if len(cleaned) > 18:
            compact_titles.append(f"{cleaned[:18].rstrip()}…")
        elif cleaned:
            compact_titles.append(cleaned)
    if compact_titles:
        trend_line = f"代表性动态包括{'、'.join(compact_titles)}。"
    else:
        trend_line = "重点仍是验证技术能否稳定落地到真实业务。"

    comment_map = {
        "模型发布": "后续更值得关注真实采用速度与单位成本改善。",
        "产品应用": "后续更值得关注流程深度整合与持续留存。",
        "技术与洞察": "后续更值得关注结论在生产环境的可复现性。",
        "前瞻与传闻": "后续更值得关注可验证的官方与代码证据。",
        "开发生态": "后续更值得关注生态兼容性与团队协作效率。",
        "要闻": "后续更值得关注企业侧落地节奏与反馈质量。",
        "行业动态": "后续更值得关注平台策略变化带来的二阶影响。",
    }
    comment = comment_map.get(dominant, comment_map["行业动态"])

    return f"{lead}{trend_line}{comment}"


def _event_time_to_iso(raw: object) -> str | None:
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.isoformat() + "+00:00"
        return raw.isoformat()
    if isinstance(raw, str):
        text = raw.strip()
        return text or None
    return None


def _looks_like_model_release(normalized_text: str) -> bool:
    has_marker = _has_explicit_model_marker(normalized_text)
    has_model_signal = _MODEL_SIGNAL_PATTERN.search(normalized_text) is not None
    has_version = _MODEL_VERSION_PATTERN.search(normalized_text) is not None
    has_variant = any(token in normalized_text for token in _MODEL_VARIANT_TOKENS)
    if has_marker and (has_model_signal or has_version):
        return True
    if has_model_signal and has_version and has_variant:
        return True
    if has_model_signal and has_version and any(token in normalized_text for token in _MODEL_RELEASE_ACTION_TOKENS):
        return True
    return False


def _looks_like_dev_ecosystem_event(normalized_text: str) -> bool:
    return any(token in normalized_text for token in _DEV_ECOSYSTEM_SIGNALS)


def _has_explicit_model_marker(normalized_text: str) -> bool:
    return any(token in normalized_text for token in _MODEL_RELEASE_TOKENS)


def _looks_like_research_event(normalized_text: str) -> bool:
    if any(token in normalized_text for token in _RESEARCH_PRIMARY_SIGNALS):
        return True
    secondary_hits = sum(1 for token in _RESEARCH_SECONDARY_SIGNALS if token in normalized_text)
    return secondary_hits >= 2


def _normalize_match_text(text: str) -> str:
    return (
        str(text or "")
        .replace("‑", "-")
        .replace("–", "-")
        .replace("—", "-")
        .lower()
    )
