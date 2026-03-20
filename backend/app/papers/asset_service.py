"""Persistence helpers for paper assets."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import PaperAsset


async def upsert_paper_asset(
    session: AsyncSession,
    *,
    paper_id: uuid.UUID,
    asset_type: str,
    source_kind: str,
    source_url: str | None,
    resolved_url: str | None,
    checksum: str | None,
    fetch_status: str,
    mime_type: str | None = None,
) -> PaperAsset:
    existing = None
    if checksum:
        stmt = select(PaperAsset).where(PaperAsset.paper_id == paper_id, PaperAsset.checksum == checksum)
        existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is None and resolved_url:
        stmt = select(PaperAsset).where(PaperAsset.paper_id == paper_id, PaperAsset.resolved_url == resolved_url)
        existing = (await session.execute(stmt)).scalar_one_or_none()

    if existing is None:
        existing = PaperAsset(
            id=uuid.uuid4(),
            paper_id=paper_id,
            asset_type=asset_type,
            source_kind=source_kind,
            source_url=source_url,
            resolved_url=resolved_url,
            checksum=checksum,
            fetch_status=fetch_status,
            mime_type=mime_type,
        )
        session.add(existing)
    else:
        existing.asset_type = asset_type
        existing.source_kind = source_kind
        existing.source_url = source_url
        existing.resolved_url = resolved_url
        existing.checksum = checksum
        existing.fetch_status = fetch_status
        existing.mime_type = mime_type

    await session.flush()
    return existing
