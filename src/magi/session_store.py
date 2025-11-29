from __future__ import annotations

from typing import Dict, Optional

from magi.models import SessionState, ModelOutput


class InMemorySessionStore:
    def __init__(self) -> None:
        self._store: Dict[str, SessionState] = {}

    def create(self, mode: str) -> SessionState:
        state = SessionState.new(mode=mode)
        self._store[state.session_id] = state
        return state

    def get(self, session_id: str) -> Optional[SessionState]:
        return self._store.get(session_id)

    def delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)

    def save_outputs(self, session_id: str, outputs: Dict[str, ModelOutput]) -> None:
        state = self._store.get(session_id)
        if not state:
            return
        state.last_outputs = outputs
