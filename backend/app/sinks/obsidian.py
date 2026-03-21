"""Obsidian / 本地 Markdown 落盘"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import httpx

from app.renderers.base import Report
from app.sinks.base import BaseSink, PublishResult


class ObsidianSink(BaseSink):
    @property
    def name(self) -> str:
        return "obsidian"

    async def publish(self, report: Report, config: dict) -> PublishResult:
        filename = _build_filename(report.title)
        mode = _normalize_mode(config.get("mode"))
        api_url = str(config.get("api_url") or "").strip()
        api_key = str(config.get("api_key") or "").strip()
        vault_path = str(config.get("vault_path") or "").strip()
        target_folder = _normalize_target_folder(str(config.get("target_folder") or ""))

        if mode is None:
            return PublishResult(
                success=False,
                sink_name=self.name,
                error="Missing Obsidian mode: choose 'rest' or 'file'",
            )

        if mode == "rest":
            if not api_url or not api_key:
                return PublishResult(
                    success=False,
                    sink_name=self.name,
                    error="Missing Obsidian REST config: api_url and api_key are required for rest mode",
                )
            return await self._publish_via_rest(
                api_url=api_url,
                api_key=api_key,
                target_folder=target_folder,
                filename=filename,
                content=report.content,
            )

        if mode != "file":
            return PublishResult(success=False, sink_name=self.name, error=f"Unsupported Obsidian mode: {mode}")

        target_dir = _resolve_local_target_dir(vault_path=vault_path, target_folder=target_folder)
        if target_dir is None:
            return PublishResult(
                success=False,
                sink_name=self.name,
                error="Missing Obsidian file config: vault_path is required for file mode",
            )

        base_dir = target_dir
        if report.level == "paper":
            metadata = report.metadata or {}
            paper_mode = metadata.get("paper_mode")
            if paper_mode == "digest":
                report_date = str(metadata.get("report_date") or "").strip()
                target_dir = base_dir / "DailyPapers"
                filename = f"{report_date}-论文推荐.md" if report_date else _build_filename(report.title)
            elif paper_mode == "note":
                paper_slug = (
                    str(metadata.get("paper_slug") or "").strip()
                    or report.title.replace("/", "-").strip()
                    or "paper-note"
                )
                target_dir = base_dir / "DailyPapers" / "Papers"
                filename = f"{paper_slug}.md"
            else:
                target_dir = base_dir
                filename = _build_filename(report.title)
        else:
            target_dir = base_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        output = target_dir / filename
        output.write_text(report.content, encoding="utf-8")
        return PublishResult(success=True, sink_name=self.name, url=str(output))

    async def _publish_via_rest(
        self,
        *,
        api_url: str,
        api_key: str,
        target_folder: str,
        filename: str,
        content: str,
    ) -> PublishResult:
        note_path = "/".join(part for part in (target_folder, filename) if part)
        url = f"{api_url.rstrip('/')}/vault/{quote(note_path, safe='/')}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "text/markdown; charset=utf-8",
        }

        try:
            async with httpx.AsyncClient(timeout=30, verify=False) as client:
                response = await client.put(url, content=content, headers=headers)
        except httpx.RequestError as exc:
            return PublishResult(success=False, sink_name=self.name, error=f"Obsidian REST request failed: {exc}")

        if response.status_code >= 400:
            return PublishResult(
                success=False,
                sink_name=self.name,
                error=f"Obsidian REST publish failed: {response.status_code} {response.text[:300]}",
            )
        return PublishResult(success=True, sink_name=self.name, url=url)


def _build_filename(title: str) -> str:
    return f"{title.replace('/', '-').strip()}.md"


def _normalize_target_folder(target_folder: str) -> str:
    return target_folder.strip().strip("/")


def _normalize_mode(value: object) -> str | None:
    raw = str(value or "").strip().lower()
    if raw in {"rest", "file"}:
        return raw
    return None


def _resolve_local_target_dir(*, vault_path: str, target_folder: str) -> Path | None:
    if not vault_path:
        return None

    target_dir = Path(vault_path)
    if target_folder:
        target_dir = target_dir / Path(target_folder)
    return target_dir
