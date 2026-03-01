from __future__ import annotations

import httpx
import pytest

from app.collectors.github_trending import GitHubTrendingCollector


class DummyResponse:
    def __init__(self, status_code: int = 200, text: str = "", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://example.com")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    def json(self):
        return self._json_data


@pytest.mark.asyncio
async def test_extracts_daily_top10(monkeypatch: pytest.MonkeyPatch) -> None:
    cards = []
    for i in range(11):
        cards.append(
            f"""
            <article class=\"Box-row\">
              <h2><a href=\"/owner{i}/repo{i}\"> owner{i} / repo{i} </a></h2>
              <p>Description {i}</p>
              <span itemprop=\"programmingLanguage\">Python</span>
              <span>{i + 1} stars today</span>
            </article>
            """
        )
    html = "<html><body>" + "\n".join(cards) + "</body></html>"

    async def fake_get(self, url, *args, **kwargs):
        if str(url) == "https://github.com/trending":
            return DummyResponse(200, text=html)
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = GitHubTrendingCollector()
    items = await collector.collect({"since": "daily", "limit": 10, "include_readme": False, "include_repo_tree": False})

    assert len(items) == 10
    assert items[0].metadata["repo_full_name"] == "owner0/repo0"
    assert items[0].metadata["stars_today"] == 1


@pytest.mark.asyncio
async def test_fetches_repo_readme_and_tree_index(monkeypatch: pytest.MonkeyPatch) -> None:
    trending_html = """
    <html><body>
      <article class=\"Box-row\">
        <h2><a href=\"/openai/example\"> openai / example </a></h2>
        <p>Project desc</p>
        <span itemprop=\"programmingLanguage\">Python</span>
        <span>99 stars today</span>
      </article>
    </body></html>
    """

    async def fake_get(self, url, *args, **kwargs):
        key = str(url)
        if key == "https://github.com/trending":
            return DummyResponse(200, text=trending_html)
        if key == "https://api.github.com/repos/openai/example":
            return DummyResponse(200, json_data={"stargazers_count": 1234, "default_branch": "main", "description": "Project desc"})
        if key == "https://api.github.com/repos/openai/example/readme":
            return DummyResponse(200, text="# README\n\nhello world")
        if key == "https://api.github.com/repos/openai/example/git/trees/main":
            return DummyResponse(200, json_data={"tree": [{"path": "README.md"}, {"path": "src/app.py"}]})
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = GitHubTrendingCollector()
    items = await collector.collect({"limit": 1, "include_readme": True, "include_repo_tree": True})

    assert len(items) == 1
    assert "README" in (items[0].content or "")
    assert items[0].metadata.get("repo_tree") == ["README.md", "src/app.py"]
    assert items[0].metadata.get("stars_total") == 1234
