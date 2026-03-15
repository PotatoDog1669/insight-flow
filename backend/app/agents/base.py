"""Base contracts for research agent runtimes."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.agents.schemas import ResearchJob, ResearchResult


class ResearchAgentRuntime(ABC):
    """Research agent runtime contract."""

    name: str

    @abstractmethod
    async def run(self, job: ResearchJob) -> ResearchResult:
        """Execute research for a single event."""
        raise NotImplementedError
