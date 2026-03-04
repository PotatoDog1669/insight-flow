"""Codex + Playwright collector adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.collectors.base import BaseCollector, RawArticle
from app.collectors.blog_scraper import (
    BlogScraperCollector,
    _normalize_url,
    _parse_datetime,
    _resolve_profile,
)
from app.collectors.registry import register
from app.collectors.site_profile_loader import validate_site_profile


@register("codex_playwright")
class CodexPlaywrightCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "codex_playwright"

    @property
    def category(self) -> str:
        return "blog"

    async def collect(self, config: dict) -> list[RawArticle]:
        try:
            browser_articles = await _collect_with_playwright(config)
            if browser_articles:
                return browser_articles
        except Exception:
            # Browser path unavailable/failed -> deterministic fallback.
            pass
        return await BlogScraperCollector().collect(config)


async def _collect_with_playwright(config: dict) -> list[RawArticle]:
    try:
        from playwright.async_api import async_playwright
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("playwright is not installed") from exc

    profile = _resolve_profile(config)
    validate_site_profile(profile)

    timeout_seconds = float(config.get("timeout_seconds", 20))
    navigation_timeout_ms = int(timeout_seconds * 1000)
    page_wait_ms = int(config.get("page_wait_ms", 1200))
    max_items = int(config.get("max_items", 20))
    user_agent = str(config.get("user_agent", "LexDeepResearchBot/0.1"))
    headless = bool(config.get("headless", True))

    start_urls = profile.get("start_urls", [])
    list_page = profile.get("list_page", {})
    detail_page = profile.get("detail_page", {})
    normalization = profile.get("normalization", {})
    min_content_chars = int(normalization.get("min_content_chars", 200))
    url_prefix = normalization.get("url_prefix")

    entries: list[dict[str, Any]] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        context = await browser.new_context(user_agent=user_agent)
        page = await context.new_page()
        try:
            for start_url in start_urls:
                try:
                    await page.goto(start_url, wait_until="domcontentloaded", timeout=navigation_timeout_ms)
                    if page_wait_ms > 0:
                        await page.wait_for_timeout(page_wait_ms)
                except Exception:
                    continue

                extracted_rows = await page.evaluate(
                    """
                    ({ itemSelector, urlSelector, urlAttr, titleSelector, publishedSelector, publishedAttr }) => {
                      const rows = [];
                      const attr = urlAttr || "href";
                      const items = document.querySelectorAll(itemSelector || "a[href]");
                      for (const item of items) {
                        const urlNode = urlSelector ? item.querySelector(urlSelector) : item;
                        const rawUrl = urlNode ? urlNode.getAttribute(attr) : null;
                        if (!rawUrl) continue;
                        const titleNode = titleSelector ? item.querySelector(titleSelector) : item;
                        const title = (titleNode ? titleNode.textContent : "") || rawUrl;
                        let publishedAt = null;
                        if (publishedSelector) {
                          const publishedNode = item.querySelector(publishedSelector);
                          if (publishedNode) {
                            publishedAt = publishedAttr
                              ? publishedNode.getAttribute(publishedAttr)
                              : publishedNode.textContent;
                          }
                        }
                        rows.push({
                          url: rawUrl,
                          title: (title || rawUrl).trim(),
                          published_at: publishedAt ? publishedAt.trim() : null,
                        });
                      }
                      return rows;
                    }
                    """,
                    {
                        "itemSelector": list_page.get("item_selector", "a[href]"),
                        "urlSelector": list_page.get("url_selector"),
                        "urlAttr": list_page.get("url_attr", "href"),
                        "titleSelector": list_page.get("title_selector"),
                        "publishedSelector": list_page.get("published_selector"),
                        "publishedAttr": list_page.get("published_attr"),
                    },
                )
                for row in extracted_rows or []:
                    if not isinstance(row, dict):
                        continue
                    raw_url = str(row.get("url") or "").strip()
                    if not raw_url:
                        continue
                    normalized_url = _normalize_url(raw_url, base_url=start_url, url_prefix=url_prefix)
                    entries.append(
                        {
                            "url": normalized_url,
                            "title": str(row.get("title") or normalized_url),
                            "published_at": _parse_datetime(str(row.get("published_at") or "")),
                        }
                    )

            dedup: dict[str, dict[str, Any]] = {}
            for entry in entries:
                dedup[entry["url"]] = entry
            selected_entries = list(dedup.values())[:max_items]

            results: list[RawArticle] = []
            for entry in selected_entries:
                url = entry["url"]
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=navigation_timeout_ms)
                    if page_wait_ms > 0:
                        await page.wait_for_timeout(page_wait_ms)
                except Exception:
                    continue

                detail = await page.evaluate(
                    """
                    ({ contentSelector, publishedSelector, publishedAttr, removeSelectors }) => {
                      for (const selector of removeSelectors || []) {
                        for (const node of document.querySelectorAll(selector)) {
                          node.remove();
                        }
                      }
                      const container =
                        document.querySelector(contentSelector || "article") ||
                        document.querySelector("main") ||
                        document.body;
                      const content = container ? (container.innerText || "") : "";

                      let publishedAt = null;
                      if (publishedSelector) {
                        const publishedNode = document.querySelector(publishedSelector);
                        if (publishedNode) {
                          publishedAt = publishedAttr
                            ? publishedNode.getAttribute(publishedAttr)
                            : publishedNode.textContent;
                        }
                      }
                      return { content: (content || "").trim(), published_at: publishedAt ? publishedAt.trim() : null };
                    }
                    """,
                    {
                        "contentSelector": detail_page.get("content_selector", "article"),
                        "publishedSelector": detail_page.get("published_selector"),
                        "publishedAttr": detail_page.get("published_attr"),
                        "removeSelectors": detail_page.get("remove_selectors", []),
                    },
                )
                detail_payload = detail if isinstance(detail, dict) else {}
                content = str(detail_payload.get("content") or "").strip()
                if len(content) < min_content_chars:
                    continue
                published_at = _parse_datetime(str(detail_payload.get("published_at") or "")) or entry.get("published_at")
                results.append(
                    RawArticle(
                        external_id=url,
                        title=entry.get("title") or url,
                        url=url,
                        content=content,
                        published_at=published_at,
                        metadata={
                            "collector": "codex_playwright",
                            "site_key": profile.get("site_key"),
                            "profile_version": profile.get("profile_version", "v1"),
                            "content_selector": detail_page.get("content_selector"),
                            "content_length": len(content),
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                )
            return results
        finally:
            await context.close()
            await browser.close()
