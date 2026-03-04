from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.database import Base
from app.models.report import Report
from app.renderers.base import Report as RenderedReport
from app.sinks.registry import get_sink


@pytest.mark.asyncio
async def test_registry_supports_rss_sink() -> None:
    sink = get_sink("rss")
    assert sink.name == "rss"


@pytest.mark.asyncio
async def test_rss_sink_generates_feed_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.sinks.rss import RssSink

    db_path = tmp_path / "rss-sink.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _prepare() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        now = datetime.now(timezone.utc)
        async with session_factory() as session:
            session.add(
                Report(
                    id=uuid.uuid4(),
                    user_id=uuid.uuid4(),
                    time_period="daily",
                    report_type="daily",
                    title="Feed Seed Report",
                    content="# Feed Seed\n\n- Item",
                    article_ids=[],
                    metadata_={"global_tldr": "Seed summary"},
                    published_to=[],
                    report_date=date.today(),
                    created_at=now,
                )
            )
            await session.commit()

    await _prepare()
    monkeypatch.setattr("app.sinks.rss.async_session", session_factory)

    feed_path = tmp_path / "feed.xml"
    sink = RssSink()
    result = await sink.publish(
        RenderedReport(level="L2", title="Generated", content="# X", article_ids=[]),
        {
            "feed_path": str(feed_path),
            "site_url": "https://app.example.com",
            "feed_url": "https://api.example.com/api/v1/feed.xml",
            "max_items": 20,
        },
    )

    assert result.success is True
    assert feed_path.exists()
    xml_body = feed_path.read_text(encoding="utf-8")
    assert "<rss" in xml_body
    assert "Feed Seed Report" in xml_body
    assert "<content:encoded>" in xml_body

    await engine.dispose()
