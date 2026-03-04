"""Sync all sources from source_presets.yaml into database."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.bootstrap import seed_initial_data
from app.models.database import async_session


async def run() -> int:
    async with async_session() as session:
        await seed_initial_data(session)
    print("[sync-sources] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
