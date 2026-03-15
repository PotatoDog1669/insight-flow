from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.collectors.base import BaseCollector, RawArticle
from app.models import Report, Source, UserSubscription
from app.scheduler import orchestrator as orchestrator_module
from app.scheduler.orchestrator import Orchestrator
from app.sinks.base import PublishResult

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
SOURCE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


class FakeCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "fake"

    @property
    def category(self) -> str:
        return "blog"

    async def collect(self, config: dict) -> list[RawArticle]:
        return [
            RawArticle(
                external_id="fake-ext-1",
                title="AI breakthrough today",
                url="https://example.com/post",
                content="New AI architecture improves multimodal reasoning and deployment efficiency.",
                published_at=datetime.now(timezone.utc),
            )
        ]


@pytest.mark.asyncio
async def test_notion_publish_trace_is_recorded(db_session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, _ = db_session_factory

    async with session_factory() as session:
        if await session.get(Source, SOURCE_ID) is None:
            session.add(
                Source(
                    id=SOURCE_ID,
                    name="E2E Source",
                    category="blog",
                    collect_method="rss",
                    config={},
                    enabled=True,
                    last_collected=None,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )

        existing_subscription = await session.execute(
            select(UserSubscription).where(
                UserSubscription.user_id == DEFAULT_USER_ID,
                UserSubscription.source_id == SOURCE_ID,
            )
        )
        if existing_subscription.scalar_one_or_none() is None:
            session.add(
                UserSubscription(
                    user_id=DEFAULT_USER_ID,
                    source_id=SOURCE_ID,
                    enabled=True,
                    custom_config={},
                )
            )
        await session.commit()

    monkeypatch.setattr(orchestrator_module, "get_collector", lambda method: FakeCollector())

    async def _mock_run_llm_json(prompt: str, config: dict | None = None) -> dict:
        lowered = prompt.lower()
        if '"keywords"' in prompt or "extract 5-8 high-signal keywords" in lowered:
            return {
                "keywords": ["ai", "agent", "benchmark"],
                "summary": "AI update relevant for engineering teams.",
            }
        return {"keep_indices": [0]}

    monkeypatch.setattr("app.providers.filter.run_llm_json", _mock_run_llm_json)
    monkeypatch.setattr("app.providers.keywords.run_llm_json", _mock_run_llm_json)

    class _ReportProvider:
        stage = "report"
        name = "llm_openai"

        async def run(self, payload: dict, config: dict | None = None) -> dict:
            return {
                "title": payload.get("title", "AI Daily Report"),
                "content": payload.get("content", ""),
                "global_tldr": payload.get("global_tldr", ""),
            }

    def _fake_get_provider(stage: str, name: str):
        if stage == "report":
            return _ReportProvider()
        raise KeyError(name)

    monkeypatch.setattr(orchestrator_module, "get_provider", _fake_get_provider)

    class _DatabaseSink:
        name = "database"

        async def publish(self, report, config):
            return PublishResult(success=True, sink_name=self.name, url="database://ok")

    class _NotionSink:
        name = "notion"

        async def publish(self, report, config):
            return PublishResult(success=True, sink_name=self.name, url="https://notion.so/page")

    def _fake_get_sink(target: str):
        if target == "database":
            return _DatabaseSink()
        return _NotionSink()

    monkeypatch.setattr(orchestrator_module, "get_sink", _fake_get_sink)

    orchestrator = Orchestrator(max_concurrency=2)
    async with session_factory() as session:
        result = await orchestrator.run_daily_pipeline(db=session, user_id=DEFAULT_USER_ID, trigger_type="manual")
        assert result["status"] == "success"
        assert result["reports_created"] >= 1

    async with session_factory() as session:
        reports = (
            await session.execute(
                select(Report).where(
                    Report.user_id == DEFAULT_USER_ID,
                    Report.report_date == date.today(),
                )
            )
        ).scalars().all()
        assert reports
        generated = max(reports, key=lambda report: report.created_at)
        assert generated.report_type == "daily"
        assert "database" in (generated.published_to or [])
        assert "notion" in (generated.published_to or [])
        assert generated.publish_trace
