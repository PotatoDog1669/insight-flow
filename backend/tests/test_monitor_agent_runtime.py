"""Unit tests for the monitor agent runtime selection."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from app.agents.monitor_agent.runtime import DraftOutline, DraftPlan, MonitorAgentRuntime
from app.agents.monitor_agent.service import MonitorAgentService
from app.models import Source, User
from app.schemas.monitor_agent import MonitorAgentRequest, MonitorConversationState


def test_monitor_agent_runtime_falls_back_without_provider_config() -> None:
    runtime = MonitorAgentRuntime()
    state = MonitorConversationState(
        conversation_id="conv-fallback",
        clarify_turn_count=0,
        inferred_fields=[],
        expires_at=datetime.now(UTC),
    )

    result = asyncio.run(
        runtime.invoke(
            message="关注 agent 前沿内容",
            state=state,
            context=SimpleNamespace(provider_config=None, sources=[]),
        )
    )

    assert result.mode == "draft_plan"
    assert result.intent_summary == "关注 agent 前沿内容"


def test_monitor_agent_service_passes_llm_openai_provider_config_to_runtime(db_session_factory, monkeypatch) -> None:
    session_factory, _ = db_session_factory

    async def _seed_provider_settings() -> None:
        async with session_factory() as session:
            user = await session.get(User, uuid.UUID("99999999-9999-9999-9999-999999999999"))
            assert user is not None
            settings = dict(user.settings or {})
            settings["providers"] = {
                "llm_openai": {
                    "enabled": True,
                    "config": {
                        "api_key": "sk-test",
                        "base_url": "https://api.openai.com/v1",
                        "model": "gpt-4o-mini",
                        "timeout_sec": 30,
                        "max_retry": 1,
                        "max_output_tokens": 256,
                        "temperature": 0,
                    },
                }
            }
            user.settings = settings
            await session.commit()

    asyncio.run(_seed_provider_settings())

    captured: dict = {}

    async def _fake_invoke(self, *, message, state, context, on_text_delta=None):
        del on_text_delta
        captured["message"] = message
        captured["provider_config"] = context.provider_config
        return DraftPlan(
            mode="draft_plan",
            user_message="我先按当前理解给你一版可编辑的 monitor 草案。",
            intent_summary=message,
            inferred_fields=["ai_provider", "schedule"],
            draft_outline=DraftOutline(topic=message, source_types=["blog"], cadence_preference="medium"),
        )

    monkeypatch.setattr(MonitorAgentRuntime, "invoke", _fake_invoke)

    async def _run() -> None:
        async with session_factory() as session:
            service = MonitorAgentService()
            response = await service.handle_message(
                request=MonitorAgentRequest(message="关注 agent 前沿内容"),
                db=session,
            )
            assert response.mode == "draft"

    asyncio.run(_run())

    assert captured["message"] == "关注 agent 前沿内容"
    assert captured["provider_config"]["api_key"] == "sk-test"
    assert captured["provider_config"]["model"] == "gpt-4o-mini"


def test_monitor_agent_service_includes_more_than_three_candidate_sources_in_draft(
    db_session_factory, monkeypatch
) -> None:
    session_factory, _ = db_session_factory

    async def _seed_more_sources() -> None:
        async with session_factory() as session:
            now = datetime.now(UTC)
            session.add_all(
                [
                    Source(
                        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                        name="Agent Blog",
                        category="blog",
                        collect_method="rss",
                        config={"url": "https://example.com/agent-blog.xml"},
                        enabled=True,
                        created_at=now,
                        updated_at=now,
                    ),
                    Source(
                        id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
                        name="Agent X Watch",
                        category="social",
                        collect_method="rss",
                        config={"url": "https://example.com/agent-x.xml"},
                        enabled=True,
                        created_at=now,
                        updated_at=now,
                    ),
                    Source(
                        id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
                        name="Agent Research Feed",
                        category="academic",
                        collect_method="rss",
                        config={"url": "https://example.com/agent-research.xml"},
                        enabled=True,
                        created_at=now,
                        updated_at=now,
                    ),
                    Source(
                        id=uuid.UUID("55555555-5555-5555-5555-555555555555"),
                        name="Agent Product Updates",
                        category="blog",
                        collect_method="rss",
                        config={"url": "https://example.com/agent-product.xml"},
                        enabled=True,
                        created_at=now,
                        updated_at=now,
                    ),
                ]
            )
            await session.commit()

    asyncio.run(_seed_more_sources())

    async def _fake_invoke(self, *, message, state, context, on_text_delta=None):
        del self, message, state, on_text_delta
        return DraftPlan(
            mode="draft_plan",
            user_message="我先按当前理解给你一版可编辑的 monitor 草案。",
            intent_summary="关注 agent 前沿内容",
            inferred_fields=["sources", "schedule"],
            draft_outline=DraftOutline(
                topic="关注 agent 前沿内容",
                selected_source_ids=[str(source.id) for source in context.sources],
                source_types=["blog", "social", "academic"],
                cadence_preference="high",
            ),
        )

    monkeypatch.setattr(MonitorAgentRuntime, "invoke", _fake_invoke)

    async def _run() -> None:
        async with session_factory() as session:
            service = MonitorAgentService()
            response = await service.handle_message(
                request=MonitorAgentRequest(message="关注 agent 前沿内容"),
                db=session,
            )
            assert response.mode == "draft"
            assert len(response.monitor_payload.source_ids) == 5

    asyncio.run(_run())


def test_monitor_agent_service_compiles_social_source_overrides_into_monitor_payload(
    db_session_factory, monkeypatch
) -> None:
    session_factory, _ = db_session_factory
    x_source_id = uuid.UUID("66666666-6666-6666-6666-666666666666")
    reddit_source_id = uuid.UUID("77777777-7777-7777-7777-777777777777")

    async def _seed_social_sources() -> None:
        async with session_factory() as session:
            now = datetime.now(UTC)
            session.add_all(
                [
                    Source(
                        id=x_source_id,
                        name="X Watch",
                        category="social",
                        collect_method="twitter_snaplytics",
                        config={"usernames": ["OpenAI", "AnthropicAI", "LangChainAI"]},
                        enabled=True,
                        created_at=now,
                        updated_at=now,
                    ),
                    Source(
                        id=reddit_source_id,
                        name="Reddit",
                        category="social",
                        collect_method="rss",
                        config={"subreddits": ["LocalLLaMA", "OpenAI", "singularity"]},
                        enabled=True,
                        created_at=now,
                        updated_at=now,
                    ),
                ]
            )
            await session.commit()

    asyncio.run(_seed_social_sources())

    async def _fake_invoke(self, *, message, state, context, on_text_delta=None):
        del self, message, state, context, on_text_delta
        return DraftPlan(
            mode="draft_plan",
            user_message="我先按当前理解给你一版可编辑的 monitor 草案。",
            intent_summary="关注 agent 前沿内容",
            inferred_fields=["sources", "schedule"],
            draft_outline=DraftOutline(
                topic="关注 agent 前沿内容",
                selected_source_ids=[str(x_source_id), str(reddit_source_id)],
                source_types=["social"],
                cadence_preference="high",
                source_overrides={
                    str(x_source_id): {"usernames": ["OpenAI", "LangChainAI"]},
                    str(reddit_source_id): {"subreddits": ["r/LocalLLaMA", "openai", "OpenAI"]},
                },
            ),
        )

    monkeypatch.setattr(MonitorAgentRuntime, "invoke", _fake_invoke)

    async def _run() -> None:
        async with session_factory() as session:
            service = MonitorAgentService()
            response = await service.handle_message(
                request=MonitorAgentRequest(message="关注 agent 前沿内容"),
                db=session,
            )
            assert response.mode == "draft"
            assert response.monitor_payload.source_ids == [x_source_id, reddit_source_id]
            assert response.monitor_payload.source_overrides == {
                str(x_source_id): {"usernames": ["OpenAI", "LangChainAI"]},
                str(reddit_source_id): {"subreddits": ["LocalLLaMA", "openai"]},
            }

    asyncio.run(_run())


def test_monitor_agent_service_compiles_academic_keywords_into_monitor_payload(
    db_session_factory, monkeypatch
) -> None:
    session_factory, _ = db_session_factory
    academic_source_id = uuid.UUID("88888888-8888-8888-8888-888888888888")

    async def _seed_academic_source() -> None:
        async with session_factory() as session:
            now = datetime.now(UTC)
            session.add(
                Source(
                    id=academic_source_id,
                    name="arXiv",
                    category="academic",
                    collect_method="rss",
                    config={"keywords": ["agent", "reasoning"], "arxiv_api": True, "max_results": 25},
                    enabled=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

    asyncio.run(_seed_academic_source())

    async def _fake_invoke(self, *, message, state, context, on_text_delta=None):
        del self, message, state, context, on_text_delta
        return DraftPlan(
            mode="draft_plan",
            user_message="我先按当前理解给你一版可编辑的 monitor 草案。",
            intent_summary="追踪多模态 agent 论文进展",
            inferred_fields=["sources", "keywords", "schedule"],
            draft_outline=DraftOutline(
                topic="追踪多模态 agent 论文进展",
                selected_source_ids=[str(academic_source_id)],
                source_types=["academic"],
                cadence_preference="medium",
                source_overrides={
                    str(academic_source_id): {
                        "keywords": ["multimodal agents", "gui agents", "reasoning"],
                        "max_results": 40,
                    }
                },
            ),
        )

    monkeypatch.setattr(MonitorAgentRuntime, "invoke", _fake_invoke)

    async def _run() -> None:
        async with session_factory() as session:
            service = MonitorAgentService()
            response = await service.handle_message(
                request=MonitorAgentRequest(message="追踪多模态 agent 论文进展"),
                db=session,
            )
            assert response.mode == "draft"
            assert response.monitor_payload.source_ids == [academic_source_id]
            assert response.monitor_payload.source_overrides == {
                str(academic_source_id): {
                    "keywords": ["multimodal agents", "gui agents", "reasoning"],
                    "max_results": 40,
                }
            }

    asyncio.run(_run())


def test_monitor_agent_service_streams_status_events_message_deltas_and_final(monkeypatch) -> None:
    service = MonitorAgentService()
    final_response = None

    async def _fake_run_agent(*, request, db, on_text_delta=None):
        del request, db
        if on_text_delta is not None:
            await on_text_delta("请再")
        await asyncio.sleep(0)
        from app.schemas.monitor_agent import MonitorAgentClarifyResponse

        return MonitorAgentClarifyResponse(
            mode="clarify",
            conversation_id="conv-stream",
            message="请再具体一点",
            missing_or_conflicting_fields=["topic_scope"],
        )

    monkeypatch.setattr(service, "_run_agent", _fake_run_agent)

    async def _collect_events():
        nonlocal final_response
        events = []
        async for event in service.stream_message_events(
            request=MonitorAgentRequest(message="关注 agent"),
            db=SimpleNamespace(),
        ):
            events.append(event)
            if getattr(event, "type", None) == "final":
                final_response = event.response
        return events

    events = asyncio.run(_collect_events())

    assert events[0].type == "status"
    assert any(event.type == "message_delta" for event in events)
    assert events[-1].type == "final"
    assert final_response is not None
    assert final_response.mode == "clarify"
