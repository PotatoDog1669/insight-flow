from __future__ import annotations

import pytest

from app.providers.errors import ProviderUnavailableError
from app.processors.paper_note_stage import run_paper_note_with_retry
from app.routing.schema import StageRoute


@pytest.mark.asyncio
async def test_run_paper_note_with_retry_uses_fallback_provider_after_failure() -> None:
    calls: list[str] = []

    class _FailingProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            calls.append("primary")
            raise RuntimeError("boom")

    class _FallbackProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            calls.append("fallback")
            return {"title": "ok", "summary": "done", "core_contributions": ["one"]}

    def _get_provider(*, stage: str, name: str):  # noqa: ANN202
        assert stage == "paper_note"
        if name == "llm_openai":
            return _FailingProvider()
        if name == "llm_backup":
            return _FallbackProvider()
        raise KeyError(name)

    result, provider_name = await run_paper_note_with_retry(
        route=StageRoute(primary="llm_openai", fallback=["llm_backup"]),
        providers={
            "llm_openai": {"max_retry": 0},
            "llm_backup": {"max_retry": 0},
        },
        provider_overrides={},
        payload={"paper": {"paper_identity": "2603.12345", "title": "World Model Policy"}},
        provider_getter=_get_provider,
    )

    assert provider_name == "llm_backup"
    assert result["summary"] == "done"
    assert calls == ["primary", "fallback"]


@pytest.mark.asyncio
async def test_run_paper_note_with_retry_reraises_unavailable_llm_openai() -> None:
    calls: list[str] = []

    class _UnavailableProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            calls.append("primary")
            raise ProviderUnavailableError(provider="llm_openai", reason="auth_failed", status_code=401)

    class _FallbackProvider:
        async def run(self, payload: dict, config: dict | None = None) -> dict:
            calls.append("fallback")
            return {"title": "ok", "summary": "done", "core_contributions": ["one"]}

    def _get_provider(*, stage: str, name: str):  # noqa: ANN202
        assert stage == "paper_note"
        if name == "llm_openai":
            return _UnavailableProvider()
        if name == "llm_backup":
            return _FallbackProvider()
        raise KeyError(name)

    with pytest.raises(ProviderUnavailableError, match="auth_failed"):
        await run_paper_note_with_retry(
            route=StageRoute(primary="llm_openai", fallback=["llm_backup"]),
            providers={
                "llm_openai": {"max_retry": 2},
                "llm_backup": {"max_retry": 0},
            },
            provider_overrides={},
            payload={"paper": {"paper_identity": "2603.12345", "title": "World Model Policy"}},
            provider_getter=_get_provider,
        )

    assert calls == ["primary"]
