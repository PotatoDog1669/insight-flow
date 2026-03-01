"""HTML 正文抽取工具（支持多策略回退）。"""

from __future__ import annotations

import re
from typing import Iterable

from bs4 import BeautifulSoup
from selectolax.parser import HTMLParser


DEFAULT_EXTRACTOR_CHAIN = ("trafilatura", "readability", "selectolax", "bs4")


def extract_fulltext(
    html: str,
    extractor_chain: Iterable[str] | None = None,
    min_content_chars: int = 200,
) -> tuple[str, str]:
    """按抽取器链路提取正文，返回 (content, extractor_name)。"""
    chain = tuple(extractor_chain or DEFAULT_EXTRACTOR_CHAIN)
    for extractor in chain:
        text = _extract_with(extractor, html)
        normalized = _normalize_text(text)
        if len(normalized) >= min_content_chars:
            return normalized, extractor
    return "", ""


def _extract_with(extractor: str, html: str) -> str:
    if extractor == "trafilatura":
        return _extract_trafilatura(html)
    if extractor == "readability":
        return _extract_readability(html)
    if extractor == "selectolax":
        return _extract_selectolax(html)
    if extractor == "bs4":
        return _extract_bs4(html)
    return ""


def _extract_trafilatura(html: str) -> str:
    try:
        import trafilatura  # type: ignore
    except Exception:
        return ""
    extracted = trafilatura.extract(html, include_comments=False, include_tables=False)
    return extracted or ""


def _extract_readability(html: str) -> str:
    try:
        from readability import Document  # type: ignore
    except Exception:
        return ""
    try:
        summary_html = Document(html).summary(html_partial=True)
    except Exception:
        return ""
    soup = BeautifulSoup(summary_html, "html.parser")
    return soup.get_text("\n", strip=True)


def _extract_selectolax(html: str) -> str:
    try:
        tree = HTMLParser(html)
    except Exception:
        return ""
    for selector in ("article", "main", ".post-content", ".entry-content", ".content", "body"):
        node = tree.css_first(selector)
        if not node:
            continue
        text = node.text(separator="\n", strip=True)
        if text:
            return text
    return ""


def _extract_bs4(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for selector in ("article", "main", ".post-content", ".entry-content", ".content", "body"):
        node = soup.select_one(selector)
        if node:
            text = node.get_text("\n", strip=True)
            if text:
                return text
    return soup.get_text("\n", strip=True)


def _normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text
