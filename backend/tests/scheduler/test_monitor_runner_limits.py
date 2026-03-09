from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select

from app.models import Monitor
from app.scheduler import monitor_runner as monitor_runner_module
from app.scheduler.monitor_runner import run_monitor_once


def _make_monitor(*, monitor_id: uuid.UUID, time_period: str) -> Monitor:
    now = datetime.now(timezone.utc)
    report_type = "daily" if time_period == "daily" else ("weekly" if time_period == "weekly" else "research")
    return Monitor(
        id=monitor_id,
        user_id=uuid.UUID("99999999-9999-9999-9999-999999999999"),
        name=f"Monitor-{time_period}",
        time_period=time_period,
        report_type=report_type,
        source_ids=["11111111-1111-1111-1111-111111111111"],
        source_overrides={},
        destination_ids=[],
        ai_routing={
            "stages": {
                "filter": {"primary": "agent_codex"},
                "report": {"primary": "llm_openai"},
            },
            "providers": {
                "agent_codex": {"model": "gpt-5-codex"},
                "llm_openai": {"model": "gpt-4o-mini"},
            },
        },
        custom_schedule=None,
        enabled=True,
        last_run=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("time_period", "expected_limit"),
    [
        ("daily", 5),
        ("weekly", 20),
        ("custom", 20),
    ],
)
async def test_run_monitor_once_passes_default_source_fetch_limit_by_time_period(
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
    time_period: str,
    expected_limit: int,
) -> None:
    session_factory, _ = db_session_factory

    monitor_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(_make_monitor(monitor_id=monitor_id, time_period=time_period))
        await session.commit()

    captured: dict = {}

    class _FakeOrchestrator:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def run_daily_pipeline(self, **kwargs):
            captured.update(kwargs)
            return {
                "sources": 1,
                "processed_articles": 0,
                "reports_created": 0,
                "status": "success",
                "source_tasks": [],
                "publish_reports": [],
                "window_hours": 24,
            }

    monkeypatch.setattr(monitor_runner_module, "Orchestrator", _FakeOrchestrator)

    async with session_factory() as session:
        monitor = (await session.execute(select(Monitor).where(Monitor.id == monitor_id))).scalars().one()
        await run_monitor_once(db=session, monitor=monitor, trigger_type="manual")

    assert captured["default_source_max_items"] == expected_limit
    assert captured["monitor_ai_routing"]["stages"]["filter"]["primary"] == "agent_codex"
    assert captured["monitor_ai_routing"]["stages"]["report"]["primary"] == "llm_openai"
    assert captured["monitor_ai_routing"]["providers"]["agent_codex"]["model"] == "gpt-5-codex"
    assert captured["monitor_ai_routing"]["providers"]["llm_openai"]["model"] == "gpt-4o-mini"
