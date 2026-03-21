"""Paper note stage providers."""

from __future__ import annotations

from app.providers.base import BaseStageProvider
from app.providers.registry import register


@register(stage="paper_note", name="llm_openai")
class LLMPaperNoteProvider(BaseStageProvider):
    stage = "paper_note"
    name = "llm_openai"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        raise NotImplementedError("paper_note provider is implemented in a follow-up task")


@register(stage="paper_note", name="llm_codex")
class CodexPaperNoteProvider(BaseStageProvider):
    stage = "paper_note"
    name = "llm_codex"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        raise NotImplementedError("paper_note provider is implemented in a follow-up task")
