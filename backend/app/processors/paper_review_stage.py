"""Shared paper review stage execution helpers."""

from __future__ import annotations

from collections.abc import Callable

from app.processors.report_stage import _max_retry, _merge_provider_config
from app.providers.errors import ProviderUnavailableError
from app.providers.registry import get_provider
from app.routing.schema import StageRoute


async def run_paper_review_with_retry(
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
        provider = provider_getter(stage="paper_review", name=provider_name)
        for _ in range(_max_retry(config) + 1):
            try:
                result = await provider.run(payload=payload, config=config)
                return result, provider_name
            except ProviderUnavailableError as exc:
                if provider_name == "llm_openai" and not exc.stage:
                    exc.stage = "paper_review"
                if provider_name == "llm_openai" or exc.provider == "llm_openai":
                    raise
                last_exc = exc
                break
            except Exception as exc:
                last_exc = exc
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("paper_review stage has no available provider")
