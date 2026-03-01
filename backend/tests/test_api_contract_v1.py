"""API v1 contract tests for frontend integration."""

from fastapi.testclient import TestClient

def test_openapi_contains_new_dashboard_routes(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json()["paths"]
    assert "/api/v1/sources" in paths
    assert "/api/v1/monitors" in paths
    assert "/api/v1/monitors/{monitor_id}/run" in paths
    assert "/api/v1/reports" in paths
    assert "/api/v1/reports/filters" in paths
    assert "/api/v1/users/me" in paths
    assert "/api/v1/articles" in paths


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


def test_monitors_contract_supports_list_create_and_run(client: TestClient) -> None:
    list_response = client.get("/api/v1/monitors")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert isinstance(listed, list)
    assert len(listed) > 0
    assert "time_period" in listed[0]
    assert "depth" in listed[0]
    assert "source_ids" in listed[0]

    create_response = client.post(
        "/api/v1/monitors",
        json={
            "name": "Daily Open Source Brief",
            "time_period": "daily",
            "depth": "brief",
            "source_ids": [listed[0]["source_ids"][0]],
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Daily Open Source Brief"
    assert created["time_period"] == "daily"
    assert created["depth"] == "brief"

    run_response = client.post(f"/api/v1/monitors/{created['id']}/run")
    assert run_response.status_code == 200
    run_data = run_response.json()
    assert "task_id" in run_data
    assert run_data["status"] in {"pending", "running"}


def test_reports_contract_supports_filters_endpoint(client: TestClient) -> None:
    list_response = client.get("/api/v1/reports", params={"time_period": "daily", "depth": "brief", "limit": 10, "page": 1})
    assert list_response.status_code == 200
    reports = list_response.json()
    assert isinstance(reports, list)
    assert len(reports) > 0
    assert reports[0]["time_period"] == "daily"
    assert reports[0]["depth"] == "brief"

    filters_response = client.get("/api/v1/reports/filters")
    assert filters_response.status_code == 200
    filters_data = filters_response.json()
    assert "time_periods" in filters_data
    assert "depths" in filters_data
    assert "categories" in filters_data


def test_users_me_contract_supports_profile_and_settings_update(client: TestClient) -> None:
    profile_response = client.get("/api/v1/users/me")
    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert "id" in profile
    assert "email" in profile
    assert "plan" in profile

    update_response = client.patch(
        "/api/v1/users/me/settings",
        json={"default_time_period": "daily", "default_depth": "brief"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["default_time_period"] == "daily"
    assert updated["default_depth"] == "brief"
