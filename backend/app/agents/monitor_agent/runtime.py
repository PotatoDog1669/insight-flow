"""Bounded runtime for the monitor agent."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from openai import OpenAIError
from pydantic import BaseModel, Field
from app.models.source import Source
from app.schemas.monitor_agent import MonitorConversationState


@dataclass(slots=True)
class MonitorAgentRuntimeContext:
    provider_config: dict | None
    sources: list[Source]


class DraftSourceOverride(BaseModel):
    max_items: int | None = Field(default=None, ge=1, le=200)
    max_results: int | None = Field(default=None, ge=1, le=200)
    keywords: list[str] | None = None
    usernames: list[str] | None = None
    subreddits: list[str] | None = None


class DraftOutline(BaseModel):
    topic: str
    selected_source_ids: list[str] = Field(default_factory=list)
    source_overrides: dict[str, DraftSourceOverride] = Field(default_factory=dict)
    source_types: list[Literal["blog", "social", "academic"]] = Field(default_factory=list)
    cadence_preference: Literal["high", "medium", "low"] | None = None
    time_period: Literal["daily", "weekly", "custom"] = "daily"
    custom_schedule: str | None = "0 9 * * *"


class ClarifyPlan(BaseModel):
    mode: Literal["clarify_plan"]
    user_message: str
    missing_fields: list[str] = Field(default_factory=list)


class DraftPlan(BaseModel):
    mode: Literal["draft_plan"]
    user_message: str | None = None
    intent_summary: str
    inferred_fields: list[str] = Field(default_factory=list)
    draft_outline: DraftOutline


class MonitorAgentRuntime:
    """LangChain-aligned runtime with a deterministic fallback.

    The backend environment in tests may not have LangChain installed.
    P0 keeps the runtime boundary here and falls back to deterministic planning
    until the real create_agent runtime is wired in.
    """

    provider_id = "llm_openai"

    async def invoke(
        self,
        *,
        message: str,
        state: MonitorConversationState,
        context: MonitorAgentRuntimeContext,
        on_text_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> ClarifyPlan | DraftPlan:
        if self._should_use_langchain(context.provider_config):
            plan = await self._invoke_with_langchain(
                message=message,
                state=state,
                context=context,
                on_text_delta=on_text_delta,
            )
            if plan is not None:
                return plan
        return self._invoke_fallback(message=message, state=state, context=context)

    def _should_use_langchain(self, provider_config: dict | None) -> bool:
        if not isinstance(provider_config, dict):
            return False
        api_key = str(provider_config.get("api_key") or "").strip()
        model = str(provider_config.get("model") or "").strip()
        return bool(api_key and model)

    async def _invoke_with_langchain(
        self,
        *,
        message: str,
        state: MonitorConversationState,
        context: MonitorAgentRuntimeContext,
        on_text_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> ClarifyPlan | DraftPlan | None:
        try:
            from app.agents.monitor_agent.langchain_runner import MonitorAgentLangChainRunner

            runner = MonitorAgentLangChainRunner(
                provider_config=context.provider_config or {},
                sources=context.sources,
            )
            return await runner.invoke(message=message, state=state, on_text_delta=on_text_delta)
        except (ImportError, RuntimeError, TypeError, ValueError, OpenAIError):
            return None

    def _invoke_fallback(
        self,
        *,
        message: str,
        state: MonitorConversationState,
        context: MonitorAgentRuntimeContext,
    ) -> ClarifyPlan | DraftPlan:
        normalized = " ".join(message.strip().split())
        if len(normalized) < 10 and state.clarify_turn_count < 2:
            return ClarifyPlan(
                mode="clarify_plan",
                user_message="我先按一个主题监控来理解。你更想关注公司/产品动态，还是论文和研究？",
                missing_fields=["topic_scope"],
            )
        topic = normalized[:80]
        selected_source_ids = [str(source.id) for source in context.sources]
        return DraftPlan(
            mode="draft_plan",
            user_message="我先按当前理解给你一版可编辑的 monitor 草案。",
            intent_summary=topic,
            inferred_fields=["ai_provider", "schedule"],
            draft_outline=DraftOutline(
                topic=topic,
                selected_source_ids=selected_source_ids,
                source_types=["blog", "social", "academic"],
                cadence_preference="medium",
                time_period="daily",
                custom_schedule="0 9 * * *",
            ),
        )
