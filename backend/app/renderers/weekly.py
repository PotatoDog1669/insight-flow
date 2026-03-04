"""周报渲染器。"""

from app.processors.pipeline import ProcessedArticle
from app.renderers.base import BaseRenderer, RenderContext, Report


class WeeklyRenderer(BaseRenderer):
    @property
    def level(self) -> str:
        return "L3"

    async def render(self, articles: list[ProcessedArticle], context: RenderContext) -> Report:
        """渲染周报。"""
        # TODO: P1 实现
        return Report(level="L3", title=f"AI 周报 — {context.date}", content="", article_ids=[])
