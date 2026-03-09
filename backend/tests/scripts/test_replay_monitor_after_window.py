from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import uuid

import pytest

from app.collectors.base import RawArticle
from app.processors.event_models import CandidateCluster, GlobalSummary, ProcessedEvent
from app.processors.pipeline import ProcessedArticle
from app.routing.schema import PublishRoute, RoutingProfile, RoutingStages, StageRoute


def _load_replay_script():  # noqa: ANN202
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "replay_monitor_after_window.py"
    spec = importlib.util.spec_from_file_location("replay_monitor_after_window_test", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


replay_script = _load_replay_script()


def _write_article_file(
    *,
    base_dir: Path,
    folder: str,
    index: int,
    title: str,
    external_id: str,
    published_at: str,
    content: str,
) -> str:
    target = base_dir / folder / f"{index:03d}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "\n".join(
            [
                f"title: {title}",
                "url: https://example.com/item",
                f"external_id: {external_id}",
                f"published_at: {published_at}",
                "source_name: Replay Source",
                f"source_id: {uuid.UUID('11111111-1111-1111-1111-111111111111')}",
                "extractor: rss",
                "",
                replay_script.FULL_CONTENT_MARKER,
                "",
                content,
            ]
        ),
        encoding="utf-8",
    )
    return str(target.relative_to(base_dir))


