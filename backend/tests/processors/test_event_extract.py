from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.collectors.base import RawArticle
from app.processors.event_extract import build_event_extraction_inputs
from app.processors.event_models import CandidateCluster
from app.processors.pipeline import ProcessingPipeline


def test_build_event_extraction_inputs_selects_primary_and_supporting_articles() -> None:
    cluster = CandidateCluster(
        cluster_id="cluster-1",
        articles=[
            RawArticle(
                external_id="social",
                title="GPT-5 发布了",
                url="https://x.com/openai/status/1",
                content="short",
                metadata={"source_category": "social"},
            ),
            RawArticle(
                external_id="blog",
                title="OpenAI 发布 GPT-5",
                url="https://openai.com/blog/gpt-5",
                content="long long long details",
                metadata={"source_category": "blog"},
            ),
        ],
    )

    result = build_event_extraction_inputs([cluster])

    assert len(result) == 1
    assert result[0].primary_article.external_id == "blog"
    assert [item.external_id for item in result[0].supporting_articles] == ["social"]


@pytest.mark.asyncio
async def test_run_event_extract_stage_emits_one_event_per_cluster(monkeypatch: pytest.MonkeyPatch) -> None:
    class _KeywordsProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            event_input = payload["event_input"]
            assert event_input.primary_article.external_id == "blog"
            return {
                "event_title": "OpenAI 发布 GPT-5",
                "keywords": ["OpenAI", "GPT-5"],
                "summary": "OpenAI 发布 GPT-5。",
                "importance": "high",
                "category": "模型发布",
                "detail": "OpenAI 发布 GPT-5，并说明其推理与代码能力进一步提升。",
                "who": "OpenAI",
                "what": "发布 GPT-5",
                "when": "2026-03-06",
                "metrics": ["30%"],
                "availability": "公开可用",
                "unknowns": "",
                "evidence": "主博客与配套来源交叉验证",
            }

    def fake_get_provider(stage: str, name: str):  # noqa: ANN201
        assert stage == "keywords"
        return _KeywordsProvider()

    monkeypatch.setattr("app.processors.pipeline.get_provider", fake_get_provider)

    pipeline = ProcessingPipeline(routing_profile="stable_v1")
    clusters = [
        CandidateCluster(
            cluster_id="cluster-1",
            articles=[
                RawArticle(
                    external_id="social",
                    title="GPT-5 发布了",
                    url="https://x.com/openai/status/1",
                    content="short",
                    published_at=datetime(2026, 3, 6, 10, 0, tzinfo=timezone.utc),
                    metadata={"source_category": "social", "source_name": "OpenAI X"},
                ),
                RawArticle(
                    external_id="blog",
                    title="OpenAI 发布 GPT-5",
                    url="https://openai.com/blog/gpt-5",
                    content="long long long details",
                    published_at=datetime(2026, 3, 6, 10, 0, tzinfo=timezone.utc),
                    metadata={"source_category": "blog", "source_name": "OpenAI"},
                ),
            ],
        )
    ]

    events, trace = await pipeline.run_event_extract_stage(clusters)

    assert len(events) == 1
    assert events[0].title == "OpenAI 发布 GPT-5"
    assert events[0].article_ids == ["social", "blog"]
    assert events[0].source_links == ["https://x.com/openai/status/1", "https://openai.com/blog/gpt-5"]
    assert trace["output"] == 1
