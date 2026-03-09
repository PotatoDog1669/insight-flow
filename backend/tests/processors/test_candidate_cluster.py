from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.collectors.base import RawArticle
from app.processors.candidate_cluster import build_candidate_clusters, select_primary_article


def test_build_candidate_clusters_groups_similar_model_release_articles() -> None:
    articles = [
        RawArticle(
            external_id="a1",
            title="OpenAI 发布 GPT-5 reasoning 模型",
            url="https://openai.com/blog/gpt-5",
            content="GPT-5 reasoning improves coding quality and latency.",
            published_at=datetime(2026, 3, 6, 10, 0, tzinfo=timezone.utc),
            metadata={"source_id": "openai-blog", "source_name": "OpenAI", "source_category": "blog"},
        ),
        RawArticle(
            external_id="a2",
            title="GPT-5 launch: OpenAI ships new reasoning model",
            url="https://news.example.com/openai-gpt5",
            content="OpenAI ships GPT-5 with stronger reasoning and lower latency.",
            published_at=datetime(2026, 3, 6, 11, 0, tzinfo=timezone.utc),
            metadata={"source_id": "news-site", "source_name": "News Site", "source_category": "blog"},
        ),
        RawArticle(
            external_id="a3",
            title="Cursor 发布新的代码补全体验",
            url="https://cursor.com/blog/new-completion",
            content="Cursor ships a new coding workflow update.",
            published_at=datetime(2026, 3, 6, 11, 0, tzinfo=timezone.utc),
            metadata={"source_id": "cursor-blog", "source_name": "Cursor", "source_category": "blog"},
        ),
    ]

    clusters = build_candidate_clusters(articles)

    assert len(clusters) == 2
    assert len(clusters[0].articles) == 2
    assert len(clusters[1].articles) == 1


def test_build_candidate_clusters_keeps_far_apart_articles_separate() -> None:
    articles = [
        RawArticle(
            external_id="a1",
            title="OpenAI 发布 GPT-5",
            url="https://openai.com/blog/gpt-5",
            content="OpenAI releases GPT-5.",
            published_at=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
        ),
        RawArticle(
            external_id="a2",
            title="OpenAI 发布 GPT-5",
            url="https://news.example.com/openai-gpt5-retro",
            content="Retrospective on GPT-5 launch.",
            published_at=datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc) + timedelta(days=3),
        ),
    ]

    clusters = build_candidate_clusters(articles)

    assert len(clusters) == 2


def test_select_primary_article_prefers_blog_then_longer_content() -> None:
    cluster = build_candidate_clusters(
        [
            RawArticle(
                external_id="social",
                title="GPT-5 发布了",
                url="https://x.com/openai/status/1",
                content="short",
                published_at=datetime(2026, 3, 6, 10, 0, tzinfo=timezone.utc),
                metadata={"source_id": "openai-x", "source_name": "OpenAI X", "source_category": "social"},
            ),
            RawArticle(
                external_id="blog",
                title="OpenAI 发布 GPT-5",
                url="https://openai.com/blog/gpt-5",
                content="long long long details",
                published_at=datetime(2026, 3, 6, 10, 0, tzinfo=timezone.utc),
                metadata={"source_id": "openai-blog", "source_name": "OpenAI", "source_category": "blog"},
            ),
        ]
    )[0]

    primary = select_primary_article(cluster)

    assert primary.external_id == "blog"


def test_build_candidate_clusters_keeps_distinct_claude_announcements_separate() -> None:
    articles = [
        RawArticle(
            external_id="claude-46",
            title="Feb 17, 2026 Product Introducing Claude Sonnet 4.6",
            url="https://anthropic.com/news/claude-sonnet-4-6",
            content="Claude Sonnet 4.6 improves coding and reasoning reliability.",
            published_at=datetime(2026, 2, 17, 10, 0, tzinfo=timezone.utc),
            metadata={"source_id": "anthropic", "source_name": "Anthropic", "source_category": "blog"},
        ),
        RawArticle(
            external_id="claude-adfree",
            title="Announcements Feb 4, 2026 Claude is a space to think",
            url="https://anthropic.com/news/claude-is-a-space-to-think",
            content="Claude will remain ad-free and expand access without compromising trust.",
            published_at=datetime(2026, 2, 17, 12, 0, tzinfo=timezone.utc),
            metadata={"source_id": "anthropic", "source_name": "Anthropic", "source_category": "blog"},
        ),
    ]

    clusters = build_candidate_clusters(articles)

    assert len(clusters) == 2


def test_build_candidate_clusters_ignores_content_only_overlap_for_distinct_titles() -> None:
    articles = [
        RawArticle(
            external_id="seed-llm",
            title="LLM",
            url="https://seed.bytedance.com/zh/direction/llm",
            content="Research on language agents, infrastructure, reasoning, and model quality.",
            published_at=datetime(2026, 3, 4, 10, 0, tzinfo=timezone.utc),
            metadata={"source_id": "seed", "source_name": "字节跳动 Seed", "source_category": "blog"},
        ),
        RawArticle(
            external_id="seed-rai",
            title="Responsible AI",
            url="https://seed.bytedance.com/zh/direction/responsible_ai",
            content="Research on infrastructure, reasoning, safety, and model quality.",
            published_at=datetime(2026, 3, 4, 11, 0, tzinfo=timezone.utc),
            metadata={"source_id": "seed", "source_name": "字节跳动 Seed", "source_category": "blog"},
        ),
        RawArticle(
            external_id="hf-paper",
            title="Classroom Final Exam: An Instructor-Tested Reasoning Benchmark",
            url="https://huggingface.co/papers/2602.19517",
            content="This benchmark evaluates language models and reasoning step efficiency.",
            published_at=datetime(2026, 3, 4, 12, 0, tzinfo=timezone.utc),
            metadata={"source_id": "hf", "source_name": "Hugging Face Daily Papers", "source_category": "academic"},
        ),
    ]

    clusters = build_candidate_clusters(articles)

    assert len(clusters) == 3