def _make_export_dir(tmp_path: Path) -> Path:
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    source_dir = export_dir / "01_replay_source_11111111"
    source_dir.mkdir()
    raw_rel = _write_article_file(
        base_dir=export_dir,
        folder="01_replay_source_11111111/raw",
        index=1,
        title="Replay Event",
        external_id="evt-1",
        published_at="2026-03-06T10:00:00+00:00",
        content="Full replay content with enough detail to survive the pipeline.",
    )
    after_window_rel = _write_article_file(
        base_dir=export_dir,
        folder="01_replay_source_11111111/after_window",
        index=1,
        title="Replay Event",
        external_id="evt-1",
        published_at="2026-03-06T10:00:00+00:00",
        content="Full replay content with enough detail to survive the pipeline.",
    )
    (source_dir / "_summary.json").write_text(
        json.dumps(
            {
                "source_id": "11111111-1111-1111-1111-111111111111",
                "source_name": "Replay Source",
                "collect_method": "rss",
                "source_category": "blog",
                "source_config": {"window_allow_first_seen_fallback": False},
                "collect_config": {"url": "https://example.com/rss"},
                "raw_count": 1,
                "after_window_count": 1,
                "raw_articles": [{"file": raw_rel}],
                "after_window_articles": [{"file": after_window_rel}],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (export_dir / "_run_summary.json").write_text(
        json.dumps(
            {
                "monitor_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "monitor_name": "Replay Monitor",
                "window_hours": 24,
                "window_start": "2026-03-05T12:00:00+00:00",
                "window_end": "2026-03-06T12:00:00+00:00",
                "output_dir": str(export_dir),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return export_dir


class _FakePipeline:
    call_counts = {
        "filter": 0,
        "candidate_cluster": 0,
        "keywords": 0,
        "event_extract": 0,
    }
    configured_stage_concurrency = 1

    @classmethod
    def reset_counts(cls) -> None:
        cls.call_counts = {
            "filter": 0,
            "candidate_cluster": 0,
            "keywords": 0,
            "event_extract": 0,
        }
        cls.configured_stage_concurrency = 1

    def __init__(self, routing_profile: str):
        self.routing_profile = RoutingProfile(
            name=routing_profile,
            stages=RoutingStages(
                collect=StageRoute(primary="rss"),
                filter=StageRoute(primary="rule"),
                keywords=StageRoute(primary="rule"),
                report=StageRoute(primary="agent_codex"),
                publish=PublishRoute(targets=[]),
            ),
            providers={},
        )
        self.last_stage_trace: dict[str, dict] = {}

    def set_provider_overrides(self, provider_overrides: dict[str, dict]) -> None:
        self.provider_overrides = provider_overrides

    def set_stage_concurrency(self, stage_concurrency: int) -> None:
        type(self).configured_stage_concurrency = stage_concurrency

    async def run_filter_stage(self, articles: list[RawArticle]) -> tuple[list[RawArticle], dict]:
        type(self).call_counts["filter"] += 1
        self.last_stage_trace["filter"] = {"provider": "rule", "input": len(articles), "output": len(articles)}
        return articles, self.last_stage_trace["filter"]

    async def run_candidate_cluster_stage(self, articles: list[RawArticle]) -> tuple[list[CandidateCluster], dict]:
        type(self).call_counts["candidate_cluster"] += 1
        clusters = [
            CandidateCluster(
                cluster_id="cluster-1",
                articles=articles,
                source_ids=["11111111-1111-1111-1111-111111111111"],
                source_names=["Replay Source"],
            )
        ]
        self.last_stage_trace["candidate_cluster"] = {
            "provider": "candidate_rule",
            "input": len(articles),
            "output": len(clusters),
        }
        return clusters, self.last_stage_trace["candidate_cluster"]

    async def run_keywords_stage(self, articles: list[RawArticle]) -> tuple[list[ProcessedArticle], dict]:
        type(self).call_counts["keywords"] += 1
        processed = [
            ProcessedArticle(
                raw=item,
                event_title="Replay Event",
                summary="Replay summary",
                keywords=["replay", "stage", "keywords"],
                detail="这是一段足够长的中文详情，用来验证阶段化回放的中间产物输出是否完整。",
                category="技术与洞察",
            )
            for item in articles
        ]
        self.last_stage_trace["keywords"] = {"provider": "rule", "input": len(articles), "output": len(processed)}
        return processed, self.last_stage_trace["keywords"]

    async def run_event_extract_stage(self, clusters: list[CandidateCluster]) -> tuple[list[ProcessedEvent], dict]:
        type(self).call_counts["event_extract"] += 1
        processed = [
            ProcessedEvent(
                event_id="event-1",
                title="Replay Event",
                summary="Replay event summary",
                detail="这是事件级提炼后的详情，用于验证 replay 输出的事件阶段产物。",
                article_ids=[item.external_id for item in cluster.articles],
                source_links=[item.url for item in cluster.articles],
                category="技术与洞察",
                keywords=["replay", "event"],
                source_count=len(cluster.articles),
                source_name="Replay Source",
                published_at=cluster.articles[0].published_at.isoformat() if cluster.articles else None,
                who="Replay Team",
                what="Replay Event",
                when="2026-03-06",
                metrics=["1 source"],
                availability="public",
                unknowns="",
                evidence="clustered replay evidence",
            )
            for cluster in clusters
        ]
        self.last_stage_trace["event_extract"] = {
            "provider": "rule",
            "input": len(clusters),
            "output": len(processed),
        }
        return processed, self.last_stage_trace["event_extract"]


def test_provider_overrides_from_user_settings_keeps_enabled_configs_and_sets_llm_timeout_floor() -> None:
    overrides = replay_script._provider_overrides_from_user_settings(
        {
            "providers": {
                "llm_openai": {
                    "enabled": True,
                    "config": {"base_url": "https://example.com/v1", "model": "qwen-test", "timeout_sec": 60},
                },
                "agent_codex": {
                    "enabled": False,
                    "config": {"base_url": "https://codex.example.com", "timeout_sec": 90},
                },
            }
        }
    )

    assert overrides == {
        "llm_openai": {
            "base_url": "https://example.com/v1",
            "model": "qwen-test",
            "timeout_sec": 120,
        }
    }


@pytest.mark.asyncio
async def test_resolve_provider_overrides_prefers_explicit_json(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"db": 0}

    async def _unexpected_db_load(monitor_id: str | None) -> dict[str, dict]:
        called["db"] += 1
        return {"llm_openai": {"timeout_sec": 300}}

    monkeypatch.setattr(replay_script, "_load_provider_overrides_from_db", _unexpected_db_load)

    resolved = await replay_script._resolve_provider_overrides(
        provider_overrides_json='{"llm_openai":{"model":"qwen-explicit","timeout_sec":45}}',
        run_summary={"monitor_id": "monitor-1"},
    )

    assert called["db"] == 0
    assert resolved["llm_openai"]["model"] == "qwen-explicit"
    assert resolved["llm_openai"]["timeout_sec"] == 120


@pytest.mark.asyncio
async def test_resolve_provider_overrides_falls_back_to_db(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_db_load(monitor_id: str | None) -> dict[str, dict]:
        assert monitor_id == "monitor-2"
        return {"llm_openai": {"model": "qwen-db", "timeout_sec": 90}}

    monkeypatch.setattr(replay_script, "_load_provider_overrides_from_db", _fake_db_load)

    resolved = await replay_script._resolve_provider_overrides(
        provider_overrides_json=None,
        run_summary={"monitor_id": "monitor-2"},
    )

    assert resolved["llm_openai"]["model"] == "qwen-db"
    assert resolved["llm_openai"]["timeout_sec"] == 120

@pytest.mark.asyncio
async def test_run_replay_can_stop_after_keywords_and_write_stage_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    export_dir = _make_export_dir(tmp_path)
    output_dir = tmp_path / "out"

    monkeypatch.setattr(replay_script, "ProcessingPipeline", _FakePipeline)

    async def _unexpected_report(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("report stage should not run when stop_after=keywords")

    monkeypatch.setattr(replay_script, "_run_report_with_retry", _unexpected_report)

    result = await replay_script._run_replay(
        export_dir=export_dir,
        output_dir=output_dir,
        routing_profile="test_profile",
        provider_overrides={},
        run_report_rewrite=True,
        max_articles=None,
        pipeline_mode="rule",
        fallback_rule_on_auth_error=False,
        stage_concurrency=4,
        stop_after="keywords",
        resume_from=None,
    )

    assert result["last_completed_stage"] == "keywords"
    assert (output_dir / "01_raw_articles.json").exists()
    assert (output_dir / "02_window_filtered.json").exists()
    assert (output_dir / "03_filter_output.json").exists()
    assert (output_dir / "03_candidate_clusters.json").exists()
    assert (output_dir / "04_keywords_output.json").exists()
    assert (output_dir / "04_event_extract_output.json").exists()
    assert _FakePipeline.configured_stage_concurrency == 4
    assert not (output_dir / "07_rendered_report.md").exists()
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["events"]["candidate_cluster_count"] == 1
    assert metrics["events"]["event_extract_count"] == 1


@pytest.mark.asyncio
async def test_run_replay_resume_from_keywords_reuses_keywords_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    export_dir = _make_export_dir(tmp_path)
    output_dir = tmp_path / "resume-keywords"

    monkeypatch.setattr(replay_script, "ProcessingPipeline", _FakePipeline)

    _FakePipeline.reset_counts()
    await replay_script._run_replay(
        export_dir=export_dir,
        output_dir=output_dir,
        routing_profile="test_profile",
        provider_overrides={},
        run_report_rewrite=False,
        max_articles=None,
        pipeline_mode="rule",
        fallback_rule_on_auth_error=False,
        stop_after="keywords",
        resume_from=None,
    )

    _FakePipeline.reset_counts()
    result = await replay_script._run_replay(
        export_dir=export_dir,
        output_dir=output_dir,
        routing_profile="test_profile",
        provider_overrides={},
        run_report_rewrite=False,
        max_articles=None,
        pipeline_mode="rule",
        fallback_rule_on_auth_error=False,
        stop_after="keywords",
        resume_from="keywords",
    )

    assert result["last_completed_stage"] == "keywords"
    assert _FakePipeline.call_counts == {
        "filter": 0,
        "candidate_cluster": 0,
        "keywords": 0,
        "event_extract": 0,
    }


@pytest.mark.asyncio
async def test_run_replay_can_stop_after_aggregate_and_write_aggregated_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    export_dir = _make_export_dir(tmp_path)
    output_dir = tmp_path / "aggregate-out"

    monkeypatch.setattr(replay_script, "ProcessingPipeline", _FakePipeline)

    result = await replay_script._run_replay(
        export_dir=export_dir,
        output_dir=output_dir,
        routing_profile="test_profile",
        provider_overrides={},
        run_report_rewrite=False,
        max_articles=None,
        pipeline_mode="rule",
        fallback_rule_on_auth_error=False,
        stop_after="aggregate",
        resume_from=None,
    )

    assert result["last_completed_stage"] == "aggregate"
    assert (output_dir / "05_aggregated_events.json").exists()
    assert not (output_dir / "07_rendered_report.md").exists()
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["events"]["candidate_cluster_count"] == 1
    assert metrics["events"]["event_extract_count"] == 1
    assert metrics["events"]["aggregated_event_count"] == 1


@pytest.mark.asyncio
async def test_run_replay_can_stop_after_global_summary_and_write_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    export_dir = _make_export_dir(tmp_path)
    output_dir = tmp_path / "global-summary-out"

    monkeypatch.setattr(replay_script, "ProcessingPipeline", _FakePipeline)

    async def _fake_global_summary_stage(*, events: list[dict], runner=None) -> GlobalSummary:  # noqa: ANN001
        assert len(events) == 1
        return GlobalSummary(
            global_tldr="这是回放生成的全局摘要。",
            provider="llm_openai",
            fallback_used=False,
            prompt_metrics={"input_event_count": 1, "output_chars": 12},
        )

    monkeypatch.setattr(replay_script, "run_global_summary_stage", _fake_global_summary_stage, raising=False)

    result = await replay_script._run_replay(
        export_dir=export_dir,
        output_dir=output_dir,
        routing_profile="test_profile",
        provider_overrides={},
        run_report_rewrite=False,
        max_articles=None,
        pipeline_mode="rule",
        fallback_rule_on_auth_error=False,
        stop_after="global_summary",
        resume_from=None,
    )

    assert result["last_completed_stage"] == "global_summary"
    assert (output_dir / "06_global_summary.json").exists()
    assert not (output_dir / "07_rendered_report.md").exists()
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["global_summary_provider_used"] == "llm_openai"
    assert metrics["global_summary_chars"] == 12
    assert metrics["global_summary_fallback_used"] is False


@pytest.mark.asyncio
async def test_run_replay_resume_from_aggregate_reuses_event_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    export_dir = _make_export_dir(tmp_path)
    output_dir = tmp_path / "resume-aggregate"

    monkeypatch.setattr(replay_script, "ProcessingPipeline", _FakePipeline)

    async def _fake_global_summary_stage(*, events: list[dict], runner=None) -> GlobalSummary:  # noqa: ANN001
        return GlobalSummary(
            global_tldr="这是回放生成的全局摘要。",
            provider="llm_openai",
            fallback_used=False,
            prompt_metrics={"input_event_count": len(events), "output_chars": 12},
        )

    monkeypatch.setattr(replay_script, "run_global_summary_stage", _fake_global_summary_stage, raising=False)

    _FakePipeline.reset_counts()
    await replay_script._run_replay(
        export_dir=export_dir,
        output_dir=output_dir,
        routing_profile="test_profile",
        provider_overrides={},
        run_report_rewrite=False,
        max_articles=None,
        pipeline_mode="rule",
        fallback_rule_on_auth_error=False,
        stop_after="aggregate",
        resume_from=None,
    )

    _FakePipeline.reset_counts()
    result = await replay_script._run_replay(
        export_dir=export_dir,
        output_dir=output_dir,
        routing_profile="test_profile",
        provider_overrides={},
        run_report_rewrite=False,
        max_articles=None,
        pipeline_mode="rule",
        fallback_rule_on_auth_error=False,
        stop_after=None,
        resume_from="aggregate",
    )

    assert result["last_completed_stage"] == "render"
    assert _FakePipeline.call_counts == {
        "filter": 0,
        "candidate_cluster": 0,
        "keywords": 0,
        "event_extract": 0,
    }
    assert (output_dir / "07_rendered_report.md").exists()
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["events"]["candidate_cluster_count"] == 1
    assert metrics["events"]["event_extract_count"] == 1
    assert metrics["events"]["aggregated_event_count"] == 1


@pytest.mark.asyncio
async def test_run_replay_resume_from_global_summary_reuses_summary_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    export_dir = _make_export_dir(tmp_path)
    output_dir = tmp_path / "resume-global-summary"

    monkeypatch.setattr(replay_script, "ProcessingPipeline", _FakePipeline)

    async def _fake_global_summary_stage(*, events: list[dict], runner=None) -> GlobalSummary:  # noqa: ANN001
        return GlobalSummary(
            global_tldr="这是回放生成的全局摘要。",
            provider="llm_openai",
            fallback_used=False,
            prompt_metrics={"input_event_count": len(events), "output_chars": 12},
        )

    monkeypatch.setattr(replay_script, "run_global_summary_stage", _fake_global_summary_stage, raising=False)

    await replay_script._run_replay(
        export_dir=export_dir,
        output_dir=output_dir,
        routing_profile="test_profile",
        provider_overrides={},
        run_report_rewrite=False,
        max_articles=None,
        pipeline_mode="rule",
        fallback_rule_on_auth_error=False,
        stop_after="global_summary",
        resume_from=None,
    )

    async def _unexpected_global_summary_stage(*, events: list[dict], runner=None) -> GlobalSummary:  # noqa: ANN001
        raise AssertionError("global summary stage should not rerun when resume_from=global_summary")

    monkeypatch.setattr(replay_script, "run_global_summary_stage", _unexpected_global_summary_stage, raising=False)

    result = await replay_script._run_replay(
        export_dir=export_dir,
        output_dir=output_dir,
        routing_profile="test_profile",
        provider_overrides={},
        run_report_rewrite=False,
        max_articles=None,
        pipeline_mode="rule",
        fallback_rule_on_auth_error=False,
        stop_after=None,
        resume_from="global_summary",
    )

    assert result["last_completed_stage"] == "render"
    assert (output_dir / "07_rendered_report.md").exists()
