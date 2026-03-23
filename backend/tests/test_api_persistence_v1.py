"""Persistence-oriented API tests (DB-backed behavior)."""

import asyncio
import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import DestinationInstance, Monitor, Report, User
from backend.tests.api_test_helpers import (
    assert_publish_trace_entry,
    destination_create_payload,
    load_user_settings,
    monitor_create_payload,
)


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


def test_reports_list_hides_paper_note_reports_from_summary_views(client: TestClient, db_session_factory) -> None:
    session_factory, _ = db_session_factory

    async def _seed_paper_reports() -> None:
        async with session_factory() as session:
            now = datetime.now(UTC)
            user_id = uuid.UUID("99999999-9999-9999-9999-999999999999")
            monitor_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
            digest_id = uuid.UUID("11111111-2222-3333-4444-555555555555")
            note_id = uuid.UUID("66666666-7777-8888-9999-000000000000")
            digest = Report(
                id=digest_id,
                user_id=user_id,
                time_period="daily",
                report_type="paper",
                title="2026-03-20 论文推荐",
                content="digest content",
                article_ids=[],
                metadata_={
                    "paper_mode": "digest",
                    "monitor_id": str(monitor_id),
                    "monitor_name": "Seed Monitor",
                },
                published_to=[],
                report_date=date.today(),
                created_at=now,
            )
            note = Report(
                id=note_id,
                user_id=user_id,
                time_period="daily",
                report_type="paper",
                title="Single Paper Note",
                content="note content",
                article_ids=[],
                metadata_={
                    "paper_mode": "note",
                    "parent_report_id": str(digest_id),
                    "monitor_id": str(monitor_id),
                    "monitor_name": "Seed Monitor",
                },
                published_to=[],
                report_date=date.today(),
                created_at=now,
            )
            session.add_all([digest, note])
            await session.commit()

    asyncio.run(_seed_paper_reports())

    response = client.get("/api/v1/reports", params={"limit": 20, "page": 1})
    assert response.status_code == 200

    reports = response.json()
    titles = [item["title"] for item in reports]
    assert "2026-03-20 论文推荐" in titles
    assert "Single Paper Note" not in titles


def test_reports_list_derives_paper_digest_tldr_from_intro_when_missing_metadata(
    client: TestClient,
    db_session_factory,
) -> None:
    session_factory, _ = db_session_factory

    async def _seed_paper_digest() -> None:
        async with session_factory() as session:
            now = datetime.now(UTC)
            user_id = uuid.UUID("99999999-9999-9999-9999-999999999999")
            digest = Report(
                id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
                user_id=user_id,
                time_period="daily",
                report_type="paper",
                title="2026-03-20 论文推荐",
                content=(
                    "# 2026-03-20 论文推荐\n\n"
                    "## 今日锐评\n\n"
                    "本期重点不只是新论文数量，而是后训练强化学习与 GUI 奖励建模两条线开始进入更可复用的工程阶段。\n\n"
                    "## World Model\n\n"
                    "### 1. Example Paper"
                ),
                article_ids=[],
                metadata_={
                    "paper_mode": "digest",
                    "monitor_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "monitor_name": "Seed Monitor",
                },
                published_to=[],
                report_date=date.today(),
                created_at=now,
            )
            session.add(digest)
            await session.commit()

    asyncio.run(_seed_paper_digest())

    response = client.get("/api/v1/reports", params={"limit": 20, "page": 1})
    assert response.status_code == 200

    reports = response.json()
    digest = next(item for item in reports if item["title"] == "2026-03-20 论文推荐")
    assert digest["tldr"] == [
        "本期重点不只是新论文数量，而是后训练强化学习与 GUI 奖励建模两条线开始进入更可复用的工程阶段。"
    ]


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
    settings = load_user_settings(session_factory)
    assert settings["default_time_period"] == "daily"
    assert settings["default_report_type"] == "daily"
    assert settings["default_sink"] == "notion"


