from pathlib import Path

import pytest

from app.renderers.base import Report
from app.sinks.obsidian import ObsidianSink


def make_report(level: str, title: str, content: str, metadata: dict | None = None) -> Report:
    return Report(level=level, title=title, content=content, article_ids=[], metadata=metadata or {})


@pytest.mark.asyncio
async def test_obsidian_publishes_paper_digest_to_dated_path(tmp_path: Path) -> None:
    sink = ObsidianSink()
    report = make_report(
        level="paper",
        title="Paper Digest",
        content="# Digest",
        metadata={"paper_mode": "digest", "report_date": "2026-03-19"},
    )

    result = await sink.publish(report, {"mode": "file", "vault_path": str(tmp_path)})

    assert result.success is True
    # digest note: DailyPapers/<report-date>-论文推荐.md
    expected = tmp_path / "DailyPapers" / "2026-03-19-论文推荐.md"
    assert Path(result.url) == expected
    assert expected.read_text(encoding="utf-8") == "# Digest"


@pytest.mark.asyncio
async def test_obsidian_publishes_paper_note_to_stable_paper_path(tmp_path: Path) -> None:
    sink = ObsidianSink()
    metadata = {"paper_mode": "note", "paper_identity": "arxiv:1234.5678", "paper_slug": "my-paper"}
    report = make_report(level="paper", title="My Paper Note", content="# Note", metadata=metadata)

    result1 = await sink.publish(report, {"mode": "file", "vault_path": str(tmp_path)})
    result2 = await sink.publish(report, {"mode": "file", "vault_path": str(tmp_path)})

    # per-paper note: DailyPapers/Papers/<paper-slug>.md
    expected = tmp_path / "DailyPapers" / "Papers" / "my-paper.md"
    assert Path(result1.url) == expected
    assert Path(result2.url) == expected
    assert expected.read_text(encoding="utf-8") == "# Note"


@pytest.mark.asyncio
async def test_obsidian_keeps_non_paper_reports_at_root(tmp_path: Path) -> None:
    sink = ObsidianSink()
    report = make_report(level="daily", title="AI Daily", content="# Daily Report", metadata={"report_date": "2026-03-19"})

    result = await sink.publish(report, {"mode": "file", "vault_path": str(tmp_path)})

    expected = tmp_path / "AI Daily.md"
    assert Path(result.url) == expected
    assert expected.read_text(encoding="utf-8") == "# Daily Report"
