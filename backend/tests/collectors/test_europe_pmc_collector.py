from __future__ import annotations

import httpx
import pytest

from app.collectors import get_collector


class DummyResponse:
    def __init__(self, status_code: int = 200, json_data=None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://www.ebi.ac.uk/europepmc/webservices/rest/search")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    def json(self):
        return self._json_data


@pytest.mark.asyncio
async def test_europe_pmc_collector_maps_results_with_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict]] = []

    async def fake_get(self, url, *args, **kwargs):
        calls.append((str(url), dict(kwargs.get("params") or {})))
        return DummyResponse(
            200,
            json_data={
                "resultList": {
                    "result": [
                        {
                            "id": "40123456",
                            "pmid": "40123456",
                            "pmcid": "PMC123456",
                            "doi": "10.1000/eupmc",
                            "title": "Biomedical Agents",
                            "abstractText": "Agent systems for biology.",
                            "pubYear": "2026",
                            "firstPublicationDate": "2026-03-08",
                            "journalTitle": "Nature Biotechnology",
                            "source": "MED",
                            "isOpenAccess": "Y",
                            "authorString": "Alice; Bob",
                            "pubType": "preprint",
                            "fullTextUrlList": {"fullTextUrl": [{"url": "https://example.com/fulltext"}]},
                        }
                    ]
                }
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = get_collector("europe_pmc")
    articles = await collector.collect(
        {
            "base_url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            "keywords": ["reasoning", "agent"],
            "max_results": 5,
            "start_at": "2026-03-01T00:00:00+00:00",
            "end_at": "2026-03-17T23:59:59+00:00",
        }
    )

    assert calls[0][0] == "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = calls[0][1]
    assert "reasoning agent" in params["query"]
    assert "FIRST_PDATE:[2026-03-01 TO 2026-03-17]" in params["query"]
    assert params["pageSize"] == 5
    assert params["format"] == "json"
    assert len(articles) == 1
    assert articles[0].external_id == "40123456"
    assert articles[0].title == "Biomedical Agents"
    assert articles[0].content == "Agent systems for biology."
    assert articles[0].metadata["pmid"] == "40123456"
    assert articles[0].metadata["pmcid"] == "PMC123456"
    assert articles[0].metadata["doi"] == "10.1000/eupmc"
    assert articles[0].metadata["source"] == "MED"
    assert articles[0].metadata["is_preprint"] is True
    assert articles[0].metadata["authors"] == ["Alice", "Bob"]


@pytest.mark.asyncio
async def test_europe_pmc_collector_falls_back_to_pubmed_abstract(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict]] = []

    async def fake_get(self, url, *args, **kwargs):
        raw_url = str(url)
        params = dict(kwargs.get("params") or {})
        calls.append((raw_url, params))
        if raw_url == "https://www.ebi.ac.uk/europepmc/webservices/rest/search":
            return DummyResponse(
                200,
                json_data={
                    "resultList": {
                        "result": [
                            {
                                "id": "40123456",
                                "pmid": "40123456",
                                "doi": "10.1000/eupmc",
                                "title": "Biomedical Agents",
                                "firstPublicationDate": "2026-03-08",
                                "source": "MED",
                                "authorString": "Alice; Bob",
                            }
                        ]
                    }
                },
            )
        if raw_url.endswith("/efetch.fcgi"):
            return DummyResponse(
                200,
                text="""<?xml version='1.0' encoding='UTF-8'?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>40123456</PMID>
      <Article>
        <Abstract>
          <AbstractText>Fallback abstract from PubMed.</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>""",
            )
        raise AssertionError(f"unexpected url: {raw_url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = get_collector("europe_pmc")
    articles = await collector.collect(
        {
            "base_url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            "keywords": ["reasoning", "agent"],
            "max_results": 1,
        }
    )

    assert len(articles) == 1
    assert articles[0].content == "Fallback abstract from PubMed."
    assert calls[1][0].endswith("/efetch.fcgi")
    assert calls[1][1]["id"] == "40123456"


@pytest.mark.asyncio
async def test_europe_pmc_collector_falls_back_to_detail_page_content(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict]] = []

    async def fake_get(self, url, *args, **kwargs):
        raw_url = str(url)
        params = dict(kwargs.get("params") or {})
        calls.append((raw_url, params))
        if raw_url == "https://www.ebi.ac.uk/europepmc/webservices/rest/search":
            return DummyResponse(
                200,
                json_data={
                    "resultList": {
                        "result": [
                            {
                                "id": "40123456",
                                "pmid": "40123456",
                                "doi": "10.1000/eupmc",
                                "title": "Biomedical Agents",
                                "firstPublicationDate": "2026-03-08",
                                "source": "MED",
                                "authorString": "Alice; Bob",
                                "fullTextUrlList": {"fullTextUrl": [{"url": "https://example.com/fulltext"}]},
                            }
                        ]
                    }
                },
            )
        if raw_url.endswith("/efetch.fcgi"):
            return DummyResponse(
                200,
                text="""<?xml version='1.0' encoding='UTF-8'?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>40123456</PMID>
      <Article />
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>""",
            )
        if raw_url == "https://example.com/fulltext":
            return DummyResponse(
                200,
                text="<html><body><article><p>Detail page fallback content for Europe PMC.</p></article></body></html>",
            )
        raise AssertionError(f"unexpected url: {raw_url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = get_collector("europe_pmc")
    articles = await collector.collect(
        {
            "base_url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            "keywords": ["reasoning", "agent"],
            "max_results": 1,
            "reader_fallback_enabled": False,
        }
    )

    assert len(articles) == 1
    assert articles[0].content == "Detail page fallback content for Europe PMC."
    assert calls[2][0] == "https://example.com/fulltext"


@pytest.mark.asyncio
async def test_europe_pmc_collector_does_not_swallow_unexpected_detail_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(self, url, *args, **kwargs):
        raw_url = str(url)
        if raw_url == "https://www.ebi.ac.uk/europepmc/webservices/rest/search":
            return DummyResponse(
                200,
                json_data={
                    "resultList": {
                        "result": [
                            {
                                "id": "40123456",
                                "pmid": "40123456",
                                "doi": "10.1000/eupmc",
                                "title": "Biomedical Agents",
                                "firstPublicationDate": "2026-03-08",
                                "source": "MED",
                                "authorString": "Alice; Bob",
                                "fullTextUrlList": {"fullTextUrl": [{"url": "https://example.com/fulltext"}]},
                            }
                        ]
                    }
                },
            )
        if raw_url.endswith("/efetch.fcgi"):
            return DummyResponse(
                200,
                text="""<?xml version='1.0' encoding='UTF-8'?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>40123456</PMID>
      <Article />
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>""",
            )
        if raw_url == "https://example.com/fulltext":
            raise RuntimeError("unexpected parser setup failure")
        raise AssertionError(f"unexpected url: {raw_url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = get_collector("europe_pmc")
    with pytest.raises(RuntimeError, match="unexpected parser setup failure"):
        await collector.collect(
            {
                "base_url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                "keywords": ["reasoning", "agent"],
                "max_results": 1,
            }
        )
