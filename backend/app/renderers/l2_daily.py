"""L2 日报渲染器（默认输出）"""

from app.processors.pipeline import ProcessedArticle
from app.renderers.base import BaseRenderer, RenderContext, Report


class L2DailyRenderer(BaseRenderer):
    @property
    def level(self) -> str:
        return "L2"

    async def render(self, articles: list[ProcessedArticle], context: RenderContext) -> Report:
        """渲染 L2 日报"""
        lines = [
            f"# AI Daily Report ({context.date})",
            "",
            f"Total items: {len(articles)}",
            "",
        ]
        for idx, item in enumerate(articles, start=1):
            lines.append(f"## {idx}. {item.raw.title}")
            if item.summary:
                lines.append(f"- Summary: {item.summary}")
            if item.keywords:
                lines.append(f"- Keywords: {', '.join(item.keywords)}")
            lines.append(f"- Score: {item.score:.2f}")
            if item.raw.url:
                lines.append(f"- URL: {item.raw.url}")
            lines.append("")
        return Report(
            level="L2",
            title=f"AI Daily Report — {context.date}",
            content="\n".join(lines).strip(),
            article_ids=[item.raw.external_id for item in articles],
        )
