from __future__ import annotations

import importlib.util
from pathlib import Path


class _OpRecorder:
    def __init__(self) -> None:
        self.added_columns: dict[str, list[str]] = {}
        self.dropped_columns: dict[str, list[str]] = {}

    def add_column(self, table_name: str, column) -> None:  # noqa: ANN001
        self.added_columns.setdefault(table_name, []).append(column.name)

    def drop_column(self, table_name: str, column_name: str) -> None:
        self.dropped_columns.setdefault(table_name, []).append(column_name)


def test_destination_instance_refs_migration_declares_expected_columns(monkeypatch) -> None:
    module_path = (
        Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260320_0012_add_destination_instance_refs.py"
    )
    spec = importlib.util.spec_from_file_location("destination_instance_refs_migration", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    recorder = _OpRecorder()

    monkeypatch.setattr(module, "op", recorder)

    module.upgrade()
    assert recorder.added_columns == {
        "monitors": ["destination_instance_ids"],
        "reports": ["published_destination_instance_ids"],
    }

    module.downgrade()
    assert recorder.dropped_columns == {
        "reports": ["published_destination_instance_ids"],
        "monitors": ["destination_instance_ids"],
    }
