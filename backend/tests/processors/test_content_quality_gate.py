from __future__ import annotations

from app.collectors.base import RawArticle
from app.processors.content_quality_gate import is_low_information_detail, is_weak_social_input


def test_is_weak_social_input_detects_short_text_plus_link() -> None:
    article = RawArticle(
        external_id="social-1",
        title="A statement from Anthropic CEO Dario Amodei: https://t.co/test",
        url="https://x.com/example/status/1",
        content="A statement from Anthropic CEO Dario Amodei: https://t.co/test",
        metadata={"source_category": "social", "source_name": "X"},
    )

    assert is_weak_social_input(article) is True


def test_is_low_information_detail_flags_placeholder_heavy_text() -> None:
    detail = "具体内容：未知。影响范围：待定。暂无信息，需等待更多信源。"

    assert is_low_information_detail(detail) is True
