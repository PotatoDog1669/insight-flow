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
async def test_obsidian_rewrites_paper_digest_detail_links_to_obsidian_wikilinks(tmp_path: Path) -> None:
    sink = ObsidianSink()
    report = make_report(
        level="paper",
        title="2026-03-19 论文推荐",
        content=(
            "---\n"
            "date: 2026-03-19\n"
            "tags:\n"
            "  - daily-papers\n"
            "---\n\n"
            "# 2026-03-19 论文推荐\n\n"
            "## 总结\n\n"
            "本期重点观察 GUI 奖励建模。\n\n"
            "## Training & Evaluation\n\n"
            "### 1. OS-Themis\n\n"
            "![OS-Themis](https://example.com/os-themis.png)\n\n"
            "- 作者：Alice\n"
            "- 来源：arXiv\n"
            "- 链接：[Abs](https://arxiv.org/abs/2603.19191)\n\n"
            "**核心方法**\n\n"
            "通过多智能体 critic 建模奖励。\n\n"
        ),
        metadata={
            "paper_mode": "digest",
            "report_date": "2026-03-19",
            "paper_note_links": [],
        },
    )

    result = await sink.publish(report, {"mode": "file", "vault_path": str(tmp_path)})

    expected = tmp_path / "DailyPapers" / "2026-03-19-论文推荐.md"
    assert Path(result.url) == expected
    content = expected.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    assert "date: 2026-03-19" in content
    assert "## Properties" not in content
    assert "- 详细笔记：" not in content
    assert "![OS-Themis](https://example.com/os-themis.png)" in content


@pytest.mark.asyncio
async def test_obsidian_rewrites_paper_note_back_link_to_obsidian_wikilink(tmp_path: Path) -> None:
    sink = ObsidianSink()
    report = make_report(
        level="paper",
        title="OS-Themis",
        content=(
            "# Note\n\n"
            "回到推荐页：[2026-03-19 论文推荐](/reports/digest-1)\n"
        ),
        metadata={
            "paper_mode": "note",
            "paper_slug": "os-themis",
            "paper_parent_link": {
                "report_id": "digest-1",
                "title": "2026-03-19 论文推荐",
            },
        },
    )

    result = await sink.publish(report, {"mode": "file", "vault_path": str(tmp_path)})

    expected = tmp_path / "DailyPapers" / "Papers" / "os-themis.md"
    assert Path(result.url) == expected
    content = expected.read_text(encoding="utf-8")
    assert "[[DailyPapers/2026-03-19-论文推荐|2026-03-19 论文推荐]]" in content
    assert "/reports/digest-1" not in content


@pytest.mark.asyncio
async def test_obsidian_keeps_non_paper_reports_at_root(tmp_path: Path) -> None:
    sink = ObsidianSink()
    report = make_report(
        level="daily",
        title="AI Daily",
        content="# Daily Report",
        metadata={"report_date": "2026-03-19"},
    )

    result = await sink.publish(report, {"mode": "file", "vault_path": str(tmp_path)})

    expected = tmp_path / "AI Daily.md"
    assert Path(result.url) == expected
    assert expected.read_text(encoding="utf-8") == "# Daily Report"
