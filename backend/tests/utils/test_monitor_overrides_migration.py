from __future__ import annotations

from app.utils.monitor_overrides import migrate_source_overrides_limit_to_max_items


def test_migrate_converts_limit_to_max_items_and_drops_legacy_limit() -> None:
    source_overrides = {
        "source-1": {"limit": 12, "keywords": ["a"]},
        "source-2": {"max_items": 7, "limit": 99},
    }

    result = migrate_source_overrides_limit_to_max_items(source_overrides)

    assert result.changed is True
    assert result.converted_limit_to_max_items == 1
    assert result.removed_legacy_limit == 2
    assert result.migrated["source-1"]["max_items"] == 12
    assert "limit" not in result.migrated["source-1"]
    assert result.migrated["source-2"]["max_items"] == 7
    assert "limit" not in result.migrated["source-2"]
    assert result.migrated["source-1"]["keywords"] == ["a"]


def test_migrate_keeps_legacy_limit_when_requested() -> None:
    source_overrides = {"source-1": {"limit": "15"}}

    result = migrate_source_overrides_limit_to_max_items(source_overrides, drop_legacy_limit=False)

    assert result.changed is True
    assert result.converted_limit_to_max_items == 1
    assert result.removed_legacy_limit == 0
    assert result.migrated["source-1"]["max_items"] == 15
    assert result.migrated["source-1"]["limit"] == "15"


def test_migrate_noop_when_already_using_max_items() -> None:
    source_overrides = {"source-1": {"max_items": 20, "keywords": ["x"]}}

    result = migrate_source_overrides_limit_to_max_items(source_overrides)

    assert result.changed is False
    assert result.converted_limit_to_max_items == 0
    assert result.removed_legacy_limit == 0
    assert result.migrated == source_overrides
