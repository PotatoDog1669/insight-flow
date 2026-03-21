"""Paper review stage providers."""

from __future__ import annotations

from app.providers.base import BaseStageProvider
from app.providers.registry import register


@register(stage="paper_review", name="llm_openai")
class LLMPaperReviewProvider(BaseStageProvider):
    stage = "paper_review"
    name = "llm_openai"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        raise NotImplementedError("paper_review provider is implemented in a follow-up task")


@register(stage="paper_review", name="llm_codex")
class CodexPaperReviewProvider(BaseStageProvider):
    stage = "paper_review"
    name = "llm_codex"

    async def run(self, payload: dict, config: dict | None = None) -> dict:
        raise NotImplementedError("paper_review provider is implemented in a follow-up task")
