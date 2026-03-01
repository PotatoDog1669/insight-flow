"""飞书文档落盘"""

from app.renderers.base import Report
from app.sinks.base import BaseSink, PublishResult


class FeishuSink(BaseSink):
    @property
    def name(self) -> str:
        return "feishu"

    async def publish(self, report: Report, config: dict) -> PublishResult:
        # TODO: P1 实现
        return PublishResult(success=False, sink_name=self.name, error="Not implemented (P1)")
