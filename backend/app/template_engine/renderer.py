"""Template rendering helpers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined
import yaml

from app.template_engine.resolver import TEMPLATE_ROOT, resolve_report_template, resolve_sink_report_template, resolve_sink_schema


def render_report_template(
    *,
    report_type: str,
    context: dict[str, Any],
    version: str = "v1",
) -> str:
    template_ref = resolve_report_template(report_type=report_type, version=version)
    template = _jinja_env().get_template(_template_name(template_ref.path))
    return str(template.render(**context)).strip()


def render_sink_report_template(
    *,
    sink: str,
    report_type: str,
    context: dict[str, Any],
    version: str = "v1",
) -> str | None:
    template_ref = resolve_sink_report_template(sink=sink, report_type=report_type, version=version)
    if template_ref is None:
        return None
    template = _jinja_env().get_template(_template_name(template_ref.path))
    return str(template.render(**context)).strip()


def load_sink_schema(*, sink: str, version: str = "v1") -> dict[str, Any]:
    schema_ref = resolve_sink_schema(sink=sink, version=version)
    if schema_ref is None:
        return {}
    parsed = yaml.safe_load(schema_ref.path.read_text(encoding="utf-8")) or {}
    return parsed if isinstance(parsed, dict) else {}


@lru_cache
def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_ROOT)),
        autoescape=False,
        trim_blocks=False,
        lstrip_blocks=False,
        undefined=StrictUndefined,
    )


def _template_name(path: Path) -> str:
    return str(path.resolve().relative_to(TEMPLATE_ROOT.resolve()))
