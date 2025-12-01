"""
Fallback manager for handling LLM rate limits.

When an LLM hits its usage limit, this module manages fallback to other LLMs
to ensure the system continues to function.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from magi.clients.base_client import BaseLLMClient
from magi.rate_limit import check_rate_limit, RateLimitInfo
from magi.prompts import build_fallback_prompt


# 役割の定義
class Role:
    """Role enumeration for Proposal Battle mode."""

    EXECUTION = "execution"  # Codexの役割
    EVALUATION = "evaluation"  # Claudeの役割
    EXPLORATION = "exploration"  # Geminiの役割


# LLM名の定義
class LLMName:
    """LLM name constants."""

    CODEX = "codex"
    CLAUDE = "claude"
    GEMINI = "gemini"


# フォールバック優先順位（Claude優先）
FALLBACK_PRIORITY: Dict[str, List[str]] = {
    Role.EXECUTION: [LLMName.CLAUDE, LLMName.GEMINI],  # Codex制限時: Claude → Gemini
    Role.EVALUATION: [LLMName.CODEX, LLMName.GEMINI],  # Claude制限時: Codex → Gemini
    Role.EXPLORATION: [LLMName.CLAUDE, LLMName.CODEX],  # Gemini制限時: Claude → Codex
}


@dataclass
class FallbackInfo:
    """Information about a fallback operation."""

    original_llm: str  # 元のLLM名
    fallback_llm: str  # フォールバック先のLLM名
    role: str  # 役割名
    reason: str  # フォールバック理由


class FallbackManager:
    """Manages fallback logic when LLMs hit rate limits."""

    def __init__(
        self,
        codex_client: BaseLLMClient,
        claude_client: BaseLLMClient,
        gemini_client: BaseLLMClient,
    ):
        self.codex_client = codex_client
        self.claude_client = claude_client
        self.gemini_client = gemini_client

        # LLM名からクライアントへのマッピング
        self.clients: Dict[str, BaseLLMClient] = {
            LLMName.CODEX: codex_client,
            LLMName.CLAUDE: claude_client,
            LLMName.GEMINI: gemini_client,
        }

        # 利用制限に達したLLMのリスト
        self.rate_limited_llms: List[str] = []

    def check_rate_limit(self, error_message: str, llm_name: str) -> RateLimitInfo:
        """
        Check if an error indicates rate limiting.

        Args:
            error_message: Error message from the LLM
            llm_name: Name of the LLM

        Returns:
            RateLimitInfo object
        """
        return check_rate_limit(error_message, llm_name)

    def mark_rate_limited(self, llm_name: str) -> None:
        """
        Mark an LLM as rate limited.

        Args:
            llm_name: Name of the LLM to mark
        """
        if llm_name not in self.rate_limited_llms:
            self.rate_limited_llms.append(llm_name)

    def is_rate_limited(self, llm_name: str) -> bool:
        """
        Check if an LLM is rate limited.

        Args:
            llm_name: Name of the LLM to check

        Returns:
            True if rate limited, False otherwise
        """
        return llm_name in self.rate_limited_llms

    def get_available_llms(self) -> List[str]:
        """
        Get list of LLMs that are not rate limited.

        Returns:
            List of available LLM names
        """
        return [llm for llm in [LLMName.CODEX, LLMName.CLAUDE, LLMName.GEMINI] if not self.is_rate_limited(llm)]

    def get_fallback_client(
        self, role: str, original_llm: str
    ) -> Tuple[Optional[BaseLLMClient], Optional[FallbackInfo]]:
        """
        Get a fallback client for a given role when the original LLM is rate limited.

        Args:
            role: The role to fulfill ("execution", "evaluation", "exploration")
            original_llm: The original LLM that was rate limited

        Returns:
            Tuple of (fallback_client, fallback_info) or (None, None) if no fallback available
        """
        if not self.is_rate_limited(original_llm):
            # 元のLLMが利用可能な場合はNoneを返す
            return None, None

        # フォールバック優先順位を取得
        fallback_candidates = FALLBACK_PRIORITY.get(role, [])

        # 利用可能なLLMからフォールバック先を選択
        for candidate in fallback_candidates:
            if not self.is_rate_limited(candidate) and candidate in self.clients:
                fallback_info = FallbackInfo(
                    original_llm=original_llm,
                    fallback_llm=candidate,
                    role=role,
                    reason=f"{original_llm} is rate limited, using {candidate} as fallback",
                )
                return self.clients[candidate], fallback_info

        # フォールバック先が見つからない場合
        return None, None

    def get_single_llm_for_all_roles(self) -> Optional[Tuple[BaseLLMClient, List[FallbackInfo]]]:
        """
        Get a single LLM that can handle all three roles when multiple LLMs are rate limited.

        This is used when 2 out of 3 LLMs are rate limited, and we need one LLM
        to handle all three roles independently.

        Returns:
            Tuple of (client, fallback_infos) or (None, []) if no LLM is available
        """
        available_llms = self.get_available_llms()

        if len(available_llms) == 0:
            # 全てのLLMが利用制限に達している
            return None, []

        if len(available_llms) == 1:
            # 1つのLLMのみが利用可能
            llm_name = available_llms[0]
            client = self.clients[llm_name]

            # 3つの役割すべてをこのLLMが代行する
            fallback_infos = []
            for role in [Role.EXECUTION, Role.EVALUATION, Role.EXPLORATION]:
                original_llm = self._get_original_llm_for_role(role)
                if original_llm != llm_name:
                    fallback_infos.append(
                        FallbackInfo(
                            original_llm=original_llm,
                            fallback_llm=llm_name,
                            role=role,
                            reason=f"{original_llm} is rate limited, using {llm_name} as fallback for {role}",
                        )
                    )

            return client, fallback_infos

        # 複数のLLMが利用可能な場合はNoneを返す（通常のフォールバックを使用）
        return None, []

    def _get_original_llm_for_role(self, role: str) -> str:
        """
        Get the original LLM name for a given role.

        Args:
            role: The role name

        Returns:
            Original LLM name for the role
        """
        role_to_llm = {
            Role.EXECUTION: LLMName.CODEX,
            Role.EVALUATION: LLMName.CLAUDE,
            Role.EXPLORATION: LLMName.GEMINI,
        }
        return role_to_llm.get(role, "")

    def build_fallback_prompt(self, role: str, fallback_llm: str, context: str) -> str:
        """
        Build a prompt for a fallback LLM to take over a role.

        Args:
            role: The role to take over
            fallback_llm: The LLM that will take over
            context: The task or previous output

        Returns:
            Formatted prompt string
        """
        return build_fallback_prompt(fallback_llm, role, context)

    def reset(self) -> None:
        """Reset the rate limited LLMs list."""
        self.rate_limited_llms.clear()

