from __future__ import annotations

import pytest

from app.providers import llm_chat


class _FakeResponse:
    def __init__(self) -> None:
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"choices": [{"message": {"content": '{"summary":"ok"}'}}]}


@pytest.mark.asyncio
async def test_run_llm_json_uses_120_second_default_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
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

    monkeypatch.setattr(llm_chat.httpx, "AsyncClient", _FakeAsyncClient)

    output = await llm_chat.run_llm_json("hello", config={"api_key": "sk-demo"})

    assert output == {"summary": "ok"}
    assert captured["timeout"] == 120.0

