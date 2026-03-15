"""Execute a DeerFlow research turn inside DeerFlow's own Python environment."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


async def _run(payload: dict) -> str:
    config_path = Path(str(payload["config_path"])).expanduser().resolve()
    deerflow_root = config_path.parent
    backend_path = deerflow_root / "backend"
    sys.path.insert(0, str(backend_path))

    from dotenv import load_dotenv
    from langchain_core.messages import HumanMessage
    from src.client import DeerFlowClient

    load_dotenv(deerflow_root / ".env")

    client = DeerFlowClient(
        config_path=str(config_path),
        thinking_enabled=bool(payload.get("thinking_enabled", True)),
        subagent_enabled=bool(payload.get("subagent_enabled", False)),
        plan_mode=bool(payload.get("plan_mode", False)),
    )
    thread_id = str(payload["thread_id"])
    config = client._get_runnable_config(thread_id)
    client._ensure_agent(config)
    state = {"messages": [HumanMessage(content=str(payload["prompt"]))]}
    context = {"thread_id": thread_id}
    result = await client._agent.ainvoke(state, config=config, context=context)
    messages = result.get("messages", [])
    if not messages:
        return ""
    return str(getattr(messages[-1], "content", "") or "")


def main() -> int:
    payload = json.loads(sys.stdin.read())
    text = asyncio.run(_run(payload))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
