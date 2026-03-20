from __future__ import annotations

import importlib.util
from pathlib import Path


class _OpRecorder:
    def __init__(self) -> None:
        self.created_tables: dict[str, tuple] = {}
        self.added_columns: dict[str, list[str]] = {}
        self.created_indexes: list[str] = []
        self.created_foreign_keys: list[str] = []

    def create_table(self, name: str, *columns, **kwargs) -> None:  # noqa: ANN002, ANN003
        self.created_tables[name] = columns

    def create_index(self, name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
        self.created_indexes.append(name)

    def add_column(self, table_name: str, column) -> None:  # noqa: ANN001
        self.added_columns.setdefault(table_name, []).append(column.name)

    def create_foreign_key(
        self,
        name: str,
        source_table: str,
        referent_table: str,
        local_cols: list[str],
        remote_cols: list[str],
    ) -> None:
        self.created_foreign_keys.append(name)


def test_academic_paper_migration_declares_expected_tables_and_columns(monkeypatch) -> None:
    module_path = (
        Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260319_0010_add_academic_paper_tables.py"
    )
    spec = importlib.util.spec_from_file_location("academic_paper_migration", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    recorder = _OpRecorder()

    monkeypatch.setattr(module, "op", recorder)

    module.upgrade()

    assert {"papers", "paper_identifiers", "paper_assets", "paper_contents"} <= set(recorder.created_tables)
    assert {"paper_id", "content_type"} <= set(recorder.added_columns.get("articles", []))
    assert "idx_papers_normalized_title" in recorder.created_indexes
    assert "idx_paper_assets_checksum" in recorder.created_indexes
    assert "fk_articles_paper_id_papers" in recorder.created_foreign_keys
