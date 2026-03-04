"""Base contracts for stage providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseStageProvider(ABC):
    """Stage provider contract."""

    stage: str
    name: str

    @abstractmethod
    async def run(self, payload: dict, config: dict | None = None) -> dict:
        """Execute stage logic."""
        raise NotImplementedError
