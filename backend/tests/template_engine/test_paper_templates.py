from __future__ import annotations

from app.template_engine.renderer import render_report_template, render_sink_report_template


def test_render_paper_digest_template() -> None:
    content = render_report_template(
        report_type="paper",
        version="v1",
        context={
            "paper_mode": "digest",
            "title": "2026-03-20 论文推荐",
            "date": "2026-03-20",
            "summary": "本期聚焦世界模型与具身智能。",
            "papers": [
                {
                    "title": "MVISTA-4D",
                    "authors": "Jiaxu Wang et al.",
                    "affiliations": "The Chinese University of Hong Kong",
                    "figure": "https://example.com/figure.png",
                    "one_line": "值得优先精读的 world model 工作。",
                    "problem": "解决什么问题",
                    "method": "方法概述",
                    "result": "关键结果",
                    "importance": "为什么重要",
                    "reading_level": "必读",
                    "detail_link": "[阅读笔记](#mvista-4d)",
                }
            ],
        },
    )

    assert "# 2026-03-20 论文推荐" in content
    assert "本期导读" in content
    assert "MVISTA-4D" in content
    assert "阅读笔记" in content
    assert "核心图" in content


def test_render_paper_digest_template_falls_back_to_date_title() -> None:
    content = render_report_template(
        report_type="paper",
        version="v1",
        context={
            "paper_mode": "digest",
            "date": "2026-03-20",
            "papers": [],
        },
    )

    assert "# 2026-03-20 论文推荐" in content


def test_render_paper_note_template() -> None:
    content = render_report_template(
        report_type="paper",
        version="v1",
        context={
            "paper_mode": "note",
            "date": "2026-03-20",
            "title": "MVISTA-4D",
            "authors": "Jiaxu Wang et al.",
            "affiliations": "The Chinese University of Hong Kong",
            "links": ["arXiv", "PDF"],
            "summary": "单篇论文的详细阅读笔记。",
            "contributions": ["贡献 1", "贡献 2"],
            "method_details": ["方法细节 1"],
            "figure_notes": ["图 1 解读"],
            "experiments": ["实验结论"],
            "interpretation": ["我的理解"],
            "limitations": ["局限与疑问"],
            "use_cases": ["适用场景"],
            "related_reading": ["相关论文"],
        },
    )

    assert "论文定位" in content
    assert "核心贡献" in content
    assert "方法拆解" in content
    assert "局限与疑问" in content


def test_render_paper_notion_sink_digest_and_note_modes() -> None:
    digest = render_sink_report_template(
        sink="notion",
        report_type="paper",
        version="v1",
        context={"paper_mode": "digest", "content": "digest body"},
    )
    note = render_sink_report_template(
        sink="notion",
        report_type="paper",
        version="v1",
        context={"metadata": {"paper_mode": "note"}, "content": "note body"},
    )

    assert digest == "digest body"
    assert note == "note body"
