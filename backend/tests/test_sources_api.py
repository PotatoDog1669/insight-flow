from datetime import datetime, timedelta, timezone
import uuid
from urllib.parse import parse_qs, urlparse

from app.collectors.base import RawArticle
from app.api.v1.sources import _to_source_response
from app.collectors.blog_scraper import _resolve_profile
from app.models.source import Source
from app.schemas.monitor import MonitorResponse
from app.schemas.report import ReportResponse


def test_to_source_response_resolves_target_url_from_site_key_profile() -> None:
    now = datetime.now(timezone.utc)
    source = Source(
        id=uuid.uuid4(),
        name="Anthropic",
        category="blog",
        collect_method="blog_scraper",
        config={"site_key": "anthropic", "max_items": 20},
        enabled=True,
        created_at=now,
        updated_at=now,
    )

    response = _to_source_response(source, None)

    assert str(response.target_url) == "https://anthropic.com/news"


def test_resolve_profile_merges_partial_inline_profile_with_site_key_profile() -> None:
    profile = _resolve_profile(
        {
            "site_key": "anthropic",
            "profile": {
                "start_urls": ["https://anthropic.com/custom-news"],
                "normalization": {"url_prefix": "https://anthropic.com"},
            },
        }
    )

    assert profile["start_urls"] == ["https://anthropic.com/custom-news"]
    assert profile["list_page"]["item_selector"] == "a[href*='/news/']"
    assert profile["detail_page"]["content_selector"]


