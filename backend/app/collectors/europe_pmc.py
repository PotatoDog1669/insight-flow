"""Europe PMC collector."""

from __future__ import annotations

import httpx

from app.collectors.academic_common import build_search_text, parse_datetime, resolve_limit
from app.collectors.base import BaseCollector, RawArticle
from app.collectors.fulltext import DEFAULT_EXTRACTOR_CHAIN, extract_fulltext
from app.collectors.pubmed import _fetch_abstracts
from app.collectors.registry import register


@register("europe_pmc")
class EuropePMCCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "Europe PMC"

    @property
    def category(self) -> str:
        return "academic"

    async def collect(self, config: dict) -> list[RawArticle]:
        base_url = str(config.get("base_url") or "https://www.ebi.ac.uk/europepmc/webservices/rest/search").strip()
        timeout_seconds = float(config.get("timeout_seconds", 20))
        user_agent = str(config.get("user_agent") or "LexDeepResearchBot/0.1").strip()
        max_results = resolve_limit(config.get("max_results"))
        extractor_chain = config.get("extractor_chain", list(DEFAULT_EXTRACTOR_CHAIN))
        min_content_chars = int(config.get("min_content_chars", 40))
        params = {
            "query": _build_query(config),
            "pageSize": max_results,
            "format": "json",
            "resultType": str(config.get("result_type") or "core"),
        }

        async with httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": user_agent},
        ) as client:
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            payload = response.json()
            pmids = _pmids(payload)
            fallback_abstracts = await _fetch_abstracts(
                client=client,
                base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
                shared_params={},
                ids=pmids,
            ) if pmids else {}
            detail_contents = await _fetch_detail_contents(
                client=client,
                payload=payload,
                fallback_abstracts=fallback_abstracts,
                extractor_chain=extractor_chain,
                min_content_chars=min_content_chars,
            )

        result_list = payload.get("resultList", {}) if isinstance(payload, dict) else {}
        items = result_list.get("result", []) if isinstance(result_list, dict) else []
        articles: list[RawArticle] = []
        for item in items[:max_results]:
            if not isinstance(item, dict):
                continue
            pmid = str(item.get("pmid") or item.get("id") or "").strip()
            title = str(item.get("title") or pmid or "Untitled").strip()
            if not title:
                continue
            authors = _authors(item.get("authorString"))
            doi = _clean_text(item.get("doi"))
            url = _full_text_url(item.get("fullTextUrlList")) or _doi_url(doi)
            pub_type = _clean_text(item.get("pubType")) or ""
            articles.append(
                RawArticle(
                    external_id=pmid or title,
                    title=title,
                    url=url,
                    content=(
                        _clean_text(item.get("abstractText"))
                        or fallback_abstracts.get(pmid)
                        or detail_contents.get(pmid)
                    ),
                    published_at=parse_datetime(item.get("firstPublicationDate")),
                    metadata={
                        "collector": "europe_pmc",
                        "pmid": pmid or None,
                        "pmcid": _clean_text(item.get("pmcid")),
                        "doi": doi,
                        "source": _clean_text(item.get("source")),
                        "journal": _clean_text(item.get("journalTitle")),
                        "authors": authors,
                        "is_preprint": pub_type.lower() == "preprint",
                    },
                )
            )
        return articles


def _build_query(config: dict) -> str:
    search_query = build_search_text(config)
    date_clause = _date_clause(config)
    parts = [part for part in [search_query, date_clause] if part]
    return " AND ".join(parts) if parts else "*"


def _pmids(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return []
    result_list = payload.get("resultList")
    if not isinstance(result_list, dict):
        return []
    results = result_list.get("result")
    if not isinstance(results, list):
        return []
    pmids: list[str] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        pmid = _clean_text(item.get("pmid") or item.get("id"))
        if pmid:
            pmids.append(pmid)
    return pmids


def _date_clause(config: dict) -> str:
    start_at = parse_datetime(config.get("start_at"))
    end_at = parse_datetime(config.get("end_at"))
    if start_at is None and end_at is None:
        return ""
    start_value = start_at.date().isoformat() if start_at is not None else "1900-01-01"
    end_value = end_at.date().isoformat() if end_at is not None else "3000-01-01"
    return f"FIRST_PDATE:[{start_value} TO {end_value}]"


async def _fetch_detail_contents(
    *,
    client: httpx.AsyncClient,
    payload: dict,
    fallback_abstracts: dict[str, str],
    extractor_chain: list[str] | tuple[str, ...],
    min_content_chars: int,
) -> dict[str, str]:
    contents: dict[str, str] = {}
    result_list = payload.get("resultList")
    if not isinstance(result_list, dict):
        return contents
    results = result_list.get("result")
    if not isinstance(results, list):
        return contents
    for item in results:
        if not isinstance(item, dict):
            continue
        pmid = _clean_text(item.get("pmid") or item.get("id"))
        if not pmid or _clean_text(item.get("abstractText")) or fallback_abstracts.get(pmid):
            continue
        url = _full_text_url(item.get("fullTextUrlList")) or _doi_url(_clean_text(item.get("doi")))
        if not url:
            continue
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            continue
        extracted, _ = extract_fulltext(
            response.text,
            extractor_chain=extractor_chain,
            min_content_chars=min_content_chars,
        )
        if extracted:
            contents[pmid] = extracted
    return contents


def _authors(raw: object) -> list[str]:
    if not isinstance(raw, str):
        return []
    return [item.strip() for item in raw.split(";") if item.strip()]


def _full_text_url(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    full_text_urls = raw.get("fullTextUrl")
    if not isinstance(full_text_urls, list):
        return None
    for item in full_text_urls:
        if not isinstance(item, dict):
            continue
        url = _clean_text(item.get("url"))
        if url:
            return url
    return None


def _doi_url(doi: str | None) -> str | None:
    if not doi:
        return None
    return f"https://doi.org/{doi}"


def _clean_text(raw: object) -> str | None:
    value = str(raw or "").strip()
    return value or None
