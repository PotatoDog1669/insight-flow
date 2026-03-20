"""Locate candidate fulltext URLs from canonical paper metadata."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.paper import Paper, PaperIdentifier


@dataclass(frozen=True, slots=True)
class FulltextCandidate:
    url: str
    source_kind: str
    asset_type: str
    priority: int


def locate_fulltext_candidates(paper: Paper, identifiers: list[PaperIdentifier]) -> list[FulltextCandidate]:
    candidates: list[FulltextCandidate] = []
    seen: set[str] = set()

    for identifier in identifiers:
        if identifier.scheme == "pmcid":
            _add_candidate(
                candidates,
                seen,
                url=f"https://pmc.ncbi.nlm.nih.gov/articles/{identifier.normalized_value}/?page=1",
                source_kind="pmc",
                asset_type="html",
                priority=0,
            )
        elif identifier.scheme == "arxiv":
            _add_candidate(
                candidates,
                seen,
                url=f"https://arxiv.org/pdf/{identifier.normalized_value}.pdf",
                source_kind="arxiv",
                asset_type="pdf",
                priority=1,
            )
        elif identifier.scheme == "doi":
            _add_candidate(
                candidates,
                seen,
                url=f"https://doi.org/{identifier.normalized_value}",
                source_kind="doi_landing",
                asset_type="html",
                priority=3,
            )

    if paper.best_pdf_url:
        _add_candidate(candidates, seen, url=paper.best_pdf_url, source_kind="publisher", asset_type="pdf", priority=2)
    if paper.best_landing_url:
        _add_candidate(
            candidates,
            seen,
            url=paper.best_landing_url,
            source_kind="doi_landing",
            asset_type="html",
            priority=4,
        )

    return sorted(candidates, key=lambda item: item.priority)


def _add_candidate(
    candidates: list[FulltextCandidate],
    seen: set[str],
    *,
    url: str | None,
    source_kind: str,
    asset_type: str,
    priority: int,
) -> None:
    normalized_url = str(url or "").strip()
    if not normalized_url or normalized_url in seen:
        return
    seen.add(normalized_url)
    candidates.append(
        FulltextCandidate(
            url=normalized_url,
            source_kind=source_kind,
            asset_type=asset_type,
            priority=priority,
        )
    )
