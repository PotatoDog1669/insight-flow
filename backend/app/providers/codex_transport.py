"""Codex JSON helpers via OpenAI-compatible responses endpoint."""

from __future__ import annotations

import json
import re

import httpx

from app.config import settings


def build_codex_headers(config: dict | None = None) -> dict[str, str]:
    cfg = dict(config or {})
    api_key = str(cfg.get("api_key") or settings.codex_api_key or settings.openai_api_key or "").strip()
    if not api_key:
        raise ValueError("Missing codex api_key")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def run_codex_json(prompt: str, config: dict | None = None) -> dict:
    cfg = dict(config or {})
    base_url = str(cfg.get("base_url") or settings.codex_base_url or "https://api.openai.com/v1").rstrip("/")
    model = str(cfg.get("model") or settings.codex_model or "gpt-5-codex").strip() or "gpt-5-codex"
    timeout_sec = float(cfg.get("timeout_sec") or settings.codex_timeout_sec or 120)
    max_tokens = int(cfg.get("max_output_tokens") or settings.llm_max_tokens or 2048)
    temperature = float(cfg.get("temperature") if cfg.get("temperature") is not None else settings.llm_temperature)

    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": str(prompt)}],
            }
        ],
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }

    headers = build_codex_headers(cfg)
    async with httpx.AsyncClient(timeout=timeout_sec, headers=headers) as client:
        response = await _post_responses_with_fallback(client=client, base_url=base_url, payload=payload)
        data = response.json() or {}
        text = _extract_response_text(data)
        parsed = _parse_json_text(text)
        if not isinstance(parsed, dict):
            raise ValueError("Codex JSON response must be an object")
        return parsed


async def _post_responses_with_fallback(client: httpx.AsyncClient, base_url: str, payload: dict) -> httpx.Response:
    endpoints = build_codex_response_endpoints(base_url)
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
    if last_error:
        raise last_error
    raise RuntimeError("No codex responses endpoint available")


def build_codex_response_endpoints(base_url: str) -> list[str]:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        return ["https://api.openai.com/v1/responses"]
    endpoints = [f"{base}/responses"]
    if not base.endswith("/v1"):
        endpoints.append(f"{base}/v1/responses")
    deduped: list[str] = []
    for endpoint in endpoints:
        if endpoint not in deduped:
            deduped.append(endpoint)
    return deduped


def _extract_response_text(data: dict) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    output = data.get("output")
    chunks: list[str] = []
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for segment in content:
                if not isinstance(segment, dict):
                    continue
                text = segment.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
    if chunks:
        return "\n".join(chunks).strip()
    raise ValueError("Codex response does not contain output text")


def _parse_json_text(raw_text: str) -> dict:
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("Empty codex response text")

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

    raise ValueError("Unable to parse JSON object from codex response")
