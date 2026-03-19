from __future__ import annotations

import httpx
import pytest

from app.providers.errors import ProviderUnavailableError
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


@pytest.mark.asyncio
async def test_run_llm_json_raises_unavailable_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_chat.settings, "openai_api_key", "")

    with pytest.raises(ProviderUnavailableError, match="missing_api_key"):
        await llm_chat.run_llm_json("hello", config={})


@pytest.mark.asyncio
async def test_run_llm_json_raises_unavailable_when_api_key_is_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_chat.settings, "openai_api_key", "")

    with pytest.raises(ProviderUnavailableError, match="placeholder_api_key"):
        await llm_chat.run_llm_json("hello", config={"api_key": "sk-your-openai-api-key"})


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403, 404])
async def test_run_llm_json_raises_unavailable_on_auth_or_missing_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
) -> None:
    class _FakeAsyncClient:
        def __init__(self, *, timeout: float, headers: dict[str, str]) -> None:
            self.timeout = timeout
            self.headers = headers

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def post(self, endpoint: str, json: dict) -> httpx.Response:
            return httpx.Response(
                status_code=status_code,
                request=httpx.Request("POST", endpoint),
            )

    monkeypatch.setattr(llm_chat.httpx, "AsyncClient", _FakeAsyncClient)

    with pytest.raises(ProviderUnavailableError) as exc_info:
        await llm_chat.run_llm_json("hello", config={"api_key": "sk-demo"})

    assert exc_info.value.status_code == status_code


@pytest.mark.asyncio
async def test_run_llm_json_keeps_timeout_as_retryable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeAsyncClient:
        def __init__(self, *, timeout: float, headers: dict[str, str]) -> None:
            self.timeout = timeout
            self.headers = headers

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def post(self, endpoint: str, json: dict) -> httpx.Response:
            raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(llm_chat.httpx, "AsyncClient", _FakeAsyncClient)

    with pytest.raises(httpx.ReadTimeout):
        await llm_chat.run_llm_json("hello", config={"api_key": "sk-demo"})
