from __future__ import annotations

from app.scheduler.orchestrator import Orchestrator


def test_runtime_routing_profile_applies_monitor_stage_overrides() -> None:
    orchestrator = Orchestrator(max_concurrency=1)
    base_filter = orchestrator.routing_profile.stages.filter.primary
    base_keywords = orchestrator.routing_profile.stages.keywords.primary
    base_global_summary = (
        orchestrator.routing_profile.stages.global_summary.primary
        if orchestrator.routing_profile.stages.global_summary is not None
        else orchestrator.routing_profile.stages.report.primary
    )
    overridden_filter = "rule" if base_filter != "rule" else "agent_codex"
    overridden_global_summary = "llm_openai" if base_global_summary != "llm_openai" else "agent_codex"

    runtime_profile = orchestrator._build_runtime_routing_profile(
        monitor_ai_routing={
            "stages": {
                "report": {"primary": "llm_openai"},
                "filter": {"primary": overridden_filter},
                "global_summary": {"primary": overridden_global_summary},
            }
        }
    )

    assert runtime_profile.stages.filter.primary == overridden_filter
    assert runtime_profile.stages.report.primary == "llm_openai"
    assert runtime_profile.stages.global_summary is not None
    assert runtime_profile.stages.global_summary.primary == overridden_global_summary
    assert runtime_profile.stages.keywords.primary == base_keywords
    assert base_filter != runtime_profile.stages.filter.primary


def test_provider_config_precedence_is_monitor_then_user_then_global() -> None:
    orchestrator = Orchestrator(max_concurrency=1)
    orchestrator.runtime_routing_profile = orchestrator._build_runtime_routing_profile(monitor_ai_routing={})
    orchestrator.provider_overrides = {
        "agent_codex": {
            "model": "user-model",
            "timeout_sec": 55,
        }
    }
    orchestrator.monitor_provider_overrides = {
        "agent_codex": {
            "model": "monitor-model",
        }
    }

    config = orchestrator._provider_config("agent_codex")

    assert config["model"] == "monitor-model"
    assert config["timeout_sec"] == 55
