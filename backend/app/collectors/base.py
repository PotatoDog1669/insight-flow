"""信息源采集器抽象基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawArticle:
    """采集到的原始文章数据结构"""

    external_id: str
    title: str
    url: str | None = None
    content: str | None = None
    published_at: datetime | None = None
    metadata: dict = field(default_factory=dict)


class BaseCollector(ABC):
    """信息源采集器抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """采集器名称"""
        ...

    @property
    @abstractmethod
    def category(self) -> str:
        """信息源类别: open_source / blog / academic / social"""
        ...

    @abstractmethod
    async def collect(self, config: dict) -> list[RawArticle]:
        """
        执行一次采集，返回原始文章列表。
        :param config: 信息源配置（来自 sources.config 字段）
        """
        ...

    async def health_check(self) -> bool:
        """健康检查，默认返回 True"""
        return True
