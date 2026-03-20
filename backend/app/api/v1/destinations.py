"""Destinations API."""

from __future__ import annotations

import json
import os
from pathlib import Path
from time import perf_counter

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.destinations.config import (
    DESTINATION_PRESETS,
    _config_with_instance_defaults,
    _load_destinations_settings,
    _normalize_destination_config,
    _normalize_obsidian_mode,
    _resolve_destination_config,
    _to_destination_response,
)
from app.destinations.instances import (
    _ensure_destination_instances,
    _get_or_create_default_user,
    _remove_destination_binding_from_monitors,
    _resolve_destination_instance,
    _sync_legacy_destination_settings,
)
from app.models.database import get_db
from app.models.destination_instance import DestinationInstance
from app.schemas.destination import (
    DestinationCreate,
    DestinationResponse,
    DestinationTestRequest,
    DestinationTestResponse,
    DestinationType,
    DestinationUpdate,
    ObsidianVaultCandidate,
    ObsidianVaultDiscoveryResponse,
)
from app.sinks.obsidian import _normalize_target_folder, _resolve_local_target_dir

router = APIRouter()


@router.get("", response_model=list[DestinationResponse])
async def list_destinations(db: AsyncSession = Depends(get_db)):
    user = await _get_or_create_default_user(db)
    instances = await _ensure_destination_instances(db, user)
    return [_to_destination_response(item) for item in instances]


@router.post("", response_model=DestinationResponse, status_code=status.HTTP_201_CREATED)
async def create_destination(
    payload: DestinationCreate,
    db: AsyncSession = Depends(get_db),
):
    user = await _get_or_create_default_user(db)
    instance = DestinationInstance(
        user_id=user.id,
        type=payload.type,
        name=payload.name.strip(),
        enabled=payload.enabled,
        config=_normalize_destination_config(payload.type, payload.config),
    )
    db.add(instance)
    await db.flush()
    instance.config = _config_with_instance_defaults(instance.type, instance.config, instance.id)
    db.add(instance)
    await _sync_legacy_destination_settings(db, user)
    await db.commit()
    await db.refresh(instance)
    return _to_destination_response(instance)


@router.get("/obsidian/discover", response_model=ObsidianVaultDiscoveryResponse)
async def discover_obsidian_vaults():
    vaults = _discover_obsidian_vaults()
    if not vaults:
        return ObsidianVaultDiscoveryResponse(
            success=False,
            message="No local Obsidian vaults detected. Please enter the vault path manually.",
            vaults=[],
        )

    detected_path = vaults[0]["path"]
    message = "Detected current Obsidian vault."
    if len(vaults) > 1:
        message = "Detected multiple Obsidian vaults. Filled the most likely path and listed all candidates."
    return ObsidianVaultDiscoveryResponse(
        success=True,
        message=message,
        detected_path=detected_path,
        vaults=[ObsidianVaultCandidate(path=item["path"], name=item["name"], open=item["open"]) for item in vaults],
    )


@router.patch("/{destination_id}", response_model=DestinationResponse)
async def update_destination(
    destination_id: str,
    payload: DestinationUpdate,
    db: AsyncSession = Depends(get_db),
):
    user = await _get_or_create_default_user(db)
    instance = await _resolve_destination_instance(
        db=db,
        user=user,
        destination_id=destination_id,
        create_legacy_default=True,
    )
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found")

    if payload.name is not None:
        instance.name = payload.name.strip()
    config = dict(instance.config or {})
    if payload.config is not None:
        config.update(payload.config)
    instance.config = _normalize_destination_config(instance.type, config)
    instance.config = _config_with_instance_defaults(instance.type, instance.config, instance.id)
    if payload.enabled is not None:
        instance.enabled = bool(payload.enabled)
    db.add(instance)
    await _sync_legacy_destination_settings(db, user)
    await db.commit()
    await db.refresh(instance)

    return _to_destination_response(instance)


@router.delete("/{destination_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_destination(
    destination_id: str,
    db: AsyncSession = Depends(get_db),
):
    user = await _get_or_create_default_user(db)
    instance = await _resolve_destination_instance(
        db=db,
        user=user,
        destination_id=destination_id,
        create_legacy_default=False,
    )
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found")
    await _remove_destination_binding_from_monitors(
        db=db,
        user_id=user.id,
        destination_instance_id=str(instance.id),
    )
    await db.delete(instance)
    await _sync_legacy_destination_settings(db, user)
    await db.commit()


