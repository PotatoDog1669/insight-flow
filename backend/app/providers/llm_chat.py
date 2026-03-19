"""LLM JSON helpers via OpenAI-compatible chat/completions endpoint."""

from __future__ import annotations

import json
import re

import httpx

from app.config import settings
from app.providers.errors import ProviderUnavailableError


def build_llm_headers(config: dict | None = None) -> dict[str, str]:
    cfg = dict(config or {})
    api_key = str(cfg.get("api_key") or settings.openai_api_key or "").strip()
    if not api_key:
        raise ProviderUnavailableError(provider="llm_openai", reason="missing_api_key")
    if _looks_like_placeholder_api_key(api_key):
        raise ProviderUnavailableError(provider="llm_openai", reason="placeholder_api_key")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def run_llm_json(prompt: str, config: dict | None = None) -> dict:
    cfg = dict(config or {})
    base_url = str(cfg.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    model = str(cfg.get("model") or settings.llm_primary_model or "gpt-4o-mini").strip() or "gpt-4o-mini"
    timeout_sec = float(cfg.get("timeout_sec") or 120)
    max_tokens = int(cfg.get("max_output_tokens") or settings.llm_max_tokens or 2048)
    temperature = float(cfg.get("temperature") if cfg.get("temperature") is not None else settings.llm_temperature)

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": str(prompt)}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    headers = build_llm_headers(cfg)
    async with httpx.AsyncClient(timeout=timeout_sec, headers=headers) as client:
        try:
            response = await _post_chat_with_fallback(client=client, base_url=base_url, payload=payload)
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 401:
                raise ProviderUnavailableError(
                    provider="llm_openai",
                    reason="auth_failed",
                    status_code=status_code,
                ) from exc
            if status_code == 403:
                raise ProviderUnavailableError(
                    provider="llm_openai",
                    reason="forbidden",
                    status_code=status_code,
                ) from exc
            if status_code == 404:
                raise ProviderUnavailableError(
                    provider="llm_openai",
                    reason="endpoint_not_found",
                    status_code=status_code,
                ) from exc
            raise
        data = response.json() or {}
        text = _extract_chat_text(data)
        parsed = _parse_json_text(text)
        if not isinstance(parsed, dict):
            raise ValueError("LLM JSON response must be an object")
        return parsed


async def _post_chat_with_fallback(client: httpx.AsyncClient, base_url: str, payload: dict) -> httpx.Response:
    endpoints = build_llm_chat_endpoints(base_url)
    last_error: Exception | None = None
    for idx, endpoint in enumerate(endpoints):
        try:
            response = await client.post(endpoint, json=payload)
            if response.status_code == 404 and idx < len(endpoints) - 1:
                continue
            response.raise_for_status()
            return response
        except Exception as exc:
            last_error = exc
            if idx == len(endpoints) - 1:
                raise
            continue
    if last_error:
        raise last_error
    raise RuntimeError("No llm chat endpoint available")


def build_llm_chat_endpoints(base_url: str) -> list[str]:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        return ["https://api.openai.com/v1/chat/completions"]
    endpoints = [f"{base}/chat/completions"]
    if not base.endswith("/v1"):
        endpoints.append(f"{base}/v1/chat/completions")
    deduped: list[str] = []
    for endpoint in endpoints:
        if endpoint not in deduped:
            deduped.append(endpoint)
    return deduped


def _looks_like_placeholder_api_key(api_key: str) -> bool:
    normalized = str(api_key or "").strip().lower()
    if not normalized:
        return False
    return "your-openai-api-key" in normalized


def _extract_chat_text(data: dict) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("LLM chat response missing choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise ValueError("LLM chat response choice is invalid")
    message = first.get("message")
    if not isinstance(message, dict):
        raise ValueError("LLM chat response missing message")
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
        if chunks:
            return "\n".join(chunks).strip()
    raise ValueError("LLM chat response does not contain message content")


def _parse_json_text(raw_text: str) -> dict:
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("Empty llm response text")

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```json\s*(\{.*\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        parsed = json.loads(fenced.group(1))
        if isinstance(parsed, dict):
            return parsed

    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and first < last:
        parsed = json.loads(text[first : last + 1])
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("Unable to parse JSON object from llm response")