def test_list_destinations_migrates_legacy_settings_into_default_instances(
    client: TestClient,
    db_session_factory,
) -> None:
    session_factory, _ = db_session_factory

    async def _seed_legacy_settings() -> None:
        async with session_factory() as session:
            user = await session.get(User, uuid.UUID("99999999-9999-9999-9999-999999999999"))
            assert user is not None
            settings = dict(user.settings or {})
            settings["destinations"] = {
                "notion": {
                    "enabled": True,
                    "config": {
                        "token": "secret",
                        "database_id": "legacy-db",
                    },
                },
                "obsidian": {
                    "enabled": True,
                    "config": {
                        "mode": "file",
                        "vault_path": "/tmp/vault",
                        "target_folder": "Research",
                    },
                },
            }
            user.settings = settings
            await session.commit()

    asyncio.run(_seed_legacy_settings())

    response = client.get("/api/v1/destinations")
    assert response.status_code == 200
    payload = response.json()
    assert {item["type"] for item in payload} == {"notion", "obsidian"}
    assert payload[0]["id"] != payload[0]["type"]

    async def _fetch_instances() -> list[DestinationInstance]:
        async with session_factory() as session:
            result = await session.execute(select(DestinationInstance).order_by(DestinationInstance.type.asc()))
            return list(result.scalars().all())

    instances = asyncio.run(_fetch_instances())
    assert [item.type for item in instances] == ["notion", "obsidian"]
    assert instances[0].name == "Notion"
    assert instances[1].name == "Obsidian"


def test_create_monitor_persists_report_type(client: TestClient, db_session_factory) -> None:
    destination_response = client.post(
        "/api/v1/destinations",
        json=destination_create_payload(
            "notion",
            "Research DB",
            config={"database_id": "db_live", "token": "secret"},
        ),
    )
    assert destination_response.status_code == 201
    destination_id = destination_response.json()["id"]

    response = client.post(
        "/api/v1/monitors",
        json=monitor_create_payload(
            "Persisted Monitor",
            ["11111111-1111-1111-1111-111111111111"],
            time_period="custom",
            report_type="research",
            destination_instance_ids=[destination_id],
            source_overrides={"11111111-1111-1111-1111-111111111111": {"limit": 20}},
            ai_routing={
                "stages": {
                    "filter": {"primary": "llm_openai"},
                    "keywords": {"primary": "llm_openai"},
                    "report": {"primary": "llm_openai"},
                },
                "providers": {
                    "llm_openai": {"model": "gpt-4o-mini"},
                },
            },
        ),
    )
    assert response.status_code == 201
    assert response.json()["report_type"] == "research"
    assert response.json()["destination_instance_ids"] == [destination_id]

    session_factory, _ = db_session_factory

    async def _fetch_monitor() -> Monitor | None:
        async with session_factory() as session:
            result = await session.execute(select(Monitor).where(Monitor.name == "Persisted Monitor"))
            return result.scalars().first()

    monitor = asyncio.run(_fetch_monitor())
    assert monitor is not None
    assert monitor.time_period == "custom"
    assert monitor.report_type == "research"
    assert monitor.destination_instance_ids == [destination_id]
    assert monitor.source_overrides == {"11111111-1111-1111-1111-111111111111": {"limit": 20}}
    assert monitor.ai_routing["stages"]["filter"]["primary"] == "llm_openai"
    assert monitor.ai_routing["stages"]["keywords"]["primary"] == "llm_openai"
    assert monitor.ai_routing["stages"]["report"]["primary"] == "llm_openai"
    assert monitor.ai_routing["providers"]["llm_openai"]["model"] == "gpt-4o-mini"


