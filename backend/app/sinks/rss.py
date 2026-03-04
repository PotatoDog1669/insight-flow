"""RSS feed sink for publishing rendered reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from email.utils import format_datetime
import html
import os
from pathlib import Path
import re
from urllib.parse import urlparse
from xml.dom.minidom import Document

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PROJECT_ROOT
from app.models.database import async_session
from app.models.report import Report as ReportModel
from app.renderers.base import Report
from app.sinks.base import BaseSink, PublishResult

ATOM_NS = "http://www.w3.org/2005/Atom"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
DEFAULT_FEED_URL = "http://localhost:8000/api/v1/feed.xml"
DEFAULT_SITE_URL = "http://localhost:3000"
DEFAULT_FEED_TITLE = "LexDeepResearch Reports"
DEFAULT_FEED_DESCRIPTION = "Latest generated reports from LexDeepResearch."
DEFAULT_MAX_ITEMS = 20
MAX_ALLOWED_ITEMS = 100
DEFAULT_FEED_PATH = PROJECT_ROOT / "backend" / "static" / "feed.xml"

_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*]\([^)]*\)")
_MARKDOWN_STRONG_RE = re.compile(r"\*\*([^*]+)\*\*")
_MARKDOWN_EM_RE = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_MARKDOWN_CODE_RE = re.compile(r"`([^`]+)`")
_HTML_HINT_RE = re.compile(r"<(p|h1|h2|h3|ul|li|a|blockquote|pre|code|img)\b", re.IGNORECASE)


@dataclass(frozen=True)
class FeedSettings:
    feed_url: str
    site_url: str
    title: str
    description: str
    max_items: int
    feed_path: Path


class RssSink(BaseSink):
    @property
    def name(self) -> str:
        return "rss"

    async def publish(self, report: Report, config: dict) -> PublishResult:
        del report  # sink output is derived from persisted report rows
        settings = resolve_feed_settings(config)

        try:
            async with async_session() as db:
                reports = await fetch_recent_reports(db=db, max_items=settings.max_items)
            xml_body = build_feed_xml(reports=reports, settings=settings)
            _write_feed_xml(path=settings.feed_path, xml_body=xml_body)
        except (SQLAlchemyError, OSError, ValueError) as exc:
            return PublishResult(success=False, sink_name=self.name, error=f"RSS publish failed: {exc}")

        return PublishResult(success=True, sink_name=self.name, url=settings.feed_url)


def resolve_feed_settings(config: dict | None) -> FeedSettings:
    payload = config if isinstance(config, dict) else {}
    feed_url = str(payload.get("feed_url") or DEFAULT_FEED_URL).strip() or DEFAULT_FEED_URL
    site_url = _resolve_site_url(raw=payload.get("site_url"), feed_url=feed_url)
    title = str(payload.get("feed_title") or DEFAULT_FEED_TITLE).strip() or DEFAULT_FEED_TITLE
    description = str(payload.get("feed_description") or DEFAULT_FEED_DESCRIPTION).strip() or DEFAULT_FEED_DESCRIPTION
    max_items = _resolve_max_items(payload.get("max_items"))
    feed_path = _resolve_feed_path(payload.get("feed_path"))
    return FeedSettings(
        feed_url=feed_url,
        site_url=site_url,
        title=title,
        description=description,
        max_items=max_items,
        feed_path=feed_path,
    )


async def fetch_recent_reports(db: AsyncSession, max_items: int) -> list[ReportModel]:
    stmt = (
        select(ReportModel)
        .order_by(ReportModel.report_date.desc(), ReportModel.created_at.desc())
        .limit(max_items)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def build_feed_xml(reports: list[ReportModel], settings: FeedSettings) -> str:
    doc = Document()
    rss = doc.createElement("rss")
    rss.setAttribute("version", "2.0")
    rss.setAttribute("xmlns:atom", ATOM_NS)
    rss.setAttribute("xmlns:content", CONTENT_NS)
    doc.appendChild(rss)

    channel = doc.createElement("channel")
    rss.appendChild(channel)

    _append_text_node(doc, channel, "title", settings.title)
    _append_text_node(doc, channel, "link", settings.site_url)
    _append_text_node(doc, channel, "description", settings.description)

    atom_link = doc.createElement("atom:link")
    atom_link.setAttribute("href", settings.feed_url)
    atom_link.setAttribute("rel", "self")
    atom_link.setAttribute("type", "application/rss+xml")
    channel.appendChild(atom_link)

    _append_text_node(doc, channel, "generator", "LexDeepResearch")
    _append_text_node(doc, channel, "language", "zh-CN")
    _append_text_node(doc, channel, "lastBuildDate", _format_rfc822(_last_build_time(reports)))

    for report in reports:
        item = doc.createElement("item")
        channel.appendChild(item)

        report_link = build_report_link(site_url=settings.site_url, report_id=str(report.id))
        _append_text_node(doc, item, "title", report.title)
        _append_text_node(doc, item, "link", report_link)
        _append_text_node(doc, item, "description", _report_summary(report))

        content_node = doc.createElement("content:encoded")
        content_node.appendChild(doc.createCDATASection(_report_html_content(report)))
        item.appendChild(content_node)

        guid = doc.createElement("guid")
        guid.setAttribute("isPermaLink", "false")
        guid.appendChild(doc.createTextNode(str(report.id)))
        item.appendChild(guid)

        _append_text_node(doc, item, "pubDate", _format_rfc822(_report_published_time(report)))

    return doc.toxml(encoding="UTF-8").decode("utf-8")


def build_report_link(site_url: str, report_id: str) -> str:
    base = site_url.rstrip("/")
    return f"{base}/reports/{report_id}"


def _resolve_max_items(raw: object) -> int:
    if isinstance(raw, int) and 1 <= raw <= MAX_ALLOWED_ITEMS:
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if text.isdigit():
            parsed = int(text)
            if 1 <= parsed <= MAX_ALLOWED_ITEMS:
                return parsed
    return DEFAULT_MAX_ITEMS


def _resolve_site_url(raw: object, feed_url: str) -> str:
    if isinstance(raw, str) and raw.strip():
        return raw.rstrip("/")
    parsed = urlparse(feed_url)
    if parsed.scheme and parsed.netloc:
        if parsed.hostname in {"localhost", "127.0.0.1"} and parsed.port == 8000:
            return f"{parsed.scheme}://{parsed.hostname}:3000"
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    return DEFAULT_SITE_URL


def _resolve_feed_path(raw: object) -> Path:
    if isinstance(raw, str) and raw.strip():
        candidate = Path(raw.strip())
        return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate
    return DEFAULT_FEED_PATH


def _append_text_node(doc: Document, parent, name: str, value: str) -> None:
    node = doc.createElement(name)
    node.appendChild(doc.createTextNode(value))
    parent.appendChild(node)


def _last_build_time(reports: list[ReportModel]) -> datetime:
    if not reports:
        return datetime.now(timezone.utc)
    return max((_report_published_time(report) for report in reports), default=datetime.now(timezone.utc))


def _report_published_time(report: ReportModel) -> datetime:
    if isinstance(report.created_at, datetime):
        if report.created_at.tzinfo is None:
            return report.created_at.replace(tzinfo=timezone.utc)
        return report.created_at.astimezone(timezone.utc)
    if isinstance(report.report_date, date):
        return datetime.combine(report.report_date, time.min, tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _format_rfc822(ts: datetime) -> str:
    value = ts.astimezone(timezone.utc)
    return format_datetime(value)


def _report_summary(report: ReportModel) -> str:
    metadata = report.metadata_ if isinstance(report.metadata_, dict) else {}
    summary = str(metadata.get("global_tldr") or "").strip()
    if not summary:
        tldr = metadata.get("tldr", [])
        if isinstance(tldr, list):
            summary = str(next((item for item in tldr if isinstance(item, str) and item.strip()), "")).strip()
    if not summary:
        summary = _strip_markdown_for_summary(report.content or "")
    compact = re.sub(r"\s+", " ", summary).strip()
    if len(compact) > 280:
        return f"{compact[:279]}…"
    return compact


def _strip_markdown_for_summary(content: str) -> str:
    text = _MARKDOWN_IMAGE_RE.sub(" ", content)
    text = _MARKDOWN_LINK_RE.sub(r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = text.replace("```", " ").replace("`", " ")
    text = text.replace("**", " ").replace("*", " ")
    text = text.replace(">", " ").replace("-", " ")
    return text


def _report_html_content(report: ReportModel) -> str:
    content = report.content or ""
    if _HTML_HINT_RE.search(content):
        return content
    return _markdown_to_html(content)


def _markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    blocks: list[str] = []
    list_items: list[str] = []

    def flush_list() -> None:
        if not list_items:
            return
        blocks.append("<ul>" + "".join(f"<li>{item}</li>" for item in list_items) + "</ul>")
        list_items.clear()

    for raw in lines:
        line = raw.strip()
        if not line:
            flush_list()
            continue
        if line == "---":
            flush_list()
            blocks.append("<hr/>")
            continue
        if line.startswith("- "):
            list_items.append(_render_inline_markdown(line[2:].strip()))
            continue

        flush_list()
        if line.startswith("### "):
            blocks.append(f"<h3>{_render_inline_markdown(line[4:].strip())}</h3>")
        elif line.startswith("## "):
            blocks.append(f"<h2>{_render_inline_markdown(line[3:].strip())}</h2>")
        elif line.startswith("# "):
            blocks.append(f"<h1>{_render_inline_markdown(line[2:].strip())}</h1>")
        elif line.startswith("> "):
            blocks.append(f"<blockquote><p>{_render_inline_markdown(line[2:].strip())}</p></blockquote>")
        else:
            blocks.append(f"<p>{_render_inline_markdown(line)}</p>")

    flush_list()
    return "\n".join(blocks)


def _render_inline_markdown(text: str) -> str:
    parts: list[str] = []
    cursor = 0
    for match in _MARKDOWN_LINK_RE.finditer(text):
        if match.start() > cursor:
            parts.append(_render_inline_without_links(text[cursor:match.start()]))
        label = html.escape(match.group(1))
        href = html.escape(match.group(2), quote=True)
        parts.append(f'<a href="{href}">{label}</a>')
        cursor = match.end()
    parts.append(_render_inline_without_links(text[cursor:]))
    return "".join(parts)


def _render_inline_without_links(text: str) -> str:
    escaped = html.escape(text)
    escaped = _MARKDOWN_CODE_RE.sub(r"<code>\1</code>", escaped)
    escaped = _MARKDOWN_STRONG_RE.sub(r"<strong>\1</strong>", escaped)
    escaped = _MARKDOWN_EM_RE.sub(r"<em>\1</em>", escaped)
    return escaped


def _write_feed_xml(path: Path, xml_body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(xml_body, encoding="utf-8")
    os.replace(temp_path, path)
