"""Normalization helpers for academic papers."""

from __future__ import annotations

import re
from datetime import datetime

_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_title(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    normalized = _NON_ALNUM_PATTERN.sub(" ", text)
    return _WHITESPACE_PATTERN.sub(" ", normalized).strip()


def normalize_person_name(value: object) -> str:
    return normalize_title(value)


def normalize_identifier(scheme: str, value: object) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    normalized_scheme = str(scheme or "").strip().lower()
    if normalized_scheme == "doi":
        candidate = raw.lower()
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if candidate.startswith(prefix):
                candidate = candidate[len(prefix):]
        return candidate.strip() or None

    if normalized_scheme == "pmcid":
        candidate = raw.upper().replace(" ", "")
        if candidate.startswith("PMCID:"):
            candidate = candidate[len("PMCID:"):]
        if candidate.startswith("PMC"):
            return candidate
        return f"PMC{candidate}" if candidate else None

    if normalized_scheme == "pmid":
        candidate = raw.upper().replace("PMID:", "").strip()
        digits = "".join(char for char in candidate if char.isdigit())
        return digits or None

    if normalized_scheme == "arxiv":
        candidate = raw.lower().strip()
        for prefix in ("https://arxiv.org/abs/", "https://arxiv.org/pdf/", "http://arxiv.org/abs/", "arxiv:"):
            if candidate.startswith(prefix):
                candidate = candidate[len(prefix):]
        if candidate.endswith(".pdf"):
            candidate = candidate[:-4]
        return candidate.strip("/") or None

    if normalized_scheme == "openalex":
        return raw.rstrip("/").lower() or None

    return raw.strip() or None


def extract_identifier_candidates(metadata: dict | None) -> list[tuple[str, str]]:
    payload = metadata or {}
    candidates: list[tuple[str, str]] = []
    for scheme, keys in (
        ("doi", ("doi",)),
        ("pmcid", ("pmcid",)),
        ("pmid", ("pmid",)),
        ("arxiv", ("arxiv_id", "arxiv")),
        ("openalex", ("openalex_id",)),
    ):
        for key in keys:
            normalized = normalize_identifier(scheme, payload.get(key))
            if normalized:
                candidates.append((scheme, normalized))
                break
    return candidates


def infer_first_author(metadata: dict | None) -> str | None:
    payload = metadata or {}
    authors = payload.get("authors")
    if isinstance(authors, list):
        for author in authors:
            name = str(author or "").strip()
            if name:
                return name
    author = str(payload.get("author") or "").strip()
    return author or None


def infer_year(published_at: datetime | None, metadata: dict | None) -> int | None:
    payload = metadata or {}
    for key in ("publication_year", "year"):
        value = payload.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    if published_at is not None:
        return published_at.year
    return None


def infer_venue(metadata: dict | None) -> str | None:
    payload = metadata or {}
    for key in ("journal", "venue"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return None


def infer_best_pdf_url(metadata: dict | None) -> str | None:
    payload = metadata or {}
    for key in ("pdf_url", "best_pdf_url"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return None


def resolve_content_type(content: str | None, metadata: dict | None) -> str:
    text = str(content or "").strip()
    if not text:
        return "metadata"

    payload = metadata or {}
    content_tier = str(payload.get("content_tier") or "").strip().lower()
    if content_tier == "fulltext":
        return "fulltext"
    if content_tier == "partial_fulltext":
        return "snippet"

    if len(text) >= 8000:
        return "fulltext"
    if len(text) >= 1500:
        return "snippet"
    return "abstract"
