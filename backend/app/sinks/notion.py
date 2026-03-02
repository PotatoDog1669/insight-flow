"""Notion 落盘 – 支持 429 重试与 3 req/s 速率贴近"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import settings
from app.renderers.base import Report
from app.sinks.base import BaseSink, PublishResult
from app.sinks.notion_client import (
    NOTION_API_BASE,
    NOTION_BLOCK_LIMIT,
    NOTION_DEFAULT_RETRY_AFTER,
    NOTION_MAX_RETRIES,
    NOTION_RICHTEXT_CHAR_LIMIT,
    NOTION_REQUEST_INTERVAL,
    NOTION_VERSION,
    chunk_blocks,
    markdown_to_paragraph_blocks,
)
from app.template_engine.renderer import load_sink_schema, render_sink_report_template
from app.utils.notion_ids import extract_notion_id

logger = logging.getLogger(__name__)


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    json: dict,
    max_retries: int = NOTION_MAX_RETRIES,
) -> httpx.Response:
    """Execute an HTTP request with automatic 429 retry & exponential backoff."""
    for attempt in range(max_retries + 1):
        if method == "POST":
            response = await client.post(url, json=json)
        else:
            response = await client.patch(url, json=json)

        if response.status_code != 429:
            return response

        if attempt == max_retries:
            return response  # exhausted retries, return the 429

        retry_after = float(response.headers.get("Retry-After", NOTION_DEFAULT_RETRY_AFTER))
        wait = max(retry_after, NOTION_DEFAULT_RETRY_AFTER) * (2 ** attempt)
        logger.warning(
            "Notion 429 rate-limited (attempt %d/%d), retrying after %.2fs",
            attempt + 1,
            max_retries,
            wait,
        )
        await asyncio.sleep(wait)

    return response  # pragma: no cover – unreachable, defensive


class NotionSink(BaseSink):
    @property
    def name(self) -> str:
        return "notion"

    async def publish(self, report: Report, config: dict) -> PublishResult:
        notion_database_id_raw = config.get("database_id") or settings.notion_database_id
        notion_parent_page_id_raw = config.get("parent_page_id") or settings.notion_parent_page_id
        notion_api_key = config.get("api_key") or settings.notion_api_key
        notion_database_id = extract_notion_id(str(notion_database_id_raw or "")) or str(notion_database_id_raw or "")
        notion_parent_page_id = extract_notion_id(str(notion_parent_page_id_raw or "")) or str(notion_parent_page_id_raw or "")
        if not notion_database_id and not notion_parent_page_id:
            return PublishResult(success=False, sink_name=self.name, error="Missing Notion database_id or parent_page_id")
        if not notion_api_key:
            return PublishResult(success=False, sink_name=self.name, error="Missing Notion api_key")

        template_version = str(config.get("template_version") or "v1").strip() or "v1"
        notion_schema = load_sink_schema(sink=self.name, version=template_version)
        title_property_default = str(notion_schema.get("title_property") or "Name")
        summary_property_default = str(notion_schema.get("summary_property") or "TL;DR")
        time_period = str(
            config.get("time_period")
            or (report.metadata or {}).get("time_period")
            or "daily"
        ).strip()
        report_type = str(
            config.get("report_type")
            or (report.metadata or {}).get("report_type")
            or ("weekly" if time_period == "weekly" else "daily")
        ).strip()
        report_date = str(config.get("report_date") or "")
        rendered_content = _render_notion_content(
            report=report,
            report_type=report_type,
            version=template_version,
            report_date=report_date,
        )

        headers = {
            "Authorization": f"Bearer {notion_api_key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }
        blocks = markdown_to_paragraph_blocks(rendered_content)
        title = report.title[:200]
        parent, properties = _build_parent_and_properties(
            notion_database_id=str(notion_database_id or ""),
            notion_parent_page_id=str(notion_parent_page_id or ""),
            title=title,
            title_property=str(config.get("title_property") or title_property_default),
            summary_property=str(config.get("summary_property") or summary_property_default),
            summary_text=str(config.get("summary_text", "")).strip(),
        )
        timeout_seconds = int(config.get("timeout_sec", 30))
        async with httpx.AsyncClient(timeout=timeout_seconds, headers=headers) as client:
            try:
                # ---- Short report: single request with children ----
                if len(blocks) <= NOTION_BLOCK_LIMIT:
                    page_payload = {
                        "parent": parent,
                        "properties": properties,
                        "children": blocks,
                    }
                    response = await _request_with_retry(client, "POST", f"{NOTION_API_BASE}/pages", json=page_payload)
                    if response.status_code >= 400:
                        return PublishResult(
                            success=False,
                            sink_name=self.name,
                            error=f"Notion create page failed: {response.status_code} {response.text[:300]}",
                        )
                    data = response.json()
                    return PublishResult(success=True, sink_name=self.name, url=data.get("url"))

                # ---- Long report: create page, then append blocks in chunks ----
                create_payload = {
                    "parent": parent,
                    "properties": properties,
                }
                create_response = await _request_with_retry(
                    client, "POST", f"{NOTION_API_BASE}/pages", json=create_payload
                )
                if create_response.status_code >= 400:
                    return PublishResult(
                        success=False,
                        sink_name=self.name,
                        error=f"Notion create page failed: {create_response.status_code} {create_response.text[:300]}",
                    )
                created = create_response.json()
                page_id = created.get("id")
                if not page_id:
                    return PublishResult(success=False, sink_name=self.name, error="Notion response missing page id")

                chunks = chunk_blocks(blocks, chunk_size=NOTION_BLOCK_LIMIT)
                for idx, chunk in enumerate(chunks):
                    # Pace at ~3 req/s – skip delay before the first chunk
                    if idx > 0:
                        await asyncio.sleep(NOTION_REQUEST_INTERVAL)

                    append_response = await _request_with_retry(
                        client,
                        "PATCH",
                        f"{NOTION_API_BASE}/blocks/{page_id}/children",
                        json={"children": chunk},
                    )
                    if append_response.status_code >= 400:
                        return PublishResult(
                            success=False,
                            sink_name=self.name,
                            error=f"Notion append blocks failed: {append_response.status_code} {append_response.text[:300]}",
                        )
                return PublishResult(success=True, sink_name=self.name, url=created.get("url"))
            except Exception as exc:  # pragma: no cover - defensive path
                return PublishResult(success=False, sink_name=self.name, error=f"Notion publish exception: {exc}")


def _build_parent_and_properties(
    notion_database_id: str,
    notion_parent_page_id: str,
    title: str,
    title_property: str,
    summary_property: str,
    summary_text: str,
) -> tuple[dict, dict]:
    title_block = [
        {
            "type": "text",
            "text": {"content": title},
        }
    ]
    if notion_database_id:
        properties = {title_property: {"title": title_block}}
        summary_chunks = _to_rich_text(summary_text)
        if summary_property and summary_chunks:
            properties[summary_property] = {"rich_text": summary_chunks}
        return {"database_id": notion_database_id}, properties
    return {"page_id": notion_parent_page_id}, {"title": title_block}


def _to_rich_text(text: str) -> list[dict]:
    if not text:
        return []
    rich_text: list[dict] = []
    remaining = text
    while remaining:
        chunk = remaining[:NOTION_RICHTEXT_CHAR_LIMIT]
        remaining = remaining[NOTION_RICHTEXT_CHAR_LIMIT:]
        rich_text.append({"type": "text", "text": {"content": chunk}})
    return rich_text


def _render_notion_content(
    *,
    report: Report,
    report_type: str,
    version: str,
    report_date: str,
) -> str:
    base_content = report.content or ""
    context = {
        "title": report.title,
        "content": base_content,
        "level": report.level,
        "article_ids": report.article_ids or [],
        "metadata": report.metadata or {},
        "report_date": report_date,
    }
    try:
        rendered = render_sink_report_template(
            sink="notion",
            report_type=report_type,
            context=context,
            version=version,
        )
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("notion_template_render_failed: %s", exc)
        return base_content
    return rendered if isinstance(rendered, str) and rendered.strip() else base_content
