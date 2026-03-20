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
            request = httpx.Request("GET", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    def json(self):
        return self._json_data


@pytest.mark.asyncio
async def test_pubmed_collector_maps_search_and_summary_results(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict]] = []

    async def fake_get(self, url, *args, **kwargs):
        raw_url = str(url)
        params = dict(kwargs.get("params") or {})
        calls.append((raw_url, params))
        if raw_url.endswith("/esearch.fcgi"):
            return DummyResponse(
                200,
                json_data={
                    "esearchresult": {
                        "idlist": ["40123456"],
                    }
                },
            )
        if raw_url.endswith("/esummary.fcgi"):
            return DummyResponse(
                200,
                json_data={
                    "result": {
                        "uids": ["40123456"],
                        "40123456": {
                            "uid": "40123456",
                            "title": "PubMed Agents",
                            "pubdate": "2026 Mar 08",
                            "sortpubdate": "2026/03/08 00:00",
                            "source": "Nature",
                            "articleids": [
                                {"idtype": "doi", "value": "10.1000/pubmed"},
                            ],
                            "authors": [
                                {"name": "Alice"},
                                {"name": "Bob"},
                            ],
                            "elocationid": "doi: 10.1000/pubmed",
                        },
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
          <AbstractText>Detailed abstract from efetch.</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>""",
            )
        raise AssertionError(f"unexpected url: {raw_url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = get_collector("pubmed")
    articles = await collector.collect(
        {
            "base_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
            "keywords": ["reasoning", "agent"],
            "max_results": 5,
            "start_at": "2026-03-01T00:00:00+00:00",
            "end_at": "2026-03-17T23:59:59+00:00",
            "api_key": "demo-key",
            "tool": "lexdeepresearch",
            "email": "research@example.com",
        }
    )

    assert calls[0][0].endswith("/esearch.fcgi")
    assert calls[0][1]["term"] == "reasoning agent"
    assert calls[0][1]["retmax"] == 5
    assert calls[0][1]["mindate"] == "2026/03/01"
    assert calls[0][1]["maxdate"] == "2026/03/17"
    assert calls[0][1]["api_key"] == "demo-key"
    assert calls[0][1]["tool"] == "lexdeepresearch"
    assert calls[0][1]["email"] == "research@example.com"
    assert calls[1][0].endswith("/esummary.fcgi")
    assert calls[1][1]["id"] == "40123456"
    assert calls[2][0].endswith("/efetch.fcgi")
    assert calls[2][1]["id"] == "40123456"
    assert len(articles) == 1
    assert articles[0].external_id == "40123456"
    assert articles[0].title == "PubMed Agents"
    assert articles[0].content == "Detailed abstract from efetch."
    assert articles[0].metadata["pmid"] == "40123456"
    assert articles[0].metadata["doi"] == "10.1000/pubmed"
    assert articles[0].metadata["authors"] == ["Alice", "Bob"]
    assert articles[0].metadata["journal"] == "Nature"
