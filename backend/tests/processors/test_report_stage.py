from __future__ import annotations

import pytest

from app.providers.errors import ProviderUnavailableError
from app.processors.report_stage import run_report_with_retry
from app.routing.schema import StageRoute


@pytest.mark.asyncio
async def test_run_report_with_retry_uses_fallback_provider_after_failure() -> None:
    calls: list[str] = []

    class _FailingProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            calls.append("primary")
            raise RuntimeError("boom")

    class _FallbackProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            calls.append("fallback")
            return {"title": "ok", "content": payload["content"], "global_tldr": "done"}

    def _get_provider(*, stage: str, name: str):  # noqa: ANN202
        assert stage == "report"
        if name == "llm_openai":
            return _FailingProvider()
        if name == "llm_backup":
            return _FallbackProvider()
        raise KeyError(name)

    result, provider_name = await run_report_with_retry(
        route=StageRoute(primary="llm_openai", fallback=["llm_backup"]),
        providers={
            "llm_openai": {"max_retry": 0},
            "llm_backup": {"max_retry": 0},
        },
        provider_overrides={},
        payload={"content": "hello"},
        provider_getter=_get_provider,
    )

    assert provider_name == "llm_backup"
    assert result["global_tldr"] == "done"
    assert calls == ["primary", "fallback"]


@pytest.mark.asyncio
async def test_run_report_with_retry_reraises_unavailable_llm_openai() -> None:
    calls: list[str] = []

    class _UnavailableProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            calls.append("primary")
            raise ProviderUnavailableError(provider="llm_openai", reason="auth_failed", status_code=401)

    class _FallbackProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            calls.append("fallback")
            return {"title": "ok", "content": payload["content"], "global_tldr": "done"}

    def _get_provider(*, stage: str, name: str):  # noqa: ANN202
        assert stage == "report"
        if name == "llm_openai":
            return _UnavailableProvider()
        if name == "llm_backup":
            return _FallbackProvider()
        raise KeyError(name)

    with pytest.raises(ProviderUnavailableError, match="auth_failed"):
        await run_report_with_retry(
            route=StageRoute(primary="llm_openai", fallback=["llm_backup"]),
            providers={
                "llm_openai": {"max_retry": 3},
                "llm_backup": {"max_retry": 0},
            },
            provider_overrides={},
            payload={"content": "hello"},
            provider_getter=_get_provider,
        )

    assert calls == ["primary"]
