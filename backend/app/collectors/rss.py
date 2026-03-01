"""通用 RSS Collector。"""

from __future__ import annotations

from datetime import datetime, timezone
import time

import feedparser
import httpx

from app.collectors.base import BaseCollector, RawArticle
from app.collectors.fulltext import DEFAULT_EXTRACTOR_CHAIN, extract_fulltext
from app.collectors.registry import register


@register("rss")
class RSSCollector(BaseCollector):
    """通用 RSS/Atom 采集器（两段式：feed 元数据 + 详情页全文）。"""

    @property
    def name(self) -> str:
        return "RSS"

    @property
    def category(self) -> str:
        return "blog"

    async def collect(self, config: dict) -> list[RawArticle]:
        feed_url = config.get("feed_url") or config.get("url") or config.get("rss_url")
        if not feed_url:
            raise ValueError("RSS collector requires feed_url/url/rss_url")
        max_items = int(config.get("max_items", 30))
        timeout_seconds = float(config.get("timeout_seconds", 20))
        retry_max_attempts = int(config.get("retry_max_attempts", 3))
        user_agent = config.get("user_agent", "LexDeepResearchBot/0.1")
        extractor_chain = config.get("extractor_chain", list(DEFAULT_EXTRACTOR_CHAIN))
        min_content_chars = int(config.get("min_content_chars", 200))

        headers = {
            "User-Agent": user_agent,
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9,*/*;q=0.8",
        }
        async with httpx.AsyncClient(timeout=timeout_seconds, headers=headers) as client:
            feed_response = await _get_with_retry(client, feed_url, retry_max_attempts)
            parsed = feedparser.parse(feed_response.text)
            entries = list(parsed.entries)[:max_items]
            articles: list[RawArticle] = []
            for idx, entry in enumerate(entries):
                link = _entry_value(entry, "link")
                title = _entry_value(entry, "title") or "Untitled"
                external_id = _entry_value(entry, "id") or _entry_value(entry, "guid") or link or f"{feed_url}#{idx}"
                published_at = _entry_datetime(entry)
                summary = (
                    _entry_value(entry, "summary")
                    or _entry_value(entry, "description")
                    or _entry_value(entry, "content")
                    or ""
                )
                content = summary
                extractor = ""
                if link:
                    try:
                        article_response = await _get_with_retry(client, link, retry_max_attempts)
                        extracted, used_extractor = extract_fulltext(
                            article_response.text,
                            extractor_chain=extractor_chain,
                            min_content_chars=min_content_chars,
                        )
                        if extracted:
                            content = extracted
                            extractor = used_extractor
                    except Exception:
                        pass
                articles.append(
                    RawArticle(
                        external_id=str(external_id),
                        title=str(title),
                        url=str(link) if link else None,
                        content=content or None,
                        published_at=published_at,
                        metadata={
                            "collector": "rss",
                            "feed_url": feed_url,
                            "extractor": extractor,
                            "content_length": len(content or ""),
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                )
        return articles


def _entry_value(entry, key: str) -> str | None:
    value = getattr(entry, key, None)
    if value:
        return str(value)
    if isinstance(entry, dict):
        raw = entry.get(key)
        if isinstance(raw, list):
            return str(raw[0]) if raw else None
        if raw is not None:
            return str(raw)
    return None


def _entry_datetime(entry) -> datetime | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed is None:
        return None
    if isinstance(parsed, time.struct_time):
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    return None


async def _get_with_retry(client: httpx.AsyncClient, url: str, max_attempts: int) -> httpx.Response:
    last_exc: Exception | None = None
    for _ in range(max_attempts):
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response
        except Exception as exc:
            last_exc = exc
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Failed to fetch url: {url}")
