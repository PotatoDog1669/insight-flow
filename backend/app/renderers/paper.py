"""Paper report renderer."""

from __future__ import annotations

from app.processors.event_models import ProcessedEvent
from app.processors.pipeline import ProcessedArticle
from app.papers.reporting import build_paper_digest_report
from app.renderers.base import BaseRenderer, RenderContext, Report


class PaperRenderer(BaseRenderer):
    @property
    def level(self) -> str:
        return "L3"

    async def render(self, articles: list[ProcessedArticle] | list[ProcessedEvent], context: RenderContext) -> Report:
        invalid_items = [article for article in articles if not isinstance(article, ProcessedArticle)]
        if invalid_items:
            raise TypeError("PaperRenderer expects ProcessedArticle inputs only")
        return build_paper_digest_report(articles=list(articles), context=context)
