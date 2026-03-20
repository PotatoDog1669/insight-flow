"""Acquire and convert academic paper fulltext."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PROJECT_ROOT
from app.models.paper import Paper, PaperContent, PaperIdentifier
from app.papers.asset_service import upsert_paper_asset
from app.papers.content_service import create_paper_content, refresh_best_content
from app.papers.converter import ConvertedContent, convert_asset_to_markdown
from app.papers.fulltext_locator import FulltextCandidate, locate_fulltext_candidates

logger = structlog.get_logger()

DEFAULT_PAPER_ASSET_DIR = PROJECT_ROOT / "output" / "paper_assets"


@dataclass(slots=True)
class AcquisitionResult:
    paper: Paper
    candidate: FulltextCandidate | None
    asset: object | None
    content: PaperContent | None


async def acquire_paper_fulltext(
    session: AsyncSession,
    paper_id: uuid.UUID,
    *,
    storage_root: Path | None = None,
    client: object | None = None,
    min_content_chars: int = 200,
) -> AcquisitionResult | None:
    paper = await session.get(Paper, paper_id)
    if paper is None:
        return None

    stmt = select(PaperIdentifier).where(PaperIdentifier.paper_id == paper_id)
    identifiers = (await session.execute(stmt)).scalars().all()
    candidates = locate_fulltext_candidates(paper, identifiers)
    if not candidates:
        paper.fulltext_status = "failed"
        await session.flush()
        return AcquisitionResult(paper=paper, candidate=None, asset=None, content=None)

    root = storage_root or DEFAULT_PAPER_ASSET_DIR
    root.mkdir(parents=True, exist_ok=True)

    own_client = False
    http_client = client
    if http_client is None:
        own_client = True
        http_client = httpx.AsyncClient(timeout=30, follow_redirects=True)

    last_asset = None
    try:
        for candidate in candidates:
            try:
                response = await http_client.get(candidate.url)
                response.raise_for_status()
            except Exception as exc:
                logger.warning("paper_fulltext_fetch_failed", paper_id=str(paper_id), url=candidate.url, error=str(exc))
                continue

            mime_type = str(getattr(response, "headers", {}).get("content-type") or "").split(";")[0].strip() or None
            asset_type = _resolve_asset_type(candidate, mime_type, candidate.url)
            checksum = f"sha256:{sha256(response.content).hexdigest()}"
            stored_path = await _store_asset_bytes(
                root=root,
                paper_id=paper_id,
                checksum=checksum,
                asset_type=asset_type,
                content=response.content,
            )
            last_asset = await upsert_paper_asset(
                session,
                paper_id=paper_id,
                asset_type=asset_type,
                source_kind=candidate.source_kind,
                source_url=candidate.url,
                resolved_url=candidate.url,
                checksum=checksum,
                fetch_status="success",
                mime_type=mime_type,
            )
            last_asset.storage_path = str(stored_path.relative_to(root))
            await session.flush()

            converted = convert_asset_to_markdown(
                asset_bytes=response.content,
                asset_type=asset_type,
                mime_type=mime_type,
                title=paper.title,
                min_content_chars=min_content_chars,
            )
            if converted is None:
                continue

            content = await _persist_converted_content(
                session,
                paper_id=paper_id,
                asset_id=last_asset.id,
                converted=converted,
            )
            await refresh_best_content(session, paper_id)
            return AcquisitionResult(paper=paper, candidate=candidate, asset=last_asset, content=content)

        paper.fulltext_status = "failed"
        await session.flush()
        return AcquisitionResult(paper=paper, candidate=candidates[0], asset=last_asset, content=None)
    finally:
        if own_client and isinstance(http_client, httpx.AsyncClient):
            await http_client.aclose()


async def _persist_converted_content(
    session: AsyncSession,
    *,
    paper_id: uuid.UUID,
    asset_id: uuid.UUID | None,
    converted: ConvertedContent,
) -> PaperContent:
    return await create_paper_content(
        session,
        paper_id=paper_id,
        asset_id=asset_id,
        content_tier=converted.content_tier,
        markdown_content=converted.markdown_content,
        plain_text=converted.plain_text,
        converter_name=converted.converter_name,
        quality_score=converted.quality_score,
        extraction_status="success",
    )


async def _store_asset_bytes(
    *,
    root: Path,
    paper_id: uuid.UUID,
    checksum: str,
    asset_type: str,
    content: bytes,
) -> Path:
    paper_dir = root / str(paper_id)
    paper_dir.mkdir(parents=True, exist_ok=True)
    extension = {"html": "html", "xml": "xml", "pdf": "pdf"}.get(asset_type, "bin")
    filename = f"{checksum.replace(':', '_')}.{extension}"
    path = paper_dir / filename
    path.write_bytes(content)
    return path


def _resolve_asset_type(candidate: FulltextCandidate, mime_type: str | None, url: str) -> str:
    if mime_type == "application/pdf":
        return "pdf"
    if mime_type in {"application/xml", "text/xml"}:
        return "xml"
    if mime_type == "text/html":
        return "html"
    lowered = url.lower()
    if lowered.endswith(".pdf"):
        return "pdf"
    if lowered.endswith(".xml"):
        return "xml"
    return candidate.asset_type
