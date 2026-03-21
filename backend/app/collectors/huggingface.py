"""Hugging Face Collector（先聚焦 Daily Papers）。"""

from __future__ import annotations

from datetime import datetime, timezone
from html import unescape
import re
from urllib.parse import urljoin

import httpx

from app.collectors.base import BaseCollector, RawArticle
from app.collectors.registry import register


@register("huggingface")
class HuggingFaceCollector(BaseCollector):
    """Hugging Face 采集器（Daily Papers + 增强详情）。"""

    @property
    def name(self) -> str:
        return "Hugging Face"

    @property
    def category(self) -> str:
        return "open_source"

    async def collect(self, config: dict) -> list[RawArticle]:
        timeout_seconds = float(config.get("timeout_seconds", 20))
        user_agent = config.get("user_agent", "LexDeepResearchBot/0.1")
        limit = int(config.get("limit", 30))
        include_paper_detail = bool(config.get("include_paper_detail", True))
        include_arxiv_repos = bool(config.get("include_arxiv_repos", True))

        params = {
            "limit": limit,
            "p": config.get("p"),
            "date": config.get("date"),
            "week": config.get("week"),
            "month": config.get("month"),
            "submitter": config.get("submitter"),
            "sort": config.get("sort"),
        }
        params = {k: v for k, v in params.items() if v is not None}
        snapshot_at = datetime.now(timezone.utc)
        snapshot_date = snapshot_at.date().isoformat()

        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True, headers={"User-Agent": user_agent}) as client:
            daily_resp = await client.get("https://huggingface.co/api/daily_papers", params=params)
            daily_resp.raise_for_status()
            daily_json = daily_resp.json() or []
            papers = daily_json.get("papers", []) if isinstance(daily_json, dict) else daily_json
            items: list[RawArticle] = []
            for paper in list(papers)[:limit]:
                if not isinstance(paper, dict):
                    continue
                paper_payload = paper.get("paper") if isinstance(paper.get("paper"), dict) else {}
                paper_id = _paper_id(paper)
                if not paper_id:
                    continue
                title = str(paper.get("title") or paper_payload.get("title") or paper_id)
                summary = str(paper.get("summary") or paper.get("abstract") or paper_payload.get("summary") or paper_payload.get("abstract") or "")
                detail_payload: dict = {}
                if include_paper_detail:
                    detail_payload = await _safe_json_get(client, f"https://huggingface.co/api/papers/{paper_id}")
                    detail_text = detail_payload.get("abstract") or detail_payload.get("summary")
                    if isinstance(detail_text, str) and detail_text.strip():
                        summary = detail_text
                arxiv_repos: dict = {}
                if include_arxiv_repos:
                    arxiv_payload = await _safe_json_get(client, f"https://huggingface.co/api/arxiv/{paper_id}/repos")
                    if isinstance(arxiv_payload, dict):
                        arxiv_repos = arxiv_payload
                organization = paper.get("organization") or paper_payload.get("organization") or detail_payload.get("organization")
                project_url = _project_url(paper, paper_payload, detail_payload)
                arxiv_figure_url = ""
                figure_caption = ""
                if include_paper_detail:
                    arxiv_html = await _safe_text_get(client, f"https://arxiv.org/html/{paper_id}")
                    arxiv_figure_url, figure_caption = _extract_first_figure(arxiv_html, base_url=f"https://arxiv.org/html/{paper_id}")
                project_teaser_url = ""
                if project_url:
                    project_html = await _safe_text_get(client, project_url)
                    project_teaser_url = _extract_project_teaser(project_html, base_url=project_url)
                metadata = {
                    "collector": "huggingface_daily_papers",
                    "paper_id": paper_id,
                    "entity_id": paper_id,
                    "snapshot_at": snapshot_at.isoformat(),
                    "snapshot_date": snapshot_date,
                    "source_endpoint": "/api/daily_papers",
                    "authors": paper.get("authors") or paper_payload.get("authors") or detail_payload.get("authors") or [],
                    "organization": organization,
                    "project_url": project_url,
                    "figure_url": arxiv_figure_url,
                    "figure_caption": figure_caption,
                    "project_teaser_url": project_teaser_url,
                    "summary_source": "hf_paper_detail" if detail_payload else "daily_papers",
                    "arxiv_repos": arxiv_repos,
                    "fetched_at": snapshot_at.isoformat(),
                }
                items.append(
                    RawArticle(
                        external_id=f"{paper_id}#{snapshot_date}",
                        title=title,
                        url=f"https://huggingface.co/papers/{paper_id}",
                        content=summary or None,
                        published_at=None,
                        metadata=metadata,
                    )
                )
        return items


def _paper_id(payload: dict) -> str:
    for key in ("id", "paperId", "paper_id", "arxivId"):
        value = payload.get(key)
        if value:
            return str(value)
    nested = payload.get("paper")
    if isinstance(nested, dict):
        for key in ("id", "paperId", "arxivId"):
            value = nested.get(key)
            if value:
                return str(value)
    return ""


def _project_url(*sources: dict) -> str:
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in ("projectPage", "project_page", "projectUrl", "project_url"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _extract_first_figure(html: str, *, base_url: str) -> tuple[str, str]:
    if not html:
        return "", ""
    figure_match = re.search(r"<figure\b[^>]*>(.*?)</figure>", html, flags=re.IGNORECASE | re.DOTALL)
    if not figure_match:
        return "", ""
    figure_block = figure_match.group(1)
    image_match = re.search(r'<img\b[^>]*src=["\']([^"\']+)["\']', figure_block, flags=re.IGNORECASE)
    if not image_match:
        return "", ""
    caption_match = re.search(r"<figcaption\b[^>]*>(.*?)</figcaption>", figure_block, flags=re.IGNORECASE | re.DOTALL)
    caption = _clean_html_text(caption_match.group(1)) if caption_match else ""
    return urljoin(base_url, image_match.group(1).strip()), caption


def _extract_project_teaser(html: str, *, base_url: str) -> str:
    if not html:
        return ""
    match = re.search(
        r'<meta\b[^>]*(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]*content=["\']([^"\']+)["\']',
        html,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return urljoin(base_url, match.group(1).strip())


def _clean_html_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = unescape(re.sub(r"\s+", " ", text)).strip()
    return text


async def _safe_json_get(client: httpx.AsyncClient, url: str) -> dict:
    try:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


async def _safe_text_get(client: httpx.AsyncClient, url: str) -> str:
    try:
        response = await client.get(url)
        response.raise_for_status()
        return str(response.text or "")
    except Exception:
        return ""
