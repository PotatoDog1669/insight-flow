"""Public RSS feed endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi import Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.destinations import DEFAULT_USER_ID, DESTINATION_PRESETS
from app.models.database import get_db
from app.models.user import User
from app.sinks.rss import build_feed_xml, fetch_recent_reports, resolve_feed_settings

router = APIRouter()


@router.get("/feed.xml", response_class=Response)
async def get_feed_xml(
    request: Request,
    db: AsyncSession = Depends(get_db),
    max_items: int | None = Query(default=None, ge=1, le=100),
):
    config = await _load_rss_destination_config(db)
    config.setdefault("feed_url", str(request.url))
    if max_items is not None:
        config["max_items"] = max_items

    settings = resolve_feed_settings(config)
    reports = await fetch_recent_reports(db=db, max_items=settings.max_items)
    xml_body = build_feed_xml(reports=reports, settings=settings)
    return Response(content=xml_body, media_type="application/rss+xml")


async def _load_rss_destination_config(db: AsyncSession) -> dict:
    default_config = dict(DESTINATION_PRESETS["rss"]["default_config"])
    user = await db.get(User, DEFAULT_USER_ID)
    if user is None or not isinstance(user.settings, dict):
        return default_config

    destinations = user.settings.get("destinations", {})
    if not isinstance(destinations, dict):
        return default_config

    rss_payload = destinations.get("rss", {})
    if not isinstance(rss_payload, dict):
        return default_config

    config = rss_payload.get("config")
    if isinstance(config, dict):
        default_config.update(config)
    return default_config
