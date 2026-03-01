from __future__ import annotations

import asyncio
import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.collectors.base import BaseCollector, RawArticle
from app.models import Article, CollectTask, Report, Source, UserSubscription
from app.scheduler import orchestrator as orchestrator_module
from app.scheduler.orchestrator import Orchestrator

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
SOURCE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


class FakeCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "fake"

    @property
    def category(self) -> str:
        return "blog"

    async def collect(self, config: dict) -> list[RawArticle]:
        return [
            RawArticle(
                external_id="fake-ext-1",
                title="AI breakthrough today",
                url="https://example.com/post",
                content="New AI architecture improves multimodal reasoning and deployment efficiency.",
            )
        ]


@pytest.mark.asyncio
async def test_orchestrator_run_daily_pipeline_persists_articles_tasks_reports(db_session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, _ = db_session_factory

    async def _prepare_subscription() -> None:
        async with session_factory() as session:
            session.add(
                UserSubscription(
                    user_id=DEFAULT_USER_ID,
                    source_id=SOURCE_ID,
                    enabled=True,
                    custom_config={},
                )
            )
            await session.commit()

    await _prepare_subscription()

    monkeypatch.setattr(orchestrator_module, "get_collector", lambda method: FakeCollector())

    orchestrator = Orchestrator(max_concurrency=2)

    async with session_factory() as session:
        result = await orchestrator.run_daily_pipeline(db=session, user_id=DEFAULT_USER_ID, trigger_type="manual")
        assert result["processed_articles"] >= 1

    async def _verify() -> tuple[int, int, int]:
        async with session_factory() as session:
            articles_count = len((await session.execute(select(Article).where(Article.source_id == SOURCE_ID))).scalars().all())
            tasks_count = len((await session.execute(select(CollectTask))).scalars().all())
            reports_count = len(
                (
                    await session.execute(
                        select(Report).where(
                            Report.user_id == DEFAULT_USER_ID,
                            Report.report_date == date.today(),
                        )
                    )
                ).scalars().all()
            )
            return articles_count, tasks_count, reports_count

    article_count, task_count, report_count = await _verify()

    assert article_count >= 1
    assert task_count >= 1
    assert report_count >= 1