def test_test_source_applies_arxiv_test_only_keywords_and_window(client, monkeypatch) -> None:
    collected_configs: list[dict] = []
    now = datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc)

    class StubCollector:
        async def collect(self, config: dict) -> list[RawArticle]:
            collected_configs.append(dict(config))
            limit = int(config.get("max_items", 30))
            articles: list[RawArticle] = []
            for index in range(limit):
                articles.append(
                    RawArticle(
                        external_id=f"inside-{index}",
                        title=f"Inside Window {index}",
                        url=f"https://arxiv.org/abs/inside-{index}",
                        published_at=now - timedelta(days=2),
                    )
                )
            articles.append(
                RawArticle(
                    external_id="outside",
                    title="Outside Window",
                    url="https://arxiv.org/abs/outside",
                    published_at=now - timedelta(days=20),
                )
            )
            return articles

    monkeypatch.setattr("app.api.v1.sources.get_collector", lambda _: StubCollector())

    create_resp = client.post(
        "/api/v1/sources",
        json={
            "name": "arXiv",
            "category": "academic",
            "collect_method": "rss",
            "config": {
                "arxiv_api": True,
                "feed_url": "https://export.arxiv.org/api/query",
                "keywords": ["reasoning"],
                "categories": ["cs.AI"],
            },
            "enabled": True,
        },
    )
    assert create_resp.status_code == 201
    source_id = create_resp.json()["id"]

    response = client.post(
        f"/api/v1/sources/{source_id}/test",
        json={
            "keywords": ["agent", "multimodal"],
            "max_results": 4,
            "start_at": "2026-03-01T00:00:00Z",
            "end_at": "2026-03-17T23:59:59Z",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["fetched_count"] == 5
    assert payload["matched_count"] == 4
    assert payload["effective_keywords"] == ["agent", "multimodal"]
    assert payload["effective_max_results"] == 4
    assert payload["window_start"] == "2026-03-01T00:00:00Z"
    assert payload["window_end"] == "2026-03-17T23:59:59Z"
    assert [item["title"] for item in payload["sample_articles"]] == [
        "Inside Window 0",
        "Inside Window 1",
        "Inside Window 2",
        "Inside Window 3",
    ]
    assert collected_configs[0]["keywords"] == ["agent", "multimodal"]
    assert collected_configs[0]["max_results"] == 4
    assert collected_configs[0]["max_items"] == 4


def test_test_source_applies_academic_api_test_window_keywords_and_limit(client, monkeypatch) -> None:
    collected_configs: list[dict] = []
    now = datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc)

    class StubCollector:
        async def collect(self, config: dict) -> list[RawArticle]:
            collected_configs.append(dict(config))
            return [
                RawArticle(
                    external_id="inside-1",
                    title="Inside Window 1",
                    url="https://api.openalex.org/W1",
                    published_at=now - timedelta(days=2),
                ),
                RawArticle(
                    external_id="inside-2",
                    title="Inside Window 2",
                    url="https://api.openalex.org/W2",
                    published_at=now - timedelta(days=4),
                ),
                RawArticle(
                    external_id="outside",
                    title="Outside Window",
                    url="https://api.openalex.org/W3",
                    published_at=now - timedelta(days=40),
                ),
            ]

    monkeypatch.setattr("app.api.v1.sources.get_collector", lambda _: StubCollector())

    create_resp = client.post(
        "/api/v1/sources",
        json={
            "name": "OpenAlex",
            "category": "academic",
            "collect_method": "openalex",
            "config": {
                "base_url": "https://api.openalex.org/works",
                "keywords": ["reasoning"],
                "max_results": 20,
                "api_key": "",
                "mailto": "research@example.com",
                "supports_time_window": True,
            },
            "enabled": True,
        },
    )
    assert create_resp.status_code == 201
    source_id = create_resp.json()["id"]

    response = client.post(
        f"/api/v1/sources/{source_id}/test",
        json={
            "keywords": ["agent", "multimodal"],
            "max_results": 2,
            "start_at": "2026-03-01T00:00:00Z",
            "end_at": "2026-03-17T23:59:59Z",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["fetched_count"] == 3
    assert payload["matched_count"] == 2
    assert payload["effective_keywords"] == ["agent", "multimodal"]
    assert payload["effective_max_results"] == 2
    assert payload["window_start"] == "2026-03-01T00:00:00Z"
    assert payload["window_end"] == "2026-03-17T23:59:59Z"
    assert [item["title"] for item in payload["sample_articles"]] == [
        "Inside Window 1",
        "Inside Window 2",
    ]
    assert collected_configs[0]["keywords"] == ["agent", "multimodal"]
    assert collected_configs[0]["max_results"] == 2
    assert collected_configs[0]["start_at"] == "2026-03-01T00:00:00+00:00"
    assert collected_configs[0]["end_at"] == "2026-03-17T23:59:59+00:00"


def test_test_source_keeps_generic_connectivity_flow_for_non_arxiv_sources(client, monkeypatch) -> None:
    class StubCollector:
        async def collect(self, config: dict) -> list[RawArticle]:
            return [
                RawArticle(
                    external_id="item-1",
                    title="Generic Item",
                    url="https://example.com/item-1",
                )
            ]

    monkeypatch.setattr("app.api.v1.sources.get_collector", lambda _: StubCollector())

    response = client.post(
        "/api/v1/sources/11111111-1111-1111-1111-111111111111/test",
        json={
            "keywords": ["should", "be", "ignored"],
            "start_at": "2026-03-01T00:00:00Z",
            "end_at": "2026-03-17T23:59:59Z",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "Connection successful. Retrieved 1 items."
    assert payload["sample_articles"][0]["title"] == "Generic Item"


def test_paper_report_type_is_accepted_in_response_shapes() -> None:
    now = datetime.now(timezone.utc)

    monitor = MonitorResponse(
        id=uuid.uuid4(),
        name="Paper Monitor",
        time_period="daily",
        report_type="paper",
        source_ids=[],
        source_overrides={},
        destination_ids=[],
        window_hours=24,
        enabled=True,
        status="active",
        last_run=None,
        created_at=now,
        updated_at=now,
    )
    report = ReportResponse(
        id=uuid.uuid4(),
        user_id=None,
        monitor_id=None,
        monitor_name="Paper Monitor",
        time_period="daily",
        report_type="paper",
        title="Paper Digest",
        report_date=now.date(),
        created_at=now,
    )

    assert monitor.report_type == "paper"
    assert report.report_type == "paper"


def test_test_source_builds_reddit_feed_url_from_subreddits(client, monkeypatch) -> None:
    collected_configs: list[dict] = []

    class StubCollector:
        async def collect(self, config: dict) -> list[RawArticle]:
            collected_configs.append(dict(config))
            return [
                RawArticle(
                    external_id="reddit-1",
                    title="Reddit Item",
                    url="https://www.reddit.com/r/LocalLLaMA/comments/example",
                )
            ]

    monkeypatch.setattr("app.api.v1.sources.get_collector", lambda _: StubCollector())

    create_resp = client.post(
        "/api/v1/sources",
        json={
            "name": "Reddit",
            "category": "social",
            "collect_method": "rss",
            "config": {
                "subreddits": ["r/LocalLLaMA", "OpenAI", "openai", "MachineLearning"],
                "max_items": 10,
                "fetch_detail": False,
            },
            "enabled": True,
        },
    )
    assert create_resp.status_code == 201
    source_id = create_resp.json()["id"]

    response = client.post(f"/api/v1/sources/{source_id}/test", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(collected_configs) == 1
    assert collected_configs[0]["subreddits"] == ["LocalLLaMA", "OpenAI", "MachineLearning"]
    parsed = urlparse(collected_configs[0]["feed_url"])
    params = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "www.reddit.com"
    assert parsed.path == "/search.rss"
    assert params["sort"][0] == "new"
    assert params["q"][0] == "subreddit:LocalLLaMA OR subreddit:OpenAI OR subreddit:MachineLearning"


def test_test_source_disables_rss_detail_fetch_for_connectivity_checks(client, monkeypatch) -> None:
    collected_configs: list[dict] = []

    class StubCollector:
        async def collect(self, config: dict) -> list[RawArticle]:
            collected_configs.append(dict(config))
            return [
                RawArticle(
                    external_id="item-1",
                    title="Feed Item",
                    url="https://example.com/item-1",
                )
            ]

    monkeypatch.setattr("app.api.v1.sources.get_collector", lambda _: StubCollector())

    create_resp = client.post(
        "/api/v1/sources",
        json={
            "name": "Qwen",
            "category": "blog",
            "collect_method": "rss",
            "config": {
                "feed_url": "https://qwenlm.github.io/blog/index.xml",
                "max_items": 30,
                "fetch_detail": True,
                "reader_mode": "prefer",
                "reader_fallback_enabled": True,
            },
            "enabled": True,
        },
    )
    assert create_resp.status_code == 201
    source_id = create_resp.json()["id"]

    response = client.post(f"/api/v1/sources/{source_id}/test", json={})

    assert response.status_code == 200
    assert collected_configs[0]["fetch_detail"] is False
