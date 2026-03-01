"""L1 速览渲染器"""

from app.processors.pipeline import ProcessedArticle
from app.renderers.base import BaseRenderer, RenderContext, Report


class L1BriefRenderer(BaseRenderer):
    @property
    def level(self) -> str:
        return "L1"

    async def render(self, articles: list[ProcessedArticle], context: RenderContext) -> Report:
        """从 L2 日报自动精简生成 L1 速览"""
        top_items = articles[:8]
        lines = [f"# AI Briefing ({context.date})", ""]
        for item in top_items:
            summary = item.summary or item.raw.title
            lines.append(f"- {summary}")
        return Report(
            level="L1",
            title=f"AI Briefing — {context.date}",
            content="\n".join(lines).strip(),
            article_ids=[item.raw.external_id for item in top_items],
        )
