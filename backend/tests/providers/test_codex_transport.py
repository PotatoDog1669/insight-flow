from __future__ import annotations

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
