from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Literal
import uuid
import time


# Phase 1: エラーハンドリングの型安全性向上
@dataclass
class LLMSuccess:
    """LLM呼び出しが成功した場合の結果"""
    model: str
    content: str
    duration_ms: float
    source: str  # wrapper url or cli command
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_model_output(self) -> "ModelOutput":
        """後方互換性のための変換メソッド"""
        return ModelOutput(
            model=self.model,
            content=self.content,
            metadata={
                **self.metadata,
                "status": "ok",
                "cli_type": "real",
                "duration_ms": str(self.duration_ms),
                "source": self.source,
            },
        )


@dataclass
class LLMFailure:
    """LLM呼び出しが失敗した場合の結果"""
    model: str
    error_type: Literal["timeout", "http_error", "cli_missing", "exception"]
    error_message: str
    duration_ms: float
    source: str  # wrapper url or cli command
    fallback_content: Optional[str] = None  # Stub content if available

    def to_model_output(self) -> "ModelOutput":
        """後方互換性のための変換メソッド"""
        content = self.fallback_content or f"Stub response for {self.model} ({self.error_message})"
        return ModelOutput(
            model=self.model,
            content=content,
            metadata={
                "status": "error",
                "cli_type": "stub" if self.fallback_content else "error",
                "error_type": self.error_type,
                "error": self.error_message,
                "duration_ms": str(self.duration_ms),
                "source": self.source,
            },
        )


# 型エイリアス: 成功または失敗のどちらか
LLMResult = LLMSuccess | LLMFailure


# 後方互換性のための既存のModelOutput（段階的移行のため保持）
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
