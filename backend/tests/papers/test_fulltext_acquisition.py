from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import Paper, PaperContent, PaperIdentifier
from app.papers.acquisition import acquire_paper_fulltext
from app.papers.normalization import normalize_identifier, normalize_title


class _Response:
    def __init__(self, *, content: bytes, content_type: str, status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self.text = content.decode("utf-8", errors="ignore")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class _Client:
    def __init__(self, mapping: dict[str, _Response]) -> None:
        self.mapping = mapping

    async def get(self, url: str) -> _Response:
        response = self.mapping.get(url)
        if response is None:
            raise RuntimeError(f"unexpected url: {url}")
        return response


@pytest.mark.asyncio
async def test_acquire_paper_fulltext_downloads_html_and_creates_markdown_content(
    db_session_factory,
    tmp_path: Path,
) -> None:
    session_factory, _ = db_session_factory
    paper_id = uuid.uuid4()
    now = datetime.now(UTC)

    async with session_factory() as session:
        session.add(
            Paper(
                id=paper_id,
                title="Reasoning Agents",
                normalized_title=normalize_title("Reasoning Agents"),
                best_landing_url="https://example.com/paper",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    html = (
        b"<html><body><article><h1>Reasoning Agents</h1>"
        b"<p>Long full text body about agents.</p></article></body></html>"
    )
    client = _Client({"https://example.com/paper": _Response(content=html, content_type="text/html; charset=utf-8")})

    async with session_factory() as session:
        result = await acquire_paper_fulltext(
            session,
            paper_id,
            storage_root=tmp_path / "paper-assets",
            client=client,
            min_content_chars=10,
        )
        await session.commit()

    assert result is not None
    assert result.content is not None
    assert result.content.content_tier == "fulltext"
    assert result.content.markdown_content is not None
    assert "Long full text body about agents." in result.content.markdown_content
    assert result.asset is not None
    assert result.asset.storage_path is not None
    assert (tmp_path / "paper-assets" / Path(result.asset.storage_path)).exists()


@pytest.mark.asyncio
async def test_acquire_paper_fulltext_converts_pmc_xml_to_markdown(db_session_factory, tmp_path: Path) -> None:
    session_factory, _ = db_session_factory
    paper_id = uuid.uuid4()
    now = datetime.now(UTC)

    async with session_factory() as session:
        session.add(
            Paper(
                id=paper_id,
                title="PMC Paper",
                normalized_title=normalize_title("PMC Paper"),
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            PaperIdentifier(
                paper_id=paper_id,
                scheme="pmcid",
                value="PMC123456",
                normalized_value=normalize_identifier("pmcid", "PMC123456") or "",
                source="europe_pmc",
                created_at=now,
            )
        )
        await session.commit()

    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
    <article>
      <front><article-meta><title-group><article-title>PMC Paper</article-title></title-group></article-meta></front>
      <body>
        <sec><title>Introduction</title><p>XML body for the paper.</p></sec>
        <sec><title>Results</title><p>Important results text.</p></sec>
      </body>
    </article>"""
    client = _Client(
        {
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC123456/?page=1": _Response(
                content=xml,
                content_type="application/xml",
            )
        }
    )

    async with session_factory() as session:
        result = await acquire_paper_fulltext(
            session,
            paper_id,
            storage_root=tmp_path / "paper-assets",
            client=client,
            min_content_chars=10,
        )
        await session.commit()

    assert result is not None
    assert result.content is not None
    assert "# PMC Paper" in (result.content.markdown_content or "")
    assert "## Introduction" in (result.content.markdown_content or "")
    assert "Important results text." in (result.content.markdown_content or "")


@pytest.mark.asyncio
async def test_acquire_paper_fulltext_records_failed_pdf_conversion_without_parser(
    db_session_factory,
    tmp_path: Path,
) -> None:
    session_factory, _ = db_session_factory
    paper_id = uuid.uuid4()
    now = datetime.now(UTC)

    async with session_factory() as session:
        session.add(
            Paper(
                id=paper_id,
                title="PDF Paper",
                normalized_title=normalize_title("PDF Paper"),
                best_pdf_url="https://example.com/paper.pdf",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    client = _Client(
        {"https://example.com/paper.pdf": _Response(content=b"%PDF-1.7 fake", content_type="application/pdf")}
    )

    async with session_factory() as session:
        result = await acquire_paper_fulltext(
            session,
            paper_id,
            storage_root=tmp_path / "paper-assets",
            client=client,
            min_content_chars=10,
        )
        await session.commit()

    async with session_factory() as session:
        paper = await session.get(Paper, paper_id)
        contents = (
            await session.execute(select(PaperContent).where(PaperContent.paper_id == paper_id))
        ).scalars().all()

    assert result is not None
    assert result.content is None
    assert paper is not None
    assert paper.fulltext_status == "failed"
    assert contents == []
