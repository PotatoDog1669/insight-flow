"""日报渲染器（事件字段化 + 模板化输出）。"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import re

from app.processors.pipeline import ProcessedArticle
from app.renderers.base import BaseRenderer, RenderContext, Report
from app.template_engine.renderer import render_report_template

CATEGORY_ORDER = ["要闻", "模型发布", "开发生态", "产品应用", "技术与洞察", "行业动态", "前瞻与传闻"]

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
_MODEL_SIGNAL_PATTERN = re.compile(r"\b(gpt|gemini|claude|llama|qwen|mistral|deepseek)\b", re.IGNORECASE)
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
_MODEL_CONTEXT_TOKENS = (
    "model",
    "release",
    "launch",
    "system card",
    "available",
    "api",
    "preview",
    "instant",
    "flash",
    "pro",
    "mini",
    "turbo",
    "发布",
    "上线",
)
MAX_DAILY_EVENTS = 20


class DailyRenderer(BaseRenderer):
    @property
    def level(self) -> str:
        return "L2"

    async def render(self, articles: list[ProcessedArticle], context: RenderContext) -> Report:
        """渲染日报（按事件动态输出，最多 15 条）。"""
        selected_articles = articles[:MAX_DAILY_EVENTS]
        events = [_build_event(item=item, index=idx) for idx, item in enumerate(selected_articles, start=1)]
        global_tldr = _build_global_tldr(events)

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

        content = render_report_template(
            report_type="daily",
            version="v1",
            context={"date": context.date, "overview": overview, "events": events},
        )

        category_counts = Counter(event["category"] for event in events)
        categories = [category for category in CATEGORY_ORDER if category_counts.get(category)]

        return Report(
            level="L2",
            title=f"AI Daily Report — {context.date}",
            content=content,
            article_ids=[item.raw.external_id for item in selected_articles],
            metadata={
                "events": events,
                "categories": categories,
                "global_tldr": global_tldr,
                "tldr": [global_tldr] if global_tldr else [],
                "time_period": "daily",
                "report_type": "daily",
            },
        )


def _build_event(item: ProcessedArticle, index: int) -> dict:
    source_name = str(item.raw.metadata.get("source_name") or "Unknown Source")
    source_category = str(item.raw.metadata.get("source_category") or "").strip().lower()
    one_line_tldr = (item.summary or item.raw.title or "N/A").strip()
    detail = _build_detail(item)
    keywords = [str(keyword).strip() for keyword in item.keywords if str(keyword).strip()]
    entities = _extract_entities(source_name=source_name, title=item.raw.title, keywords=keywords)
    metrics = _extract_metrics(f"{item.raw.title}\n{item.summary}\n{item.raw.content or ''}")
    links = _extract_links(item)
    published_at = _event_time_to_iso(
        item.raw.published_at
        if isinstance(item.raw.published_at, datetime)
        else item.raw.metadata.get("snapshot_at")
    )
    importance = getattr(item, "importance", "normal") or "normal"

    return {
        "event_id": item.raw.external_id,
        "index": index,
        "title": item.raw.title,
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
    }


def _classify_event(item: ProcessedArticle, source_category: str) -> str:
    # importance=high overrides to 要闻
    importance = getattr(item, "importance", "normal") or "normal"
    if importance == "high":
        return "要闻"

    text = " ".join(
        [
            item.raw.title or "",
            item.summary or "",
            " ".join(item.keywords or []),
            str(item.raw.metadata.get("source_name") or ""),
            source_category,
        ]
    ).lower()
    normalized_text = _normalize_match_text(text)
    if _looks_like_model_release(normalized_text):
        return "模型发布"
    for category in CATEGORY_ORDER:
        if category == "要闻":
            continue  # 要闻 is only assigned via importance
        for keyword in _CATEGORY_KEYWORDS.get(category, ()):
            if keyword in normalized_text:
                return category
    if source_category in {"academic", "research"}:
        return "技术与洞察"
    if source_category in {"open_source"}:
        return "开发生态"
    return "行业动态"


def _build_detail(item: ProcessedArticle) -> str:
    # Prefer LLM-generated detail from keywords stage
    llm_detail = getattr(item, "detail", "") or ""
    llm_detail = llm_detail.strip()
    if llm_detail and len(llm_detail) >= 50:
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

    count = len(events)
    category_counts = Counter(str(event.get("category", "行业动态")) for event in events)
    category_summary = "，".join([f"{name}{category_counts[name]}条" for name in CATEGORY_ORDER if category_counts.get(name)])

    key_titles = [str(event.get("title", "")).strip() for event in events[:3] if str(event.get("title", "")).strip()]
    keyline = "；".join(key_titles) if key_titles else "暂无可展示重点事件"
    summary = f"今日共整理 {count} 条 AI 事件，按主题分布为：{category_summary}。重点包括：{keyline}。"

    dominant = category_counts.most_common(1)[0][0]
    if dominant == "模型发布":
        comment = "模型发布仍是主轴，性能数字继续内卷，下一阶段比拼将转向工程化成本与真实场景转化率。"
    elif dominant == "产品应用":
        comment = "产品层动作最密集，说明能力红利正快速向交付与流程整合迁移。"
    elif dominant == "技术与洞察":
        comment = "研究与评测信息密集出现，短期要警惕“指标领先但落地滞后”的叙事偏差。"
    elif dominant == "前瞻与传闻":
        comment = "传闻占比提升时，信息噪音会同步上升，需优先追踪可验证的官方与代码证据。"
    else:
        comment = "行业侧信号偏强，策略上应同步跟踪资本、政策与平台入口变化带来的二阶影响。"

    return f"总结：{summary}\n锐评：{comment}"


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
    if not _MODEL_SIGNAL_PATTERN.search(normalized_text):
        return False
    return any(token in normalized_text for token in _MODEL_CONTEXT_TOKENS)


def _normalize_match_text(text: str) -> str:
    return (
        str(text or "")
        .replace("‑", "-")
        .replace("–", "-")
        .replace("—", "-")
        .lower()
    )
