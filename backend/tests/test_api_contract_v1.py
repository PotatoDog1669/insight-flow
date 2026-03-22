"""API v1 contract tests for frontend integration."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import CollectTask
from backend.tests.api_test_helpers import (
    assert_publish_trace_entry,
    destination_create_payload,
    monitor_create_payload,
)


def test_health_contract_uses_insight_flow_brand(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    payload = res.json()
    assert payload["service"] == "Insight Flow"


def test_openapi_title_uses_insight_flow_brand(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["info"]["title"] == "Insight Flow"


def test_openapi_contains_new_dashboard_routes(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json()["paths"]
    assert "/api/v1/sources" in paths
    assert "/api/v1/monitors" in paths
    assert "/api/v1/monitors/ai-routing/defaults" in paths
    assert "/api/v1/monitors/{monitor_id}/run" in paths
    assert "/api/v1/monitors/{monitor_id}/runs/{run_id}/cancel" in paths
    assert "/api/v1/reports" in paths
    assert "/api/v1/reports/{report_id}" in paths
    assert "/api/v1/reports/{report_id}/publish" in paths
    assert "/api/v1/reports/filters" in paths
    assert "/api/v1/users/me" in paths
    assert "/api/v1/articles" in paths
    assert "/api/v1/destinations" in paths
    assert "/api/v1/destinations/obsidian/discover" in paths
    assert "/api/v1/destinations/{destination_id}" in paths
    assert "/api/v1/destinations/{destination_id}/test" in paths
    assert "/api/v1/providers" in paths
    assert "/api/v1/providers/{provider_id}" in paths
    assert "/api/v1/providers/{provider_id}/test" in paths
    assert "/api/v1/feed.xml" in paths


def test_sources_contract_includes_runtime_status_fields(client: TestClient) -> None:
    response = client.get("/api/v1/sources")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

    item = data[0]
    assert "status" in item
    assert "last_run" in item
    assert "target_url" in item
    assert item["status"] in {"healthy", "error", "running"}


def test_monitors_ai_routing_defaults_contract(client: TestClient) -> None:
    response = client.get("/api/v1/monitors/ai-routing/defaults")
    assert response.status_code == 200
    data = response.json()
    assert data["profile_name"]
    assert data["stages"]["filter"] in {"rule", "llm_openai", "llm_codex"}
    assert data["stages"]["keywords"] in {"rule", "llm_openai", "llm_codex"}
    assert data["stages"]["paper_review"] in {"llm_openai", "llm_codex"}
    assert data["stages"]["paper_note"] in {"llm_openai", "llm_codex"}
    assert data["stages"]["report"] in {"llm_openai", "llm_codex"}


def test_monitors_contract_supports_list_create_and_run(client: TestClient, monkeypatch) -> None:
    destination_a = client.post(
        "/api/v1/destinations",
        json=destination_create_payload(
            "notion",
            "Daily DB",
            config={"database_id": "db_daily", "token": "secret-a"},
        ),
    )
    destination_b = client.post(
        "/api/v1/destinations",
        json=destination_create_payload(
            "rss",
            "Daily Feed",
            config={"feed_url": "http://localhost:8000/api/v1/feed-daily.xml"},
        ),
    )
    assert destination_a.status_code == 201
    assert destination_b.status_code == 201
    destination_instance_ids = [destination_a.json()["id"], destination_b.json()["id"]]

    list_response = client.get("/api/v1/monitors")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert isinstance(listed, list)
    assert len(listed) > 0
    assert "time_period" in listed[0]
    assert "report_type" in listed[0]
    assert "source_ids" in listed[0]
    assert "ai_routing" in listed[0]
    assert "ai_provider" in listed[0]

    create_response = client.post(
        "/api/v1/monitors",
        json=monitor_create_payload(
            "Daily Open Source Brief",
            [listed[0]["source_ids"][0]],
            report_type="research",
            destination_instance_ids=destination_instance_ids,
            source_overrides={
                listed[0]["source_ids"][0]: {
                    "max_items": 9,
                    "limit": 12,
                    "max_results": 40,
                    "keywords": ["reasoning", "agent"],
                    "subreddits": ["r/LocalLLaMA", "OpenAI", "openai"],
                }
            },
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
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Daily Open Source Brief"
    assert created["time_period"] == "daily"
    assert created["report_type"] == "research"
    assert created["destination_instance_ids"] == destination_instance_ids
    assert created["window_hours"] == 24
    assert created["source_overrides"][created["source_ids"][0]]["max_items"] == 9
    assert created["source_overrides"][created["source_ids"][0]]["limit"] == 12
    assert created["source_overrides"][created["source_ids"][0]]["max_results"] == 40
    assert created["source_overrides"][created["source_ids"][0]]["keywords"] == ["reasoning", "agent"]
    assert created["source_overrides"][created["source_ids"][0]]["subreddits"] == ["LocalLLaMA", "OpenAI"]
    assert created["ai_routing"]["stages"]["filter"]["primary"] == "llm_openai"
    assert created["ai_routing"]["stages"]["keywords"]["primary"] == "llm_openai"
    assert created["ai_routing"]["stages"]["report"]["primary"] == "llm_openai"
    assert created["ai_routing"]["providers"]["llm_openai"]["model"] == "gpt-4o-mini"

    captured: dict = {}

    class _FakeOrchestrator:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def run_daily_pipeline(self, **kwargs):
            captured.update(kwargs)
            return {
                "sources": 1,
                "processed_articles": 2,
                "reports_created": 1,
                "status": "success",
                "source_tasks": [
                    {
                        "source_id": created["source_ids"][0],
                        "status": "success",
                        "articles_count": 2,
                        "stage_trace": [
                            {"stage": "collect", "provider": "rss", "status": "success", "articles": 2},
                            {"stage": "process", "provider": "pipeline", "status": "success", "articles": 2},
                            {"stage": "persist", "provider": "database", "status": "success", "articles": 2},
                        ],
                    }
                ],
                "publish_reports": [
                    {
                        "report_type": "daily",
                        "publish_trace": [
                            {
                                "stage": "publish",
                                "sink": "database",
                                "provider": "database",
                                "status": "success",
                                "url": "database://ok",
                                "error": None,
                                "latency_ms": 1,
                            }
                        ],
                    }
                ],
            }

    monkeypatch.setattr("app.scheduler.monitor_runner.Orchestrator", _FakeOrchestrator)

    async def _fake_execute(monitor_id, task_id, trigger_type, window_hours_override):
        from app.main import app
        from app.models.database import get_db
        from app.scheduler.monitor_runner import execute_monitor_pipeline
        # Use the test's dependency override to get a session
        generator = app.dependency_overrides.get(get_db, get_db)()
        session = await generator.__anext__()
        try:
            from app.models.monitor import Monitor
            from app.models.task import CollectTask
            monitor = await session.get(Monitor, monitor_id)
            task = await session.get(CollectTask, task_id)
            await execute_monitor_pipeline(
                db=session,
                monitor=monitor,
                task=task,
                trigger_type=trigger_type,
                window_hours_override=window_hours_override
            )
        finally:
            try:
                await generator.__anext__()
            except StopAsyncIteration:
                pass

    monkeypatch.setattr("app.api.v1.monitors._background_execute_monitor", _fake_execute)

    run_response = client.post(f"/api/v1/monitors/{created['id']}/run")
    assert run_response.status_code == 200
    run_data = run_response.json()
    assert "task_id" in run_data
    assert "run_id" in run_data
    assert run_data["status"] in {"pending", "running"}
    assert captured["trigger_type"] == "manual"
    assert captured["monitor_id"] == uuid.UUID(created["id"])
    assert captured["destination_ids"] == ["database", *destination_instance_ids]
    assert captured["source_ids"] == [uuid.UUID(created["source_ids"][0])]
    assert captured["report_type"] == "research"
    assert captured["window_hours"] == 24
    assert captured["source_overrides"][created["source_ids"][0]]["max_items"] == 9
    assert captured["source_overrides"][created["source_ids"][0]]["limit"] == 12
    assert captured["source_overrides"][created["source_ids"][0]]["max_results"] == 40
    assert captured["source_overrides"][created["source_ids"][0]]["keywords"] == ["reasoning", "agent"]
    assert captured["source_overrides"][created["source_ids"][0]]["subreddits"] == ["LocalLLaMA", "OpenAI"]
    assert captured["monitor_ai_routing"]["stages"]["filter"]["primary"] == "llm_openai"
    assert captured["monitor_ai_routing"]["stages"]["keywords"]["primary"] == "llm_openai"
    assert captured["monitor_ai_routing"]["stages"]["report"]["primary"] == "llm_openai"
    assert captured["monitor_ai_routing"]["providers"]["llm_openai"]["model"] == "gpt-4o-mini"

    logs_response = client.get(f"/api/v1/monitors/{created['id']}/logs")
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) >= 1
    trace = logs[0]["stage_trace"]
    stages = {item.get("stage") for item in trace if isinstance(item, dict)}
    assert "collect" in stages
    assert "process" in stages
    assert "persist" in stages
    assert "publish" in stages


def test_monitors_contract_expands_arxiv_keywords_and_accepts_single_ai_provider(client: TestClient) -> None:
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

    create_response = client.post(
        "/api/v1/monitors",
        json=monitor_create_payload(
            "Daily Paper Intent",
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
    assert create_response.status_code == 201

    created = create_response.json()
    arxiv_override = created["source_overrides"][arxiv_source["id"]]
    assert created["ai_provider"] == "llm_codex"
    assert arxiv_override["keywords"] == ["webagent"]
    assert arxiv_override["expanded_keywords"] == [
        "webagent",
        "web agents",
        "web navigation",
        "browser agent",
        "gui agent",
        "computer use",
    ]
    assert created["ai_routing"]["stages"]["filter"]["primary"] == "llm_codex"
    assert created["ai_routing"]["stages"]["keywords"]["primary"] == "llm_codex"
    assert created["ai_routing"]["stages"]["global_summary"]["primary"] == "llm_codex"
    assert created["ai_routing"]["stages"]["report"]["primary"] == "llm_codex"
    assert created["ai_routing"]["stages"]["paper_review"]["primary"] == "llm_codex"
    assert created["ai_routing"]["stages"]["paper_note"]["primary"] == "llm_codex"


def test_reports_contract_supports_manual_publish(client: TestClient, monkeypatch) -> None:
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
    payload = response.json()
    assert "obsidian" in payload["published_to"]
    assert payload["published_destination_instance_ids"] == [destination_id]
    trace = payload["publish_trace"]
    assert isinstance(trace, list)
    assert_publish_trace_entry(
        trace[-1],
        sink="obsidian",
        status="success",
        url="/tmp/obsidian-vault/Reports/Seed Daily Brief.md",
        destination_instance_id=destination_id,
        destination_instance_name="Research Vault",
    )


def test_monitors_contract_supports_run_cancel(client: TestClient, monkeypatch) -> None:
    listed = client.get("/api/v1/monitors").json()
    source_id = listed[0]["source_ids"][0]
    create_response = client.post(
        "/api/v1/monitors",
        json=monitor_create_payload("Cancelable monitor", [source_id]),
    )
    assert create_response.status_code == 201
    created = create_response.json()

    async def _fake_prepare_monitor_run(
        *,
        db: AsyncSession,
        monitor,
        trigger_type: str,
    ) -> CollectTask:
        now = datetime.now(UTC)
        task = CollectTask(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            monitor_id=monitor.id,
            source_id=None,
            trigger_type=trigger_type,
            status="running",
            started_at=now,
            created_at=now,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    async def _fake_execute(*args, **kwargs):
        pass

    monkeypatch.setattr("app.api.v1.monitors.prepare_monitor_run", _fake_prepare_monitor_run)
    monkeypatch.setattr("app.api.v1.monitors._background_execute_monitor", _fake_execute)

    run_response = client.post(f"/api/v1/monitors/{created['id']}/run")
    assert run_response.status_code == 200
    run_payload = run_response.json()

    cancel_response = client.post(f"/api/v1/monitors/{created['id']}/runs/{run_payload['run_id']}/cancel")
    assert cancel_response.status_code == 200
    cancel_payload = cancel_response.json()
    assert cancel_payload["monitor_id"] == created["id"]
    assert cancel_payload["run_id"] == run_payload["run_id"]
    assert cancel_payload["status"] == "cancelling"

    runs_response = client.get(f"/api/v1/monitors/{created['id']}/runs")
    assert runs_response.status_code == 200
    runs = runs_response.json()
    assert runs
    assert runs[0]["run_id"] == run_payload["run_id"]
    assert runs[0]["status"] in {"cancelling", "cancelled"}


def test_monitors_contract_rejects_invalid_report_stage_provider(client: TestClient) -> None:
    listed = client.get("/api/v1/monitors").json()
    source_id = listed[0]["source_ids"][0]
    response = client.post(
        "/api/v1/monitors",
        json=monitor_create_payload(
            "Invalid AI routing",
            [source_id],
            ai_routing={
                "stages": {
                    "report": {"primary": "rule"},
                }
            },
        ),
    )
    assert response.status_code == 422


def test_reports_contract_supports_filters_endpoint(client: TestClient) -> None:
    list_response = client.get(
        "/api/v1/reports",
        params={"time_period": "daily", "report_type": "daily", "limit": 10, "page": 1},
    )
    assert list_response.status_code == 200
    reports = list_response.json()
    assert isinstance(reports, list)
    assert len(reports) > 0
    assert reports[0]["time_period"] == "daily"
    assert reports[0]["report_type"] == "daily"
    assert "events" in reports[0]
    assert isinstance(reports[0]["events"], list)
    assert "global_tldr" in reports[0]
    assert reports[0]["monitor_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert reports[0]["monitor_name"] == "Seed Monitor"

    filters_response = client.get("/api/v1/reports/filters")
    assert filters_response.status_code == 200
    filters_data = filters_response.json()
    assert "time_periods" in filters_data
    assert "report_types" in filters_data
    assert "categories" in filters_data
    assert "monitors" in filters_data
    assert filters_data["monitors"] == [
        {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "name": "Seed Monitor"}
    ]


def test_users_me_contract_supports_profile_and_settings_update(client: TestClient) -> None:
    profile_response = client.get("/api/v1/users/me")
    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert "id" in profile
    assert "email" in profile
    assert "plan" in profile
    assert profile["email"] == "admin@example.com"

    update_response = client.patch(
        "/api/v1/users/me/settings",
        json={"default_time_period": "daily", "default_report_type": "daily"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["default_time_period"] == "daily"
    assert updated["default_report_type"] == "daily"


def test_destinations_contract_supports_list_and_update(client: TestClient) -> None:
    list_response = client.get("/api/v1/destinations")
    assert list_response.status_code == 200
    items = list_response.json()
    assert isinstance(items, list)
    assert items == []

    update_response = client.patch(
        "/api/v1/destinations/notion",
        json={"enabled": True, "config": {"database_id": "db_live"}},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["id"] != "notion"
    assert updated["type"] == "notion"
    assert updated["enabled"] is True
    assert updated["config"]["database_id"] == "db_live"


def test_destinations_contract_supports_instance_crud(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/destinations",
        json=destination_create_payload(
            "notion",
            "Research DB",
            config={
                "token": "secret",
                "database_id": "3170dd9284fc805ca19bfd4a76db602e",
            },
        ),
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["type"] == "notion"
    assert created["name"] == "Research DB"
    assert created["id"] != "notion"

    patch_response = client.patch(
        f"/api/v1/destinations/{created['id']}",
        json={
            "name": "Research DB 2",
            "config": {
                "parent_page_id": "https://www.notion.so/workspace/Page-3170dd9284fc805ca19bfd4a76db602e",
            },
        },
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["name"] == "Research DB 2"
    assert patched["config"]["parent_page_id"] == "3170dd9284fc805ca19bfd4a76db602e"

    test_response = client.post(f"/api/v1/destinations/{created['id']}/test")
    assert test_response.status_code == 200
    tested = test_response.json()
    assert tested["success"] is True
    assert tested["mode"] == "config"

    delete_response = client.delete(f"/api/v1/destinations/{created['id']}")
    assert delete_response.status_code == 204

    list_response = client.get("/api/v1/destinations")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert all(item["id"] != created["id"] for item in listed)


def test_feed_contract_returns_rss_xml(client: TestClient) -> None:
    response = client.get("/api/v1/feed.xml")
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("application/rss+xml")
    body = response.text
    assert "<rss" in body
    assert "<channel>" in body
    assert "<item>" in body
    assert "Seed Daily Brief" in body


def test_destinations_update_parses_notion_database_url(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/destinations/notion",
        json={
            "enabled": True,
            "config": {
                "database_id": "https://www.notion.so/3170dd9284fc805ca19bfd4a76db602e?v=3170dd9284fc80f6a693000c0b36598f&source=copy_link"
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["database_id"] == "3170dd9284fc805ca19bfd4a76db602e"


def test_destinations_contract_supports_obsidian_connectivity_test(client: TestClient, monkeypatch) -> None:
    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str):
            assert url == "https://127.0.0.1:27124/"
            return httpx.Response(200, request=httpx.Request("GET", url), json={"status": "ok"})

    from app.api.v1 import destinations as destinations_module

    monkeypatch.setattr(
        destinations_module,
        "httpx",
        SimpleNamespace(AsyncClient=lambda *args, **kwargs: StubClient(), HTTPError=httpx.HTTPError),
        raising=False,
    )

    response = client.post(
        "/api/v1/destinations/obsidian/test",
        json={
            "config": {
                "mode": "rest",
                "api_url": " https://127.0.0.1:27124/ ",
                "api_key": "obsidian-secret",
                "target_folder": "AI-Reports/",
            }
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["success"] is True
    assert payload["mode"] == "rest"
    assert payload["checked_target"] == "https://127.0.0.1:27124"
    assert payload["message"] == "Obsidian REST API reachable"
    assert isinstance(payload["latency_ms"], int)


def test_destinations_contract_supports_obsidian_vault_discovery(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.v1.destinations._discover_obsidian_vaults",
        lambda: [
            {"path": "/Users/leo/Documents/Obsidian Vault", "name": "Obsidian Vault", "open": True, "ts": 1},
            {"path": "/Users/leo/Documents/Archive Vault", "name": "Archive Vault", "open": False, "ts": 0},
        ],
    )

    response = client.get("/api/v1/destinations/obsidian/discover")
    assert response.status_code == 200

    payload = response.json()
    assert payload["success"] is True
    assert payload["detected_path"] == "/Users/leo/Documents/Obsidian Vault"
    assert len(payload["vaults"]) == 2
    assert payload["vaults"][0]["open"] is True


def test_providers_contract_supports_list_and_update(client: TestClient) -> None:
    list_response = client.get("/api/v1/providers")
    assert list_response.status_code == 200
    items = list_response.json()
    assert isinstance(items, list)
    assert [item["id"] for item in items] == ["llm_codex", "llm_openai"]
    codex_default = items[0]
    llm_default = items[0]
    assert codex_default["id"] == "llm_codex"
    assert codex_default["config"]["timeout_sec"] == 120
    assert codex_default["config"]["auth_mode"] == "api_key"
    llm_default = items[1]
    assert llm_default["config"]["timeout_sec"] == 120
    assert llm_default["config"]["auth_mode"] == "api_key"

    llm_update = client.patch(
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
    assert llm_update.status_code == 200
    llm_payload = llm_update.json()
    assert llm_payload["id"] == "llm_openai"
    assert llm_payload["enabled"] is True
    assert llm_payload["config"]["base_url"] == "https://api.openai.com/v1"
    assert llm_payload["config"]["model"] == "gpt-4o-mini"
    assert llm_payload["config"]["max_retry"] == 3
    assert llm_payload["config"]["auth_mode"] == "api_key"

    codex_update = client.patch(
        "/api/v1/providers/llm_codex",
        json={
            "enabled": True,
            "config": {
                "auth_mode": "local_codex",
                "model": "gpt-5.4",
                "timeout_sec": 90,
                "max_retry": 1,
                "api_key": "sk-should-be-cleared",
            },
        },
    )
    assert codex_update.status_code == 200
    codex_payload = codex_update.json()
    assert codex_payload["id"] == "llm_codex"
    assert codex_payload["enabled"] is True
    assert codex_payload["config"]["auth_mode"] == "local_codex"
    assert codex_payload["config"]["model"] == "gpt-5.4"
    assert codex_payload["config"]["api_key"] == ""

    missing = client.patch("/api/v1/providers/legacy_provider", json={"enabled": True})
    assert missing.status_code == 422


def test_providers_contract_supports_connectivity_test(client: TestClient, monkeypatch) -> None:
    async def _fake_llm(prompt: str, config: dict | None = None) -> dict:
        assert "Return JSON" in prompt
        assert config is not None
        assert config["base_url"] == "https://api.openai.com/v1"
        assert config["model"] == "gpt-4.1-mini"
        return {"ok": True, "message": "pong"}

    monkeypatch.setattr("app.api.v1.providers.run_llm_json", _fake_llm)

    response = client.post(
        "/api/v1/providers/llm_openai/test",
        json={
            "config": {
                "base_url": "https://api.openai.com/v1/",
                "model": "gpt-4.1-mini",
                "timeout_sec": 8,
            }
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "pong"
    assert payload["model"] == "gpt-4.1-mini"
    assert isinstance(payload["latency_ms"], int)


def test_providers_contract_supports_codex_connectivity_test(client: TestClient, monkeypatch) -> None:
    async def _fake_codex(prompt: str, config: dict | None = None) -> dict:
        assert "Return JSON" in prompt
        assert config is not None
        assert config["base_url"] == "https://api.openai.com/v1"
        assert config["model"] == "gpt-5-codex"
        assert config["auth_mode"] == "api_key"
        return {"ok": True, "message": "codex-pong"}

    monkeypatch.setattr("app.api.v1.providers.run_codex_json", _fake_codex)

    response = client.post(
        "/api/v1/providers/llm_codex/test",
        json={
            "config": {
                "base_url": "https://api.openai.com/v1/",
                "model": "gpt-5-codex",
                "timeout_sec": 8,
            }
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "codex-pong"
    assert payload["model"] == "gpt-5-codex"
    assert isinstance(payload["latency_ms"], int)


def test_providers_contract_supports_local_codex_connectivity_test(client: TestClient, monkeypatch) -> None:
    async def _fake_codex(prompt: str, config: dict | None = None) -> dict:
        assert "Return JSON" in prompt
        assert config is not None
        assert config["auth_mode"] == "local_codex"
        assert config["model"] == "gpt-5.4"
        assert config["api_key"] == ""
        return {"ok": True, "message": "local-codex-pong"}

    monkeypatch.setattr("app.api.v1.providers.run_codex_json", _fake_codex)

    response = client.post(
        "/api/v1/providers/llm_codex/test",
        json={
            "config": {
                "auth_mode": "local_codex",
                "model": "gpt-5.4",
                "timeout_sec": 8,
                "api_key": "sk-should-be-cleared",
            }
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "local-codex-pong"
    assert payload["model"] == "gpt-5.4"
    assert isinstance(payload["latency_ms"], int)


def test_providers_contract_retries_transient_codex_connectivity_errors(client: TestClient, monkeypatch) -> None:
    calls = {"count": 0}

    async def _fake_codex(prompt: str, config: dict | None = None) -> dict:
        assert "Return JSON" in prompt
        calls["count"] += 1
        if calls["count"] == 1:
            request = httpx.Request("POST", "https://api.openai.com/v1/responses")
            response = httpx.Response(502, request=request)
            raise httpx.HTTPStatusError("Bad gateway", request=request, response=response)
        assert config is not None
        assert config["max_retry"] == 1
        return {"ok": True, "message": "codex-pong"}

    monkeypatch.setattr("app.api.v1.providers.run_codex_json", _fake_codex)

    response = client.post(
        "/api/v1/providers/llm_codex/test",
        json={
            "config": {
                "base_url": "https://api.openai.com/v1/",
                "model": "gpt-5.4",
                "timeout_sec": 8,
                "max_retry": 1,
            }
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert calls["count"] == 2
    assert payload["success"] is True
    assert payload["message"] == "codex-pong"
    assert payload["model"] == "gpt-5.4"
