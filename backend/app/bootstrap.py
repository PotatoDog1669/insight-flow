"""Runtime bootstrap: sync source presets into database."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import structlog
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.reddit_config import merge_reddit_subreddits
from app.models.database import async_session
from app.models.source import Source
from app.models.subscription import UserSubscription
from app.models.user import User

logger = structlog.get_logger()

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
PRESETS_PATH = Path(__file__).resolve().parent / "collectors" / "source_presets.yaml"
SITE_PROFILE_DIR = Path(__file__).resolve().parent / "collectors" / "site_profiles"
VALID_SOURCE_CATEGORIES = {"open_source", "blog", "academic", "social"}


def _source_uuid(key: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"lexdeepresearch:source:{key}")


def _infer_collect_method(preset: dict) -> tuple[str, dict]:
    rss_url = preset.get("rss_url")
    collect_config = preset.get("collect_config")
    strategy = str(preset.get("strategy", ""))
    key = str(preset.get("key") or "custom_site")
    urls = preset.get("urls") or []
    primary_url = urls[0] if urls else None
    github_urls = [url for url in urls if isinstance(url, str) and "github.com" in url]

    if strategy in {"openalex_api", "europe_pmc_api", "pubmed_api"}:
        collector_name = strategy.replace("_api", "")
        config: dict = dict(collect_config) if isinstance(collect_config, dict) else {}
        if primary_url and not isinstance(config.get("base_url"), str):
            config["base_url"] = primary_url
        return collector_name, config

    if rss_url:
        config: dict = {"feed_url": rss_url, "max_items": 30}
        if isinstance(collect_config, dict):
            config.update(collect_config)
        if bool(preset.get("require_browser")):
            config["require_browser"] = True
        return "rss", config

    if strategy in {"twitter_snaplytics", "twitter_snaplytics_profile"}:
        config: dict = {"max_items": 30}
        if isinstance(collect_config, dict):
            config.update(collect_config)
        username = str(config.get("username") or "").strip()
        if not username:
            username = _infer_twitter_username_from_urls(urls)
        if username:
            config["username"] = username
        return "twitter_snaplytics", config

    if strategy == "github_only":
        return "github_trending", {"since": "daily", "limit": 10, "include_readme": True, "include_repo_tree": True}

    config: dict = {
        "site_key": key,
        "max_items": 20,
        "fallback_chain": ["blog_scraper", "deepbrowse"],
    }
    if github_urls:
        config["github_repo_urls"] = github_urls
    if strategy in {"github_plus_docs", "github_plus_site_scraper"}:
        config["fallback_chain"] = ["blog_scraper", "github_trending", "deepbrowse"]

    profile_path = SITE_PROFILE_DIR / f"{key}.yaml"
    if not profile_path.exists():
        # 兜底：内联最小 profile，避免因为 profile 文件缺失导致启动不可用。
        config["profile"] = {
            "site_key": key,
            "start_urls": [primary_url] if primary_url else [],
            "list_page": {"item_selector": "a[href]", "url_attr": "href"},
            "detail_page": {
                "content_selector": "article, main, body",
                "remove_selectors": ["script", "style", "nav"],
            },
            "normalization": {
                "url_prefix": _origin(primary_url) if primary_url else "",
                "min_content_chars": 200,
            },
        }
    return "blog_scraper", config


def _infer_twitter_username_from_urls(urls: list) -> str:
    for raw_url in urls:
        if not isinstance(raw_url, str):
            continue
        parsed = urlparse(raw_url)
        host = parsed.netloc.lower()
        if not host:
            continue
        if host.startswith("www."):
            host = host[4:]
        if host not in {"x.com", "twitter.com"}:
            continue
        path = (parsed.path or "").strip("/")
        if not path:
            continue
        username = path.split("/", 1)[0].strip()
        if username and username.lower() not in {"home", "explore", "search"}:
            return username
    return ""


def _origin(url: str | None) -> str:
    if not url:
        return ""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return ""


def _merge_twitter_usernames(existing_config: dict | None, synced_config: dict) -> dict:
    if not isinstance(synced_config, dict):
        return {}

    merged = dict(synced_config)
    raw_candidates: list[str] = []
    for config in (existing_config or {}, synced_config):
        if not isinstance(config, dict):
            continue
        for key in ("username", "handle"):
            value = str(config.get(key) or "").strip()
            if value:
                raw_candidates.append(value)
        usernames = config.get("usernames")
        if isinstance(usernames, str):
            raw_candidates.extend([part.strip() for part in usernames.replace("\n", ",").split(",") if part.strip()])
        elif isinstance(usernames, (list, tuple, set)):
            raw_candidates.extend([str(item).strip() for item in usernames if str(item).strip()])

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in raw_candidates:
        normalized = candidate.lstrip("@").strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)

    if deduped:
        merged["usernames"] = deduped
        merged.pop("username", None)
        merged.pop("handle", None)
    return merged


def _merge_reddit_subreddits(existing_config: dict | None, synced_config: dict) -> dict:
    if not isinstance(synced_config, dict):
        return {}

    merged = dict(synced_config)
    merged_subreddits = merge_reddit_subreddits(
        (existing_config or {}).get("subreddits") if isinstance(existing_config, dict) else None,
        synced_config.get("subreddits"),
    )
    if merged_subreddits:
        merged["subreddits"] = merged_subreddits
    return merged


async def seed_initial_data(db: AsyncSession) -> None:
    now = datetime.now(UTC)

    # Backward compatibility: DeepSeek was previously hardcoded as open_source.
    deepseek = await db.get(Source, _source_uuid("deepseek"))
    if deepseek and deepseek.category == "open_source":
        deepseek.category = "blog"
        deepseek.updated_at = now
        db.add(deepseek)
        await db.commit()

    user = await db.get(User, DEFAULT_USER_ID)
    if user is None:
        user = User(
            id=DEFAULT_USER_ID,
            email="admin@lexmount.com",
            name="Lex Researcher",
            settings={"default_time_period": "daily", "default_report_type": "daily", "default_sink": "database"},
            created_at=now,
            updated_at=now,
        )
        db.add(user)

    presets_payload = yaml.safe_load(PRESETS_PATH.read_text(encoding="utf-8")) if PRESETS_PATH.exists() else {}
    preset_sources = presets_payload.get("sources", []) if isinstance(presets_payload, dict) else []

    synced_source_ids: list[uuid.UUID] = []

    for preset in preset_sources:
        if not isinstance(preset, dict):
            continue

        key = str(preset.get("key") or "")
        if not key:
            continue
        company = str(preset.get("company") or key)
        raw_category = str(preset.get("category") or "blog").strip().lower()
        category = raw_category if raw_category in VALID_SOURCE_CATEGORIES else "blog"
        enabled = bool(preset.get("enabled", False))

        collect_method, config = _infer_collect_method(preset)
        source_id = _source_uuid(key)
        source = await db.get(Source, source_id)
        if source is None:
            source = Source(
                id=source_id,
                name=company,
                category=category,
                collect_method=collect_method,
                config=config,
                enabled=enabled,
                created_at=now,
                updated_at=now,
            )
        else:
            source.name = company
            source.category = category
            source.collect_method = collect_method
            if collect_method == "twitter_snaplytics":
                source.config = _merge_twitter_usernames(source.config, config)
            elif key == "reddit_social" and collect_method == "rss":
                source.config = _merge_reddit_subreddits(source.config, config)
            else:
                source.config = config
            source.enabled = enabled
            source.updated_at = now
        db.add(source)
        synced_source_ids.append(source.id)

    # 固定补充 2 个系统信息源（P0）
    system_sources = [
        {
            "key": "github_trending_daily",
            "name": "GitHub Trending Daily",
            "category": "open_source",
            "collect_method": "github_trending",
            "config": {"since": "daily", "limit": 10, "include_readme": True, "include_repo_tree": True},
        },
        {
            "key": "huggingface_daily_papers",
            "name": "Hugging Face Daily Papers",
            "category": "open_source",
            "collect_method": "huggingface",
            "config": {"limit": 30, "include_paper_detail": True, "include_arxiv_repos": True},
        },
    ]
    for source in system_sources:
        source_id = _source_uuid(source["key"])
        existing = await db.get(Source, source_id)
        if existing is None:
            existing = Source(
                id=source_id,
                name=source["name"],
                category=source["category"],
                collect_method=source["collect_method"],
                config=source["config"],
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        else:
            existing.name = source["name"]
            existing.category = source["category"]
            existing.collect_method = source["collect_method"]
            existing.config = source["config"]
            existing.enabled = True
            existing.updated_at = now
        db.add(existing)
        synced_source_ids.append(existing.id)

    await db.flush()

    unique_source_ids = list(dict.fromkeys(synced_source_ids))
    subscription_additions = 0
    for source_id in unique_source_ids:
        existing_subscription = await db.execute(
            select(UserSubscription.id).where(
                UserSubscription.user_id == DEFAULT_USER_ID,
                UserSubscription.source_id == source_id,
            )
        )
        if existing_subscription.scalar_one_or_none() is not None:
            continue
        db.add(
            UserSubscription(
                id=uuid.uuid4(),
                user_id=DEFAULT_USER_ID,
                source_id=source_id,
                enabled=True,
                custom_config={},
                created_at=now,
            )
        )
        subscription_additions += 1

    await db.commit()
    logger.info(
        "seeded_initial_data",
        sources=len(unique_source_ids),
        subscriptions_added=subscription_additions,
    )


async def bootstrap_runtime_data() -> None:
    try:
        async with async_session() as session:
            await seed_initial_data(session)
    except Exception as exc:  # pragma: no cover - startup fallback
        logger.warning("bootstrap_skipped", error=str(exc))
