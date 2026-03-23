from app.providers.registry import get_provider, list_providers


def test_registry_returns_provider_by_stage_and_name() -> None:
    provider = get_provider(stage="keywords", name="rule")
    assert provider.stage == "keywords"
    assert provider.name == "rule"


def test_filter_stage_supports_rule_and_llm_executors() -> None:
    providers = list_providers(stage="filter")
    assert providers == ["llm_codex", "llm_openai", "rule"]


def test_keywords_and_report_stage_use_unified_modules() -> None:
    keyword_rule = get_provider(stage="keywords", name="rule")
    keyword_codex = get_provider(stage="keywords", name="llm_codex")
    keyword_llm = get_provider(stage="keywords", name="llm_openai")
    report_codex = get_provider(stage="report", name="llm_codex")
    report_llm = get_provider(stage="report", name="llm_openai")
    summary_codex = get_provider(stage="global_summary", name="llm_codex")
    summary_llm = get_provider(stage="global_summary", name="llm_openai")
    paper_review_codex = get_provider(stage="paper_review", name="llm_codex")
    paper_review_llm = get_provider(stage="paper_review", name="llm_openai")
    paper_note_codex = get_provider(stage="paper_note", name="llm_codex")
    paper_note_llm = get_provider(stage="paper_note", name="llm_openai")

    assert keyword_rule.__class__.__module__ == "app.providers.keywords"
    assert keyword_codex.__class__.__module__ == "app.providers.keywords"
    assert keyword_llm.__class__.__module__ == "app.providers.keywords"
    assert report_codex.__class__.__module__ == "app.providers.report"
    assert report_llm.__class__.__module__ == "app.providers.report"
    assert summary_codex.__class__.__module__ == "app.providers.global_summary"
    assert summary_llm.__class__.__module__ == "app.providers.global_summary"
    assert paper_review_codex.__class__.__module__ == "app.providers.paper_review"
    assert paper_review_llm.__class__.__module__ == "app.providers.paper_review"
    assert paper_note_codex.__class__.__module__ == "app.providers.paper_note"
    assert paper_note_llm.__class__.__module__ == "app.providers.paper_note"


def test_paper_stage_supports_llm_executors() -> None:
    assert list_providers(stage="paper_review") == ["llm_codex", "llm_openai"]
    assert list_providers(stage="paper_note") == ["llm_codex", "llm_openai"]
