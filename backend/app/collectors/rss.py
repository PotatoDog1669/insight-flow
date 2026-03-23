"""通用 RSS Collector。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from urllib.parse import urlencode

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
        max_items = int(config.get("max_items", 30))
        feed_url = _resolve_feed_url(config=config, max_items=max_items)
        fetch_detail = bool(config.get("fetch_detail", True))
        timeout_seconds = float(config.get("timeout_seconds", 20))
        retry_max_attempts = int(config.get("retry_max_attempts", 3))
        user_agent = config.get("user_agent", "LexDeepResearchBot/0.1")
        extractor_chain = config.get("extractor_chain", list(DEFAULT_EXTRACTOR_CHAIN))
        min_content_chars = int(config.get("min_content_chars", 200))
        require_browser = bool(config.get("require_browser", False))
        reader_fallback_enabled = bool(config.get("reader_fallback_enabled", True))
        reader_base_url = str(config.get("reader_base_url", "https://r.jina.ai/")).strip()
        reader_timeout_seconds = float(config.get("reader_timeout_seconds", max(timeout_seconds, 45)))
        reader_mode = str(config.get("reader_mode", "fallback")).strip().lower()
        if reader_mode not in {"fallback", "prefer", "off"}:
            reader_mode = "fallback"
        if reader_mode == "off":
            reader_fallback_enabled = False

        headers = {
            "User-Agent": user_agent,
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9,*/*;q=0.8",
        }
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True, headers=headers) as client:
            feed_response = await _get_with_retry(client, feed_url, retry_max_attempts)
            parsed = feedparser.parse(feed_response.text)
            entries = list(parsed.entries)[:max_items]

            # Collect links that need browser-based extraction
            entry_data: list[dict] = []
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
                entry_data.append({
                    "link": link,
                    "title": title,
                    "external_id": external_id,
                    "published_at": published_at,
                    "summary": summary,
                })

            # When require_browser is set, batch-extract all articles with a single browser instance
            browser_results: dict[str, str] = {}
            if require_browser and fetch_detail:
                urls_to_fetch = [e["link"] for e in entry_data if e["link"]]
                browser_results = await _browser_batch_extract(urls_to_fetch, min_content_chars)

            articles: list[RawArticle] = []
            for idx, ed in enumerate(entry_data):
                link = ed["link"]
                content = ed["summary"]
                extractor = ""

                if link and fetch_detail:
                    try:
                        if require_browser:
                            browser_text = browser_results.get(link)
                            if browser_text:
                                content = browser_text
                                extractor = "playwright"
                            else:
                                extracted, used_extractor = await _extract_from_article_link(
                                    client=client,
                                    link=link,
                                    retry_max_attempts=retry_max_attempts,
                                    extractor_chain=extractor_chain,
                                    min_content_chars=min_content_chars,
                                    expected_title=str(ed["title"]),
                                    allow_browser_fallback=False,
                                    reader_fallback_enabled=reader_fallback_enabled,
                                    reader_base_url=reader_base_url,
                                    reader_timeout_seconds=reader_timeout_seconds,
                                    reader_mode=reader_mode,
                                )
                            if extracted:
                                content = extracted
                                extractor = used_extractor
                        else:
                            extracted, used_extractor = await _extract_from_article_link(
                                client=client,
                                link=link,
                                retry_max_attempts=retry_max_attempts,
                                extractor_chain=extractor_chain,
                                min_content_chars=min_content_chars,
                                expected_title=str(ed["title"]),
                                allow_browser_fallback=True,
                                reader_fallback_enabled=reader_fallback_enabled,
                                reader_base_url=reader_base_url,
                                reader_timeout_seconds=reader_timeout_seconds,
                                reader_mode=reader_mode,
                            )
                            if extracted:
                                content = extracted
                                extractor = used_extractor
                    except Exception:
                        pass
                elif content:
                    extractor = "feed_summary"
                articles.append(
                    RawArticle(
                        external_id=str(ed["external_id"]),
                        title=str(ed["title"]),
                        url=str(link) if link else None,
                        content=content or None,
                        published_at=ed["published_at"],
                        metadata={
                            "collector": "rss",
                            "feed_url": feed_url,
                            "extractor": extractor,
                            "detail_fetch_enabled": fetch_detail,
                            "content_length": len(content or ""),
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                )
        return articles


async def _extract_from_article_link(
    *,
    client: httpx.AsyncClient,
    link: str,
    retry_max_attempts: int,
    extractor_chain: list[str] | tuple[str, ...],
    min_content_chars: int,
    expected_title: str,
    allow_browser_fallback: bool,
    reader_fallback_enabled: bool,
    reader_base_url: str,
    reader_timeout_seconds: float,
    reader_mode: str = "fallback",
) -> tuple[str, str]:
    if reader_mode == "prefer":
        preferred_reader_text = await _reader_fallback(
            client=client,
            url=link,
            retry_max_attempts=retry_max_attempts,
            min_content_chars=min_content_chars,
            enabled=reader_fallback_enabled,
            base_url=reader_base_url,
            timeout_seconds=reader_timeout_seconds,
        )
        if preferred_reader_text:
            return preferred_reader_text, "jina_reader"

    article_response = await _get_with_retry(client, link, retry_max_attempts)
    if _is_blocked(article_response):
        if allow_browser_fallback:
            browser_text = await _browser_fallback(link, min_content_chars)
            if browser_text:
                return browser_text, "playwright"
        reader_text = await _reader_fallback(
            client=client,
            url=link,
            retry_max_attempts=retry_max_attempts,
            min_content_chars=min_content_chars,
            enabled=reader_fallback_enabled,
            base_url=reader_base_url,
            timeout_seconds=reader_timeout_seconds,
        )
        if reader_text:
            return reader_text, "jina_reader"
        return "", ""

    extracted, used_extractor = extract_fulltext(
        article_response.text,
        extractor_chain=extractor_chain,
        min_content_chars=min_content_chars,
    )
    if extracted:
        if _content_matches_title(extracted, expected_title):
            return extracted, used_extractor
        reader_text = await _reader_fallback(
            client=client,
            url=link,
            retry_max_attempts=retry_max_attempts,
            min_content_chars=min_content_chars,
            enabled=reader_fallback_enabled,
            base_url=reader_base_url,
            timeout_seconds=reader_timeout_seconds,
        )
        if reader_text:
            return reader_text, "jina_reader"
        return extracted, used_extractor

    reader_text = await _reader_fallback(
        client=client,
        url=link,
        retry_max_attempts=retry_max_attempts,
        min_content_chars=min_content_chars,
        enabled=reader_fallback_enabled,
        base_url=reader_base_url,
        timeout_seconds=reader_timeout_seconds,
    )
    if reader_text:
        return reader_text, "jina_reader"
    return "", ""


def _resolve_feed_url(config: dict, max_items: int) -> str:
    if bool(config.get("arxiv_api")):
        return _build_arxiv_api_url(config=config, max_items=max_items)

    feed_url = config.get("feed_url") or config.get("url") or config.get("rss_url")
    if feed_url:
        return str(feed_url)

    raise ValueError("RSS collector requires feed_url/url/rss_url")


def _build_arxiv_api_url(config: dict, max_items: int) -> str:
    base_url = str(
        config.get("arxiv_api_url")
        or config.get("feed_url")
        or config.get("url")
        or config.get("rss_url")
        or "https://export.arxiv.org/api/query"
    ).strip()
    search_query = _build_arxiv_search_query(config)
    if not search_query:
        raise ValueError("arXiv API query requires search_query or keywords/categories")

    params = {
        "search_query": search_query,
        "start": int(config.get("start", 0)),
        "max_results": int(config.get("max_results", max_items)),
        "sortBy": str(config.get("sort_by", "submittedDate")),
        "sortOrder": str(config.get("sort_order", "descending")),
    }
    encoded = urlencode(params)
    if "?" in base_url:
        sep = "&" if not base_url.endswith("?") and not base_url.endswith("&") else ""
        return f"{base_url}{sep}{encoded}"
    return f"{base_url}?{encoded}"


def _build_arxiv_search_query(config: dict) -> str:
    search_query = str(config.get("search_query") or "").strip()
    submitted_date_expr = _build_arxiv_submitted_date_expr(
        config.get("submitted_date_from"),
        config.get("submitted_date_to"),
    )
    if search_query:
        if submitted_date_expr and "submittedDate:[" not in search_query:
            return f"{search_query} AND {submitted_date_expr}"
        return search_query

    keyword_expr = _join_terms(
        [_build_arxiv_keyword_term(keyword) for keyword in _normalize_str_list(config.get("keywords"))],
        operator=str(config.get("keyword_operator") or "OR"),
    )
    category_expr = _join_terms(
        [f"cat:{cat}" for cat in _normalize_str_list(config.get("categories"))],
        operator=str(config.get("category_operator") or "OR"),
    )
    parts = [expr for expr in [keyword_expr, category_expr, submitted_date_expr] if expr]
    return " AND ".join(parts)


def _build_arxiv_keyword_term(keyword: str) -> str:
    normalized = " ".join(keyword.replace('"', " ").split())
    if not normalized:
        return ""
    if " " in normalized:
        return f'all:"{normalized}"'
    return f"all:{normalized}"


def _build_arxiv_submitted_date_expr(start: object, end: object) -> str:
    start_value = _format_arxiv_datetime_value(start)
    end_value = _format_arxiv_datetime_value(end)
    if not start_value or not end_value:
        return ""
    return f"submittedDate:[{start_value} TO {end_value}]"


def _format_arxiv_datetime_value(value: object) -> str:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc).strftime("%Y%m%d%H%M")
    if not isinstance(value, str):
        return ""
    raw = value.strip()
    if len(raw) == 12 and raw.isdigit():
        return raw
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return ""
    normalized = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).strftime("%Y%m%d%H%M")


def _normalize_str_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    normalized: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if value:
            normalized.append(value)
    return normalized


def _join_terms(terms: list[str], operator: str) -> str:
    if not terms:
        return ""
    if len(terms) == 1:
        return terms[0]
    op = "AND" if operator.strip().upper() == "AND" else "OR"
    return f"({' {} '.format(op).join(terms)})"


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


async def _get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    max_attempts: int,
    *,
    timeout_seconds: float | None = None,
    backoff_base_seconds: float = 0.0,
) -> httpx.Response:
    last_exc: Exception | None = None
    attempts = max(1, int(max_attempts))
    for attempt in range(attempts):
        try:
            kwargs = {"timeout": timeout_seconds} if timeout_seconds is not None else {}
            response = await client.get(url, **kwargs)
            # Handle 429 Too Many Requests
            if response.status_code == 429 and attempt < attempts - 1:
                # ArXiv specifically requires 5+ seconds backoff
                wait_time = 5.0 + (attempt * 2.0)
                await asyncio.sleep(wait_time)
                continue

            # Return 403 without raising so caller can check for Cloudflare
            if response.status_code == 403:
                return response
            response.raise_for_status()
            return response
        except Exception as exc:
            last_exc = exc
            if backoff_base_seconds > 0 and attempt < attempts - 1:
                await asyncio.sleep(backoff_base_seconds * (attempt + 1))
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Failed to fetch url: {url}")


def _is_blocked(response: httpx.Response) -> bool:
    """Detect Cloudflare JS challenge or other bot protection."""
    if response.status_code == 403:
        indicators = ["cf_chl_opt", "challenge-platform", "cf-browser-verification", "_cf_chl_tk"]
        return any(ind in response.text for ind in indicators)
    return False


async def _browser_fallback(url: str, min_content_chars: int) -> str | None:
    """Try Playwright browser fallback for blocked pages."""
    try:
        from app.collectors.browser_fulltext import fetch_fulltext_via_browser
        return await fetch_fulltext_via_browser(url, min_content_chars=min_content_chars)
    except Exception:
        return None


async def _reader_fallback(
    *,
    client: httpx.AsyncClient,
    url: str,
    retry_max_attempts: int,
    min_content_chars: int,
    enabled: bool,
    base_url: str,
    timeout_seconds: float,
) -> str | None:
    if not enabled:
        return None

    reader_url = _build_reader_url(base_url=base_url, source_url=url)
    if not reader_url:
        return None
    try:
        response = await _get_with_retry(
            client,
            reader_url,
            retry_max_attempts,
            timeout_seconds=timeout_seconds,
            backoff_base_seconds=0.6,
        )
    except Exception:
        return None
    content = response.text.strip()
    if len(content) < min_content_chars:
        return None
    return content


def _build_reader_url(*, base_url: str, source_url: str) -> str:
    normalized_base = str(base_url or "").strip()
    normalized_source = str(source_url or "").strip()
    if not normalized_base or not normalized_source:
        return ""
    if "{url}" in normalized_base:
        return normalized_base.replace("{url}", normalized_source)
    if not normalized_base.endswith("/"):
        normalized_base = normalized_base + "/"
    return normalized_base + normalized_source


def _content_matches_title(content: str, expected_title: str) -> bool:
    body = _normalize_text_for_match(content)
    title = _normalize_text_for_match(expected_title)
    if not body or not title:
        return True

    title_tokens = [token for token in title.split() if token]
    strong_tokens = [token for token in title_tokens if len(token) >= 4]
    cjk_tokens = [token for token in title_tokens if any("\u4e00" <= ch <= "\u9fff" for ch in token)]
    candidates = strong_tokens[:6] or cjk_tokens[:6] or title_tokens[:4]
    if not candidates:
        return True
    return any(token in body for token in candidates)


def _normalize_text_for_match(value: str) -> str:
    lowered = str(value or "").lower()
    filtered = "".join(ch if (ch.isalnum() or ("\u4e00" <= ch <= "\u9fff")) else " " for ch in lowered)
    return " ".join(filtered.split())


async def _browser_batch_extract(urls: list[str], min_content_chars: int) -> dict[str, str]:
    """Extract fulltext from multiple URLs using a single shared Playwright browser instance.

    Returns a dict mapping URL -> extracted text (only for successful extractions).
    """
    if not urls:
        return {}

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {}

    from app.collectors.browser_fulltext import _REMOVE_SELECTORS, _CONTENT_SELECTORS

    results: dict[str, str] = {}
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            )
            page = await context.new_page()
            try:
                for url in urls:
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                        await page.wait_for_timeout(1500)
                        content = await page.evaluate(
                            """
                            ({ removeSelectors, contentSelectors, minChars }) => {
                              for (const sel of removeSelectors) {
                                for (const node of document.querySelectorAll(sel)) {
                                  node.remove();
                                }
                              }
                              let best = "";
                              for (const sel of contentSelectors) {
                                const el = document.querySelector(sel);
                                if (el) {
                                  const text = (el.innerText || "").trim();
                                  if (text.length >= minChars && text.length > best.length) {
                                    best = text;
                                  }
                                }
                              }
                              if (!best || best.length < minChars) {
                                const body = document.body;
                                if (body) {
                                  best = (body.innerText || "").trim();
                                }
                              }
                              return best;
                            }
                            """,
                            {
                                "removeSelectors": _REMOVE_SELECTORS,
                                "contentSelectors": _CONTENT_SELECTORS,
                                "minChars": min_content_chars,
                            },
                        )
                        if content and len(content) >= min_content_chars:
                            results[url] = content
                    except Exception:
                        continue
            finally:
                await context.close()
                await browser.close()
    except Exception:
        pass

    return results
