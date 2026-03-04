"""Run the minimal codex-agent daily chain for 4 curated sources -> Notion."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import uuid

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.models.database import async_session
from app.models.source import Source
from app.scheduler.orchestrator import DEFAULT_USER_ID, Orchestrator

MVP_SOURCE_KEYS = [
    "openai",
    "anthropic",
    "github_trending_daily",
    "huggingface_daily_papers",
]


def _source_uuid(key: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"lexdeepresearch:source:{key}")


async def run() -> int:
    source_ids = [_source_uuid(key) for key in MVP_SOURCE_KEYS]

    async with async_session() as session:
        rows = (
            await session.execute(
                select(Source.id, Source.name).where(Source.id.in_(source_ids), Source.enabled.is_(True))
            )
        ).all()
        found_ids = {row[0] for row in rows}
        missing = [key for key, source_id in zip(MVP_SOURCE_KEYS, source_ids) if source_id not in found_ids]
        if missing:
            print(f"[mvp] missing required sources in DB: {missing}")
            print("[mvp] start backend once to trigger bootstrap seeding, then retry.")
            return 1

    orchestrator = Orchestrator(max_concurrency=settings.collector_max_concurrency)
    result = await orchestrator.run_daily_pipeline(
        user_id=DEFAULT_USER_ID,
        trigger_type="manual",
        source_ids=source_ids,
        destination_ids=["notion"],
    )
    print("[mvp] pipeline_result:", result)
    print("[mvp] sources:", MVP_SOURCE_KEYS)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
