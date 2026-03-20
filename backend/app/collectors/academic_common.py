"""Shared helpers for academic API collectors."""

from __future__ import annotations

from datetime import UTC, datetime


def build_search_text(config: dict) -> str:
    search_query = str(config.get("search_query") or "").strip()
    if search_query:
        return search_query
    keywords = [item.strip() for item in config.get("keywords", []) if isinstance(item, str) and item.strip()]
    return " ".join(keywords)


def resolve_limit(raw: object, *, default: int = 20, max_limit: int = 200) -> int:
    if isinstance(raw, int) and 1 <= raw <= max_limit:
        return raw
    if isinstance(raw, str):
        value = raw.strip()
        if value.isdigit():
            normalized = int(value)
            if 1 <= normalized <= max_limit:
                return normalized
    return default


def parse_datetime(raw: object) -> datetime | None:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo is not None else raw.replace(tzinfo=UTC)
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(f"{value}T00:00:00+00:00")
        except ValueError:
            return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
