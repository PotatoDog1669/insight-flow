"""Provider registry by stage and provider name."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

from app.providers.base import BaseStageProvider

_REGISTRY: dict[str, dict[str, BaseStageProvider]] = defaultdict(dict)
_LOADED = False


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    __import__("app.providers.filter")
    __import__("app.providers.global_summary")
    __import__("app.providers.keywords")
    __import__("app.providers.report")
    _LOADED = True


def register(stage: str, name: str) -> Callable[[type[BaseStageProvider]], type[BaseStageProvider]]:
    def decorator(cls: type[BaseStageProvider]) -> type[BaseStageProvider]:
        provider = cls()
        _REGISTRY[stage][name] = provider
        return cls

    return decorator


def get_provider(stage: str, name: str) -> BaseStageProvider:
    _ensure_loaded()
    try:
        return _REGISTRY[stage][name]
    except KeyError as exc:
        available = sorted(_REGISTRY.get(stage, {}).keys())
        raise KeyError(f"Provider not found for stage={stage}, name={name}, available={available}") from exc


def list_providers(stage: str) -> list[str]:
    _ensure_loaded()
    return sorted(_REGISTRY.get(stage, {}).keys())
