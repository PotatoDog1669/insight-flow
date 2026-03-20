"""Converters from downloaded assets to markdown/plain text."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass

from bs4 import BeautifulSoup

from app.collectors.fulltext import DEFAULT_EXTRACTOR_CHAIN, extract_fulltext


@dataclass(frozen=True, slots=True)
class ConvertedContent:
    markdown_content: str
    plain_text: str
    content_tier: str
    converter_name: str
    quality_score: float


def convert_asset_to_markdown(
    *,
    asset_bytes: bytes,
    asset_type: str,
    mime_type: str | None,
    title: str | None,
    min_content_chars: int = 200,
    extractor_chain: Iterable[str] | None = None,
) -> ConvertedContent | None:
    if asset_type == "html":
        return _convert_html(
            asset_bytes.decode("utf-8", errors="ignore"),
            title=title,
            min_content_chars=min_content_chars,
            extractor_chain=extractor_chain,
        )
    if asset_type == "xml":
        return _convert_xml(asset_bytes.decode("utf-8", errors="ignore"), fallback_title=title)
    if asset_type == "pdf":
        return _convert_pdf(asset_bytes, title=title, min_content_chars=min_content_chars)
    return None


def _convert_html(
    html: str,
    *,
    title: str | None,
    min_content_chars: int,
    extractor_chain: Iterable[str] | None,
) -> ConvertedContent | None:
    extracted, extractor_name = extract_fulltext(
        html,
        extractor_chain=extractor_chain or DEFAULT_EXTRACTOR_CHAIN,
        min_content_chars=min_content_chars,
    )
    if len(extracted) < min_content_chars:
        return None
    heading = str(title or _html_title(html) or "Untitled").strip()
    markdown = f"# {heading}\n\n{_paragraphize(extracted)}".strip()
    return ConvertedContent(
        markdown_content=markdown,
        plain_text=extracted,
        content_tier="fulltext",
        converter_name=f"html:{extractor_name or 'unknown'}",
        quality_score=0.8,
    )


def _convert_xml(xml_text: str, *, fallback_title: str | None) -> ConvertedContent | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    title = _xml_text(root, ".//article-title") or str(fallback_title or "Untitled").strip()
    sections: list[str] = []
    plain_parts: list[str] = []

    for sec in root.findall(".//sec"):
        sec_title = _xml_text(sec, "./title")
        paragraphs = [" ".join(node.itertext()).strip() for node in sec.findall("./p")]
        paragraphs = [paragraph for paragraph in paragraphs if paragraph]
        if not sec_title and not paragraphs:
            continue
        if sec_title:
            sections.append(f"## {sec_title}")
            plain_parts.append(sec_title)
        for paragraph in paragraphs:
            sections.append(paragraph)
            plain_parts.append(paragraph)

    if not sections:
        body_text = " ".join(root.itertext()).strip()
        if len(body_text) < 50:
            return None
        markdown = f"# {title}\n\n{_paragraphize(body_text)}"
        return ConvertedContent(
            markdown_content=markdown,
            plain_text=body_text,
            content_tier="fulltext",
            converter_name="xml:fallback",
            quality_score=0.7,
        )

    markdown = "\n\n".join([f"# {title}", *sections]).strip()
    plain_text = "\n".join(plain_parts).strip()
    return ConvertedContent(
        markdown_content=markdown,
        plain_text=plain_text,
        content_tier="fulltext",
        converter_name="xml:jats",
        quality_score=0.95,
    )


def _convert_pdf(asset_bytes: bytes, *, title: str | None, min_content_chars: int) -> ConvertedContent | None:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return None

    try:
        import io

        reader = PdfReader(io.BytesIO(asset_bytes))
        text_chunks = [page.extract_text() or "" for page in reader.pages]
    except Exception:
        return None

    plain_text = "\n\n".join(chunk.strip() for chunk in text_chunks if chunk.strip()).strip()
    if len(plain_text) < min_content_chars:
        return None

    heading = str(title or "Untitled").strip()
    markdown = f"# {heading}\n\n{_paragraphize(plain_text)}"
    return ConvertedContent(
        markdown_content=markdown,
        plain_text=plain_text,
        content_tier="fulltext",
        converter_name="pdf:pypdf",
        quality_score=0.75,
    )


def _html_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.find("title")
    if title_node is None:
        return None
    value = title_node.get_text(" ", strip=True)
    return value or None


def _xml_text(root: ET.Element, path: str) -> str | None:
    node = root.find(path)
    if node is None:
        return None
    text = " ".join(node.itertext()).strip()
    return text or None


def _paragraphize(text: str) -> str:
    chunks = [chunk.strip() for chunk in text.replace("\r", "\n").split("\n") if chunk.strip()]
    if not chunks:
        return ""
    return "\n\n".join(chunks)
