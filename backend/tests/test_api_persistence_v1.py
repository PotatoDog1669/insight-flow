"""Persistence-oriented API tests (DB-backed behavior)."""

import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import Monitor, User


def test_reports_reads_seeded_rows_from_database(client: TestClient) -> None:
    response = client.get("/api/v1/reports", params={"time_period": "daily", "depth": "brief"})
    assert response.status_code == 200

    reports = response.json()
    assert len(reports) == 1
    assert reports[0]["title"] == "Seed Daily Brief"


def test_update_user_settings_persists_to_database(client: TestClient, db_session_factory) -> None:
    response = client.patch(
        "/api/v1/users/me/settings",
        json={"default_time_period": "daily", "default_depth": "brief", "default_sink": "notion"},
    )
    assert response.status_code == 200

    session_factory, _ = db_session_factory

    async def _fetch_settings() -> dict:
        async with session_factory() as session:
            result = await session.execute(select(User).where(User.id == uuid.UUID("99999999-9999-9999-9999-999999999999")))
            user = result.scalar_one_or_none()
            assert user is not None
            return user.settings

    settings = asyncio.run(_fetch_settings())
    assert settings["default_time_period"] == "daily"
    assert settings["default_depth"] == "brief"
    assert settings["default_sink"] == "notion"


def test_create_monitor_inserts_row_into_monitors_table(client: TestClient, db_session_factory) -> None:
    response = client.post(
        "/api/v1/monitors",
        json={
            "name": "Persisted Monitor",
            "time_period": "daily",
            "depth": "brief",
            "source_ids": ["11111111-1111-1111-1111-111111111111"],
        },
    )
    assert response.status_code == 201

    session_factory, _ = db_session_factory

    async def _count_rows() -> int:
        async with session_factory() as session:
            result = await session.execute(select(Monitor).where(Monitor.name == "Persisted Monitor"))
            return len(result.scalars().all())

    assert asyncio.run(_count_rows()) == 1
