"""采集流水线编排器"""

import asyncio
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx
import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.destinations.instances import _destination_settings_from_user
from app.agents.registry import get_agent
from app.agents.schemas import ResearchEvent, ResearchJob
from app.collectors.base import RawArticle
from app.collectors.reddit_config import build_reddit_feed_url, normalize_reddit_subreddits
from app.collectors.registry import get_collector
from app.config import settings
from app.models.article import Article
from app.models.database import async_session
from app.models.monitor import Monitor
from app.models.paper import Paper
from app.models.report import Report
from app.models.source import Source
from app.models.subscription import UserSubscription
from app.models.task import CollectTask
from app.models.user import User
from app.papers.acquisition import acquire_paper_fulltext
from app.papers.evidence import build_evidence_coverage
from app.papers.literature import build_literature_context
from app.papers.service import sync_article_paper_link
from app.providers.errors import ProviderUnavailableError
from app.providers.registry import get_provider
from app.processors.event_models import CandidateCluster, GlobalSummary, ProcessedEvent
from app.processors.global_summary import run_global_summary_stage, run_global_summary_with_retry
from app.processors.pipeline import ProcessedArticle, ProcessingPipeline
from app.processors.report_stage import run_report_with_retry
from app.processors.window_filter import filter_raw_articles_by_window
from app.renderers.base import RenderContext, Report as RenderedReport
from app.renderers.daily import DailyRenderer, build_daily_events, render_daily_report
from app.routing.loader import load_routing_profile
from app.routing.schema import PublishRoute, RoutingProfile, RoutingStages, StageRoute
from app.sinks.registry import get_sink, normalize_sink_name
from app.scheduler.run_debug import (
    build_article_log_items,
    build_candidate_cluster_log_items,
    build_processed_article_log_items,
    build_report_event_log_items,
    build_section,
    build_transparent_log_payload,
    partition_article_log_items,
    write_run_debug_artifact,
)
from app.scheduler.task_events import append_task_event

logger = structlog.get_logger()

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
_AI_STAGE_ALLOWED_PROVIDERS: dict[str, set[str]] = {
    "filter": {"rule", "llm_codex", "llm_openai"},
    "keywords": {"rule", "llm_codex", "llm_openai"},
    "global_summary": {"llm_codex", "llm_openai"},
    "report": {"llm_codex", "llm_openai"},
}
_AI_PROVIDER_NAMES = {"rule", "llm_codex", "llm_openai"}
_ORIGINAL_PIPELINE_PROCESS = ProcessingPipeline.process


@dataclass(slots=True)
class SourceProcessResult:
    relevant_articles: list[RawArticle]
    candidate_clusters: list[CandidateCluster]
    processed_articles: list[ProcessedArticle]
    stage_trace: list[dict]
    compat_mode: bool = False


