from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.models import Report, UserSubscription
from app.scheduler import orchestrator as orchestrator_module
from app.scheduler.orchestrator import Orchestrator
from app.sinks.base import PublishResult
from tests.scheduler.test_orchestrator_e2e import FakeCollector

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
SOURCE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_notion_publish_trace_is_recorded(db_session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, _ = db_session_factory

    async with session_factory() as session:
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

    async def _mock_run_codex_json(prompt: str, config: dict | None = None) -> dict:
        lowered = prompt.lower()
        if "keep_indices" in lowered:
            return {"keep_indices": [0]}
        if '"keywords"' in prompt or "extract 5-8 high-signal keywords" in lowered:
            return {
                "keywords": ["ai", "agent", "benchmark"],
                "summary": "AI update relevant for engineering teams.",
            }
        return {}

    monkeypatch.setattr("app.providers.filter.run_codex_json", _mock_run_codex_json)
    monkeypatch.setattr("app.providers.keywords.run_codex_json", _mock_run_codex_json)

    class _ReportProvider:
        stage = "report"
        name = "agent_codex"

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

    async with session_factory() as session:
        reports = (
            await session.execute(
                select(Report).where(
                    Report.user_id == DEFAULT_USER_ID,
                    Report.report_date == date.today(),
                )
            )
        ).scalars().all()
        generated = [report for report in reports if report.title != "Seed Daily Brief"]
        assert generated
        assert all(report.report_type == "daily" for report in generated)
        for report in generated:
            assert "database" in (report.published_to or [])
            assert "notion" in (report.published_to or [])
            assert report.publish_trace
