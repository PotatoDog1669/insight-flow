"""Deterministic local E2E smoke check for the daily pipeline."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import uuid
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.collectors.base import BaseCollector, RawArticle
from app.collectors.registry import register
from app.models import Article, CollectTask, Report, Source, User, UserSubscription
from app.models.database import Base
from app.scheduler.orchestrator import Orchestrator

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
SOURCE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SMOKE_DB = ROOT / ".smoke_e2e.db"


@register("smoke_fake")
class SmokeFakeCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "smoke_fake"

    @property
    def category(self) -> str:
        return "blog"

    async def collect(self, config: dict) -> list[RawArticle]:
        return [
            RawArticle(
                external_id="smoke-article-1",
                title="Open source AI agent release benchmark",
                url="https://example.com/smoke",
                content=(
                    "This open source AI agent release includes benchmark, model reasoning improvements, "
                    "and production deployment notes for engineering teams."
                ),
                published_at=datetime.now(timezone.utc),
                metadata={"source_name": "Smoke Source", "source_category": "blog"},
            )
        ]


async def seed(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        User(
            id=DEFAULT_USER_ID,
            email="admin@lexmount.com",
            name="Lex Researcher",
            settings={"default_time_period": "daily", "default_depth": "brief", "default_sink": "database"},
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        Source(
            id=SOURCE_ID,
            name="Smoke Source",
            category="blog",
            collect_method="smoke_fake",
            config={},
            enabled=True,
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        UserSubscription(
            id=uuid.uuid4(),
            user_id=DEFAULT_USER_ID,
            source_id=SOURCE_ID,
            enabled=True,
            custom_config={},
            created_at=now,
        )
    )
    await session.commit()


async def run() -> int:
    if SMOKE_DB.exists():
        SMOKE_DB.unlink()

    engine = create_async_engine(f"sqlite+aiosqlite:///{SMOKE_DB}", future=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        await seed(session)

    async with session_factory() as session:
        orchestrator = Orchestrator(max_concurrency=1)
        result = await orchestrator.run_daily_pipeline(db=session, user_id=DEFAULT_USER_ID, trigger_type="manual")
        print("pipeline_result", result)

    async with session_factory() as session:
        article_count = len((await session.execute(select(Article))).scalars().all())
        task_count = len((await session.execute(select(CollectTask))).scalars().all())
        reports = (await session.execute(select(Report))).scalars().all()
        report_count = len(reports)
        publish_trace_ok = all(isinstance((report.publish_trace or []), list) for report in reports)
        published_to_ok = all("database" in (report.published_to or []) for report in reports)

    await engine.dispose()

    ok = article_count >= 1 and task_count >= 1 and report_count >= 1 and publish_trace_ok and published_to_ok
    print(
        f"articles={article_count} tasks={task_count} reports={report_count} "
        f"publish_trace_ok={publish_trace_ok} published_to_ok={published_to_ok}"
    )
    print("SMOKE_E2E", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
