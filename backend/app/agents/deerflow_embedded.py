"""Embedded DeerFlow research runtime."""

from __future__ import annotations

import asyncio
import importlib
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import structlog

from app.agents.base import ResearchAgentRuntime
from app.agents.schemas import ResearchJob, ResearchResult, ResearchSource

logger = structlog.get_logger()

_JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def _load_deerflow_client_class(config_path: str | None):
    config_text = str(config_path or "").strip()
    if not config_text:
        raise RuntimeError("deerflow embedded runtime requires config_path")
    config_file = Path(config_text).expanduser()
    backend_path = config_file.resolve().parent / "backend"
    if not backend_path.exists():
        raise RuntimeError(f"DeerFlow backend path not found: {backend_path}")
    backend_str = str(backend_path)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)
    module = importlib.import_module("src.client")
    return getattr(module, "DeerFlowClient")


class DeerFlowEmbeddedRuntime(ResearchAgentRuntime):
    """Research runtime that embeds DeerFlowClient in-process."""

    name = "deerflow_embedded"

    def __init__(self, config: dict | None = None) -> None:
        self.config = dict(config or {})
        self._client: Any | None = None

    async def run(self, job: ResearchJob) -> ResearchResult:
        prompt = self._build_prompt(job)
        client = self._get_client()
        response_text = await asyncio.to_thread(client.chat, prompt, thread_id=job.job_id)
        return self._normalize_response(job=job, raw_text=str(response_text or ""))

    def _get_client(self):
        if self._client is not None:
            return self._client

        config_path = str(self.config.get("config_path") or "").strip()
        if not config_path:
            raise RuntimeError("deerflow embedded runtime requires research.agents.deerflow_embedded.config_path")

        try:
            client_cls = _load_deerflow_client_class(config_path)
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "DeerFlow dependencies are not available in the current Python environment. "
                "Install DeerFlow dependencies into the active interpreter, or switch this runtime to execute "
                "within DeerFlow's own environment."
            ) from exc
        self._client = client_cls(
            config_path=config_path,
            thinking_enabled=bool(self.config.get("thinking_enabled", True)),
            subagent_enabled=bool(self.config.get("subagent_enabled", False)),
            plan_mode=bool(self.config.get("plan_mode", False)),
        )
        return self._client

    @staticmethod
    def _build_prompt(job: ResearchJob) -> str:
        payload = {
            "task": "research_event",
            "template": job.template,
            "frequency": job.frequency,
            "event": asdict(job.event),
            "focus_questions": list(job.focus_questions),
            "constraints": {
                "must_verify": job.must_verify,
                "max_sources": job.max_sources,
                "include_timeline": job.include_timeline,
                "include_competitive_context": job.include_competitive_context,
            },
            "output_format": {
                "type": "json",
                "keys": ["title", "summary", "content_markdown", "sources", "confidence", "artifacts", "metadata"],
            },
        }
        return (
            "Research the following event. Use the enabled skills and available tools to produce a structured deep "
            "research result. Prioritize the provided event details and source links. Only use web search when "
            "needed to verify, cross-check, or fill important gaps. Return JSON only.\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    def _normalize_response(self, *, job: ResearchJob, raw_text: str) -> ResearchResult:
        payload = self._parse_payload(raw_text)
        if payload is None:
            return ResearchResult(
                title=job.event.title,
                summary="",
                content_markdown=raw_text.strip(),
                sources=[],
                confidence_level="unknown",
                confidence_reason="",
                artifacts=[],
                metadata={},
                raw_response={},
            )

        content_markdown = str(
            payload.get("content_markdown") or payload.get("content") or payload.get("output") or ""
        ).strip()
        raw_sources = payload.get("sources")
        sources: list[ResearchSource] = []
        if isinstance(raw_sources, list):
            for item in raw_sources:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url") or "").strip()
                if not url:
                    continue
                sources.append(
                    ResearchSource(
                        title=str(item.get("title") or url).strip() or url,
                        url=url,
                        source_type=str(item.get("source_type") or "unknown").strip() or "unknown",
                    )
                )

        confidence = payload.get("confidence")
        confidence_dict = confidence if isinstance(confidence, dict) else {}
        metadata = payload.get("metadata")
        metadata_dict = metadata if isinstance(metadata, dict) else {}
        raw_artifacts = payload.get("artifacts")
        artifacts = [str(item).strip() for item in raw_artifacts] if isinstance(raw_artifacts, list) else []

        return ResearchResult(
            title=str(payload.get("title") or job.event.title).strip() or job.event.title,
            summary=str(payload.get("summary") or "").strip(),
            content_markdown=content_markdown,
            sources=sources,
            confidence_level=str(confidence_dict.get("level") or "unknown").strip() or "unknown",
            confidence_reason=str(confidence_dict.get("reason") or "").strip(),
            artifacts=[item for item in artifacts if item],
            metadata=metadata_dict,
            raw_response=payload,
        )

    @staticmethod
    def _parse_payload(raw_text: str) -> dict[str, Any] | None:
        text = raw_text.strip()
        if not text:
            return None
        candidates = [text]
        match = _JSON_BLOCK_PATTERN.search(text)
        if match:
            candidates.insert(0, match.group(1).strip())
        for candidate in candidates:
            try:
                data = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return data
        logger.warning("deerflow_embedded_non_json_response")
        return None
