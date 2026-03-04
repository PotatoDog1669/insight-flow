"""Twitter/X collector via Snaplytics viewer backend."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse

import httpx

from app.collectors.base import BaseCollector, RawArticle
from app.collectors.registry import register


@register("twitter_snaplytics")
class TwitterSnaplyticsCollector(BaseCollector):
    """Collect public X/Twitter posts from Snaplytics viewer backend."""

    @property
    def name(self) -> str:
        return "Twitter Snaplytics"

    @property
    def category(self) -> str:
        return "social"

    async def collect(self, config: dict) -> list[RawArticle]:
        usernames = self._resolve_usernames(config)
        max_items = max(1, int(config.get("max_items", 30)))
        per_username_max_items = max(1, int(config.get("per_username_max_items", max_items)))
        max_pages = max(1, int(config.get("max_pages", 1)))
        include_retweets = bool(config.get("include_retweets", True))
        include_pinned = bool(config.get("include_pinned", True))
        timeout_seconds = float(config.get("timeout_seconds", 20))
        base_url = str(config.get("api_base_url", "https://twittermedia.b-cdn.net")).strip().rstrip("/")
        referer = str(config.get("referer", "https://snaplytics.io/twitter-viewer/")).strip()
        origin = str(config.get("origin", "https://snaplytics.io")).strip()
        user_agent = str(
            config.get(
                "user_agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            )
        ).strip()
        since = self._parse_iso_datetime(config.get("since"))
        until = self._parse_iso_datetime(config.get("until"))

        common_headers = {
            "User-Agent": user_agent,
            "Referer": referer,
            "Origin": origin,
            "Accept": "application/json, text/plain, */*",
        }

        results: list[RawArticle] = []
        seen_ids: set[str] = set()

        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            for username in usernames:
                user_articles = await self._collect_single_username(
                    client=client,
                    base_url=base_url,
                    username=username,
                    headers=common_headers,
                    max_pages=max_pages,
                    max_items=per_username_max_items,
                    include_retweets=include_retweets,
                    include_pinned=include_pinned,
                    since=since,
                    until=until,
                )
                for article in user_articles:
                    if article.external_id in seen_ids:
                        continue
                    seen_ids.add(article.external_id)
                    results.append(article)
        results.sort(key=lambda item: item.published_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return results[:max_items]

    @staticmethod
    def _resolve_username(value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            raise ValueError("twitter_snaplytics collector requires `username`")

        if raw.startswith("@"):
            raw = raw[1:]

        if raw.startswith("http://") or raw.startswith("https://"):
            parsed = urlparse(raw)
            path = (parsed.path or "").strip("/")
            segment = path.split("/", 1)[0] if path else ""
            raw = segment

        raw = raw.strip()
        if not raw or "/" in raw or " " in raw:
            raise ValueError(f"Invalid twitter username: {value}")
        return raw

    @classmethod
    def _resolve_usernames(cls, config: dict) -> list[str]:
        raw_candidates: list[Any] = []
        if config.get("username") is not None:
            raw_candidates.append(config.get("username"))
        if config.get("handle") is not None:
            raw_candidates.append(config.get("handle"))

        usernames_payload = config.get("usernames")
        if isinstance(usernames_payload, str):
            raw_candidates.extend([part for part in usernames_payload.replace("\n", ",").split(",") if part.strip()])
        elif isinstance(usernames_payload, (list, tuple, set)):
            raw_candidates.extend(list(usernames_payload))

        resolved: list[str] = []
        seen: set[str] = set()
        for candidate in raw_candidates:
            username = cls._resolve_username(candidate)
            key = username.lower()
            if key in seen:
                continue
            seen.add(key)
            resolved.append(username)

        if not resolved:
            raise ValueError("twitter_snaplytics collector requires `username` or `usernames`")
        return resolved

    async def _collect_single_username(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        username: str,
        headers: dict[str, str],
        max_pages: int,
        max_items: int,
        include_retweets: bool,
        include_pinned: bool,
        since: datetime | None,
        until: datetime | None,
    ) -> list[RawArticle]:
        results: list[RawArticle] = []
        cursor: str | None = None
        profile_username: str | None = None

        for _ in range(max_pages):
            challenge = await self._solve_challenge(client=client, base_url=base_url, headers=headers)
            page = await self._fetch_viewer_page(
                client=client,
                base_url=base_url,
                username=username,
                cursor=cursor,
                headers={
                    **headers,
                    "Content-Type": "application/json",
                    "X-Challenge-ID": challenge["challenge_id"],
                    "X-Challenge-Solution": challenge["solution"],
                },
            )
            if not profile_username:
                profile = page.get("profile")
                if isinstance(profile, dict):
                    raw_profile_username = profile.get("username")
                    if raw_profile_username:
                        profile_username = str(raw_profile_username)

            tweets = page.get("tweets")
            if not isinstance(tweets, list) or not tweets:
                break

            for tweet in tweets:
                article = self._tweet_to_raw_article(
                    tweet=tweet,
                    query_username=username,
                    profile_username=profile_username,
                    include_retweets=include_retweets,
                    include_pinned=include_pinned,
                    since=since,
                    until=until,
                )
                if article is None:
                    continue
                results.append(article)
                if len(results) >= max_items:
                    return results

            next_cursor = page.get("cursor")
            cursor = str(next_cursor) if next_cursor else None
            if not cursor:
                break

        return results

    @staticmethod
    def _parse_iso_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        normalized = raw.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    @staticmethod
    def _parse_twitter_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        return datetime.strptime(raw, "%a %b %d %H:%M:%S %z %Y")

    @staticmethod
    async def _solve_challenge(*, client: httpx.AsyncClient, base_url: str, headers: dict[str, str]) -> dict[str, str]:
        url = f"{base_url}/challenge/"
        response = await client.get(url, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"twitter_snaplytics challenge failed: status={response.status_code}")
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError("twitter_snaplytics challenge failed: invalid json response") from exc
        challenge_id = payload.get("challenge_id")
        timestamp = payload.get("timestamp")
        random_value = payload.get("random_value")
        if not challenge_id or timestamp is None or random_value is None:
            raise RuntimeError("twitter_snaplytics challenge failed: missing fields")
        solution = sha256(f"{timestamp}{random_value}".encode()).hexdigest()[:8]
        return {"challenge_id": str(challenge_id), "solution": solution}

    @staticmethod
    async def _fetch_viewer_page(
        *,
        client: httpx.AsyncClient,
        base_url: str,
        username: str,
        cursor: str | None,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        params = {"data": username, "type": "profile"}
        if cursor:
            params["cursor"] = cursor
        response = await client.get(f"{base_url}/viewer/", params=params, headers=headers)
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError(
                f"twitter_snaplytics viewer failed: status={response.status_code}, detail=invalid_json"
            ) from exc
        if response.status_code >= 400:
            detail = payload.get("detail") if isinstance(payload, dict) else None
            raise RuntimeError(
                f"twitter_snaplytics viewer failed: status={response.status_code}, detail={detail or 'unknown'}"
            )
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def _tweet_to_raw_article(
        cls,
        *,
        tweet: Any,
        query_username: str,
        profile_username: str | None,
        include_retweets: bool,
        include_pinned: bool,
        since: datetime | None,
        until: datetime | None,
    ) -> RawArticle | None:
        if not isinstance(tweet, dict):
            return None

        tweet_id = str(tweet.get("id") or "").strip()
        if not tweet_id:
            return None

        is_retweet = bool(tweet.get("is_retweet"))
        is_pinned = bool(tweet.get("is_pinned"))
        if is_retweet and not include_retweets:
            return None
        if is_pinned and not include_pinned:
            return None

        published_at = cls._parse_twitter_datetime(tweet.get("created_at"))
        if published_at is None:
            return None
        if since and published_at < since:
            return None
        if until and published_at > until:
            return None

        author = tweet.get("author") if isinstance(tweet.get("author"), dict) else {}
        author_username = str(author.get("username") or profile_username or query_username)
        author_name = str(author.get("name") or "")
        text = str(tweet.get("text") or "").strip()

        title_source = text.splitlines()[0].strip() if text else f"Tweet {tweet_id}"
        title = title_source if len(title_source) <= 120 else title_source[:117] + "..."
        url = f"https://x.com/{author_username}/status/{tweet_id}"
        stats = tweet.get("stats") if isinstance(tweet.get("stats"), dict) else {}

        return RawArticle(
            external_id=tweet_id,
            title=title,
            url=url,
            content=text or None,
            published_at=published_at,
            metadata={
                "collector": "twitter_snaplytics",
                "query_username": query_username,
                "author_username": author_username,
                "author_name": author_name,
                "is_retweet": is_retweet,
                "is_pinned": is_pinned,
                "stats": {
                    "likes": stats.get("likes"),
                    "retweets": stats.get("retweets"),
                    "replies": stats.get("replies"),
                    "views": stats.get("views"),
                },
                "fetched_at": datetime.now(UTC).isoformat(),
            },
        )
