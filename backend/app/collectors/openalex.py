"""OpenAlex collector."""

from __future__ import annotations

import httpx

from app.collectors.academic_common import build_search_text, parse_datetime, resolve_limit
from app.collectors.base import BaseCollector, RawArticle
from app.collectors.registry import register


@register("openalex")
class OpenAlexCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "OpenAlex"

    @property
    def category(self) -> str:
        return "academic"

    async def collect(self, config: dict) -> list[RawArticle]:
        base_url = str(config.get("base_url") or "https://api.openalex.org/works").strip()
        timeout_seconds = float(config.get("timeout_seconds", 20))
        user_agent = str(config.get("user_agent") or "LexDeepResearchBot/0.1").strip()
        max_results = resolve_limit(config.get("max_results"))
        params = {
            "search": build_search_text(config),
            "per-page": max_results,
            "filter": _date_filter(config),
        }
        mailto = str(config.get("mailto") or "").strip()
        if mailto:
            params["mailto"] = mailto
        params = {key: value for key, value in params.items() if value not in {"", None}}
        headers = {"User-Agent": user_agent}
        api_key = str(config.get("api_key") or "").strip()
        if api_key:
            headers["api-key"] = api_key

        async with httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": user_agent},
        ) as client:
            response = await client.get(base_url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()

        items = payload.get("results", []) if isinstance(payload, dict) else []
        articles: list[RawArticle] = []
        for item in items[:max_results]:
            if not isinstance(item, dict):
                continue
            openalex_id = str(item.get("id") or "").strip()
            title = str(item.get("title") or openalex_id or "Untitled").strip()
            if not title:
                continue
            doi = _normalize_doi(item.get("doi"))
            authors = _authors(item.get("authorships"))
            venue = _venue(item.get("primary_location"))
            url = _landing_page_url(item.get("primary_location")) or openalex_id or None
            published_at = parse_datetime(item.get("publication_date"))
            articles.append(
                RawArticle(
                    external_id=openalex_id or title,
                    title=title,
                    url=url,
                    content=_abstract_text(item.get("abstract_inverted_index")),
                    published_at=published_at,
                    metadata={
                        "collector": "openalex",
                        "openalex_id": openalex_id,
                        "doi": doi,
                        "authors": authors,
                        "venue": venue,
                        "publication_year": item.get("publication_year"),
                    },
                )
            )
        return articles


def _date_filter(config: dict) -> str:
    filters: list[str] = []
    start_at = parse_datetime(config.get("start_at"))
    end_at = parse_datetime(config.get("end_at"))
    if start_at is not None:
        filters.append(f"from_publication_date:{start_at.date().isoformat()}")
    if end_at is not None:
        filters.append(f"to_publication_date:{end_at.date().isoformat()}")
    return ",".join(filters)


def _authors(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        author = item.get("author")
        if not isinstance(author, dict):
            continue
        display_name = str(author.get("display_name") or "").strip()
        if display_name:
            names.append(display_name)
    return names


def _venue(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    source = raw.get("source")
    if not isinstance(source, dict):
        return None
    display_name = str(source.get("display_name") or "").strip()
    return display_name or None


def _landing_page_url(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    landing_page_url = str(raw.get("landing_page_url") or "").strip()
    return landing_page_url or None


def _normalize_doi(raw: object) -> str | None:
    value = str(raw or "").strip()
    if not value:
        return None
    return value.replace("https://doi.org/", "").replace("http://doi.org/", "")


def _abstract_text(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    words_by_position: dict[int, str] = {}
    for word, positions in raw.items():
        if not isinstance(word, str) or not isinstance(positions, list):
            continue
        for position in positions:
            if isinstance(position, int):
                words_by_position[position] = word
    if not words_by_position:
        return None
    return " ".join(words_by_position[index] for index in sorted(words_by_position))
