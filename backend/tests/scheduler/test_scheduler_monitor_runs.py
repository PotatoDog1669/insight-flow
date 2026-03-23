import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from app.models import CollectTask
from sqlalchemy import select

from app.models import Monitor
from app.scheduler import scheduler as scheduler_module


class FakeScheduler:
    def __init__(self) -> None:
        self.running = True
        self.jobs: dict[str, dict] = {}

    def add_job(self, func, trigger, id: str, replace_existing: bool = False, kwargs: dict | None = None):
        self.jobs[id] = {
            "func": func,
            "trigger": trigger,
            "kwargs": kwargs or {},
            "replace_existing": replace_existing,
        }

    def get_job(self, job_id: str):
        job = self.jobs.get(job_id)
        if job is None:
            return None
        return SimpleNamespace(id=job_id, **job)

    def get_jobs(self):
        return [SimpleNamespace(id=job_id, **job) for job_id, job in self.jobs.items()]

    def remove_job(self, job_id: str):
        self.jobs.pop(job_id, None)


@pytest.mark.asyncio
async def test_sync_all_monitor_schedules_registers_enabled_monitors(db_session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, _ = db_session_factory

    async with session_factory() as session:
        now = (await session.execute(select(Monitor))).scalars().first().updated_at
        session.add(
            Monitor(
                id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                user_id=uuid.UUID("99999999-9999-9999-9999-999999999999"),
                name="Disabled Monitor",
                time_period="daily",
                report_type="daily",
                source_ids=["11111111-1111-1111-1111-111111111111"],
                source_overrides={},
                destination_ids=[],
                custom_schedule=None,
                enabled=False,
                last_run=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            Monitor(
                id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
                user_id=uuid.UUID("99999999-9999-9999-9999-999999999999"),
                name="Second Enabled Monitor",
                time_period="daily",
                report_type="daily",
                source_ids=["11111111-1111-1111-1111-111111111111"],
                source_overrides={},
                destination_ids=["notion"],
                window_hours=24,
                custom_schedule="15 9 * * 3",
                enabled=True,
                last_run=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            Monitor(
                id=uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
                user_id=uuid.UUID("99999999-9999-9999-9999-999999999999"),
                name="Disabled Custom Monitor",
                time_period="custom",
                report_type="research",
                source_ids=["11111111-1111-1111-1111-111111111111"],
                source_overrides={},
                destination_ids=[],
                window_hours=24,
                custom_schedule=None,
                enabled=False,
                last_run=None,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    fake_scheduler = FakeScheduler()
    monkeypatch.setattr("app.scheduler.scheduler.async_session", session_factory)
    monkeypatch.setattr("app.scheduler.scheduler.scheduler", fake_scheduler)

    await scheduler_module.sync_all_monitor_schedules()

    assert set(fake_scheduler.jobs) == {
        "monitor:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "monitor:cccccccc-cccc-cccc-cccc-cccccccccccc",
    }
    assert fake_scheduler.jobs["monitor:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"]["kwargs"] == {
        "monitor_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    }
    assert "day_of_week='3'" in str(fake_scheduler.jobs["monitor:cccccccc-cccc-cccc-cccc-cccccccccccc"]["trigger"])


@pytest.mark.asyncio
async def test_upsert_monitor_schedule_replaces_existing_job_and_removes_disabled_monitor(
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory, _ = db_session_factory
    fake_scheduler = FakeScheduler()

    monkeypatch.setattr("app.scheduler.scheduler.async_session", session_factory)
    monkeypatch.setattr("app.scheduler.scheduler.scheduler", fake_scheduler)

    await scheduler_module.sync_all_monitor_schedules()
    original_trigger = str(fake_scheduler.jobs["monitor:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"]["trigger"])

    async with session_factory() as session:
        monitor = await session.get(Monitor, uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
        assert monitor is not None
        monitor.time_period = "weekly"
        monitor.custom_schedule = "45 18 * * 4"
        await session.commit()

    await scheduler_module.upsert_monitor_schedule(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))

    updated_trigger = str(fake_scheduler.jobs["monitor:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"]["trigger"])
    assert updated_trigger != original_trigger
    assert "day_of_week='4'" in updated_trigger

    async with session_factory() as session:
        monitor = await session.get(Monitor, uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
        assert monitor is not None
        monitor.enabled = False
        await session.commit()

    await scheduler_module.upsert_monitor_schedule(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
    assert "monitor:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" not in fake_scheduler.jobs


@pytest.mark.asyncio
async def test_upsert_custom_interval_schedule_registers_daily_trigger(
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory, _ = db_session_factory
    fake_scheduler = FakeScheduler()

    monkeypatch.setattr("app.scheduler.scheduler.async_session", session_factory)
    monkeypatch.setattr("app.scheduler.scheduler.scheduler", fake_scheduler)

    await scheduler_module.sync_all_monitor_schedules()

    async with session_factory() as session:
        monitor = await session.get(Monitor, uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
        assert monitor is not None
        monitor.time_period = "custom"
        monitor.custom_schedule = "interval:3@18:45"
        await session.commit()

    await scheduler_module.upsert_monitor_schedule(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))

    updated_trigger = str(fake_scheduler.jobs["monitor:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"]["trigger"])
    assert "hour='18'" in updated_trigger
    assert "minute='45'" in updated_trigger


@pytest.mark.asyncio
async def test_run_scheduled_monitor_skips_custom_interval_until_due(db_session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, _ = db_session_factory

    monkeypatch.setattr("app.scheduler.scheduler.async_session", session_factory)

    calls: list[tuple[str, str]] = []

    async def _fake_run_monitor_once(*, db, monitor, trigger_type: str):
        calls.append((str(monitor.id), trigger_type))

    monkeypatch.setattr("app.scheduler.scheduler.run_monitor_once", _fake_run_monitor_once, raising=False)

    async with session_factory() as session:
        monitor = await session.get(Monitor, uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
        assert monitor is not None
        recent_scheduled_run = datetime.now(timezone.utc)
        monitor.time_period = "custom"
        monitor.custom_schedule = "interval:3@06:30"
        monitor.last_run = recent_scheduled_run
        session.add(
            CollectTask(
                id=uuid.uuid4(),
                run_id=uuid.uuid4(),
                monitor_id=monitor.id,
                source_id=None,
                trigger_type="scheduled",
                status="success",
                started_at=recent_scheduled_run,
                finished_at=recent_scheduled_run,
                created_at=recent_scheduled_run,
            )
        )
        await session.commit()

    await scheduler_module.run_scheduled_monitor("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    assert calls == []


@pytest.mark.asyncio
async def test_run_scheduled_monitor_executes_monitor_once(db_session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, _ = db_session_factory

    monkeypatch.setattr("app.scheduler.scheduler.async_session", session_factory)

    calls: list[tuple[str, str]] = []

    async def _fake_run_monitor_once(*, db, monitor, trigger_type: str):
        calls.append((str(monitor.id), trigger_type))

    monkeypatch.setattr("app.scheduler.scheduler.run_monitor_once", _fake_run_monitor_once, raising=False)

    async with session_factory() as session:
        monitor = await session.get(Monitor, uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
        assert monitor is not None
        old_scheduled_run = datetime.now(timezone.utc) - timedelta(days=3)
        monitor.time_period = "custom"
        monitor.custom_schedule = "interval:2@06:30"
        monitor.last_run = old_scheduled_run
        session.add(
            CollectTask(
                id=uuid.uuid4(),
                run_id=uuid.uuid4(),
                monitor_id=monitor.id,
                source_id=None,
                trigger_type="scheduled",
                status="success",
                started_at=old_scheduled_run,
                finished_at=old_scheduled_run,
                created_at=old_scheduled_run,
            )
        )
        await session.commit()

    await scheduler_module.run_scheduled_monitor("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    assert calls == [("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "scheduled")]


@pytest.mark.asyncio
async def test_run_scheduled_monitor_ignores_recent_manual_run_for_custom_interval(
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory, _ = db_session_factory

    monkeypatch.setattr("app.scheduler.scheduler.async_session", session_factory)

    calls: list[tuple[str, str]] = []

    async def _fake_run_monitor_once(*, db, monitor, trigger_type: str):
        calls.append((str(monitor.id), trigger_type))

    monkeypatch.setattr("app.scheduler.scheduler.run_monitor_once", _fake_run_monitor_once, raising=False)

    async with session_factory() as session:
        monitor = await session.get(Monitor, uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
        assert monitor is not None
        old_scheduled_run = datetime.now(timezone.utc) - timedelta(days=2)
        recent_manual_run = datetime.now(timezone.utc)
        monitor.time_period = "custom"
        monitor.custom_schedule = "interval:1@06:30"
        monitor.last_run = recent_manual_run
        session.add(
            CollectTask(
                id=uuid.uuid4(),
                run_id=uuid.uuid4(),
                monitor_id=monitor.id,
                source_id=None,
                trigger_type="scheduled",
                status="success",
                started_at=old_scheduled_run,
                finished_at=old_scheduled_run,
                created_at=old_scheduled_run,
            )
        )
        session.add(
            CollectTask(
                id=uuid.uuid4(),
                run_id=uuid.uuid4(),
                monitor_id=monitor.id,
                source_id=None,
                trigger_type="manual",
                status="success",
                started_at=recent_manual_run,
                finished_at=recent_manual_run,
                created_at=recent_manual_run,
            )
        )
        await session.commit()

    await scheduler_module.run_scheduled_monitor("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    assert calls == [("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "scheduled")]
