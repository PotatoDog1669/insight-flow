"""LangChain-backed runtime for the monitor agent."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Literal

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.agents.monitor_agent.runtime import (
    ClarifyPlan,
    DraftOutline,
    DraftPlan,
    DraftSourceOverride,
)
from app.collectors.reddit_config import normalize_reddit_subreddits
from app.models.source import Source
from app.schemas.monitor_agent import MonitorConversationState

_JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)
MIN_RECOMMENDED_SOURCE_COUNT = 5


class LangChainMonitorAgentResult(BaseModel):
    mode: Literal["clarify_plan", "draft_plan"]
    user_message: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    intent_summary: str | None = None
    inferred_fields: list[str] = Field(default_factory=list)
    selected_source_ids: list[str] = Field(default_factory=list)
    source_overrides: dict[str, DraftSourceOverride] = Field(default_factory=dict)
    source_types: list[Literal["blog", "social", "academic"]] = Field(default_factory=list)
    cadence_preference: Literal["high", "medium", "low"] | None = None
    time_period: Literal["daily", "weekly", "custom"] = "daily"
    custom_schedule: str | None = "0 9 * * *"


class MonitorAgentLangChainRunner:
    def __init__(self, *, provider_config: dict, sources: list[Source]) -> None:
        self._provider_config = dict(provider_config)
        self._sources = list(sources)

    async def invoke(
        self,
        *,
        message: str,
        state: MonitorConversationState,
        on_text_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> ClarifyPlan | DraftPlan:
        model = ChatOpenAI(
            model=str(self._provider_config["model"]),
            api_key=str(self._provider_config["api_key"]),
            base_url=str(self._provider_config["base_url"]),
            timeout=float(self._provider_config["timeout_sec"]),
            max_retries=int(self._provider_config["max_retry"]),
            temperature=float(self._provider_config["temperature"]),
            max_completion_tokens=int(self._provider_config["max_output_tokens"]),
        )
        agent = create_agent(
            model=model,
            tools=_build_tools(self._sources),
            system_prompt=_build_system_prompt(state=state),
            name="monitor_agent",
        )
        payload = {"messages": [{"role": "user", "content": message}]}
        config = {"configurable": {"thread_id": state.conversation_id}}
        if on_text_delta is None or not hasattr(agent, "astream"):
            result = await agent.ainvoke(payload, config=config)
        else:
            result = await self._astream_result(
                agent=agent,
                payload=payload,
                config=config,
                on_text_delta=on_text_delta,
            )
        structured = _parse_agent_result(result)
        structured = _ensure_minimum_source_coverage(
            result=structured,
            fallback_topic=message,
            sources=self._sources,
        )
        return _to_runtime_plan(structured)

    async def _astream_result(
        self,
        *,
        agent: object,
        payload: dict,
        config: dict,
        on_text_delta: Callable[[str], Awaitable[None]],
    ) -> dict:
        raw_output = ""
        extractor = _UserMessageStreamExtractor()

        async for event in agent.astream(payload, config=config, stream_mode="messages", version="v2"):
            if not isinstance(event, dict) or event.get("type") != "messages":
                continue
            data = event.get("data")
            if not isinstance(data, tuple) or len(data) != 2:
                continue
            chunk, _metadata = data
            text = _flatten_message_content(getattr(chunk, "content", None), strip=False)
            if not text:
                continue
            raw_output += text
            delta = extractor.feed(text)
            if delta:
                await on_text_delta(delta)

        return {"messages": [{"role": "assistant", "content": raw_output}]}


def _build_tools(sources: list[Source]) -> list:
    catalog = [_serialize_source(source) for source in sources]

    @tool
    def list_enabled_sources() -> list[dict]:
        """List the currently enabled sources available for this monitor draft."""
        return catalog

    @tool
    def get_monitor_defaults() -> dict:
        """Return default monitor settings that should be used unless the user specifies otherwise."""
        return {
            "ai_provider": "llm_openai",
            "time_period": "daily",
            "custom_schedule": "0 9 * * *",
            "window_hours": 24,
        }

    @tool
    def recommend_source_ids(topic: str) -> list[str]:
        """Recommend source ids for a topic using lightweight keyword matching over the source catalog."""
        return _recommend_source_ids(
            topic=topic,
            sources=catalog,
            limit=min(len(catalog), MIN_RECOMMENDED_SOURCE_COUNT),
        )

    return [list_enabled_sources, get_monitor_defaults, recommend_source_ids]


def _serialize_source(source: Source) -> dict:
    config = source.config if isinstance(source.config, dict) else {}
    target_url = str(config.get("url") or config.get("feed_url") or "").strip()
    available_usernames = (
        [item.strip() for item in config.get("usernames", []) if isinstance(item, str) and item.strip()]
        if isinstance(config.get("usernames"), list)
        else []
    )
    available_subreddits = normalize_reddit_subreddits(config.get("subreddits"))
    available_keywords = (
        [item.strip() for item in config.get("keywords", []) if isinstance(item, str) and item.strip()]
        if isinstance(config.get("keywords"), list)
        else []
    )
    default_max_results = config.get("max_results") if isinstance(config.get("max_results"), int) else None
    return {
        "id": str(source.id),
        "name": source.name,
        "category": source.category,
        "collect_method": source.collect_method,
        "target_url": target_url,
        "summary": _summarize_source_config(config),
        "available_usernames": available_usernames,
        "available_subreddits": available_subreddits,
        "available_keywords": available_keywords,
        "default_max_results": default_max_results,
    }


def _summarize_source_config(config: dict) -> str:
    for key in ("subreddits", "usernames", "categories", "keywords"):
        value = config.get(key)
        if isinstance(value, list) and value:
            items = ", ".join(str(item) for item in value[:3])
            return f"{key}: {items}"
    target_url = str(config.get("url") or config.get("feed_url") or "").strip()
    return target_url


def _recommend_source_ids(*, topic: str, sources: list[dict], limit: int) -> list[str]:
    normalized_topic = str(topic or "").lower()
    scored: list[tuple[int, str]] = []
    for source in sources:
        haystack = " ".join(
            [
                str(source.get("name") or ""),
                str(source.get("category") or ""),
                str(source.get("collect_method") or ""),
                str(source.get("summary") or ""),
                str(source.get("target_url") or ""),
            ]
        ).lower()
        score = 1
        for token in _topic_tokens(normalized_topic):
            if token and token in haystack:
                score += 2
        scored.append((score, str(source["id"])))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [source_id for _, source_id in scored[: max(0, limit)]]


def _topic_tokens(topic: str) -> list[str]:
    normalized = topic.replace("前沿", " frontier ").replace("agent", " agent ")
    tokens = [token.strip() for token in normalized.split() if token.strip()]
    return tokens[:8]


def _build_system_prompt(*, state: MonitorConversationState) -> str:
    clarify_budget = max(0, 2 - int(state.clarify_turn_count))
    return (
        "You configure monitor drafts for Insight Flow.\n"
        "Always call list_enabled_sources and get_monitor_defaults before finalizing the answer.\n"
        "Use recommend_source_ids when the topic needs source selection help.\n"
        "Prefer filling missing fields automatically. Ask a clarification question only when the request is too vague to produce a usable draft.\n"
        "When 5 or more enabled sources are available for a broad topic, return at least 5 selected_source_ids.\n"
        f"Remaining clarification budget: {clarify_budget}.\n"
        "Use ai_provider llm_openai by default.\n"
        "Always include a concise user_message in Chinese and place it immediately after mode in the JSON object.\n"
        "Return JSON only in the final answer. Do not add markdown or explanation text.\n"
        "The JSON schema is: "
        "{"
        '"mode":"clarify_plan|draft_plan",'
        '"user_message":"string",'
        '"missing_fields":["string"],'
        '"intent_summary":"string|null",'
        '"inferred_fields":["string"],'
        '"selected_source_ids":["string"],'
        '"source_overrides":{"source_id":{"usernames":["string"],"subreddits":["string"],"keywords":["string"],"max_items":1,"max_results":1}},'
        '"source_types":["blog|social|academic"],'
        '"cadence_preference":"high|medium|low|null",'
        '"time_period":"daily|weekly|custom",'
        '"custom_schedule":"string|null"'
        "}.\n"
        "When a selected source has available_usernames, you may return source_overrides[source_id].usernames using only that list.\n"
        "When a selected source has available_subreddits, you may return source_overrides[source_id].subreddits using only that list.\n"
        "When a selected source has available_keywords or is academic, you may return source_overrides[source_id].keywords as a short list of focused academic search terms.\n"
        "When a selected source has default_max_results or is academic, you may return source_overrides[source_id].max_results within 1..200.\n"
        "Only include source_overrides for selected_source_ids.\n"
        "When you return draft_plan, include user_message, intent_summary, selected_source_ids, time_period, custom_schedule, inferred_fields, and any applicable source_overrides."
    )


def _to_runtime_plan(result: LangChainMonitorAgentResult) -> ClarifyPlan | DraftPlan:
    if result.mode == "clarify_plan":
        return ClarifyPlan(
            mode="clarify_plan",
            user_message=result.user_message or "请补充你更想关注的主题范围。",
            missing_fields=result.missing_fields,
        )
    intent_summary = (result.intent_summary or "").strip()
    if not intent_summary:
        raise ValueError("LangChain runtime returned empty intent_summary")
    return DraftPlan(
        mode="draft_plan",
        user_message=result.user_message or "我先按当前理解给你一版可编辑的 monitor 草案。",
        intent_summary=intent_summary,
        inferred_fields=result.inferred_fields or ["ai_provider", "schedule"],
        draft_outline=DraftOutline(
            topic=intent_summary,
            selected_source_ids=result.selected_source_ids,
            source_overrides=result.source_overrides,
            source_types=result.source_types,
            cadence_preference=result.cadence_preference,
            time_period=result.time_period,
            custom_schedule=result.custom_schedule,
        ),
    )


def _ensure_minimum_source_coverage(
    *,
    result: LangChainMonitorAgentResult,
    fallback_topic: str,
    sources: list[Source],
) -> LangChainMonitorAgentResult:
    if result.mode != "draft_plan":
        return result

    minimum_count = min(len(sources), MIN_RECOMMENDED_SOURCE_COUNT)
    if minimum_count == 0 or len(result.selected_source_ids) >= minimum_count:
        return result

    catalog = [_serialize_source(source) for source in sources]
    ranked_source_ids = _recommend_source_ids(
        topic=result.intent_summary or fallback_topic,
        sources=catalog,
        limit=minimum_count,
    )
    merged_source_ids: list[str] = []
    for source_id in [*result.selected_source_ids, *ranked_source_ids]:
        if source_id and source_id not in merged_source_ids:
            merged_source_ids.append(source_id)
        if len(merged_source_ids) >= minimum_count:
            break
    return result.model_copy(update={"selected_source_ids": merged_source_ids})


def _parse_agent_result(result: dict) -> LangChainMonitorAgentResult:
    structured = result.get("structured_response")
    if structured is not None:
        return LangChainMonitorAgentResult.model_validate(structured)

    final_message = _extract_final_message_text(result.get("messages"))
    if not final_message:
        raise ValueError("LangChain runtime returned neither structured_response nor final assistant message")
    return LangChainMonitorAgentResult.model_validate(_parse_json_payload(final_message))


def _extract_final_message_text(messages: object) -> str:
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if isinstance(message, dict):
            role = str(message.get("role") or "")
            content = message.get("content")
            message_type = str(message.get("type") or "")
        else:
            role = str(getattr(message, "role", "") or "")
            content = getattr(message, "content", None)
            message_type = str(getattr(message, "type", "") or "")
        if role == "assistant" or message_type == "ai":
            return _flatten_message_content(content)
    return ""


def _flatten_message_content(content: object, *, strip: bool = True) -> str:
    if isinstance(content, str):
        return content.strip() if strip else content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            text = block.strip() if strip else block
        elif isinstance(block, dict):
            text = str(block.get("text") or "")
            if strip:
                text = text.strip()
        else:
            text = str(getattr(block, "text", "") or "")
            if strip:
                text = text.strip()
        if text:
            parts.append(text)
    return ("\n".join(parts)).strip() if strip else "".join(parts)


def _parse_json_payload(text: str) -> dict:
    candidates = [text.strip()]
    match = _JSON_BLOCK_PATTERN.search(text)
    if match:
        candidates.insert(0, match.group(1).strip())
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("LangChain runtime returned non-JSON final assistant message")


class _UserMessageStreamExtractor:
    _FIELD_PATTERN = re.compile(r'"user_message"\s*:\s*"')

    def __init__(self) -> None:
        self._raw = ""
        self._emitted = ""

    def feed(self, delta: str) -> str:
        self._raw += delta
        current = self._extract_current_value()
        if not current or len(current) <= len(self._emitted):
            return ""
        next_delta = current[len(self._emitted) :]
        self._emitted = current
        return next_delta

    def _extract_current_value(self) -> str:
        match = self._FIELD_PATTERN.search(self._raw)
        if match is None:
            return ""
        chars: list[str] = []
        index = match.end()
        escaping = False
        while index < len(self._raw):
            char = self._raw[index]
            index += 1
            if escaping:
                chars.append(_decode_json_escape(char))
                escaping = False
                continue
            if char == "\\":
                escaping = True
                continue
            if char == '"':
                break
            chars.append(char)
        return "".join(chars)


def _decode_json_escape(char: str) -> str:
    return {
        '"': '"',
        "\\": "\\",
        "/": "/",
        "b": "\b",
        "f": "\f",
        "n": "\n",
        "r": "\r",
        "t": "\t",
    }.get(char, char)
