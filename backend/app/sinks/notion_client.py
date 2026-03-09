"""Helpers for Notion page creation and block chunking."""

from __future__ import annotations

import re


NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
NOTION_BLOCK_LIMIT = 100
NOTION_RICHTEXT_CHAR_LIMIT = 2000

# Rate-limit / retry constants
NOTION_MAX_RETRIES = 3
NOTION_DEFAULT_RETRY_AFTER = 1.0  # seconds, fallback when Retry-After header missing
NOTION_REQUEST_INTERVAL = 0.34  # ~3 req/s (1/3 ≈ 0.333s), slight margin

_ESCAPED_MARKDOWN_TOKEN_PATTERN = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|])")
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLETED_LIST_PATTERN = re.compile(r"^[-*+]\s+(.*)$")
_NUMBERED_LIST_PATTERN = re.compile(r"^\d+[.)]\s+(.*)$")
_DIVIDER_PATTERN = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")
_TABLE_SEPARATOR_PATTERN = re.compile(r"^\|?\s*:?-{3,}:?(?:\s*\|\s*:?-{3,}:?)*\s*\|?$")
_QUOTE_PATTERN = re.compile(r"^>\s+(.*)$")
_INLINE_MARKDOWN_PATTERN = re.compile(
    r"\[([^\]]+)\]\((https?://[^\s)]+)\)|"  # 1=link, 2=url
    r"\*\*([^*]+)\*\*|"                    # 3=bold
    r"(?<!\*)\*([^*]+)\*(?!\*)|"           # 4=italic
    r"`([^`]+)`"                           # 5=code
)


def markdown_to_paragraph_blocks(markdown: str) -> list[dict]:
    normalized = _normalize_markdown(markdown)
    lines = [line.rstrip() for line in normalized.splitlines()]
    if not any(line.strip() for line in lines):
        lines = ["(empty)"]
    blocks: list[dict] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue

        table_block, next_idx = _parse_table_block(lines, idx)
        if table_block is not None:
            blocks.append(table_block)
            idx = next_idx
            continue

        if _DIVIDER_PATTERN.match(line):
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            idx += 1
            continue

        heading_match = _HEADING_PATTERN.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            blocks.append(_make_heading_block(level=level, text=heading_match.group(2).strip()))
            idx += 1
            continue

        bullet_match = _BULLETED_LIST_PATTERN.match(line)
        if bullet_match:
            blocks.append(_make_text_block("bulleted_list_item", bullet_match.group(1).strip()))
            idx += 1
            continue

        numbered_match = _NUMBERED_LIST_PATTERN.match(line)
        if numbered_match:
            blocks.append(_make_text_block("numbered_list_item", numbered_match.group(1).strip()))
            idx += 1
            continue

        quote_match = _QUOTE_PATTERN.match(line)
        if quote_match:
            blocks.append(_make_text_block("quote", quote_match.group(1).strip()))
            idx += 1
            continue

        blocks.append(_make_text_block("paragraph", line))
        idx += 1
    return blocks


def chunk_blocks(blocks: list[dict], chunk_size: int = NOTION_BLOCK_LIMIT) -> list[list[dict]]:
    return [blocks[idx : idx + chunk_size] for idx in range(0, len(blocks), chunk_size)]


def _normalize_markdown(markdown: str) -> str:
    normalized_newlines = str(markdown or "").replace("\r\n", "\n").replace("\r", "\n")
    return _ESCAPED_MARKDOWN_TOKEN_PATTERN.sub(r"\1", normalized_newlines)


def _make_heading_block(*, level: int, text: str) -> dict:
    block_type = f"heading_{max(1, min(level, 3))}"
    rich_text = _parse_inline_markdown(text)
    payload = {block_type: {"rich_text": rich_text}}
    return {"object": "block", "type": block_type, **payload}


