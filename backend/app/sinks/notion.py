"""Notion 落盘"""

from app.renderers.base import Report
from app.sinks.base import BaseSink, PublishResult


class NotionSink(BaseSink):
    @property
    def name(self) -> str:
        return "notion"

    async def publish(self, report: Report, config: dict) -> PublishResult:
        notion_database_id = config.get("database_id")
        if not notion_database_id:
            return PublishResult(success=False, sink_name=self.name, error="Missing Notion database_id")
        # P0: 仅保留接口占位，真实 API 对接在后续迭代开启。
        return PublishResult(success=True, sink_name=self.name, url=f"notion://database/{notion_database_id}")
