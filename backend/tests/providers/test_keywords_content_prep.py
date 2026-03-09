from __future__ import annotations

from app.collectors.base import RawArticle
from app.processors.event_models import CandidateCluster, EventExtractionInput
from app.providers.keywords import _event_input_to_prompt_article, _extract_summary, _prepare_content_for_prompt


def test_prepare_content_for_prompt_removes_navigation_noise() -> None:
    raw = """
Title: Gemini 3.1 Flash-Lite
URL Source: https://deepmind.google/blog/abc
Published Time: 2026-03-03T16:34:00+00:00

Markdown Content:
[Skip to main content](https://deepmind.google/#jump-content)
[Home](https://deepmind.google/)
Share
Gemini 3.1 Flash-Lite is our most cost-effective model yet.
It improves latency by 28% in internal tests while keeping quality stable.
[See all](https://deepmind.google/innovation-and-ai/)
"""

    prepared = _prepare_content_for_prompt(raw)

    assert "Skip to main content" not in prepared
    assert "See all" not in prepared
    assert "most cost-effective model yet" in prepared
    assert "latency by 28%" in prepared


def test_prepare_content_for_prompt_limits_output_length() -> None:
    raw = "line with useful context " * 2000
    prepared = _prepare_content_for_prompt(raw)
    assert len(prepared) <= 4000


def test_prepare_content_for_prompt_removes_image_and_html_fragments() -> None:
    raw = """
![badge](https://img.shields.io/badge/test-green.svg)
<img src="https://example.com/banner.png" alt="banner" />
Core update: model latency improved by 35% in production traffic.
"""
    prepared = _prepare_content_for_prompt(raw)

    assert "img.shields.io" not in prepared
    assert "<img" not in prepared
    assert "latency improved by 35%" in prepared


def test_prepare_content_for_prompt_removes_markdown_image_clusters() -> None:
    raw = """
![Vital Signs](#vital-sign-detection) ![ESP32 Ready](#esp32-s3-hardware-pipeline)
| What | How | Speed |
The project uses CSI signals to estimate pose and breathing in real time.
"""
    prepared = _prepare_content_for_prompt(raw)

    assert "Vital Signs" not in prepared
    assert "| What | How | Speed |" not in prepared
    assert "estimate pose and breathing" in prepared


def test_extract_summary_prefers_informative_text_over_social_noise() -> None:
    article = type("Article", (), {})()
    article.title = "Gemini 3.1 Flash-Lite"
    article.content = """
Markdown Content:
x.comFacebookLinkedInMail
Gemini 3.1 Flash-Lite is our most cost-effective model yet.
In internal evaluations, Gemini 3.1 Flash-Lite latency improved by 28% while quality remained stable.
"""

    summary = _extract_summary(article)

    assert "x.comFacebookLinkedInMail" not in summary
    assert "latency improved by 28%" in summary


def test_extract_summary_prefers_sentence_aligned_with_title_topic() -> None:
    article = type("Article", (), {})()
    article.title = "GPT-5.3 Instant: Smoother conversations"
    article.content = """
Markdown Content:
Quick physics primer: for a 300m throw, drag matters and textbook equations break.
GPT-5.3 Instant improves conversational flow and web-grounded answer quality in ChatGPT.
"""

    summary = _extract_summary(article)

    assert "GPT-5.3 Instant" in summary


def test_extract_summary_handles_unicode_dash_for_title_alignment() -> None:
    article = type("Article", (), {})()
    article.title = "GPT-5.3 Instant: Smoother conversations"
    article.content = """
Markdown Content:
With air resistance, textbook equations can fail at long range.
GPT‑5.3 Instant improves conversational flow and answer quality for ChatGPT users.
"""

    summary = _extract_summary(article)

    assert "GPT‑5.3 Instant" in summary or "GPT-5.3 Instant" in summary


def test_event_input_to_prompt_article_combines_primary_and_supporting_sources() -> None:
    event_input = EventExtractionInput(
        cluster=CandidateCluster(
            cluster_id="cluster-1",
            articles=[],
        ),
        primary_article=RawArticle(
            external_id="primary",
            title="OpenAI 发布 GPT-5",
            url="https://openai.com/blog/gpt-5",
            content="OpenAI 发布 GPT-5，并解释其推理与代码能力提升。",
        ),
        supporting_articles=[
            RawArticle(
                external_id="support-1",
                title="GPT-5 launch coverage",
                url="https://news.example.com/gpt-5",
                content="媒体补充了发布时间与可用范围。",
            )
        ],
    )

    prompt_article = _event_input_to_prompt_article(event_input)

    assert prompt_article.title == "OpenAI 发布 GPT-5"
    assert "Primary Source" in prompt_article.content
    assert "Supporting Source 1" in prompt_article.content
    assert "媒体补充了发布时间与可用范围" in prompt_article.content
