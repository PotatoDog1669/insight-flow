"""Obsidian / 本地 Markdown 落盘"""

from pathlib import Path

from app.renderers.base import Report
from app.sinks.base import BaseSink, PublishResult


class ObsidianSink(BaseSink):
    @property
    def name(self) -> str:
        return "obsidian"

    async def publish(self, report: Report, config: dict) -> PublishResult:
        vault_path = config.get("vault_path")
        if not vault_path:
            return PublishResult(success=False, sink_name=self.name, error="Missing Obsidian vault_path")

        target_dir = Path(vault_path)
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{report.title.replace('/', '-').strip()}.md"
        output = target_dir / filename
        output.write_text(report.content, encoding="utf-8")
        return PublishResult(success=True, sink_name=self.name, url=str(output))
