"""Shared pytest fixtures for API tests."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.models import Monitor, Report, Source, User
from app.models.database import Base, get_db


@pytest.fixture()
def db_session_factory(tmp_path: Path):
    db_path = tmp_path / "api-tests.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(db_url, future=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        now = datetime.now(timezone.utc)
        async with session_factory() as session:
            source = Source(
                id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
                name="Seed Source",
                category="blog",
                collect_method="rss",
                config={"url": "https://example.com/rss"},
                enabled=True,
                created_at=now,
                updated_at=now,
            )
            user = User(
                id=uuid.UUID("99999999-9999-9999-9999-999999999999"),
                email="admin@lexmount.com",
                name="Lex Researcher",
                settings={"default_time_period": "daily", "default_report_type": "daily", "default_sink": "notion"},
                created_at=now,
                updated_at=now,
            )
            monitor = Monitor(
                id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                user_id=user.id,
                name="Seed Monitor",
                time_period="daily",
                report_type="daily",
                source_ids=[str(source.id)],
                custom_schedule=None,
                enabled=True,
                last_run=now,
                created_at=now,
                updated_at=now,
            )
            report = Report(
                id=uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
                user_id=user.id,
                time_period="daily",
                report_type="daily",
                title="Seed Daily Brief",
                content="Seed content",
                article_ids=[],
                metadata_={"categories": ["blog"], "tldr": ["Seed TL;DR"]},
                published_to=["notion"],
                report_date=date.today(),
                created_at=now,
            )
            session.add_all([source, user, monitor, report])
            await session.commit()

    asyncio.run(_setup())
    yield session_factory, engine
    asyncio.run(engine.dispose())


@pytest.fixture()
def client(db_session_factory):
    session_factory, _ = db_session_factory

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
