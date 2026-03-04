"""Persistence tests for sources/articles/tasks endpoints."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.models import Article, CollectTask, Source


SOURCE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def test_create_update_delete_source_persists_to_database(client, db_session_factory) -> None:
    create_resp = client.post(
        "/api/v1/sources",
        json={
            "name": "Persisted Source",
            "category": "blog",
            "collect_method": "rss",
            "config": {"feed_url": "https://example.com/feed.xml"},
            "enabled": True,
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    created_id = uuid.UUID(created["id"])

    session_factory, _ = db_session_factory

    async def _fetch_created() -> Source | None:
        async with session_factory() as session:
            return await session.get(Source, created_id)

    source = asyncio.run(_fetch_created())
    assert source is not None
    assert source.name == "Persisted Source"

    update_resp = client.patch(f"/api/v1/sources/{created_id}", json={"enabled": False, "name": "Persisted Source 2"})
    assert update_resp.status_code == 200

    async def _fetch_updated() -> Source | None:
        async with session_factory() as session:
            return await session.get(Source, created_id)

    updated = asyncio.run(_fetch_updated())
    assert updated is not None
    assert updated.enabled is False
    assert updated.name == "Persisted Source 2"

    delete_resp = client.delete(f"/api/v1/sources/{created_id}")
    assert delete_resp.status_code == 204

    async def _fetch_deleted() -> Source | None:
        async with session_factory() as session:
            return await session.get(Source, created_id)

    assert asyncio.run(_fetch_deleted()) is None


def test_articles_reads_database_rows(client, db_session_factory) -> None:
    session_factory, _ = db_session_factory
    article_id = uuid.uuid4()

    async def _seed_article() -> None:
        now = datetime.now(timezone.utc)
        async with session_factory() as session:
            session.add(
                Article(
                    id=article_id,
                    source_id=SOURCE_ID,
                    external_id=f"seed-{article_id}",
                    title="Persisted Article",
                    url="https://example.com/article",
                    raw_content="full text",
                    summary="short summary",
                    keywords=["ai", "agent"],
                    ai_score=0.9,
                    status="processed",
                    source_type="primary",
                    metadata_={},
                    published_at=now,
                    collected_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

    asyncio.run(_seed_article())

    response = client.get("/api/v1/articles", params={"status": "processed"})
    assert response.status_code == 200

    items = response.json()
    assert any(item["id"] == str(article_id) for item in items)



def test_trigger_collect_creates_task_row(client, db_session_factory) -> None:
    response = client.post("/api/v1/tasks/trigger", json={"source_id": str(SOURCE_ID)})
    assert response.status_code == 200

    task = response.json()
    task_id = uuid.UUID(task["id"])
    assert task["source_id"] == str(SOURCE_ID)
    assert task["status"] in {"pending", "running", "success"}
    assert task["stage_trace"] == []

    session_factory, _ = db_session_factory

    async def _fetch_task() -> CollectTask | None:
        async with session_factory() as session:
            return await session.get(CollectTask, task_id)

    db_task = asyncio.run(_fetch_task())
    assert db_task is not None

    get_resp = client.get(f"/api/v1/tasks/{task_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == str(task_id)

    list_resp = client.get("/api/v1/tasks")
    assert list_resp.status_code == 200
    assert any(item["id"] == str(task_id) for item in list_resp.json())

    # category filter should include this task because source is blog
    filtered_resp = client.get("/api/v1/tasks", params={"category": "blog"})
    assert filtered_resp.status_code == 200
    assert any(item["id"] == str(task_id) for item in filtered_resp.json())
