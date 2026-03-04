"""GitHub Trending Collector。"""

from __future__ import annotations

from datetime import datetime, timezone
import re

from bs4 import BeautifulSoup
import httpx

from app.collectors.base import BaseCollector, RawArticle
from app.collectors.registry import register


@register("github_trending")
class GitHubTrendingCollector(BaseCollector):
    """GitHub Trending 采集器（TopN + Repo 元数据增强）。"""

    @property
    def name(self) -> str:
        return "GitHub Trending"

    @property
    def category(self) -> str:
        return "open_source"

    async def collect(self, config: dict) -> list[RawArticle]:
        limit = int(config.get("limit", 10))
        since = config.get("since", "daily")
        language = config.get("language")
        include_readme = bool(config.get("include_readme", True))
        include_repo_tree = bool(config.get("include_repo_tree", True))
        timeout_seconds = float(config.get("timeout_seconds", 20))
        github_token = config.get("github_token", "")
        user_agent = config.get("user_agent", "LexDeepResearchBot/0.1")

        headers = {"User-Agent": user_agent}
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"

        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True, headers=headers) as client:
            params = {"since": since}
            if language:
                params["l"] = language
            response = await client.get("https://github.com/trending", params=params)
            response.raise_for_status()
            repos = _parse_trending(response.text)[:limit]
            snapshot_at = datetime.now(timezone.utc)
            snapshot_date = snapshot_at.date().isoformat()

            items: list[RawArticle] = []
            for repo in repos:
                full_name = repo["repo_full_name"]
                enrich = await _fetch_repo_enrichment(
                    client=client,
                    full_name=full_name,
                    include_readme=include_readme,
                    include_repo_tree=include_repo_tree,
                )
                content = enrich.get("readme") or repo.get("description") or ""
                metadata = {
                    "collector": "github_trending",
                    "repo_full_name": full_name,
                    "entity_id": full_name,
                    "snapshot_at": snapshot_at.isoformat(),
                    "snapshot_date": snapshot_date,
                    "stars_today": repo.get("stars_today", 0),
                    "stars_total": enrich.get("stars_total"),
                    "language": repo.get("language"),
                    "description": repo.get("description"),
                    "readme_source": "github_api" if enrich.get("readme") else None,
                    "readme_chars": len(enrich.get("readme") or ""),
                    "repo_tree": enrich.get("repo_tree", []),
                    "fetched_at": snapshot_at.isoformat(),
                }
                items.append(
                    RawArticle(
                        external_id=f"{full_name}#{snapshot_date}",
                        title=full_name,
                        url=f"https://github.com/{full_name}",
                        content=content or None,
                        published_at=None,
                        metadata=metadata,
                    )
                )
        return items


def _parse_trending(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("article.Box-row")
    repos: list[dict] = []
    for row in rows:
        link = row.select_one("h2 a")
        if not link:
            continue
        href = (link.get("href") or "").strip()
        if not href:
            continue
        full_name = href.strip("/").replace(" ", "")
        if "/" not in full_name:
            continue
        description = _text_or_none(row.select_one("p"))
        language = _text_or_none(row.select_one("[itemprop='programmingLanguage']"))
        stars_today = _parse_stars_today(row.get_text(" ", strip=True))
        repos.append(
            {
                "repo_full_name": full_name,
                "description": description,
                "language": language,
                "stars_today": stars_today,
            }
        )
    return repos


def _parse_stars_today(text: str) -> int:
    match = re.search(r"(\d[\d,]*)\s+stars?\s+today", text, flags=re.IGNORECASE)
    if not match:
        return 0
    return int(match.group(1).replace(",", ""))


def _text_or_none(node) -> str | None:
    if not node:
        return None
    text = node.get_text(" ", strip=True)
    return text or None


async def _fetch_repo_enrichment(
    client: httpx.AsyncClient,
    full_name: str,
    include_readme: bool,
    include_repo_tree: bool,
) -> dict:
    result: dict = {"stars_total": None, "readme": "", "repo_tree": []}
    default_branch = "main"
    try:
        repo_resp = await client.get(f"https://api.github.com/repos/{full_name}")
        repo_resp.raise_for_status()
        repo_json = repo_resp.json()
        result["stars_total"] = repo_json.get("stargazers_count")
        default_branch = repo_json.get("default_branch") or default_branch
        if not result.get("description") and repo_json.get("description"):
            result["description"] = repo_json["description"]
    except Exception:
        return result

    if include_readme:
        try:
            readme_resp = await client.get(
                f"https://api.github.com/repos/{full_name}/readme",
                headers={"Accept": "application/vnd.github.raw+json"},
            )
            readme_resp.raise_for_status()
            result["readme"] = readme_resp.text
        except Exception:
            pass

    if include_repo_tree:
        try:
            tree_resp = await client.get(
                f"https://api.github.com/repos/{full_name}/git/trees/{default_branch}",
                params={"recursive": 1},
            )
            tree_resp.raise_for_status()
            tree_json = tree_resp.json() or {}
            result["repo_tree"] = [
                str(item.get("path"))
                for item in (tree_json.get("tree") or [])
                if isinstance(item, dict) and item.get("path")
            ][:200]
        except Exception:
            pass

    return result
