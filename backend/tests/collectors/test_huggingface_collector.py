from __future__ import annotations

import httpx
import pytest

from app.collectors.huggingface import HuggingFaceCollector


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
async def test_collects_daily_papers_with_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(self, url, *args, **kwargs):
        if str(url) == "https://huggingface.co/api/daily_papers":
            return DummyResponse(
                200,
                json_data=[
                    {"id": "2509.02523", "title": "Paper A", "summary": "Summary A"},
                    {"id": "2509.11111", "title": "Paper B", "summary": "Summary B"},
                ],
            )
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = HuggingFaceCollector()
    items = await collector.collect({"limit": 2, "include_paper_detail": False, "include_arxiv_repos": False})

    assert len(items) == 2
    assert items[0].external_id.startswith("2509.02523#")
    assert items[0].metadata["entity_id"] == "2509.02523"
    assert "snapshot_date" in items[0].metadata
    assert "snapshot_at" in items[0].metadata
    assert items[0].url == "https://huggingface.co/papers/2509.02523"


@pytest.mark.asyncio
async def test_enriches_with_paper_detail_or_arxiv_repos(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(self, url, *args, **kwargs):
        key = str(url)
        if key == "https://huggingface.co/api/daily_papers":
            return DummyResponse(200, json_data=[{"id": "2509.02523", "title": "Paper A"}])
        if key == "https://huggingface.co/api/papers/2509.02523":
            return DummyResponse(200, json_data={"abstract": "Detailed abstract"})
        if key == "https://huggingface.co/api/arxiv/2509.02523/repos":
            return DummyResponse(200, json_data={"models": ["org/model-a"], "spaces": [], "datasets": []})
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = HuggingFaceCollector()
    items = await collector.collect({"limit": 1, "include_paper_detail": True, "include_arxiv_repos": True})

    assert len(items) == 1
    assert "Detailed abstract" in (items[0].content or "")
    assert items[0].metadata["arxiv_repos"]["models"] == ["org/model-a"]
