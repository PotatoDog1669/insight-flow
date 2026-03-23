"""Paper figure URL helpers."""

from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx

_ARXIV_HTML_ROOT = "https://arxiv.org/html/"
_ARXIV_RELATIVE_ASSET_RE = re.compile(r"^\d{4}\.\d{4,5}v\d+/")
_ARXIV_DUPLICATED_PATH_RE = re.compile(
    r"(?P<prefix>https?://arxiv\.org/html/)(?P<arxiv_id>\d{4}\.\d{4,5}v\d+)/(?P=arxiv_id)/"
)


def normalize_arxiv_figure_url(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    return _ARXIV_DUPLICATED_PATH_RE.sub(r"\g<prefix>\g<arxiv_id>/", value)


def resolve_figure_url(*, base_url: str, image_src: str) -> str:
    source = str(image_src or "").strip()
    if not source:
        return ""
    if _ARXIV_RELATIVE_ASSET_RE.match(source):
        return normalize_arxiv_figure_url(urljoin(_ARXIV_HTML_ROOT, source))
    normalized_base = base_url if base_url.endswith("/") else f"{base_url}/"
    return normalize_arxiv_figure_url(urljoin(normalized_base, source))


def extract_first_figure_candidate(html: str, *, base_url: str) -> tuple[str, str]:
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
    caption = ""
    if caption_match:
        caption = re.sub(r"<[^>]+>", " ", caption_match.group(1))
        caption = re.sub(r"\s+", " ", caption).strip()
    return resolve_figure_url(base_url=base_url, image_src=image_match.group(1)), caption


async def is_reachable_image_url(client: httpx.AsyncClient, url: str) -> bool:
    target = str(url or "").strip()
    if not target:
        return False
    try:
        response = await client.get(target)
        response.raise_for_status()
    except Exception:
        return False
    content_type = str((response.headers or {}).get("content-type") or "").lower()
    return "image" in content_type


async def select_primary_figure_url(
    client: httpx.AsyncClient,
    *,
    html: str,
    base_url: str,
    project_teaser_url: str = "",
) -> tuple[str, str]:
    figure_url, caption = extract_first_figure_candidate(html, base_url=base_url)
    if figure_url and await is_reachable_image_url(client, figure_url):
        return figure_url, caption
    teaser = str(project_teaser_url or "").strip()
    if teaser and await is_reachable_image_url(client, teaser):
        return teaser, ""
    return "", ""
