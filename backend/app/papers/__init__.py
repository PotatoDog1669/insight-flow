"""Academic paper services."""

from app.papers.acquisition import AcquisitionResult, acquire_paper_fulltext
from app.papers.asset_service import upsert_paper_asset
from app.papers.content_service import create_paper_content, refresh_best_content
from app.papers.evidence import build_evidence_coverage
from app.papers.fulltext_locator import FulltextCandidate, locate_fulltext_candidates
from app.papers.literature import build_literature_context
from app.papers.service import sync_article_paper_link

__all__ = [
    "AcquisitionResult",
    "acquire_paper_fulltext",
    "FulltextCandidate",
    "locate_fulltext_candidates",
    "upsert_paper_asset",
    "create_paper_content",
    "refresh_best_content",
    "build_evidence_coverage",
    "build_literature_context",
    "sync_article_paper_link",
]
