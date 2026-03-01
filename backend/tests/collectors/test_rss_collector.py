from __future__ import annotations

import httpx
import pytest

from app.collectors.rss import RSSCollector


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
async def test_rss_fetches_full_article_content_not_feed_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_url = "https://example.com/feed.xml"
    article_url = "https://example.com/posts/1"
    feed_xml = f"""
    <rss version=\"2.0\">
      <channel>
        <title>Example Feed</title>
        <item>
          <guid>p1</guid>
          <title>Example Post</title>
          <link>{article_url}</link>
          <pubDate>Sun, 01 Mar 2026 10:00:00 GMT</pubDate>
          <description>short summary only</description>
        </item>
      </channel>
    </rss>
    """
    full_text = " ".join(["fulltext"] * 120)

    routes = {
        feed_url: DummyResponse(200, text=feed_xml),
        article_url: DummyResponse(200, text=f"<html><body><article><h1>Example</h1><p>{full_text}</p></article></body></html>"),
    }

    async def fake_get(self, url, *args, **kwargs):
        return routes[str(url)]

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = RSSCollector()
    articles = await collector.collect({"feed_url": feed_url, "max_items": 5})

    assert len(articles) == 1
    assert articles[0].title == "Example Post"
    assert articles[0].url == article_url
    assert articles[0].content is not None
    assert "short summary only" not in articles[0].content
    assert "fulltext" in articles[0].content


@pytest.mark.asyncio
async def test_rss_extractor_fallback_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_url = "https://example.com/fallback.xml"
    article_url = "https://example.com/posts/2"
    feed_xml = f"""
    <rss version=\"2.0\">
      <channel>
        <item>
          <guid>p2</guid>
          <title>Fallback Post</title>
          <link>{article_url}</link>
          <description>summary text</description>
        </item>
      </channel>
    </rss>
    """

    routes = {
        feed_url: DummyResponse(200, text=feed_xml),
        article_url: DummyResponse(200, text="<html><body><main><p>Readable body from bs4 fallback.</p></main></body></html>"),
    }

    async def fake_get(self, url, *args, **kwargs):
        return routes[str(url)]

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = RSSCollector()
    articles = await collector.collect(
        {
            "feed_url": feed_url,
            "extractor_chain": ["readability", "bs4"],
            "min_content_chars": 10,
        }
    )

    assert len(articles) == 1
    assert "Readable body" in (articles[0].content or "")
    assert articles[0].metadata.get("extractor") == "bs4"
