from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.renderers.base import Report
from app.sinks import obsidian as obsidian_module
from app.sinks.obsidian import ObsidianSink


@pytest.mark.asyncio
async def test_obsidian_sink_publishes_via_rest_api(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict[str, str], str]] = []

    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def put(self, url: str, *, content: str, headers: dict[str, str]):
            calls.append(("PUT", url, headers, content))
            return httpx.Response(201, request=httpx.Request("PUT", url))

    monkeypatch.setattr(
        obsidian_module,
        "httpx",
        SimpleNamespace(AsyncClient=lambda *args, **kwargs: StubClient()),
        raising=False,
    )

    sink = ObsidianSink()
    result = await sink.publish(
        Report(level="L2", title="Daily / Brief", content="# Report", article_ids=[]),
        {
            "mode": "rest",
            "api_url": "https://127.0.0.1:27124",
            "api_key": "obsidian-secret",
            "target_folder": "AI Reports/Daily",
        },
    )

    assert result.success is True
    assert calls == [
        (
            "PUT",
            "https://127.0.0.1:27124/vault/AI%20Reports/Daily/Daily%20-%20Brief.md",
            {
                "Authorization": "Bearer obsidian-secret",
                "Content-Type": "text/markdown; charset=utf-8",
            },
            "# Report",
        )
    ]
    assert result.url == "https://127.0.0.1:27124/vault/AI%20Reports/Daily/Daily%20-%20Brief.md"


@pytest.mark.asyncio
async def test_obsidian_sink_falls_back_to_local_vault_path(tmp_path: Path) -> None:
    sink = ObsidianSink()
    result = await sink.publish(
        Report(level="L2", title="Daily / Brief", content="# Report", article_ids=[]),
        {
            "mode": "file",
            "vault_path": str(tmp_path),
            "target_folder": "AI-Reports",
        },
    )

    output = tmp_path / "AI-Reports" / "Daily - Brief.md"

    assert result.success is True
    assert output.exists()
    assert output.read_text(encoding="utf-8") == "# Report"
    assert result.url == str(output)


@pytest.mark.asyncio
async def test_obsidian_sink_returns_error_when_rest_request_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def put(self, url: str, *, content: str, headers: dict[str, str]):
            return httpx.Response(401, request=httpx.Request("PUT", url), text="unauthorized")

    monkeypatch.setattr(
        obsidian_module,
        "httpx",
        SimpleNamespace(AsyncClient=lambda *args, **kwargs: StubClient()),
        raising=False,
    )

    sink = ObsidianSink()
    result = await sink.publish(
        Report(level="L2", title="Daily Brief", content="# Report", article_ids=[]),
        {
            "mode": "rest",
            "api_url": "https://127.0.0.1:27124",
            "api_key": "bad-key",
            "target_folder": "AI Reports",
        },
    )

    assert result.success is False
    assert "401" in (result.error or "")


@pytest.mark.asyncio
async def test_obsidian_sink_requires_explicit_mode() -> None:
    sink = ObsidianSink()
    result = await sink.publish(
        Report(level="L2", title="Daily Brief", content="# Report", article_ids=[]),
        {
            "api_url": "https://127.0.0.1:27124",
            "api_key": "obsidian-secret",
            "target_folder": "AI Reports",
        },
    )

    assert result.success is False
    assert "mode" in (result.error or "")
