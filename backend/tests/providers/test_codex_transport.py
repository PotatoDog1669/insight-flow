from __future__ import annotations

from pathlib import Path

import pytest

from app.providers import codex_transport


class _FakeResponse:
    def __init__(self) -> None:
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "output": [
                {
                    "content": [
                        {
                            "text": '{"summary":"ok"}',
                        }
                    ]
                }
            ]
        }


@pytest.mark.asyncio
async def test_run_codex_json_uses_120_second_default_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeAsyncClient:
        def __init__(self, *, timeout: float, headers: dict[str, str]) -> None:
            captured["timeout"] = timeout
            captured["headers"] = headers

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def post(self, endpoint: str, json: dict) -> _FakeResponse:
            captured["endpoint"] = endpoint
            captured["payload"] = json
            return _FakeResponse()

    monkeypatch.setattr(codex_transport.httpx, "AsyncClient", _FakeAsyncClient)

    output = await codex_transport.run_codex_json("hello", config={"api_key": "sk-demo"})

    assert output == {"summary": "ok"}
    assert captured["timeout"] == 120.0
    assert captured["endpoint"] == "https://api.openai.com/v1/responses"
    assert captured["payload"]["model"] == "gpt-5-codex"


@pytest.mark.asyncio
async def test_run_codex_json_uses_local_codex_cli_when_auth_mode_local(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    class _ForbiddenAsyncClient:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            raise AssertionError("HTTP transport should not be used for local_codex")

    class _FakeProcess:
        def __init__(self, *, returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> None:
            self.returncode = returncode
            self._stdout = stdout
            self._stderr = stderr

        async def communicate(self, input: bytes | None = None) -> tuple[bytes, bytes]:
            captured.setdefault("inputs", []).append(input)
            args = captured["calls"][len(captured.setdefault("inputs", [])) - 1]
            if "--output-last-message" in args:
                output_index = args.index("--output-last-message") + 1
                Path(args[output_index]).write_text('{"summary":"ok-local"}', encoding="utf-8")
            return self._stdout, self._stderr

    async def _fake_create_subprocess_exec(*args, **kwargs):  # noqa: ANN002, ANN003
        captured.setdefault("calls", []).append(args)
        captured["cwd"] = kwargs.get("cwd")
        call_index = len(captured["calls"])
        if call_index == 1:
            return _FakeProcess(returncode=0, stdout=b"Logged in using ChatGPT\n")
        return _FakeProcess(returncode=0, stdout=b'{"type":"turn.completed"}\n')

    monkeypatch.setattr(codex_transport.httpx, "AsyncClient", _ForbiddenAsyncClient)
    monkeypatch.setattr(codex_transport.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    output = await codex_transport.run_codex_json(
        "hello local codex",
        config={"auth_mode": "local_codex", "model": "gpt-5.4", "timeout_sec": 9, "cwd": str(tmp_path)},
    )

    assert output == {"summary": "ok-local"}
    assert captured["cwd"] == str(tmp_path)
    login_call = captured["calls"][0]
    exec_call = captured["calls"][1]
    assert login_call[:3] == ("codex", "login", "status")
    assert exec_call[0:2] == ("codex", "exec")
    assert "--skip-git-repo-check" in exec_call
    assert "--output-last-message" in exec_call
    assert b"hello local codex" in captured["inputs"][1]
