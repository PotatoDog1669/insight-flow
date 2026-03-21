"""报告 API"""

import uuid
from datetime import UTC, date, datetime
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.destinations.instances import (
    _destination_settings_from_user,
    _get_or_create_default_user,
)
from app.models.database import get_db
from app.models.report import Report
from app.renderers.base import Report as RenderedReport
from app.scheduler.orchestrator import Orchestrator
from app.schemas.report import (
    ReportCustomRequest,
    ReportEvent,
    ReportFilterMonitorOption,
    ReportFiltersResponse,
    ReportPublishRequest,
    ReportResponse,
    ReportTopic,
)
from app.sinks.registry import get_sink

router = APIRouter()
_PAPER_DIGEST_SUMMARY_RE = re.compile(
    r"^##\s*本期导读\s*(?:\n+)(.+?)(?=\n##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)


@router.get("", response_model=list[ReportResponse])
async def list_reports(
    db: AsyncSession = Depends(get_db),
    time_period: str | None = Query(default=None),
    report_type: str | None = Query(default=None),
    monitor_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    page: int = Query(default=1, ge=1),
):
    """查看报告列表"""
    stmt = select(Report)
    if time_period:
        stmt = stmt.where(Report.time_period == time_period)
    if report_type:
        stmt = stmt.where(Report.report_type == report_type)
    stmt = stmt.order_by(Report.report_date.desc(), Report.created_at.desc())
    result = await db.execute(stmt)
    reports = result.scalars().all()
    reports = [
        report
        for report in reports
        if not (
            report.report_type == "paper"
            and isinstance(report.metadata_, dict)
            and str(report.metadata_.get("paper_mode") or "").strip().lower() == "note"
        )
    ]
    monitor_uuid = _parse_optional_uuid(monitor_id)
    if monitor_uuid is not None:
        reports = [report for report in reports if _report_monitor_id(report) == monitor_uuid]
    offset = (page - 1) * limit
    selected_reports = reports[offset : offset + limit]
    return [_to_report_response(report, include_full_content=False) for report in selected_reports]


@router.get("/filters", response_model=ReportFiltersResponse)
async def get_report_filters(db: AsyncSession = Depends(get_db)):
    """获取报告筛选维度聚合（P0）"""
    result = await db.execute(select(Report))
    reports = result.scalars().all()
    periods = sorted({report.time_period for report in reports if report.time_period})
    report_types = sorted({report.report_type for report in reports if report.report_type})
    categories: set[str] = set()
    monitors: dict[uuid.UUID, str] = {}
    for report in reports:
        categories.update((report.metadata_ or {}).get("categories", []))
        monitor_uuid = _report_monitor_id(report)
        monitor_name = _report_monitor_name(report)
        if monitor_uuid is not None and monitor_name:
            monitors[monitor_uuid] = monitor_name
    return ReportFiltersResponse(
        time_periods=periods,
        report_types=report_types,
        categories=sorted(categories),
        monitors=[
            ReportFilterMonitorOption(id=monitor_uuid, name=monitor_name)
            for monitor_uuid, monitor_name in sorted(monitors.items(), key=lambda item: item[1])
        ],
    )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: str, db: AsyncSession = Depends(get_db)):
    """查看单份报告详情"""
    report = await db.get(Report, _parse_uuid(report_id))
    if report:
        return _to_report_response(report, include_full_content=True)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(report_id: str, db: AsyncSession = Depends(get_db)):
    """删除单份报告"""
    report = await db.get(Report, _parse_uuid(report_id))
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    await db.delete(report)
    await db.commit()


@router.post("/{report_id}/publish", response_model=ReportResponse)
async def publish_report(report_id: str, payload: ReportPublishRequest, db: AsyncSession = Depends(get_db)):
    """手动补同步单份报告到指定目标"""
    report = await db.get(Report, _parse_uuid(report_id))
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    user = await _get_or_create_default_user(db)
    destination_settings = await _destination_settings_from_user(db, user)
    targets = _resolve_publish_targets(payload)
    if not targets:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one destination must be selected",
        )

    rendered = _to_rendered_report(report)
    publish_trace = list(report.publish_trace or [])
    published_to = [str(item) for item in (report.published_to or []) if str(item).strip()]
    last_failure: str | None = None

    for target in targets:
        destination = destination_settings.get(target)
        if not isinstance(destination, dict):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found")
        if destination.get("enabled") is False:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Destination is not enabled")

        sink_name = Orchestrator._resolve_sink_name(target=target, destination_settings=destination_settings)
        sink_config = Orchestrator._build_sink_config(
            target=target,
            report_id=str(report.id),
            destination_settings=destination_settings,
        )
        sink_config.setdefault("time_period", report.time_period)
        sink_config.setdefault("template_version", "v1")
        sink_config.setdefault("report_type", str((report.metadata_ or {}).get("report_type") or report.report_type))
        sink_config.setdefault("report_date", str(report.report_date))
        sink_config.setdefault("report_metadata", dict(report.metadata_ or {}))
        if sink_name == "notion":
            sink_config.setdefault("summary_property", "TL;DR")
            summary_text = str((report.metadata_ or {}).get("global_tldr") or "").strip()
            if summary_text:
                sink_config["summary_text"] = summary_text

        started_at = datetime.now(UTC)
        publish_result = await get_sink(sink_name).publish(rendered, sink_config)
        latency_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)
        publish_trace.append(
            {
                "stage": "publish",
                "sink": sink_name,
                "provider": target,
                "destination_instance_id": Orchestrator._destination_instance_id(
                    target=target,
                    destination_settings=destination_settings,
                ),
                "destination_instance_name": Orchestrator._destination_instance_name(
                    target=target,
                    destination_settings=destination_settings,
                ),
                "status": "success" if publish_result.success else "failed",
                "url": publish_result.url,
                "error": publish_result.error,
                "latency_ms": latency_ms,
                "trigger": "manual",
            }
        )
        if publish_result.success and sink_name not in published_to:
            published_to.append(sink_name)
        if not publish_result.success:
            last_failure = publish_result.error or "Publish failed"

    report.publish_trace = publish_trace
    report.published_to = published_to
    report.published_destination_instance_ids = Orchestrator._published_destination_instance_ids(publish_trace)
    db.add(report)
    await db.commit()
    await db.refresh(report)

    if last_failure:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": last_failure, "report": _to_report_response(report)},
        )
    return _to_report_response(report)


