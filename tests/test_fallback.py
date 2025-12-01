"""
Tests for LLM rate limit fallback functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from magi.rate_limit import is_rate_limited, extract_retry_time, check_rate_limit
from magi.fallback_manager import FallbackManager, Role, LLMName
from magi.clients import CodexClient, ClaudeClient, GeminiClient


class TestRateLimitDetection:
    """Tests for rate limit detection."""

    def test_is_rate_limited_usage_limit(self):
        """Test detection of usage limit error."""
        error_msg = "ERROR: You've hit your usage limit. Upgrade to Pro"
        assert is_rate_limited(error_msg) is True

    def test_is_rate_limited_quota_exceeded(self):
        """Test detection of quota exceeded error."""
        error_msg = "quota exceeded for this month"
        assert is_rate_limited(error_msg) is True

    def test_is_rate_limited_rate_limit(self):
        """Test detection of rate limit error."""
        error_msg = "rate limit: too many requests"
        assert is_rate_limited(error_msg) is True

    def test_is_rate_limited_credits(self):
        """Test detection of credits error."""
        error_msg = "insufficient credits to complete this request"
        assert is_rate_limited(error_msg) is True

    def test_is_rate_limited_upgrade(self):
        """Test detection of upgrade required error."""
        error_msg = "upgrade to pro to continue"
        assert is_rate_limited(error_msg) is True

    def test_is_not_rate_limited(self):
        """Test that non-rate-limit errors are not detected."""
        error_msg = "connection timeout"
        assert is_rate_limited(error_msg) is False

    def test_check_rate_limit(self):
        """Test check_rate_limit function."""
        error_msg = "ERROR: You've hit your usage limit. Upgrade to Pro"
        info = check_rate_limit(error_msg, "codex")
        assert info.is_rate_limited is True
        assert info.service_name == "codex"


class TestFallbackManager:
    """Tests for fallback manager."""

    @pytest.fixture
    def fallback_manager(self):
        """Create a fallback manager with mock clients."""
        codex_client = MagicMock(spec=CodexClient)
        codex_client.model_name = "codex"
        claude_client = MagicMock(spec=ClaudeClient)
        claude_client.model_name = "claude"
        gemini_client = MagicMock(spec=GeminiClient)
        gemini_client.model_name = "gemini"
        return FallbackManager(codex_client, claude_client, gemini_client)

    def test_mark_rate_limited(self, fallback_manager):
        """Test marking an LLM as rate limited."""
        fallback_manager.mark_rate_limited("codex")
        assert fallback_manager.is_rate_limited("codex") is True
        assert fallback_manager.is_rate_limited("claude") is False

    def test_get_available_llms(self, fallback_manager):
        """Test getting available LLMs."""
        fallback_manager.mark_rate_limited("codex")
        available = fallback_manager.get_available_llms()
        assert "codex" not in available
        assert "claude" in available
        assert "gemini" in available

    def test_get_fallback_client_execution(self, fallback_manager):
        """Test getting fallback client for execution role."""
        fallback_manager.mark_rate_limited("codex")
        client, info = fallback_manager.get_fallback_client(Role.EXECUTION, "codex")
        assert client is not None
        assert info is not None
        assert info.fallback_llm == "claude"  # Claude優先

    def test_get_fallback_client_evaluation(self, fallback_manager):
        """Test getting fallback client for evaluation role."""
        fallback_manager.mark_rate_limited("claude")
        client, info = fallback_manager.get_fallback_client(Role.EVALUATION, "claude")
        assert client is not None
        assert info is not None
        assert info.fallback_llm == "codex"  # Codex優先

    def test_get_fallback_client_exploration(self, fallback_manager):
        """Test getting fallback client for exploration role."""
        fallback_manager.mark_rate_limited("gemini")
        client, info = fallback_manager.get_fallback_client(Role.EXPLORATION, "gemini")
        assert client is not None
        assert info is not None
        assert info.fallback_llm == "claude"  # Claude優先

    def test_get_single_llm_for_all_roles(self, fallback_manager):
        """Test getting single LLM for all roles."""
        fallback_manager.mark_rate_limited("codex")
        fallback_manager.mark_rate_limited("claude")
        client, infos = fallback_manager.get_single_llm_for_all_roles()
        assert client is not None
        assert client.model_name == "gemini"
        assert len(infos) == 2  # ExecutionとEvaluationのフォールバック情報

    def test_get_single_llm_all_limited(self, fallback_manager):
        """Test when all LLMs are rate limited."""
        fallback_manager.mark_rate_limited("codex")
        fallback_manager.mark_rate_limited("claude")
        fallback_manager.mark_rate_limited("gemini")
        client, infos = fallback_manager.get_single_llm_for_all_roles()
        assert client is None
        assert len(infos) == 0

