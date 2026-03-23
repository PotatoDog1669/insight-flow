"""Application service for the monitor agent endpoint."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.monitor_agent.conversation_store import build_monitor_conversation_store
from app.agents.monitor_agent.runtime import (
    ClarifyPlan,
    DraftPlan,
    MonitorAgentRuntime,
    MonitorAgentRuntimeContext,
)
from app.config import settings
from app.generators.monitor_generator import MonitorGenerator
from app.models.source import Source
from app.models.user import User
from app.schemas.monitor_agent import (
    MonitorAgentClarifyResponse,
    MonitorAgentDraftResponse,
    MonitorAgentFinalEvent,
    MonitorAgentMessageDeltaEvent,
    MonitorAgentRequest,
    MonitorAgentStatusEvent,
)

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
MONITOR_AGENT_CANDIDATE_SOURCE_LIMIT = 12
MONITOR_AGENT_PROGRESS_STEPS = [
    ("understand", "理解需求"),
    ("scope", "补全监控范围"),
    ("sources", "匹配来源"),
    ("draft", "生成草案"),
]
MONITOR_AGENT_PROGRESS_WAIT_SECONDS = 0.45


class MonitorAgentService:
    def __init__(self) -> None:
        self._store = build_monitor_conversation_store()
        self._runtime = MonitorAgentRuntime()
        self._generator = MonitorGenerator()

    async def handle_message(
        self,
        *,
        request: MonitorAgentRequest,
        db: AsyncSession,
    ) -> MonitorAgentClarifyResponse | MonitorAgentDraftResponse:
        return await self._run_agent(request=request, db=db)

    async def stream_message_events(
        self,
        *,
        request: MonitorAgentRequest,
        db: AsyncSession,
    ) -> AsyncIterator[MonitorAgentStatusEvent | MonitorAgentMessageDeltaEvent | MonitorAgentFinalEvent]:
        message_queue: asyncio.Queue[str] = asyncio.Queue()
        streamed_delta_count = 0

        async def _on_text_delta(delta: str) -> None:
            if delta:
                await message_queue.put(delta)

        response_task = asyncio.create_task(self._run_agent(request=request, db=db, on_text_delta=_on_text_delta))
        completed_keys: set[str] = set()
        current_index = 0

        current_key, current_label = MONITOR_AGENT_PROGRESS_STEPS[current_index]
        yield MonitorAgentStatusEvent(key=current_key, label=current_label, status="running")

        while True:
            if response_task.done() and message_queue.empty():
                break

            try:
                delta = await asyncio.wait_for(message_queue.get(), timeout=MONITOR_AGENT_PROGRESS_WAIT_SECONDS)
            except TimeoutError:
                if response_task.done() or current_index >= len(MONITOR_AGENT_PROGRESS_STEPS) - 1:
                    continue
                completed_keys.add(current_key)
                yield MonitorAgentStatusEvent(key=current_key, label=current_label, status="completed")
                current_index += 1
                current_key, current_label = MONITOR_AGENT_PROGRESS_STEPS[current_index]
                yield MonitorAgentStatusEvent(key=current_key, label=current_label, status="running")
                continue

            streamed_delta_count += 1
            yield MonitorAgentMessageDeltaEvent(delta=delta)

        response = await response_task

        if current_key not in completed_keys:
            yield MonitorAgentStatusEvent(key=current_key, label=current_label, status="completed")

        if streamed_delta_count == 0:
            final_message = str(response.message or "").strip()
            if final_message:
                for chunk in _chunk_message(final_message):
                    yield MonitorAgentMessageDeltaEvent(delta=chunk)

        yield MonitorAgentFinalEvent(response=response)

    async def _run_agent(
        self,
        *,
        request: MonitorAgentRequest,
        db: AsyncSession,
        on_text_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> MonitorAgentClarifyResponse | MonitorAgentDraftResponse:
        state = await self._resolve_state(request)
        sources = await _load_candidate_sources(db)
        context = MonitorAgentRuntimeContext(
            provider_config=await _load_llm_openai_provider_config(db),
            sources=sources,
        )
        if on_text_delta is None:
            plan = await self._runtime.invoke(
                message=request.message,
                state=state,
                context=context,
            )
        else:
            plan = await self._runtime.invoke(
                message=request.message,
                state=state,
                context=context,
                on_text_delta=on_text_delta,
            )

        if isinstance(plan, ClarifyPlan):
            state.clarify_turn_count += 1
            await self._store.save(state)
            return MonitorAgentClarifyResponse(
                mode="clarify",
                conversation_id=state.conversation_id,
                message=plan.user_message,
                missing_or_conflicting_fields=plan.missing_fields,
            )

        selected_sources = _select_sources_for_plan(plan=plan, available_sources=sources)
        draft = self._generator.build_draft(
            topic=plan.intent_summary,
            sources=selected_sources,
            time_period=plan.draft_outline.time_period,
            custom_schedule=plan.draft_outline.custom_schedule,
        )
        payload = self._generator.compile_monitor_payload(
            draft,
            source_overrides={
                source_id: override.model_dump(exclude_none=True)
                for source_id, override in plan.draft_outline.source_overrides.items()
            },
        )
        payload = self._generator.validate_monitor_payload(payload)
        state.intent_summary = plan.intent_summary
        state.inferred_fields = list(plan.inferred_fields)
        await self._store.save(state)
        return MonitorAgentDraftResponse(
            mode="draft",
            conversation_id=state.conversation_id,
            message=plan.user_message or "我先按当前理解给你一版可编辑的 monitor 草案。",
            draft=draft,
            monitor_payload=payload,
            inferred_fields=plan.inferred_fields,
        )

    async def _resolve_state(self, request: MonitorAgentRequest):
        if request.conversation_id:
            existing = await self._store.load(request.conversation_id)
            if existing is not None:
                return existing
        return await self._store.create()


async def _load_candidate_sources(db: AsyncSession) -> list[Source]:
    stmt = (
        select(Source)
        .where(Source.enabled.is_(True))
        .order_by(Source.created_at.asc())
        .limit(MONITOR_AGENT_CANDIDATE_SOURCE_LIMIT)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _load_llm_openai_provider_config(db: AsyncSession) -> dict | None:
    user = await db.get(User, DEFAULT_USER_ID)
    if user is None:
        return None
    raw_providers = (user.settings or {}).get("providers", {})
    if not isinstance(raw_providers, dict):
        return None
    provider_state = raw_providers.get("llm_openai")
    if not isinstance(provider_state, dict) or not provider_state.get("enabled"):
        return None
    config = provider_state.get("config")
    if not isinstance(config, dict):
        return None
    return {
        "api_key": str(config.get("api_key") or "").strip(),
        "base_url": str(config.get("base_url") or "https://api.openai.com/v1").strip() or "https://api.openai.com/v1",
        "model": str(config.get("model") or settings.llm_primary_model or "gpt-4o-mini").strip() or "gpt-4o-mini",
        "timeout_sec": int(config.get("timeout_sec") or 120),
        "max_retry": int(config.get("max_retry") or 2),
        "max_output_tokens": int(config.get("max_output_tokens") or settings.llm_max_tokens or 2048),
        "temperature": float(config.get("temperature") if config.get("temperature") is not None else 0),
    }


def _select_sources_for_plan(*, plan: DraftPlan, available_sources: list[Source]) -> list[Source]:
    selected_source_ids = set(plan.draft_outline.selected_source_ids)
    if not selected_source_ids:
        return available_sources
    selected = [source for source in available_sources if str(source.id) in selected_source_ids]
    return selected or available_sources


def _chunk_message(message: str) -> list[str]:
    normalized = message.strip()
    if not normalized:
        return []
    chunk_size = 14
    return [normalized[index : index + chunk_size] for index in range(0, len(normalized), chunk_size)]
