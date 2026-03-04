from __future__ import annotations

import pytest

from app.config import settings
from app.providers.codex_agent import build_codex_headers, build_codex_response_endpoints


def test_codex_headers_supports_api_key_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "codex_auth_mode", "api_key")
    monkeypatch.setattr(settings, "codex_api_key", "sk-codex-api-key")
    monkeypatch.setattr(settings, "codex_oauth_token", "")
    monkeypatch.setattr(settings, "openai_api_key", "")

    headers = build_codex_headers({})

    assert headers["Authorization"] == "Bearer sk-codex-api-key"


def test_codex_headers_supports_oauth_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "codex_auth_mode", "oauth")
    monkeypatch.setattr(settings, "codex_oauth_token", "oauth-access-token")
    monkeypatch.setattr(settings, "codex_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "")

    headers = build_codex_headers({})

    assert headers["Authorization"] == "Bearer oauth-access-token"


def test_codex_headers_raises_when_selected_mode_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "codex_auth_mode", "oauth")
    monkeypatch.setattr(settings, "codex_oauth_token", "")
    monkeypatch.setattr(settings, "codex_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "")

    with pytest.raises(ValueError):
        build_codex_headers({})


def test_codex_response_endpoints_supports_base_url_without_v1() -> None:
    endpoints = build_codex_response_endpoints("https://gmn.chuangzuoli.com")
    assert endpoints[0] == "https://gmn.chuangzuoli.com/responses"
    assert endpoints[1] == "https://gmn.chuangzuoli.com/v1/responses"


def test_codex_response_endpoints_deduplicates_when_v1_already_present() -> None:
    endpoints = build_codex_response_endpoints("https://api.openai.com/v1")
    assert endpoints == ["https://api.openai.com/v1/responses"]
