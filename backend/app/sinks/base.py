"""落盘目标抽象基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.renderers.base import Report


@dataclass
class PublishResult:
    """落盘结果"""

    success: bool
    sink_name: str
    url: str | None = None  # 落盘后的访问链接
    error: str | None = None


class BaseSink(ABC):
    """落盘目标抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def publish(self, report: Report, config: dict) -> PublishResult:
        """将报告发布到目标位置"""
        ...

    async def health_check(self) -> bool:
        return True
