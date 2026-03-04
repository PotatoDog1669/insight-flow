"""Providers API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import get_db
from app.models.user import User
from app.schemas.provider import ProviderId, ProviderResponse, ProviderUpdate

router = APIRouter()

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")

PROVIDER_PRESETS: dict[ProviderId, dict] = {
    "agent_codex": {
        "name": "Codex Agent",
        "type": "agent",
        "description": "AI processing executor for filter / keywords / report stages.",
        "default_config": {
            "auth_mode": settings.codex_auth_mode or "api_key",
            "base_url": settings.codex_base_url or "https://api.openai.com/v1",
            "model": settings.codex_model or "gpt-5-codex",
            "timeout_sec": settings.codex_timeout_sec or 90,
            "api_key": "",
            "oauth_token": "",
        },
    },
    "llm_openai": {
        "name": "LLM OpenAI",
        "type": "llm",
        "description": "LLM executor for filter / keywords / report stages.",
        "default_config": {
            "base_url": "https://api.openai.com/v1",
            "model": settings.llm_primary_model or "gpt-4o-mini",
            "timeout_sec": 30,
            "max_retry": 2,
            "max_output_tokens": settings.llm_max_tokens or 2048,
            "temperature": settings.llm_temperature or 0.3,
            "api_key": "",
        },
    },
}


@router.get("", response_model=list[ProviderResponse])
async def list_providers(db: AsyncSession = Depends(get_db)):
    user = await _get_or_create_default_user(db)
    providers_data = _load_providers_settings(user.settings)
    return [_to_provider_response(provider_id, providers_data) for provider_id in PROVIDER_PRESETS]


@router.patch("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: ProviderId,
    payload: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
):
    if provider_id not in PROVIDER_PRESETS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    user = await _get_or_create_default_user(db)
    settings_data = dict(user.settings or {})
    providers_data = _load_providers_settings(settings_data)

    existing = providers_data.get(provider_id, {})
    config = dict(existing.get("config") or PROVIDER_PRESETS[provider_id]["default_config"])
    if payload.config is not None:
        config.update(payload.config)
    config = _normalize_provider_config(provider_id, config)

    enabled = existing.get("enabled", False) if payload.enabled is None else payload.enabled
    providers_data[provider_id] = {"enabled": bool(enabled), "config": config}
    settings_data["providers"] = providers_data
    user.settings = settings_data
    user.updated_at = datetime.now(timezone.utc)
    db.add(user)
    await db.commit()

    return _to_provider_response(provider_id, providers_data)


def _load_providers_settings(settings_data: dict | None) -> dict[str, dict]:
    raw = (settings_data or {}).get("providers", {})
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, dict] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            normalized[str(key)] = value
    return normalized


def _normalize_provider_config(provider_id: ProviderId, config: dict) -> dict:
    normalized = dict(config)

    if provider_id == "agent_codex":
        auth_mode = str(normalized.get("auth_mode", "api_key")).strip().lower()
        normalized["auth_mode"] = auth_mode if auth_mode in {"api_key", "oauth"} else "api_key"

        base_url = str(normalized.get("base_url", "")).strip()
        if base_url:
            normalized["base_url"] = base_url.rstrip("/")

        model = str(normalized.get("model", "")).strip()
        if model:
            normalized["model"] = model

        timeout_raw = normalized.get("timeout_sec")
        try:
            timeout_sec = int(timeout_raw)
        except Exception:
            timeout_sec = int(PROVIDER_PRESETS[provider_id]["default_config"]["timeout_sec"])
        normalized["timeout_sec"] = max(timeout_sec, 1)

        for key in ("api_key", "oauth_token"):
            normalized[key] = str(normalized.get(key, "")).strip()

        return normalized

    if provider_id == "llm_openai":
        base_url = str(normalized.get("base_url", "")).strip()
        if base_url:
            normalized["base_url"] = base_url.rstrip("/")

        model = str(normalized.get("model", "")).strip()
        if model:
            normalized["model"] = model

        timeout_raw = normalized.get("timeout_sec")
        try:
            timeout_sec = int(timeout_raw)
        except Exception:
            timeout_sec = int(PROVIDER_PRESETS[provider_id]["default_config"]["timeout_sec"])
        normalized["timeout_sec"] = max(timeout_sec, 1)

        retry_raw = normalized.get("max_retry")
        try:
            max_retry = int(retry_raw)
        except Exception:
            max_retry = int(PROVIDER_PRESETS[provider_id]["default_config"]["max_retry"])
        normalized["max_retry"] = max(max_retry, 0)

        max_tokens_raw = normalized.get("max_output_tokens")
        try:
            max_tokens = int(max_tokens_raw)
        except Exception:
            max_tokens = int(PROVIDER_PRESETS[provider_id]["default_config"]["max_output_tokens"])
        normalized["max_output_tokens"] = max(max_tokens, 1)

        temperature_raw = normalized.get("temperature")
        try:
            temperature = float(temperature_raw)
        except Exception:
            temperature = float(PROVIDER_PRESETS[provider_id]["default_config"]["temperature"])
        normalized["temperature"] = temperature

        normalized["api_key"] = str(normalized.get("api_key", "")).strip()
        return normalized

    return normalized


def _to_provider_response(provider_id: ProviderId, providers_data: dict[str, dict]) -> ProviderResponse:
    preset = PROVIDER_PRESETS[provider_id]
    current = providers_data.get(provider_id, {})
    config = dict(preset["default_config"])
    if isinstance(current.get("config"), dict):
        config.update(current["config"])
    return ProviderResponse(
        id=provider_id,
        name=str(preset["name"]),
        type=str(preset["type"]),
        description=str(preset["description"]),
        config=config,
        enabled=bool(current.get("enabled", False)),
    )


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
