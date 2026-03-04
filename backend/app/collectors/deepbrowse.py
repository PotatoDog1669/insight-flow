"""deepbrowse 兜底采集器"""

from app.collectors.base import BaseCollector, RawArticle
from app.collectors.blog_scraper import BlogScraperCollector
from app.collectors.registry import get_collector, register


@register("deepbrowse")
class DeepBrowseCollector(BaseCollector):
    """deepbrowse 浏览器 Agent 采集器（兜底方案）"""

    @property
    def name(self) -> str:
        return "deepbrowse"

    @property
    def category(self) -> str:
        return "blog"  # 默认分类，实际使用时根据配置覆盖

    async def collect(self, config: dict) -> list[RawArticle]:
        requested_agent = str(config.get("browser_agent", "codex_playwright")).strip() or "codex_playwright"
        if requested_agent and requested_agent not in {"deepbrowse", "blog_scraper"}:
            try:
                delegated = get_collector(requested_agent)
                delegated_config = {**config}
                delegated_config.pop("browser_agent", None)
                return await delegated.collect(delegated_config)
            except Exception:
                # Unknown agent or delegated collector failed -> fallback to profile scraper.
                pass

        # P0: default fallback to profile scraper.
        scraper = BlogScraperCollector()
        return await scraper.collect(config)
