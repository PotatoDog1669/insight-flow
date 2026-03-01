"""deepbrowse 兜底采集器"""

from app.collectors.base import BaseCollector, RawArticle
from app.collectors.blog_scraper import BlogScraperCollector
from app.collectors.registry import register


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
        # P0 先复用 profile 爬虫逻辑作为 deepbrowse 兜底，后续可替换为真实 browser agent。
        scraper = BlogScraperCollector()
        return await scraper.collect(config)
