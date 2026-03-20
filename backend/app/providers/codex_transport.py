"""Codex JSON helpers via OpenAI-compatible responses endpoint."""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from pathlib import Path

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
    auth_mode = str(cfg.get("auth_mode") or "api_key").strip() or "api_key"
    if auth_mode == "local_codex":
        return await _run_local_codex_json(prompt=prompt, config=cfg)

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


async def _run_local_codex_json(prompt: str, config: dict) -> dict:
    model = str(config.get("model") or settings.codex_model or "gpt-5-codex").strip() or "gpt-5-codex"
    timeout_sec = float(config.get("timeout_sec") or settings.codex_timeout_sec or 120)
    cwd = str(config.get("cwd") or os.getcwd()).strip() or os.getcwd()

    await _ensure_local_codex_login(timeout_sec=timeout_sec, cwd=cwd)

    temp_fd, temp_name = tempfile.mkstemp(prefix="codex-local-", suffix=".txt")
    os.close(temp_fd)
    temp_path = Path(temp_name)
    try:
        returncode, stdout_text, stderr_text = await _run_local_codex_command(
            "exec",
            "--skip-git-repo-check",
            "--json",
            "--output-last-message",
            str(temp_path),
            "-m",
            model,
            input_text=prompt,
            timeout_sec=timeout_sec,
            cwd=cwd,
        )
        if returncode != 0:
            raise RuntimeError(_format_local_codex_exec_error(stdout_text, stderr_text))
        response_text = temp_path.read_text(encoding="utf-8").strip() if temp_path.exists() else ""
        if not response_text:
            raise ValueError("Local Codex did not return a final message")
        parsed = _parse_json_text(response_text)
        if not isinstance(parsed, dict):
            raise ValueError("Codex JSON response must be an object")
        return parsed
    finally:
        temp_path.unlink(missing_ok=True)


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


async def _ensure_local_codex_login(*, timeout_sec: float, cwd: str) -> None:
    returncode, stdout_text, stderr_text = await _run_local_codex_command(
        "login",
        "status",
        timeout_sec=min(timeout_sec, 10.0),
        cwd=cwd,
    )
    status_text = f"{stdout_text}\n{stderr_text}".strip().lower()
    if returncode != 0 or "logged in" not in status_text:
        raise ValueError("Detected codex CLI, but the current machine is not logged in")


async def _run_local_codex_command(
    *args: str,
    input_text: str | None = None,
    timeout_sec: float,
    cwd: str,
) -> tuple[int, str, str]:
    try:
        process = await asyncio.create_subprocess_exec(
            "codex",
            *args,
            stdin=asyncio.subprocess.PIPE if input_text is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
    except FileNotFoundError as exc:
        raise ValueError("Local Codex CLI is not installed") from exc

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(input_text.encode("utf-8") if input_text is not None else None),
            timeout=timeout_sec,
        )
    except TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise RuntimeError(f"Local Codex call timed out ({int(timeout_sec)}s)") from exc

    return (
        process.returncode,
        stdout_bytes.decode("utf-8", errors="replace"),
        stderr_bytes.decode("utf-8", errors="replace"),
    )


def _format_local_codex_exec_error(stdout_text: str, stderr_text: str) -> str:
    detail = "\n".join(part.strip() for part in [stderr_text, stdout_text] if part.strip()).strip()
    if detail:
        return f"Local Codex execution failed: {detail}"
    return "Local Codex execution failed"


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
