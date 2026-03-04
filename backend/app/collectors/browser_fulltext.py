"""Playwright 浏览器全文提取 — 用于绕过 Cloudflare 等 JS 反爬。"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_REMOVE_SELECTORS = ["script", "style", "nav", "footer", "header", ".share", ".social", "iframe"]
_CONTENT_SELECTORS = ["article", "main", "[role='main']", ".post-content", ".entry-content", ".content"]


async def fetch_fulltext_via_browser(
    url: str,
    *,
    timeout_ms: int = 20_000,
    wait_ms: int = 2000,
    min_content_chars: int = 200,
    headless: bool = True,
) -> str | None:
    """用 Playwright 打开页面并提取正文，返回纯文本或 None。

    适用场景：httpx 因 Cloudflare/JS 渲染无法获取内容时作为回退。
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.debug("playwright not installed, skipping browser fallback")
        return None

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=headless)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            )
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                if wait_ms > 0:
                    await page.wait_for_timeout(wait_ms)

                content = await page.evaluate(
                    """
                    ({ removeSelectors, contentSelectors, minChars }) => {
                      // Remove noise elements
                      for (const sel of removeSelectors) {
                        for (const node of document.querySelectorAll(sel)) {
                          node.remove();
                        }
                      }
                      // Try content selectors in order, pick the longest one above minChars
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
                      // Fallback to body
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
                    logger.info("Browser fulltext OK: %s (%d chars)", url, len(content))
                    return content
                return None
            finally:
                await context.close()
                await browser.close()
    except Exception as exc:
        logger.warning("Browser fulltext failed for %s: %s", url, exc)
        return None


def is_cloudflare_blocked(status_code: int, html: str) -> bool:
    """检测是否被 Cloudflare JS Challenge 拦截。"""
    if status_code == 403:
        indicators = ["cf_chl_opt", "challenge-platform", "cf-browser-verification", "_cf_chl_tk"]
        return any(ind in html for ind in indicators)
    return False
