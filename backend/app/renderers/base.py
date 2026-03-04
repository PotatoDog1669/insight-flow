"""报告渲染器抽象基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.processors.pipeline import ProcessedArticle


@dataclass
class RenderContext:
    """渲染上下文"""

    date: str = ""
    user_id: str | None = None
    extra: dict | None = None


@dataclass
class Report:
    """渲染后的报告"""

    level: str
    title: str
    content: str  # Markdown / HTML
    article_ids: list[str] | None = None
    metadata: dict = field(default_factory=dict)


class BaseRenderer(ABC):
    """报告渲染器抽象基类"""

    @property
    @abstractmethod
    def level(self) -> str:
        """模板等级: L1 / L2 / L3 / L4"""
        ...

    @abstractmethod
    async def render(self, articles: list[ProcessedArticle], context: RenderContext) -> Report:
        """渲染生成报告"""
        ...
