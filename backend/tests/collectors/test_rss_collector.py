from __future__ import annotations

import httpx
import pytest
from urllib.parse import parse_qs, urlparse

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
async def test_rss_can_skip_detail_fetch_and_keep_feed_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_url = "https://example.com/reddit.rss"
    article_url = "https://www.reddit.com/r/LocalLLaMA/comments/example"
    feed_xml = f"""
    <rss version=\"2.0\">
      <channel>
        <title>Reddit Feed</title>
        <item>
          <guid>reddit-1</guid>
          <title>Reddit Post</title>
          <link>{article_url}</link>
          <description>feed summary only</description>
        </item>
      </channel>
    </rss>
    """
    called_urls: list[str] = []

    async def fake_get(self, url, *args, **kwargs):
        called_urls.append(str(url))
        if str(url) != feed_url:
            raise AssertionError(f"unexpected url: {url}")
        return DummyResponse(200, text=feed_xml)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = RSSCollector()
    articles = await collector.collect({"feed_url": feed_url, "max_items": 5, "fetch_detail": False})

    assert called_urls == [feed_url]
    assert len(articles) == 1
    assert articles[0].content == "feed summary only"
    assert articles[0].metadata.get("extractor") == "feed_summary"


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


@pytest.mark.asyncio
async def test_rss_supports_arxiv_api_keyword_query(monkeypatch: pytest.MonkeyPatch) -> None:
    article_url = "https://arxiv.org/abs/2603.00001"
    feed_xml = f"""
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2603.00001v1</id>
        <title>Reasoning with Agents</title>
        <link href="{article_url}" rel="alternate" type="text/html" />
        <summary>abstract summary</summary>
      </entry>
    </feed>
    """
    called_urls: list[str] = []

    async def fake_get(self, url, *args, **kwargs):
        raw = str(url)
        called_urls.append(raw)
        if raw.startswith("https://export.arxiv.org/api/query?"):
            return DummyResponse(200, text=feed_xml)
        if raw == article_url:
            return DummyResponse(200, text="<html><body><article><p>paper full text</p></article></body></html>")
        raise AssertionError(f"unexpected url: {raw}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = RSSCollector()
    articles = await collector.collect(
        {
            "arxiv_api": True,
            "feed_url": "https://export.arxiv.org/api/query",
            "keywords": ["reasoning", "agent"],
            "categories": ["cs.AI", "cs.LG"],
            "max_results": 25,
            "max_items": 5,
        }
    )

    assert len(articles) == 1
    assert called_urls
    first_url = called_urls[0]
    parsed = urlparse(first_url)
    params = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "export.arxiv.org"
    assert parsed.path == "/api/query"
    assert "search_query" in params
    query = params["search_query"][0]
    assert "all:reasoning" in query
    assert "all:agent" in query
    assert "cat:cs.AI" in query
    assert "cat:cs.LG" in query
    assert params["max_results"][0] == "25"
    assert params["sortBy"][0] == "submittedDate"
    assert params["sortOrder"][0] == "descending"


@pytest.mark.asyncio
async def test_rss_quotes_arxiv_phrase_keywords_and_applies_submitted_date_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    article_url = "https://arxiv.org/abs/2603.00002"
    feed_xml = f"""
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2603.00002v1</id>
        <title>Web Agents for Computer Use</title>
        <link href="{article_url}" rel="alternate" type="text/html" />
        <summary>abstract summary</summary>
      </entry>
    </feed>
    """
    called_urls: list[str] = []

    async def fake_get(self, url, *args, **kwargs):
        raw = str(url)
        called_urls.append(raw)
        if raw.startswith("https://export.arxiv.org/api/query?"):
            return DummyResponse(200, text=feed_xml)
        if raw == article_url:
            return DummyResponse(200, text="<html><body><article><p>paper full text</p></article></body></html>")
        raise AssertionError(f"unexpected url: {raw}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = RSSCollector()
    await collector.collect(
        {
            "arxiv_api": True,
            "feed_url": "https://export.arxiv.org/api/query",
            "keywords": ["webagent", "web agents", "computer use"],
            "categories": ["cs.AI"],
            "submitted_date_from": "202603140000",
            "submitted_date_to": "202603210000",
            "max_items": 5,
        }
    )

    parsed = urlparse(called_urls[0])
    params = parse_qs(parsed.query)
    query = params["search_query"][0]

    assert 'all:webagent' in query
    assert 'all:"web agents"' in query
    assert 'all:"computer use"' in query
    assert "submittedDate:[202603140000 TO 202603210000]" in query
    assert "cat:cs.AI" in query


@pytest.mark.asyncio
async def test_rss_reader_fallback_when_browser_required_and_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_url = "https://example.com/openai-feed.xml"
    article_url = "https://openai.com/index/example-post"
    reader_url = f"https://r.jina.ai/{article_url}"
    feed_xml = f"""
    <rss version=\"2.0\">
      <channel>
        <item>
          <guid>openai-1</guid>
          <title>OpenAI Post</title>
          <link>{article_url}</link>
          <description>feed summary only</description>
        </item>
      </channel>
    </rss>
    """
    challenge_html = "<html><body>cf_chl_opt challenge-platform</body></html>"
    reader_text = " ".join(["full"] * 500)

    routes = {
        feed_url: DummyResponse(200, text=feed_xml),
        article_url: DummyResponse(403, text=challenge_html),
        reader_url: DummyResponse(200, text=reader_text),
    }

    async def fake_get(self, url, *args, **kwargs):
        raw = str(url)
        if raw not in routes:
            raise AssertionError(f"unexpected url: {raw}")
        return routes[raw]

    async def fake_browser_batch_extract(urls: list[str], min_content_chars: int) -> dict[str, str]:
        return {}

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr("app.collectors.rss._browser_batch_extract", fake_browser_batch_extract)

    collector = RSSCollector()
    articles = await collector.collect(
        {
            "feed_url": feed_url,
            "max_items": 5,
            "require_browser": True,
            "reader_fallback_enabled": True,
            "reader_base_url": "https://r.jina.ai/",
        }
    )

    assert len(articles) == 1
    assert articles[0].content is not None
    assert "feed summary only" not in articles[0].content
    assert "full full full" in articles[0].content
    assert articles[0].metadata.get("extractor") == "jina_reader"


@pytest.mark.asyncio
async def test_rss_reader_mode_prefer_uses_reader_content_first(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_url = "https://example.com/qwen-feed.xml"
    article_url = "https://example.com/posts/reader-first"
    reader_url = f"https://r.jina.ai/{article_url}"
    feed_xml = f"""
    <rss version=\"2.0\">
      <channel>
        <item>
          <guid>reader-first-1</guid>
          <title>Reader First Post</title>
          <link>{article_url}</link>
          <description>feed summary only</description>
        </item>
      </channel>
    </rss>
    """
    html_text = "<html><body><article><p>HTML extractor body.</p></article></body></html>"
    reader_text = " ".join(["reader-full-content"] * 50)

    routes = {
        feed_url: DummyResponse(200, text=feed_xml),
        article_url: DummyResponse(200, text=html_text),
        reader_url: DummyResponse(200, text=reader_text),
    }

    async def fake_get(self, url, *args, **kwargs):
        raw = str(url)
        if raw not in routes:
            raise AssertionError(f"unexpected url: {raw}")
        return routes[raw]

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = RSSCollector()
    articles = await collector.collect(
        {
            "feed_url": feed_url,
            "max_items": 5,
            "reader_mode": "prefer",
            "reader_fallback_enabled": True,
            "reader_base_url": "https://r.jina.ai/",
        }
    )

    assert len(articles) == 1
    assert articles[0].content is not None
    assert "reader-full-content" in articles[0].content
    assert articles[0].metadata.get("extractor") == "jina_reader"


@pytest.mark.asyncio
async def test_rss_falls_back_to_reader_when_extracted_content_mismatches_title(monkeypatch: pytest.MonkeyPatch) -> None:
    feed_url = "https://example.com/nvidia-feed.xml"
    article_url = "https://example.com/posts/true-article"
    reader_url = f"https://r.jina.ai/{article_url}"
    feed_xml = f"""
    <rss version=\"2.0\">
      <channel>
        <item>
          <guid>nvidia-1</guid>
          <title>True Article About New Platform</title>
          <link>{article_url}</link>
          <description>summary only</description>
        </item>
      </channel>
    </rss>
    """
    wrong_html = "<html><body><article>Other teaser card ... Read Article</article></body></html>"
    reader_text = "True Article About New Platform " + ("detailed body " * 80)

    routes = {
        feed_url: DummyResponse(200, text=feed_xml),
        article_url: DummyResponse(200, text=wrong_html),
        reader_url: DummyResponse(200, text=reader_text),
    }

    async def fake_get(self, url, *args, **kwargs):
        raw = str(url)
        if raw not in routes:
            raise AssertionError(f"unexpected url: {raw}")
        return routes[raw]

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = RSSCollector()
    articles = await collector.collect(
        {
            "feed_url": feed_url,
            "max_items": 5,
            "reader_mode": "fallback",
            "reader_fallback_enabled": True,
            "reader_base_url": "https://r.jina.ai/",
        }
    )

    assert len(articles) == 1
    assert articles[0].content is not None
    assert "True Article About New Platform" in articles[0].content
    assert articles[0].metadata.get("extractor") == "jina_reader"
