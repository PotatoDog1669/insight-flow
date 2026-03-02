"""Template path resolver."""

from __future__ import annotations

from pathlib import Path

from app.config import PROJECT_ROOT
from app.template_engine.contracts import TemplateRef

TEMPLATE_ROOT = PROJECT_ROOT / "backend" / "app" / "templates"


def resolve_report_template(
    *,
    report_type: str,
    version: str = "v1",
) -> TemplateRef:
    safe_report_type = _safe_segment(report_type, field="report_type")
    safe_version = _safe_segment(version, field="version")
    path = _safe_join(
        TEMPLATE_ROOT,
        "reports",
        safe_report_type,
        f"{safe_version}.md.j2",
    )
    _assert_exists(path)
    return TemplateRef(
        namespace="reports",
        key=f"{safe_report_type}/{safe_version}",
        path=path,
    )


def resolve_sink_report_template(
    *,
    sink: str,
    report_type: str,
    version: str = "v1",
) -> TemplateRef | None:
    safe_sink = _safe_segment(sink, field="sink")
    safe_report_type = _safe_segment(report_type, field="report_type")
    safe_version = _safe_segment(version, field="version")
    path = _safe_join(
        TEMPLATE_ROOT,
        "sinks",
        safe_sink,
        "reports",
        safe_report_type,
        f"{safe_version}.md.j2",
    )
    if not path.exists():
        return None
    return TemplateRef(
        namespace="sink_reports",
        key=f"{safe_sink}/{safe_report_type}/{safe_version}",
        path=path,
    )


def resolve_sink_schema(
    *,
    sink: str,
    version: str = "v1",
) -> TemplateRef | None:
    safe_sink = _safe_segment(sink, field="sink")
    safe_version = _safe_segment(version, field="version")
    path = _safe_join(
        TEMPLATE_ROOT,
        "sinks",
        safe_sink,
        "schema",
        f"{safe_version}.yaml",
    )
    if not path.exists():
        return None
    return TemplateRef(
        namespace="sink_schema",
        key=f"{safe_sink}/{safe_version}",
        path=path,
    )


def _safe_segment(value: str, *, field: str) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        raise ValueError(f"Empty template segment: {field}")
    if "/" in candidate or "\\" in candidate or ".." in candidate:
        raise ValueError(f"Invalid template segment: {field}")
    return candidate


def _safe_join(root: Path, *parts: str) -> Path:
    path = (root / Path(*parts)).resolve()
    root_resolved = root.resolve()
    if not path.is_relative_to(root_resolved):
        raise ValueError("Template path escapes template root")
    return path


def _assert_exists(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
