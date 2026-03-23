"""Compatibility helpers for monitor ai_routing payloads."""

from __future__ import annotations

from typing import Any

LLM_PROVIDER_NAMES = {"llm_codex", "llm_openai"}
MONITOR_LLM_STAGES = ("filter", "keywords", "global_summary", "paper_review", "paper_note", "report")
LEGACY_MONITOR_LLM_STAGES = ("filter", "keywords", "global_summary", "report")
PAPER_MONITOR_LLM_STAGES = ("paper_review", "paper_note")


def backfill_monitor_ai_routing(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    normalized = dict(payload)
    raw_stages = normalized.get("stages")
    stages = dict(raw_stages) if isinstance(raw_stages, dict) else {}
    raw_providers = normalized.get("providers")
    providers = dict(raw_providers) if isinstance(raw_providers, dict) else {}

    working_payload: dict[str, Any] = {}
    if stages:
        working_payload["stages"] = stages
    if providers:
        working_payload["providers"] = providers

    inferred_provider = infer_monitor_ai_provider(working_payload)
    if inferred_provider is None:
        return working_payload

    for stage_name in PAPER_MONITOR_LLM_STAGES:
        stage = stages.get(stage_name)
        if isinstance(stage, dict):
            primary = str(stage.get("primary") or "").strip()
            if primary in LLM_PROVIDER_NAMES:
                continue
        stages[stage_name] = {"primary": inferred_provider}
    working_payload["stages"] = stages
    return working_payload


def infer_monitor_ai_provider(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None

    providers: set[str] = set()
    stages = payload.get("stages")
    if isinstance(stages, dict):
        for stage_name in MONITOR_LLM_STAGES:
            stage = stages.get(stage_name)
            if not isinstance(stage, dict):
                continue
            primary = str(stage.get("primary") or "").strip()
            if primary in LLM_PROVIDER_NAMES:
                providers.add(primary)
    if len(providers) == 1:
        return next(iter(providers))

    provider_configs = payload.get("providers")
    if isinstance(provider_configs, dict):
        configured = [name for name in provider_configs if name in LLM_PROVIDER_NAMES]
        if len(configured) == 1:
            return configured[0]
    return None
