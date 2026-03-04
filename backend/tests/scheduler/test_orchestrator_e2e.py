from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.collectors.base import BaseCollector, RawArticle
from app.models import Article, CollectTask, Report, Source, User, UserSubscription
from app.scheduler import orchestrator as orchestrator_module
from app.scheduler.orchestrator import Orchestrator
from app.sinks.base import PublishResult

DEFAULT_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
SOURCE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SECOND_SOURCE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


class FakeCollector(BaseCollector):
    @property
    def name(self) -> str:
        return "fake"

    @property
    def category(self) -> str:
        return "blog"

    async def collect(self, config: dict) -> list[RawArticle]:
        return [
            RawArticle(
                external_id="fake-ext-1",
                title="AI breakthrough today",
                url="https://example.com/post",
                content="New AI architecture improves multimodal reasoning and deployment efficiency.",
                published_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            )
        ]


@pytest.fixture(autouse=True)
def _stub_report_provider(monkeypatch: pytest.MonkeyPatch):
    original_get_provider = orchestrator_module.get_provider

    class _ReportProvider:
        stage = "report"
        name = "agent_codex"

        async def run(self, payload: dict, config: dict | None = None) -> dict:
            return {
                "title": str(payload.get("title") or "AI Daily Report"),
                "content": str(payload.get("content") or ""),
                "global_tldr": str(payload.get("global_tldr") or ""),
            }

    def _wrapped_get_provider(stage: str, name: str):
        if stage == "report":
            return _ReportProvider()
        return original_get_provider(stage=stage, name=name)

    monkeypatch.setattr(orchestrator_module, "get_provider", _wrapped_get_provider)


@pytest.fixture(autouse=True)
def _stub_ai_processing_calls(monkeypatch: pytest.MonkeyPatch):
    async def _mock_run_codex_json(prompt: str, config: dict | None = None) -> dict:
        lowered = prompt.lower()
        if "keep_indices" in lowered:
            return {"keep_indices": [0]}
        if '"keywords"' in prompt or "extract 5-8 high-signal keywords" in lowered:
            return {
                "keywords": ["ai", "agent", "benchmark"],
                "summary": "AI update relevant for engineering teams.",
            }
        if '"global_tldr"' in prompt or "rewrite this ai daily report" in lowered:
            return {
                "title": "AI Daily Report",
                "content": "AI daily content",
                "global_tldr": "summary + comment",
            }
        return {}

    monkeypatch.setattr("app.providers.filter.run_codex_json", _mock_run_codex_json)
    monkeypatch.setattr("app.providers.keywords.run_codex_json", _mock_run_codex_json)
    monkeypatch.setattr("app.providers.report.run_codex_json", _mock_run_codex_json)


