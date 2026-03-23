"""Small helpers for API contract and persistence tests."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy import select

from app.models import User

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


def destination_create_payload(
    destination_type: str,
    name: str,
    *,
    enabled: bool = True,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": destination_type,
        "name": name,
        "enabled": enabled,
        "config": config or {},
    }


def monitor_create_payload(
    name: str,
    source_ids: list[str],
    *,
    time_period: str = "daily",
    report_type: str | None = None,
    destination_instance_ids: list[str] | None = None,
    enabled: bool | None = None,
    source_overrides: dict[str, Any] | None = None,
    ai_provider: str | None = None,
    ai_routing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "time_period": time_period,
        "source_ids": source_ids,
    }
    if report_type is not None:
        payload["report_type"] = report_type
    if destination_instance_ids is not None:
        payload["destination_instance_ids"] = destination_instance_ids
    if enabled is not None:
        payload["enabled"] = enabled
    if source_overrides is not None:
        payload["source_overrides"] = source_overrides
    if ai_provider is not None:
        payload["ai_provider"] = ai_provider
    if ai_routing is not None:
        payload["ai_routing"] = ai_routing
    return payload


def assert_publish_trace_entry(
    entry: dict[str, Any],
    *,
    sink: str,
    status: str,
    destination_instance_id: str,
    destination_instance_name: str,
    url: str | None = None,
) -> None:
    assert entry["sink"] == sink
    assert entry["status"] == status
    assert entry["destination_instance_id"] == destination_instance_id
    assert entry["destination_instance_name"] == destination_instance_name
    if url is not None:
        assert entry["url"] == url


def load_user_settings(session_factory: Any) -> dict[str, Any]:
    async def _fetch_settings() -> dict[str, Any]:
        async with session_factory() as session:
            result = await session.execute(select(User).where(User.id == DEFAULT_USER_ID))
            user = result.scalar_one_or_none()
            assert user is not None
            return dict(user.settings or {})

    return asyncio.run(_fetch_settings())
