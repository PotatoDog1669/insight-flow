"""Utilities for monitor source_overrides migration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SourceOverridesMigrationResult:
    migrated: dict
    changed: bool
    converted_limit_to_max_items: int
    removed_legacy_limit: int


def migrate_source_overrides_limit_to_max_items(
    source_overrides: dict | None,
    *,
    drop_legacy_limit: bool = True,
) -> SourceOverridesMigrationResult:
    if not isinstance(source_overrides, dict):
        return SourceOverridesMigrationResult(
            migrated={},
            changed=bool(source_overrides),
            converted_limit_to_max_items=0,
            removed_legacy_limit=0,
        )

    migrated = {}
    changed = False
    converted = 0
    removed_limit = 0

    for source_id, raw_config in source_overrides.items():
        if not isinstance(raw_config, dict):
            migrated[source_id] = raw_config
            continue

        config = dict(raw_config)
        parsed_max_items = _parse_positive_int(config.get("max_items"))
        parsed_limit = _parse_positive_int(config.get("limit"))

        if parsed_max_items is None and parsed_limit is not None:
            config["max_items"] = parsed_limit
            converted += 1
            changed = True

        if drop_legacy_limit and "limit" in config:
            del config["limit"]
            removed_limit += 1
            changed = True

        migrated[source_id] = config

    return SourceOverridesMigrationResult(
        migrated=migrated,
        changed=changed,
        converted_limit_to_max_items=converted,
        removed_legacy_limit=removed_limit,
    )


def _parse_positive_int(value: object) -> int | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            value = int(stripped)
    if isinstance(value, int) and 1 <= value <= 200:
        return value
    return None
