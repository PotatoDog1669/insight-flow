"""Unit tests for the LangChain-backed monitor agent runner."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

from langchain_core.messages import AIMessage

from app.models.source import Source
from app.schemas.monitor_agent import MonitorConversationState


def test_langchain_runner_builds_draft_plan_from_structured_response(monkeypatch) -> None:
    from app.agents.monitor_agent.langchain_runner import LangChainMonitorAgentResult, MonitorAgentLangChainRunner

    captured: dict = {}

    class _FakeGraph:
        async def ainvoke(self, payload, config=None):
            captured["payload"] = payload
            captured["config"] = config
            return {
                "structured_response": LangChainMonitorAgentResult(
                    mode="draft_plan",
                    intent_summary="关注 agent 前沿内容",
                    inferred_fields=["ai_provider", "schedule"],
                    selected_source_ids=["11111111-1111-1111-1111-111111111111"],
                    source_overrides={
                        "11111111-1111-1111-1111-111111111111": {
                            "keywords": ["agent", "reasoning"],
                            "max_results": 25,
                        }
                    },
                    source_types=["blog", "academic"],
                    cadence_preference="medium",
                    time_period="daily",
                    custom_schedule="0 9 * * *",
                )
            }

    def _fake_create_agent(**kwargs):
        captured["agent_kwargs"] = kwargs
        return _FakeGraph()

    def _fake_chat_openai(**kwargs):
        captured["model_kwargs"] = kwargs
        return object()

    monkeypatch.setattr("app.agents.monitor_agent.langchain_runner.create_agent", _fake_create_agent)
    monkeypatch.setattr("app.agents.monitor_agent.langchain_runner.ChatOpenAI", _fake_chat_openai)

    runner = MonitorAgentLangChainRunner(
        provider_config={
            "api_key": "sk-test",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "timeout_sec": 30,
            "max_retry": 1,
            "max_output_tokens": 256,
            "temperature": 0,
        },
        sources=[
            Source(
                id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
                name="Seed Source",
                category="blog",
                collect_method="rss",
                config={"url": "https://example.com/rss"},
                enabled=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        ],
    )

    plan = asyncio.run(
        runner.invoke(
            message="关注 agent 前沿内容",
            state=MonitorConversationState(
                conversation_id="conv-langchain",
                clarify_turn_count=0,
                inferred_fields=[],
                expires_at=datetime.now(UTC),
            ),
        )
    )

    assert plan.intent_summary == "关注 agent 前沿内容"
    assert plan.draft_outline.selected_source_ids == ["11111111-1111-1111-1111-111111111111"]
    assert plan.draft_outline.source_overrides["11111111-1111-1111-1111-111111111111"].keywords == ["agent", "reasoning"]
    assert plan.draft_outline.source_overrides["11111111-1111-1111-1111-111111111111"].max_results == 25
    assert captured["model_kwargs"]["model"] == "gpt-4o-mini"
    assert captured["model_kwargs"]["base_url"] == "https://api.openai.com/v1"
    assert captured["config"] == {"configurable": {"thread_id": "conv-langchain"}}
    assert "response_format" not in captured["agent_kwargs"]


def test_langchain_runner_parses_json_from_final_message_when_structured_output_is_unavailable(monkeypatch) -> None:
    from app.agents.monitor_agent.langchain_runner import MonitorAgentLangChainRunner

    class _FakeGraph:
        async def ainvoke(self, payload, config=None):
            del payload, config
            return {
                "messages": [
                    {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "mode": "draft_plan",
                                "intent_summary": "关注 agent 前沿内容",
                                "inferred_fields": ["ai_provider", "schedule"],
                                "selected_source_ids": ["11111111-1111-1111-1111-111111111111"],
                                "source_types": ["blog", "academic"],
                                "cadence_preference": "medium",
                                "time_period": "daily",
                                "custom_schedule": "0 9 * * *",
                            },
                            ensure_ascii=False,
                        )
                    }
                ]
            }

    monkeypatch.setattr("app.agents.monitor_agent.langchain_runner.create_agent", lambda **_: _FakeGraph())
    monkeypatch.setattr("app.agents.monitor_agent.langchain_runner.ChatOpenAI", lambda **_: object())

    runner = MonitorAgentLangChainRunner(
        provider_config={
            "api_key": "sk-test",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "timeout_sec": 30,
            "max_retry": 1,
            "max_output_tokens": 256,
            "temperature": 0,
        },
        sources=[
            Source(
                id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
                name="Seed Source",
                category="blog",
                collect_method="rss",
                config={"url": "https://example.com/rss"},
                enabled=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        ],
    )

    plan = asyncio.run(
        runner.invoke(
            message="关注 agent 前沿内容",
            state=MonitorConversationState(
                conversation_id="conv-json",
                clarify_turn_count=0,
                inferred_fields=[],
                expires_at=datetime.now(UTC),
            ),
        )
    )

    assert plan.intent_summary == "关注 agent 前沿内容"
    assert plan.draft_outline.selected_source_ids == ["11111111-1111-1111-1111-111111111111"]


def test_langchain_runner_parses_json_from_ai_message_objects(monkeypatch) -> None:
    from app.agents.monitor_agent.langchain_runner import MonitorAgentLangChainRunner

    class _FakeGraph:
        async def ainvoke(self, payload, config=None):
            del payload, config
            return {
                "messages": [
                    AIMessage(
                        content=json.dumps(
                            {
                                "mode": "draft_plan",
                                "intent_summary": "关注 agent 前沿内容",
                                "inferred_fields": ["ai_provider", "schedule"],
                                "selected_source_ids": ["11111111-1111-1111-1111-111111111111"],
                                "source_types": ["blog", "academic"],
                                "cadence_preference": "medium",
                                "time_period": "daily",
                                "custom_schedule": "0 9 * * *",
                            },
                            ensure_ascii=False,
                        ),
                        name="monitor_agent",
                    )
                ]
            }

    monkeypatch.setattr("app.agents.monitor_agent.langchain_runner.create_agent", lambda **_: _FakeGraph())
    monkeypatch.setattr("app.agents.monitor_agent.langchain_runner.ChatOpenAI", lambda **_: object())

    runner = MonitorAgentLangChainRunner(
        provider_config={
            "api_key": "sk-test",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "timeout_sec": 30,
            "max_retry": 1,
            "max_output_tokens": 256,
            "temperature": 0,
        },
        sources=[
            Source(
                id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
                name="Seed Source",
                category="blog",
                collect_method="rss",
                config={"url": "https://example.com/rss"},
                enabled=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        ],
    )

    plan = asyncio.run(
        runner.invoke(
            message="关注 agent 前沿内容",
            state=MonitorConversationState(
                conversation_id="conv-ai-message",
                clarify_turn_count=0,
                inferred_fields=[],
                expires_at=datetime.now(UTC),
            ),
        )
    )

    assert plan.intent_summary == "关注 agent 前沿内容"
    assert plan.draft_outline.selected_source_ids == ["11111111-1111-1111-1111-111111111111"]


def test_langchain_runner_streams_user_message_deltas_from_json_tokens(monkeypatch) -> None:
    from app.agents.monitor_agent.langchain_runner import MonitorAgentLangChainRunner

    streamed_deltas: list[str] = []
    final_json = json.dumps(
        {
            "mode": "draft_plan",
            "user_message": "我先按当前理解给你一版可编辑的 monitor 草案。",
            "intent_summary": "关注 agent 前沿内容",
            "inferred_fields": ["ai_provider", "schedule"],
            "selected_source_ids": ["11111111-1111-1111-1111-111111111111"],
            "source_types": ["blog", "academic"],
            "cadence_preference": "medium",
            "time_period": "daily",
            "custom_schedule": "0 9 * * *",
        },
        ensure_ascii=False,
    )

    class _Chunk:
        def __init__(self, content: str) -> None:
            self.content = content

    class _FakeGraph:
        async def astream(self, payload, config=None, stream_mode=None, version=None):
            del payload, config
            assert stream_mode == "messages"
            assert version == "v2"
            midpoint = len(final_json) // 2
            yield {"type": "messages", "data": (_Chunk(final_json[:midpoint]), {"langgraph_node": "model"})}
            yield {"type": "messages", "data": (_Chunk(final_json[midpoint:]), {"langgraph_node": "model"})}

    monkeypatch.setattr("app.agents.monitor_agent.langchain_runner.create_agent", lambda **_: _FakeGraph())
    monkeypatch.setattr("app.agents.monitor_agent.langchain_runner.ChatOpenAI", lambda **_: object())

    runner = MonitorAgentLangChainRunner(
        provider_config={
            "api_key": "sk-test",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "timeout_sec": 30,
            "max_retry": 1,
            "max_output_tokens": 256,
            "temperature": 0,
        },
        sources=[
            Source(
                id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
                name="Seed Source",
                category="blog",
                collect_method="rss",
                config={"url": "https://example.com/rss"},
                enabled=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        ],
    )

    async def _on_text_delta(delta: str) -> None:
        streamed_deltas.append(delta)

    plan = asyncio.run(
        runner.invoke(
            message="关注 agent 前沿内容",
            state=MonitorConversationState(
                conversation_id="conv-streaming",
                clarify_turn_count=0,
                inferred_fields=[],
                expires_at=datetime.now(UTC),
            ),
            on_text_delta=_on_text_delta,
        )
    )

    assert "".join(streamed_deltas) == "我先按当前理解给你一版可编辑的 monitor 草案。"
    assert plan.intent_summary == "关注 agent 前沿内容"


def test_langchain_runner_backfills_selected_sources_when_model_returns_too_few(monkeypatch) -> None:
    from app.agents.monitor_agent.langchain_runner import LangChainMonitorAgentResult, MonitorAgentLangChainRunner

    class _FakeGraph:
        async def ainvoke(self, payload, config=None):
            del payload, config
            return {
                "structured_response": LangChainMonitorAgentResult(
                    mode="draft_plan",
                    intent_summary="关注 agent 前沿内容",
                    inferred_fields=["ai_provider", "schedule"],
                    selected_source_ids=[
                        "11111111-1111-1111-1111-111111111111",
                        "22222222-2222-2222-2222-222222222222",
                        "33333333-3333-3333-3333-333333333333",
                    ],
                    source_types=["blog", "social", "academic"],
                    cadence_preference="medium",
                    time_period="daily",
                    custom_schedule="0 9 * * *",
                )
            }

    monkeypatch.setattr("app.agents.monitor_agent.langchain_runner.create_agent", lambda **_: _FakeGraph())
    monkeypatch.setattr("app.agents.monitor_agent.langchain_runner.ChatOpenAI", lambda **_: object())

    now = datetime.now(UTC)
    runner = MonitorAgentLangChainRunner(
        provider_config={
            "api_key": "sk-test",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "timeout_sec": 30,
            "max_retry": 1,
            "max_output_tokens": 256,
            "temperature": 0,
        },
        sources=[
            Source(
                id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
                name="OpenAI",
                category="blog",
                collect_method="rss",
                config={"feed_url": "https://openai.com/news/rss.xml"},
                enabled=True,
                created_at=now,
                updated_at=now,
            ),
            Source(
                id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                name="Anthropic",
                category="blog",
                collect_method="rss",
                config={"feed_url": "https://www.anthropic.com/news/rss.xml"},
                enabled=True,
                created_at=now,
                updated_at=now,
            ),
            Source(
                id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
                name="arXiv",
                category="academic",
                collect_method="rss",
                config={"keywords": ["agent", "reasoning"]},
                enabled=True,
                created_at=now,
                updated_at=now,
            ),
            Source(
                id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
                name="OpenRouter",
                category="blog",
                collect_method="rss",
                config={"feed_url": "https://openrouter.ai/blog/rss.xml"},
                enabled=True,
                created_at=now,
                updated_at=now,
            ),
            Source(
                id=uuid.UUID("55555555-5555-5555-5555-555555555555"),
                name="Reddit AI Agents",
                category="social",
                collect_method="rss",
                config={"subreddits": ["singularity", "localllama", "OpenAI"]},
                enabled=True,
                created_at=now,
                updated_at=now,
            ),
        ],
    )

    plan = asyncio.run(
        runner.invoke(
            message="关注 agent 前沿内容",
            state=MonitorConversationState(
                conversation_id="conv-backfill",
                clarify_turn_count=0,
                inferred_fields=[],
                expires_at=datetime.now(UTC),
            ),
        )
    )

    assert len(plan.draft_outline.selected_source_ids) == 5
    assert plan.draft_outline.selected_source_ids[:3] == [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
        "33333333-3333-3333-3333-333333333333",
    ]
