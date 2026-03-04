"""深度报告渲染器。"""

from app.processors.pipeline import ProcessedArticle
from app.renderers.base import BaseRenderer, RenderContext, Report


class DeepReportRenderer(BaseRenderer):
    @property
    def level(self) -> str:
        return "L4"

    async def render(self, articles: list[ProcessedArticle], context: RenderContext) -> Report:
        """渲染深度报告。"""
        # TODO: P1 实现
        return Report(level="L4", title="深度报告", content="", article_ids=[])
