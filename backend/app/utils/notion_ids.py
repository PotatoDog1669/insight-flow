"""Utilities for extracting Notion object IDs from raw input."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, unquote, urlparse

_NOTION_ID_PATTERN = re.compile(
    r"([0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)
_QUERY_ID_KEYS = ("database_id", "page_id", "id", "p", "block_id")


def extract_notion_id(value: str | None) -> str | None:
    """Extract a canonical 32-char Notion ID from an ID or notion.so URL."""
    if value is None:
        return None

    raw = unquote(str(value).strip())
    if not raw:
        return None

    if _is_notion_id(raw):
        return _canonicalize(raw)

    parsed = urlparse(raw)
    if parsed.netloc and "notion.so" in parsed.netloc.lower():
        path_candidates = _extract_ids(parsed.path)
        if path_candidates:
            return _canonicalize(path_candidates[-1])

        query_pairs = parse_qsl(parsed.query, keep_blank_values=False)
        lower_pairs = [(k.lower(), v) for k, v in query_pairs]
        for key in _QUERY_ID_KEYS:
            for pair_key, pair_value in lower_pairs:
                if pair_key == key:
                    candidate = _first_id(pair_value)
                    if candidate:
                        return _canonicalize(candidate)

    fallback = _first_id(raw)
    if fallback:
        return _canonicalize(fallback)

    return None


def _extract_ids(text: str) -> list[str]:
    return [match.group(1) for match in _NOTION_ID_PATTERN.finditer(text or "")]


def _first_id(text: str) -> str | None:
    match = _NOTION_ID_PATTERN.search(text or "")
    if match:
        return match.group(1)
    return None


def _is_notion_id(text: str) -> bool:
    compact = text.replace("-", "")
    return bool(re.fullmatch(r"[0-9a-fA-F]{32}", compact))


def _canonicalize(text: str) -> str:
    return text.replace("-", "").lower()
