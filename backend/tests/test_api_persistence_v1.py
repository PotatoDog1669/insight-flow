"""Persistence-oriented API tests (DB-backed behavior)."""

import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import Monitor, Report, User


def test_reports_reads_seeded_rows_from_database(client: TestClient) -> None:
    response = client.get("/api/v1/reports", params={"time_period": "daily", "report_type": "daily"})
    assert response.status_code == 200

    reports = response.json()
    assert len(reports) == 1
    assert reports[0]["title"] == "Seed Daily Brief"
    assert reports[0]["report_type"] == "daily"
    assert reports[0]["publish_trace"] == []
    assert reports[0]["monitor_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert reports[0]["monitor_name"] == "Seed Monitor"


def test_reports_list_returns_summary_payload_while_detail_keeps_full_content(client: TestClient) -> None:
    list_response = client.get("/api/v1/reports", params={"time_period": "daily", "report_type": "daily"})
    assert list_response.status_code == 200
    reports = list_response.json()
    assert len(reports) == 1
    assert reports[0]["content"] == ""
    assert reports[0]["events"] == []
    assert reports[0]["metadata"] == {}

    detail_response = client.get("/api/v1/reports/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["content"] == "Seed content"
    assert detail["monitor_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert detail["monitor_name"] == "Seed Monitor"


def test_delete_report_removes_row_from_database(client: TestClient, db_session_factory) -> None:
    delete_response = client.delete("/api/v1/reports/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    assert delete_response.status_code == 204

    detail_response = client.get("/api/v1/reports/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    assert detail_response.status_code == 404

    session_factory, _ = db_session_factory

    async def _fetch_report() -> Report | None:
        async with session_factory() as session:
            result = await session.execute(
                select(Report).where(Report.id == uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"))
            )
            return result.scalar_one_or_none()

    report = asyncio.run(_fetch_report())
    assert report is None


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
            "ai_routing": {
                "stages": {
                    "filter": {"primary": "llm_openai"},
                    "keywords": {"primary": "llm_openai"},
                    "report": {"primary": "llm_openai"},
                },
                "providers": {
                    "llm_openai": {"model": "gpt-4o-mini"},
                },
            },
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
    assert monitor.ai_routing["stages"]["filter"]["primary"] == "llm_openai"
    assert monitor.ai_routing["stages"]["keywords"]["primary"] == "llm_openai"
    assert monitor.ai_routing["stages"]["report"]["primary"] == "llm_openai"
    assert monitor.ai_routing["providers"]["llm_openai"]["model"] == "gpt-4o-mini"


def test_update_monitor_with_null_ai_routing_clears_override(client: TestClient, db_session_factory) -> None:
    create_response = client.post(
        "/api/v1/monitors",
        json={
            "name": "Clear Routing Monitor",
            "time_period": "daily",
            "source_ids": ["11111111-1111-1111-1111-111111111111"],
            "ai_routing": {
                "stages": {
                    "filter": {"primary": "llm_openai"},
                }
            },
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["ai_routing"]["stages"]["filter"]["primary"] == "llm_openai"

    update_response = client.patch(
        f"/api/v1/monitors/{created['id']}",
        json={"ai_routing": None},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["ai_routing"]["stages"]["filter"] is None
    assert updated["ai_routing"]["stages"]["keywords"] is None
    assert updated["ai_routing"]["stages"]["report"] is None
    assert updated["ai_routing"]["providers"] == {}

    session_factory, _ = db_session_factory

    async def _fetch_monitor() -> Monitor | None:
        async with session_factory() as session:
            result = await session.execute(select(Monitor).where(Monitor.id == uuid.UUID(created["id"])))
            return result.scalars().first()

    monitor = asyncio.run(_fetch_monitor())
    assert monitor is not None
    assert monitor.ai_routing == {}


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
        "/api/v1/providers/llm_openai",
        json={
            "enabled": True,
            "config": {
                "base_url": "https://api.openai.com/v1/",
                "model": "gpt-4.1-mini",
                "timeout_sec": 45,
                "max_retry": 3,
                "api_key": "sk-live-provider",
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
    assert providers["llm_openai"]["config"]["model"] == "gpt-4.1-mini"


def test_update_codex_provider_persists_to_user_settings(client: TestClient, db_session_factory) -> None:
    response = client.patch(
        "/api/v1/providers/llm_codex",
        json={
            "enabled": True,
            "config": {
                "base_url": "https://api.openai.com/v1/",
                "model": "gpt-5-codex",
                "timeout_sec": 90,
                "max_retry": 1,
                "api_key": "sk-codex-provider",
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
    assert providers["llm_codex"]["enabled"] is True
    assert providers["llm_codex"]["config"]["base_url"] == "https://api.openai.com/v1"
    assert providers["llm_codex"]["config"]["model"] == "gpt-5-codex"
    assert providers["llm_codex"]["config"]["max_retry"] == 1

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


def test_provider_connectivity_test_does_not_persist_unsaved_config(
    client: TestClient,
    db_session_factory,
    monkeypatch,
) -> None:
    save_response = client.patch(
        "/api/v1/providers/llm_openai",
        json={
            "enabled": True,
            "config": {
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
                "timeout_sec": 45,
                "max_retry": 3,
                "api_key": "sk-saved-provider",
            },
        },
    )
    assert save_response.status_code == 200

    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        assert config is not None
        assert config["model"] == "gpt-4.1-mini"
        assert config["api_key"] == "sk-unsaved-provider"
        return {"ok": True, "message": "ready"}

    monkeypatch.setattr("app.api.v1.providers.run_llm_json", _fake_llm)

    test_response = client.post(
        "/api/v1/providers/llm_openai/test",
        json={
            "config": {
                "model": "gpt-4.1-mini",
                "api_key": "sk-unsaved-provider",
            }
        },
    )
    assert test_response.status_code == 200
    assert test_response.json()["success"] is True

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
    assert providers["llm_openai"]["config"]["model"] == "gpt-4o-mini"
    assert providers["llm_openai"]["config"]["api_key"] == "sk-saved-provider"
