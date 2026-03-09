from __future__ import annotations

from app.sinks.notion_client import markdown_to_paragraph_blocks


def _extract_block_types(blocks: list[dict]) -> list[str]:
    return [str(block.get("type", "")) for block in blocks]


def _collect_text_fragments(block: dict) -> list[str]:
    block_type = str(block.get("type", ""))
    payload = block.get(block_type, {})
    if block_type == "table":
        fragments: list[str] = []
        for row in payload.get("children", []):
            for cell in row.get("table_row", {}).get("cells", []):
                for rich in cell:
                    fragments.append(str(rich.get("text", {}).get("content", "")))
        return fragments
    return [
        str(item.get("text", {}).get("content", ""))
        for item in payload.get("rich_text", [])
    ]


def test_markdown_to_paragraph_blocks_converts_core_block_types() -> None:
    markdown = """# 主标题

## 小节
- **重点项** [原文](https://example.com)
1. `code` check
---
普通段落
"""
    blocks = markdown_to_paragraph_blocks(markdown)

    assert _extract_block_types(blocks) == [
        "heading_1",
        "heading_2",
        "bulleted_list_item",
        "numbered_list_item",
        "divider",
        "paragraph",
    ]

    bullet_rich = blocks[2]["bulleted_list_item"]["rich_text"]
    assert any(item.get("annotations", {}).get("bold") for item in bullet_rich)
    assert any(item.get("text", {}).get("link", {}).get("url") == "https://example.com" for item in bullet_rich)


def test_markdown_to_paragraph_blocks_converts_markdown_table() -> None:
    markdown = """| 项目 | 指标 | 状态 |
| --- | --- | --- |
| Gemini 3.1 Flash-Lite | 输入 $0.25/M | 预览 |
| Shannon Lite | 96.15% | 开源 |
"""
    blocks = markdown_to_paragraph_blocks(markdown)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "table"
    assert blocks[0]["table"]["table_width"] == 3
    assert blocks[0]["table"]["has_column_header"] is True
    assert len(blocks[0]["table"]["children"]) == 3
    first_data_row_cells = blocks[0]["table"]["children"][1]["table_row"]["cells"]
    assert first_data_row_cells[0][0]["text"]["content"] == "Gemini 3.1 Flash-Lite"


def test_markdown_to_paragraph_blocks_unescapes_markdown_tokens_before_parse() -> None:
    markdown = """\\*\\*事件概览\\*\\*

\\| 模型 \\| 状态 \\|
\\| --- \\| --- \\|
\\| GPT-5.3 Instant \\| rollout \\|
"""
    blocks = markdown_to_paragraph_blocks(markdown)

    assert _extract_block_types(blocks) == ["paragraph", "table"]

    paragraph_rich = blocks[0]["paragraph"]["rich_text"]
    assert any(item.get("annotations", {}).get("bold") for item in paragraph_rich)
    assert any(item.get("text", {}).get("content") == "事件概览" for item in paragraph_rich)

    text_fragments = []
    for block in blocks:
        text_fragments.extend(_collect_text_fragments(block))
    assert all("\\" not in fragment for fragment in text_fragments)


def test_markdown_to_paragraph_blocks_maps_heading_level_4_to_heading_3() -> None:
    markdown = "#### 深层小节"
    blocks = markdown_to_paragraph_blocks(markdown)

    assert _extract_block_types(blocks) == ["heading_3"]
    rich_text = blocks[0]["heading_3"]["rich_text"]
    assert rich_text[0]["text"]["content"] == "深层小节"
