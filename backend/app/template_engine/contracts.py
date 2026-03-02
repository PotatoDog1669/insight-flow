"""Contracts for template resolution and rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

TemplateNamespace = Literal["reports", "sink_reports", "sink_schema"]


@dataclass(frozen=True, slots=True)
class TemplateRef:
    """Resolved template reference."""

    namespace: TemplateNamespace
    key: str
    path: Path
