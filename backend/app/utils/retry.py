"""重试与降级工具"""

import structlog
from app.collectors.base import RawArticle
from app.collectors.registry import get_collector

logger = structlog.get_logger()


class AllCollectorsFailed(Exception):
    """所有采集方式均失败"""

    def __init__(self, source_name: str):
        super().__init__(f"All collectors failed for source: {source_name}")


async def collect_with_fallback(source_name: str, config: dict) -> list[RawArticle]:
    """按优先级尝试多种采集方式（API → RSS → 爬虫 → deepbrowse）"""
    methods = config.get("fallback_chain", [config.get("collect_method", "rss")])

    for method in methods:
        try:
            collector = get_collector(method)
            result = await collector.collect(config)
            logger.info("collect_success", source=source_name, method=method, count=len(result))
            return result
        except Exception as e:
            logger.warning("collect_failed", source=source_name, method=method, error=str(e))
            continue

    raise AllCollectorsFailed(source_name)
