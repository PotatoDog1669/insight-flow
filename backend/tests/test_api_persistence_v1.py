"""Persistence-oriented API tests (DB-backed behavior)."""

import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import Monitor, User


def test_reports_reads_seeded_rows_from_database(client: TestClient) -> None:
    response = client.get("/api/v1/reports", params={"time_period": "daily", "report_type": "daily"})
    assert response.status_code == 200

    reports = response.json()
    assert len(reports) == 1
    assert reports[0]["title"] == "Seed Daily Brief"
    assert reports[0]["report_type"] == "daily"
    assert reports[0]["publish_trace"] == []


def test_update_user_settings_persists_to_database(client: TestClient, db_session_factory) -> None:
    response = client.patch(
        "/api/v1/users/me/settings",
        json={"default_time_period": "daily", "default_report_type": "daily", "default_sink": "notion"},
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
    assert settings["default_report_type"] == "daily"
    assert settings["default_sink"] == "notion"


def test_create_monitor_persists_report_type(client: TestClient, db_session_factory) -> None:
    response = client.post(
        "/api/v1/monitors",
        json={
            "name": "Persisted Monitor",
            "time_period": "custom",
            "report_type": "research",
            "source_ids": ["11111111-1111-1111-1111-111111111111"],
            "destination_ids": ["notion"],
            "source_overrides": {"11111111-1111-1111-1111-111111111111": {"limit": 20}},
        },
    )
    assert response.status_code == 201
    assert response.json()["report_type"] == "research"

    session_factory, _ = db_session_factory

    async def _fetch_monitor() -> Monitor | None:
        async with session_factory() as session:
            result = await session.execute(select(Monitor).where(Monitor.name == "Persisted Monitor"))
            return result.scalars().first()

    monitor = asyncio.run(_fetch_monitor())
    assert monitor is not None
    assert monitor.time_period == "custom"
    assert monitor.report_type == "research"
    assert monitor.destination_ids == ["notion"]
    assert monitor.source_overrides == {"11111111-1111-1111-1111-111111111111": {"limit": 20}}


def test_update_destination_persists_to_user_settings(client: TestClient, db_session_factory) -> None:
    response = client.patch(
        "/api/v1/destinations/notion",
        json={
            "enabled": True,
            "config": {
                "database_id": "https://www.notion.so/3170dd9284fc805ca19bfd4a76db602e?v=3170dd9284fc80f6a693000c0b36598f&source=copy_link",
                "token": "secret",
            },
        },
    )
    assert response.status_code == 200

    session_factory, _ = db_session_factory

    async def _fetch_settings() -> dict:
        async with session_factory() as session:
            result = await session.execute(
                select(User).where(User.id == uuid.UUID("99999999-9999-9999-9999-999999999999"))
            )
            user = result.scalar_one_or_none()
            assert user is not None
            return user.settings

    settings = asyncio.run(_fetch_settings())
    destinations = settings.get("destinations", {})
    assert destinations["notion"]["enabled"] is True
    assert destinations["notion"]["config"]["database_id"] == "3170dd9284fc805ca19bfd4a76db602e"


def test_update_provider_persists_to_user_settings(client: TestClient, db_session_factory) -> None:
    response = client.patch(
        "/api/v1/providers/agent_codex",
        json={
            "enabled": True,
            "config": {
                "auth_mode": "oauth",
                "oauth_token": "oauth-live-token",
                "base_url": "https://gmn.chuangzuoli.com/",
                "model": "gpt-5.3-codex",
            },
        },
    )
    assert response.status_code == 200

    session_factory, _ = db_session_factory

    async def _fetch_settings() -> dict:
        async with session_factory() as session:
            result = await session.execute(
                select(User).where(User.id == uuid.UUID("99999999-9999-9999-9999-999999999999"))
            )
            user = result.scalar_one_or_none()
            assert user is not None
            return user.settings

    settings = asyncio.run(_fetch_settings())
    providers = settings.get("providers", {})
    assert providers["agent_codex"]["enabled"] is True
    assert providers["agent_codex"]["config"]["auth_mode"] == "oauth"
    assert providers["agent_codex"]["config"]["base_url"] == "https://gmn.chuangzuoli.com"


def test_update_llm_provider_persists_to_user_settings(client: TestClient, db_session_factory) -> None:
    response = client.patch(
        "/api/v1/providers/llm_openai",
        json={
            "enabled": True,
            "config": {
                "base_url": "https://api.openai.com/v1/",
                "model": "gpt-4o-mini",
                "timeout_sec": 45,
                "max_retry": 3,
                "api_key": "sk-llm-provider",
            },
        },
    )
    assert response.status_code == 200

    session_factory, _ = db_session_factory

    async def _fetch_settings() -> dict:
        async with session_factory() as session:
            result = await session.execute(
                select(User).where(User.id == uuid.UUID("99999999-9999-9999-9999-999999999999"))
            )
            user = result.scalar_one_or_none()
            assert user is not None
            return user.settings

    settings = asyncio.run(_fetch_settings())
    providers = settings.get("providers", {})
    assert providers["llm_openai"]["enabled"] is True
    assert providers["llm_openai"]["config"]["base_url"] == "https://api.openai.com/v1"
    assert providers["llm_openai"]["config"]["model"] == "gpt-4o-mini"
    assert providers["llm_openai"]["config"]["max_retry"] == 3
