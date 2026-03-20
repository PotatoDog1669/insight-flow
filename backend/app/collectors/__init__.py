"""信息获取层 — Collectors"""

from app.collectors.base import BaseCollector, RawArticle
from app.collectors.registry import register, get_collector, list_collectors
from app.collectors import blog_scraper as _blog_scraper  # noqa: F401
from app.collectors import browser_use as _browser_use  # noqa: F401
from app.collectors import codex_playwright as _codex_playwright  # noqa: F401
from app.collectors import deepbrowse as _deepbrowse  # noqa: F401
from app.collectors import github_trending as _github_trending  # noqa: F401
from app.collectors import huggingface as _huggingface  # noqa: F401
from app.collectors import openalex as _openalex  # noqa: F401
from app.collectors import europe_pmc as _europe_pmc  # noqa: F401
from app.collectors import pubmed as _pubmed  # noqa: F401
from app.collectors import rss as _rss  # noqa: F401
from app.collectors import twitter_snaplytics as _twitter_snaplytics  # noqa: F401

__all__ = ["BaseCollector", "RawArticle", "register", "get_collector", "list_collectors"]
