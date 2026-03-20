"""PubMed collector."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import httpx

from app.collectors.academic_common import build_search_text, parse_datetime, resolve_limit
from app.collectors.base import BaseCollector, RawArticle
from app.collectors.registry import register


@register("pubmed")
class PubMedCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "PubMed"

    @property
    def category(self) -> str:
        return "academic"

    async def collect(self, config: dict) -> list[RawArticle]:
        base_url = str(config.get("base_url") or "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/").rstrip("/")
        timeout_seconds = float(config.get("timeout_seconds", 20))
        user_agent = str(config.get("user_agent") or "LexDeepResearchBot/0.1").strip()
        max_results = resolve_limit(config.get("max_results"))
        shared_params = {
            "db": "pubmed",
            "retmode": "json",
            "api_key": _clean_text(config.get("api_key")),
            "tool": _clean_text(config.get("tool")),
            "email": _clean_text(config.get("email")),
        }
        shared_params = {key: value for key, value in shared_params.items() if value not in {None, ""}}
        search_params = {
            **shared_params,
            "term": build_search_text(config),
            "retmax": max_results,
            "datetype": "pdat",
            "mindate": _date_value(config.get("start_at")),
            "maxdate": _date_value(config.get("end_at")),
        }
        search_params = {key: value for key, value in search_params.items() if value not in {None, ""}}

        async with httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": user_agent},
        ) as client:
            search_response = await client.get(f"{base_url}/esearch.fcgi", params=search_params)
            search_response.raise_for_status()
            search_payload = search_response.json()
            ids = _search_ids(search_payload)
            if not ids:
                return []
            summary_response = await client.get(
                f"{base_url}/esummary.fcgi",
                params={**shared_params, "id": ",".join(ids)},
            )
            summary_response.raise_for_status()
            summary_payload = summary_response.json()
            abstract_by_pmid = await _fetch_abstracts(
                client=client,
                base_url=base_url,
                shared_params=shared_params,
                ids=ids,
            )

        articles: list[RawArticle] = []
        results = summary_payload.get("result", {}) if isinstance(summary_payload, dict) else {}
        for uid in ids:
            item = results.get(uid)
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or uid).strip()
            if not title:
                continue
            doi = _resolve_doi(item)
            authors = _authors(item.get("authors"))
            articles.append(
                RawArticle(
                    external_id=uid,
                    title=title,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                    content=abstract_by_pmid.get(uid),
                    published_at=_parse_summary_datetime(item.get("sortpubdate") or item.get("pubdate")),
                    metadata={
                        "collector": "pubmed",
                        "pmid": uid,
                        "doi": doi,
                        "authors": authors,
                        "journal": _clean_text(item.get("source")),
                    },
                )
            )
        return articles


def _search_ids(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return []
    result = payload.get("esearchresult")
    if not isinstance(result, dict):
        return []
    idlist = result.get("idlist")
    if not isinstance(idlist, list):
        return []
    return [str(item).strip() for item in idlist if str(item).strip()]


def _resolve_doi(item: dict) -> str | None:
    article_ids = item.get("articleids")
    if isinstance(article_ids, list):
        for article_id in article_ids:
            if not isinstance(article_id, dict):
                continue
            if str(article_id.get("idtype") or "").strip().lower() != "doi":
                continue
            doi = _clean_text(article_id.get("value"))
            if doi:
                return doi
    elocation = _clean_text(item.get("elocationid"))
    if not elocation:
        return None
    prefix = "doi:"
    if elocation.lower().startswith(prefix):
        return elocation[len(prefix):].strip() or None
    return None


def _authors(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = _clean_text(item.get("name"))
        if name:
            names.append(name)
    return names


def _date_value(raw: object) -> str | None:
    parsed = parse_datetime(raw)
    if parsed is None:
        return None
    return parsed.strftime("%Y/%m/%d")


async def _fetch_abstracts(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    shared_params: dict[str, str],
    ids: list[str],
) -> dict[str, str]:
    if not ids:
        return {}
    response = await client.get(
        f"{base_url}/efetch.fcgi",
        params={**shared_params, "db": "pubmed", "id": ",".join(ids), "retmode": "xml"},
    )
    response.raise_for_status()
    return _parse_efetch_abstracts(response.text)


def _parse_summary_datetime(raw: object) -> datetime | None:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo is not None else raw.replace(tzinfo=UTC)
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    if not value:
        return None
    candidates = [
        ("%Y/%m/%d %H:%M", value),
        ("%Y %b %d", value),
    ]
    for fmt, candidate in candidates:
        try:
            return datetime.strptime(candidate, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _parse_efetch_abstracts(xml_text: str) -> dict[str, str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return {}

    abstracts: dict[str, str] = {}
    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext("./MedlineCitation/PMID")
        if not isinstance(pmid, str) or not pmid.strip():
            continue
        parts: list[str] = []
        for abstract_text in article.findall(".//Abstract/AbstractText"):
            text = "".join(abstract_text.itertext()).strip()
            if text:
                parts.append(text)
        if parts:
            abstracts[pmid.strip()] = "\n\n".join(parts)
    return abstracts


def _clean_text(raw: object) -> str | None:
    value = str(raw or "").strip()
    return value or None
