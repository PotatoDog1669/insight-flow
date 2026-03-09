from __future__ import annotations

import pytest

from app.template_engine.renderer import load_sink_schema, render_report_template, render_sink_report_template
from app.template_engine.resolver import resolve_report_template


def test_resolve_report_template_path() -> None:
    ref = resolve_report_template(report_type="daily", version="v1")
    assert ref.key == "daily/v1"
    assert ref.path.name == "v1.md.j2"
    assert "templates/reports/daily" in str(ref.path)


def test_legacy_depth_contract_is_rejected() -> None:
    with pytest.raises(TypeError):
        resolve_report_template(time_period="daily", depth="brief", version="v1")  # type: ignore[call-arg]


def test_render_report_template_daily() -> None:
    content = render_report_template(
        report_type="daily",
        version="v1",
        context={"date": "2026-03-02", "overview": [], "events": []},
    )
    assert "## 概览" in content


def test_render_sink_report_template_notion_override() -> None:
    rendered = render_sink_report_template(
        sink="notion",
        report_type="daily",
        version="v1",
        context={"content": "hello notion"},
    )
    assert rendered == "hello notion"


def test_load_sink_schema_defaults() -> None:
    schema = load_sink_schema(sink="notion", version="v1")
    assert schema["title_property"] == "Name"
    assert schema["summary_property"] == "TL;DR"
