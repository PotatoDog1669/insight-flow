"""Destinations API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.user import User
from app.schemas.destination import DestinationId, DestinationResponse, DestinationUpdate
from app.utils.notion_ids import extract_notion_id

router = APIRouter()

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")

DESTINATION_PRESETS: dict[DestinationId, dict] = {
    "notion": {
        "name": "Notion Workspace",
        "description": "Sync reports to databases via Notion Integration.",
        "default_config": {
            "token": "",
            "database_id": "",
            "parent_page_id": "",
            "title_property": "Name",
            "summary_property": "TL;DR",
            "template_version": "v1",
        },
    },
    "obsidian": {
        "name": "Obsidian Vault",
        "description": "Write markdown to your Obsidian vault or REST bridge.",
        "default_config": {"api_url": "http://127.0.0.1:27123", "api_key": "", "target_folder": "LexDeepResearch/"},
    },
    "rss": {
        "name": "RSS Feed",
        "description": "Expose generated reports as RSS feed.",
        "default_config": {
            "feed_url": "http://localhost:8000/api/v1/feed.xml",
            "site_url": "http://localhost:3000",
            "feed_title": "LexDeepResearch Reports",
            "feed_description": "Latest generated reports from LexDeepResearch.",
            "max_items": 20,
        },
    },
}


@router.get("", response_model=list[DestinationResponse])
async def list_destinations(db: AsyncSession = Depends(get_db)):
    user = await _get_or_create_default_user(db)
    destinations_data = _load_destinations_settings(user.settings)
    return [_to_destination_response(dest_id, destinations_data) for dest_id in DESTINATION_PRESETS]


@router.patch("/{destination_id}", response_model=DestinationResponse)
async def update_destination(
    destination_id: DestinationId,
    payload: DestinationUpdate,
    db: AsyncSession = Depends(get_db),
):
    if destination_id not in DESTINATION_PRESETS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found")

    user = await _get_or_create_default_user(db)
    settings = dict(user.settings or {})
    destinations_data = _load_destinations_settings(settings)

    existing = destinations_data.get(destination_id, {})
    config = dict(existing.get("config") or DESTINATION_PRESETS[destination_id]["default_config"])
    if payload.config is not None:
        config.update(payload.config)
    config = _normalize_destination_config(destination_id, config)

    enabled = existing.get("enabled", False) if payload.enabled is None else payload.enabled
    destinations_data[destination_id] = {"enabled": bool(enabled), "config": config}
    settings["destinations"] = destinations_data
    user.settings = settings
    user.updated_at = datetime.now(timezone.utc)
    db.add(user)
    await db.commit()

    return _to_destination_response(destination_id, destinations_data)


def _load_destinations_settings(settings: dict | None) -> dict[str, dict]:
    raw = (settings or {}).get("destinations", {})
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, dict] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            normalized[str(key)] = value
    return normalized


def _to_destination_response(dest_id: DestinationId, destinations_data: dict[str, dict]) -> DestinationResponse:
    preset = DESTINATION_PRESETS[dest_id]
    current = destinations_data.get(dest_id, {})
    config = dict(preset["default_config"])
    if isinstance(current.get("config"), dict):
        config.update(current["config"])
    return DestinationResponse(
        id=dest_id,
        name=str(preset["name"]),
        type=dest_id,
        description=str(preset["description"]),
        config=config,
        enabled=bool(current.get("enabled", False)),
    )


def _normalize_destination_config(destination_id: DestinationId, config: dict) -> dict:
    if destination_id != "notion":
        return config

    normalized = dict(config)
    for key in ("database_id", "parent_page_id"):
        raw = str(normalized.get(key) or "").strip()
        if not raw:
            continue
        parsed = extract_notion_id(raw)
        normalized[key] = parsed or raw
    return normalized


async def _get_or_create_default_user(db: AsyncSession) -> User:
    user = await db.get(User, DEFAULT_USER_ID)
    if user:
        return user

    now = datetime.now(timezone.utc)
    user = User(
        id=DEFAULT_USER_ID,
        email="admin@lexmount.com",
        name="Lex Researcher",
        settings={"default_time_period": "daily", "default_report_type": "daily", "default_sink": "notion"},
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
