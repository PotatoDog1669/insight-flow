from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.collectors.twitter_snaplytics import TwitterSnaplyticsCollector


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
async def test_collect_fetches_challenge_and_maps_tweets(monkeypatch: pytest.MonkeyPatch) -> None:
    base_url = "https://twittermedia.b-cdn.net"
    challenge_url = f"{base_url}/challenge/"
    viewer_url = f"{base_url}/viewer/"
    ts = 1772531949
    rand = "JxvJD15o6Zc"
    challenge_id = "bz8ipEGToSDQSLr1YRqDDQ"
    expected_solution = sha256(f"{ts}{rand}".encode()).hexdigest()[:8]
    seen_headers: list[dict] = []
    seen_urls: list[str] = []

    async def fake_get(self, url, *args, **kwargs):
        raw_url = str(url)
        seen_urls.append(raw_url)
        headers = kwargs.get("headers") or {}
        seen_headers.append(headers)
        params = kwargs.get("params") or {}
        parsed = urlparse(raw_url)
        qs = parse_qs(parsed.query)
        if "cursor" in params:
            qs["cursor"] = [str(params["cursor"])]

        if raw_url == challenge_url:
            return DummyResponse(
                200,
                json_data={
                    "challenge_id": challenge_id,
                    "timestamp": ts,
                    "random_value": rand,
                },
            )
        if raw_url.startswith(viewer_url) and qs.get("cursor") == ["cursor-1"]:
            return DummyResponse(
                200,
                json_data={
                    "profile": {"username": "OpenAI"},
                    "tweets": [
                        {
                            "id": "3",
                            "text": "third tweet",
                            "created_at": "Sat Mar 01 00:00:00 +0000 2026",
                            "author": {"username": "OpenAI", "name": "OpenAI"},
                            "stats": {"likes": 3, "retweets": 2, "replies": 1, "views": 100},
                            "is_retweet": False,
                            "is_pinned": False,
                        }
                    ],
                    "cursor": None,
                },
            )
        if raw_url.startswith(viewer_url):
            return DummyResponse(
                200,
                json_data={
                    "profile": {"username": "OpenAI"},
                    "tweets": [
                        {
                            "id": "1",
                            "text": "first tweet",
                            "created_at": "Mon Mar 03 10:00:00 +0000 2026",
                            "author": {"username": "OpenAI", "name": "OpenAI"},
                            "stats": {"likes": 10, "retweets": 2, "replies": 1, "views": 1000},
                            "is_retweet": False,
                            "is_pinned": True,
                        },
                        {
                            "id": "2",
                            "text": "second tweet",
                            "created_at": "Sun Mar 02 09:00:00 +0000 2026",
                            "author": {"username": "OpenAI", "name": "OpenAI"},
                            "stats": {"likes": 9, "retweets": 1, "replies": 1, "views": 900},
                            "is_retweet": False,
                            "is_pinned": False,
                        },
                    ],
                    "cursor": "cursor-1",
                },
            )
        raise AssertionError(f"Unexpected URL: {raw_url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = TwitterSnaplyticsCollector()
    items = await collector.collect({"username": "openai", "max_items": 10, "max_pages": 3})

    assert len(items) == 3
    assert items[0].external_id == "1"
    assert items[0].url == "https://x.com/OpenAI/status/1"
    assert items[0].metadata["collector"] == "twitter_snaplytics"
    assert items[0].metadata["is_pinned"] is True
    assert items[0].metadata["is_retweet"] is False
    assert items[0].metadata["stats"]["likes"] == 10
    assert isinstance(items[0].published_at, datetime)
    assert items[0].published_at.tzinfo is not None

    challenge_headers = seen_headers[0]
    assert challenge_headers.get("Referer") == "https://snaplytics.io/twitter-viewer/"
    assert challenge_headers.get("Origin") == "https://snaplytics.io"

    viewer_headers = seen_headers[1]
    assert viewer_headers.get("X-Challenge-ID") == challenge_id
    assert viewer_headers.get("X-Challenge-Solution") == expected_solution

    assert seen_urls[0] == challenge_url
    assert seen_urls[1].startswith(viewer_url)


@pytest.mark.asyncio
async def test_collect_respects_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(self, url, *args, **kwargs):
        raw = str(url)
        if raw.endswith("/challenge/"):
            return DummyResponse(
                200,
                json_data={"challenge_id": "id", "timestamp": 1700000000, "random_value": "abc"},
            )
        if "/viewer/" in raw:
            return DummyResponse(
                200,
                json_data={
                    "profile": {"username": "OpenAI"},
                    "tweets": [
                        {
                            "id": "pinned",
                            "text": "pinned",
                            "created_at": "Mon Mar 03 10:00:00 +0000 2026",
                            "author": {"username": "OpenAI", "name": "OpenAI"},
                            "stats": {"likes": 1, "retweets": 1, "replies": 1},
                            "is_retweet": False,
                            "is_pinned": True,
                        },
                        {
                            "id": "retweet",
                            "text": "rt",
                            "created_at": "Mon Mar 03 09:00:00 +0000 2026",
                            "author": {"username": "OpenAIDevs", "name": "OpenAI Devs"},
                            "stats": {"likes": 1, "retweets": 1, "replies": 1},
                            "is_retweet": True,
                            "is_pinned": False,
                        },
                        {
                            "id": "normal",
                            "text": "normal",
                            "created_at": "Mon Mar 03 08:00:00 +0000 2026",
                            "author": {"username": "OpenAI", "name": "OpenAI"},
                            "stats": {"likes": 1, "retweets": 1, "replies": 1},
                            "is_retweet": False,
                            "is_pinned": False,
                        },
                    ],
                    "cursor": None,
                },
            )
        raise AssertionError(f"Unexpected URL: {raw}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = TwitterSnaplyticsCollector()
    items = await collector.collect(
        {
            "username": "openai",
            "include_pinned": False,
            "include_retweets": False,
        }
    )

    assert [item.external_id for item in items] == ["normal"]


@pytest.mark.asyncio
async def test_collect_applies_time_window(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(self, url, *args, **kwargs):
        raw = str(url)
        if raw.endswith("/challenge/"):
            return DummyResponse(
                200,
                json_data={"challenge_id": "id", "timestamp": 1700000000, "random_value": "abc"},
            )
        if "/viewer/" in raw:
            return DummyResponse(
                200,
                json_data={
                    "profile": {"username": "OpenAI"},
                    "tweets": [
                        {
                            "id": "in",
                            "text": "in",
                            "created_at": "Sat Feb 28 20:39:00 +0000 2026",
                            "author": {"username": "OpenAI", "name": "OpenAI"},
                            "stats": {"likes": 1, "retweets": 1, "replies": 1},
                            "is_retweet": False,
                            "is_pinned": False,
                        },
                        {
                            "id": "out",
                            "text": "out",
                            "created_at": "Mon Feb 09 00:03:38 +0000 2026",
                            "author": {"username": "OpenAI", "name": "OpenAI"},
                            "stats": {"likes": 1, "retweets": 1, "replies": 1},
                            "is_retweet": False,
                            "is_pinned": False,
                        },
                    ],
                    "cursor": None,
                },
            )
        raise AssertionError(f"Unexpected URL: {raw}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = TwitterSnaplyticsCollector()
    items = await collector.collect(
        {
            "username": "openai",
            "since": "2026-03-01T00:00:00+08:00",
            "until": "2026-03-04T00:00:00+08:00",
        }
    )

    assert [item.external_id for item in items] == ["in"]


@pytest.mark.asyncio
async def test_collect_raises_when_challenge_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(self, url, *args, **kwargs):
        raw = str(url)
        if raw.endswith("/challenge/"):
            return DummyResponse(403, text="<html>forbidden</html>", json_data={"detail": "forbidden"})
        raise AssertionError(f"Unexpected URL: {raw}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = TwitterSnaplyticsCollector()
    with pytest.raises(RuntimeError, match="challenge"):
        await collector.collect({"username": "openai"})


@pytest.mark.asyncio
async def test_collect_requires_username() -> None:
    collector = TwitterSnaplyticsCollector()
    with pytest.raises(ValueError, match="username"):
        await collector.collect({})


@pytest.mark.asyncio
async def test_collect_supports_usernames_list_and_merges_results(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get(self, url, *args, **kwargs):
        raw = str(url)
        params = kwargs.get("params") or {}
        username = str(params.get("data") or "")
        if raw.endswith("/challenge/"):
            return DummyResponse(
                200,
                json_data={"challenge_id": "id", "timestamp": 1700000000, "random_value": "abc"},
            )
        if "/viewer/" in raw and username.lower() == "openai":
            return DummyResponse(
                200,
                json_data={
                    "profile": {"username": "OpenAI"},
                    "tweets": [
                        {
                            "id": "o1",
                            "text": "openai tweet",
                            "created_at": "Mon Mar 03 10:00:00 +0000 2026",
                            "author": {"username": "OpenAI", "name": "OpenAI"},
                            "stats": {"likes": 3, "retweets": 2, "replies": 1},
                            "is_retweet": False,
                            "is_pinned": False,
                        }
                    ],
                    "cursor": None,
                },
            )
        if "/viewer/" in raw and username.lower() == "anthropicai":
            return DummyResponse(
                200,
                json_data={
                    "profile": {"username": "AnthropicAI"},
                    "tweets": [
                        {
                            "id": "a1",
                            "text": "anthropic tweet",
                            "created_at": "Mon Mar 03 11:00:00 +0000 2026",
                            "author": {"username": "AnthropicAI", "name": "Anthropic"},
                            "stats": {"likes": 3, "retweets": 2, "replies": 1},
                            "is_retweet": False,
                            "is_pinned": False,
                        }
                    ],
                    "cursor": None,
                },
            )
        raise AssertionError(f"Unexpected URL: {raw} params={params}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = TwitterSnaplyticsCollector()
    items = await collector.collect({"usernames": ["openai", "anthropicai"], "max_items": 10})

    assert [item.external_id for item in items] == ["a1", "o1"]
    assert items[0].metadata["author_username"] == "AnthropicAI"
    assert items[1].metadata["author_username"] == "OpenAI"


@pytest.mark.asyncio
async def test_collect_defaults_to_five_items_per_username(monkeypatch: pytest.MonkeyPatch) -> None:
    def _tweet(tweet_id: str, hour: int, username: str) -> dict:
        return {
            "id": tweet_id,
            "text": f"{username} tweet {tweet_id}",
            "created_at": f"Mon Mar 03 {hour:02d}:00:00 +0000 2026",
            "author": {"username": username, "name": username},
            "stats": {"likes": 3, "retweets": 2, "replies": 1},
            "is_retweet": False,
            "is_pinned": False,
        }

    async def fake_get(self, url, *args, **kwargs):
        raw = str(url)
        params = kwargs.get("params") or {}
        username = str(params.get("data") or "")
        if raw.endswith("/challenge/"):
            return DummyResponse(
                200,
                json_data={"challenge_id": "id", "timestamp": 1700000000, "random_value": "abc"},
            )
        if "/viewer/" in raw and username.lower() == "openai":
            return DummyResponse(
                200,
                json_data={
                    "profile": {"username": "OpenAI"},
                    "tweets": [_tweet(f"o{i}", 20 - i, "OpenAI") for i in range(6)],
                    "cursor": None,
                },
            )
        if "/viewer/" in raw and username.lower() == "anthropicai":
            return DummyResponse(
                200,
                json_data={
                    "profile": {"username": "AnthropicAI"},
                    "tweets": [_tweet(f"a{i}", 10 - i, "AnthropicAI") for i in range(6)],
                    "cursor": None,
                },
            )
        raise AssertionError(f"Unexpected URL: {raw} params={params}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = TwitterSnaplyticsCollector()
    items = await collector.collect({"usernames": ["openai", "anthropicai"], "max_items": 5})

    assert len(items) == 10
    assert sum(1 for item in items if item.metadata["author_username"] == "OpenAI") == 5
    assert sum(1 for item in items if item.metadata["author_username"] == "AnthropicAI") == 5


def test_resolve_usernames_handles_single_or_list() -> None:
    resolved_from_single = TwitterSnaplyticsCollector._resolve_usernames({"username": "@OpenAI"})
    resolved_from_list = TwitterSnaplyticsCollector._resolve_usernames({"usernames": ["@OpenAI", "https://x.com/AnthropicAI"]})

    assert resolved_from_single == ["OpenAI"]
    assert resolved_from_list == ["OpenAI", "AnthropicAI"]


def test_parse_twitter_datetime_returns_aware_time() -> None:
    dt = TwitterSnaplyticsCollector._parse_twitter_datetime("Mon Mar 03 10:00:00 +0000 2026")
    assert dt == datetime(2026, 3, 3, 10, 0, 0, tzinfo=UTC)
