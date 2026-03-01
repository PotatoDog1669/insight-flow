"""Runtime bootstrap: seed minimal P0 data for a fresh database."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid

import structlog
import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session
from app.models.source import Source
from app.models.subscription import UserSubscription
from app.models.user import User

logger = structlog.get_logger()

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
PRESETS_PATH = Path(__file__).resolve().parent / "collectors" / "source_presets.yaml"


def _source_uuid(key: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"lexdeepresearch:source:{key}")


def _infer_collect_method(preset: dict) -> tuple[str, dict]:
    rss_url = preset.get("rss_url")
    strategy = str(preset.get("strategy", ""))
    urls = preset.get("urls") or []
    primary_url = urls[0] if urls else None

    if rss_url:
        return "rss", {"feed_url": rss_url, "max_items": 30}

    if strategy in {"github_only", "github_plus_docs", "github_plus_site_scraper"}:
        return "github_trending", {"since": "daily", "limit": 10, "include_readme": True, "include_repo_tree": True}

    profile = {
        "site_key": preset.get("key", "custom_site"),
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
    return "blog_scraper", {"profile": profile, "max_items": 20}


def _origin(url: str | None) -> str:
    if not url:
        return ""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return ""


async def seed_initial_data(db: AsyncSession) -> None:
    source_count = await db.scalar(select(func.count()).select_from(Source))
    if source_count and source_count > 0:
        return

    now = datetime.now(timezone.utc)

    user = await db.get(User, DEFAULT_USER_ID)
    if user is None:
        user = User(
            id=DEFAULT_USER_ID,
            email="admin@lexmount.com",
            name="Lex Researcher",
            settings={"default_time_period": "daily", "default_depth": "brief", "default_sink": "database"},
            created_at=now,
            updated_at=now,
        )
        db.add(user)

    presets_payload = yaml.safe_load(PRESETS_PATH.read_text(encoding="utf-8")) if PRESETS_PATH.exists() else {}
    preset_sources = presets_payload.get("sources", []) if isinstance(presets_payload, dict) else []

    seeded_sources: list[Source] = []
    for preset in preset_sources:
        if not isinstance(preset, dict):
            continue
        if preset.get("priority") != "p0" or not preset.get("enabled", False):
            continue

        key = str(preset.get("key") or "")
        company = str(preset.get("company") or key)
        category = "blog"
        if key in {"deepseek"}:
            category = "open_source"

        collect_method, config = _infer_collect_method(preset)
        source = Source(
            id=_source_uuid(key),
            name=company,
            category=category,
            collect_method=collect_method,
            config=config,
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        db.add(source)
        seeded_sources.append(source)

    # 固定补充 2 个系统信息源（P0）
    system_sources = [
        Source(
            id=_source_uuid("github_trending_daily"),
            name="GitHub Trending Daily",
            category="open_source",
            collect_method="github_trending",
            config={"since": "daily", "limit": 10, "include_readme": True, "include_repo_tree": True},
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        Source(
            id=_source_uuid("huggingface_daily_papers"),
            name="Hugging Face Daily Papers",
            category="open_source",
            collect_method="huggingface",
            config={"limit": 30, "include_paper_detail": True, "include_arxiv_repos": True},
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
    ]
    for source in system_sources:
        db.add(source)
        seeded_sources.append(source)

    await db.flush()

    for source in seeded_sources:
        db.add(
            UserSubscription(
                id=uuid.uuid4(),
                user_id=DEFAULT_USER_ID,
                source_id=source.id,
                enabled=True,
                custom_config={},
                created_at=now,
            )
        )

    await db.commit()
    logger.info("seeded_initial_data", sources=len(seeded_sources))


async def bootstrap_runtime_data() -> None:
    try:
        async with async_session() as session:
            await seed_initial_data(session)
    except Exception as exc:  # pragma: no cover - startup fallback
        logger.warning("bootstrap_skipped", error=str(exc))
