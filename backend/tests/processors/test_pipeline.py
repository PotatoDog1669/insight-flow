from __future__ import annotations

import pytest

from app.collectors.base import RawArticle
from app.processors.pipeline import ProcessingPipeline


@pytest.mark.asyncio
async def test_pipeline_filters_dedups_and_scores() -> None:
    raw_items = [
        RawArticle(
            external_id="1",
            title="OpenAI 发布新模型",
            url="https://example.com/a1",
            content="This AI model improves reasoning and coding performance significantly.",
        ),
        RawArticle(
            external_id="2",
            title="OpenAI 发布新模型",
            url="https://example.com/a1-dup",
            content="Duplicate entry with similar information.",
        ),
        RawArticle(
            external_id="3",
            title="Cooking recipe of the day",
            url="https://example.com/other",
            content="How to cook pasta with tomato sauce.",
        ),
    ]

    pipeline = ProcessingPipeline(score_threshold=0.3)
    processed = await pipeline.process(raw_items)

    assert len(processed) == 1
    item = processed[0]
    assert item.raw.external_id == "1"
    assert item.summary
    assert item.keywords
    assert item.score >= 0.3
