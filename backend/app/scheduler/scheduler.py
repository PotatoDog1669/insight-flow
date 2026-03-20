"""Per-monitor task scheduler."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.config import settings
from app.models.database import async_session
from app.models.monitor import Monitor
from app.scheduler.monitor_runner import run_monitor_once

logger = structlog.get_logger()

MONITOR_JOB_PREFIX = "monitor:"
INTERVAL_SCHEDULE_PATTERN = re.compile(r"^interval:(\d{1,3})@(\d{1,2}):(\d{2})$", re.IGNORECASE)


def _scheduler_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.scheduler_timezone)
    except ZoneInfoNotFoundError:
        logger.warning("invalid_scheduler_timezone", timezone=settings.scheduler_timezone, fallback="UTC")
        return ZoneInfo("UTC")


scheduler = AsyncIOScheduler(timezone=_scheduler_timezone())


def _monitor_job_id(monitor_id: uuid.UUID | str) -> str:
    return f"{MONITOR_JOB_PREFIX}{monitor_id}"


def _normalize_weekday(raw_day: str) -> str:
    normalized = str(raw_day or "").strip().lower()
    aliases = {
        "0": "0",
        "7": "0",
        "sun": "0",
        "sunday": "0",
        "1": "1",
        "mon": "1",
        "monday": "1",
        "2": "2",
        "tue": "2",
        "tues": "2",
        "tuesday": "2",
        "3": "3",
        "wed": "3",
        "wednesday": "3",
        "4": "4",
        "thu": "4",
        "thur": "4",
        "thurs": "4",
        "thursday": "4",
        "5": "5",
        "fri": "5",
        "friday": "5",
        "6": "6",
        "sat": "6",
        "saturday": "6",
    }
    return aliases.get(normalized, "0")


def _parse_interval_schedule(raw_schedule: str | None) -> tuple[int, int, int] | None:
    normalized = str(raw_schedule or "").strip()
    match = INTERVAL_SCHEDULE_PATTERN.match(normalized)
    if not match:
        return None

    interval_days = max(1, min(365, int(match.group(1))))
    hour = int(match.group(2))
    minute = int(match.group(3))
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return interval_days, hour, minute


def _default_daily_crontab() -> str:
    hour_text, minute_text = settings.daily_collect_time.split(":")
    return f"{int(minute_text)} {int(hour_text)} * * *"


def _default_weekly_crontab() -> str:
    hour_text, minute_text = settings.weekly_report_time.split(":")
    weekday = _normalize_weekday(settings.weekly_report_day)
    return f"{int(minute_text)} {int(hour_text)} * * {weekday}"


def _resolve_monitor_crontab(monitor: Monitor) -> str | None:
    if not monitor.enabled:
        return None

    configured = str(monitor.custom_schedule or "").strip()
    if configured:
        return configured

    if monitor.time_period == "daily":
        return _default_daily_crontab()
    if monitor.time_period == "weekly":
        return _default_weekly_crontab()
    return None


def _remove_job_if_exists(job_id: str) -> None:
    if scheduler.get_job(job_id) is not None:
        scheduler.remove_job(job_id)


def _schedule_monitor_job(monitor: Monitor) -> None:
    job_id = _monitor_job_id(monitor.id)
    interval_schedule = _parse_interval_schedule(monitor.custom_schedule)
    if interval_schedule is not None:
        _, hour, minute = interval_schedule
        trigger = CronTrigger(hour=hour, minute=minute, timezone=_scheduler_timezone())
    else:
        crontab = _resolve_monitor_crontab(monitor)
        if not crontab:
            _remove_job_if_exists(job_id)
            return

        try:
            trigger = CronTrigger.from_crontab(crontab, timezone=_scheduler_timezone())
        except ValueError:
            logger.warning("invalid_monitor_schedule", monitor_id=str(monitor.id), custom_schedule=crontab)
            _remove_job_if_exists(job_id)
            return

    scheduler.add_job(
        run_scheduled_monitor,
        trigger=trigger,
        id=job_id,
        replace_existing=True,
        kwargs={"monitor_id": str(monitor.id)},
    )


async def run_scheduled_monitor(monitor_id: str) -> None:
    try:
        monitor_uuid = uuid.UUID(str(monitor_id))
    except ValueError:
        logger.warning("invalid_scheduled_monitor_id", monitor_id=str(monitor_id))
        return

    async with async_session() as db:
        monitor = await db.get(Monitor, monitor_uuid)
        if monitor is None:
            logger.warning("scheduled_monitor_missing", monitor_id=str(monitor_uuid))
            _remove_job_if_exists(_monitor_job_id(monitor_uuid))
            return
        if not monitor.enabled:
            logger.info("scheduled_monitor_disabled_skip", monitor_id=str(monitor_uuid))
            _remove_job_if_exists(_monitor_job_id(monitor_uuid))
            return
        interval_schedule = _parse_interval_schedule(monitor.custom_schedule)
        if interval_schedule is not None:
            interval_days, _, _ = interval_schedule
            last_run = monitor.last_run
            if last_run is not None:
                if last_run.tzinfo is None:
                    last_run = last_run.replace(tzinfo=timezone.utc)
                next_due_at = last_run + timedelta(days=interval_days)
                if datetime.now(timezone.utc) < next_due_at:
                    logger.info(
                        "scheduled_monitor_interval_skip",
                        monitor_id=str(monitor_uuid),
                        interval_days=interval_days,
                        next_due_at=next_due_at.isoformat(),
                    )
                    return
        try:
            await run_monitor_once(db=db, monitor=monitor, trigger_type="scheduled")
        except Exception as exc:  # pragma: no cover - scheduler guard
            logger.warning("scheduled_monitor_run_failed", monitor_id=str(monitor_uuid), error=str(exc))


async def sync_all_monitor_schedules() -> None:
    if not scheduler.running:
        return

    for job in scheduler.get_jobs():
        if str(job.id).startswith(MONITOR_JOB_PREFIX):
            scheduler.remove_job(job.id)

    async with async_session() as db:
        result = await db.execute(
            select(Monitor)
            .where(Monitor.enabled.is_(True))
            .order_by(Monitor.updated_at.desc())
        )
        monitors = result.scalars().all()
        for monitor in monitors:
            _schedule_monitor_job(monitor)


async def upsert_monitor_schedule(monitor_id: uuid.UUID) -> None:
    if not scheduler.running:
        return

    async with async_session() as db:
        monitor = await db.get(Monitor, monitor_id)
        if monitor is None or not monitor.enabled:
            _remove_job_if_exists(_monitor_job_id(monitor_id))
            return
        _schedule_monitor_job(monitor)


async def remove_monitor_schedule(monitor_id: uuid.UUID) -> None:
    if not scheduler.running:
        return
    _remove_job_if_exists(_monitor_job_id(monitor_id))


async def init_scheduler() -> None:
    """Initialize the scheduler and register enabled monitor jobs."""
    if scheduler.running:
        return
    scheduler.start()
    await sync_all_monitor_schedules()


def shutdown_scheduler() -> None:
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
