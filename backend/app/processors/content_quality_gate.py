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
