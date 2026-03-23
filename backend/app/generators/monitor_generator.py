"""Deterministic draft and payload compilation for the monitor agent."""

from __future__ import annotations

import uuid
from collections.abc import Mapping

from app.collectors.reddit_config import normalize_reddit_subreddits
from app.models.source import Source
from app.schemas.monitor import MonitorCreate
from app.schemas.monitor_agent import DraftItem, DraftSection, MonitorDraft


class MonitorGenerator:
    def build_draft(
        self,
        *,
        topic: str,
        sources: list[Source],
        time_period: str = "daily",
        custom_schedule: str | None = "0 9 * * *",
    ) -> MonitorDraft:
        source_items = [
            DraftItem(
                key=f"source:{source.id}",
                type="source",
                label=source.name,
                source_id=str(source.id),
                status="ready",
                reason="来自当前系统中可直接绑定的 Source",
            )
            for source in sources
        ]
        sections: list[DraftSection] = []
        if source_items:
            sections.append(DraftSection(kind="source_list", title="推荐来源", items=source_items))
        schedule_label = _schedule_label_from_config(time_period=time_period, custom_schedule=custom_schedule)
        sections.append(
            DraftSection(
                kind="schedule",
                title="调度建议",
                items=[
                    DraftItem(
                        key=f"schedule:{time_period}:{custom_schedule or 'default'}",
                        type="schedule",
                        label=schedule_label,
                        status="ready",
                        time_period=time_period,  # type: ignore[arg-type]
                        custom_schedule=custom_schedule,
                    )
                ],
            )
        )
        return MonitorDraft(
            name=_draft_name_from_topic(topic),
            summary=f"围绕“{topic}”生成的首版监控草案。",
            sections=sections,
        )

    def compile_monitor_payload(
        self,
        draft: MonitorDraft,
        *,
        source_overrides: Mapping[str, Mapping[str, object]] | None = None,
    ) -> MonitorCreate:
        source_ids: list[uuid.UUID] = []
        time_period = "daily"
        custom_schedule = "0 9 * * *"
        for section in draft.sections:
            for item in section.items:
                if item.type == "source" and item.status == "ready" and item.source_id:
                    source_ids.append(uuid.UUID(item.source_id))
                if item.type == "schedule" and item.time_period:
                    time_period = item.time_period
                    custom_schedule = item.custom_schedule
        source_id_lookup = {str(source_id): source_id for source_id in source_ids}
        return MonitorCreate(
            name=draft.name,
            time_period=time_period,  # type: ignore[arg-type]
            report_type="daily",
            source_ids=source_ids,
            source_overrides=_normalize_source_overrides(
                source_overrides=source_overrides,
                selected_source_ids=set(source_id_lookup),
            ),
            ai_provider="llm_openai",
            window_hours=24,
            custom_schedule=custom_schedule,
            enabled=True,
        )

    def validate_monitor_payload(self, payload: MonitorCreate) -> MonitorCreate:
        return MonitorCreate.model_validate(payload.model_dump())


def _draft_name_from_topic(topic: str) -> str:
    stripped = topic.strip()
    if not stripped:
        return "New Monitor"
    words = stripped.split()
    if len(words) == 1:
        return f"{words[0].capitalize()} Monitor"
    title = " ".join(words[:4]).strip()
    if len(title) > 64:
        title = title[:64].rstrip()
    return title


def _schedule_label_from_config(*, time_period: str, custom_schedule: str | None) -> str:
    if time_period == "weekly":
        return "每周一次"
    if time_period == "custom" and custom_schedule:
        return f"Cron: {custom_schedule}"
    return "每天 09:00"


def _normalize_source_overrides(
    *,
    source_overrides: Mapping[str, Mapping[str, object]] | None,
    selected_source_ids: set[str],
) -> dict[str, dict]:
    if not source_overrides:
        return {}

    cleaned: dict[str, dict] = {}
    for source_id, raw_override in source_overrides.items():
        if source_id not in selected_source_ids or not isinstance(raw_override, Mapping):
            continue
        normalized = _normalize_single_source_override(raw_override)
        if normalized:
            cleaned[source_id] = normalized
    return cleaned


def _normalize_single_source_override(raw_override: Mapping[str, object]) -> dict:
    cleaned: dict[str, object] = {}

    max_items = _parse_positive_int(raw_override.get("max_items"))
    if max_items is not None:
        cleaned["max_items"] = max_items

    max_results = _parse_positive_int(raw_override.get("max_results"))
    if max_results is not None:
        cleaned["max_results"] = max_results

    keywords = _normalize_string_list(raw_override.get("keywords"))
    if keywords:
        cleaned["keywords"] = keywords

    usernames = _normalize_string_list(raw_override.get("usernames"))
    if usernames:
        cleaned["usernames"] = usernames

    subreddits = normalize_reddit_subreddits(raw_override.get("subreddits"))
    if subreddits:
        cleaned["subreddits"] = subreddits

    return cleaned


def _parse_positive_int(value: object) -> int | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            value = int(stripped)
    if isinstance(value, int) and 1 <= value <= 200:
        return value
    return None


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized
