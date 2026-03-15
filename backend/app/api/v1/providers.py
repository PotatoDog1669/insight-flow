"""Providers API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from time import perf_counter

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import get_db
from app.models.user import User
from app.providers.codex_transport import run_codex_json
from app.providers.llm_chat import run_llm_json
from app.schemas.provider import ProviderId, ProviderResponse, ProviderTestRequest, ProviderTestResponse, ProviderUpdate

router = APIRouter()

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")

PROVIDER_PRESETS: dict[ProviderId, dict] = {
    "llm_codex": {
        "name": "LLM Codex",
        "type": "llm",
        "description": "用于 workflow 加工阶段的 Codex LLM 配置，与 OpenAI 共享同一套 prompts 和 workflow。",
        "default_config": {
            "base_url": settings.codex_base_url or "https://api.openai.com/v1",
            "model": settings.codex_model or "gpt-5-codex",
            "timeout_sec": settings.codex_timeout_sec or 120,
            "max_retry": 2,
            "max_output_tokens": settings.llm_max_tokens or 2048,
            "temperature": settings.llm_temperature or 0.3,
            "api_key": "",
        },
    },
    "llm_openai": {
        "name": "LLM OpenAI",
        "type": "llm",
        "description": "用于 workflow 加工阶段的 OpenAI LLM 配置，与 Codex 共享同一套 prompts 和 workflow。",
        "default_config": {
            "base_url": "https://api.openai.com/v1",
            "model": settings.llm_primary_model or "gpt-4o-mini",
            "timeout_sec": 120,
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
    config = _resolve_provider_config(provider_id, providers_data, payload.config)

    existing = providers_data.get(provider_id, {})
    enabled = existing.get("enabled", False) if payload.enabled is None else payload.enabled
    providers_data[provider_id] = {"enabled": bool(enabled), "config": config}
    settings_data["providers"] = providers_data
    user.settings = settings_data
    user.updated_at = datetime.now(timezone.utc)
    db.add(user)
    await db.commit()

    return _to_provider_response(provider_id, providers_data)


@router.post("/{provider_id}/test", response_model=ProviderTestResponse)
async def test_provider(
    provider_id: ProviderId,
    payload: ProviderTestRequest,
    db: AsyncSession = Depends(get_db),
):
    if provider_id not in PROVIDER_PRESETS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    user = await _get_or_create_default_user(db)
    providers_data = _load_providers_settings(user.settings)
    config = _resolve_provider_config(provider_id, providers_data, payload.config)
    return await _run_provider_connectivity_test(provider_id, config)


def _load_providers_settings(settings_data: dict | None) -> dict[str, dict]:
    raw = (settings_data or {}).get("providers", {})
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, dict] = {}
    for provider_id in PROVIDER_PRESETS:
        payload = raw.get(provider_id)
        if isinstance(payload, dict):
            normalized[provider_id] = _normalize_provider_state(provider_id, payload)
    return normalized


def _resolve_provider_config(
    provider_id: ProviderId,
    providers_data: dict[str, dict],
    overrides: dict | None = None,
) -> dict:
    existing = providers_data.get(provider_id, {})
    config = dict(existing.get("config") or PROVIDER_PRESETS[provider_id]["default_config"])
    if overrides is not None:
        config.update(overrides)
    return _normalize_provider_config(provider_id, config)


def _normalize_provider_config(provider_id: ProviderId, config: dict) -> dict:
    normalized = dict(config)
    base_url = str(normalized.get("base_url", "")).strip()
    if base_url:
        normalized["base_url"] = base_url.rstrip("/")

    model = str(normalized.get("model", "")).strip()
    if model:
        normalized["model"] = model

    timeout_raw = normalized.get("timeout_sec")
    try:
        timeout_sec = int(timeout_raw)
    except (TypeError, ValueError):
        timeout_sec = int(PROVIDER_PRESETS[provider_id]["default_config"]["timeout_sec"])
    normalized["timeout_sec"] = max(timeout_sec, 1)

    retry_raw = normalized.get("max_retry")
    try:
        max_retry = int(retry_raw)
    except (TypeError, ValueError):
        max_retry = int(PROVIDER_PRESETS[provider_id]["default_config"]["max_retry"])
    normalized["max_retry"] = max(max_retry, 0)

    max_tokens_raw = normalized.get("max_output_tokens")
    try:
        max_tokens = int(max_tokens_raw)
    except (TypeError, ValueError):
        max_tokens = int(PROVIDER_PRESETS[provider_id]["default_config"]["max_output_tokens"])
    normalized["max_output_tokens"] = max(max_tokens, 1)

    temperature_raw = normalized.get("temperature")
    try:
        temperature = float(temperature_raw)
    except (TypeError, ValueError):
        temperature = float(PROVIDER_PRESETS[provider_id]["default_config"]["temperature"])
    normalized["temperature"] = temperature

    normalized["api_key"] = str(normalized.get("api_key", "")).strip()
    return normalized


def _normalize_provider_state(provider_id: ProviderId, payload: dict) -> dict:
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    return {
        "enabled": bool(payload.get("enabled", False)),
        "config": _normalize_provider_config(provider_id, config),
    }
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


async def _run_provider_connectivity_test(provider_id: ProviderId, config: dict) -> ProviderTestResponse:
    started_at = perf_counter()
    try:
        result = await _execute_provider_test(provider_id, config)
        latency_ms = max(int((perf_counter() - started_at) * 1000), 0)
        message = str(result.get("message") or "Connection successful")
        return ProviderTestResponse(success=True, message=message, latency_ms=latency_ms, model=str(config.get("model") or ""))
    except (ValueError, RuntimeError, httpx.HTTPError) as exc:
        latency_ms = max(int((perf_counter() - started_at) * 1000), 0)
        return ProviderTestResponse(
            success=False,
            message=_format_provider_test_error(exc),
            latency_ms=latency_ms,
            model=str(config.get("model") or ""),
        )


async def _execute_provider_test(provider_id: ProviderId, config: dict) -> dict:
    prompt = (
        'Return JSON only: {"ok": true, "message": "pong"}. '
        "Do not include markdown fences or extra text."
    )
    request_config = dict(config)
    request_config["temperature"] = 0
    request_config["max_output_tokens"] = 32

    if provider_id == "llm_codex":
        return await run_codex_json(prompt=prompt, config=request_config)
    return await run_llm_json(prompt=prompt, config=request_config)


def _format_provider_test_error(exc: ValueError | RuntimeError | httpx.HTTPError) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Provider returned HTTP {exc.response.status_code}"
    if isinstance(exc, httpx.RequestError):
        return f"Network error: {exc}"
    return str(exc)
