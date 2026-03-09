from __future__ import annotations

import pytest
import httpx

from app.renderers.base import Report
from app.sinks.notion import NotionSink, _render_notion_content


@pytest.mark.asyncio
async def test_notion_sink_creates_page_for_short_report(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict):
            calls.append(("POST", url))
            return httpx.Response(200, json={"id": "page_1", "url": "https://notion.so/page_1"})

        async def patch(self, url: str, json: dict):
            calls.append(("PATCH", url))
            return httpx.Response(200, json={"results": []})

    monkeypatch.setattr("app.sinks.notion.httpx.AsyncClient", lambda *args, **kwargs: StubClient())
    sink = NotionSink()
    result = await sink.publish(
        Report(level="L2", title="Daily Brief", content="line1\nline2", article_ids=[]),
        {"database_id": "db123", "api_key": "secret_test"},
    )

    assert ("POST", "https://api.notion.com/v1/pages") in calls
    assert result.success is True
    assert result.url == "https://notion.so/page_1"


@pytest.mark.asyncio
async def test_notion_sink_accepts_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads: list[dict] = []

    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict):
            payloads.append(json)
            return httpx.Response(200, json={"id": "page_3", "url": "https://notion.so/page_3"})

        async def patch(self, url: str, json: dict):
            return httpx.Response(200, json={"results": []})

    monkeypatch.setattr("app.sinks.notion.httpx.AsyncClient", lambda *args, **kwargs: StubClient())
    sink = NotionSink()
    result = await sink.publish(
        Report(level="L2", title="Daily Brief", content="line1\nline2", article_ids=[]),
        {
            "database_id": "https://www.notion.so/3170dd9284fc805ca19bfd4a76db602e?v=3170dd9284fc80f6a693000c0b36598f&source=copy_link",
            "api_key": "secret_test",
        },
    )

    assert result.success is True
    assert payloads
    assert payloads[0]["parent"] == {"database_id": "3170dd9284fc805ca19bfd4a76db602e"}


@pytest.mark.asyncio
async def test_notion_sink_writes_summary_property(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads: list[dict] = []

    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict):
            payloads.append(json)
            return httpx.Response(200, json={"id": "page_4", "url": "https://notion.so/page_4"})

        async def patch(self, url: str, json: dict):
            return httpx.Response(200, json={"results": []})

    monkeypatch.setattr("app.sinks.notion.httpx.AsyncClient", lambda *args, **kwargs: StubClient())
    sink = NotionSink()
    result = await sink.publish(
        Report(level="L2", title="Daily Brief", content="line1\nline2", article_ids=[]),
        {
            "database_id": "db123",
            "api_key": "secret_test",
            "title_property": "名称",
            "summary_property": "TL;DR",
            "summary_text": "这是全篇总结与锐评。",
        },
    )

    assert result.success is True
    assert payloads
    assert payloads[0]["properties"]["TL;DR"]["rich_text"][0]["text"]["content"] == "这是全篇总结与锐评。"


@pytest.mark.asyncio
async def test_notion_sink_fails_when_missing_database_id() -> None:
    from app.config import settings

    settings.notion_database_id = ""
    settings.notion_parent_page_id = ""
    sink = NotionSink()
    result = await sink.publish(
        Report(level="L2", title="Daily Brief", content="line1", article_ids=[]),
        {"api_key": "secret_test"},
    )
    assert result.success is False
    assert "database_id or parent_page_id" in (result.error or "")


@pytest.mark.asyncio
async def test_notion_sink_creates_page_under_parent_page(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    settings.notion_database_id = ""
    settings.notion_parent_page_id = ""
    payloads: list[dict] = []

    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict):
            payloads.append(json)
            return httpx.Response(200, json={"id": "page_2", "url": "https://notion.so/page_2"})

        async def patch(self, url: str, json: dict):
            return httpx.Response(200, json={"results": []})

    monkeypatch.setattr("app.sinks.notion.httpx.AsyncClient", lambda *args, **kwargs: StubClient())
    sink = NotionSink()
    result = await sink.publish(
        Report(level="L2", title="Daily Brief", content="line1\nline2", article_ids=[]),
        {"parent_page_id": "page_parent_123", "api_key": "secret_test"},
    )

    assert result.success is True
    assert payloads
    assert payloads[0]["parent"] == {"page_id": "page_parent_123"}
    assert "title" in payloads[0]["properties"]


