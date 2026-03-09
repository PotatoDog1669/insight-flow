from app.routing.loader import load_routing_profile


def test_load_stable_profile_has_stage_and_fallbacks() -> None:
    profile = load_routing_profile("stable_v1")

    assert profile.name == "stable_v1"
    assert profile.stages.filter.primary == "llm_openai"
    assert profile.stages.global_summary is not None
    assert profile.stages.global_summary.primary
    assert "rule" in profile.stages.filter.fallback
    assert "database" in profile.stages.publish.targets


def test_load_codex_mvp_profile_prefers_agent_for_processing() -> None:
    profile = load_routing_profile("codex_mvp_v1")

    assert profile.name == "codex_mvp_v1"
    assert profile.stages.filter.primary == "agent_codex"
    assert profile.stages.keywords.primary == "agent_codex"
    assert profile.stages.global_summary is not None
    assert profile.stages.report.primary == "agent_codex"
    assert "notion_api" in profile.stages.publish.targets
