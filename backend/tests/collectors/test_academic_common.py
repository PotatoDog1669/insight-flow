from __future__ import annotations

from datetime import UTC, datetime

from app.collectors.academic_common import build_search_text, parse_datetime, resolve_limit


def test_build_search_text_prefers_explicit_query() -> None:
    assert build_search_text({"search_query": "graph agents", "keywords": ["ignored"]}) == "graph agents"


def test_build_search_text_joins_keywords() -> None:
    assert build_search_text({"keywords": [" reasoning ", "", "agent"]}) == "reasoning agent"


def test_resolve_limit_accepts_int_and_string() -> None:
    assert resolve_limit(5) == 5
    assert resolve_limit("12") == 12
    assert resolve_limit("oops", default=7) == 7


def test_parse_datetime_supports_iso_and_date_only() -> None:
    assert parse_datetime("2026-03-20T08:30:00Z") == datetime(2026, 3, 20, 8, 30, tzinfo=UTC)
    assert parse_datetime("2026-03-20") == datetime(2026, 3, 20, 0, 0, tzinfo=UTC)
