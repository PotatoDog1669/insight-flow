"""采集流水线编排器"""

import asyncio
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Awaitable, Callable
import uuid

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import RawArticle
from app.collectors.registry import get_collector
from app.config import settings
from app.models.article import Article
from app.models.database import async_session
from app.models.report import Report
from app.models.source import Source
from app.models.subscription import UserSubscription
from app.models.task import CollectTask
from app.models.user import User
from app.providers.registry import get_provider
from app.processors.pipeline import ProcessedArticle, ProcessingPipeline
from app.renderers.base import RenderContext
from app.renderers.daily import DailyRenderer
from app.routing.loader import load_routing_profile
from app.routing.schema import StageRoute
from app.sinks.registry import get_sink, normalize_sink_name
from app.scheduler.task_events import append_task_event

logger = structlog.get_logger()

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


class Orchestrator:
    """采集流水线编排 — 全局采集 → 加工 → 分发 → 渲染 → 落盘"""

    def __init__(self, max_concurrency: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.routing_profile = load_routing_profile(settings.routing_default_profile)
        self.pipeline = ProcessingPipeline(routing_profile=self.routing_profile.name)
        self.provider_overrides: dict[str, dict] = {}
        self.daily_renderer = DailyRenderer()

    async def collect_source(
        self,
        source_id: str,
        method: str,
        config: dict,
        trace_emitter: Callable[[dict], Awaitable[None]] | None = None,
    ) -> tuple[list[RawArticle], list[dict]]:
        """采集单个信息源（带并发控制）"""
        async with self.semaphore:
            methods = list(config.get("fallback_chain") or [method])
            last_exc: Exception | None = None
            trace: list[dict] = []
            for idx, candidate in enumerate(methods):
                logger.info(
                    "collecting",
                    source_id=source_id,
                    method=candidate,
                    attempt=idx + 1,
                    total_attempts=len(methods),
                )
                collector = get_collector(candidate)
                try:
                    articles = await collector.collect({**config, "collect_method": candidate})
                    trace.append(
                        {
                            "stage": "collect",
                            "provider": candidate,
                            "status": "success",
                            "attempt": idx + 1,
                            "articles": len(articles),
                        }
                    )
                    if trace_emitter:
                        await trace_emitter(trace[-1])
                    return articles, trace
                except Exception as exc:  # pragma: no cover - defensive path
                    last_exc = exc
                    trace.append(
                        {
                            "stage": "collect",
                            "provider": candidate,
                            "status": "failed",
                            "attempt": idx + 1,
                            "error": str(exc)[:300],
                        }
                    )
                    if trace_emitter:
                        await trace_emitter(trace[-1])
                    logger.warning("collect_attempt_failed", source_id=source_id, method=candidate, error=str(exc))
                    continue
            if last_exc:
                raise last_exc
            return [], trace

    async def run_daily_pipeline(
        self,
        db: AsyncSession | None = None,
        user_id: uuid.UUID = DEFAULT_USER_ID,
        trigger_type: str = "scheduled",
        run_id: uuid.UUID | None = None,
        monitor_id: uuid.UUID | None = None,
        monitor_task_id: uuid.UUID | None = None,
        source_ids: list[uuid.UUID] | None = None,
        destination_ids: list[str] | None = None,
        source_overrides: dict[str, dict] | None = None,
        default_source_max_items: int | None = None,
        report_type: str = "daily",
        window_hours: int = 24,
    ) -> dict:
        """执行完整的每日采集编排"""
        if db is not None:
            return await self._run_daily_pipeline(
                db=db,
                user_id=user_id,
                trigger_type=trigger_type,
                run_id=run_id,
                monitor_id=monitor_id,
                monitor_task_id=monitor_task_id,
                source_ids=source_ids,
                destination_ids=destination_ids,
                source_overrides=source_overrides,
                default_source_max_items=default_source_max_items,
                report_type=report_type,
                window_hours=window_hours,
            )
        async with async_session() as session:
            return await self._run_daily_pipeline(
                db=session,
                user_id=user_id,
                trigger_type=trigger_type,
                run_id=run_id,
                monitor_id=monitor_id,
                monitor_task_id=monitor_task_id,
                source_ids=source_ids,
                destination_ids=destination_ids,
                source_overrides=source_overrides,
                default_source_max_items=default_source_max_items,
                report_type=report_type,
                window_hours=window_hours,
            )

    async def _run_daily_pipeline(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        trigger_type: str,
        run_id: uuid.UUID | None = None,
        monitor_id: uuid.UUID | None = None,
        monitor_task_id: uuid.UUID | None = None,
        source_ids: list[uuid.UUID] | None = None,
        destination_ids: list[str] | None = None,
        source_overrides: dict[str, dict] | None = None,
        default_source_max_items: int | None = None,
        report_type: str = "daily",
        window_hours: int = 24,
    ) -> dict:
        pipeline_run_id = run_id or uuid.uuid4()
        normalized_window_hours = window_hours if isinstance(window_hours, int) and 1 <= window_hours <= 168 else 24
        window_end = datetime.now(timezone.utc)
        window_start = window_end - timedelta(hours=normalized_window_hours)
        subscribed_sources = await self._load_subscribed_sources(db, user_id, source_ids=source_ids)
        if not subscribed_sources:
            if monitor_task_id is not None:
                await append_task_event(
                    db,
                    run_id=pipeline_run_id,
                    monitor_id=monitor_id,
                    task_id=monitor_task_id,
                    source_id=None,
                    stage="collect",
                    event_type="no_sources",
                    message="No subscribed sources available for this run",
                    payload={"source_ids": [str(item) for item in source_ids or []]},
                )
                await db.commit()
            return {
                "sources": 0,
                "processed_articles": 0,
                "reports_created": 0,
                "status": "success",
                "source_tasks": [],
                "publish_reports": [],
                "window_hours": normalized_window_hours,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
            }

        processed_articles: list[ProcessedArticle] = []
        persisted_article_ids: list[uuid.UUID] = []
        task_rows: dict[uuid.UUID, CollectTask] = {}
        source_name_by_id: dict[uuid.UUID, str] = {item.id: item.name for item in subscribed_sources}
        user = await db.get(User, user_id)
        destination_settings = self._extract_destination_settings(user.settings if user else {})
        provider_overrides = self._extract_provider_settings(user.settings if user else {})
        self.provider_overrides = provider_overrides
        self.pipeline.set_provider_overrides(provider_overrides)

        now = datetime.now(timezone.utc)
        for source in subscribed_sources:
            task = CollectTask(
                id=uuid.uuid4(),
                run_id=pipeline_run_id,
                monitor_id=monitor_id,
                source_id=source.id,
                trigger_type=trigger_type,
                status="pending",
                created_at=now,
            )
            task_rows[source.id] = task
            db.add(task)
        await db.commit()

        run_cancelled = False
        cancel_reason = "Run cancelled by user"
        source_configs = {
            source.id: self._resolve_source_config(
                source=source,
                source_overrides=source_overrides,
                default_source_max_items=default_source_max_items,
            )
            for source in subscribed_sources
        }
        collect_jobs: dict[uuid.UUID, asyncio.Task[tuple[list[RawArticle], list[dict]]]] = {}

        for source in subscribed_sources:
            if await self._is_monitor_run_cancelling(db, monitor_task_id=monitor_task_id):
                run_cancelled = True
                break

            task = task_rows[source.id]
            task.status = "running"
            task.started_at = datetime.now(timezone.utc)
            task.stage_trace = [
                {"stage": "collect", "provider": source.collect_method, "status": "running"},
            ]
            db.add(task)
            await append_task_event(
                db,
                run_id=pipeline_run_id,
                monitor_id=monitor_id,
                task_id=task.id,
                source_id=source.id,
                stage="collect",
                event_type="source_started",
                message=f"[{source.name}] collect started",
                payload={"source_name": source.name, "provider": source.collect_method},
            )
            await db.commit()

            collect_jobs[source.id] = asyncio.create_task(
                self.collect_source(
                    source_id=str(source.id),
                    method=source.collect_method,
                    config=source_configs[source.id],
                )
            )

        if not run_cancelled and collect_jobs:
            pending_jobs = dict(collect_jobs)
            while pending_jobs:
                done, _pending = await asyncio.wait(
                    set(pending_jobs.values()),
                    timeout=1.0,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for source_id, job in list(pending_jobs.items()):
                    if job in done:
                        pending_jobs.pop(source_id, None)

                if pending_jobs and await self._is_monitor_run_cancelling(db, monitor_task_id=monitor_task_id):
                    run_cancelled = True
                    for job in pending_jobs.values():
                        job.cancel()
                    await asyncio.gather(*pending_jobs.values(), return_exceptions=True)
                    break

        if run_cancelled:
            await self._finalize_cancelled_run(
                db=db,
                task_rows=task_rows,
                source_name_by_id=source_name_by_id,
                run_id=pipeline_run_id,
                monitor_id=monitor_id,
                monitor_task_id=monitor_task_id,
                reason=cancel_reason,
            )
            return {
                "sources": len(subscribed_sources),
                "processed_articles": len(processed_articles),
                "reports_created": 0,
                "status": "cancelled",
                "source_tasks": self._build_source_tasks(subscribed_sources=subscribed_sources, task_rows=task_rows),
                "publish_reports": [],
                "window_hours": normalized_window_hours,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
            }

        collected_by_source: dict[uuid.UUID, tuple[list[RawArticle], list[dict]]] = {}
        for source in subscribed_sources:
            task = task_rows[source.id]
            job = collect_jobs.get(source.id)
            if job is None:
                continue

            try:
                raw_articles, collect_trace = job.result()

                for trace_item in collect_trace:
                    status = str(trace_item.get("status", "unknown"))
                    await append_task_event(
                        db,
                        run_id=pipeline_run_id,
                        monitor_id=monitor_id,
                        task_id=task.id,
                        source_id=source.id,
                        stage="collect",
                        level="warning" if status == "failed" else "info",
                        event_type=f"collect_attempt_{status}",
                        message=f"[{source.name}] collect attempt {trace_item.get('attempt')} {status}",
                        payload=trace_item,
                    )
                await db.commit()

                for raw in raw_articles:
                    raw.metadata.setdefault("source_name", source.name)
                    raw.metadata.setdefault("source_category", source.category)
                collected_by_source[source.id] = (raw_articles, collect_trace)
            except Exception as exc:  # pragma: no cover - defensive path
                task.status = "failed"
                task.error_message = str(exc)[:1000]
                task.finished_at = datetime.now(timezone.utc)
                existing_trace = task.stage_trace or []
                task.stage_trace = [
                    *existing_trace,
                    {"stage": "collect", "provider": source.collect_method, "status": "failed", "error": str(exc)[:300]},
                    {"stage": "pipeline", "provider": "orchestrator", "status": "failed", "error": str(exc)[:300]},
                ]
                db.add(task)
                await append_task_event(
                    db,
                    run_id=pipeline_run_id,
                    monitor_id=monitor_id,
                    task_id=task.id,
                    source_id=source.id,
                    stage="collect",
                    level="error",
                    event_type="source_failed",
                    message=f"[{source.name}] source task failed",
                    payload={"error": str(exc)[:1000]},
                )
                await self._cancel_unfinished_sources_after_failure(
                    db=db,
                    task_rows=task_rows,
                    source_name_by_id=source_name_by_id,
                    failed_source_id=source.id,
                    run_id=pipeline_run_id,
                    monitor_id=monitor_id,
                    reason=f"Run aborted because [{source.name}] collect failed",
                )
                await db.commit()
                raise

        for source in subscribed_sources:
            if await self._is_monitor_run_cancelling(db, monitor_task_id=monitor_task_id):
                run_cancelled = True
                break

            task = task_rows[source.id]
            if task.status != "running":
                continue

            raw_articles, collect_trace = collected_by_source.get(source.id, ([], []))

            try:
                filtered_raw, filter_trace = await self._filter_raw_articles_by_window(
                    db=db,
                    source=source,
                    raw_articles=raw_articles,
                    window_start=window_start,
                    window_end=window_end,
                    window_hours=normalized_window_hours,
                )
                task.stage_trace = [
                    *collect_trace,
                    {
                        "stage": "window_filter",
                        "provider": "monitor_window",
                        "status": "running",
                        "window_hours": normalized_window_hours,
                        "window_start": window_start.isoformat(),
                        "window_end": window_end.isoformat(),
                    },
                ]
                db.add(task)
                await append_task_event(
                    db,
                    run_id=pipeline_run_id,
                    monitor_id=monitor_id,
                    task_id=task.id,
                    source_id=source.id,
                    stage="window_filter",
                    event_type="window_filter_completed",
                    message=f"[{source.name}] window filter {filter_trace.get('after', 0)}/{filter_trace.get('before', 0)} kept",
                    payload=filter_trace,
                )
                await append_task_event(
                    db,
                    run_id=pipeline_run_id,
                    monitor_id=monitor_id,
                    task_id=task.id,
                    source_id=source.id,
                    stage="process",
                    event_type="process_started",
                    message=f"[{source.name}] processing started",
                    payload={"input": len(filtered_raw)},
                )
                await db.commit()

                if await self._is_monitor_run_cancelling(db, monitor_task_id=monitor_task_id):
                    await self._mark_source_cancelled(
                        db=db,
                        task=task,
                        source=source,
                        run_id=pipeline_run_id,
                        monitor_id=monitor_id,
                        reason=cancel_reason,
                        stage="window_filter",
                    )
                    run_cancelled = True
                    break

                processed = await self.pipeline.process(filtered_raw)
                processing_trace = self._trace_dict_to_list(self.pipeline.last_stage_trace)
                task.stage_trace = [
                    *collect_trace,
                    filter_trace,
                    {"stage": "process", "provider": "pipeline", "status": "running", "articles": len(processed)},
                    {"stage": "persist", "provider": "database", "status": "running"},
                ]
                db.add(task)
                await append_task_event(
                    db,
                    run_id=pipeline_run_id,
                    monitor_id=monitor_id,
                    task_id=task.id,
                    source_id=source.id,
                    stage="process",
                    event_type="process_completed",
                    message=f"[{source.name}] processing completed",
                    payload={"output": len(processed), "trace": processing_trace},
                )
                await append_task_event(
                    db,
                    run_id=pipeline_run_id,
                    monitor_id=monitor_id,
                    task_id=task.id,
                    source_id=source.id,
                    stage="persist",
                    event_type="persist_started",
                    message=f"[{source.name}] persisting processed articles",
                    payload={"input": len(processed)},
                )
                await db.commit()

                if await self._is_monitor_run_cancelling(db, monitor_task_id=monitor_task_id):
                    await self._mark_source_cancelled(
                        db=db,
                        task=task,
                        source=source,
                        run_id=pipeline_run_id,
                        monitor_id=monitor_id,
                        reason=cancel_reason,
                        stage="process",
                    )
                    run_cancelled = True
                    break

                article_ids = await self._persist_processed_articles(
                    db, source, processed, processing_trace=processing_trace, trigger_type=trigger_type
                )
                persisted_article_ids.extend(article_ids)
                processed_articles.extend(processed)

                source.last_collected = datetime.now(timezone.utc)
                task.status = "success"
                task.articles_count = len(article_ids)
                task.finished_at = datetime.now(timezone.utc)
                task.stage_trace = [
                    *collect_trace,
                    filter_trace,
                    *processing_trace,
                    {"stage": "process", "provider": "pipeline", "status": "success", "articles": len(processed)},
                    {"stage": "persist", "provider": "database", "status": "success", "articles": len(article_ids)},
                ]
                db.add(source)
                db.add(task)
                await append_task_event(
                    db,
                    run_id=pipeline_run_id,
                    monitor_id=monitor_id,
                    task_id=task.id,
                    source_id=source.id,
                    stage="persist",
                    event_type="source_completed",
                    message=f"[{source.name}] source task completed",
                    payload={
                        "articles_persisted": len(article_ids),
                        "processed_articles": len(processed),
                        "status": task.status,
                    },
                )
                await db.commit()
            except Exception as exc:  # pragma: no cover - defensive path
                task.status = "failed"
                task.error_message = str(exc)[:1000]
                task.finished_at = datetime.now(timezone.utc)
                existing_trace = task.stage_trace or []
                task.stage_trace = [
                    *existing_trace,
                    {"stage": "process", "provider": "pipeline", "status": "failed", "error": str(exc)[:300]},
                    {"stage": "pipeline", "provider": "orchestrator", "status": "failed", "error": str(exc)[:300]},
                ]
                db.add(task)
                await append_task_event(
                    db,
                    run_id=pipeline_run_id,
                    monitor_id=monitor_id,
                    task_id=task.id,
                    source_id=source.id,
                    stage="process",
                    level="error",
                    event_type="source_failed",
                    message=f"[{source.name}] source task failed",
                    payload={"error": str(exc)[:1000]},
                )
                await self._cancel_unfinished_sources_after_failure(
                    db=db,
                    task_rows=task_rows,
                    source_name_by_id=source_name_by_id,
                    failed_source_id=source.id,
                    run_id=pipeline_run_id,
                    monitor_id=monitor_id,
                    reason=f"Run aborted because [{source.name}] processing failed",
                )
                await db.commit()
                raise

        if run_cancelled:
            await self._finalize_cancelled_run(
                db=db,
                task_rows=task_rows,
                source_name_by_id=source_name_by_id,
                run_id=pipeline_run_id,
                monitor_id=monitor_id,
                monitor_task_id=monitor_task_id,
                reason=cancel_reason,
            )
            return {
                "sources": len(subscribed_sources),
                "processed_articles": len(processed_articles),
                "reports_created": 0,
                "status": "cancelled",
                "source_tasks": self._build_source_tasks(subscribed_sources=subscribed_sources, task_rows=task_rows),
                "publish_reports": [],
                "window_hours": normalized_window_hours,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
            }

        if trigger_type == "test":
            report_ids, publish_status, publish_reports = [], "success", []
        else:
            report_ids, publish_status, publish_reports = await self._render_and_persist_reports(
                db=db,
                user_id=user_id,
                processed_articles=processed_articles,
                article_ids=persisted_article_ids,
                destination_ids=destination_ids,
                destination_settings=destination_settings,
                report_type=report_type,
                run_id=pipeline_run_id,
                monitor_id=monitor_id,
                monitor_task_id=monitor_task_id,
            )

        source_tasks = self._build_source_tasks(subscribed_sources=subscribed_sources, task_rows=task_rows)
        if monitor_task_id is not None:
            await append_task_event(
                db,
                run_id=pipeline_run_id,
                monitor_id=monitor_id,
                task_id=monitor_task_id,
                source_id=None,
                stage="monitor_run",
                event_type="pipeline_completed",
                message="Pipeline execution completed",
                payload={
                    "sources": len(subscribed_sources),
                    "processed_articles": len(processed_articles),
                    "reports_created": len(report_ids),
                    "status": publish_status,
                },
            )
            await db.commit()
        return {
            "sources": len(subscribed_sources),
            "processed_articles": len(processed_articles),
            "reports_created": len(report_ids),
            "status": publish_status,
            "source_tasks": source_tasks,
            "publish_reports": publish_reports,
            "window_hours": normalized_window_hours,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
        }

    async def _load_subscribed_sources(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        source_ids: list[uuid.UUID] | None = None,
    ) -> list[Source]:
        if source_ids:
            normalized_source_ids = [item for item in source_ids if isinstance(item, uuid.UUID)]
            if not normalized_source_ids:
                return []
            stmt = (
                select(Source)
                .where(Source.enabled.is_(True), Source.id.in_(normalized_source_ids))
                .order_by(Source.updated_at.desc())
            )
            result = await db.execute(stmt)
            sources = result.scalars().all()
            by_id = {source.id: source for source in sources}
            return [by_id[item] for item in normalized_source_ids if item in by_id]

        stmt = (
            select(Source)
            .join(UserSubscription, UserSubscription.source_id == Source.id)
            .where(
                and_(
                    UserSubscription.user_id == user_id,
                    UserSubscription.enabled.is_(True),
                    Source.enabled.is_(True),
                )
            )
            .order_by(Source.updated_at.desc())
        )
        result = await db.execute(stmt)
        sources = result.scalars().all()
        if sources:
            return sources

        fallback_stmt = select(Source).where(Source.enabled.is_(True)).order_by(Source.updated_at.desc()).limit(10)
        fallback_result = await db.execute(fallback_stmt)
        return fallback_result.scalars().all()

    async def _is_monitor_run_cancelling(self, db: AsyncSession, *, monitor_task_id: uuid.UUID | None) -> bool:
        if monitor_task_id is None:
            return False
        stmt = select(CollectTask.status).where(CollectTask.id == monitor_task_id).limit(1)
        current_status = (await db.execute(stmt)).scalar_one_or_none()
        if current_status is None:
            return False
        return str(current_status) in {"cancelling", "cancelled"}

    async def _mark_source_cancelled(
        self,
        *,
        db: AsyncSession,
        task: CollectTask,
        source: Source,
        run_id: uuid.UUID,
        monitor_id: uuid.UUID | None,
        reason: str,
        stage: str,
    ) -> None:
        trace = task.stage_trace or []
        trace.append({"stage": stage, "provider": "orchestrator", "status": "cancelled", "reason": reason})
        task.status = "cancelled"
        task.finished_at = datetime.now(timezone.utc)
        task.error_message = reason
        task.stage_trace = trace
        db.add(task)
        await append_task_event(
            db,
            run_id=run_id,
            monitor_id=monitor_id,
            task_id=task.id,
            source_id=source.id,
            stage="monitor_run",
            event_type="source_cancelled",
            message=f"[{source.name}] source task cancelled",
            payload={"reason": reason, "stage": stage},
        )
        await db.commit()

    async def _cancel_unfinished_sources_after_failure(
        self,
        *,
        db: AsyncSession,
        task_rows: dict[uuid.UUID, CollectTask],
        source_name_by_id: dict[uuid.UUID, str],
        failed_source_id: uuid.UUID,
        run_id: uuid.UUID,
        monitor_id: uuid.UUID | None,
        reason: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        for source_id, task in task_rows.items():
            if source_id == failed_source_id:
                continue
            if task.status not in {"pending", "running", "cancelling"}:
                continue

            trace = task.stage_trace or []
            trace.append({"stage": "monitor_run", "provider": "orchestrator", "status": "cancelled", "reason": reason})
            task.status = "cancelled"
            task.finished_at = now
            task.error_message = reason[:1000]
            task.stage_trace = trace
            db.add(task)
            await append_task_event(
                db,
                run_id=run_id,
                monitor_id=monitor_id,
                task_id=task.id,
                source_id=source_id,
                stage="monitor_run",
                event_type="source_cancelled",
                message=f"[{source_name_by_id.get(source_id, source_id)}] source task cancelled",
                payload={"reason": reason},
            )

        await db.commit()

    async def _finalize_cancelled_run(
        self,
        *,
        db: AsyncSession,
        task_rows: dict[uuid.UUID, CollectTask],
        source_name_by_id: dict[uuid.UUID, str],
        run_id: uuid.UUID,
        monitor_id: uuid.UUID | None,
        monitor_task_id: uuid.UUID | None,
        reason: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        for source_id, task in task_rows.items():
            if task.status not in {"pending", "running", "cancelling"}:
                continue
            trace = task.stage_trace or []
            trace.append({"stage": "monitor_run", "provider": "orchestrator", "status": "cancelled", "reason": reason})
            task.status = "cancelled"
            task.finished_at = now
            task.error_message = reason
            task.stage_trace = trace
            db.add(task)
            await append_task_event(
                db,
                run_id=run_id,
                monitor_id=monitor_id,
                task_id=task.id,
                source_id=source_id,
                stage="monitor_run",
                event_type="source_cancelled",
                message=f"[{source_name_by_id.get(source_id, source_id)}] source task cancelled",
                payload={"reason": reason},
            )

        if monitor_task_id is not None:
            await append_task_event(
                db,
                run_id=run_id,
                monitor_id=monitor_id,
                task_id=monitor_task_id,
                source_id=None,
                stage="monitor_run",
                event_type="run_cancelled",
                message="Monitor run cancelled",
                payload={"reason": reason},
            )
        await db.commit()

    @staticmethod
    def _build_source_tasks(*, subscribed_sources: list[Source], task_rows: dict[uuid.UUID, CollectTask]) -> list[dict]:
        source_tasks: list[dict] = []
        for source in subscribed_sources:
            task = task_rows[source.id]
            source_tasks.append(
                {
                    "source_id": str(source.id),
                    "status": task.status,
                    "articles_count": int(task.articles_count or 0),
                    "error_message": task.error_message,
                    "stage_trace": task.stage_trace or [],
                }
            )
        return source_tasks

    @staticmethod
    def _resolve_source_config(
        source: Source,
        source_overrides: dict[str, dict] | None = None,
        default_source_max_items: int | None = None,
    ) -> dict:
        config = dict(source.config or {})
        resolved_max_items = default_source_max_items if isinstance(default_source_max_items, int) and 1 <= default_source_max_items <= 200 else None
        if not isinstance(source_overrides, dict):
            if resolved_max_items is not None:
                config = Orchestrator._apply_source_max_items(config=config, source=source, max_items=resolved_max_items)
            return config

        override = source_overrides.get(str(source.id))
        if not isinstance(override, dict):
            if resolved_max_items is not None:
                config = Orchestrator._apply_source_max_items(config=config, source=source, max_items=resolved_max_items)
            return config

        raw_max_items = override.get("max_items")
        if isinstance(raw_max_items, str):
            raw_max_items = raw_max_items.strip()
            if raw_max_items.isdigit():
                raw_max_items = int(raw_max_items)
        if isinstance(raw_max_items, int) and 1 <= raw_max_items <= 200:
            resolved_max_items = raw_max_items

        if source.collect_method == "huggingface":
            raw_limit = override.get("limit")
            if isinstance(raw_limit, str):
                raw_limit = raw_limit.strip()
                if raw_limit.isdigit():
                    raw_limit = int(raw_limit)
            if resolved_max_items is None and isinstance(raw_limit, int) and 1 <= raw_limit <= 200:
                resolved_max_items = raw_limit

        if source.collect_method == "rss" and bool(config.get("arxiv_api")):
            raw_max_results = override.get("max_results")
            if isinstance(raw_max_results, str):
                raw_max_results = raw_max_results.strip()
                if raw_max_results.isdigit():
                    raw_max_results = int(raw_max_results)
            if resolved_max_items is None and isinstance(raw_max_results, int) and 1 <= raw_max_results <= 200:
                resolved_max_items = raw_max_results

            raw_keywords = override.get("keywords")
            keywords: list[str] = []
            if isinstance(raw_keywords, str):
                keywords = [item.strip() for item in raw_keywords.split(",") if item.strip()]
            elif isinstance(raw_keywords, list):
                for item in raw_keywords:
                    if not isinstance(item, str):
                        continue
                    value = item.strip()
                    if value:
                        keywords.append(value)
            if keywords:
                config["keywords"] = list(dict.fromkeys(keywords))[:20]

        if source.collect_method == "twitter_snaplytics":
            raw_usernames = override.get("usernames")
            usernames: list[str] = []
            if isinstance(raw_usernames, list):
                for item in raw_usernames:
                    if not isinstance(item, str):
                        continue
                    value = item.strip()
                    if value and value not in usernames:
                        usernames.append(value)
            if usernames:
                config["usernames"] = usernames

        if resolved_max_items is not None:
            config = Orchestrator._apply_source_max_items(config=config, source=source, max_items=resolved_max_items)
        return config

    @staticmethod
    def _apply_source_max_items(*, config: dict, source: Source, max_items: int) -> dict:
        if not isinstance(max_items, int) or not (1 <= max_items <= 200):
            return config

        config["max_items"] = max_items

        method = str(source.collect_method or "")
        if method in {"huggingface", "github_trending"}:
            config["limit"] = max_items
        if method == "rss" and bool(config.get("arxiv_api")):
            # Keep arXiv API max_results aligned with fetch cap.
            config["max_results"] = max_items
        return config

    async def _filter_raw_articles_by_window(
        self,
        *,
        db: AsyncSession,
        source: Source,
        raw_articles: list[RawArticle],
        window_start: datetime,
        window_end: datetime,
        window_hours: int,
    ) -> tuple[list[RawArticle], dict]:
        if not raw_articles:
            return [], {
                "stage": "window_filter",
                "provider": "monitor_window",
                "status": "success",
                "window_hours": window_hours,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "before": 0,
                "after": 0,
                "outside_window": 0,
                "first_seen_fallback": 0,
                "missing_event_time": 0,
                "allow_first_seen_fallback": False,
            }

        kept: list[RawArticle] = []
        pending_first_seen: list[RawArticle] = []
        outside_window = 0
        snapshot_after_window_end = 0
        missing_event_time = 0
        now_utc = datetime.now(timezone.utc)
        source_config = source.config if isinstance(source.config, dict) else {}
        allow_first_seen_fallback = bool(source_config.get("window_allow_first_seen_fallback", False))

        for raw in raw_articles:
            published_event_time = self._normalize_datetime(raw.published_at)
            snapshot_event_time = None
            if published_event_time is None:
                metadata = raw.metadata if isinstance(raw.metadata, dict) else {}
                snapshot_event_time = self._normalize_datetime(metadata.get("snapshot_at"))
            event_time = published_event_time or snapshot_event_time
            if event_time is None:
                if allow_first_seen_fallback:
                    pending_first_seen.append(raw)
                else:
                    outside_window += 1
                    missing_event_time += 1
                continue
            if window_start <= event_time <= window_end:
                kept.append(raw)
            elif (
                published_event_time is None
                and snapshot_event_time is not None
                and window_start <= snapshot_event_time <= now_utc
            ):
                # Sources like GitHub Trending / HF Daily use snapshot_at as event time.
                # When run window_end is captured at run start, source collection that
                # happens later should still be considered in-window for this run.
                kept.append(raw)
                snapshot_after_window_end += 1
            else:
                outside_window += 1

        first_seen_kept = 0
        if pending_first_seen:
            existing_external_ids: set[str] = set()
            candidate_ids = [item.external_id for item in pending_first_seen if item.external_id]
            if candidate_ids:
                stmt = select(Article.external_id).where(
                    and_(
                        Article.source_id == source.id,
                        Article.external_id.in_(candidate_ids),
                    )
                )
                result = await db.execute(stmt)
                existing_external_ids = {str(item) for item in result.scalars().all() if item}

            for item in pending_first_seen:
                if not item.external_id or item.external_id not in existing_external_ids:
                    kept.append(item)
                    first_seen_kept += 1

        trace = {
            "stage": "window_filter",
            "provider": "monitor_window",
            "status": "success",
            "window_hours": window_hours,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "before": len(raw_articles),
            "after": len(kept),
            "outside_window": outside_window,
            "first_seen_fallback": first_seen_kept,
            "snapshot_after_window_end": snapshot_after_window_end,
            "missing_event_time": missing_event_time,
            "allow_first_seen_fallback": allow_first_seen_fallback,
        }
        return kept, trace

    @staticmethod
    def _raw_event_time(raw: RawArticle) -> datetime | None:
        published = Orchestrator._normalize_datetime(raw.published_at)
        if published is not None:
            return published

        metadata = raw.metadata if isinstance(raw.metadata, dict) else {}
        snapshot = metadata.get("snapshot_at")
        return Orchestrator._normalize_datetime(snapshot)

    @staticmethod
    def _normalize_datetime(raw: object) -> datetime | None:
        if isinstance(raw, datetime):
            if raw.tzinfo is None:
                return raw.replace(tzinfo=timezone.utc)
            return raw.astimezone(timezone.utc)
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return None
            if text.endswith("Z"):
                text = f"{text[:-1]}+00:00"
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                return None
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        return None

    async def _persist_processed_articles(
        self,
        db: AsyncSession,
        source: Source,
        processed_articles: list[ProcessedArticle],
        processing_trace: list[dict] | None = None,
        trigger_type: str = "scheduled",
    ) -> list[uuid.UUID]:
        if trigger_type == "test":
            # For test runs, do not persist to database, return dummy UUIDs
            return [uuid.uuid4() for _ in processed_articles]

        article_ids: list[uuid.UUID] = []
        now = datetime.now(timezone.utc)
        for item in processed_articles:
            raw = item.raw
            stmt = select(Article).where(
                and_(
                    Article.source_id == source.id,
                    Article.external_id == raw.external_id,
                )
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()
            if existing is None:
                existing = Article(
                    id=uuid.uuid4(),
                    source_id=source.id,
                    external_id=raw.external_id,
                    title=raw.title,
                    url=raw.url,
                    raw_content=raw.content,
                    summary=item.summary,
                    keywords=item.keywords,
                    ai_score=item.score,
                    status="processed",
                    source_type="primary",
                    metadata_=raw.metadata or {},
                    processing_trace=processing_trace or [],
                    published_at=raw.published_at,
                    collected_at=now,
                    created_at=now,
                    updated_at=now,
                )
            else:
                existing.title = raw.title
                existing.url = raw.url
                existing.raw_content = raw.content
                existing.summary = item.summary
                existing.keywords = item.keywords
                existing.ai_score = item.score
                existing.status="processed"
                existing.metadata_=raw.metadata or {}
                existing.processing_trace=processing_trace or []
                existing.published_at=raw.published_at
                existing.collected_at=now
                existing.updated_at=now
            db.add(existing)
            await db.flush()
            article_ids.append(existing.id)
        await db.commit()
        return article_ids

    async def _render_and_persist_reports(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        processed_articles: list[ProcessedArticle],
        article_ids: list[uuid.UUID],
        destination_ids: list[str] | None = None,
        destination_settings: dict[str, dict] | None = None,
        report_type: str = "daily",
        run_id: uuid.UUID | None = None,
        monitor_id: uuid.UUID | None = None,
        monitor_task_id: uuid.UUID | None = None,
    ) -> tuple[list[uuid.UUID], str, list[dict]]:
        if not processed_articles:
            return [], "success", []

        today = date.today()
        context = RenderContext(date=today.isoformat(), user_id=str(user_id))
        daily_report = await self.daily_renderer.render(processed_articles, context)

        categories = sorted(
            {
                str(item.raw.metadata.get("source_category"))
                for item in processed_articles
                if item.raw.metadata.get("source_category")
            }
        )
        topic_counts: Counter[str] = Counter()
        for item in processed_articles:
            for keyword in item.keywords[:3]:
                topic_counts[keyword] += 1
        topics = [{"name": topic, "weight": weight} for topic, weight in topic_counts.most_common(10)]
        fallback_tldr = [item.summary for item in processed_articles[:8] if item.summary]
        daily_metadata = dict(daily_report.metadata or {})
        global_tldr = str(daily_metadata.get("global_tldr") or "").strip()
        report_output, report_provider = await self._run_report_with_retry(
            route=self.routing_profile.stages.report,
            payload={
                "title": daily_report.title,
                "content": daily_report.content,
                "events": daily_metadata.get("events", []),
                "global_tldr": global_tldr,
                "date": context.date,
            },
        )
        generated_title = str(report_output.get("title") or "").strip()
        generated_content = str(report_output.get("content") or "").strip()
        generated_tldr = str(report_output.get("global_tldr") or "").strip()
        if generated_title:
            daily_report.title = generated_title
        if generated_content:
            daily_report.content = generated_content
        if generated_tldr:
            global_tldr = generated_tldr
            daily_metadata["global_tldr"] = generated_tldr
            daily_metadata["tldr"] = [generated_tldr]
        daily_metadata["report_provider"] = report_provider
        daily_report.metadata = daily_metadata
        deep_tldr = [global_tldr] if global_tldr else fallback_tldr
        deep_categories = daily_metadata.get("categories")
        if not isinstance(deep_categories, list) or not deep_categories:
            deep_categories = categories
        deep_events = daily_metadata.get("events")
        if not isinstance(deep_events, list):
            deep_events = []
        article_id_strings = [str(item) for item in article_ids]
        selected_report_type = _normalize_report_type(report_type)
        selected_time_period = "daily"
        if selected_report_type == "weekly":
            selected_time_period = "weekly"
        elif selected_report_type == "research":
            selected_time_period = "custom"

        report_rows = [
            Report(
                id=uuid.uuid4(),
                user_id=user_id,
                time_period=selected_time_period,
                report_type=selected_report_type,
                title=daily_report.title,
                content=daily_report.content,
                article_ids=article_id_strings,
                metadata_={
                    "categories": deep_categories,
                    "tldr": deep_tldr,
                    "topics": topics,
                    "report_type": selected_report_type,
                    "events": deep_events,
                    "global_tldr": global_tldr,
                },
                published_to=[],
                publish_trace=[],
                report_date=today,
                created_at=datetime.now(timezone.utc),
            ),
        ]
        db.add_all(report_rows)
        await db.commit()

        rendered_reports = [daily_report]
        publish_stage = self.routing_profile.stages.publish
        targets = self._resolve_publish_targets(
            default_targets=publish_stage.targets or ["database"],
            destination_ids=destination_ids,
            destination_settings=destination_settings or {},
        )
        on_failure = publish_stage.on_failure or {}
        final_status = "success"
        publish_reports: list[dict] = []

        for report, rendered in zip(report_rows, rendered_reports):
            published_to: list[str] = []
            publish_trace: list[dict] = []
            for target in targets:
                sink_name = normalize_sink_name(target)
                try:
                    sink = get_sink(target)
                except KeyError as exc:
                    if run_id is not None:
                        await append_task_event(
                            db,
                            run_id=run_id,
                            monitor_id=monitor_id,
                            task_id=monitor_task_id,
                            source_id=None,
                            stage="publish",
                            level="error",
                            event_type="publish_failed",
                            message=f"[{report.report_type}] publish target not found: {target}",
                            payload={"target": target, "error": str(exc)},
                        )
                        await db.commit()
                    publish_trace.append(
                        {
                            "stage": "publish",
                            "sink": sink_name,
                            "provider": target,
                            "status": "failed",
                            "url": None,
                            "error": str(exc),
                            "latency_ms": 0,
                        }
                    )
                    final_status = "partial_success"
                    continue
                sink_name = normalize_sink_name(target)
                sink_config = self._build_sink_config(
                    target=target,
                    report_id=str(report.id),
                    destination_settings=destination_settings or {},
                )
                sink_config.setdefault("time_period", report.time_period)
                sink_config.setdefault("template_version", "v1")
                sink_config.setdefault(
                    "report_type",
                    str((report.metadata_ or {}).get("report_type") or report.report_type),
                )
                sink_config.setdefault("report_date", str(report.report_date))
                sink_config.setdefault("report_metadata", dict(report.metadata_ or {}))
                if sink_name == "notion":
                    sink_config.setdefault("summary_property", "TL;DR")
                    summary_text = str((report.metadata_ or {}).get("global_tldr") or "").strip()
                    if summary_text:
                        sink_config["summary_text"] = summary_text
                started_at = datetime.now(timezone.utc)
                publish_result = await sink.publish(rendered, sink_config)
                latency_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)

                if run_id is not None:
                    await append_task_event(
                        db,
                        run_id=run_id,
                        monitor_id=monitor_id,
                        task_id=monitor_task_id,
                        source_id=None,
                        stage="publish",
                        level="info" if publish_result.success else "warning",
                        event_type="publish_success" if publish_result.success else "publish_failed",
                        message=f"[{report.report_type}] publish to {sink_name}: {'success' if publish_result.success else 'failed'}",
                        payload={
                            "target": target,
                            "sink": sink_name,
                            "success": publish_result.success,
                            "url": publish_result.url,
                            "error": publish_result.error,
                            "latency_ms": latency_ms,
                        },
                    )
                    await db.commit()

                publish_trace.append(
                    {
                        "stage": "publish",
                        "sink": sink_name,
                        "provider": target,
                        "status": "success" if publish_result.success else "failed",
                        "url": publish_result.url,
                        "error": publish_result.error,
                        "latency_ms": latency_ms,
                    }
                )
                if publish_result.success:
                    if sink_name not in published_to:
                        published_to.append(sink_name)
                    continue

                action = on_failure.get(target) or on_failure.get(sink_name)
                if not action:
                    action = "abort" if sink_name == "database" else "continue"
                if action == "abort":
                    raise RuntimeError(f"Publish to {target} failed: {publish_result.error}")
                final_status = "partial_success"

            report.published_to = published_to
            report.publish_trace = publish_trace
            publish_reports.append(
                {
                    "report_id": str(report.id),
                    "report_type": report.report_type,
                    "published_to": list(published_to),
                    "publish_trace": list(publish_trace),
                }
            )
            db.add(report)
        await db.commit()
        return [row.id for row in report_rows], final_status, publish_reports

    @staticmethod
    def _trace_dict_to_list(trace: dict[str, dict]) -> list[dict]:
        ordered: list[dict] = []
        for stage, data in trace.items():
            ordered.append({"stage": stage, **data})
        return ordered

    @staticmethod
    def _extract_destination_settings(user_settings: dict | None) -> dict[str, dict]:
        if not isinstance(user_settings, dict):
            return {}
        raw_destinations = user_settings.get("destinations", {})
        if not isinstance(raw_destinations, dict):
            return {}
        normalized: dict[str, dict] = {}
        for destination_id, payload in raw_destinations.items():
            if not isinstance(payload, dict):
                continue
            key = normalize_sink_name(str(destination_id))
            normalized[key] = {
                "enabled": payload.get("enabled"),
                "config": payload.get("config") if isinstance(payload.get("config"), dict) else {},
            }
        return normalized

    @staticmethod
    def _extract_provider_settings(user_settings: dict | None) -> dict[str, dict]:
        if not isinstance(user_settings, dict):
            return {}
        raw_providers = user_settings.get("providers", {})
        if not isinstance(raw_providers, dict):
            return {}
        normalized: dict[str, dict] = {}
        for provider_name, payload in raw_providers.items():
            if not isinstance(payload, dict):
                continue
            if payload.get("enabled") is False:
                continue
            config = payload.get("config")
            if not isinstance(config, dict):
                continue
            normalized[str(provider_name)] = config
        return normalized

    @staticmethod
    def _resolve_publish_targets(
        default_targets: list[str],
        destination_ids: list[str] | None,
        destination_settings: dict[str, dict],
    ) -> list[str]:
        if destination_ids:
            requested_targets = ["database", *destination_ids]
        else:
            requested_targets = list(default_targets or ["database"])

        resolved: list[str] = []
        seen: set[str] = set()
        for target in requested_targets:
            if not target:
                continue
            normalized = normalize_sink_name(str(target))
            if normalized in seen:
                continue
            if not destination_ids and normalized != "database":
                setting = destination_settings.get(normalized)
                if setting is not None and setting.get("enabled") is False:
                    continue
            resolved.append(str(target))
            seen.add(normalized)

        if "database" not in seen:
            resolved.insert(0, "database")
        return resolved

    @staticmethod
    def _build_sink_config(target: str, report_id: str, destination_settings: dict[str, dict]) -> dict:
        normalized = normalize_sink_name(target)
        config: dict = {}
        if normalized == "database":
            config = {"report_id": report_id}
        elif normalized == "notion":
            config = {
                "database_id": settings.notion_database_id,
                "parent_page_id": settings.notion_parent_page_id,
                "api_key": settings.notion_api_key,
            }
        elif normalized == "obsidian":
            config = {"vault_path": settings.obsidian_vault_path}
        elif normalized == "rss":
            config = {
                "feed_url": "http://localhost:8000/api/v1/feed.xml",
                "site_url": "http://localhost:3000",
                "feed_title": "LexDeepResearch Reports",
                "feed_description": "Latest generated reports from LexDeepResearch.",
                "max_items": 20,
            }

        user_destination = destination_settings.get(normalized, {})
        user_config = user_destination.get("config")
        if isinstance(user_config, dict):
            config.update(Orchestrator._normalize_user_sink_config(normalized, user_config))
        return config

    @staticmethod
    def _normalize_user_sink_config(normalized_sink: str, user_config: dict) -> dict:
        if normalized_sink == "notion":
            notion_config: dict = {}
            if user_config.get("database_id"):
                notion_config["database_id"] = str(user_config["database_id"])
            if user_config.get("parent_page_id"):
                notion_config["parent_page_id"] = str(user_config["parent_page_id"])
            elif user_config.get("page_id"):
                notion_config["parent_page_id"] = str(user_config["page_id"])
            if user_config.get("api_key"):
                notion_config["api_key"] = str(user_config["api_key"])
            elif user_config.get("token"):
                notion_config["api_key"] = str(user_config["token"])
            if user_config.get("title_property"):
                notion_config["title_property"] = str(user_config["title_property"])
            if user_config.get("summary_property"):
                notion_config["summary_property"] = str(user_config["summary_property"])
            return notion_config

        if normalized_sink == "obsidian":
            obsidian_config: dict = {}
            if user_config.get("vault_path"):
                obsidian_config["vault_path"] = str(user_config["vault_path"])
            elif user_config.get("target_folder"):
                obsidian_config["vault_path"] = str(user_config["target_folder"])
            return obsidian_config

        if normalized_sink == "rss":
            rss_config: dict = {}
            if user_config.get("feed_url"):
                rss_config["feed_url"] = str(user_config["feed_url"])
            if user_config.get("site_url"):
                rss_config["site_url"] = str(user_config["site_url"])
            if user_config.get("feed_title"):
                rss_config["feed_title"] = str(user_config["feed_title"])
            if user_config.get("feed_description"):
                rss_config["feed_description"] = str(user_config["feed_description"])
            if user_config.get("feed_path"):
                rss_config["feed_path"] = str(user_config["feed_path"])

            raw_max_items = user_config.get("max_items")
            if isinstance(raw_max_items, str):
                raw_text = raw_max_items.strip()
                if raw_text.isdigit():
                    raw_max_items = int(raw_text)
            if isinstance(raw_max_items, int) and 1 <= raw_max_items <= 100:
                rss_config["max_items"] = raw_max_items
            return rss_config

        return {}

    async def _run_report_with_retry(self, route: StageRoute, payload: dict) -> tuple[dict, str]:
        provider_name = str(route.primary or "").strip()
        if not provider_name:
            raise RuntimeError("No report provider configured")

        provider = get_provider(stage="report", name=provider_name)
        provider_config = self._provider_config(provider_name)
        max_retry = self._max_retry(provider_config)
        last_exc: Exception | None = None

        for _ in range(max_retry + 1):
            try:
                result = await provider.run(payload=payload, config=provider_config)
                return result, provider_name
            except Exception as exc:  # pragma: no cover - retry guard
                last_exc = exc
                continue

        if last_exc:
            raise last_exc
        raise RuntimeError("Report provider failed without explicit exception")

    def _provider_config(self, provider_name: str) -> dict:
        raw_config = self.routing_profile.providers.get(provider_name, {})
        merged: dict = dict(raw_config) if isinstance(raw_config, dict) else {}
        override_config = self.provider_overrides.get(provider_name, {})
        if isinstance(override_config, dict):
            merged.update(override_config)
        return merged

    @staticmethod
    def _max_retry(provider_config: dict) -> int:
        raw = provider_config.get("max_retry", 0) if isinstance(provider_config, dict) else 0
        try:
            value = int(raw)
        except Exception:
            value = 0
        return max(value, 0)


def _normalize_report_type(value: str | None) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in {"daily", "weekly", "research"}:
        return candidate
    return "daily"
