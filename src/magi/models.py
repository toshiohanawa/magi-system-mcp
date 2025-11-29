from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional
import uuid


@dataclass
class ModelOutput:
    model: str
    content: str
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class SessionState:
    session_id: str
    mode: str
    last_outputs: Dict[str, ModelOutput] = field(default_factory=dict)

    @classmethod
    def new(cls, mode: str) -> "SessionState":
        return cls(session_id=str(uuid.uuid4()), mode=mode)
