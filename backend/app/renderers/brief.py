"""速览渲染器。"""

from app.processors.pipeline import ProcessedArticle
from app.renderers.base import BaseRenderer, RenderContext, Report
from app.template_engine.renderer import render_report_template


class BriefRenderer(BaseRenderer):
    @property
    def level(self) -> str:
        return "L1"

    async def render(self, articles: list[ProcessedArticle], context: RenderContext) -> Report:
        """从日报条目中提炼速览。"""
        top_items = articles[:8]
        items = [(item.summary or item.raw.title).strip() for item in top_items if (item.summary or item.raw.title)]
        overview = [{"category": "Highlights", "events": [{"title": item, "index": idx + 1, "first_link": ""} for idx, item in enumerate(items)]}]
        content = render_report_template(
            report_type="daily",
            version="v1",
            context={"date": context.date, "overview": overview, "events": []},
        )
        return Report(
            level="L1",
            title=f"AI Briefing — {context.date}",
            content=content,
            article_ids=[item.raw.external_id for item in top_items],
            metadata={
                "time_period": "daily",
                "report_type": "daily",
            },
        )
