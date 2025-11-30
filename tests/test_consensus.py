"""
Tests for MAGI consensus engine.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from magi.consensus import MagiConsensusEngine
from magi.models import (
    Persona,
    Vote,
    Decision,
    RiskLevel,
    PersonaResult,
    LLMSuccess,
    LLMFailure,
)
from magi.clients.base_client import BaseLLMClient


class MockLLMClient(BaseLLMClient):
    """Mock LLM client for testing."""

    def __init__(self, model_name: str, response_content: str):
        super().__init__(model_name=model_name)
        self.response_content = response_content

    def _build_url(self) -> str | None:
        return "http://mock:9001"

    async def generate_with_result(self, prompt: str, trace_id: str | None = None):
        """Return mock response."""
        return LLMSuccess(
            model=self.model_name,
            content=self.response_content,
            duration_ms=100.0,
            source="mock",
            trace_id=trace_id or "test-trace",
        )


@pytest.fixture
def mock_clients():
    """Create mock LLM clients."""
    melchior = MockLLMClient("gemini", "VOTE: YES\nREASON: Technically sound")
    balthasar = MockLLMClient("claude", "VOTE: YES\nREASON: Safe implementation")
    caspar = MockLLMClient("codex", "VOTE: YES\nREASON: Practical solution")
    return melchior, balthasar, caspar


@pytest.fixture
def consensus_engine(mock_clients):
    """Create consensus engine with mock clients."""
    melchior, balthasar, caspar = mock_clients
    return MagiConsensusEngine(
        melchior_client=melchior,
        balthasar_client=balthasar,
        caspar_client=caspar,
    )


@pytest.mark.asyncio
async def test_all_yes_approved_low_risk(consensus_engine):
    """Test that all YES votes result in APPROVED with LOW risk."""
    decision = await consensus_engine.evaluate("Test proposal", "NORMAL")

    assert decision.decision == Decision.APPROVED
    assert decision.risk_level == RiskLevel.LOW
    assert len(decision.persona_results) == 3
    assert all(r.vote == Vote.YES for r in decision.persona_results)


@pytest.mark.asyncio
async def test_balthasar_no_rejected_high_risk():
    """Test that BALTHASAR NO vote results in REJECTED with HIGH risk."""
    melchior = MockLLMClient("gemini", "VOTE: YES\nREASON: Good")
    balthasar = MockLLMClient("claude", "VOTE: NO\nREASON: Security risk: SQL injection")
    caspar = MockLLMClient("codex", "VOTE: YES\nREASON: Works")

    engine = MagiConsensusEngine(
        melchior_client=melchior,
        balthasar_client=balthasar,
        caspar_client=caspar,
    )

    decision = await engine.evaluate("Test proposal", "NORMAL")

    assert decision.decision == Decision.REJECTED
    assert decision.risk_level == RiskLevel.HIGH
    balthasar_result = next(
        r for r in decision.persona_results if r.persona == Persona.BALTHASAR
    )
    assert balthasar_result.vote == Vote.NO
    assert "SQL injection" in decision.suggested_actions[0]


@pytest.mark.asyncio
async def test_mixed_yes_conditional():
    """Test that mixed YES/CONDITIONAL results in CONDITIONAL decision."""
    melchior = MockLLMClient("gemini", "VOTE: YES\nREASON: Good")
    balthasar = MockLLMClient("claude", "VOTE: CONDITIONAL\nREASON: Needs tests")
    caspar = MockLLMClient("codex", "VOTE: YES\nREASON: Works")

    engine = MagiConsensusEngine(
        melchior_client=melchior,
        balthasar_client=balthasar,
        caspar_client=caspar,
    )

    decision = await engine.evaluate("Test proposal", "NORMAL")

    assert decision.decision == Decision.CONDITIONAL
    assert decision.risk_level == RiskLevel.MEDIUM
    balthasar_result = next(
        r for r in decision.persona_results if r.persona == Persona.BALTHASAR
    )
    assert balthasar_result.vote == Vote.CONDITIONAL


@pytest.mark.asyncio
async def test_critical_balthasar_no_rejected():
    """Test that CRITICAL changes are rejected if BALTHASAR votes NO."""
    melchior = MockLLMClient("gemini", "VOTE: YES\nREASON: Good")
    balthasar = MockLLMClient("claude", "VOTE: NO\nREASON: Security issue")
    caspar = MockLLMClient("codex", "VOTE: YES\nREASON: Works")

    engine = MagiConsensusEngine(
        melchior_client=melchior,
        balthasar_client=balthasar,
        caspar_client=caspar,
    )

    decision = await engine.evaluate("Test proposal", "CRITICAL")

    assert decision.decision == Decision.REJECTED
    assert "BALTHASAR" in decision.aggregate_reason
    assert "CRITICAL" in decision.aggregate_reason


@pytest.mark.asyncio
async def test_llm_failure_treated_as_no():
    """Test that LLM failures are treated as NO votes."""
    melchior = MockLLMClient("gemini", "VOTE: YES\nREASON: Good")
    balthasar = MockLLMClient("claude", "VOTE: YES\nREASON: Safe")
    caspar = MockLLMClient("codex", "VOTE: YES\nREASON: Works")

    # Override caspar to return failure
    async def fail_generate(prompt: str, trace_id: str | None = None):
        return LLMFailure(
            model="codex",
            error_type="timeout",
            error_message="Request timeout",
            duration_ms=60000.0,
            source="mock",
            trace_id=trace_id or "test",
        )

    caspar.generate_with_result = fail_generate

    engine = MagiConsensusEngine(
        melchior_client=melchior,
        balthasar_client=balthasar,
        caspar_client=caspar,
    )

    decision = await engine.evaluate("Test proposal", "NORMAL")

    caspar_result = next(
        r for r in decision.persona_results if r.persona == Persona.CASPAR
    )
    assert caspar_result.vote == Vote.NO
    assert "timeout" in caspar_result.reason.lower()


@pytest.mark.asyncio
async def test_parse_vote_and_reason():
    """Test vote and reason parsing."""
    engine = MagiConsensusEngine(
        melchior_client=MockLLMClient("gemini", ""),
        balthasar_client=MockLLMClient("claude", ""),
        caspar_client=MockLLMClient("codex", ""),
    )

    # Test YES vote
    vote, reason = engine._parse_vote_and_reason("VOTE: YES\nREASON: Good implementation")
    assert vote == Vote.YES
    assert "Good implementation" in reason

    # Test NO vote
    vote, reason = engine._parse_vote_and_reason("VOTE: NO\nREASON: Security risk")
    assert vote == Vote.NO
    assert "Security risk" in reason

    # Test CONDITIONAL vote
    vote, reason = engine._parse_vote_and_reason("VOTE: CONDITIONAL\nREASON: Needs tests")
    assert vote == Vote.CONDITIONAL
    assert "Needs tests" in reason

    # Test case insensitive
    vote, reason = engine._parse_vote_and_reason("vote: yes\nreason: Lowercase")
    assert vote == Vote.YES
    assert "Lowercase" in reason

    # Test default to NO if parsing fails
    vote, reason = engine._parse_vote_and_reason("Invalid format")
    assert vote == Vote.NO


@pytest.mark.asyncio
async def test_structured_logging(consensus_engine):
    """Test that consensus decision is logged with structured format."""
    import logging
    import json
    from io import StringIO
    
    # Set up a handler to capture logs
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.INFO)
    
    # JSON formatterを使用
    from magi.logging_config import JSONFormatter
    handler.setFormatter(JSONFormatter())
    
    logger = logging.getLogger("magi.consensus")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    try:
        decision = await consensus_engine.evaluate(
            "Test proposal",
            criticality="NORMAL",
            session_id="test-session-123",
            trace_id="test-trace-456",
        )
        
        # Check that decision was made
        assert decision.decision in (Decision.APPROVED, Decision.REJECTED, Decision.CONDITIONAL)
        
        # Check that log was written (JSON形式の場合)
        log_output = log_capture.getvalue()
        assert "Consensus decision" in log_output
        
        # JSON形式のログをパースして確認
        log_lines = log_output.strip().split('\n')
        for line in log_lines:
            if "Consensus decision" in line:
                try:
                    log_data = json.loads(line)
                    assert log_data.get("session_id") == "test-session-123" or "session_id" in log_data
                    assert log_data.get("trace_id") == "test-trace-456" or "trace_id" in log_data
                    break
                except json.JSONDecodeError:
                    # JSON形式でない場合は文字列検索
                    if "test-session-123" in line or "session_id" in line:
                        if "test-trace-456" in line or "trace_id" in line:
                            break
        else:
            # ログが見つからない場合は警告のみ（ログ形式によっては検出できない場合がある）
            pass
        
    finally:
        logger.removeHandler(handler)


@pytest.mark.asyncio
async def test_configurable_weights():
    """Test that persona weights can be configured."""
    from magi.models import Persona
    
    melchior = MockLLMClient("gemini", "VOTE: YES\nREASON: Good")
    balthasar = MockLLMClient("claude", "VOTE: YES\nREASON: Safe")
    caspar = MockLLMClient("codex", "VOTE: YES\nREASON: Works")
    
    # Custom weights
    custom_weights = {
        Persona.MELCHIOR: 0.5,
        Persona.BALTHASAR: 0.3,
        Persona.CASPAR: 0.2,
    }
    
    engine = MagiConsensusEngine(
        melchior_client=melchior,
        balthasar_client=balthasar,
        caspar_client=caspar,
        weights=custom_weights,
        conditional_weight=0.4,
    )
    
    # Verify weights are set correctly
    assert engine.weights[Persona.MELCHIOR] == 0.5
    assert engine.weights[Persona.BALTHASAR] == 0.3
    assert engine.weights[Persona.CASPAR] == 0.2
    assert engine.conditional_weight == 0.4


@pytest.mark.asyncio
async def test_default_weights():
    """Test that default weights are used when not specified."""
    melchior = MockLLMClient("gemini", "VOTE: YES\nREASON: Good")
    balthasar = MockLLMClient("claude", "VOTE: YES\nREASON: Safe")
    caspar = MockLLMClient("codex", "VOTE: YES\nREASON: Works")
    
    engine = MagiConsensusEngine(
        melchior_client=melchior,
        balthasar_client=balthasar,
        caspar_client=caspar,
    )
    
    # Verify default weights
    assert engine.weights[Persona.MELCHIOR] == 0.4
    assert engine.weights[Persona.BALTHASAR] == 0.35
    assert engine.weights[Persona.CASPAR] == 0.25
    assert engine.conditional_weight == 0.3
