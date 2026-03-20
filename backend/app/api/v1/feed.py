"""Public RSS feed endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.destinations.config import DESTINATION_PRESETS
from app.destinations.instances import DEFAULT_USER_ID
from app.models.database import get_db
from app.models.destination_instance import DestinationInstance
from app.models.user import User
from app.sinks.rss import build_feed_xml, fetch_recent_reports, resolve_feed_settings

router = APIRouter()


@router.get("/feed.xml", response_class=Response)
async def get_feed_xml(
    request: Request,
    db: AsyncSession = Depends(get_db),
    max_items: int | None = Query(default=None, ge=1, le=100),
    destination_id: str | None = Query(default=None),
):
    config, resolved_destination_id = await _load_rss_destination_config(db, destination_id=destination_id)
    config.setdefault("feed_url", str(request.url))
    if max_items is not None:
        config["max_items"] = max_items

    settings = resolve_feed_settings(config)
    reports = await fetch_recent_reports(
        db=db,
        max_items=settings.max_items,
        destination_instance_id=resolved_destination_id,
    )
    xml_body = build_feed_xml(reports=reports, settings=settings)
    return Response(content=xml_body, media_type="application/rss+xml")


async def _load_rss_destination_config(
    db: AsyncSession,
    *,
    destination_id: str | None,
) -> tuple[dict, str | None]:
    default_config = dict(DESTINATION_PRESETS["rss"]["default_config"])
    if destination_id:
        try:
            parsed_destination_id = uuid.UUID(destination_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="RSS destination not found") from exc
        destination = await db.get(DestinationInstance, parsed_destination_id)
        if destination is None or destination.type != "rss":
            raise HTTPException(status_code=404, detail="RSS destination not found")
        if not destination.enabled:
            raise HTTPException(status_code=404, detail="RSS destination not found")
        config = dict(destination.config or {})
        default_config.update(config)
        return default_config, str(destination.id)

    user = await db.get(User, DEFAULT_USER_ID)
    if user is None or not isinstance(user.settings, dict):
        return default_config, None

    destinations = user.settings.get("destinations", {})
    if not isinstance(destinations, dict):
        return default_config, None

    rss_payload = destinations.get("rss", {})
    if not isinstance(rss_payload, dict):
        return default_config, None

    config = rss_payload.get("config")
    if isinstance(config, dict):
        default_config.update(config)
    return default_config, None
