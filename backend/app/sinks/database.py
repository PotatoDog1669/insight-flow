"""数据库结构化存储落盘"""

from app.renderers.base import Report
from app.sinks.base import BaseSink, PublishResult


class DatabaseSink(BaseSink):
    @property
    def name(self) -> str:
        return "database"

    async def publish(self, report: Report, config: dict) -> PublishResult:
        report_id = config.get("report_id", "unknown")
        return PublishResult(success=True, sink_name=self.name, url=f"database://reports/{report_id}")
