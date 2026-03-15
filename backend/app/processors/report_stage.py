"""Shared report-stage execution helpers."""

from __future__ import annotations

from collections.abc import Callable

from app.providers.registry import get_provider
from app.routing.schema import StageRoute


def _merge_provider_config(
    *,
    provider_name: str,
    profile_config: dict,
    provider_overrides: dict[str, dict],
) -> dict:
    merged = dict(profile_config) if isinstance(profile_config, dict) else {}
    override = provider_overrides.get(provider_name)
    if isinstance(override, dict):
        merged.update(override)
    return merged


def _max_retry(config: dict) -> int:
    raw = config.get("max_retry", 0) if isinstance(config, dict) else 0
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return 0


async def run_report_with_retry(
    *,
    route: StageRoute,
    providers: dict[str, dict],
    provider_overrides: dict[str, dict],
    payload: dict,
    provider_getter: Callable[..., object] = get_provider,
) -> tuple[dict, str]:
    provider_chain: list[str] = []
    for raw_name in [route.primary, *(route.fallback or [])]:
        provider_name = str(raw_name or "").strip()
        if not provider_name or provider_name in provider_chain:
            continue
        provider_chain.append(provider_name)
    last_exc: Exception | None = None
    for provider_name in provider_chain:
        config = _merge_provider_config(
            provider_name=provider_name,
            profile_config=providers.get(provider_name, {}),
            provider_overrides=provider_overrides,
        )
        provider = provider_getter(stage="report", name=provider_name)
        for _ in range(_max_retry(config) + 1):
            try:
                result = await provider.run(payload=payload, config=config)
                return result, provider_name
            except Exception as exc:
                last_exc = exc
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("report stage has no available provider")