@pytest.mark.asyncio
async def test_notion_sink_chunks_for_long_report(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict):
            calls.append(("POST", url))
            return httpx.Response(200, json={"id": "page_long", "url": "https://notion.so/page_long"})

        async def patch(self, url: str, json: dict):
            calls.append(("PATCH", url))
            return httpx.Response(200, json={"results": []})

    monkeypatch.setattr("app.sinks.notion.httpx.AsyncClient", lambda *args, **kwargs: StubClient())
    sink = NotionSink()
    long_content = "\n".join([f"line-{i}" for i in range(0, 140)])
    result = await sink.publish(
        Report(level="L4", title="Deep Report", content=long_content, article_ids=[]),
        {"database_id": "db123", "api_key": "secret_test"},
    )

    assert ("POST", "https://api.notion.com/v1/pages") in calls
    patch_calls = [call for call in calls if call[0] == "PATCH"]
    assert len(patch_calls) == 2
    assert result.success is True


@pytest.mark.asyncio
async def test_notion_sink_retries_on_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """429 on first attempt → retry → succeed on second."""
    attempt_count = 0
    sleeps: list[float] = []

    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                return httpx.Response(429, headers={"Retry-After": "0.1"})
            return httpx.Response(200, json={"id": "page_retry", "url": "https://notion.so/page_retry"})

    monkeypatch.setattr("app.sinks.notion.httpx.AsyncClient", lambda *a, **kw: StubClient())

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("app.sinks.notion.asyncio.sleep", fake_sleep)

    sink = NotionSink()
    result = await sink.publish(
        Report(level="L2", title="Retry Test", content="hello", article_ids=[]),
        {"database_id": "db123", "api_key": "secret_test"},
    )
    assert result.success is True
    assert result.url == "https://notion.so/page_retry"
    assert attempt_count == 2
    assert len(sleeps) >= 1  # at least one retry sleep


@pytest.mark.asyncio
async def test_notion_sink_fails_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """All attempts return 429 → publish fails."""
    sleeps: list[float] = []

    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict):
            return httpx.Response(429, headers={"Retry-After": "0.1"})

    monkeypatch.setattr("app.sinks.notion.httpx.AsyncClient", lambda *a, **kw: StubClient())

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("app.sinks.notion.asyncio.sleep", fake_sleep)

    sink = NotionSink()
    result = await sink.publish(
        Report(level="L2", title="Fail Test", content="hello", article_ids=[]),
        {"database_id": "db123", "api_key": "secret_test"},
    )
    assert result.success is False
    assert "429" in (result.error or "")


def test_render_notion_content_falls_back_to_base_content_on_template_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args, **kwargs):
        raise RuntimeError("template failed")

    monkeypatch.setattr("app.sinks.notion.render_sink_report_template", _raise)
    report = Report(level="L2", title="Fallback Test", content="base content", article_ids=[])
    rendered = _render_notion_content(report=report, report_type="daily", version="v1", report_date="2026-03-02")
    assert rendered == "base content"


def test_render_notion_content_removes_redundant_title_and_summary_when_property_present() -> None:
    report = Report(
        level="L2",
        title="AI Daily Report — 2026-03-05",
        content=(
            "# AI Daily Report — 2026-03-05\n\n"
            "## 执行摘要\n\n"
            "这里是正文内摘要。\n\n"
            "## 概览\n\n"
            "- 事件一 [#1](#event-1)\n"
        ),
        article_ids=[],
    )
    rendered = _render_notion_content(
        report=report,
        report_type="daily",
        version="v1",
        report_date="2026-03-05",
        summary_text="这里是属性 TL;DR。",
    )

    assert "# AI Daily Report — 2026-03-05" not in rendered
    assert "## 执行摘要" not in rendered
    assert "## 概览" in rendered
    assert "[#1](#event-1)" not in rendered


def test_render_notion_content_strips_internal_event_anchor_and_relabels_arrow_link() -> None:
    report = Report(
        level="L2",
        title="AI Daily Report — 2026-03-05",
        content="## 概览\n\n- 事件一 [↗](https://example.com/a) [#1](#event-1)\n",
        article_ids=[],
    )
    rendered = _render_notion_content(
        report=report,
        report_type="daily",
        version="v1",
        report_date="2026-03-05",
        summary_text="",
    )

    assert "[#1](#event-1)" not in rendered
    assert "[↗](https://example.com/a)" not in rendered
    assert "- 事件一 [原文](https://example.com/a)" in rendered


def test_render_notion_content_injects_overview_when_missing_in_daily_report() -> None:
    report = Report(
        level="L2",
        title="AI Daily Report — 2026-03-05",
        content="## 详细事件记录\n\n## OpenAI 发布更新 #1\n\n详情内容",
        article_ids=[],
        metadata={
            "events": [
                {
                    "index": 1,
                    "title": "OpenAI 发布更新",
                    "category": "要闻",
                    "source_links": ["https://openai.com/news"],
                }
            ]
        },
    )
    rendered = _render_notion_content(
        report=report,
        report_type="daily",
        version="v1",
        report_date="2026-03-05",
        summary_text="",
    )

    assert "## 概览" in rendered
    assert "### 要闻" in rendered
    assert "[#1](#event-1)" not in rendered
    assert "OpenAI 发布更新 [原文](https://openai.com/news)" in rendered
