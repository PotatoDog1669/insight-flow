"""Browser-use style collector adapter (MVP wrapper)."""

from app.collectors.base import BaseCollector, RawArticle
from app.collectors.blog_scraper import BlogScraperCollector
from app.collectors.registry import register


@register("browser_use")
class BrowserUseCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "browser_use"

    @property
    def category(self) -> str:
        return "blog"

    async def collect(self, config: dict) -> list[RawArticle]:
        # MVP: reuse profile scraper until real browser_use bridge is integrated.
        return await BlogScraperCollector().collect(config)