def test_create_monitor_persists_arxiv_expansion_and_single_ai_provider(client: TestClient, db_session_factory) -> None:
    source_create_response = client.post(
        "/api/v1/sources",
        json={
            "name": "arXiv",
            "category": "academic",
            "collect_method": "rss",
            "config": {
                "arxiv_api": True,
                "feed_url": "https://export.arxiv.org/api/query",
                "categories": ["cs.AI"],
            },
            "enabled": True,
        },
    )
    assert source_create_response.status_code == 201
    arxiv_source = source_create_response.json()

    response = client.post(
        "/api/v1/monitors",
        json=monitor_create_payload(
            "Arxiv Intent Monitor",
            [arxiv_source["id"]],
            report_type="paper",
            source_overrides={
                arxiv_source["id"]: {
                    "keywords": ["webagent"],
                    "max_results": 40,
                }
            },
            ai_provider="llm_codex",
        ),
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["ai_provider"] == "llm_codex"
    assert payload["source_overrides"][arxiv_source["id"]]["expanded_keywords"] == [
        "webagent",
        "web agents",
        "web navigation",
        "browser agent",
        "gui agent",
        "computer use",
    ]

    session_factory, _ = db_session_factory

    async def _fetch_monitor() -> Monitor | None:
        async with session_factory() as session:
            result = await session.execute(select(Monitor).where(Monitor.name == "Arxiv Intent Monitor"))
            return result.scalars().first()

    monitor = asyncio.run(_fetch_monitor())
    assert monitor is not None
    assert monitor.source_overrides == {
        arxiv_source["id"]: {
            "keywords": ["webagent"],
            "expanded_keywords": [
                "webagent",
                "web agents",
                "web navigation",
                "browser agent",
                "gui agent",
                "computer use",
            ],
            "max_results": 40,
        }
    }
    assert monitor.ai_routing["stages"]["filter"]["primary"] == "llm_codex"
    assert monitor.ai_routing["stages"]["keywords"]["primary"] == "llm_codex"
    assert monitor.ai_routing["stages"]["global_summary"]["primary"] == "llm_codex"
    assert monitor.ai_routing["stages"]["report"]["primary"] == "llm_codex"
    assert monitor.ai_routing["stages"]["paper_review"]["primary"] == "llm_codex"
    assert monitor.ai_routing["stages"]["paper_note"]["primary"] == "llm_codex"


def test_monitor_agent_draft_can_be_saved_as_monitor(client: TestClient, db_session_factory) -> None:
    agent_response = client.post(
        "/api/v1/monitors/agent",
        json={
            "message": "关注 agent 前沿内容",
        },
    )
    assert agent_response.status_code == 200
    draft_payload = agent_response.json()
    assert draft_payload["mode"] == "draft"
    assert draft_payload["monitor_payload"]["ai_provider"] == "llm_openai"
    assert draft_payload["monitor_payload"]["source_ids"] == ["11111111-1111-1111-1111-111111111111"]
    assert draft_payload["monitor_payload"]["name"] == draft_payload["draft"]["name"]

    create_response = client.post("/api/v1/monitors", json=draft_payload["monitor_payload"])
    assert create_response.status_code == 201
    created_monitor = create_response.json()
    assert created_monitor["name"] == draft_payload["draft"]["name"]
    assert created_monitor["ai_provider"] == "llm_openai"
    assert created_monitor["source_ids"] == ["11111111-1111-1111-1111-111111111111"]

    session_factory, _ = db_session_factory

    async def _fetch_monitor() -> Monitor | None:
        async with session_factory() as session:
            result = await session.execute(select(Monitor).where(Monitor.id == uuid.UUID(created_monitor["id"])))
            return result.scalars().one_or_none()

    monitor = asyncio.run(_fetch_monitor())
    assert monitor is not None
    assert monitor.name == draft_payload["draft"]["name"]
    assert monitor.source_ids == ["11111111-1111-1111-1111-111111111111"]
    assert monitor.custom_schedule == "0 9 * * *"
    assert monitor.ai_routing["stages"]["filter"]["primary"] == "llm_openai"
    assert monitor.ai_routing["stages"]["report"]["primary"] == "llm_openai"


def test_update_monitor_with_null_ai_routing_clears_override(client: TestClient, db_session_factory) -> None:
    create_response = client.post(
        "/api/v1/monitors",
        json=monitor_create_payload(
            "Clear Routing Monitor",
            ["11111111-1111-1111-1111-111111111111"],
            ai_routing={
                "stages": {
                    "filter": {"primary": "llm_openai"},
                }
            },
        ),
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


def test_list_monitors_backfills_legacy_paper_stage_routes_in_response(client: TestClient, db_session_factory) -> None:
    session_factory, _ = db_session_factory

    async def _seed_legacy_monitor() -> None:
        async with session_factory() as session:
            monitor = Monitor(
                id=uuid.uuid4(),
                user_id=uuid.UUID("99999999-9999-9999-9999-999999999999"),
                name="Legacy Paper Monitor",
                time_period="daily",
                report_type="paper",
                source_ids=["11111111-1111-1111-1111-111111111111"],
                source_overrides={},
                ai_routing={
                    "stages": {
                        "filter": {"primary": "llm_codex"},
                        "keywords": {"primary": "llm_codex"},
                        "global_summary": {"primary": "llm_codex"},
                        "report": {"primary": "llm_codex"},
                    }
                },
                destination_ids=[],
                destination_instance_ids=[],
                window_hours=24,
                custom_schedule=None,
                enabled=True,
            )
            session.add(monitor)
            await session.commit()

    asyncio.run(_seed_legacy_monitor())

    response = client.get("/api/v1/monitors")

    assert response.status_code == 200
    items = response.json()
    legacy = next(item for item in items if item["name"] == "Legacy Paper Monitor")
    assert legacy["ai_provider"] == "llm_codex"
    assert legacy["ai_routing"]["stages"]["paper_review"]["primary"] == "llm_codex"
    assert legacy["ai_routing"]["stages"]["paper_note"]["primary"] == "llm_codex"


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
    settings = load_user_settings(session_factory)
    destinations = settings.get("destinations", {})
    assert destinations["notion"]["enabled"] is True
    assert destinations["notion"]["config"]["database_id"] == "3170dd9284fc805ca19bfd4a76db602e"


def test_delete_destination_removes_monitor_bindings(client: TestClient, db_session_factory) -> None:
    destination_response = client.post(
        "/api/v1/destinations",
        json=destination_create_payload(
            "notion",
            "Bound Notion",
            config={"database_id": "db_live", "token": "secret"},
        ),
    )
    assert destination_response.status_code == 201
    destination_id = destination_response.json()["id"]

    monitor_response = client.post(
        "/api/v1/monitors",
        json=monitor_create_payload(
            "Bound Monitor",
            ["11111111-1111-1111-1111-111111111111"],
            destination_instance_ids=[destination_id],
            enabled=True,
        ),
    )
    assert monitor_response.status_code == 201
    monitor_id = monitor_response.json()["id"]

    delete_response = client.delete(f"/api/v1/destinations/{destination_id}")
    assert delete_response.status_code == 204

    session_factory, _ = db_session_factory

    async def _fetch_monitor() -> Monitor | None:
        async with session_factory() as session:
            result = await session.execute(select(Monitor).where(Monitor.id == uuid.UUID(monitor_id)))
            return result.scalars().first()

    monitor = asyncio.run(_fetch_monitor())
    assert monitor is not None
    assert monitor.destination_instance_ids == []


def test_feed_endpoint_reads_rss_instance_specific_reports(client: TestClient, db_session_factory) -> None:
    destination_a = client.post(
        "/api/v1/destinations",
        json=destination_create_payload(
            "rss",
            "Research Feed",
            config={
                "feed_title": "Research Feed",
                "feed_description": "Research-only reports",
            },
        ),
    )
    destination_b = client.post(
        "/api/v1/destinations",
        json=destination_create_payload(
            "rss",
            "Ops Feed",
            config={
                "feed_title": "Ops Feed",
                "feed_description": "Ops-only reports",
            },
        ),
    )
    assert destination_a.status_code == 201
    assert destination_b.status_code == 201
    destination_a_id = destination_a.json()["id"]
    destination_b_id = destination_b.json()["id"]

    session_factory, _ = db_session_factory

    async def _seed_reports() -> None:
        async with session_factory() as session:
            seeded = await session.get(Report, uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"))
            assert seeded is not None
            seeded.published_to = ["rss"]
            seeded.published_destination_instance_ids = [destination_a_id]

            session.add(
                Report(
                    id=uuid.uuid4(),
                    user_id=uuid.UUID("99999999-9999-9999-9999-999999999999"),
                    time_period="daily",
                    report_type="daily",
                    title="Ops Status Brief",
                    content="Ops content",
                    article_ids=[],
                    metadata_={"monitor_name": "Ops Monitor"},
                    published_to=["rss"],
                    published_destination_instance_ids=[destination_b_id],
                    report_date=date.today(),
                )
            )
            await session.commit()

    asyncio.run(_seed_reports())

    response = client.get("/api/v1/feed.xml", params={"destination_id": destination_a_id})
    assert response.status_code == 200
    body = response.text
    assert "Research Feed" in body
    assert "Seed Daily Brief" in body
    assert "Ops Status Brief" not in body


def test_feed_endpoint_rejects_disabled_rss_destination(client: TestClient) -> None:
    destination_response = client.post(
        "/api/v1/destinations",
        json=destination_create_payload(
            "rss",
            "Disabled Feed",
            enabled=False,
            config={
                "feed_title": "Disabled Feed",
                "feed_description": "Should not be public",
            },
        ),
    )
    assert destination_response.status_code == 201
    destination_id = destination_response.json()["id"]

    response = client.get("/api/v1/feed.xml", params={"destination_id": destination_id})
    assert response.status_code == 404


def test_manual_report_publish_persists_trace_and_destination(
    client: TestClient,
    db_session_factory,
    monkeypatch,
) -> None:
    create_response = client.post(
        "/api/v1/destinations",
        json=destination_create_payload(
            "obsidian",
            "Research Vault",
            config={
                "mode": "file",
                "vault_path": "/tmp/obsidian-vault",
                "target_folder": "Reports",
            },
        ),
    )
    assert create_response.status_code == 201
    destination_id = create_response.json()["id"]

    class _FakeSink:
        name = "obsidian"

        async def publish(self, report, config):
            return SimpleNamespace(
                success=True,
                sink_name="obsidian",
                url="/tmp/obsidian-vault/Reports/Seed Daily Brief.md",
                error=None,
            )

    monkeypatch.setattr("app.api.v1.reports.get_sink", lambda name: _FakeSink())

    response = client.post(
        "/api/v1/reports/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/publish",
        json={"destination_instance_ids": [destination_id]},
    )
    assert response.status_code == 200

    session_factory, _ = db_session_factory

    async def _fetch_report() -> Report | None:
        async with session_factory() as session:
            result = await session.execute(
                select(Report).where(Report.id == uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"))
            )
            return result.scalar_one_or_none()

    report = asyncio.run(_fetch_report())
    assert report is not None
    assert "obsidian" in (report.published_to or [])
    assert report.published_destination_instance_ids == [destination_id]
    assert report.publish_trace
    assert_publish_trace_entry(
        report.publish_trace[-1],
        sink="obsidian",
        status="success",
        destination_instance_id=destination_id,
        destination_instance_name="Research Vault",
    )


@pytest.mark.parametrize(
    ("provider_id", "payload", "expected_config"),
    [
        (
            "llm_openai",
            {
                "enabled": True,
                "config": {
                    "base_url": "https://api.openai.com/v1/",
                    "model": "gpt-4.1-mini",
                    "timeout_sec": 45,
                    "max_retry": 3,
                    "api_key": "sk-live-provider",
                },
            },
            {
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4.1-mini",
                "max_retry": 3,
            },
        ),
        (
            "llm_codex",
            {
                "enabled": True,
                "config": {
                    "base_url": "https://api.openai.com/v1/",
                    "model": "gpt-5-codex",
                    "timeout_sec": 90,
                    "max_retry": 1,
                    "api_key": "sk-codex-provider",
                },
            },
            {
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-5-codex",
                "max_retry": 1,
            },
        ),
    ],
)
def test_update_provider_persists_to_user_settings(
    client: TestClient,
    db_session_factory,
    provider_id: str,
    payload: dict,
    expected_config: dict[str, str | int],
) -> None:
    response = client.patch(f"/api/v1/providers/{provider_id}", json=payload)
    assert response.status_code == 200

    session_factory, _ = db_session_factory
    settings = load_user_settings(session_factory)
    providers = settings.get("providers", {})
    assert providers[provider_id]["enabled"] is True
    assert providers[provider_id]["config"]["base_url"] == expected_config["base_url"]
    assert providers[provider_id]["config"]["model"] == expected_config["model"]
    assert providers[provider_id]["config"]["max_retry"] == expected_config["max_retry"]


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
