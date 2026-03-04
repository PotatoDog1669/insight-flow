from __future__ import annotations

from app.utils.notion_ids import extract_notion_id


def test_extract_notion_id_returns_compact_id_for_raw_id() -> None:
    raw = "3170dd92-84fc-805c-a19b-fd4a76db602e"
    assert extract_notion_id(raw) == "3170dd9284fc805ca19bfd4a76db602e"


def test_extract_notion_id_parses_database_url_with_view_query() -> None:
    url = "https://www.notion.so/3170dd9284fc805ca19bfd4a76db602e?v=3170dd9284fc80f6a693000c0b36598f&source=copy_link"
    assert extract_notion_id(url) == "3170dd9284fc805ca19bfd4a76db602e"


def test_extract_notion_id_parses_slug_url() -> None:
    url = "https://www.notion.so/workspace/Morning-Briefing-Center-3170dd9284fc805ca19bfd4a76db602e?pvs=4"
    assert extract_notion_id(url) == "3170dd9284fc805ca19bfd4a76db602e"


def test_extract_notion_id_returns_none_for_invalid_input() -> None:
    assert extract_notion_id("not-a-notion-id") is None
