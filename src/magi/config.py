from __future__ import annotations

import os
import socket
import shlex
import shutil
from dataclasses import dataclass, field
from typing import Optional, List


DEFAULT_TIMEOUT = os.getenv("MAGI_TIMEOUT_DEFAULT") or os.getenv("LLM_TIMEOUT") or "600"


def _split_cmd(value: str) -> List[str]:
    return shlex.split(value) if value else []


def command_available(command: Optional[List[str]]) -> bool:
    if not command:
        return False
    program = command[0]
    if os.path.isabs(program):
        return os.path.exists(program) and os.access(program, os.X_OK)
    return shutil.which(program) is not None


def _preferred_wrapper_host() -> str:
    """
    Pick the host that should be used for wrapper URLs.

    - Inside Docker, host.docker.internal should resolve to the host.
    - On the host, host.docker.internal may not resolve, so fall back to localhost.
    """
    if os.path.exists("/.dockerenv"):
        return "host.docker.internal"
    try:
        socket.gethostbyname("host.docker.internal")
        return "host.docker.internal"
    except socket.gaierror:
        return "127.0.0.1"


def _default_wrapper_url(env_var: str, port: int) -> str:
    """
    Resolve a wrapper URL with environment override and host fallback.
    """
    if url := os.getenv(env_var):
        return url
    host = _preferred_wrapper_host()
    return f"http://{host}:{port}"


def _timeout_from_env(env_var: str, default: str = "120") -> float:
    """
    Resolve timeout seconds from env with a common fallback LLM_TIMEOUT.
    """
    base_default = default or DEFAULT_TIMEOUT
    return float(os.getenv(env_var, os.getenv("LLM_TIMEOUT", base_default)))


@dataclass
class LLMConfig:
    name: str
    cli_command: Optional[List[str]] = None
    base_url: Optional[str] = None
    timeout: float = 30.0

    @classmethod
    def for_codex(cls) -> "LLMConfig":
        return cls(
            name="codex",
            cli_command=_split_cmd(os.getenv("CODEX_COMMAND", "codex exec --skip-git-repo-check")),
            base_url=_default_wrapper_url("CODEX_WRAPPER_URL", 9001),
            timeout=_timeout_from_env("CODEX_TIMEOUT"),
        )

    @classmethod
    def for_claude(cls) -> "LLMConfig":
        return cls(
            name="claude",
            cli_command=_split_cmd(os.getenv("CLAUDE_COMMAND", "claude generate")),
            base_url=_default_wrapper_url("CLAUDE_WRAPPER_URL", 9002),
            timeout=_timeout_from_env("CLAUDE_TIMEOUT"),
        )

    @classmethod
    def for_gemini(cls) -> "LLMConfig":
        return cls(
            name="gemini",
            cli_command=_split_cmd(os.getenv("GEMINI_COMMAND", "gemini generate")),
            base_url=_default_wrapper_url("GEMINI_WRAPPER_URL", 9003),
            timeout=_timeout_from_env("GEMINI_TIMEOUT"),
        )

    @classmethod
    def for_judge(cls) -> "LLMConfig":
        return cls(
            name="judge",
            cli_command=_split_cmd(os.getenv("JUDGE_COMMAND", "judge generate")),
            base_url=_default_wrapper_url("JUDGE_WRAPPER_URL", 9004),
            timeout=_timeout_from_env("JUDGE_TIMEOUT"),
        )


@dataclass
class AppConfig:
    codex: LLMConfig = field(default_factory=LLMConfig.for_codex)
    claude: LLMConfig = field(default_factory=LLMConfig.for_claude)
    gemini: LLMConfig = field(default_factory=LLMConfig.for_gemini)
    judge: LLMConfig = field(default_factory=LLMConfig.for_judge)
    fallback_policy: str = "lenient"
    verbose_default: bool = True

    @classmethod
    def from_env(cls) -> "AppConfig":
        """
        環境変数から設定を読み込む
        
        Phase 1: pydantic-settingsを使用した新しい設定システムを統合
        （後方互換性を維持しながら、型安全性とバリデーションを向上）
        """
        try:
            # Phase 1: 新しい設定システムを使用（.envファイル対応、バリデーション付き）
            from magi.settings import Settings
            settings = Settings.from_env()
            return cls(
                codex=LLMConfig(**settings.get_codex_config()),
                claude=LLMConfig(**settings.get_claude_config()),
                gemini=LLMConfig(**settings.get_gemini_config()),
                judge=LLMConfig(**settings.get_judge_config()),
                fallback_policy=settings.get_fallback_policy(),
                verbose_default=settings.get_verbose_default(),
            )
        except ImportError:
            # pydantic-settingsがインストールされていない場合は既存の実装を使用
            return cls()
