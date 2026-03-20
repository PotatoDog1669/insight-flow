"""Destination configuration helpers."""

from __future__ import annotations

import uuid

from app.models.destination_instance import DestinationInstance
from app.schemas.destination import DestinationResponse, DestinationType
from app.sinks.obsidian import _normalize_target_folder
from app.utils.notion_ids import extract_notion_id

DESTINATION_PRESETS: dict[DestinationType, dict] = {
    "notion": {
        "name": "Notion",
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
        "name": "Obsidian",
        "description": "Write markdown to your Obsidian vault or REST bridge.",
        "default_config": {
            "mode": "rest",
            "api_url": "https://127.0.0.1:27124",
            "api_key": "",
            "vault_path": "",
            "target_folder": "AI Daily/",
        },
    },
    "rss": {
        "name": "RSS",
        "description": "Expose generated reports as RSS feed.",
        "default_config": {
            "feed_url": "http://localhost:8000/api/v1/feed.xml",
            "site_url": "http://localhost:3018",
            "feed_title": "LexDeepResearch Reports",
            "feed_description": "Latest generated reports from LexDeepResearch.",
            "max_items": 20,
        },
    },
}

DEFAULT_RSS_FEED_URL = str(DESTINATION_PRESETS["rss"]["default_config"]["feed_url"])
DEFAULT_RSS_FEED_PATH = "backend/static/feed.xml"


def _load_destinations_settings(settings: dict | None) -> dict[str, dict]:
    raw = (settings or {}).get("destinations", {})
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, dict] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            normalized[str(key)] = value
    return normalized


def _to_destination_response(instance: DestinationInstance) -> DestinationResponse:
    preset = DESTINATION_PRESETS[instance.type]
    config = dict(preset["default_config"])
    config.update(_resolved_instance_config(instance))
    return DestinationResponse(
        id=instance.id,
        name=instance.name,
        type=instance.type,  # type: ignore[arg-type]
        description=str(preset["description"]),
        config=config,
        enabled=bool(instance.enabled),
    )


def _resolve_destination_config(
    destination_id: DestinationType,
    destinations_data: dict[str, dict],
    overrides: dict | None = None,
) -> dict:
    current = destinations_data.get(destination_id, {})
    config = dict(current.get("config") or DESTINATION_PRESETS[destination_id]["default_config"])
    if overrides is not None:
        config.update(overrides)
    return _normalize_destination_config(destination_id, config)


def _normalize_destination_config(destination_id: DestinationType, config: dict) -> dict:
    normalized = dict(config)
    if destination_id == "obsidian":
        normalized["mode"] = _normalize_obsidian_mode(normalized)
        api_url = str(normalized.get("api_url") or "").strip()
        if api_url:
            normalized["api_url"] = api_url.rstrip("/")
        normalized["api_key"] = str(normalized.get("api_key") or "").strip()
        target_folder = str(normalized.get("target_folder") or "")
        if target_folder:
            normalized["target_folder"] = _normalize_target_folder(target_folder)
        vault_path = str(normalized.get("vault_path") or "").strip()
        if vault_path:
            normalized["vault_path"] = vault_path
        return normalized

    if destination_id != "notion":
        return normalized

    for key in ("database_id", "parent_page_id"):
        raw = str(normalized.get(key) or "").strip()
        if not raw:
            continue
        parsed = extract_notion_id(raw)
        normalized[key] = parsed or raw
    return normalized


def _resolved_instance_config(instance: DestinationInstance) -> dict:
    return _config_with_instance_defaults(instance.type, instance.config, instance.id)


def _config_with_instance_defaults(
    destination_type: DestinationType,
    config: dict | None,
    instance_id: uuid.UUID,
) -> dict:
    normalized = _normalize_destination_config(destination_type, dict(config or {}))
    if destination_type != "rss":
        return normalized

    feed_url = str(normalized.get("feed_url") or "").strip()
    if not feed_url or feed_url == DEFAULT_RSS_FEED_URL:
        normalized["feed_url"] = _default_rss_feed_url(instance_id)

    feed_path = str(normalized.get("feed_path") or "").strip()
    if not feed_path or feed_path == DEFAULT_RSS_FEED_PATH:
        normalized["feed_path"] = _default_rss_feed_path(instance_id)

    normalized["destination_instance_id"] = str(instance_id)
    return normalized


def _default_rss_feed_url(instance_id: uuid.UUID) -> str:
    return f"{DEFAULT_RSS_FEED_URL}?destination_id={instance_id}"


def _default_rss_feed_path(instance_id: uuid.UUID) -> str:
    return f"backend/static/rss/feed-{instance_id}.xml"


def _normalize_obsidian_mode(config: dict, *, allow_inference: bool = True) -> str | None:
    raw = str(config.get("mode") or "").strip().lower()
    if raw in {"rest", "file"}:
        return raw
    if not allow_inference:
        return None
    if str(config.get("vault_path") or "").strip() and not str(config.get("api_url") or "").strip():
        return "file"
    if str(config.get("api_url") or "").strip():
        return "rest"
    return "rest"
