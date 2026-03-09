import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from app.models.report import Report
from app.api.v1.reports import _to_report_response
from app.schemas.report import ReportEvent
import logging

DATABASE_URL = "postgresql+asyncpg://lex:password@localhost:5432/lexdeepresearch"
engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)

async def main():
    async with async_session() as session:
        stmt = select(Report).order_by(Report.created_at.desc()).limit(1)
        res = await session.execute(stmt)
        report = res.scalars().first()
        raw_events = report.metadata_.get('events', [])
        print('Raw events count:', len(raw_events))
        if raw_events:
            print('Type of first event:', type(raw_events[0]))
            for i, raw_event in enumerate(raw_events):
                try:
                    event = ReportEvent.model_validate(raw_event)
                except Exception as e:
                    print(f"Error validating event {i}:", e)
        resp = _to_report_response(report, include_full_content=False)
        print('Events count in response:', len(resp.events))

if __name__ == "__main__":
    asyncio.run(main())
