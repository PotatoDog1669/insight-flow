from app.routing.loader import load_routing_profile


def test_load_stable_profile_has_stage_and_fallbacks() -> None:
    profile = load_routing_profile("stable_v1")

    assert profile.name == "stable_v1"
    assert profile.stages.filter.primary == "llm_openai"
    assert profile.stages.global_summary is not None
    assert profile.stages.global_summary.primary
    assert "rule" in profile.stages.filter.fallback
    assert "database" in profile.stages.publish.targets


def test_load_missing_profile_falls_back_to_stable_shape() -> None:
    profile = load_routing_profile("removed_profile")

    assert profile.name == "removed_profile"
    assert profile.stages.filter.primary in {"rule", "llm_openai"}
    assert profile.stages.keywords.primary == "llm_openai"
    assert profile.stages.global_summary is not None
    assert profile.stages.report.primary == "llm_openai"
    assert profile.stages.publish.targets == ["database"]
