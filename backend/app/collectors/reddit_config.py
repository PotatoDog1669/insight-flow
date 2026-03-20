from __future__ import annotations

from urllib.parse import urlencode

DEFAULT_REDDIT_SUBREDDITS = ("LocalLLaMA", "singularity", "OpenAI")


def normalize_reddit_subreddit(value: object) -> str:
    if not isinstance(value, str):
        return ""
    normalized = value.strip()
    if normalized.lower().startswith("r/"):
        normalized = normalized[2:]
    normalized = normalized.strip().strip("/")
    if not normalized or any(char.isspace() for char in normalized) or "/" in normalized:
        return ""
    return normalized


def normalize_reddit_subreddits(values: object) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = normalize_reddit_subreddit(value)
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized


def merge_reddit_subreddits(existing_values: object, synced_values: object) -> list[str]:
    synced = normalize_reddit_subreddits(synced_values)
    preferred = {item.lower(): item for item in synced}
    merged: list[str] = []
    seen: set[str] = set()

    for bucket in (existing_values, synced):
        values = normalize_reddit_subreddits(bucket)
        for value in values:
            canonical = preferred.get(value.lower(), value)
            key = canonical.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(canonical)
    return merged


def build_reddit_feed_url(subreddits: object) -> str:
    normalized = normalize_reddit_subreddits(subreddits)
    if not normalized:
        normalized = list(DEFAULT_REDDIT_SUBREDDITS)
    query = " OR ".join(f"subreddit:{item}" for item in normalized)
    return f"https://www.reddit.com/search.rss?{urlencode({'q': query, 'sort': 'new'})}"