def _make_text_block(block_type: str, text: str) -> dict:
    rich_text = _parse_inline_markdown(text)
    return {"object": "block", "type": block_type, block_type: {"rich_text": rich_text}}


def _parse_inline_markdown(text: str) -> list[dict]:
    if not text:
        return []
    rich_text: list[dict] = []
    cursor = 0
    for match in _INLINE_MARKDOWN_PATTERN.finditer(text):
        if match.start() > cursor:
            rich_text.extend(_to_plain_text(text[cursor : match.start()]))
        link_title = match.group(1)
        link_url = match.group(2)
        bold_text = match.group(3)
        italic_text = match.group(4)
        code_text = match.group(5)
        if link_title and link_url:
            rich_text.extend(_to_plain_text(link_title, link=link_url))
        elif bold_text is not None:
            rich_text.extend(_to_plain_text(bold_text, bold=True))
        elif italic_text is not None:
            rich_text.extend(_to_plain_text(italic_text, italic=True))
        elif code_text is not None:
            rich_text.extend(_to_plain_text(code_text, code=True))
        cursor = match.end()
    if cursor < len(text):
        rich_text.extend(_to_plain_text(text[cursor:]))
    return rich_text


def _to_plain_text(
    content: str,
    *,
    bold: bool = False,
    italic: bool = False,
    code: bool = False,
    link: str | None = None,
) -> list[dict]:
    if not content:
        return []
    rich_text: list[dict] = []
    remaining = content
    while remaining:
        chunk = remaining[:NOTION_RICHTEXT_CHAR_LIMIT]
        remaining = remaining[NOTION_RICHTEXT_CHAR_LIMIT:]
        text_payload: dict = {"content": chunk}
        if link:
            text_payload["link"] = {"url": link}
        text_chunk: dict = {"type": "text", "text": text_payload}
        if bold or code or italic:
            text_chunk["annotations"] = _annotations(bold=bold, code=code, italic=italic)
        rich_text.append(text_chunk)
    return rich_text


def _annotations(*, bold: bool = False, code: bool = False, italic: bool = False) -> dict:
    return {
        "bold": bold,
        "italic": italic,
        "strikethrough": False,
        "underline": False,
        "code": code,
        "color": "default",
    }


def _parse_table_block(lines: list[str], idx: int) -> tuple[dict | None, int]:
    if idx + 1 >= len(lines):
        return None, idx
    header_line = lines[idx].strip()
    separator_line = lines[idx + 1].strip()
    if not _is_table_row(header_line):
        return None, idx
    if not _TABLE_SEPARATOR_PATTERN.match(separator_line):
        return None, idx

    header_cells = _split_table_cells(header_line)
    if len(header_cells) < 2:
        return None, idx

    width = len(header_cells)
    rows: list[list[str]] = [header_cells]
    next_idx = idx + 2
    while next_idx < len(lines):
        row_line = lines[next_idx].strip()
        if not row_line:
            break
        if not _is_table_row(row_line):
            break
        row_cells = _split_table_cells(row_line)
        if len(row_cells) < 2:
            break
        rows.append(_normalize_table_row(row_cells, width))
        next_idx += 1

    return _make_table_block(rows=rows, width=width), next_idx


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return stripped.count("|") >= 2


def _split_table_cells(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _normalize_table_row(cells: list[str], width: int) -> list[str]:
    normalized = cells[:width]
    while len(normalized) < width:
        normalized.append("")
    return normalized


def _make_table_block(*, rows: list[list[str]], width: int) -> dict:
    children = [_make_table_row(row=row, width=width) for row in rows]
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "has_row_header": False,
            "children": children,
        },
    }


def _make_table_row(*, row: list[str], width: int) -> dict:
    normalized_row = _normalize_table_row(row, width)
    cells = [_parse_inline_markdown(cell) for cell in normalized_row]
    return {
        "object": "block",
        "type": "table_row",
        "table_row": {"cells": cells},
    }
