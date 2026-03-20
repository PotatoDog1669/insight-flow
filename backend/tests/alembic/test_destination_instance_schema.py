from __future__ import annotations

import importlib.util
from pathlib import Path


class _OpRecorder:
    def __init__(self) -> None:
        self.created_tables: dict[str, tuple] = {}
        self.created_indexes: list[str] = []

    def create_table(self, name: str, *columns, **kwargs) -> None:  # noqa: ANN002, ANN003
        self.created_tables[name] = columns

    def create_index(self, name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
        self.created_indexes.append(name)


def test_destination_instance_migration_declares_expected_table_and_indexes(monkeypatch) -> None:
    module_path = (
        Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260320_0011_add_destination_instances.py"
    )
    spec = importlib.util.spec_from_file_location("destination_instance_migration", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    recorder = _OpRecorder()

    monkeypatch.setattr(module, "op", recorder)

    module.upgrade()

    assert "destination_instances" in recorder.created_tables
    assert "idx_destination_instances_user_type" in recorder.created_indexes
