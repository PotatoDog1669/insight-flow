import uuid

import pytest
from sqlalchemy import select

from app.models import Monitor
from app.scheduler.scheduler import daily_collect_and_report


@pytest.mark.asyncio
async def test_daily_collect_and_report_runs_enabled_monitors(db_session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
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
                custom_schedule=None,
                enabled=True,
                last_run=None,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    monkeypatch.setattr("app.scheduler.scheduler.async_session", session_factory)

    calls: list[tuple[str, str]] = []

    async def _fake_run_monitor_once(*, db, monitor, trigger_type: str):
        calls.append((str(monitor.id), trigger_type))

    monkeypatch.setattr("app.scheduler.scheduler.run_monitor_once", _fake_run_monitor_once, raising=False)

    await daily_collect_and_report()

    called_ids = {monitor_id for monitor_id, _ in calls}
    assert called_ids == {
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "cccccccc-cccc-cccc-cccc-cccccccccccc",
    }
    assert all(trigger_type == "scheduled" for _, trigger_type in calls)
