"""技术博客爬虫 Collector。"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import httpx

from app.collectors.base import BaseCollector, RawArticle
from app.collectors.registry import register
from app.collectors.site_profile_loader import load_site_profile, validate_site_profile


@register("blog_scraper")
class BlogScraperCollector(BaseCollector):
    """技术博客定向爬虫采集器（profile 驱动）。"""

    @property
    def name(self) -> str:
        return "Blog Scraper"

    @property
    def category(self) -> str:
        return "blog"

    async def collect(self, config: dict) -> list[RawArticle]:
        profile = _resolve_profile(config)
        validate_site_profile(profile)
        timeout_seconds = float(config.get("timeout_seconds", 20))
        max_items = int(config.get("max_items", 20))
        user_agent = config.get("user_agent", "LexDeepResearchBot/0.1")

        start_urls = profile.get("start_urls", [])
        list_page = profile.get("list_page", {})
        detail_page = profile.get("detail_page", {})
        normalization = profile.get("normalization", {})
        min_content_chars = int(normalization.get("min_content_chars", 200))
        url_prefix = normalization.get("url_prefix")

        async with httpx.AsyncClient(timeout=timeout_seconds, headers={"User-Agent": user_agent}) as client:
            entries: list[dict[str, Any]] = []
            for start_url in start_urls:
                try:
                    response = await client.get(start_url)
                    response.raise_for_status()
                except Exception:
                    continue
                entries.extend(_extract_list_entries(response.text, base_url=start_url, list_page=list_page, url_prefix=url_prefix))

            dedup: dict[str, dict[str, Any]] = {}
            for entry in entries:
                dedup[entry["url"]] = entry
            selected_entries = list(dedup.values())[:max_items]

            results: list[RawArticle] = []
            for entry in selected_entries:
                url = entry["url"]
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                except Exception:
                    continue
                content, published_at = _extract_detail(response.text, detail_page)
                if len(content) < min_content_chars:
                    continue
                results.append(
                    RawArticle(
                        external_id=url,
                        title=entry.get("title") or url,
                        url=url,
                        content=content,
                        published_at=published_at or entry.get("published_at"),
                        metadata={
                            "collector": "blog_scraper",
                            "site_key": profile.get("site_key"),
                            "profile_version": profile.get("profile_version", "v1"),
                            "content_selector": detail_page.get("content_selector"),
                            "content_length": len(content),
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                )
        return results


def _resolve_profile(config: dict) -> dict[str, Any]:
    profile = config.get("profile")
    if isinstance(profile, dict):
        return profile
    site_key = config.get("site_key")
    if site_key:
        return load_site_profile(str(site_key))
    raise ValueError("BlogScraper collector requires profile dict or site_key")


def _extract_list_entries(
    html: str,
    base_url: str,
    list_page: dict,
    url_prefix: str | None,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    item_selector = list_page.get("item_selector", "a[href]")
    url_selector = list_page.get("url_selector")
    url_attr = list_page.get("url_attr", "href")
    title_selector = list_page.get("title_selector")
    published_selector = list_page.get("published_selector")
    published_attr = list_page.get("published_attr")

    entries: list[dict[str, Any]] = []
    for item in soup.select(item_selector):
        url_node = item.select_one(url_selector) if url_selector else item
        raw_url = url_node.get(url_attr) if url_node and hasattr(url_node, "get") else None
        if not raw_url:
            continue
        normalized_url = _normalize_url(raw_url, base_url=base_url, url_prefix=url_prefix)
        title_node = item.select_one(title_selector) if title_selector else item
        title = title_node.get_text(" ", strip=True) if title_node else normalized_url

        published_at = None
        if published_selector:
            published_node = item.select_one(published_selector)
            if published_node:
                raw_published = (
                    published_node.get(published_attr) if published_attr else published_node.get_text(" ", strip=True)
                )
                published_at = _parse_datetime(raw_published)
        entries.append({"url": normalized_url, "title": title or normalized_url, "published_at": published_at})
    return entries


def _extract_detail(html: str, detail_page: dict) -> tuple[str, datetime | None]:
    soup = BeautifulSoup(html, "html.parser")
    for selector in detail_page.get("remove_selectors", []):
        for node in soup.select(selector):
            node.decompose()

    content_selector = detail_page.get("content_selector", "article")
    container = soup.select_one(content_selector) or soup.select_one("main") or soup.body or soup
    content = container.get_text("\n", strip=True) if container else ""
    published_at = None
    published_selector = detail_page.get("published_selector")
    if published_selector:
        published_node = soup.select_one(published_selector)
        if published_node:
            published_attr = detail_page.get("published_attr")
            raw_published = published_node.get(published_attr) if published_attr else published_node.get_text(" ", strip=True)
            published_at = _parse_datetime(raw_published)
    return content.strip(), published_at


def _normalize_url(raw_url: str, base_url: str, url_prefix: str | None) -> str:
    if raw_url.startswith("http://") or raw_url.startswith("https://"):
        return raw_url
    if url_prefix:
        return urljoin(url_prefix.rstrip("/") + "/", raw_url.lstrip("/"))
    return urljoin(base_url, raw_url)


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
