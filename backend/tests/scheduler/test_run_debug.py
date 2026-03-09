from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.collectors.base import RawArticle
from app.scheduler import run_debug


def test_build_article_log_items_keeps_safe_debug_fields() -> None:
    items = run_debug.build_article_log_items(
        [
            RawArticle(
                external_id="article-1",
                title="GPT-5.3 Instant System Card",
                url="https://openai.com/index/gpt-5-3-instant-system-card",
                content="very long raw content that should never be exposed in UI logs",
                published_at=datetime(2026, 3, 7, 10, 0, tzinfo=timezone.utc),
                metadata={
                    "source_name": "OpenAI",
                    "source_id": "source-openai",
                    "debug_file": "raw/001_gpt53.txt",
                },
            )
        ],
        reason="collected",
    )

    assert items == [
        {
            "title": "GPT-5.3 Instant System Card",
            "source_name": "OpenAI",
            "source_id": "source-openai",
            "url": "https://openai.com/index/gpt-5-3-instant-system-card",
            "external_id": "article-1",
            "published_at": "2026-03-07T10:00:00+00:00",
            "debug_file": "raw/001_gpt53.txt",
            "reason": "collected",
        }
    ]


def test_write_run_debug_artifact_creates_expected_json_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(run_debug, "RUN_ARTIFACT_DIR", tmp_path)

    path = run_debug.write_run_debug_artifact(
        run_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        source_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        filename="03_pipeline_filter_kept.json",
        payload=[{"title": "GPT-5.3 Instant"}],
    )

    assert path == "output/run_artifacts/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/source_bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/03_pipeline_filter_kept.json"
    artifact = tmp_path / "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" / "source_bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" / "03_pipeline_filter_kept.json"
    assert json.loads(artifact.read_text(encoding="utf-8")) == [{"title": "GPT-5.3 Instant"}]