@router.post("/{destination_id}/test", response_model=DestinationTestResponse)
async def test_destination(
    destination_id: str,
    payload: DestinationTestRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    user = await _get_or_create_default_user(db)
    if destination_id in DESTINATION_PRESETS:
        destinations_data = _load_destinations_settings(user.settings)
        overrides = payload.config if payload is not None else None
        config = _resolve_destination_config(destination_id, destinations_data, overrides)
        return await _run_destination_connectivity_test(destination_id, config)

    instance = await _resolve_destination_instance(
        db=db,
        user=user,
        destination_id=destination_id,
        create_legacy_default=False,
    )
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found")

    config = dict(instance.config or {})
    if payload is not None and payload.config is not None:
        config.update(payload.config)
    normalized_config = _normalize_destination_config(instance.type, config)
    return await _run_destination_connectivity_test(instance.type, normalized_config)


async def _run_destination_connectivity_test(destination_id: DestinationType, config: dict) -> DestinationTestResponse:
    started_at = perf_counter()
    try:
        if destination_id == "obsidian":
            result = await _run_obsidian_connectivity_test(config)
        elif destination_id == "notion":
            result = _run_notion_configuration_test(config)
        else:
            result = _run_rss_configuration_test(config)
        latency_ms = max(int((perf_counter() - started_at) * 1000), 0)
        return DestinationTestResponse(success=True, latency_ms=latency_ms, **result)
    except (ValueError, OSError, httpx.HTTPError) as exc:
        latency_ms = max(int((perf_counter() - started_at) * 1000), 0)
        return DestinationTestResponse(
            success=False,
            message=_format_destination_test_error(exc),
            latency_ms=latency_ms,
        )


async def _run_obsidian_connectivity_test(config: dict) -> dict:
    mode = _normalize_obsidian_mode(config, allow_inference=False)
    if mode is None:
        raise ValueError("Missing Obsidian mode: choose 'rest' or 'file'")

    api_url = str(config.get("api_url") or "").strip().rstrip("/")
    api_key = str(config.get("api_key") or "").strip()
    if mode == "rest":
        if not api_url or not api_key:
            raise ValueError("Missing Obsidian REST config: api_url and api_key are required for rest mode")
        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            response = await client.get(f"{api_url}/")
            response.raise_for_status()
        return {
            "message": "Obsidian REST API reachable",
            "mode": "rest",
            "checked_target": api_url,
        }

    if mode != "file":
        raise ValueError(f"Unsupported Obsidian mode: {mode}")

    target_dir = _resolve_local_target_dir(
        vault_path=str(config.get("vault_path") or "").strip(),
        target_folder=_normalize_target_folder(str(config.get("target_folder") or "")),
    )
    if target_dir is None:
        raise ValueError("Missing Obsidian file config: vault_path is required for file mode")
    target_dir.mkdir(parents=True, exist_ok=True)
    if not target_dir.is_dir():
        raise OSError(f"Obsidian path is not a directory: {target_dir}")
    if not _is_writable_directory(target_dir):
        raise PermissionError(f"Obsidian path is not writable: {target_dir}")
    return {
        "message": "Obsidian vault directory is writable",
        "mode": "file",
        "checked_target": str(target_dir),
    }


def _run_notion_configuration_test(config: dict) -> dict:
    token = str(config.get("token") or config.get("api_key") or "").strip()
    database_id = str(config.get("database_id") or "").strip()
    parent_page_id = str(config.get("parent_page_id") or "").strip()
    if not token:
        raise ValueError("Missing Notion token")
    if not database_id and not parent_page_id:
        raise ValueError("Missing Notion database_id or parent_page_id")
    checked_target = database_id or parent_page_id
    return {
        "message": "Notion destination configuration looks valid",
        "mode": "config",
        "checked_target": checked_target,
    }


def _run_rss_configuration_test(config: dict) -> dict:
    feed_url = str(config.get("feed_url") or "").strip()
    if not feed_url:
        raise ValueError("Missing RSS feed_url")
    return {
        "message": "RSS destination configuration looks valid",
        "mode": "config",
        "checked_target": feed_url,
    }


def _is_writable_directory(path: Path) -> bool:
    probe = path / ".obsidian-write-test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False
    return True


def _format_destination_test_error(exc: ValueError | OSError | httpx.HTTPError) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Destination returned HTTP {exc.response.status_code}"
    if isinstance(exc, httpx.RequestError):
        return f"Network error: {exc}"
    return str(exc)


def _discover_obsidian_vaults() -> list[dict[str, str | bool | int]]:
    discovered: dict[str, dict[str, str | bool | int]] = {}
    for config_path in _obsidian_config_paths():
        if not config_path.exists():
            continue
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        raw_vaults = payload.get("vaults")
        if not isinstance(raw_vaults, dict):
            continue
        for item in raw_vaults.values():
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "").strip()
            if not path:
                continue
            candidate = {
                "path": path,
                "name": Path(path).name or path,
                "open": bool(item.get("open", False)),
                "ts": int(item.get("ts") or 0),
            }
            existing = discovered.get(path)
            if existing is None or _vault_sort_key(candidate) < _vault_sort_key(existing):
                discovered[path] = candidate
    return sorted(discovered.values(), key=_vault_sort_key)


def _obsidian_config_paths() -> list[Path]:
    home = Path.home()
    paths = [
        home / "Library" / "Application Support" / "obsidian" / "obsidian.json",
        home / ".config" / "obsidian" / "obsidian.json",
    ]
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.append(Path(appdata) / "obsidian" / "obsidian.json")
    return paths


def _vault_sort_key(item: dict[str, str | bool | int]) -> tuple[int, int, str]:
    return (
        0 if bool(item.get("open", False)) else 1,
        -int(item.get("ts") or 0),
        str(item.get("name") or ""),
    )
