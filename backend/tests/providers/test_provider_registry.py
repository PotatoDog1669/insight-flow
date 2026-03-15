from app.providers.registry import get_provider, list_providers


def test_registry_returns_provider_by_stage_and_name() -> None:
    provider = get_provider(stage="keywords", name="rule")
    assert provider.stage == "keywords"
    assert provider.name == "rule"


def test_filter_stage_supports_rule_and_llm_executors() -> None:
    providers = list_providers(stage="filter")
    assert providers == ["llm_openai", "rule"]


def test_keywords_and_report_stage_use_unified_modules() -> None:
    keyword_rule = get_provider(stage="keywords", name="rule")
    keyword_llm = get_provider(stage="keywords", name="llm_openai")
    report_llm = get_provider(stage="report", name="llm_openai")
    summary_llm = get_provider(stage="global_summary", name="llm_openai")

    assert keyword_rule.__class__.__module__ == "app.providers.keywords"
    assert keyword_llm.__class__.__module__ == "app.providers.keywords"
    assert report_llm.__class__.__module__ == "app.providers.report"
    assert summary_llm.__class__.__module__ == "app.providers.global_summary"
