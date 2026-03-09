"""Shared raw-article window filtering."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
import re

from app.collectors.base import RawArticle

ExistingExternalIdsResolver = Callable[[list[str]], Awaitable[set[str]]]
TITLE_DATE_PATTERN = re.compile(
    r"\b(?P<month>Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|Sept|September|Oct|October|Nov|November|Dec|December)\s+"
    r"(?P<day>\d{1,2}),\s*(?P<year>\d{4})\b",
    re.IGNORECASE,
)


def _normalize_datetime(raw: object) -> datetime | None:
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    text = str(raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _infer_event_time_from_title(title: object) -> datetime | None:
    text = str(title or "").strip()
    if not text:
        return None
    match = TITLE_DATE_PATTERN.search(text)
    if not match:
        return None
    candidate = f"{match.group('month')} {match.group('day')}, {match.group('year')}"
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            parsed = datetime.strptime(candidate, fmt)
        except ValueError:
            continue
        return parsed.replace(tzinfo=timezone.utc)
    return None


async def filter_raw_articles_by_window(
    *,
    raw_articles: list[RawArticle],
    window_start: datetime,
    window_end: datetime,
    window_hours: int,
    allow_first_seen_fallback: bool,
    existing_external_ids_resolver: ExistingExternalIdsResolver | None = None,
    now_utc: datetime | None = None,
) -> tuple[list[RawArticle], dict]:
    if not raw_articles:
        return [], {
            "stage": "window_filter",
            "provider": "monitor_window",
            "status": "success",
            "window_hours": window_hours,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "before": 0,
            "after": 0,
            "outside_window": 0,
            "first_seen_fallback": 0,
            "missing_event_time": 0,
            "snapshot_after_window_end": 0,
            "allow_first_seen_fallback": allow_first_seen_fallback,
        }

    kept: list[RawArticle] = []
    pending_first_seen: list[RawArticle] = []
    outside_window = 0
    snapshot_after_window_end = 0
    missing_event_time = 0
    current_time = now_utc or datetime.now(timezone.utc)

    for raw in raw_articles:
        published_event_time = _normalize_datetime(raw.published_at)
        metadata = raw.metadata if isinstance(raw.metadata, dict) else {}
        snapshot_event_time = _normalize_datetime(metadata.get("snapshot_at")) if published_event_time is None else None
        title_event_time = _infer_event_time_from_title(raw.title) if published_event_time is None and snapshot_event_time is None else None
        event_time = published_event_time or snapshot_event_time or title_event_time
        if event_time is None:
            if allow_first_seen_fallback:
                pending_first_seen.append(raw)
            else:
                outside_window += 1
                missing_event_time += 1
            continue
        if window_start <= event_time <= current_time:
            kept.append(raw)
            if event_time > window_end:
                snapshot_after_window_end += 1
            continue
        outside_window += 1

    first_seen_kept = 0
    if pending_first_seen:
        existing_external_ids: set[str] = set()
        candidate_ids = [item.external_id for item in pending_first_seen if item.external_id]
        if candidate_ids and existing_external_ids_resolver is not None:
            existing_external_ids = await existing_external_ids_resolver(candidate_ids)
        for item in pending_first_seen:
            if not item.external_id or item.external_id not in existing_external_ids:
                kept.append(item)
                first_seen_kept += 1

    return kept, {
        "stage": "window_filter",
        "provider": "monitor_window",
        "status": "success",
        "window_hours": window_hours,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "before": len(raw_articles),
        "after": len(kept),
        "outside_window": outside_window,
        "first_seen_fallback": first_seen_kept,
        "snapshot_after_window_end": snapshot_after_window_end,
        "missing_event_time": missing_event_time,
        "allow_first_seen_fallback": allow_first_seen_fallback,
    }
