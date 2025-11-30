"""
Phase 1: 設定管理の簡素化（pydantic-settings）

既存のAppConfig.from_env()を置き換え、型安全性とバリデーションを向上させます。
後方互換性を維持しながら改善します。
"""
from __future__ import annotations

import os
import socket
import shlex
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

from magi.config import (
    _preferred_wrapper_host,
    _split_cmd,
    _default_wrapper_url,
    _timeout_from_env,
    DEFAULT_TIMEOUT,
)

_ALLOWED_POLICIES = {"strict", "lenient"}


class LLMClientSettings(BaseSettings):
    """個別のLLMクライアント設定"""
    url: str
    timeout: float = Field(default=600.0, description="タイムアウト（秒）")
    command: Optional[str] = None
    
    model_config = SettingsConfigDict(
        env_prefix="",  # 環境変数のプレフィックスなし（個別に設定）
        case_sensitive=False,
    )


class Settings(BaseSettings):
    """アプリケーション全体の設定"""
    # Codex設定
    codex_url: str = Field(
        default_factory=lambda: f"http://{_preferred_wrapper_host()}:9001"
    )
    codex_timeout: float = Field(default=float(DEFAULT_TIMEOUT), description="Codexタイムアウト（秒）")
    codex_command: str = Field(default="codex exec --skip-git-repo-check")
    
    # Claude設定
    claude_url: str = Field(
        default_factory=lambda: f"http://{_preferred_wrapper_host()}:9002"
    )
    claude_timeout: float = Field(default=float(DEFAULT_TIMEOUT), description="Claudeタイムアウト（秒）")
    claude_command: str = Field(default="claude generate")
    
    # Gemini設定
    gemini_url: str = Field(
        default_factory=lambda: f"http://{_preferred_wrapper_host()}:9003"
    )
    gemini_timeout: float = Field(default=float(DEFAULT_TIMEOUT), description="Geminiタイムアウト（秒）")
    gemini_command: str = Field(default="gemini generate")
    
    # Judge設定
    judge_url: str = Field(
        default_factory=lambda: f"http://{_preferred_wrapper_host()}:9004"
    )
    judge_timeout: float = Field(default=float(DEFAULT_TIMEOUT), description="Judgeタイムアウト（秒）")
    judge_command: str = Field(default="judge generate")
    
    # 共通設定
    llm_timeout: float = Field(default=float(DEFAULT_TIMEOUT), description="全LLMのデフォルトタイムアウト（秒）")
    wrapper_timeout: float = Field(default=float(DEFAULT_TIMEOUT), description="ラッパーのタイムアウト（秒）")
    fallback_policy: str = Field(default="lenient", description="LLM失敗時のフォールバックポリシー (lenient|strict)")
    verbose_default: bool = Field(default=False, description="verboseレスポンスをデフォルトで有効にするか (MAGI_VERBOSE_DEFAULT)")
    
    # MAGI Consensus設定
    melchior_weight: float = Field(default=0.4, description="Melchior persona weight")
    balthasar_weight: float = Field(default=0.35, description="Balthasar persona weight")
    caspar_weight: float = Field(default=0.25, description="Caspar persona weight")
    conditional_weight: float = Field(default=0.3, description="Conditional vote weight")
    default_criticality: str = Field(default="NORMAL", description="Default criticality level (CRITICAL|NORMAL|LOW)")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 未知の環境変数を無視
    )
    
    @field_validator("codex_timeout", "claude_timeout", "gemini_timeout", "judge_timeout", "llm_timeout", "wrapper_timeout")
    @classmethod
    def validate_timeout(cls, v: float) -> float:
        """タイムアウト値のバリデーション"""
        if v <= 0:
            raise ValueError("timeout must be positive")
        if v > 1200:  # 20分を超える場合は警告
            import warnings
            warnings.warn(f"Timeout {v}s is very long, consider reducing it")
        return v
    
    def get_codex_config(self) -> dict:
        """Codex設定を取得（後方互換性のため）"""
        # 環境変数を優先（既存の動作を維持）
        timeout_val = _timeout_from_env("CODEX_TIMEOUT", str(self.codex_timeout))
        url = os.getenv("CODEX_WRAPPER_URL") or self.codex_url or _default_wrapper_url("CODEX_WRAPPER_URL", 9001)
        command = os.getenv("CODEX_COMMAND") or self.codex_command
        
        return {
            "name": "codex",
            "cli_command": _split_cmd(command),
            "base_url": url,
            "timeout": timeout_val,
        }
    
    def get_claude_config(self) -> dict:
        """Claude設定を取得（後方互換性のため）"""
        # 環境変数を優先（既存の動作を維持）
        timeout_val = _timeout_from_env("CLAUDE_TIMEOUT", str(self.claude_timeout))
        url = os.getenv("CLAUDE_WRAPPER_URL") or self.claude_url or _default_wrapper_url("CLAUDE_WRAPPER_URL", 9002)
        command = os.getenv("CLAUDE_COMMAND") or self.claude_command
        
        return {
            "name": "claude",
            "cli_command": _split_cmd(command),
            "base_url": url,
            "timeout": timeout_val,
        }
    
    def get_gemini_config(self) -> dict:
        """Gemini設定を取得（後方互換性のため）"""
        # 環境変数を優先（既存の動作を維持）
        timeout_val = _timeout_from_env("GEMINI_TIMEOUT", str(self.gemini_timeout))
        url = os.getenv("GEMINI_WRAPPER_URL") or self.gemini_url or _default_wrapper_url("GEMINI_WRAPPER_URL", 9003)
        command = os.getenv("GEMINI_COMMAND") or self.gemini_command
        
        return {
            "name": "gemini",
            "cli_command": _split_cmd(command),
            "base_url": url,
            "timeout": timeout_val,
        }
    
    def get_judge_config(self) -> dict:
        """Judge設定を取得（後方互換性のため）"""
        # 環境変数を優先（既存の動作を維持）
        timeout_val = _timeout_from_env("JUDGE_TIMEOUT", str(self.judge_timeout))
        url = os.getenv("JUDGE_WRAPPER_URL") or self.judge_url or _default_wrapper_url("JUDGE_WRAPPER_URL", 9004)
        command = os.getenv("JUDGE_COMMAND") or self.judge_command
        
        return {
            "name": "judge",
            "cli_command": _split_cmd(command),
            "base_url": url,
            "timeout": timeout_val,
        }
    
    def get_fallback_policy(self) -> str:
        """フォールバックポリシー（strict/lenient）を取得"""
        env_value = os.getenv("MAGI_FALLBACK_POLICY", self.fallback_policy)
        normalized = env_value.strip().lower()
        if normalized not in _ALLOWED_POLICIES:
            return "lenient"
        return normalized

    def get_verbose_default(self) -> bool:
        """verboseをデフォルトで有効にするか"""
        env_value = os.getenv("MAGI_VERBOSE_DEFAULT")
        if env_value is None:
            return bool(self.verbose_default)
        # accept truthy strings
        return env_value.strip().lower() in {"1", "true", "yes", "on"}
    
    @classmethod
    def from_env(cls) -> "Settings":
        """環境変数から設定を読み込む（後方互換性のため）"""
        return cls()