@pytest.mark.asyncio
async def test_orchestrator_run_daily_pipeline_persists_articles_tasks_reports(db_session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory, _ = db_session_factory

    async def _prepare_subscription() -> None:
        async with session_factory() as session:
            session.add(
                UserSubscription(
                    user_id=DEFAULT_USER_ID,
                    source_id=SOURCE_ID,
                    enabled=True,
                    custom_config={},
                )
            )
            await session.commit()

    await _prepare_subscription()

    monkeypatch.setattr(orchestrator_module, "get_collector", lambda method: FakeCollector())

    orchestrator = Orchestrator(max_concurrency=2)

    async with session_factory() as session:
        result = await orchestrator.run_daily_pipeline(db=session, user_id=DEFAULT_USER_ID, trigger_type="manual")
        assert result["processed_articles"] >= 1

    async def _verify() -> tuple[int, int, int]:
        async with session_factory() as session:
            articles_count = len((await session.execute(select(Article).where(Article.source_id == SOURCE_ID))).scalars().all())
            tasks_count = len((await session.execute(select(CollectTask))).scalars().all())
            reports_count = len(
                (
                    await session.execute(
                        select(Report).where(
                            Report.user_id == DEFAULT_USER_ID,
                            Report.report_date == date.today(),
                        )
                    )
                ).scalars().all()
            )
            return articles_count, tasks_count, reports_count

    article_count, task_count, report_count = await _verify()

    assert article_count >= 1
    assert task_count >= 1
    assert report_count >= 1


@pytest.mark.asyncio
async def test_orchestrator_marks_partial_success_when_notion_fails(
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory, _ = db_session_factory

    async def _prepare_subscription() -> None:
        async with session_factory() as session:
            session.add(
                UserSubscription(
                    user_id=DEFAULT_USER_ID,
                    source_id=SOURCE_ID,
                    enabled=True,
                    custom_config={},
                )
            )
            await session.commit()

    await _prepare_subscription()
    monkeypatch.setattr(orchestrator_module, "get_collector", lambda method: FakeCollector())

    class _DatabaseSink:
        name = "database"

        async def publish(self, report, config):
            return PublishResult(success=True, sink_name=self.name, url="database://ok")

    class _NotionSink:
        name = "notion"

        async def publish(self, report, config):
            return PublishResult(success=False, sink_name=self.name, error="notion down")

    def _fake_get_sink(target: str):
        if target == "database":
            return _DatabaseSink()
        return _NotionSink()

    monkeypatch.setattr(orchestrator_module, "get_sink", _fake_get_sink)

    orchestrator = Orchestrator(max_concurrency=2)
    async with session_factory() as session:
        result = await orchestrator.run_daily_pipeline(db=session, user_id=DEFAULT_USER_ID, trigger_type="manual")
        assert result["status"] == "partial_success"

    async with session_factory() as session:
        reports = (
            await session.execute(
                select(Report).where(
                    Report.user_id == DEFAULT_USER_ID,
                    Report.report_date == date.today(),
                )
            )
        ).scalars().all()
        generated = [report for report in reports if report.title != "Seed Daily Brief"]
        assert generated
        assert all(report.report_type == "daily" for report in generated)
        for report in generated:
            assert "database" in (report.published_to or [])
            assert report.publish_trace


@pytest.mark.asyncio
async def test_orchestrator_applies_huggingface_limit_override_to_collect_config(
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory, _ = db_session_factory

    async def _prepare_subscription() -> None:
        async with session_factory() as session:
            source = await session.get(Source, SOURCE_ID)
            assert source is not None
            source.collect_method = "huggingface"
            source.config = {"limit": 30, "include_paper_detail": True}
            session.add(
                UserSubscription(
                    user_id=DEFAULT_USER_ID,
                    source_id=SOURCE_ID,
                    enabled=True,
                    custom_config={},
                )
            )
            await session.commit()

    await _prepare_subscription()

    captured_config: dict = {}

    class _CaptureCollector(BaseCollector):
        @property
        def name(self) -> str:
            return "capture"

        @property
        def category(self) -> str:
            return "open_source"

        async def collect(self, config: dict) -> list[RawArticle]:
            captured_config.update(config)
            return []

    monkeypatch.setattr(orchestrator_module, "get_collector", lambda method: _CaptureCollector())

    orchestrator = Orchestrator(max_concurrency=2)
    async with session_factory() as session:
        await orchestrator.run_daily_pipeline(
            db=session,
            user_id=DEFAULT_USER_ID,
            trigger_type="manual",
            source_ids=[SOURCE_ID],
            source_overrides={str(SOURCE_ID): {"limit": 7}},
        )

    assert captured_config["limit"] == 7
    assert captured_config["include_paper_detail"] is True


@pytest.mark.asyncio
async def test_orchestrator_applies_max_items_override_to_huggingface_collect_config(
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory, _ = db_session_factory

    async def _prepare_subscription() -> None:
        async with session_factory() as session:
            source = await session.get(Source, SOURCE_ID)
            assert source is not None
            source.collect_method = "huggingface"
            source.config = {"limit": 30, "include_paper_detail": True}
            session.add(
                UserSubscription(
                    user_id=DEFAULT_USER_ID,
                    source_id=SOURCE_ID,
                    enabled=True,
                    custom_config={},
                )
            )
            await session.commit()

    await _prepare_subscription()

    captured_config: dict = {}

    class _CaptureCollector(BaseCollector):
        @property
        def name(self) -> str:
            return "capture"

        @property
        def category(self) -> str:
            return "open_source"

        async def collect(self, config: dict) -> list[RawArticle]:
            captured_config.update(config)
            return []

    monkeypatch.setattr(orchestrator_module, "get_collector", lambda method: _CaptureCollector())

    orchestrator = Orchestrator(max_concurrency=2)
    async with session_factory() as session:
        await orchestrator.run_daily_pipeline(
            db=session,
            user_id=DEFAULT_USER_ID,
            trigger_type="manual",
            source_ids=[SOURCE_ID],
            source_overrides={str(SOURCE_ID): {"max_items": 6}},
        )

    assert captured_config["limit"] == 6
    assert captured_config["include_paper_detail"] is True


@pytest.mark.asyncio
async def test_orchestrator_applies_arxiv_overrides_to_collect_config(
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory, _ = db_session_factory

    async def _prepare_subscription() -> None:
        async with session_factory() as session:
            source = await session.get(Source, SOURCE_ID)
            assert source is not None
            source.collect_method = "rss"
            source.config = {
                "feed_url": "https://export.arxiv.org/api/query",
                "arxiv_api": True,
                "keywords": ["baseline"],
                "max_results": 25,
                "max_items": 25,
            }
            session.add(
                UserSubscription(
                    user_id=DEFAULT_USER_ID,
                    source_id=SOURCE_ID,
                    enabled=True,
                    custom_config={},
                )
            )
            await session.commit()

    await _prepare_subscription()

    captured_config: dict = {}

    class _CaptureCollector(BaseCollector):
        @property
        def name(self) -> str:
            return "capture"

        @property
        def category(self) -> str:
            return "academic"

        async def collect(self, config: dict) -> list[RawArticle]:
            captured_config.update(config)
            return []

    monkeypatch.setattr(orchestrator_module, "get_collector", lambda method: _CaptureCollector())

    orchestrator = Orchestrator(max_concurrency=2)
    async with session_factory() as session:
        await orchestrator.run_daily_pipeline(
            db=session,
            user_id=DEFAULT_USER_ID,
            trigger_type="manual",
            source_ids=[SOURCE_ID],
            source_overrides={
                str(SOURCE_ID): {
                    "keywords": ["reasoning", "agent"],
                    "max_results": 7,
                }
            },
        )

    assert captured_config["keywords"] == ["reasoning", "agent"]
    assert captured_config["max_results"] == 7
    assert captured_config["max_items"] == 7


@pytest.mark.asyncio
async def test_orchestrator_honors_source_and_destination_overrides_with_user_destination_config(
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory, _ = db_session_factory

    async def _prepare() -> None:
        async with session_factory() as session:
            session.add(
                Source(
                    id=SECOND_SOURCE_ID,
                    name="Second Source",
                    category="blog",
                    collect_method="rss",
                    config={"feed_url": "https://example.com/second"},
                    enabled=True,
                )
            )
            session.add_all(
                [
                    UserSubscription(
                        user_id=DEFAULT_USER_ID,
                        source_id=SOURCE_ID,
                        enabled=True,
                        custom_config={},
                    ),
                    UserSubscription(
                        user_id=DEFAULT_USER_ID,
                        source_id=SECOND_SOURCE_ID,
                        enabled=True,
                        custom_config={},
                    ),
                ]
            )
            user = await session.get(User, DEFAULT_USER_ID)
            assert user is not None
            user.settings = {
                "default_time_period": "daily",
                "default_report_type": "daily",
                "default_sink": "notion",
                "destinations": {
                    "notion": {
                        "enabled": True,
                        "config": {
                            "token": "secret_test_token",
                            "parent_page_id": "parent_page_test",
                            "title_property": "名称",
                        },
                    }
                },
            }
            await session.commit()

    await _prepare()
    monkeypatch.setattr(orchestrator_module, "get_collector", lambda method: FakeCollector())

    sink_calls: list[tuple[str, dict]] = []

    class _DatabaseSink:
        name = "database"

        async def publish(self, report, config):
            sink_calls.append(("database", dict(config)))
            return PublishResult(success=True, sink_name=self.name, url="database://ok")

    class _NotionSink:
        name = "notion"

        async def publish(self, report, config):
            sink_calls.append(("notion", dict(config)))
            return PublishResult(success=True, sink_name=self.name, url="https://notion.so/page")

    def _fake_get_sink(target: str):
        if target == "database":
            return _DatabaseSink()
        return _NotionSink()

    monkeypatch.setattr(orchestrator_module, "get_sink", _fake_get_sink)

    orchestrator = Orchestrator(max_concurrency=2)
    async with session_factory() as session:
        result = await orchestrator.run_daily_pipeline(
            db=session,
            user_id=DEFAULT_USER_ID,
            trigger_type="manual",
            source_ids=[SOURCE_ID],
            destination_ids=["notion"],
        )
        assert result["sources"] == 1

    async with session_factory() as session:
        tasks = (await session.execute(select(CollectTask).where(CollectTask.source_id.is_not(None)))).scalars().all()
        source_ids = {task.source_id for task in tasks}
        assert SOURCE_ID in source_ids
        assert SECOND_SOURCE_ID not in source_ids

    notion_configs = [cfg for sink, cfg in sink_calls if sink == "notion"]
    assert notion_configs
    assert notion_configs[0]["api_key"] == "secret_test_token"
    assert notion_configs[0]["parent_page_id"] == "parent_page_test"
    assert notion_configs[0]["title_property"] == "名称"
    assert notion_configs[0]["summary_property"] == "TL;DR"
    assert notion_configs[0]["summary_text"]


@pytest.mark.asyncio
async def test_orchestrator_applies_report_provider_output_before_publish(
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory, _ = db_session_factory

    async def _prepare_subscription() -> None:
        async with session_factory() as session:
            session.add(
                UserSubscription(
                    user_id=DEFAULT_USER_ID,
                    source_id=SOURCE_ID,
                    enabled=True,
                    custom_config={},
                )
            )
            await session.commit()

    await _prepare_subscription()
    monkeypatch.setattr(orchestrator_module, "get_collector", lambda method: FakeCollector())

    class _ReportProvider:
        stage = "report"
        name = "agent_codex"

        async def run(self, payload: dict, config: dict | None = None) -> dict:
            return {
                "title": "Codex Rewritten Daily",
                "content": "This deep report was rewritten by codex agent.",
            }

    def _fake_get_provider(stage: str, name: str):
        if stage == "report" and name == "agent_codex":
            return _ReportProvider()
        raise KeyError(name)

    monkeypatch.setattr(orchestrator_module, "get_provider", _fake_get_provider)

    published_payloads: list[tuple[str, str]] = []

    class _DatabaseSink:
        name = "database"

        async def publish(self, report, config):
            published_payloads.append((report.title, report.content))
            return PublishResult(success=True, sink_name=self.name, url="database://ok")

    class _NotionSink:
        name = "notion"

        async def publish(self, report, config):
            published_payloads.append((report.title, report.content))
            return PublishResult(success=True, sink_name=self.name, url="https://notion.so/page")

    def _fake_get_sink(target: str):
        if target == "database":
            return _DatabaseSink()
        return _NotionSink()

    monkeypatch.setattr(orchestrator_module, "get_sink", _fake_get_sink)

    orchestrator = Orchestrator(max_concurrency=2)
    orchestrator.routing_profile.stages.publish.targets = ["database", "notion_api"]
    orchestrator.routing_profile.stages.report.primary = "agent_codex"
    orchestrator.routing_profile.stages.report.fallback = []
    orchestrator.routing_profile.providers["agent_codex"] = {"auth_mode": "api_key", "api_key": "sk-test"}

    async with session_factory() as session:
        result = await orchestrator.run_daily_pipeline(db=session, user_id=DEFAULT_USER_ID, trigger_type="manual")
        assert result["status"] == "success"

    assert any(title == "Codex Rewritten Daily" for title, _ in published_payloads)
    assert any(content == "This deep report was rewritten by codex agent." for _, content in published_payloads)


@pytest.mark.asyncio
async def test_orchestrator_merges_user_provider_overrides_into_report_provider_config(
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory, _ = db_session_factory

    async def _prepare_subscription_and_provider_settings() -> None:
        async with session_factory() as session:
            session.add(
                UserSubscription(
                    user_id=DEFAULT_USER_ID,
                    source_id=SOURCE_ID,
                    enabled=True,
                    custom_config={},
                )
            )
            user = await session.get(User, DEFAULT_USER_ID)
            assert user is not None
            user.settings = {
                "default_time_period": "daily",
                "default_report_type": "daily",
                "default_sink": "notion",
                "providers": {
                    "agent_codex": {
                        "enabled": True,
                        "config": {
                            "auth_mode": "oauth",
                            "oauth_token": "oauth-from-ui",
                            "base_url": "https://gmn.chuangzuoli.com",
                            "model": "gpt-5.3-codex",
                            "timeout_sec": 120,
                        },
                    }
                },
            }
            await session.commit()

    await _prepare_subscription_and_provider_settings()
    monkeypatch.setattr(orchestrator_module, "get_collector", lambda method: FakeCollector())

    captured_configs: list[dict] = []

    class _ReportProvider:
        stage = "report"
        name = "agent_codex"

        async def run(self, payload: dict, config: dict | None = None) -> dict:
            captured_configs.append(dict(config or {}))
            return {
                "title": payload.get("title", "AI Daily Report"),
                "content": payload.get("content", ""),
            }

    def _fake_get_provider(stage: str, name: str):
        if stage == "report" and name == "agent_codex":
            return _ReportProvider()
        raise KeyError(name)

    monkeypatch.setattr(orchestrator_module, "get_provider", _fake_get_provider)

    class _DatabaseSink:
        name = "database"

        async def publish(self, report, config):
            return PublishResult(success=True, sink_name=self.name, url="database://ok")

    class _NotionSink:
        name = "notion"

        async def publish(self, report, config):
            return PublishResult(success=True, sink_name=self.name, url="https://notion.so/page")

    def _fake_get_sink(target: str):
        if target == "database":
            return _DatabaseSink()
        return _NotionSink()

    monkeypatch.setattr(orchestrator_module, "get_sink", _fake_get_sink)

    orchestrator = Orchestrator(max_concurrency=2)
    orchestrator.routing_profile.stages.publish.targets = ["database", "notion_api"]
    orchestrator.routing_profile.stages.report.primary = "agent_codex"
    orchestrator.routing_profile.stages.report.fallback = []

    async with session_factory() as session:
        result = await orchestrator.run_daily_pipeline(db=session, user_id=DEFAULT_USER_ID, trigger_type="manual")
        assert result["status"] == "success"

    assert captured_configs
    assert captured_configs[0]["auth_mode"] == "oauth"
    assert captured_configs[0]["oauth_token"] == "oauth-from-ui"
    assert captured_configs[0]["base_url"] == "https://gmn.chuangzuoli.com"
    assert captured_configs[0]["model"] == "gpt-5.3-codex"


@pytest.mark.asyncio
async def test_orchestrator_report_stage_retries_and_raises_after_exhausted(
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory, _ = db_session_factory

    async def _prepare_subscription() -> None:
        async with session_factory() as session:
            session.add(
                UserSubscription(
                    user_id=DEFAULT_USER_ID,
                    source_id=SOURCE_ID,
                    enabled=True,
                    custom_config={},
                )
            )
            await session.commit()

    await _prepare_subscription()
    monkeypatch.setattr(orchestrator_module, "get_collector", lambda method: FakeCollector())

    attempts = {"count": 0}

    class _FailingReportProvider:
        stage = "report"
        name = "agent_codex"

        async def run(self, payload: dict, config: dict | None = None) -> dict:
            attempts["count"] += 1
            raise RuntimeError("report provider down")

    def _fake_get_provider(stage: str, name: str):
        if stage == "report" and name == "agent_codex":
            return _FailingReportProvider()
        raise KeyError(name)

    monkeypatch.setattr(orchestrator_module, "get_provider", _fake_get_provider)

    orchestrator = Orchestrator(max_concurrency=2)
    orchestrator.routing_profile.stages.report.primary = "agent_codex"
    orchestrator.routing_profile.stages.report.fallback = ["llm_openai"]
    orchestrator.routing_profile.providers["agent_codex"] = {"max_retry": 1}

    async with session_factory() as session:
        with pytest.raises(RuntimeError, match="report provider down"):
            await orchestrator.run_daily_pipeline(db=session, user_id=DEFAULT_USER_ID, trigger_type="manual")

    # Initial call + 1 retry. No fallback to secondary provider.
    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_orchestrator_collects_sources_concurrently_before_processing(
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory, _ = db_session_factory

    async def _prepare_two_sources() -> None:
        async with session_factory() as session:
            session.add(
                Source(
                    id=SECOND_SOURCE_ID,
                    name="Second Source",
                    category="blog",
                    collect_method="rss",
                    config={"feed_url": "https://example.com/second"},
                    enabled=True,
                )
            )
            session.add_all(
                [
                    UserSubscription(
                        user_id=DEFAULT_USER_ID,
                        source_id=SOURCE_ID,
                        enabled=True,
                        custom_config={},
                    ),
                    UserSubscription(
                        user_id=DEFAULT_USER_ID,
                        source_id=SECOND_SOURCE_ID,
                        enabled=True,
                        custom_config={},
                    ),
                ]
            )
            await session.commit()

    await _prepare_two_sources()

    in_flight = {"count": 0, "max": 0}

    class _SlowCollector(BaseCollector):
        @property
        def name(self) -> str:
            return "slow"

        @property
        def category(self) -> str:
            return "blog"

        async def collect(self, config: dict) -> list[RawArticle]:
            in_flight["count"] += 1
            in_flight["max"] = max(in_flight["max"], in_flight["count"])
            await asyncio.sleep(0.05)
            in_flight["count"] -= 1
            marker = str(config.get("feed_url") or config.get("url") or "unknown")
            return [
                RawArticle(
                    external_id=f"{marker}-ext-1",
                    title=f"title:{marker}",
                    url=f"{marker}/1",
                    content=f"full content from {marker}",
                )
            ]

    monkeypatch.setattr(orchestrator_module, "get_collector", lambda method: _SlowCollector())

    orchestrator = Orchestrator(max_concurrency=4)
    async with session_factory() as session:
        result = await orchestrator.run_daily_pipeline(
            db=session,
            user_id=DEFAULT_USER_ID,
            trigger_type="test",
            source_ids=[SOURCE_ID, SECOND_SOURCE_ID],
        )
        assert result["status"] == "success"
        assert result["sources"] == 2

    assert in_flight["max"] >= 2
