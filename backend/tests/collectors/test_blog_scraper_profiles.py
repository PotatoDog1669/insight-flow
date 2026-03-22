from __future__ import annotations

import httpx
import pytest

from app.collectors.blog_scraper import BlogScraperCollector


class DummyResponse:
    def __init__(self, status_code: int = 200, text: str = "", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://example.com")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    def json(self):
        return self._json_data


@pytest.mark.asyncio
async def test_profile_driven_list_and_detail_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    list_url = "https://example.com/news"
    post1 = "https://example.com/news/post-1"
    post2 = "https://example.com/news/post-2"

    async def fake_get(self, url, *args, **kwargs):
        key = str(url)
        if key == list_url:
            return DummyResponse(
                200,
                text=f"""
                <html><body>
                  <article class=\"entry\"><a class=\"link\" href=\"{post1}\">Title 1</a></article>
                  <article class=\"entry\"><a class=\"link\" href=\"{post2}\">Title 2</a></article>
                </body></html>
                """,
            )
        if key == post1:
            return DummyResponse(200, text="<html><article><p>Post 1 body content.</p></article></html>")
        if key == post2:
            return DummyResponse(200, text="<html><article><p>Post 2 body content.</p></article></html>")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    profile = {
        "site_key": "example_news",
        "start_urls": [list_url],
        "list_page": {"item_selector": "article.entry", "url_selector": "a.link", "url_attr": "href", "title_selector": "a.link"},
        "detail_page": {"content_selector": "article", "remove_selectors": ["script", "style"]},
        "normalization": {"min_content_chars": 5},
    }

    collector = BlogScraperCollector()
    items = await collector.collect({"profile": profile, "max_items": 5})

    assert len(items) == 2
    assert items[0].metadata.get("site_key") == "example_news"
    assert "body content" in (items[0].content or "")


@pytest.mark.asyncio
async def test_two_sites_with_different_profiles(monkeypatch: pytest.MonkeyPatch) -> None:
    list_a = "https://a.example/blog"
    post_a = "https://a.example/blog/1"
    list_b = "https://b.example/news"
    post_b = "https://b.example/news/1"

    async def fake_get(self, url, *args, **kwargs):
        key = str(url)
        if key == list_a:
            return DummyResponse(200, text=f"<div class='item'><a href='{post_a}'>A1</a></div>")
        if key == post_a:
            return DummyResponse(200, text="<main><p>Alpha site content</p></main>")
        if key == list_b:
            return DummyResponse(200, text=f"<article><h2><a href='{post_b}'>B1</a></h2></article>")
        if key == post_b:
            return DummyResponse(200, text="<article><p>Beta site content</p></article>")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    profile_a = {
        "site_key": "site_a",
        "start_urls": [list_a],
        "list_page": {"item_selector": "div.item", "url_selector": "a", "url_attr": "href", "title_selector": "a"},
        "detail_page": {"content_selector": "main"},
        "normalization": {"min_content_chars": 5},
    }
    profile_b = {
        "site_key": "site_b",
        "start_urls": [list_b],
        "list_page": {"item_selector": "article", "url_selector": "h2 a", "url_attr": "href", "title_selector": "h2 a"},
        "detail_page": {"content_selector": "article"},
        "normalization": {"min_content_chars": 5},
    }

    collector = BlogScraperCollector()
    items_a = await collector.collect({"profile": profile_a, "max_items": 5})
    items_b = await collector.collect({"profile": profile_b, "max_items": 5})

    assert len(items_a) == 1
    assert len(items_b) == 1
    assert "Alpha" in (items_a[0].content or "")
    assert "Beta" in (items_b[0].content or "")


@pytest.mark.asyncio
async def test_cursor_profile_extracts_recent_blog_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    list_url = "https://cursor.com/blog"
    post_url = "https://cursor.com/blog/automations"

    async def fake_get(self, url, *args, **kwargs):
        key = str(url)
        if key == list_url:
            return DummyResponse(
                200,
                text=f"""
                <html><body>
                  <article class="flex grow-1 flex-col mb-g1">
                    <a class="card" href="/blog/automations">
                      <div>
                        <p>Build agents that run automatically</p>
                        <time datetime="2026-03-06T12:00:00.000Z">Mar 6, 2026</time>
                      </div>
                    </a>
                  </article>
                </body></html>
                """,
            )
        if key == post_url:
            return DummyResponse(
                200,
                text="""
                <html><body>
                  <main>
                    <article>
                      <h1>Automations</h1>
                      <p>Cursor now supports automations for recurring agent workflows.</p>
                      <p>Users can schedule repeated tasks, define workspace scope, and route long-running maintenance jobs without reopening the app each time.</p>
                      <p>The post also explains output expectations, notification behavior, and how teams can standardize recurring agent routines with shared prompts.</p>
                    </article>
                  </main>
                </body></html>
                """,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = BlogScraperCollector()
    items = await collector.collect({"site_key": "cursor", "max_items": 5})

    assert len(items) == 1
    assert items[0].url == post_url
    assert items[0].title == "Build agents that run automatically"
    assert "automations for recurring agent workflows" in (items[0].content or "")


@pytest.mark.asyncio
async def test_blog_scraper_skips_anchor_links_and_prefers_detail_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_url = "https://example.com/blog"
    post_url = "https://example.com/blog/launch"

    async def fake_get(self, url, *args, **kwargs):
        key = str(url)
        if key == list_url:
            return DummyResponse(
                200,
                text=f"""
                <html><body>
                  <a href="#content">Skip to content</a>
                  <a href="{post_url}">Read More</a>
                </body></html>
                """,
            )
        if key == post_url:
            return DummyResponse(
                200,
                text="""
                <html><body>
                  <main>
                    <h1>Launch Notes</h1>
                    <article>
                      <p>Detailed launch notes for the collector test.</p>
                      <p>This should be the only collected article.</p>
                    </article>
                  </main>
                </body></html>
                """,
            )
        if key == f"{list_url}#content":
            return DummyResponse(200, text="<html><body><main><p>Navigation shell</p></main></body></html>")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = BlogScraperCollector()
    items = await collector.collect(
        {
            "profile": {
                "site_key": "anchor_filter",
                "start_urls": [list_url],
                "list_page": {"item_selector": "a[href]", "url_attr": "href"},
                "detail_page": {"content_selector": "article"},
                "normalization": {"min_content_chars": 20},
            },
            "max_items": 5,
        }
    )

    assert len(items) == 1
    assert items[0].url == post_url
    assert items[0].title == "Launch Notes"


@pytest.mark.asyncio
async def test_blog_scraper_prefers_meaningful_duplicate_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_url = "https://example.com/news"
    post_url = "https://example.com/news/post-1"

    async def fake_get(self, url, *args, **kwargs):
        key = str(url)
        if key == list_url:
            return DummyResponse(
                200,
                text=f"""
                <html><body>
                  <a href="{post_url}">Real article title</a>
                  <a href="{post_url}">Read More</a>
                </body></html>
                """,
            )
        if key == post_url:
            return DummyResponse(
                200,
                text="""
                <html><body>
                  <article>
                    <h1>Real article title</h1>
                    <p>This entry should keep the better list title instead of the generic duplicate.</p>
                  </article>
                </body></html>
                """,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = BlogScraperCollector()
    items = await collector.collect(
        {
            "profile": {
                "site_key": "duplicate_title",
                "start_urls": [list_url],
                "list_page": {"item_selector": "a[href]", "url_attr": "href"},
                "detail_page": {"content_selector": "article"},
                "normalization": {"min_content_chars": 20},
            },
            "max_items": 5,
        }
    )

    assert len(items) == 1
    assert items[0].title == "Real article title"