class Orchestrator:
    """采集流水线编排 — 全局采集 → 加工 → 分发 → 渲染 → 落盘"""

    def __init__(self, max_concurrency: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.routing_profile = load_routing_profile(settings.routing_default_profile)
        self.pipeline = ProcessingPipeline(routing_profile=self.routing_profile.name)
        self.provider_overrides: dict[str, dict] = {}
        self.monitor_provider_overrides: dict[str, dict] = {}
        self.runtime_provider_overrides: dict[str, dict] = {}
        self.runtime_routing_profile = self.routing_profile
        self.daily_renderer = DailyRenderer()
        self.research_default_agent = settings.research_default_agent
        self.research_agents_config = (
            dict(settings.research_agents) if isinstance(settings.research_agents, dict) else {}
        )

    @staticmethod
    def _error_message(exc: Exception, *, limit: int = 1000) -> str:
        message = str(exc).strip()
        if not message:
            message = type(exc).__name__
        return message[:limit]

    async def _append_provider_unavailable_event(
        self,
        db: AsyncSession,
        *,
        run_id: uuid.UUID | None,
        monitor_id: uuid.UUID | None,
        task_id: uuid.UUID | None,
        source_id: uuid.UUID | None,
        stage: str,
        exc: ProviderUnavailableError,
    ) -> None:
        if run_id is None:
            return
        await append_task_event(
            db,
            run_id=run_id,
            monitor_id=monitor_id,
            task_id=task_id,
            source_id=source_id,
            stage=stage,
            level="error",
            event_type="provider_unavailable",
            message=f"[{exc.provider}] unavailable during {stage}",
            payload={
                "provider": exc.provider,
                "reason": exc.reason,
                "status_code": exc.status_code,
                "stage": stage,
            },
        )

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
                            "error": self._error_message(exc, limit=300),
                        }
                    )
                    if trace_emitter:
                        await trace_emitter(trace[-1])
                    logger.warning(
                        "collect_attempt_failed",
                        source_id=source_id,
                        method=candidate,
                        error=self._error_message(exc, limit=300),
                    )
                    continue
            if last_exc:
                raise last_exc
            return [], trace

    async def _process_source_articles(self, raw_articles: list[RawArticle]) -> SourceProcessResult:
        pipeline = ProcessingPipeline(routing_profile=self.runtime_routing_profile.name)
        pipeline.set_routing_profile(self.runtime_routing_profile)
        pipeline.set_provider_overrides(
            {name: dict(cfg) if isinstance(cfg, dict) else {} for name, cfg in self.runtime_provider_overrides.items()}
        )
        filter_provider = pipeline.routing_profile.stages.filter.primary
        keywords_provider = pipeline.routing_profile.stages.keywords.primary
        if not raw_articles:
            pipeline.last_stage_trace = {
                "filter": {
                    "provider": filter_provider,
                    "model": pipeline._trace_model(filter_provider),
                    "input": 0,
                    "output": 0,
                    "skipped": True,
                },
                "candidate_cluster": {
                    "provider": "candidate_rule",
                    "input": 0,
                    "output": 0,
                    "largest_cluster": 0,
                    "skipped": True,
                },
                "summarizer": {
                    "provider": keywords_provider,
                    "model": pipeline._trace_model(keywords_provider),
                    "input": 0,
                    "output": 0,
                    "compact_output": 0,
                    "stage_concurrency": pipeline.stage_concurrency,
                    "skipped": True,
                },
            }
            return SourceProcessResult(
                relevant_articles=[],
                candidate_clusters=[],
                processed_articles=[],
                stage_trace=self._trace_dict_to_list(pipeline.last_stage_trace),
                compat_mode=False,
            )
        if type(pipeline).process is not _ORIGINAL_PIPELINE_PROCESS:
            async with self.semaphore:
                processed = await pipeline.process(raw_articles)
            if not pipeline.last_stage_trace:
                pipeline.last_stage_trace = {
                    "filter": {
                        "provider": filter_provider,
                        "model": pipeline._trace_model(filter_provider),
                        "input": len(raw_articles),
                        "output": len(raw_articles),
                        "compat_mode": True,
                    },
                    "candidate_cluster": {
                        "provider": "candidate_rule",
                        "input": len(raw_articles),
                        "output": 0,
                        "largest_cluster": 0,
                        "compat_mode": True,
                    },
                    "summarizer": {
                        "provider": keywords_provider,
                        "model": pipeline._trace_model(keywords_provider),
                        "input": len(raw_articles),
                        "output": len(processed),
                        "compact_output": 0,
                        "stage_concurrency": pipeline.stage_concurrency,
                        "compat_mode": True,
                    },
                }
            return SourceProcessResult(
                relevant_articles=list(raw_articles),
                candidate_clusters=[],
                processed_articles=processed,
                stage_trace=self._trace_dict_to_list(pipeline.last_stage_trace),
                compat_mode=True,
            )
        async with self.semaphore:
            relevant, _ = await pipeline.run_filter_stage(raw_articles)
            clusters, _ = await pipeline.run_candidate_cluster_stage(relevant)
            processed: list[ProcessedArticle] = []
            if relevant:
                processed, _ = await pipeline.run_keywords_stage(relevant)
            else:
                pipeline.last_stage_trace["summarizer"] = {
                    "provider": keywords_provider,
                    "model": pipeline._trace_model(keywords_provider),
                    "input": 0,
                    "output": 0,
                    "compact_output": 0,
                    "stage_concurrency": pipeline.stage_concurrency,
                    "skipped": True,
                }
        return SourceProcessResult(
            relevant_articles=relevant,
            candidate_clusters=clusters,
            processed_articles=processed,
            stage_trace=self._trace_dict_to_list(pipeline.last_stage_trace),
            compat_mode=False,
        )

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
        monitor_ai_routing: dict | None = None,
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
                monitor_ai_routing=monitor_ai_routing,
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
                monitor_ai_routing=monitor_ai_routing,
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
        monitor_ai_routing: dict | None = None,
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
        source_by_id: dict[uuid.UUID, Source] = {item.id: item for item in subscribed_sources}
        source_name_by_id: dict[uuid.UUID, str] = {item.id: item.name for item in subscribed_sources}
        user = await db.get(User, user_id)
        destination_settings = await _destination_settings_from_user(db, user) if user else {}
        provider_overrides = self._extract_provider_settings(user.settings if user else {})
        normalized_monitor_ai_routing = self._normalize_monitor_ai_routing(monitor_ai_routing)
        self.runtime_routing_profile = self._build_runtime_routing_profile(normalized_monitor_ai_routing)
        self.monitor_provider_overrides = self._extract_monitor_provider_overrides(normalized_monitor_ai_routing)
        self.provider_overrides = provider_overrides
        self.runtime_provider_overrides = self._merge_provider_overrides(provider_overrides, self.monitor_provider_overrides)
        self.pipeline.set_routing_profile(self.runtime_routing_profile)
        self.pipeline.set_provider_overrides(self.runtime_provider_overrides)

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
                    raw.metadata.setdefault("source_id", str(source.id))
                    raw.metadata.setdefault("source_name", source.name)
                    raw.metadata.setdefault("source_category", source.category)
                raw_items = build_article_log_items(raw_articles)
                raw_artifact_path = write_run_debug_artifact(
                    run_id=pipeline_run_id,
                    source_id=source.id,
                    filename="01_collect_raw_items.json",
                    payload=raw_items,
                )
                await append_task_event(
                    db,
                    run_id=pipeline_run_id,
                    monitor_id=monitor_id,
                    task_id=task.id,
                    source_id=source.id,
                    stage="collect",
                    event_type="source_collected_detail",
                    message=f"[{source.name}] collected {len(raw_articles)} raw items",
                    payload=build_transparent_log_payload(
                        summary={
                            "source_name": source.name,
                            "provider": collect_trace[-1].get("provider") if collect_trace else source.collect_method,
                            "collected": len(raw_articles),
                        },
                        sections=[
                            build_section(
                                title="Raw Items",
                                section_type="article_items",
                                items=raw_items,
                                artifact_path=raw_artifact_path,
                            )
                        ],
                    ),
                )
                await db.commit()
                collected_by_source[source.id] = (raw_articles, collect_trace)
            except Exception as exc:  # pragma: no cover - defensive path
                error_text = self._error_message(exc, limit=1000)
                task.status = "failed"
                task.error_message = error_text
                task.finished_at = datetime.now(timezone.utc)
                existing_trace = task.stage_trace or []
                task.stage_trace = [
                    *existing_trace,
                    {
                        "stage": "collect",
                        "provider": source.collect_method,
                        "status": "failed",
                        "error": self._error_message(exc, limit=300),
                    },
                    {
                        "stage": "pipeline",
                        "provider": "orchestrator",
                        "status": "failed",
                        "error": self._error_message(exc, limit=300),
                    },
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
                    payload={"error": error_text},
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

        process_inputs: dict[uuid.UUID, tuple[list[RawArticle], list[dict], dict]] = {}
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
                window_kept_items, window_dropped_items = partition_article_log_items(
                    raw_articles,
                    filtered_raw,
                    dropped_reason="outside_monitor_window",
                )
                window_kept_artifact = write_run_debug_artifact(
                    run_id=pipeline_run_id,
                    source_id=source.id,
                    filename="02_window_kept.json",
                    payload=window_kept_items,
                )
                window_dropped_artifact = write_run_debug_artifact(
                    run_id=pipeline_run_id,
                    source_id=source.id,
                    filename="02_window_dropped.json",
                    payload=window_dropped_items,
                )
                await append_task_event(
                    db,
                    run_id=pipeline_run_id,
                    monitor_id=monitor_id,
                    task_id=task.id,
                    source_id=source.id,
                    stage="window_filter",
                    event_type="window_filter_completed",
                    message=f"[{source.name}] window filter {filter_trace.get('after', 0)}/{filter_trace.get('before', 0)} kept",
                    payload=build_transparent_log_payload(
                        summary={
                            "provider": filter_trace.get("provider"),
                            "window_hours": normalized_window_hours,
                            "kept": len(window_kept_items),
                            "dropped": len(window_dropped_items),
                            "outside_window": int(filter_trace.get("outside_window", 0) or 0),
                            "first_seen_fallback": int(filter_trace.get("first_seen_fallback", 0) or 0),
                        },
                        sections=[
                            build_section(
                                title="Kept Items",
                                section_type="article_items",
                                items=window_kept_items,
                                artifact_path=window_kept_artifact,
                            ),
                            build_section(
                                title="Dropped Items",
                                section_type="article_items",
                                items=window_dropped_items,
                                artifact_path=window_dropped_artifact,
                            ),
                        ],
                    ),
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

                process_inputs[source.id] = (filtered_raw, collect_trace, filter_trace)
            except Exception as exc:  # pragma: no cover - defensive path
                error_text = self._error_message(exc, limit=1000)
                task.status = "failed"
                task.error_message = error_text
                task.finished_at = datetime.now(timezone.utc)
                existing_trace = task.stage_trace or []
                task.stage_trace = [
                    *existing_trace,
                    {
                        "stage": "process",
                        "provider": "pipeline",
                        "status": "failed",
                        "error": self._error_message(exc, limit=300),
                    },
                    {
                        "stage": "pipeline",
                        "provider": "orchestrator",
                        "status": "failed",
                        "error": self._error_message(exc, limit=300),
                    },
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
                    payload={"error": error_text},
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

        if not run_cancelled and process_inputs:
            process_jobs: dict[uuid.UUID, asyncio.Task[SourceProcessResult]] = {
                source_id: asyncio.create_task(self._process_source_articles(filtered_raw))
                for source_id, (filtered_raw, _collect_trace, _filter_trace) in process_inputs.items()
            }
            pending_process_jobs = dict(process_jobs)

            while pending_process_jobs:
                done, _pending = await asyncio.wait(
                    set(pending_process_jobs.values()),
                    timeout=1.0,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                completed_source_ids: list[uuid.UUID] = []
                for source_id, job in list(pending_process_jobs.items()):
                    if job in done:
                        pending_process_jobs.pop(source_id, None)
                        completed_source_ids.append(source_id)

                if pending_process_jobs and await self._is_monitor_run_cancelling(db, monitor_task_id=monitor_task_id):
                    run_cancelled = True
                    for job in pending_process_jobs.values():
                        job.cancel()
                    await asyncio.gather(*pending_process_jobs.values(), return_exceptions=True)
                    break

                for source_id in completed_source_ids:
                    source = source_by_id[source_id]
                    task = task_rows[source_id]
                    _filtered_raw, collect_trace, filter_trace = process_inputs[source_id]
                    job = process_jobs[source_id]

                    try:
                        process_result = job.result()
                    except Exception as exc:  # pragma: no cover - defensive path
                        error_text = self._error_message(exc, limit=1000)
                        failure_stage = exc.stage if isinstance(exc, ProviderUnavailableError) and exc.stage else "process"
                        task.status = "failed"
                        task.error_message = error_text
                        task.finished_at = datetime.now(timezone.utc)
                        existing_trace = task.stage_trace or []
                        task.stage_trace = [
                            *existing_trace,
                            {
                                "stage": failure_stage,
                                "provider": getattr(exc, "provider", "pipeline"),
                                "status": "failed",
                                "error": self._error_message(exc, limit=300),
                            },
                            {
                                "stage": "pipeline",
                                "provider": "orchestrator",
                                "status": "failed",
                                "error": self._error_message(exc, limit=300),
                            },
                        ]
                        db.add(task)
                        if isinstance(exc, ProviderUnavailableError):
                            await self._append_provider_unavailable_event(
                                db,
                                run_id=pipeline_run_id,
                                monitor_id=monitor_id,
                                task_id=task.id,
                                source_id=source.id,
                                stage=failure_stage,
                                exc=exc,
                            )
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
                            payload={"error": error_text},
                        )
                        if pending_process_jobs:
                            for pending_job in pending_process_jobs.values():
                                pending_job.cancel()
                            await asyncio.gather(*pending_process_jobs.values(), return_exceptions=True)
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

                    relevant_raw = process_result.relevant_articles
                    candidate_clusters = process_result.candidate_clusters
                    processed = process_result.processed_articles
                    processing_trace = process_result.stage_trace
                    compat_mode = process_result.compat_mode
                    filter_stage_trace = self._find_stage_trace(processing_trace, "filter")
                    candidate_cluster_trace = self._find_stage_trace(processing_trace, "candidate_cluster")
                    keywords_trace = self._find_stage_trace(processing_trace, "summarizer")
                    task.stage_trace = [
                        *collect_trace,
                        filter_trace,
                        {"stage": "process", "provider": "pipeline", "status": "running", "articles": len(processed)},
                        {"stage": "persist", "provider": "database", "status": "running"},
                    ]
                    db.add(task)
                    pipeline_kept_items, pipeline_dropped_items = partition_article_log_items(
                        _filtered_raw,
                        relevant_raw,
                        dropped_reason="filtered_out_by_provider",
                    )
                    pipeline_kept_artifact = write_run_debug_artifact(
                        run_id=pipeline_run_id,
                        source_id=source.id,
                        filename="03_pipeline_filter_kept.json",
                        payload=pipeline_kept_items,
                    )
                    pipeline_dropped_artifact = write_run_debug_artifact(
                        run_id=pipeline_run_id,
                        source_id=source.id,
                        filename="03_pipeline_filter_dropped.json",
                        payload=pipeline_dropped_items,
                    )
                    await append_task_event(
                        db,
                        run_id=pipeline_run_id,
                        monitor_id=monitor_id,
                        task_id=task.id,
                        source_id=source.id,
                        stage="process",
                        event_type="pipeline_filter_completed",
                        message=f"[{source.name}] pipeline filter kept {len(pipeline_kept_items)}/{len(_filtered_raw)}",
                        payload=build_transparent_log_payload(
                            summary={
                                "provider": filter_stage_trace.get("provider"),
                                "model": filter_stage_trace.get("model"),
                                "kept": len(pipeline_kept_items),
                                "dropped": len(pipeline_dropped_items),
                            },
                            sections=[
                                build_section(
                                    title="Kept Items",
                                    section_type="article_items",
                                    items=pipeline_kept_items,
                                    artifact_path=pipeline_kept_artifact,
                                ),
                                build_section(
                                    title="Dropped Items",
                                    section_type="article_items",
                                    items=pipeline_dropped_items,
                                    artifact_path=pipeline_dropped_artifact,
                                ),
                            ],
                        ),
                    )
                    cluster_items = build_candidate_cluster_log_items(candidate_clusters)
                    cluster_artifact_path = write_run_debug_artifact(
                        run_id=pipeline_run_id,
                        source_id=source.id,
                        filename="04_candidate_clusters.json",
                        payload=cluster_items,
                    )
                    await append_task_event(
                        db,
                        run_id=pipeline_run_id,
                        monitor_id=monitor_id,
                        task_id=task.id,
                        source_id=source.id,
                        stage="process",
                        event_type="candidate_cluster_completed",
                        message=f"[{source.name}] candidate clustering produced {len(candidate_clusters)} clusters",
                        payload=build_transparent_log_payload(
                            summary={
                                "provider": candidate_cluster_trace.get("provider", "candidate_rule"),
                                "clusters": len(candidate_clusters),
                                "articles": len(relevant_raw),
                                "largest_cluster": int(candidate_cluster_trace.get("largest_cluster", 0) or 0),
                            },
                            sections=[
                                build_section(
                                    title="Clusters",
                                    section_type="candidate_clusters",
                                    items=cluster_items,
                                    artifact_path=cluster_artifact_path,
                                )
                            ],
                        ),
                    )
                    processed_items = build_processed_article_log_items(processed)
                    processed_artifact_path = write_run_debug_artifact(
                        run_id=pipeline_run_id,
                        source_id=source.id,
                        filename="05_keywords_output.json",
                        payload=processed_items,
                    )
                    await append_task_event(
                        db,
                        run_id=pipeline_run_id,
                        monitor_id=monitor_id,
                        task_id=task.id,
                        source_id=source.id,
                        stage="process",
                        event_type="keywords_completed",
                        message=f"[{source.name}] keywords stage produced {len(processed_items)} processed items",
                        payload=build_transparent_log_payload(
                            summary={
                                "provider": keywords_trace.get("provider"),
                                "model": keywords_trace.get("model"),
                                "processed": len(processed_items),
                                "compact_output": int(keywords_trace.get("compact_output", 0) or 0),
                            },
                            sections=[
                                build_section(
                                    title="Processed Items",
                                    section_type="processed_articles",
                                    items=processed_items,
                                    artifact_path=processed_artifact_path,
                                )
                            ],
                        ),
                    )
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
                        if pending_process_jobs:
                            for pending_job in pending_process_jobs.values():
                                pending_job.cancel()
                            await asyncio.gather(*pending_process_jobs.values(), return_exceptions=True)
                        break

                    article_ids: list[uuid.UUID] = []
                    if not compat_mode:
                        article_ids = await self._persist_processed_articles(
                            db,
                            source,
                            processed,
                            processing_trace=processing_trace,
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

                if run_cancelled:
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

        await self._run_fulltext_acquisition_stage(
            db=db,
            article_ids=persisted_article_ids,
            source_by_id=source_by_id,
            report_type=report_type,
            run_id=pipeline_run_id,
            monitor_id=monitor_id,
            monitor_task_id=monitor_task_id,
        )
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
        if source.collect_method == "rss" and isinstance(config.get("subreddits"), list):
            subreddits = normalize_reddit_subreddits(config.get("subreddits"))
            if subreddits:
                config["subreddits"] = subreddits
            config["feed_url"] = build_reddit_feed_url(subreddits or config.get("subreddits"))
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

        if source.collect_method in {"openalex", "europe_pmc", "pubmed"} or (
            source.collect_method == "rss" and bool(config.get("arxiv_api"))
        ):
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

        if source.collect_method == "rss":
            subreddits = normalize_reddit_subreddits(override.get("subreddits"))
            if subreddits:
                config["subreddits"] = subreddits
                config["feed_url"] = build_reddit_feed_url(subreddits)

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
        if method in {"openalex", "europe_pmc", "pubmed"} or (method == "rss" and bool(config.get("arxiv_api"))):
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
        source_config = source.config if isinstance(source.config, dict) else {}
        allow_first_seen_fallback = bool(source_config.get("window_allow_first_seen_fallback", False))

        async def _existing_external_ids(candidate_ids: list[str]) -> set[str]:
            if not candidate_ids:
                return set()
            stmt = select(Article.external_id).where(
                and_(
                    Article.source_id == source.id,
                    Article.external_id.in_(candidate_ids),
                )
            )
            result = await db.execute(stmt)
            return {str(item) for item in result.scalars().all() if item}

        return await filter_raw_articles_by_window(
            raw_articles=raw_articles,
            window_start=window_start,
            window_end=window_end,
            window_hours=window_hours,
            allow_first_seen_fallback=allow_first_seen_fallback,
            existing_external_ids_resolver=_existing_external_ids,
        )

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
    ) -> list[uuid.UUID]:
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
            await sync_article_paper_link(db, existing, source)
            db.add(existing)
            await db.flush()
            article_ids.append(existing.id)
        await db.commit()
        return article_ids

    async def _render_and_persist_reports(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        processed_articles: list[ProcessedArticle] | list[ProcessedEvent],
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
        selected_report_type = _normalize_report_type(report_type)
        selected_time_period = "daily"
        if selected_report_type == "weekly":
            selected_time_period = "weekly"
        elif selected_report_type == "research":
            selected_time_period = "custom"
        context = RenderContext(date=today.isoformat(), user_id=str(user_id))
        report_events = build_daily_events(processed_articles)
        if run_id is not None:
            report_event_items = build_report_event_log_items(report_events)
            report_events_artifact_path = write_run_debug_artifact(
                run_id=run_id,
                source_id=None,
                filename="06_report_events.json",
                payload=report_event_items,
            )
            await append_task_event(
                db,
                run_id=run_id,
                monitor_id=monitor_id,
                task_id=monitor_task_id,
                source_id=None,
                stage="report",
                event_type="report_events_generated",
                message=f"[{selected_report_type}] assembled {len(report_event_items)} report events",
                payload=build_transparent_log_payload(
                    summary={
                        "events": len(report_event_items),
                        "categories": sorted(
                            {
                                str(item.get("category") or "").strip()
                                for item in report_event_items
                                if str(item.get("category") or "").strip()
                            }
                        ),
                    },
                    sections=[
                        build_section(
                            title="Events",
                            section_type="report_events",
                            items=report_event_items,
                            artifact_path=report_events_artifact_path,
                        )
                    ],
                ),
            )
            await db.commit()
        if selected_report_type == "research":
            report_rows, rendered_reports = await self._build_research_reports(
                db=db,
                user_id=user_id,
                report_events=report_events,
                article_ids=article_ids,
                selected_time_period=selected_time_period,
                selected_report_type=selected_report_type,
                report_date=today,
                run_id=run_id,
                monitor_id=monitor_id,
                monitor_task_id=monitor_task_id,
            )
            return await self._publish_report_rows(
                db=db,
                report_rows=report_rows,
                rendered_reports=rendered_reports,
                destination_ids=destination_ids,
                destination_settings=destination_settings,
                run_id=run_id,
                monitor_id=monitor_id,
                monitor_task_id=monitor_task_id,
            )
        summary_route = self.runtime_routing_profile.stages.global_summary or self.runtime_routing_profile.stages.report
        try:
            global_summary: GlobalSummary = await run_global_summary_stage(
                events=report_events,
                runner=lambda payload: self._run_global_summary_with_retry(summary_route, payload),
            )
        except ProviderUnavailableError as exc:
            await self._append_provider_unavailable_event(
                db,
                run_id=run_id,
                monitor_id=monitor_id,
                task_id=monitor_task_id,
                source_id=None,
                stage=exc.stage or "global_summary",
                exc=exc,
            )
            await db.commit()
            raise
        daily_report = render_daily_report(
            events=report_events,
            context=context,
            global_summary=global_summary.global_tldr,
        )

        categories = sorted(
            {
                category
                for item in processed_articles
                for category in _item_source_categories(item)
            }
        )
        topic_counts: Counter[str] = Counter()
        for item in processed_articles:
            for keyword in _item_keywords(item)[:3]:
                topic_counts[keyword] += 1
        topics = [{"name": topic, "weight": weight} for topic, weight in topic_counts.most_common(10)]
        fallback_tldr = [_item_summary(item) for item in processed_articles[:8] if _item_summary(item)]
        daily_metadata = dict(daily_report.metadata or {})
        daily_metadata["global_summary_provider"] = global_summary.provider
        daily_metadata["global_summary_fallback_used"] = global_summary.fallback_used
        daily_metadata["global_summary_metrics"] = global_summary.prompt_metrics
        daily_report.metadata = daily_metadata
        global_tldr = str(daily_metadata.get("global_tldr") or "").strip()
        report_input_content = str(daily_report.content or "")
        report_input_events = daily_metadata.get("events")
        report_input_event_count = len(report_input_events) if isinstance(report_input_events, list) else 0
        report_provider = "renderer_compose"
        report_metrics = {
            "input_content_chars": len(report_input_content),
            "prompt_content_chars": 0,
            "prompt_content_truncated": False,
            "output_content_chars": len(report_input_content),
        }
        report_route = self.runtime_routing_profile.stages.report
        if str(report_route.primary or "").strip():
            report_payload = {
                "title": daily_report.title,
                "content": daily_report.content,
                "events": report_input_events if isinstance(report_input_events, list) else [],
                "global_tldr": global_tldr,
                "date": today.isoformat(),
            }
            try:
                report_output, report_provider = await self._run_report_with_retry(report_route, report_payload)
                raw_metrics = report_output.get("report_metrics")
                if isinstance(raw_metrics, dict):
                    report_metrics.update(raw_metrics)
                else:
                    report_metrics["prompt_content_chars"] = len(str(report_payload["events"]))

                generated_tldr = str(report_output.get("global_tldr") or "").strip()
                if generated_tldr:
                    global_tldr = generated_tldr
                    daily_metadata["global_tldr"] = generated_tldr
                    daily_metadata["tldr"] = [generated_tldr]
                    daily_report.metadata = daily_metadata
            except ProviderUnavailableError as exc:
                await self._append_provider_unavailable_event(
                    db,
                    run_id=run_id,
                    monitor_id=monitor_id,
                    task_id=monitor_task_id,
                    source_id=None,
                    stage=exc.stage or "report",
                    exc=exc,
                )
                await db.commit()
                raise
            except Exception as exc:  # pragma: no cover - runtime fallback
                logger.warning(
                    "report_provider_fallback_to_renderer",
                    provider=report_route.primary,
                    error=self._error_message(exc),
                )

        daily_metadata["report_provider"] = report_provider
        daily_metadata["report_metrics"] = report_metrics
        daily_report.metadata = daily_metadata
        deep_tldr = [global_tldr] if global_tldr else fallback_tldr
        deep_categories = daily_metadata.get("categories")
        if not isinstance(deep_categories, list) or not deep_categories:
            deep_categories = categories
        deep_events = daily_metadata.get("events")
        if not isinstance(deep_events, list):
            deep_events = []
        monitor_name = ""
        if monitor_id is not None:
            monitor = await db.get(Monitor, monitor_id)
            if monitor is not None:
                monitor_name = monitor.name
        article_id_strings = [str(item) for item in article_ids]
        report_payload = {
            "provider": report_provider,
            "report_type": selected_report_type,
            "input_events": report_input_event_count,
            "output_heading3_count": _count_markdown_heading_level(str(daily_report.content or ""), 3),
            "input_content_chars": int(report_metrics.get("input_content_chars", len(report_input_content))),
            "prompt_content_chars": int(report_metrics.get("prompt_content_chars", 0)),
            "prompt_content_truncated": bool(report_metrics.get("prompt_content_truncated", False)),
            "output_content_chars": int(report_metrics.get("output_content_chars", len(str(daily_report.content or "")))),
        }
        if run_id is not None:
            await append_task_event(
                db,
                run_id=run_id,
                monitor_id=monitor_id,
                task_id=monitor_task_id,
                source_id=None,
                stage="report",
                event_type="report_generated",
                message=f"[{selected_report_type}] report generated via {report_provider}",
                payload=report_payload,
            )
            await db.commit()

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
                    "global_tldr_source": daily_metadata.get("global_tldr_source"),
                    "global_summary_provider": daily_metadata.get("global_summary_provider"),
                    "global_summary_fallback_used": daily_metadata.get("global_summary_fallback_used"),
                    "global_summary_metrics": daily_metadata.get("global_summary_metrics"),
                    "report_provider": report_provider,
                    "monitor_id": str(monitor_id) if monitor_id is not None else None,
                    "monitor_name": monitor_name,
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
        return await self._publish_report_rows(
            db=db,
            report_rows=report_rows,
            rendered_reports=rendered_reports,
            destination_ids=destination_ids,
            destination_settings=destination_settings,
            run_id=run_id,
            monitor_id=monitor_id,
            monitor_task_id=monitor_task_id,
        )

    async def _build_research_reports(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        report_events: list[dict],
        article_ids: list[uuid.UUID],
        selected_time_period: str,
        selected_report_type: str,
        report_date: date,
        run_id: uuid.UUID | None,
        monitor_id: uuid.UUID | None,
        monitor_task_id: uuid.UUID | None,
    ) -> tuple[list[Report], list[RenderedReport]]:
        target_event = self._select_research_target_event(report_events)
        event_article_ids = [str(item).strip() for item in target_event.get("article_ids", []) if str(item).strip()]
        target_article_ids = await self._resolve_research_article_ids(
            db,
            event_article_ids=event_article_ids,
            fallback_article_ids=article_ids,
        )
        literature_context = await build_literature_context(db, target_article_ids)
        if run_id is not None:
            await append_task_event(
                db,
                run_id=run_id,
                monitor_id=monitor_id,
                task_id=monitor_task_id,
                source_id=None,
                stage="report",
                event_type="research_target_selected",
                message=f"[research] selected target event {target_event['event_id']}",
                payload={"event_id": target_event["event_id"], "title": target_event["title"]},
            )
            await db.commit()

        job = self._build_research_job(
            target_event=target_event,
            frequency=selected_time_period,
            user_id=user_id,
            monitor_id=monitor_id,
            report_date=report_date,
            metadata=literature_context,
        )
        if run_id is not None:
            await append_task_event(
                db,
                run_id=run_id,
                monitor_id=monitor_id,
                task_id=monitor_task_id,
                source_id=None,
                stage="report",
                event_type="research_job_built",
                message="[research] job built",
                payload={
                    "job_id": job.job_id,
                    "agent": self._research_agent_name(),
                    "analysis_mode": str(job.metadata.get("analysis_mode") or "event_research"),
                    "literature_items": int((job.metadata.get("literature_summary") or {}).get("paper_count") or 0),
                },
            )
            await db.commit()

        agent_name = self._research_agent_name()
        agent_config = self._research_agent_config(agent_name)
        started_at = datetime.now(timezone.utc)
        try:
            result = await get_agent(agent_name, config=agent_config).run(job)
        except Exception as exc:
            if run_id is not None:
                await append_task_event(
                    db,
                    run_id=run_id,
                    monitor_id=monitor_id,
                    task_id=monitor_task_id,
                    source_id=None,
                    stage="report",
                    level="error",
                    event_type="research_failed",
                    message=f"[research] agent failed via {agent_name}",
                    payload={"agent": agent_name, "error": self._error_message(exc)},
                )
                await db.commit()
            raise

        if not str(result.content_markdown or "").strip():
            exc = RuntimeError("Research agent returned empty content")
            if run_id is not None:
                await append_task_event(
                    db,
                    run_id=run_id,
                    monitor_id=monitor_id,
                    task_id=monitor_task_id,
                    source_id=None,
                    stage="report",
                    level="error",
                    event_type="research_failed",
                    message=f"[research] empty content via {agent_name}",
                    payload={"agent": agent_name, "error": self._error_message(exc)},
                )
                await db.commit()
            raise exc

        latency_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        if run_id is not None:
            await append_task_event(
                db,
                run_id=run_id,
                monitor_id=monitor_id,
                task_id=monitor_task_id,
                source_id=None,
                stage="report",
                event_type="research_response_received",
                message=f"[research] response received via {agent_name}",
                payload={"agent": agent_name, "latency_ms": latency_ms},
            )
            await db.commit()

        monitor_name = ""
        if monitor_id is not None:
            monitor = await db.get(Monitor, monitor_id)
            if monitor is not None:
                monitor_name = monitor.name

        source_payload = [
            {"title": item.title, "url": item.url, "source_type": item.source_type}
            for item in result.sources
        ]
        article_id_strings = [str(item) for item in target_article_ids]
        evidence_coverage = await build_evidence_coverage(db, target_article_ids)
        analysis_mode = str(job.metadata.get("analysis_mode") or "event_research")
        metadata = {
            "template": "research",
            "frequency": selected_time_period,
            "report_type": selected_report_type,
            "analysis_mode": analysis_mode,
            "events": [target_event],
            "event_ids": [str(target_event["event_id"])],
            "global_tldr": result.summary,
            "tldr": [result.summary] if result.summary else [],
            "research_agent": agent_name,
            "research_runtime": agent_name,
            "research_assistant_id": str(result.metadata.get("agent_name") or "lead_agent"),
            "research_job_id": job.job_id,
            "research_sources": source_payload,
            "research_confidence": {
                "level": result.confidence_level or "unknown",
                "reason": result.confidence_reason,
            },
            "research_artifacts": list(result.artifacts),
            "research_metrics": {"latency_ms": latency_ms, "fetched_urls": len(source_payload)},
            "monitor_id": str(monitor_id) if monitor_id is not None else None,
            "monitor_name": monitor_name,
        }
        report_row = Report(
            id=uuid.uuid4(),
            user_id=user_id,
            time_period=selected_time_period,
            report_type=selected_report_type,
            title=result.title,
            content=result.content_markdown,
            article_ids=article_id_strings,
            metadata_=metadata,
            published_to=[],
            publish_trace=[],
            report_date=report_date,
            created_at=datetime.now(timezone.utc),
        )
        rendered_report = RenderedReport(
            level="L4",
            title=result.title,
            content=result.content_markdown,
            article_ids=article_id_strings,
            metadata=metadata,
        )
        db.add(report_row)
        await db.commit()
        if run_id is not None:
            await append_task_event(
                db,
                run_id=run_id,
                monitor_id=monitor_id,
                task_id=monitor_task_id,
                source_id=None,
                stage="report",
                event_type="research_report_generated",
                message=f"[research] report generated via {agent_name}",
                payload={
                    "agent": agent_name,
                    "analysis_mode": analysis_mode,
                    "output_content_chars": len(result.content_markdown),
                    "evidence_coverage": evidence_coverage,
                },
            )
            await db.commit()
        return [report_row], [rendered_report]

    async def _publish_report_rows(
        self,
        db: AsyncSession,
        report_rows: list[Report],
        rendered_reports: list[RenderedReport],
        destination_ids: list[str] | None,
        destination_settings: dict[str, dict] | None,
        run_id: uuid.UUID | None,
        monitor_id: uuid.UUID | None,
        monitor_task_id: uuid.UUID | None,
    ) -> tuple[list[uuid.UUID], str, list[dict]]:
        publish_stage = self.runtime_routing_profile.stages.publish
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
                sink_name = self._resolve_sink_name(target=str(target), destination_settings=destination_settings or {})
                try:
                    sink = get_sink(sink_name)
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
                            "destination_instance_id": self._destination_instance_id(
                                target=str(target),
                                destination_settings=destination_settings or {},
                            ),
                            "destination_instance_name": self._destination_instance_name(
                                target=str(target),
                                destination_settings=destination_settings or {},
                            ),
                            "status": "failed",
                            "url": None,
                            "error": str(exc),
                            "latency_ms": 0,
                        }
                    )
                    final_status = "partial_success"
                    continue
                sink_config = self._build_sink_config(
                    target=target,
                    report_id=str(report.id),
                    destination_settings=destination_settings or {},
                )
                sink_config.setdefault("time_period", report.time_period)
                sink_config.setdefault("template_version", "v1")
                sink_config.setdefault("report_type", str((report.metadata_ or {}).get("report_type") or report.report_type))
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
                        "destination_instance_id": self._destination_instance_id(
                            target=str(target),
                            destination_settings=destination_settings or {},
                        ),
                        "destination_instance_name": self._destination_instance_name(
                            target=str(target),
                            destination_settings=destination_settings or {},
                        ),
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
            report.published_destination_instance_ids = self._published_destination_instance_ids(publish_trace)
            report.publish_trace = publish_trace
            publish_reports.append(
                {
                    "report_id": str(report.id),
                    "report_type": report.report_type,
                    "published_to": list(published_to),
                    "published_destination_instance_ids": list(report.published_destination_instance_ids or []),
                    "publish_trace": list(publish_trace),
                }
            )
            db.add(report)
        await db.commit()
        return [row.id for row in report_rows], final_status, publish_reports

    def _research_agent_name(self) -> str:
        candidate = str(self.research_default_agent or "").strip()
        return candidate or "deerflow_embedded"

    def _research_agent_config(self, name: str) -> dict:
        raw = self.research_agents_config.get(name, {}) if isinstance(self.research_agents_config, dict) else {}
        if not isinstance(raw, dict):
            return {}
        return dict(raw)

    def _select_research_target_event(self, report_events: list[dict]) -> dict:
        candidates: list[dict] = []
        for event in report_events:
            if not isinstance(event, dict):
                continue
            source_links = event.get("source_links")
            if not isinstance(source_links, list) or not any(str(item).strip() for item in source_links):
                continue
            category = str(event.get("category") or "").strip()
            non_empty_fields = sum(
                1
                for value in (event.get("title"), event.get("one_line_tldr"), event.get("detail"))
                if str(value or "").strip()
            )
            if not category or non_empty_fields < 2:
                continue
            candidates.append(event)

        if not candidates:
            raise RuntimeError("No eligible research event found")

        def _sort_key(item: dict) -> tuple[int, int, str]:
            importance_rank = {"critical": 4, "high": 3, "normal": 2, "low": 1}.get(
                str(item.get("importance") or "normal").strip().lower(),
                0,
            )
            source_count = int(item.get("source_count") or 0)
            published_at = str(item.get("published_at") or "").strip()
            return importance_rank, source_count, published_at

        return sorted(candidates, key=_sort_key, reverse=True)[0]

    async def _run_fulltext_acquisition_stage(
        self,
        db: AsyncSession,
        *,
        article_ids: list[uuid.UUID],
        source_by_id: dict[uuid.UUID, Source],
        report_type: str,
        run_id: uuid.UUID | None,
        monitor_id: uuid.UUID | None,
        monitor_task_id: uuid.UUID | None,
    ) -> None:
        if _normalize_report_type(report_type) != "research" or not article_ids:
            return

        stmt = select(Article).where(Article.id.in_(article_ids))
        articles = (await db.execute(stmt)).scalars().all()
        paper_ids: list[uuid.UUID] = []
        for article in articles:
            if article.paper_id is None:
                continue
            source = source_by_id.get(article.source_id)
            if source is None or source.category != "academic":
                continue
            if article.paper_id not in paper_ids:
                paper_ids.append(article.paper_id)

        if not paper_ids:
            return

        requested = 0
        succeeded = 0
        failed = 0
        skipped = 0

        if run_id is not None:
            await append_task_event(
                db,
                run_id=run_id,
                monitor_id=monitor_id,
                task_id=monitor_task_id,
                source_id=None,
                stage="fulltext",
                event_type="fulltext_started",
                message=f"[research] starting fulltext acquisition for {len(paper_ids)} papers",
                payload={"papers_requested": len(paper_ids)},
            )
            await db.commit()

        for paper_id in paper_ids:
            if await self._is_monitor_run_cancelling(db, monitor_task_id=monitor_task_id):
                break
            paper = await db.get(Paper, paper_id)
            if paper is None:
                failed += 1
                continue
            if paper.best_content_id is not None or paper.fulltext_status == "converted":
                skipped += 1
                continue

            requested += 1
            result = await acquire_paper_fulltext(db, paper_id)
            await db.flush()
            refreshed_paper = await db.get(Paper, paper_id)
            acquisition_succeeded = bool(
                result is not None
                and result.content is not None
                or refreshed_paper is not None
                and (refreshed_paper.best_content_id is not None or refreshed_paper.fulltext_status == "converted")
            )
            if acquisition_succeeded:
                succeeded += 1
                if run_id is not None:
                    await append_task_event(
                        db,
                        run_id=run_id,
                        monitor_id=monitor_id,
                        task_id=monitor_task_id,
                        source_id=None,
                        stage="fulltext",
                        event_type="paper_fulltext_acquired",
                        message=f"[research] acquired fulltext for paper {paper_id}",
                        payload={
                            "paper_id": str(paper_id),
                            "content_tier": (
                                result.content.content_tier
                                if result is not None and result.content is not None
                                else "fulltext"
                            ),
                        },
                    )
            else:
                failed += 1
                if run_id is not None:
                    await append_task_event(
                        db,
                        run_id=run_id,
                        monitor_id=monitor_id,
                        task_id=monitor_task_id,
                        source_id=None,
                        stage="fulltext",
                        event_type="paper_fulltext_failed",
                        message=f"[research] fulltext unavailable for paper {paper_id}",
                        payload={"paper_id": str(paper_id)},
                    )
            await db.commit()

        if run_id is not None:
            await append_task_event(
                db,
                run_id=run_id,
                monitor_id=monitor_id,
                task_id=monitor_task_id,
                source_id=None,
                stage="fulltext",
                event_type="fulltext_completed",
                message="[research] fulltext acquisition completed",
                payload={
                    "papers_total": len(paper_ids),
                    "papers_requested": requested,
                    "papers_succeeded": succeeded,
                    "papers_failed": failed,
                    "papers_skipped": skipped,
                },
            )
            await db.commit()

    async def _resolve_research_article_ids(
        self,
        db: AsyncSession,
        *,
        event_article_ids: list[str],
        fallback_article_ids: list[uuid.UUID],
    ) -> list[uuid.UUID]:
        if not event_article_ids:
            return list(fallback_article_ids)

        resolved_ids = [_coerce_uuid(item) for item in event_article_ids]
        resolved_ids = [item for item in resolved_ids if item is not None]
        if resolved_ids:
            return resolved_ids

        stmt = select(Article.id).where(
            Article.id.in_(fallback_article_ids),
            Article.external_id.in_(event_article_ids),
        )
        matched_ids = (await db.execute(stmt)).scalars().all()
        return matched_ids or list(fallback_article_ids)

    def _build_research_job(
        self,
        *,
        target_event: dict,
        frequency: str,
        user_id: uuid.UUID,
        monitor_id: uuid.UUID | None,
        report_date: date,
        metadata: dict | None = None,
    ) -> ResearchJob:
        return ResearchJob(
            job_id=str(uuid.uuid4()),
            frequency=frequency if frequency in {"daily", "weekly", "custom"} else "custom",
            template="research",
            event=ResearchEvent(
                event_id=str(target_event.get("event_id") or ""),
                title=str(target_event.get("title") or "").strip(),
                summary=str(target_event.get("one_line_tldr") or "").strip(),
                detail=str(target_event.get("detail") or "").strip(),
                category=str(target_event.get("category") or "").strip() or "其他",
                importance=str(target_event.get("importance") or "normal").strip() or "normal",
                source_links=[str(item).strip() for item in target_event.get("source_links", []) if str(item).strip()],
                source_count=int(target_event.get("source_count") or 0),
                source_name=str(target_event.get("source_name") or "").strip(),
                published_at=str(target_event.get("published_at") or "").strip() or None,
                who=str(target_event.get("who") or "").strip(),
                what=str(target_event.get("what") or "").strip(),
                when=str(target_event.get("when") or "").strip(),
                metrics=[str(item).strip() for item in target_event.get("metrics", []) if str(item).strip()],
                availability=str(target_event.get("availability") or "").strip(),
                unknowns=str(target_event.get("unknowns") or "").strip(),
                evidence=str(target_event.get("evidence") or "").strip(),
                keywords=[str(item).strip() for item in target_event.get("keywords", []) if str(item).strip()],
            ),
            focus_questions=self._default_research_questions(target_event),
            monitor_id=str(monitor_id) if monitor_id is not None else None,
            user_id=str(user_id),
            report_date=report_date.isoformat(),
            metadata=dict(metadata or {}),
        )

    @staticmethod
    def _default_research_questions(target_event: dict) -> list[str]:
        title = str(target_event.get("title") or "").strip()
        subject = title or "该事件"
        return [
            f"{subject}的核心变化是什么",
            "哪些信息已经确认，哪些仍未证实",
            "对开发者和企业用户的影响是什么",
            "后续最值得关注的变量是什么",
        ]

    @staticmethod
    def _trace_dict_to_list(trace: dict[str, dict]) -> list[dict]:
        ordered: list[dict] = []
        for stage, data in trace.items():
            ordered.append({"stage": stage, **data})
        return ordered

    @staticmethod
    def _find_stage_trace(trace: list[dict], stage: str) -> dict:
        for item in trace:
            if str(item.get("stage") or "") == stage:
                return item
        return {}

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
            normalized[str(provider_name)] = dict(config)
        return normalized

    @staticmethod
    def _normalize_monitor_ai_routing(monitor_ai_routing: dict | None) -> dict:
        if not isinstance(monitor_ai_routing, dict):
            return {}

        normalized_stages: dict[str, dict] = {}
        raw_stages = monitor_ai_routing.get("stages")
        if isinstance(raw_stages, dict):
            for stage_name, allowed in _AI_STAGE_ALLOWED_PROVIDERS.items():
                raw_stage = raw_stages.get(stage_name)
                if not isinstance(raw_stage, dict):
                    continue
                primary = str(raw_stage.get("primary") or "").strip()
                if primary in allowed:
                    normalized_stages[stage_name] = {"primary": primary}

        normalized_providers: dict[str, dict] = {}
        raw_providers = monitor_ai_routing.get("providers")
        if isinstance(raw_providers, dict):
            for raw_name, raw_config in raw_providers.items():
                provider_name = str(raw_name).strip()
                if provider_name not in _AI_PROVIDER_NAMES or not isinstance(raw_config, dict):
                    continue

                cleaned: dict[str, object] = {}
                model = str(raw_config.get("model") or "").strip()
                if model:
                    cleaned["model"] = model

                timeout = raw_config.get("timeout_sec")
                if isinstance(timeout, str):
                    timeout = timeout.strip()
                    if timeout.isdigit():
                        timeout = int(timeout)
                if isinstance(timeout, int) and 1 <= timeout <= 600:
                    cleaned["timeout_sec"] = timeout

                max_retry = raw_config.get("max_retry")
                if isinstance(max_retry, str):
                    max_retry = max_retry.strip()
                    if max_retry.isdigit():
                        max_retry = int(max_retry)
                if isinstance(max_retry, int) and 0 <= max_retry <= 10:
                    cleaned["max_retry"] = max_retry

                if cleaned:
                    normalized_providers[provider_name] = cleaned

        normalized: dict[str, dict] = {}
        if normalized_stages:
            normalized["stages"] = normalized_stages
        if normalized_providers:
            normalized["providers"] = normalized_providers
        return normalized

    def _build_runtime_routing_profile(self, monitor_ai_routing: dict | None) -> RoutingProfile:
        normalized = self._normalize_monitor_ai_routing(monitor_ai_routing)
        stages_override = normalized.get("stages", {})
        base = self.routing_profile

        stages = RoutingStages(
            collect=StageRoute(
                primary=base.stages.collect.primary,
                fallback=list(base.stages.collect.fallback),
            ),
            filter=StageRoute(
                primary=base.stages.filter.primary,
                fallback=list(base.stages.filter.fallback),
            ),
            keywords=StageRoute(
                primary=base.stages.keywords.primary,
                fallback=list(base.stages.keywords.fallback),
            ),
            report=StageRoute(
                primary=base.stages.report.primary,
                fallback=list(base.stages.report.fallback),
            ),
            publish=PublishRoute(
                targets=list(base.stages.publish.targets),
                on_failure=dict(base.stages.publish.on_failure),
            ),
            global_summary=StageRoute(
                primary=(
                    base.stages.global_summary.primary
                    if base.stages.global_summary is not None
                    else base.stages.report.primary
                ),
                fallback=list(
                    base.stages.global_summary.fallback
                    if base.stages.global_summary is not None
                    else base.stages.report.fallback
                ),
            ),
        )

        for stage_name in ("filter", "keywords", "global_summary", "report"):
            stage_override = stages_override.get(stage_name, {})
            primary = str(stage_override.get("primary") or "").strip()
            if not primary:
                continue
            allowed = _AI_STAGE_ALLOWED_PROVIDERS.get(stage_name, set())
            if primary not in allowed:
                continue
            getattr(stages, stage_name).primary = primary

        return RoutingProfile(
            name=base.name,
            stages=stages,
            providers={name: dict(cfg) if isinstance(cfg, dict) else {} for name, cfg in base.providers.items()},
        )

    @staticmethod
    def _extract_monitor_provider_overrides(monitor_ai_routing: dict | None) -> dict[str, dict]:
        if not isinstance(monitor_ai_routing, dict):
            return {}
        providers = monitor_ai_routing.get("providers")
        if not isinstance(providers, dict):
            return {}
        normalized: dict[str, dict] = {}
        for provider_name, config in providers.items():
            if not isinstance(config, dict):
                continue
            normalized[str(provider_name)] = dict(config)
        return normalized

    @staticmethod
    def _merge_provider_overrides(user_overrides: dict[str, dict], monitor_overrides: dict[str, dict]) -> dict[str, dict]:
        merged: dict[str, dict] = {}
        for provider_name, config in user_overrides.items():
            if isinstance(config, dict):
                merged[provider_name] = dict(config)
        for provider_name, config in monitor_overrides.items():
            if not isinstance(config, dict):
                continue
            current = merged.get(provider_name, {})
            current.update(config)
            merged[provider_name] = current
        return merged

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
            normalized = Orchestrator._resolve_sink_name(str(target), destination_settings)
            if normalized == str(target) and Orchestrator._looks_like_uuid(str(target)):
                continue
            dedupe_key = Orchestrator._destination_dedupe_key(str(target), destination_settings)
            if dedupe_key in seen:
                continue
            if not destination_ids and normalized != "database":
                setting = destination_settings.get(normalized)
                if setting is not None and setting.get("enabled") is False:
                    continue
            resolved.append(str(target))
            seen.add(dedupe_key)

        if "sink:database" not in seen and "instance:database" not in seen:
            resolved.insert(0, "database")
        return resolved

    @staticmethod
    def _build_sink_config(target: str, report_id: str, destination_settings: dict[str, dict]) -> dict:
        payload = destination_settings.get(str(target), {})
        normalized = normalize_sink_name(str(payload.get("type") or target))
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
                "site_url": "http://localhost:3018",
                "feed_title": "LexDeepResearch Reports",
                "feed_description": "Latest generated reports from LexDeepResearch.",
                "max_items": 20,
            }

        user_destination = payload if payload else destination_settings.get(normalized, {})
        user_config = user_destination.get("config")
        if isinstance(user_config, dict):
            config.update(Orchestrator._normalize_user_sink_config(normalized, user_config))
        if normalized == "rss" and payload.get("id"):
            config["destination_instance_id"] = str(payload["id"])
        return config

    @staticmethod
    def _resolve_sink_name(target: str, destination_settings: dict[str, dict]) -> str:
        payload = destination_settings.get(str(target), {})
        return normalize_sink_name(str(payload.get("type") or target))

    @staticmethod
    def _destination_dedupe_key(target: str, destination_settings: dict[str, dict]) -> str:
        payload = destination_settings.get(str(target), {})
        if payload.get("id"):
            return f"instance:{target}"
        return f"sink:{Orchestrator._resolve_sink_name(target, destination_settings)}"

    @staticmethod
    def _destination_instance_id(target: str, destination_settings: dict[str, dict]) -> str | None:
        payload = destination_settings.get(str(target), {})
        value = str(payload.get("id") or "").strip()
        return value or None

    @staticmethod
    def _destination_instance_name(target: str, destination_settings: dict[str, dict]) -> str | None:
        payload = destination_settings.get(str(target), {})
        value = str(payload.get("name") or "").strip()
        return value or None

    @staticmethod
    def _looks_like_uuid(value: str) -> bool:
        try:
            uuid.UUID(str(value))
        except ValueError:
            return False
        return True

    @staticmethod
    def _published_destination_instance_ids(publish_trace: list[dict]) -> list[str]:
        published: list[str] = []
        for item in publish_trace:
            if item.get("status") != "success":
                continue
            destination_instance_id = str(item.get("destination_instance_id") or "").strip()
            if not destination_instance_id or destination_instance_id in published:
                continue
            published.append(destination_instance_id)
        return published

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
            if user_config.get("mode"):
                obsidian_config["mode"] = str(user_config["mode"])
            if user_config.get("api_url"):
                obsidian_config["api_url"] = str(user_config["api_url"])
            if user_config.get("api_key"):
                obsidian_config["api_key"] = str(user_config["api_key"])
            if user_config.get("target_folder"):
                obsidian_config["target_folder"] = str(user_config["target_folder"])
            if user_config.get("vault_path"):
                obsidian_config["vault_path"] = str(user_config["vault_path"])
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
        return await run_report_with_retry(
            route=route,
            providers=self.runtime_routing_profile.providers,
            provider_overrides=self.runtime_provider_overrides,
            payload=payload,
            provider_getter=get_provider,
        )

    async def _run_global_summary_with_retry(self, route: StageRoute, payload: dict) -> tuple[dict, str]:
        return await run_global_summary_with_retry(
            route=route,
            providers=self.runtime_routing_profile.providers,
            provider_overrides=self.runtime_provider_overrides,
            payload=payload,
            provider_getter=get_provider,
        )

    def _provider_config(self, provider_name: str) -> dict:
        raw_config = self.runtime_routing_profile.providers.get(provider_name, {})
        merged: dict = dict(raw_config) if isinstance(raw_config, dict) else {}
        user_override_config = self.provider_overrides.get(provider_name, {})
        if isinstance(user_override_config, dict):
            merged.update(user_override_config)
        monitor_override_config = self.monitor_provider_overrides.get(provider_name, {})
        if isinstance(monitor_override_config, dict):
            merged.update(monitor_override_config)
        return merged

    @staticmethod
    def _max_retry(provider_config: dict) -> int:
        raw = provider_config.get("max_retry", 0) if isinstance(provider_config, dict) else 0
        try:
            value = int(raw)
        except Exception:
            value = 0
        return max(value, 0)

    @staticmethod
    def _is_timeout_exception(exc: Exception) -> bool:
        return isinstance(exc, (asyncio.TimeoutError, TimeoutError, httpx.TimeoutException))


def _normalize_report_type(value: str | None) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in {"daily", "weekly", "research"}:
        return candidate
    return "daily"


def _count_markdown_heading_level(content: str, level: int) -> int:
    normalized_level = max(int(level), 1)
    prefix = f'{"#" * normalized_level} '
    return sum(1 for line in str(content or "").splitlines() if line.lstrip().startswith(prefix))


def _coerce_uuid(value: uuid.UUID | str) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _item_source_categories(item: ProcessedArticle | ProcessedEvent) -> list[str]:
    if isinstance(item, ProcessedEvent):
        category = str(item.category or "").strip()
        return [category] if category else []
    value = str(item.raw.metadata.get("source_category") or "").strip()
    return [value] if value else []


def _item_keywords(item: ProcessedArticle | ProcessedEvent) -> list[str]:
    return [str(keyword).strip() for keyword in item.keywords if str(keyword).strip()]


def _item_summary(item: ProcessedArticle | ProcessedEvent) -> str:
    return str(item.summary or "").strip()
