"""技术博客爬虫 Collector。"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
import json
import re
from typing import Any
from urllib.parse import urljoin
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import httpx

from app.collectors.base import BaseCollector, RawArticle
from app.collectors.registry import register
from app.collectors.site_profile_loader import load_site_profile, validate_site_profile

_TEXT_DATETIME_PATTERNS = (
    re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?(?:Z|[+-]\d{2}:\d{2})?\b"),
    re.compile(r"\b\d{4}/\d{1,2}/\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\b"),
    re.compile(r"\b\d{4}\.\d{1,2}\.\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\b"),
    re.compile(r"\b\d{4}年\d{1,2}月\d{1,2}日(?:\s*\d{1,2}:\d{2}(?::\d{2})?)?\b"),
)
_GENERIC_PUBLISHED_SELECTORS = (
    ("time[datetime]", "datetime"),
    ("time[dateTime]", "datetime"),
    ("meta[property='article:published_time']", "content"),
    ("meta[name='publish_date']", "content"),
    ("meta[name='publishdate']", "content"),
    ("meta[name='pubdate']", "content"),
)
_STRUCTURED_DATA_DATE_KEYS = ("datePublished", "dateCreated", "uploadDate")


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

        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True, headers={"User-Agent": user_agent}) as client:
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
                existing = dedup.get(entry["url"])
                if existing is None or _is_better_entry(candidate=entry, existing=existing):
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
                content, published_at, detail_title = _extract_detail(response.text, detail_page)
                if len(content) < min_content_chars:
                    continue
                results.append(
                    RawArticle(
                        external_id=url,
                        title=_resolve_article_title(entry.get("title"), detail_title, url),
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
        site_key = config.get("site_key")
        if isinstance(site_key, str) and site_key:
            try:
                base_profile = load_site_profile(site_key)
            except (FileNotFoundError, ValueError):
                return profile
            return _deep_merge_profile(base_profile, profile)
        return profile
    site_key = config.get("site_key")
    if site_key:
        return load_site_profile(str(site_key))
    raise ValueError("BlogScraper collector requires profile dict or site_key")


def _deep_merge_profile(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = _deep_merge_profile(base[key], value)
            continue
        merged[key] = value
    return merged


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
        if not raw_url or _should_skip_raw_url(raw_url):
            continue
        normalized_url = _normalize_url(raw_url, base_url=base_url, url_prefix=url_prefix)
        if _should_skip_normalized_url(normalized_url, base_url=base_url):
            continue
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


def _extract_detail(html: str, detail_page: dict) -> tuple[str, datetime | None, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    for selector in detail_page.get("remove_selectors", []):
        for node in soup.select(selector):
            node.decompose()

    content_selector = detail_page.get("content_selector", "article")
    container = soup.select_one(content_selector) or soup.select_one("main") or soup.body or soup
    content = container.get_text("\n", strip=True) if container else ""
    detail_title = _extract_detail_title(soup, detail_page)
    published_at = _extract_detail_published_at(soup, detail_page, container)
    return content.strip(), published_at, detail_title


def _normalize_url(raw_url: str, base_url: str, url_prefix: str | None) -> str:
    if raw_url.startswith("http://") or raw_url.startswith("https://"):
        return raw_url
    if url_prefix:
        return urljoin(url_prefix.rstrip("/") + "/", raw_url.lstrip("/"))
    return urljoin(base_url, raw_url)


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    normalized_text = re.sub(r"\s+", " ", text).strip()
    text = normalized_text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    normalized = normalized_text.replace("年", "-").replace("月", "-").replace("日", "")
    normalized = normalized.replace("/", "-").replace(".", "-")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(normalized, fmt)
        except ValueError:
            continue
        return parsed.replace(tzinfo=timezone.utc)
    return None


def _extract_detail_published_at(soup: BeautifulSoup, detail_page: dict, container: Any) -> datetime | None:
    published_selector = detail_page.get("published_selector")
    if isinstance(published_selector, str) and published_selector.strip():
        published_node = soup.select_one(published_selector)
        if published_node:
            published_attr = detail_page.get("published_attr")
            raw_published = published_node.get(published_attr) if published_attr else published_node.get_text(" ", strip=True)
            published_at = _parse_datetime(raw_published)
            if published_at is not None:
                return published_at

    for selector, attr in _GENERIC_PUBLISHED_SELECTORS:
        published_node = soup.select_one(selector)
        if published_node is None:
            continue
        raw_published = published_node.get(attr) if attr else published_node.get_text(" ", strip=True)
        published_at = _parse_datetime(raw_published)
        if published_at is not None:
            return published_at

    for candidate_text in _build_published_text_candidates(soup, container):
        published_at = _find_datetime_in_text(candidate_text)
        if published_at is not None:
            return published_at

    return _extract_structured_data_published_at(soup)


def _build_published_text_candidates(soup: BeautifulSoup, container: Any) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def _push(text: str | None, *, limit: int | None = None) -> None:
        normalized = re.sub(r"\s+", " ", str(text or "")).strip()
        if not normalized:
            return
        if limit is not None:
            normalized = normalized[:limit]
        if normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    h1 = soup.select_one("h1")
    if h1 is not None and getattr(h1, "parent", None) is not None:
        _push(h1.parent.get_text(" ", strip=True), limit=600)
    if container is not None and hasattr(container, "get_text"):
        _push(container.get_text(" ", strip=True), limit=1200)
    return candidates


def _find_datetime_in_text(text: str | None) -> datetime | None:
    if not text:
        return None
    matches: list[tuple[int, str]] = []
    for pattern in _TEXT_DATETIME_PATTERNS:
        for match in pattern.finditer(text):
            matches.append((match.start(), match.group(0)))
    for _, candidate in sorted(matches, key=lambda item: item[0]):
        parsed = _parse_datetime(candidate)
        if parsed is not None:
            return parsed
    return None


def _extract_structured_data_published_at(soup: BeautifulSoup) -> datetime | None:
    for script in soup.select("script[type='application/ld+json']"):
        raw_payload = script.string or script.get_text(" ", strip=True)
        if not raw_payload:
            continue
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            continue
        for candidate in _iter_structured_data_dates(payload):
            published_at = _parse_datetime(candidate)
            if published_at is not None:
                return published_at
    return None


def _iter_structured_data_dates(payload: Any) -> list[str]:
    values: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in _STRUCTURED_DATA_DATE_KEYS and isinstance(value, str):
                values.append(value)
            else:
                values.extend(_iter_structured_data_dates(value))
    elif isinstance(payload, list):
        for item in payload:
            values.extend(_iter_structured_data_dates(item))
    return values


def _extract_detail_title(soup: BeautifulSoup, detail_page: dict) -> str | None:
    title_selector = detail_page.get("title_selector")
    if isinstance(title_selector, str) and title_selector.strip():
        title_node = soup.select_one(title_selector)
        if title_node:
            title_attr = detail_page.get("title_attr")
            if title_attr:
                title_value = title_node.get(title_attr)
                if isinstance(title_value, str) and title_value.strip():
                    return title_value.strip()
            title_text = title_node.get_text(" ", strip=True)
            if title_text:
                return title_text

    h1 = soup.select_one("h1")
    if h1:
        title_text = h1.get_text(" ", strip=True)
        if title_text:
            return title_text

    if soup.title:
        title_text = soup.title.get_text(" ", strip=True)
        if title_text:
            return title_text
    return None


def _should_skip_raw_url(raw_url: str) -> bool:
    value = raw_url.strip()
    if not value:
        return True
    lowered = value.lower()
    return lowered.startswith(("#", "javascript:", "mailto:", "tel:"))


def _should_skip_normalized_url(normalized_url: str, *, base_url: str) -> bool:
    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"}:
        return True
    base_parsed = urlparse(base_url)
    same_document = (
        parsed.scheme == base_parsed.scheme
        and parsed.netloc == base_parsed.netloc
        and parsed.path == base_parsed.path
        and parsed.fragment
        and not parsed.query
    )
    return same_document


def _title_quality(title: str | None, url: str) -> tuple[int, int]:
    normalized = (title or "").strip()
    if not normalized:
        return (0, 0)
    if normalized == url:
        return (1, len(normalized))
    if _looks_like_placeholder_title(normalized):
        return (2, len(normalized))
    return (3, len(normalized))


def _looks_like_placeholder_title(title: str) -> bool:
    normalized = re.sub(r"\s+", " ", title.strip()).lower()
    return normalized in {
        "read more",
        "learn more",
        "skip to content",
        "skip to main content",
        "skip to main menu",
        "skip to footer",
        "company",
        "products",
        "groq",
        "简体中文",
        "×",
        "了解更多",
    }


def _is_better_entry(*, candidate: dict[str, Any], existing: dict[str, Any]) -> bool:
    candidate_quality = _title_quality(str(candidate.get("title") or ""), str(candidate.get("url") or ""))
    existing_quality = _title_quality(str(existing.get("title") or ""), str(existing.get("url") or ""))
    if candidate_quality != existing_quality:
        return candidate_quality > existing_quality
    return bool(candidate.get("published_at")) and not existing.get("published_at")


def _resolve_article_title(list_title: str | None, detail_title: str | None, url: str) -> str:
    if detail_title and _title_quality(detail_title, url) > _title_quality(list_title, url):
        return detail_title
    return (list_title or detail_title or url).strip() or url
