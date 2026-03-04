"""One-time migration: source_overrides.limit -> source_overrides.max_items."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.models.database import async_session
from app.models.monitor import Monitor
from app.utils.monitor_overrides import migrate_source_overrides_limit_to_max_items


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate monitor source_overrides limit to max_items.")
    parser.add_argument("--apply", action="store_true", help="Persist changes. Default is dry-run.")
    parser.add_argument("--keep-limit", action="store_true", help="Keep legacy limit key in source_overrides.")
    parser.add_argument("--monitor-id", default="", help="Optional single monitor id.")
    parser.add_argument("--max-preview", type=int, default=20, help="Max changed monitor ids to print.")
    return parser.parse_args()


async def _run(*, apply: bool, keep_limit: bool, monitor_id: str, max_preview: int) -> dict:
    async with async_session() as db:
        stmt = select(Monitor).order_by(Monitor.created_at.asc())
        if monitor_id:
            stmt = stmt.where(Monitor.id == monitor_id)

        monitors = (await db.execute(stmt)).scalars().all()

        changed_monitor_ids: list[str] = []
        converted_total = 0
        removed_limit_total = 0
        changed_monitors = 0
        now = datetime.now(timezone.utc)

        for monitor in monitors:
            result = migrate_source_overrides_limit_to_max_items(
                monitor.source_overrides,
                drop_legacy_limit=not keep_limit,
            )
            if not result.changed:
                continue

            changed_monitors += 1
            converted_total += result.converted_limit_to_max_items
            removed_limit_total += result.removed_legacy_limit
            changed_monitor_ids.append(str(monitor.id))

            if apply:
                monitor.source_overrides = result.migrated
                monitor.updated_at = now
                db.add(monitor)

        if apply:
            await db.commit()

        summary = {
            "mode": "apply" if apply else "dry_run",
            "keep_limit": keep_limit,
            "monitor_count": len(monitors),
            "changed_monitors": changed_monitors,
            "converted_limit_to_max_items": converted_total,
            "removed_legacy_limit": removed_limit_total,
            "preview_changed_monitor_ids": changed_monitor_ids[: max(0, max_preview)],
        }
        return summary


def main() -> int:
    args = _parse_args()
    summary = asyncio.run(
        _run(
            apply=bool(args.apply),
            keep_limit=bool(args.keep_limit),
            monitor_id=str(args.monitor_id or "").strip(),
            max_preview=max(0, int(args.max_preview)),
        )
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
