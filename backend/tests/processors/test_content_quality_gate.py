from __future__ import annotations

from app.collectors.base import RawArticle
from app.processors.content_quality_gate import apply_content_quality_gate, is_low_information_detail, is_weak_social_input
from app.processors.pipeline import ProcessedArticle


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


def test_apply_content_quality_gate_builds_brief_for_short_social_product_launch() -> None:
    article = ProcessedArticle(
        raw=RawArticle(
            external_id="social-launch-1",
            title="Comet is now available for iOS.",
            url="https://x.com/perplexity_ai/status/1",
            content="Comet is now available for iOS.\nDownload on the App Store: https://apps.apple.com/us/app/comet-a/id123",
            metadata={
                "source_category": "social",
                "source_name": "X",
                "author_name": "Perplexity",
                "author_username": "perplexity_ai",
            },
        ),
        event_title="Comet推出iOS版本",
        summary="Comet 已上线 iOS 平台。",
    )

    gated = apply_content_quality_gate(article)

    assert gated.detail_mode == "compact"
    assert gated.detail == (
        "Perplexity 宣布旗下 Comet 已上线 iOS，用户现可通过 App Store 下载。"
        "原帖确认了 iOS 版本已可用，但具体功能范围、开放地区与定价细节尚未说明。"
    )
