"""定时任务调度器"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.scheduler.orchestrator import Orchestrator

scheduler = AsyncIOScheduler()


async def daily_collect_and_report():
    """每日采集 + 生成报告"""
    orchestrator = Orchestrator(max_concurrency=settings.collector_max_concurrency)
    await orchestrator.run_daily_pipeline()


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
