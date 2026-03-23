from __future__ import annotations

import httpx
import pytest

from app.collectors.huggingface import HuggingFaceCollector


class DummyResponse:
    def __init__(self, status_code: int = 200, text: str = "", json_data=None, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data
        self.headers = headers or {}

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


@pytest.mark.asyncio
async def test_enriches_visual_assets_from_arxiv_html_and_project_page(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(self, url, *args, **kwargs):
        key = str(url)
        if key == "https://huggingface.co/api/daily_papers":
            return DummyResponse(200, json_data=[{"id": "2509.02523", "title": "Paper A"}])
        if key == "https://huggingface.co/api/papers/2509.02523":
            return DummyResponse(
                200,
                json_data={
                    "abstract": "Detailed abstract",
                    "projectPage": "https://demo.example.com/project",
                },
            )
        if key == "https://arxiv.org/html/2509.02523":
            return DummyResponse(
                200,
                text=(
                    '<figure><img src="/html/2509.02523v1/x1.png" />'
                    "<figcaption>Figure 1: Pipeline overview</figcaption></figure>"
                ),
            )
        if key == "https://arxiv.org/html/2509.02523v1/x1.png":
            return DummyResponse(200, headers={"content-type": "image/png"})
        if key == "https://demo.example.com/project":
            return DummyResponse(
                200,
                text='<html><head><meta property="og:image" content="/assets/teaser.png" /></head></html>',
            )
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = HuggingFaceCollector()
    items = await collector.collect({"limit": 1, "include_paper_detail": True, "include_arxiv_repos": False})

    assert len(items) == 1
    assert items[0].metadata["figure_url"] == "https://arxiv.org/html/2509.02523v1/x1.png"
    assert items[0].metadata["figure_caption"] == "Figure 1: Pipeline overview"
    assert items[0].metadata["project_url"] == "https://demo.example.com/project"
    assert items[0].metadata["project_teaser_url"] == "https://demo.example.com/assets/teaser.png"


@pytest.mark.asyncio
async def test_normalizes_arxiv_relative_figure_urls_before_storing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(self, url, *args, **kwargs):
        key = str(url)
        if key == "https://huggingface.co/api/daily_papers":
            return DummyResponse(200, json_data=[{"id": "2509.02523v1", "title": "Paper A"}])
        if key == "https://huggingface.co/api/papers/2509.02523v1":
            return DummyResponse(200, json_data={"abstract": "Detailed abstract"})
        if key == "https://arxiv.org/html/2509.02523v1":
            return DummyResponse(
                200,
                text=(
                    '<figure><img src="2509.02523v1/x1.png" />'
                    "<figcaption>Figure 1: Pipeline overview</figcaption></figure>"
                ),
            )
        if key == "https://arxiv.org/html/2509.02523v1/x1.png":
            return DummyResponse(200, headers={"content-type": "image/png"})
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = HuggingFaceCollector()
    items = await collector.collect({"limit": 1, "include_paper_detail": True, "include_arxiv_repos": False})

    assert len(items) == 1
    assert items[0].metadata["figure_url"] == "https://arxiv.org/html/2509.02523v1/x1.png"


@pytest.mark.asyncio
async def test_falls_back_to_project_teaser_when_arxiv_figure_is_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(self, url, *args, **kwargs):
        key = str(url)
        if key == "https://huggingface.co/api/daily_papers":
            return DummyResponse(200, json_data=[{"id": "2509.02523v1", "title": "Paper A"}])
        if key == "https://huggingface.co/api/papers/2509.02523v1":
            return DummyResponse(
                200,
                json_data={
                    "abstract": "Detailed abstract",
                    "projectPage": "https://demo.example.com/project",
                },
            )
        if key == "https://arxiv.org/html/2509.02523v1":
            return DummyResponse(
                200,
                text=(
                    '<figure><img src="2509.02523v1/x1.png" />'
                    "<figcaption>Figure 1: Pipeline overview</figcaption></figure>"
                ),
            )
        if key == "https://arxiv.org/html/2509.02523v1/x1.png":
            return DummyResponse(404)
        if key == "https://demo.example.com/project":
            return DummyResponse(
                200,
                text='<html><head><meta property="og:image" content="/assets/teaser.png" /></head></html>',
            )
        if key == "https://demo.example.com/assets/teaser.png":
            return DummyResponse(200, headers={"content-type": "image/png"})
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = HuggingFaceCollector()
    items = await collector.collect({"limit": 1, "include_paper_detail": True, "include_arxiv_repos": False})

    assert len(items) == 1
    assert items[0].metadata["figure_url"] == "https://demo.example.com/assets/teaser.png"
    assert items[0].metadata["project_teaser_url"] == "https://demo.example.com/assets/teaser.png"


@pytest.mark.asyncio
async def test_falls_back_to_pdf_extraction_when_arxiv_and_teaser_are_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(self, url, *args, **kwargs):
        key = str(url)
        if key == "https://huggingface.co/api/daily_papers":
            return DummyResponse(200, json_data=[{"id": "2509.02523v1", "title": "Paper A"}])
        if key == "https://huggingface.co/api/papers/2509.02523v1":
            return DummyResponse(200, json_data={"abstract": "Detailed abstract"})
        if key == "https://arxiv.org/html/2509.02523v1":
            return DummyResponse(200, text="<html><body>No figures</body></html>")
        raise AssertionError(f"Unexpected URL: {url}")

    async def fake_pdf_fallback(*args, **kwargs) -> str:  # noqa: ANN002, ANN003
        return "http://127.0.0.1:8000/api/v1/reports/paper-assets/2509.02523v1/figure.png"

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr("app.collectors.huggingface.extract_pdf_figure_public_url", fake_pdf_fallback)

    collector = HuggingFaceCollector()
    items = await collector.collect({"limit": 1, "include_paper_detail": True, "include_arxiv_repos": False})

    assert len(items) == 1
    assert items[0].metadata["figure_url"] == "http://127.0.0.1:8000/api/v1/reports/paper-assets/2509.02523v1/figure.png"


@pytest.mark.asyncio
async def test_collect_uses_nested_paper_authors_and_tracks_source_organization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(self, url, *args, **kwargs):
        if str(url) == "https://huggingface.co/api/daily_papers":
            return DummyResponse(
                200,
                json_data=[
                    {
                        "title": "Paper A",
                        "paper": {
                            "id": "2603.13045",
                            "authors": [
                                {"name": "Yifeng Liu"},
                                {"name": "Siqi Ouyang"},
                            ],
                        },
                        "organization": {"fullname": "Tsinghua NLP"},
                    }
                ],
            )
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = HuggingFaceCollector()
    items = await collector.collect({"limit": 1, "include_paper_detail": False, "include_arxiv_repos": False})

    assert len(items) == 1
    assert items[0].metadata["authors"] == [
        {"name": "Yifeng Liu"},
        {"name": "Siqi Ouyang"},
    ]
    assert items[0].metadata["organization"] == {"fullname": "Tsinghua NLP"}
