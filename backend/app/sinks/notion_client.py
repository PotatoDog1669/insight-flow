"""Helpers for Notion page creation and block chunking."""

from __future__ import annotations


NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
NOTION_BLOCK_LIMIT = 100
NOTION_RICHTEXT_CHAR_LIMIT = 2000

# Rate-limit / retry constants
NOTION_MAX_RETRIES = 3
NOTION_DEFAULT_RETRY_AFTER = 1.0  # seconds, fallback when Retry-After header missing
NOTION_REQUEST_INTERVAL = 0.34  # ~3 req/s (1/3 ≈ 0.333s), slight margin


def markdown_to_paragraph_blocks(markdown: str) -> list[dict]:
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    if not lines:
        lines = ["(empty)"]

    blocks: list[dict] = []
    for line in lines:
        text = line
        while text:
            chunk = text[:NOTION_RICHTEXT_CHAR_LIMIT]
            text = text[NOTION_RICHTEXT_CHAR_LIMIT:]
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": chunk},
                            }
                        ]
                    },
                }
            )
    return blocks


def chunk_blocks(blocks: list[dict], chunk_size: int = NOTION_BLOCK_LIMIT) -> list[list[dict]]:
    return [blocks[idx : idx + chunk_size] for idx in range(0, len(blocks), chunk_size)]
