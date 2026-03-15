"""Registry for research agent runtimes."""

from __future__ import annotations

from app.agents.base import ResearchAgentRuntime
from app.agents.deerflow_embedded import DeerFlowEmbeddedRuntime
from app.agents.deerflow_subprocess import DeerFlowSubprocessRuntime

_REGISTRY: dict[str, type[ResearchAgentRuntime]] = {
    "deerflow_embedded": DeerFlowEmbeddedRuntime,
    "deerflow_subprocess": DeerFlowSubprocessRuntime,
}


def get_agent(name: str, config: dict | None = None) -> ResearchAgentRuntime:
    try:
        runtime_cls = _REGISTRY[name]
    except KeyError as exc:
        available = sorted(_REGISTRY.keys())
        raise ValueError(f"Unknown research agent: {name} (available={available})") from exc
    return runtime_cls(config=config)
