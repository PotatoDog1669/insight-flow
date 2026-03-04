from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest

from app.collectors.base import RawArticle
from app.models.source import Source
from app.scheduler.orchestrator import Orchestrator


class _ScalarResult:
    def __init__(self, values: list[str]):
        self._values = values

    def scalars(self) -> "_ScalarResult":
        return self

    def all(self) -> list[str]:
        return self._values


class _FakeSession:
    def __init__(self, existing_external_ids: set[str]):
        self._existing_external_ids = existing_external_ids

    async def execute(self, _stmt) -> _ScalarResult:
        return _ScalarResult(list(self._existing_external_ids))


def _source(config: dict | None = None) -> Source:
    return Source(
        id=uuid.uuid4(),
        name="Test Source",
        category="blog",
        collect_method="rss",
        config=config or {},
        enabled=True,
    )


@pytest.mark.asyncio
async def test_window_filter_keeps_only_articles_with_event_time_in_window() -> None:
    orchestrator = Orchestrator(max_concurrency=1)
    now = datetime.now(timezone.utc)

    raw_articles = [
        RawArticle(external_id="in-window", title="In", published_at=now - timedelta(hours=2)),
        RawArticle(external_id="out-window", title="Out", published_at=now - timedelta(hours=30)),
    ]

    kept, trace = await orchestrator._filter_raw_articles_by_window(
        db=_FakeSession(existing_external_ids=set()),
        source=_source(),
        raw_articles=raw_articles,
        window_start=now - timedelta(hours=24),
        window_end=now,
        window_hours=24,
    )

    assert [item.external_id for item in kept] == ["in-window"]
    assert trace["before"] == 2
    assert trace["after"] == 1
    assert trace["outside_window"] == 1
    assert trace["first_seen_fallback"] == 0
    assert trace["snapshot_after_window_end"] == 0
    assert trace["missing_event_time"] == 0
    assert trace["allow_first_seen_fallback"] is False


@pytest.mark.asyncio
async def test_window_filter_uses_snapshot_at_and_drops_missing_event_time_by_default() -> None:
    orchestrator = Orchestrator(max_concurrency=1)
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

    kept, trace = await orchestrator._filter_raw_articles_by_window(
        db=_FakeSession(existing_external_ids={"already-seen"}),
        source=_source(),
        raw_articles=raw_articles,
        window_start=now - timedelta(hours=24),
        window_end=now,
        window_hours=24,
    )

    assert [item.external_id for item in kept] == ["snapshot-window"]
    assert trace["before"] == 3
    assert trace["after"] == 1
    assert trace["outside_window"] == 2
    assert trace["first_seen_fallback"] == 0
    assert trace["snapshot_after_window_end"] == 0
    assert trace["missing_event_time"] == 2
    assert trace["allow_first_seen_fallback"] is False


@pytest.mark.asyncio
async def test_window_filter_can_opt_in_first_seen_fallback() -> None:
    orchestrator = Orchestrator(max_concurrency=1)
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

    kept, trace = await orchestrator._filter_raw_articles_by_window(
        db=_FakeSession(existing_external_ids={"already-seen"}),
        source=_source(config={"window_allow_first_seen_fallback": True}),
        raw_articles=raw_articles,
        window_start=now - timedelta(hours=24),
        window_end=now,
        window_hours=24,
    )

    assert [item.external_id for item in kept] == ["snapshot-window", "new-item"]
    assert trace["before"] == 3
    assert trace["after"] == 2
    assert trace["outside_window"] == 0
    assert trace["first_seen_fallback"] == 1
    assert trace["snapshot_after_window_end"] == 0
    assert trace["missing_event_time"] == 0
    assert trace["allow_first_seen_fallback"] is True


@pytest.mark.asyncio
async def test_window_filter_keeps_snapshot_items_collected_after_run_window_end() -> None:
    orchestrator = Orchestrator(max_concurrency=1)
    now = datetime.now(timezone.utc)

    raw_articles = [
        RawArticle(
            external_id="snapshot-after-window-end",
            title="Snapshot Late",
            metadata={"snapshot_at": (now - timedelta(minutes=1)).isoformat()},
        ),
    ]

    kept, trace = await orchestrator._filter_raw_articles_by_window(
        db=_FakeSession(existing_external_ids=set()),
        source=_source(),
        raw_articles=raw_articles,
        window_start=now - timedelta(hours=24),
        window_end=now - timedelta(minutes=5),
        window_hours=24,
    )

    assert [item.external_id for item in kept] == ["snapshot-after-window-end"]
    assert trace["before"] == 1
    assert trace["after"] == 1
    assert trace["outside_window"] == 0
    assert trace["first_seen_fallback"] == 0
    assert trace["snapshot_after_window_end"] == 1
    assert trace["missing_event_time"] == 0
    assert trace["allow_first_seen_fallback"] is False
