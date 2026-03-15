"""报告 API"""

import uuid
from datetime import date

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.report import Report
from app.schemas.report import ReportCustomRequest
from app.schemas.report import ReportEvent
from app.schemas.report import ReportFilterMonitorOption
from app.schemas.report import ReportFiltersResponse
from app.schemas.report import ReportResponse
from app.schemas.report import ReportTopic

router = APIRouter()


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
        tldr=[str(item) for item in tldr],
        article_count=len(report.article_ids or []),
        topics=topics,
        events=events,
        global_tldr=global_tldr,
        content=response_content,
        article_ids=[uuid.UUID(item) if isinstance(item, str) else item for item in (report.article_ids or [])],
        published_to=report.published_to or [],
        publish_trace=report.publish_trace or [],
        metadata=response_metadata,
        report_date=report.report_date if isinstance(report.report_date, date) else date.today(),
        created_at=report.created_at,
    )
