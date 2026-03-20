from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents import deerflow_embedded as deerflow_module
from app.agents import deerflow_subprocess as subprocess_module
from app.agents.deerflow_embedded import DeerFlowEmbeddedRuntime
from app.agents.deerflow_subprocess import DeerFlowSubprocessRuntime
from app.agents.schemas import ResearchEvent, ResearchJob


def _build_job() -> ResearchJob:
    return ResearchJob(
        job_id="job-123",
        frequency="daily",
        template="research",
        event=ResearchEvent(
            event_id="evt-1",
            title="OpenAI releases model",
            summary="Model launch summary",
            detail="Detailed event content",
            category="model_release",
            importance="high",
            source_links=["https://example.com/official"],
            source_count=1,
            source_name="OpenAI",
            who="OpenAI",
            what="Release",
            when="2026-03-13",
            keywords=["openai", "model"],
        ),
        focus_questions=["What changed?"],
        metadata={
            "analysis_mode": "literature",
            "literature_corpus": [
                {
                    "paper_id": "paper-1",
                    "title": "OpenAI releases model",
                    "evidence_level": "fulltext",
                    "analysis_text": "Fulltext literature content",
                }
            ],
        },
    )


@pytest.mark.asyncio
async def test_deerflow_embedded_runtime_normalizes_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeClient:
        def __init__(
            self,
            *,
            config_path: str | None = None,
            thinking_enabled: bool,
            subagent_enabled: bool,
            plan_mode: bool,
        ):
            captured["config_path"] = config_path
            captured["thinking_enabled"] = thinking_enabled
            captured["subagent_enabled"] = subagent_enabled
            captured["plan_mode"] = plan_mode

        def chat(self, message: str, *, thread_id: str | None = None, **kwargs) -> str:
            captured["message"] = message
            captured["thread_id"] = thread_id
            captured["chat_kwargs"] = kwargs
            return json.dumps(
                {
                    "title": "Research title",
                    "summary": "Research summary",
                    "content_markdown": "# Executive Summary\nBody",
                    "sources": [
                        {
                            "title": "Official",
                            "url": "https://example.com/official",
                            "source_type": "official",
                        }
                    ],
                    "confidence": {"level": "high", "reason": "official source"},
                    "artifacts": ["/tmp/output.md"],
                    "metadata": {"agent_name": "lead_agent"},
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(deerflow_module, "_load_deerflow_client_class", lambda config_path: _FakeClient)

    runtime = DeerFlowEmbeddedRuntime(
        config={
            "config_path": "/tmp/deer-flow/config.yaml",
            "thinking_enabled": False,
            "subagent_enabled": True,
            "plan_mode": True,
        }
    )

    result = await runtime.run(_build_job())

    assert captured["config_path"] == "/tmp/deer-flow/config.yaml"
    assert captured["thinking_enabled"] is False
    assert captured["subagent_enabled"] is True
    assert captured["plan_mode"] is True
    assert captured["thread_id"] == "job-123"
    assert "Use the enabled skills" in str(captured["message"])
    assert "Prioritize the provided event details and source links" in str(captured["message"])
    assert "OpenAI releases model" in str(captured["message"])
    assert '"analysis_mode": "literature"' in str(captured["message"])
    assert "Fulltext literature content" in str(captured["message"])
    assert result.title == "Research title"
    assert result.summary == "Research summary"
    assert result.content_markdown.startswith("# Executive Summary")
    assert result.sources[0].url == "https://example.com/official"
    assert result.confidence_level == "high"
    assert result.artifacts == ["/tmp/output.md"]
    assert result.metadata["agent_name"] == "lead_agent"


@pytest.mark.asyncio
async def test_deerflow_embedded_runtime_falls_back_to_plain_text_content(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeClient:
        def __init__(self, **_: object) -> None:
            pass

        def chat(self, message: str, *, thread_id: str | None = None, **kwargs) -> str:
            return "# Executive Summary\nPlain text response"

    monkeypatch.setattr(deerflow_module, "_load_deerflow_client_class", lambda config_path: _FakeClient)

    runtime = DeerFlowEmbeddedRuntime(config={"config_path": "/tmp/deer-flow/config.yaml"})

    result = await runtime.run(_build_job())

    assert result.title == "OpenAI releases model"
    assert result.summary == ""
    assert result.content_markdown == "# Executive Summary\nPlain text response"
    assert result.sources == []
    assert result.confidence_level == "unknown"


@pytest.mark.asyncio
async def test_deerflow_embedded_runtime_raises_actionable_error_when_deerflow_import_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_import(config_path: str | None):
        raise ModuleNotFoundError("No module named 'langchain'")

    monkeypatch.setattr(deerflow_module, "_load_deerflow_client_class", _raise_import)

    runtime = DeerFlowEmbeddedRuntime(config={"config_path": "/tmp/deer-flow/config.yaml"})

    with pytest.raises(RuntimeError, match="DeerFlow dependencies are not available"):
        await runtime.run(_build_job())


@pytest.mark.asyncio
async def test_deerflow_subprocess_runtime_normalizes_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def _fake_run_subprocess(*, script_path: Path, python_bin: Path, payload: dict) -> str:
        captured["script_path"] = script_path
        captured["python_bin"] = python_bin
        captured["payload"] = payload
        return json.dumps(
            {
                "title": "Subprocess title",
                "summary": "Subprocess summary",
                "content_markdown": "# Executive Summary\nSubprocess body",
                "sources": [{"title": "Official", "url": "https://example.com/official"}],
                "confidence": {"level": "high", "reason": "verified"},
                "metadata": {"agent_name": "lead_agent"},
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(subprocess_module, "_run_deerflow_subprocess", _fake_run_subprocess)

    runtime = DeerFlowSubprocessRuntime(
        config={"config_path": "/Users/leo/workspace/DeepResearch/deer-flow/config.yaml"}
    )

    result = await runtime.run(_build_job())

    assert captured["python_bin"] == Path("/Users/leo/workspace/DeepResearch/deer-flow/backend/.venv/bin/python")
    assert "Use the enabled skills" in str(captured["payload"])
    assert "Prioritize the provided event details and source links" in str(captured["payload"])
    assert result.title == "Subprocess title"
    assert result.summary == "Subprocess summary"
    assert result.content_markdown.startswith("# Executive Summary")
    assert result.confidence_level == "high"


@pytest.mark.asyncio
async def test_deerflow_subprocess_runtime_surfaces_subprocess_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_run_subprocess(*, script_path: Path, python_bin: Path, payload: dict) -> str:
        raise RuntimeError("subprocess failed")

    monkeypatch.setattr(subprocess_module, "_run_deerflow_subprocess", _fake_run_subprocess)

    runtime = DeerFlowSubprocessRuntime(
        config={"config_path": "/Users/leo/workspace/DeepResearch/deer-flow/config.yaml"}
    )

    with pytest.raises(RuntimeError, match="subprocess failed"):
        await runtime.run(_build_job())
