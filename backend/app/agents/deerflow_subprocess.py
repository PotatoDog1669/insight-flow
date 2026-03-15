"""DeerFlow runtime executed in DeerFlow's own Python environment."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.agents.base import ResearchAgentRuntime
from app.agents.deerflow_embedded import DeerFlowEmbeddedRuntime
from app.agents.schemas import ResearchJob, ResearchResult
from app.config import PROJECT_ROOT


async def _run_deerflow_subprocess(*, script_path: Path, python_bin: Path, payload: dict) -> str:
    process = await asyncio.create_subprocess_exec(
        str(python_bin),
        str(script_path),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip() or stdout.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or f"DeerFlow subprocess failed with exit code {process.returncode}")
    return stdout.decode("utf-8", errors="replace").strip()


class DeerFlowSubprocessRuntime(ResearchAgentRuntime):
    """Research runtime that uses DeerFlow's own .venv and async agent execution."""

    name = "deerflow_subprocess"

    def __init__(self, config: dict | None = None) -> None:
        self.config = dict(config or {})

    async def run(self, job: ResearchJob) -> ResearchResult:
        payload = {
            "config_path": str(self._config_path()),
            "thread_id": job.job_id,
            "thinking_enabled": bool(self.config.get("thinking_enabled", True)),
            "subagent_enabled": bool(self.config.get("subagent_enabled", False)),
            "plan_mode": bool(self.config.get("plan_mode", False)),
            "prompt": DeerFlowEmbeddedRuntime._build_prompt(job),
        }
        raw_text = await _run_deerflow_subprocess(
            script_path=self._script_path(),
            python_bin=self._python_bin(),
            payload=payload,
        )
        return DeerFlowEmbeddedRuntime(config={})._normalize_response(job=job, raw_text=raw_text)

    def _config_path(self) -> Path:
        value = str(self.config.get("config_path") or "").strip()
        if not value:
            raise RuntimeError("deerflow subprocess runtime requires research.agents.deerflow_subprocess.config_path")
        return Path(value).expanduser().resolve()

    def _python_bin(self) -> Path:
        configured = str(self.config.get("python_bin") or "").strip()
        if configured:
            return Path(configured).expanduser().resolve()
        return self._config_path().parent / "backend" / ".venv" / "bin" / "python"

    @staticmethod
    def _script_path() -> Path:
        return PROJECT_ROOT / "backend" / "app" / "agents" / "scripts" / "run_deerflow_research.py"
