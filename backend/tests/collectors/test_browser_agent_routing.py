from __future__ import annotations

import pytest

from app.collectors.base import BaseCollector, RawArticle
from app.collectors.codex_playwright import CodexPlaywrightCollector
from app.collectors.deepbrowse import DeepBrowseCollector


class _StubAgentCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "stub-agent"

    @property
    def category(self) -> str:
        return "blog"

    async def collect(self, config: dict) -> list[RawArticle]:
        return [
            RawArticle(
                external_id="agent-routed",
                title="Agent Routed",
                url="https://example.com/agent",
                content="from browser agent",
            )
        ]


@pytest.mark.asyncio
async def test_collect_uses_browser_agent_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.collectors.deepbrowse.get_collector", lambda _: _StubAgentCollector())

    collector = DeepBrowseCollector()
    output = await collector.collect({"browser_agent": "codex_playwright"})

    assert output
    assert output[0].external_id == "agent-routed"


@pytest.mark.asyncio
async def test_deepbrowse_defaults_to_codex_playwright_when_no_agent_specified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []

    def _fake_get_collector(name: str):
        called.append(name)
        return _StubAgentCollector()

    monkeypatch.setattr("app.collectors.deepbrowse.get_collector", _fake_get_collector)

    collector = DeepBrowseCollector()
    output = await collector.collect({})

    assert output
    assert called[0] == "codex_playwright"


@pytest.mark.asyncio
async def test_codex_playwright_prefers_playwright_path(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_collect_with_playwright(config: dict) -> list[RawArticle]:
        return [
            RawArticle(
                external_id="pw-1",
                title="Playwright hit",
                url="https://example.com/playwright",
                content="from playwright",
            )
        ]

    async def _fail_blog_scraper_collect(self, config: dict) -> list[RawArticle]:
        raise AssertionError("blog scraper should not be called when playwright succeeds")

    monkeypatch.setattr("app.collectors.codex_playwright._collect_with_playwright", _fake_collect_with_playwright)
    monkeypatch.setattr(
        "app.collectors.codex_playwright.BlogScraperCollector.collect",
        _fail_blog_scraper_collect,
    )

    output = await CodexPlaywrightCollector().collect({"site_key": "anthropic"})

    assert output
    assert output[0].external_id == "pw-1"
