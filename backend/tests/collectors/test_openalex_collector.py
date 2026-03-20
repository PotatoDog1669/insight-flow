from __future__ import annotations

import httpx
import pytest

from app.collectors import get_collector


class DummyResponse:
    def __init__(self, status_code: int = 200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://api.openalex.org/works")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    def json(self):
        return self._json_data


@pytest.mark.asyncio
async def test_openalex_collector_maps_works_with_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    async def fake_get(self, url, *args, **kwargs):
        called["url"] = str(url)
        called["params"] = dict(kwargs.get("params") or {})
        called["headers"] = dict(kwargs.get("headers") or {})
        return DummyResponse(
            200,
            json_data={
                "results": [
                    {
                        "id": "https://openalex.org/W123",
                        "doi": "https://doi.org/10.1000/openalex",
                        "title": "Reasoning Agents in Practice",
                        "publication_date": "2026-03-10",
                        "publication_year": 2026,
                        "primary_location": {
                            "landing_page_url": "https://example.com/paper",
                            "source": {"display_name": "NeurIPS"},
                        },
                        "authorships": [
                            {"author": {"display_name": "Alice"}},
                            {"author": {"display_name": "Bob"}},
                        ],
                        "abstract_inverted_index": {"Reasoning": [0], "agents": [1]},
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = get_collector("openalex")
    articles = await collector.collect(
        {
            "base_url": "https://api.openalex.org/works",
            "keywords": ["reasoning", "agent"],
            "max_results": 5,
            "start_at": "2026-03-01T00:00:00+00:00",
            "end_at": "2026-03-17T23:59:59+00:00",
            "mailto": "research@example.com",
            "api_key": "demo-key",
        }
    )

    assert called["url"] == "https://api.openalex.org/works"
    params = called["params"]
    assert params["search"] == "reasoning agent"
    assert params["per-page"] == 5
    assert "from_publication_date:2026-03-01" in params["filter"]
    assert "to_publication_date:2026-03-17" in params["filter"]
    assert params["mailto"] == "research@example.com"
    assert called["headers"]["api-key"] == "demo-key"
    assert len(articles) == 1
    assert articles[0].external_id == "https://openalex.org/W123"
    assert articles[0].title == "Reasoning Agents in Practice"
    assert articles[0].url == "https://example.com/paper"
    assert articles[0].metadata["openalex_id"] == "https://openalex.org/W123"
    assert articles[0].metadata["doi"] == "10.1000/openalex"
    assert articles[0].metadata["authors"] == ["Alice", "Bob"]
    assert articles[0].metadata["venue"] == "NeurIPS"
