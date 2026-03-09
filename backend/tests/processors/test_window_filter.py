from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.collectors.base import RawArticle
from app.processors.window_filter import filter_raw_articles_by_window


@pytest.mark.asyncio
async def test_filter_raw_articles_by_window_supports_first_seen_fallback() -> None:
    now = datetime.now(timezone.utc)
    raw_articles = [
        RawArticle(
            external_id="snapshot-window",
            title="Snapshot",
            metadata={"snapshot_at": (now - timedelta(hours=3)).isoformat()},
        ),
        RawArticle(external_id="already-seen", title="Seen"),
        RawArticle(external_id="new-item", title="New"),
    ]

    async def _existing_external_ids(external_ids: list[str]) -> set[str]:
        assert set(external_ids) == {"already-seen", "new-item"}
        return {"already-seen"}

    kept, trace = await filter_raw_articles_by_window(
        raw_articles=raw_articles,
        window_start=now - timedelta(hours=24),
        window_end=now,
        window_hours=24,
        allow_first_seen_fallback=True,
        existing_external_ids_resolver=_existing_external_ids,
    )

    assert [item.external_id for item in kept] == ["snapshot-window", "new-item"]
    assert trace["before"] == 3
    assert trace["after"] == 2
    assert trace["first_seen_fallback"] == 1
    assert trace["allow_first_seen_fallback"] is True


@pytest.mark.asyncio
async def test_filter_raw_articles_by_window_parses_title_date_when_published_at_missing() -> None:
    now = datetime(2026, 3, 7, 12, 0, tzinfo=timezone.utc)
    raw_articles = [
        RawArticle(
            external_id="anthropic-current",
            title="Mar 7, 2026 Announcements Claude helps security teams",
            url="https://anthropic.com/news/claude-security-teams",
        ),
        RawArticle(
            external_id="anthropic-old",
            title="Feb 17, 2026 Product Introducing Claude Sonnet 4.6",
            url="https://anthropic.com/news/claude-sonnet-4-6",
        ),
    ]

    kept, trace = await filter_raw_articles_by_window(
        raw_articles=raw_articles,
        window_start=now - timedelta(hours=24),
        window_end=now,
        window_hours=24,
        allow_first_seen_fallback=False,
        now_utc=now,
    )

    assert [item.external_id for item in kept] == ["anthropic-current"]
    assert trace["before"] == 2
    assert trace["after"] == 1
    assert trace["outside_window"] == 1
