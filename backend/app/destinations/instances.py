"""Destination instance persistence helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.destinations.config import (
    DESTINATION_PRESETS,
    _config_with_instance_defaults,
    _load_destinations_settings,
    _normalize_destination_config,
    _resolved_instance_config,
)
from app.models.destination_instance import DestinationInstance
from app.models.monitor import Monitor
from app.models.user import User

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


async def _ensure_destination_instances(db: AsyncSession, user: User) -> list[DestinationInstance]:
    result = await db.execute(
        select(DestinationInstance)
        .where(DestinationInstance.user_id == user.id)
        .order_by(DestinationInstance.created_at.asc(), DestinationInstance.type.asc())
    )
    instances = list(result.scalars().all())
    if instances:
        return instances

    destinations_data = _load_destinations_settings(user.settings)
    if not destinations_data:
        return []

    created: list[DestinationInstance] = []
    for dest_type in DESTINATION_PRESETS:
        legacy = destinations_data.get(dest_type)
        if not isinstance(legacy, dict):
            continue
        config = dict(DESTINATION_PRESETS[dest_type]["default_config"])
        if isinstance(legacy.get("config"), dict):
            config.update(legacy["config"])
        instance = DestinationInstance(
            user_id=user.id,
            type=dest_type,
            name=str(DESTINATION_PRESETS[dest_type]["name"]),
            enabled=bool(legacy.get("enabled", False)),
            config=_normalize_destination_config(dest_type, config),
        )
        db.add(instance)
        created.append(instance)

    if created:
        await db.flush()
        for item in created:
            item.config = _config_with_instance_defaults(item.type, item.config, item.id)
            db.add(item)
        await db.commit()
        for item in created:
            await db.refresh(item)
    return created


async def _destination_settings_from_user(db: AsyncSession, user: User) -> dict[str, dict]:
    instances = await _ensure_destination_instances(db, user)
    settings: dict[str, dict] = {}
    for instance in instances:
        payload = {
            "id": str(instance.id),
            "type": instance.type,
            "name": instance.name,
            "enabled": bool(instance.enabled),
            "config": _resolved_instance_config(instance),
        }
        settings[str(instance.id)] = payload
        settings.setdefault(instance.type, payload)
    return settings


async def _get_or_create_default_user(db: AsyncSession) -> User:
    user = await db.get(User, DEFAULT_USER_ID)
    if user:
        return user

    now = datetime.now(UTC)
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


async def _resolve_destination_instance(
    *,
    db: AsyncSession,
    user: User,
    destination_id: str,
    create_legacy_default: bool,
) -> DestinationInstance | None:
    parsed_uuid = _parse_uuid_or_none(destination_id)
    if parsed_uuid is not None:
        instance = await db.get(DestinationInstance, parsed_uuid)
        if instance is None or instance.user_id != user.id:
            return None
        return instance

    if destination_id not in DESTINATION_PRESETS:
        return None

    instances = await _ensure_destination_instances(db, user)
    for item in instances:
        if item.type == destination_id:
            return item

    if not create_legacy_default:
        return None

    instance = DestinationInstance(
        user_id=user.id,
        type=destination_id,
        name=str(DESTINATION_PRESETS[destination_id]["name"]),
        enabled=False,
        config=dict(DESTINATION_PRESETS[destination_id]["default_config"]),
    )
    instance.config = _normalize_destination_config(destination_id, instance.config)
    db.add(instance)
    await db.flush()
    return instance


async def _sync_legacy_destination_settings(db: AsyncSession, user: User) -> None:
    result = await db.execute(
        select(DestinationInstance)
        .where(DestinationInstance.user_id == user.id)
        .order_by(DestinationInstance.created_at.asc())
    )
    instances = list(result.scalars().all())
    settings = dict(user.settings or {})
    destinations: dict[str, dict] = {}
    seen_types: set[str] = set()
    for item in instances:
        if item.type in seen_types:
            continue
        destinations[item.type] = {
            "enabled": bool(item.enabled),
            "config": _resolved_instance_config(item),
        }
        seen_types.add(item.type)
    if destinations:
        settings["destinations"] = destinations
    else:
        settings.pop("destinations", None)
    user.settings = settings
    user.updated_at = datetime.now(UTC)
    db.add(user)


def _parse_uuid_or_none(raw: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        return None


async def _remove_destination_binding_from_monitors(
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
    destination_instance_id: str,
) -> None:
    monitors_result = await db.execute(select(Monitor).where(Monitor.user_id == user_id))
    for monitor in monitors_result.scalars().all():
        existing = [str(item).strip() for item in (monitor.destination_instance_ids or []) if str(item).strip()]
        updated = [item for item in existing if item != destination_instance_id]
        if updated == existing:
            continue
        monitor.destination_instance_ids = updated
        db.add(monitor)