@router.post("/custom", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_custom_report(request: ReportCustomRequest):
    """提交自定义报告请求（P2 预留）"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "Not implemented (P2)",
            "request_echo": request.model_dump(mode="json"),
        },
    )


def _parse_uuid(raw_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid UUID") from exc


def _parse_optional_uuid(raw_id: str | None) -> uuid.UUID | None:
    if not raw_id:
        return None
    return _parse_uuid(raw_id)


def _report_monitor_id(report: Report) -> uuid.UUID | None:
    raw_monitor_id = (report.metadata_ or {}).get("monitor_id")
    if not raw_monitor_id:
        return None
    try:
        return uuid.UUID(str(raw_monitor_id))
    except ValueError:
        return None


def _report_monitor_name(report: Report) -> str:
    return str((report.metadata_ or {}).get("monitor_name") or "").strip()


def _to_report_response(report: Report, *, include_full_content: bool = True) -> ReportResponse:
    metadata = report.metadata_ or {}
    topics = [
        ReportTopic(name=item.get("name", ""), weight=max(int(item.get("weight", 1)), 1))
        for item in metadata.get("topics", [])
        if isinstance(item, dict) and item.get("name")
    ]
    tldr = metadata.get("tldr", [])
    if not isinstance(tldr, list):
        tldr = []
    tldr = [str(item).strip() for item in tldr if str(item).strip()]
    if not tldr:
        fallback_tldr = _fallback_report_tldr(report=report, metadata=metadata)
        if fallback_tldr:
            tldr = [fallback_tldr]
    events: list[ReportEvent] = []
    global_tldr = ""
    response_metadata: dict = {}
    response_content = ""
    raw_events = metadata.get("events", [])
    if isinstance(raw_events, list):
        for raw_event in raw_events:
            if not isinstance(raw_event, dict):
                continue
            try:
                events.append(ReportEvent.model_validate(raw_event))
            except Exception:
                continue

    if include_full_content:
        global_tldr = str(metadata.get("global_tldr") or "")
        response_metadata = metadata
        response_content = report.content or ""
    return ReportResponse(
        id=report.id,
        user_id=report.user_id,
        monitor_id=_report_monitor_id(report),
        monitor_name=_report_monitor_name(report),
        time_period=report.time_period,  # type: ignore[arg-type]
        report_type=report.report_type,  # type: ignore[arg-type]
        title=report.title,
        tldr=tldr,
        article_count=len(report.article_ids or []),
        topics=topics,
        events=events,
        global_tldr=global_tldr,
        content=response_content,
        article_ids=[uuid.UUID(item) if isinstance(item, str) else item for item in (report.article_ids or [])],
        published_to=report.published_to or [],
        published_destination_instance_ids=[
            str(item) for item in (report.published_destination_instance_ids or []) if str(item).strip()
        ],
        publish_trace=report.publish_trace or [],
        metadata=response_metadata,
        report_date=report.report_date if isinstance(report.report_date, date) else date.today(),
        created_at=report.created_at,
    )


def _to_rendered_report(report: Report) -> RenderedReport:
    metadata = dict(report.metadata_ or {})
    raw_article_ids = report.article_ids or []
    article_ids = [str(item) for item in raw_article_ids]
    level = str(metadata.get("level") or "L2").strip() or "L2"
    return RenderedReport(
        level=level,
        title=report.title,
        content=report.content or "",
        article_ids=article_ids,
        metadata=metadata,
    )


def _resolve_publish_targets(payload: ReportPublishRequest) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    requested_targets = [str(item) for item in payload.destination_instance_ids]
    if payload.destination_id:
        requested_targets.append(payload.destination_id)
    for target in requested_targets:
        value = str(target).strip()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


def _fallback_report_tldr(*, report: Report, metadata: dict) -> str:
    global_tldr = str(metadata.get("global_tldr") or "").strip()
    if global_tldr:
        return global_tldr
    if report.report_type != "paper":
        return ""
    if str(metadata.get("paper_mode") or "").strip().lower() != "digest":
        return ""
    return _extract_paper_digest_summary(report.content or "")


def _extract_paper_digest_summary(content: str) -> str:
    text = str(content or "").replace("\r\n", "\n")
    match = _PAPER_DIGEST_SUMMARY_RE.search(text)
    if not match:
        return ""
    summary = match.group(1).strip()
    summary = re.sub(r"\n{2,}", "\n", summary)
    summary = re.sub(r"\s+", " ", summary)
    return summary.strip()
