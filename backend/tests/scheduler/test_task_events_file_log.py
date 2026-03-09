from __future__ import annotations

import json
import uuid

import pytest

from app.scheduler import task_events


class _DummySession:
    def __init__(self) -> None:
        self.items: list[object] = []

    def add(self, item: object) -> None:
        self.items.append(item)


@pytest.mark.asyncio
async def test_append_task_event_writes_run_log_jsonl(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(task_events, "TASK_EVENT_LOG_DIR", tmp_path)
    db = _DummySession()
    run_id = uuid.uuid4()
    monitor_id = uuid.uuid4()
    task_id = uuid.uuid4()
    source_id = uuid.uuid4()

    await task_events.append_task_event(
        db,
        run_id=run_id,
        monitor_id=monitor_id,
        task_id=task_id,
        source_id=source_id,
        stage="process",
        event_type="source_failed",
        message="ReadTimeout",
        level="error",
        payload={"error": "ReadTimeout"},
    )

    assert len(db.items) == 1
    run_log_files = sorted(tmp_path.glob("run_*.jsonl"))
    assert len(run_log_files) == 1
    run_log_file = run_log_files[0]
    assert str(run_id) not in run_log_file.name

    lines = run_log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["created_at"].endswith("+08:00")
    assert event["run_id"] == str(run_id)
    assert event["monitor_id"] == str(monitor_id)
    assert event["task_id"] == str(task_id)
    assert event["source_id"] == str(source_id)
    assert event["stage"] == "process"
    assert event["event_type"] == "source_failed"
    assert event["level"] == "error"
    assert event["payload"]["error"] == "ReadTimeout"


@pytest.mark.asyncio
async def test_append_task_event_writes_human_readable_run_log(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(task_events, "TASK_EVENT_LOG_DIR", tmp_path)
    db = _DummySession()
    run_id = uuid.uuid4()
    task_id = uuid.uuid4()
    source_id = uuid.uuid4()

    await task_events.append_task_event(
        db,
        run_id=run_id,
        monitor_id=None,
        task_id=task_id,
        source_id=source_id,
        stage="collect",
        event_type="source_started",
        message="[Seed Source] collect started",
        payload={"source_name": "Seed Source", "provider": "huggingface"},
    )

    run_log_files = sorted(tmp_path.glob("run_*.log"))
    assert len(run_log_files) == 1
    run_log_file = run_log_files[0]
    assert str(run_id) not in run_log_file.name

    lines = run_log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    context_line = lines[0]
    event_line = lines[1]
    assert f"run={run_id}" in context_line
    assert f"task={task_id}" in context_line
    assert f"source={source_id}" in context_line

    assert "INFO" in event_line
    assert "+08:00" in event_line
    assert "run=" not in event_line
    assert "monitor=" not in event_line
    assert "task=" not in event_line
    assert "source=" not in event_line
    assert "stage=collect" in event_line
    assert "event=source_started" in event_line
    assert "\"[Seed Source] collect started\"" in event_line
    assert "payload=" in event_line


@pytest.mark.asyncio
async def test_append_task_event_appends_multiple_lines_for_same_run(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(task_events, "TASK_EVENT_LOG_DIR", tmp_path)
    db = _DummySession()
    run_id = uuid.uuid4()

    await task_events.append_task_event(
        db,
        run_id=run_id,
        monitor_id=None,
        task_id=None,
        source_id=None,
        stage="collect",
        event_type="source_started",
        message="[OpenAI] collect started",
    )
    await task_events.append_task_event(
        db,
        run_id=run_id,
        monitor_id=None,
        task_id=None,
        source_id=None,
        stage="publish",
        event_type="publish_success",
        message="[daily] publish to notion: success",
    )

    run_log_files = sorted(tmp_path.glob("run_*.jsonl"))
    assert len(run_log_files) == 1
    run_log_file = run_log_files[0]
    lines = run_log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first_event = json.loads(lines[0])
    second_event = json.loads(lines[1])
    assert first_event["event_type"] == "source_started"
    assert second_event["event_type"] == "publish_success"
