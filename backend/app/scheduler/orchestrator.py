"""采集流水线编排器"""

import asyncio
from collections import Counter
from datetime import date, datetime, timezone
import uuid

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import RawArticle
from app.collectors.registry import get_collector
from app.models.article import Article
from app.models.database import async_session
from app.models.report import Report
from app.models.source import Source
from app.models.subscription import UserSubscription
from app.models.task import CollectTask
from app.processors.pipeline import ProcessedArticle, ProcessingPipeline
from app.renderers.base import RenderContext
from app.renderers.l1_brief import L1BriefRenderer
from app.renderers.l2_daily import L2DailyRenderer
from app.sinks.database import DatabaseSink

logger = structlog.get_logger()

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


class Orchestrator:
    """采集流水线编排 — 全局采集 → 加工 → 分发 → 渲染 → 落盘"""

    def __init__(self, max_concurrency: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.pipeline = ProcessingPipeline()
        self.brief_renderer = L1BriefRenderer()
        self.daily_renderer = L2DailyRenderer()
        self.database_sink = DatabaseSink()

    async def collect_source(self, source_id: str, method: str, config: dict) -> list[RawArticle]:
        """采集单个信息源（带并发控制）"""
        async with self.semaphore:
            collector = get_collector(method)
            logger.info("collecting", source_id=source_id, method=method)
            return await collector.collect(config)

    async def run_daily_pipeline(
        self,
        db: AsyncSession | None = None,
        user_id: uuid.UUID = DEFAULT_USER_ID,
        trigger_type: str = "scheduled",
    ) -> dict:
        """执行完整的每日采集编排"""
        if db is not None:
            return await self._run_daily_pipeline(db=db, user_id=user_id, trigger_type=trigger_type)
        async with async_session() as session:
            return await self._run_daily_pipeline(db=session, user_id=user_id, trigger_type=trigger_type)

    async def _run_daily_pipeline(self, db: AsyncSession, user_id: uuid.UUID, trigger_type: str) -> dict:
        subscribed_sources = await self._load_subscribed_sources(db, user_id)
        if not subscribed_sources:
            return {"sources": 0, "processed_articles": 0, "reports_created": 0}

        processed_articles: list[ProcessedArticle] = []
        persisted_article_ids: list[uuid.UUID] = []
        task_rows: dict[uuid.UUID, CollectTask] = {}

        now = datetime.now(timezone.utc)
        for source in subscribed_sources:
            task = CollectTask(
                id=uuid.uuid4(),
                source_id=source.id,
                trigger_type=trigger_type,
                status="pending",
                created_at=now,
            )
            task_rows[source.id] = task
            db.add(task)
        await db.commit()

        for source in subscribed_sources:
            task = task_rows[source.id]
            task.status = "running"
            task.started_at = datetime.now(timezone.utc)
            db.add(task)
            await db.commit()

            try:
                raw_articles = await self.collect_source(
                    source_id=str(source.id),
                    method=source.collect_method,
                    config=source.config or {},
                )
                for raw in raw_articles:
                    raw.metadata.setdefault("source_name", source.name)
                    raw.metadata.setdefault("source_category", source.category)

                processed = await self.pipeline.process(raw_articles)
                article_ids = await self._persist_processed_articles(db, source, processed)
                persisted_article_ids.extend(article_ids)
                processed_articles.extend(processed)

                source.last_collected = datetime.now(timezone.utc)
                task.status = "success"
                task.articles_count = len(article_ids)
                task.finished_at = datetime.now(timezone.utc)
                db.add(source)
                db.add(task)
                await db.commit()
            except Exception as exc:  # pragma: no cover - defensive path
                task.status = "failed"
                task.error_message = str(exc)[:1000]
                task.finished_at = datetime.now(timezone.utc)
                db.add(task)
                await db.commit()

        report_ids = await self._render_and_persist_reports(
            db=db,
            user_id=user_id,
            processed_articles=processed_articles,
            article_ids=persisted_article_ids,
        )
        return {
            "sources": len(subscribed_sources),
            "processed_articles": len(processed_articles),
            "reports_created": len(report_ids),
        }

    async def _load_subscribed_sources(self, db: AsyncSession, user_id: uuid.UUID) -> list[Source]:
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

    async def _persist_processed_articles(
        self, db: AsyncSession, source: Source, processed_articles: list[ProcessedArticle]
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
                existing.status = "processed"
                existing.metadata_ = raw.metadata or {}
                existing.published_at = raw.published_at
                existing.collected_at = now
                existing.updated_at = now
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
    ) -> list[uuid.UUID]:
        if not processed_articles:
            return []

        today = date.today()
        context = RenderContext(date=today.isoformat(), user_id=str(user_id))
        brief_report = await self.brief_renderer.render(processed_articles, context)
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
        tldr = [item.summary for item in processed_articles[:8] if item.summary]
        article_id_strings = [str(item) for item in article_ids]

        report_rows = [
            Report(
                id=uuid.uuid4(),
                user_id=user_id,
                time_period="daily",
                depth="brief",
                title=brief_report.title,
                content=brief_report.content,
                article_ids=article_id_strings,
                metadata_={"categories": categories, "tldr": tldr, "topics": topics, "report_type": "brief"},
                published_to=[],
                report_date=today,
                created_at=datetime.now(timezone.utc),
            ),
            Report(
                id=uuid.uuid4(),
                user_id=user_id,
                time_period="daily",
                depth="deep",
                title=daily_report.title,
                content=daily_report.content,
                article_ids=article_id_strings,
                metadata_={"categories": categories, "tldr": tldr, "topics": topics, "report_type": "deep"},
                published_to=[],
                report_date=today,
                created_at=datetime.now(timezone.utc),
            ),
        ]
        db.add_all(report_rows)
        await db.commit()

        rendered_reports = [brief_report, daily_report]
        for report, rendered in zip(report_rows, rendered_reports):
            publish_result = await self.database_sink.publish(rendered, {"report_id": str(report.id)})
            if publish_result.success:
                report.published_to = [self.database_sink.name]
                db.add(report)
        await db.commit()
        return [row.id for row in report_rows]
