"""Compact weak-input and low-information event details."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.collectors.base import RawArticle

if TYPE_CHECKING:
    from app.processors.event_models import ProcessedEvent
    from app.processors.pipeline import ProcessedArticle

URL_PATTERN = re.compile(r"https?://\S+|t\.co/\S+", re.IGNORECASE)
METRIC_PATTERN = re.compile(r"\b\d+(?:\.\d+)?(?:%|x|k|m|b|亿|万)?\b", re.IGNORECASE)
DATE_PATTERN = re.compile(r"(20\d{2}[-/年.]\d{1,2}(?:[-/月.]\d{1,2})?|\d{1,2}月\d{1,2}日)")
PLACEHOLDER_PHRASES = (
    "未知",
    "待定",
    "暂无信息",
    "暂无公开数据",
    "需等待更多信源",
    "只有链接",
    "没有上下文",
    "无法判断",
)
_PLATFORM_PATTERNS = (
    (re.compile(r"\bios\b", re.IGNORECASE), "iOS"),
    (re.compile(r"\bandroid\b", re.IGNORECASE), "Android"),
    (re.compile(r"\bmacos\b", re.IGNORECASE), "macOS"),
    (re.compile(r"\bipad\b", re.IGNORECASE), "iPad"),
    (re.compile(r"\biphone\b", re.IGNORECASE), "iPhone"),
)
_LAUNCH_PATTERNS = (
    re.compile(r"\bavailable\b", re.IGNORECASE),
    re.compile(r"\bdownload\b", re.IGNORECASE),
    re.compile(r"上线"),
    re.compile(r"推出"),
    re.compile(r"可用"),
)


def is_weak_social_input(article: RawArticle) -> bool:
    metadata = article.metadata if isinstance(article.metadata, dict) else {}
    source_category = str(metadata.get("source_category") or "").strip().lower()
    source_name = str(metadata.get("source_name") or "").strip().lower()
    if source_category != "social" and " x" not in f" {source_name}" and "twitter" not in source_name:
        return False
    text = _normalize_text(article.content or article.title or "")
    if not text or len(text) > 220 or not URL_PATTERN.search(text):
        return False
    text_without_links = _normalize_text(URL_PATTERN.sub("", text))
    return len(text_without_links) <= 80


def is_low_information_detail(detail: str) -> bool:
    text = _normalize_text(detail)
    if not text:
        return True
    placeholder_hits = sum(text.count(phrase) for phrase in PLACEHOLDER_PHRASES)
    if placeholder_hits < 2:
        return False
    if METRIC_PATTERN.search(text) or DATE_PATTERN.search(text):
        return False
    return True


def apply_content_quality_gate(article: ProcessedArticle) -> ProcessedArticle:
    if is_weak_social_input(article.raw) or is_low_information_detail(article.detail):
        article.detail = _compact_fact(article)
        article.detail_mode = "compact"
        if article.availability in {"暂无信息", "暂无公开数据"}:
            article.availability = ""
        if article.unknowns in {"无明显信息缺口", "暂无信息", "待定"}:
            article.unknowns = ""
    return article


def apply_event_content_quality_gate(event: ProcessedEvent) -> ProcessedEvent:
    if is_low_information_detail(event.detail):
        event.detail = _ensure_sentence(_normalize_text(event.summary)[:80]) or "信息较弱，当前保留一句事实。"
        event.detail_mode = "compact"
        if event.availability in {"暂无信息", "暂无公开数据"}:
            event.availability = ""
        if event.unknowns in {"无明显信息缺口", "暂无信息", "待定"}:
            event.unknowns = ""
    return event


def _compact_fact(article: ProcessedArticle) -> str:
    product_launch_brief = _build_social_product_launch_brief(article)
    if product_launch_brief:
        return product_launch_brief
    summary = _normalize_text(article.summary)
    if summary:
        return _ensure_sentence(summary[:80])
    fallback = _normalize_text(URL_PATTERN.sub("", article.raw.title or ""))
    if fallback:
        return _ensure_sentence(fallback[:80])
    return "信息较弱，当前保留一句事实。"


def _ensure_sentence(text: str) -> str:
    cleaned = str(text or "").strip().rstrip("。；;，,")
    if not cleaned:
        return ""
    return f"{cleaned}。"


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _build_social_product_launch_brief(article: ProcessedArticle) -> str:
    metadata = article.raw.metadata if isinstance(article.raw.metadata, dict) else {}
    author_name = _normalize_text(metadata.get("author_name") or metadata.get("author_username") or "")
    if not author_name:
        return ""

    combined_text = _normalize_text(
        "\n".join(
            [
                article.event_title,
                article.summary,
                article.raw.title or "",
                article.raw.content or "",
            ]
        )
    )
    platform = _extract_platform(combined_text)
    product = _extract_product_name(article)
    if not product or not platform:
        return ""
    if not any(pattern.search(combined_text) for pattern in _LAUNCH_PATTERNS):
        return ""

    if author_name.lower() == product.lower():
        first_sentence = f"{product} 已上线 {platform}"
    else:
        first_sentence = f"{author_name} 宣布旗下 {product} 已上线 {platform}"

    if _has_app_store_link(article):
        first_sentence = f"{first_sentence}，用户现可通过 App Store 下载"
    elif _has_google_play_link(article):
        first_sentence = f"{first_sentence}，用户现可通过 Google Play 下载"

    return (
        f"{_ensure_sentence(first_sentence)}"
        f"原帖确认了 {platform} 版本已可用，但具体功能范围、开放地区与定价细节尚未说明。"
    )


def _extract_platform(text: str) -> str:
    normalized = _normalize_text(text)
    for pattern, platform in _PLATFORM_PATTERNS:
        if pattern.search(normalized):
            return platform
    return ""


def _extract_product_name(article: ProcessedArticle) -> str:
    candidates = [article.event_title, article.summary, article.raw.title or ""]
    patterns = (
        re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9 .:+_-]{0,40}?)\s*(?:推出|上线|发布)"),
        re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9 .:+_-]{0,40}?)\s*(?:已)?上线"),
        re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9 .:+_-]{0,40}?)\s+is now available", re.IGNORECASE),
    )
    for candidate in candidates:
        text = _normalize_text(candidate)
        if not text:
            continue
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                return match.group(1).strip(" .:-_")
    return ""


def _has_app_store_link(article: ProcessedArticle) -> bool:
    combined = f"{article.raw.content or ''}\n{article.raw.url or ''}".lower()
    return "apps.apple.com" in combined or "app store" in combined


def _has_google_play_link(article: ProcessedArticle) -> bool:
    combined = f"{article.raw.content or ''}\n{article.raw.url or ''}".lower()
    return "play.google.com" in combined or "google play" in combined
