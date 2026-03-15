"""API v1 contract tests for frontend integration."""

from datetime import datetime, timezone
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import CollectTask

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
    assert "/api/v1/reports/filters" in paths
    assert "/api/v1/users/me" in paths
    assert "/api/v1/articles" in paths
    assert "/api/v1/destinations" in paths
    assert "/api/v1/destinations/{destination_id}" in paths
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
    assert item["status"] in {"healthy", "error", "running"}


def test_monitors_ai_routing_defaults_contract(client: TestClient) -> None:
    response = client.get("/api/v1/monitors/ai-routing/defaults")
    assert response.status_code == 200
    data = response.json()
    assert data["profile_name"]
    assert data["stages"]["filter"] in {"rule", "llm_openai", "llm_codex"}
    assert data["stages"]["keywords"] in {"rule", "llm_openai", "llm_codex"}
    assert data["stages"]["report"] in {"llm_openai", "llm_codex"}


def test_monitors_contract_supports_list_create_and_run(client: TestClient, monkeypatch) -> None:
    list_response = client.get("/api/v1/monitors")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert isinstance(listed, list)
    assert len(listed) > 0
    assert "time_period" in listed[0]
    assert "report_type" in listed[0]
    assert "source_ids" in listed[0]
    assert "ai_routing" in listed[0]

    create_response = client.post(
        "/api/v1/monitors",
        json={
            "name": "Daily Open Source Brief",
            "time_period": "daily",
            "report_type": "research",
            "source_ids": [listed[0]["source_ids"][0]],
            "destination_ids": ["notion"],
            "source_overrides": {
                listed[0]["source_ids"][0]: {
                    "max_items": 9,
                    "limit": 12,
                    "max_results": 40,
                    "keywords": ["reasoning", "agent"],
                }
            },
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
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Daily Open Source Brief"
    assert created["time_period"] == "daily"
    assert created["report_type"] == "daily"
    assert created["destination_ids"] == ["notion"]
    assert created["window_hours"] == 24
    assert created["source_overrides"][created["source_ids"][0]]["max_items"] == 9
    assert created["source_overrides"][created["source_ids"][0]]["limit"] == 12
    assert created["source_overrides"][created["source_ids"][0]]["max_results"] == 40
    assert created["source_overrides"][created["source_ids"][0]]["keywords"] == ["reasoning", "agent"]
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
        from app.scheduler.monitor_runner import execute_monitor_pipeline
        from app.models.database import get_db
        from app.main import app
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
    assert captured["destination_ids"] == ["database", "notion"]
    assert captured["source_ids"] == [uuid.UUID(created["source_ids"][0])]
    assert captured["report_type"] == "daily"
    assert captured["window_hours"] == 24
    assert captured["source_overrides"][created["source_ids"][0]]["max_items"] == 9
    assert captured["source_overrides"][created["source_ids"][0]]["limit"] == 12
    assert captured["source_overrides"][created["source_ids"][0]]["max_results"] == 40
    assert captured["source_overrides"][created["source_ids"][0]]["keywords"] == ["reasoning", "agent"]
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


def test_monitors_contract_supports_run_cancel(client: TestClient, monkeypatch) -> None:
    listed = client.get("/api/v1/monitors").json()
    source_id = listed[0]["source_ids"][0]
    create_response = client.post(
        "/api/v1/monitors",
        json={
            "name": "Cancelable monitor",
            "time_period": "daily",
            "source_ids": [source_id],
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()

    async def _fake_prepare_monitor_run(
        *,
        db: AsyncSession,
        monitor,
        trigger_type: str,
    ) -> CollectTask:
        now = datetime.now(timezone.utc)
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
        json={
            "name": "Invalid AI routing",
            "time_period": "daily",
            "source_ids": [source_id],
            "ai_routing": {
                "stages": {
                    "report": {"primary": "rule"},
                }
            },
        },
    )
    assert response.status_code == 422


def test_reports_contract_supports_filters_endpoint(client: TestClient) -> None:
    list_response = client.get("/api/v1/reports", params={"time_period": "daily", "report_type": "daily", "limit": 10, "page": 1})
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
    assert any(item["id"] == "notion" for item in items)
    assert any(item["id"] == "obsidian" for item in items)
    assert any(item["id"] == "rss" for item in items)

    update_response = client.patch(
        "/api/v1/destinations/notion",
        json={"enabled": True, "config": {"database_id": "db_live"}},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["id"] == "notion"
    assert updated["enabled"] is True
    assert updated["config"]["database_id"] == "db_live"


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
    llm_default = items[1]
    assert llm_default["config"]["timeout_sec"] == 120

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
