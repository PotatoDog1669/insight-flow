from __future__ import annotations

import re

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
            "properties": [
                {"label": "date", "value": "2026-03-20"},
                {"label": "keywords", "value": "world model, robotics"},
                {"label": "tags", "value": "daily-papers, auto-generated"},
            ],
            "theme_groups": [
                {
                    "title": "World Model",
                    "papers": [
                        {
                            "title": "MVISTA-4D",
                            "authors": "Jiaxu Wang et al.",
                            "affiliations": "The Chinese University of Hong Kong",
                            "figure": "https://example.com/figure.png",
                            "one_line_judgment": "值得优先精读的 world model 工作。",
                            "core_problem": "这篇先把多视角时空建模里最难的对齐问题讲清楚了。",
                            "core_method": "方法概述",
                            "key_result": "关键结果",
                            "why_it_matters": "为什么重要",
                            "reading_advice": "建议先看问题设定，再看实验里的泛化边界。",
                            "recommendation": "必读",
                            "source_label": "arXiv",
                            "links": [
                                {"label": "Abs", "url": "https://arxiv.org/abs/2603.12345"},
                                {"label": "HTML", "url": "https://arxiv.org/html/2603.12345"},
                            ],
                        }
                    ],
                }
            ],
        },
    )

    assert content.startswith("---\n")
    assert "date: 2026-03-20" in content
    assert "keywords:" in content
    assert "tags:" in content
    assert "# 2026-03-20 论文推荐" in content
    assert content.count("# 2026-03-20 论文推荐") == 1
    assert "## Properties" not in content
    assert "| date | 2026-03-20 |" not in content
    assert "## 总结" in content
    assert "## World Model" in content
    assert "MVISTA-4D" in content
    assert "![MVISTA-4D](https://example.com/figure.png)" in content
    assert "- 核心图：" not in content
    assert "- 笔记：" not in content
    assert "- 详细笔记：" not in content
    assert "- 推荐级别：" not in content
    assert "- 作者：Jiaxu Wang et al." in content
    assert "- 来源：arXiv" in content
    assert re.search(r"- 链接：\[Abs\]\(https://arxiv\.org/abs/2603\.12345\) / \[HTML\]\(https://arxiv\.org/html/2603\.12345\)", content)
    assert "**核心方法**" in content
    assert "这篇先把多视角时空建模里最难的对齐问题讲清楚了。" in content
    assert "方法概述" in content
    assert "**对比方法 / Baselines**" in content
    assert "关键结果" in content
    assert "**借鉴意义**" in content
    assert "为什么重要" in content
    assert "**阅读建议**" in content
    assert "值得优先精读的 world model 工作。" in content
    assert "建议先看问题设定，再看实验里的泛化边界。" in content


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

    assert content.startswith("---\n")
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
            "core_contributions": ["贡献 1", "贡献 2"],
            "problem_background": [
                "要解决复杂场景下的世界模型一致性问题。",
                "现有方法难以保证多视角与时间维度的一致建模。",
            ],
            "method_breakdown": ["方法细节 1"],
            "figure_notes": [
                "### Figure 1: Overview\n\n![Overview](https://example.com/figure.png)\n\n图示说明：整体框架。",
            ],
            "experiments": ["实验结论"],
            "strengths": ["优点 1"],
            "limitations": ["局限与疑问"],
            "next_steps": ["后续阅读 1"],
            "related_reading": ["相关论文"],
            "back_link": "[2026-03-20 论文推荐](/reports/digest-1)",
        },
    )

    assert "元信息" in content
    assert "| 标题 | MVISTA-4D |" in content
    assert "一句话总结" in content
    assert "核心贡献" in content
    assert "问题背景" in content
    assert "方法详解" in content
    assert "批判性思考" in content
    assert "后续阅读" in content
    assert "### Figure 1: Overview" in content
    assert "![Overview](https://example.com/figure.png)" in content
    assert "- ### Figure 1: Overview" not in content


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
