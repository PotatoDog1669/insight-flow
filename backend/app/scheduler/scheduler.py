"""定时任务调度器"""

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import settings
from app.models.database import async_session
from app.models.monitor import Monitor
from app.scheduler.monitor_runner import run_monitor_once

scheduler = AsyncIOScheduler()
logger = structlog.get_logger()


async def daily_collect_and_report():
    """每日采集 + 生成报告"""
    async with async_session() as db:
        result = await db.execute(
            select(Monitor)
            .where(Monitor.enabled.is_(True))
            .order_by(Monitor.updated_at.desc())
        )
        monitors = result.scalars().all()
        for monitor in monitors:
            try:
                await run_monitor_once(db=db, monitor=monitor, trigger_type="scheduled")
            except Exception as exc:  # pragma: no cover - scheduler guard
                logger.warning("scheduled_monitor_run_failed", monitor_id=str(monitor.id), error=str(exc))


async def weekly_report():
    """每周生成周报"""
    # TODO: P1 实现
    pass


def init_scheduler():
    """初始化定时任务"""
    if scheduler.running:
        return
    hour, minute = settings.daily_collect_time.split(":")
    scheduler.add_job(
        daily_collect_and_report,
        trigger="cron",
        hour=int(hour),
        minute=int(minute),
        id="daily_collect",
        replace_existing=True,
    )

    # P1: 周报定时任务
    # scheduler.add_job(weekly_report, trigger="cron", ...)

    scheduler.start()


def shutdown_scheduler():
    """优雅关闭定时器。"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
