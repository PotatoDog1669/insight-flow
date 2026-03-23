"""Short-lived storage for monitor agent conversations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.schemas.monitor_agent import MonitorConversationState


class MonitorConversationStore(Protocol):
    async def create(self) -> MonitorConversationState: ...

    async def load(self, conversation_id: str) -> MonitorConversationState | None: ...

    async def save(self, state: MonitorConversationState) -> None: ...


class InMemoryMonitorConversationStore:
    def __init__(self, *, ttl_minutes: int = 60) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._states: dict[str, MonitorConversationState] = {}

    async def create(self) -> MonitorConversationState:
        state = MonitorConversationState(
            conversation_id=str(uuid.uuid4()),
            expires_at=datetime.now(UTC) + self._ttl,
        )
        self._states[state.conversation_id] = state
        return state

    async def load(self, conversation_id: str) -> MonitorConversationState | None:
        state = self._states.get(conversation_id)
        if state is None:
            return None
        if state.expires_at <= datetime.now(UTC):
            self._states.pop(conversation_id, None)
            return None
        return state

    async def save(self, state: MonitorConversationState) -> None:
        state.expires_at = datetime.now(UTC) + self._ttl
        self._states[state.conversation_id] = state


_STORE = InMemoryMonitorConversationStore()


def build_monitor_conversation_store() -> MonitorConversationStore:
    return _STORE
