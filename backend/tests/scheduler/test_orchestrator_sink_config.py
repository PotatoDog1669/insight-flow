from __future__ import annotations

from app.config import settings
from app.scheduler.orchestrator import Orchestrator


def test_build_sink_config_keeps_obsidian_rest_settings() -> None:
    previous_vault_path = settings.obsidian_vault_path
    settings.obsidian_vault_path = "/Users/test/ObsidianVault"

    try:
        config = Orchestrator._build_sink_config(
            "obsidian",
            report_id="report-1",
            destination_settings={
                "obsidian": {
                    "enabled": True,
                    "config": {
                        "mode": "rest",
                        "api_url": "https://127.0.0.1:27124",
                        "api_key": "obsidian-secret",
                        "target_folder": "LexDeepResearch/Daily",
                    },
                }
            },
        )
    finally:
        settings.obsidian_vault_path = previous_vault_path

    assert config == {
        "vault_path": "/Users/test/ObsidianVault",
        "mode": "rest",
        "api_url": "https://127.0.0.1:27124",
        "api_key": "obsidian-secret",
        "target_folder": "LexDeepResearch/Daily",
    }


def test_build_sink_config_uses_destination_instance_payload() -> None:
    config = Orchestrator._build_sink_config(
        "11111111-1111-1111-1111-111111111111",
        report_id="report-1",
        destination_settings={
            "11111111-1111-1111-1111-111111111111": {
                "type": "notion",
                "name": "Research DB",
                "enabled": True,
                "config": {
                    "database_id": "db_live",
                    "token": "secret-token",
                    "summary_property": "TL;DR",
                },
            }
        },
    )

    assert config["database_id"] == "db_live"
    assert config["api_key"] == "secret-token"
    assert config["summary_property"] == "TL;DR"
