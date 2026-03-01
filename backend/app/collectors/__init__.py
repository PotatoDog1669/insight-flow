"""信息获取层 — Collectors"""

from app.collectors.base import BaseCollector, RawArticle
from app.collectors.registry import register, get_collector, list_collectors
from app.collectors import blog_scraper as _blog_scraper  # noqa: F401
from app.collectors import deepbrowse as _deepbrowse  # noqa: F401
from app.collectors import github_trending as _github_trending  # noqa: F401
from app.collectors import huggingface as _huggingface  # noqa: F401
from app.collectors import rss as _rss  # noqa: F401

__all__ = ["BaseCollector", "RawArticle", "register", "get_collector", "list_collectors"]
