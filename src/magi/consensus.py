"""
MAGI Consensus Engine.

Orchestrates parallel LLM calls with persona-based evaluation,
aggregates votes, and produces explainable decisions.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Optional, Any

from magi.clients.base_client import BaseLLMClient
from magi.models import (
    Persona,
    Vote,
    Decision,
    RiskLevel,
    PersonaResult,
    MagiDecision,
    LLMResult,
    LLMSuccess,
    LLMFailure,
)
from magi.prompt_builder import build_persona_prompt, Persona as PersonaEnum
from magi.fallback_manager import FallbackManager, LLMName
from magi.rate_limit import check_rate_limit

logger = logging.getLogger(__name__)


class MagiConsensusEngine:
    """
    MAGI consensus engine that orchestrates three LLM personas
    and aggregates their votes into a final decision.
    """

    def __init__(
        self,
        melchior_client: BaseLLMClient,  # Gemini
        balthasar_client: BaseLLMClient,  # Claude
        caspar_client: BaseLLMClient,  # Codex
        weights: Optional[Dict[Persona, float]] = None,
        conditional_weight: Optional[float] = None,
    ) -> None:
        """
        Initialize the consensus engine.

        Args:
            melchior_client: Gemini client (scientist persona)
            balthasar_client: Claude client (safety persona)
            caspar_client: Codex client (pragmatist persona)
            weights: Persona weights for voting (default: MELCHIOR=0.4, BALTHASAR=0.35, CASPAR=0.25)
            conditional_weight: Weight for conditional votes (default: 0.3)
        """
        self.melchior_client = melchior_client
        self.balthasar_client = balthasar_client
        self.caspar_client = caspar_client

        # Default weights: scientist gets highest, safety is critical, pragmatist is lower
        self.weights = weights or {
            Persona.MELCHIOR: 0.4,
            Persona.BALTHASAR: 0.35,
            Persona.CASPAR: 0.25,
        }

        # Conditional vote weight (configurable)
        self.conditional_weight = conditional_weight if conditional_weight is not None else 0.3

        # フォールバックマネージャーを初期化
        # コンセンサスモードでは、caspar=Codex, balthasar=Claude, melchior=Gemini
        # FallbackManagerはBaseLLMClientを受け入れるため、直接渡す
        self.fallback_manager = FallbackManager(
            caspar_client,   # Codex
            balthasar_client,  # Claude
            melchior_client,   # Gemini
        )

    async def evaluate(
        self, 
        proposal: str, 
        criticality: str = "NORMAL",
        persona_overrides: Optional[Dict[Persona, str]] = None,
        session_id: str | None = None,
        trace_id: str | None = None,
        verbose: bool = False,
    ) -> MagiDecision | tuple[MagiDecision, list[Dict[str, Any]], str, list[str]]:
        """
        Evaluate a proposal using three personas in parallel.

        Args:
            proposal: The proposal to evaluate
            criticality: "CRITICAL" | "NORMAL" | "LOW"
            persona_overrides: Optional dict mapping Persona to override text
            session_id: Session ID for logging
            trace_id: Trace ID for logging
            verbose: If True, return detailed logs and timeline

        Returns:
            MagiDecision with final decision, risk level, and explanations
            If verbose=True, returns tuple of (MagiDecision, logs, summary, timeline)
        """
        logs: list[Dict[str, Any]] = []
        timeline: list[str] = []
        
        # Build persona prompts with optional overrides
        persona_overrides = persona_overrides or {}
        mel_prompt = build_persona_prompt(
            PersonaEnum.MELCHIOR, 
            proposal, 
            override=persona_overrides.get(Persona.MELCHIOR)
        )
        bal_prompt = build_persona_prompt(
            PersonaEnum.BALTHASAR, 
            proposal, 
            override=persona_overrides.get(Persona.BALTHASAR)
        )
        cas_prompt = build_persona_prompt(
            PersonaEnum.CASPAR, 
            proposal, 
            override=persona_overrides.get(Persona.CASPAR)
        )

        # Execute all three in parallel with fallback support
        logger.info("Starting parallel persona evaluation")
        if verbose:
            timeline.append(f"[start] parallel evaluation (trace_id={trace_id or 'unknown'})")
        
        # フォールバックマネージャーをリセット
        if self.fallback_manager:
            self.fallback_manager.reset()
        
        # 最初の並列実行
        results = await asyncio.gather(
            self.melchior_client.generate_with_result(mel_prompt, trace_id=trace_id),
            self.balthasar_client.generate_with_result(bal_prompt, trace_id=trace_id),
            self.caspar_client.generate_with_result(cas_prompt, trace_id=trace_id),
            return_exceptions=True,
        )
        
        # 利用制限をチェックしてフォールバックを実行
        logger.info(f"Before fallback: results types = {[type(r).__name__ for r in results]}")
        results = await self._apply_fallbacks(
            results,
            [Persona.MELCHIOR, Persona.BALTHASAR, Persona.CASPAR],
            [mel_prompt, bal_prompt, cas_prompt],
            proposal,
            trace_id,
            verbose,
            logs,
            timeline,
        )
        logger.info(f"After fallback: results types = {[type(r).__name__ for r in results]}")
        
        # Parse results with verbose logging (フォールバック後の結果を使用)
        mel_result = self._parse_persona_result(
            Persona.MELCHIOR, results[0], "melchior"
        )
        bal_result = self._parse_persona_result(
            Persona.BALTHASAR, results[1], "balthasar"
        )
        cas_result = self._parse_persona_result(
            Persona.CASPAR, results[2], "caspar"
        )

        if verbose:
            for result, persona_name in [
                (mel_result, "melchior"),
                (bal_result, "balthasar"),
                (cas_result, "caspar"),
            ]:
                logs.append({
                    "t": datetime.now(timezone.utc).isoformat(),
                    "persona": persona_name,
                    "vote": result.vote.value,
                    "reason": result.reason[:200],
                })
                timeline.append(
                    f"[{persona_name}] {result.vote.value} - {result.reason[:100]}"
                )

        persona_results = [mel_result, bal_result, cas_result]

        # Aggregate votes
        decision, aggregate_reason = self._aggregate_votes(
            persona_results, criticality
        )

        # Derive risk level
        risk_level = self._derive_risk_level(persona_results)

        # Compose suggested actions
        suggested_actions = self._compose_suggested_actions(
            persona_results, decision
        )

        # 構造化ロギング
        current_trace_id = trace_id or "unknown"
        logger.info(
            "Consensus decision",
            extra={
                "decision": decision.value,
                "risk_level": risk_level.value,
                "persona_results": [
                    {
                        "persona": r.persona.value,
                        "vote": r.vote.value,
                        "reason": r.reason[:200]  # 切り詰め
                    }
                    for r in persona_results
                ],
                "aggregate_reason": aggregate_reason,
                "criticality": criticality,
                "session_id": session_id or "unknown",
                "trace_id": current_trace_id,
            }
        )

        magi_decision = MagiDecision(
            decision=decision,
            risk_level=risk_level,
            persona_results=persona_results,
            aggregate_reason=aggregate_reason,
            suggested_actions=suggested_actions,
        )
        
        if verbose:
            summary = self._build_summary(persona_results, decision, risk_level)
            return magi_decision, logs, summary, timeline
        
        return magi_decision
    
    def _build_summary(
        self, 
        persona_results: list[PersonaResult], 
        decision: Decision, 
        risk_level: RiskLevel
    ) -> str:
        """Build a human-readable summary of the consensus evaluation."""
        parts = []
        for result in persona_results:
            parts.append(f"{result.persona.value}({result.vote.value})")
        return f"{decision.value} ({risk_level.value} risk): " + " -> ".join(parts)

    def _parse_persona_result(
        self, persona: Persona, result: LLMResult | Exception, model_name: str
    ) -> PersonaResult:
        """
        Parse LLM result into PersonaResult.

        Handles exceptions and stubbed outputs by mapping to NO vote.
        Provides detailed error information for debugging.
        """
        if isinstance(result, Exception):
            error_msg = str(result)
            error_type = type(result).__name__
            logger.error(
                f"{persona.value} evaluation failed with {error_type}: {error_msg}",
                exc_info=result if isinstance(result, Exception) else None,
            )
            return PersonaResult(
                persona=persona,
                vote=Vote.NO,
                reason=f"LLM error ({error_type}): {error_msg[:500]}",
            )

        if isinstance(result, LLMFailure):
            logger.warning(
                f"{persona.value} evaluation failed: {result.error_type} - {result.error_message}",
                extra={
                    "persona": persona.value,
                    "error_type": result.error_type,
                    "error_message": result.error_message,
                    "duration_ms": result.duration_ms,
                    "source": result.source,
                    "trace_id": result.trace_id,
                }
            )
            # より詳細なエラーメッセージ
            detailed_reason = (
                f"LLM {result.error_type}: {result.error_message}"
            )
            if result.duration_ms > 0:
                detailed_reason += f" (took {result.duration_ms:.0f}ms)"
            return PersonaResult(
                persona=persona,
                vote=Vote.NO,
                reason=detailed_reason,
            )

        if isinstance(result, LLMSuccess):
            try:
                # Parse VOTE, REASON, and OPTIONAL_NOTES from content
                vote, reason, optional_notes = self._parse_persona_output(result.content)
                logger.debug(
                    f"{persona.value} evaluation succeeded: {vote.value}",
                    extra={
                        "persona": persona.value,
                        "vote": vote.value,
                        "duration_ms": result.duration_ms,
                        "trace_id": result.trace_id,
                    }
                )
                return PersonaResult(
                    persona=persona, 
                    vote=vote, 
                    reason=reason,
                    optional_notes=optional_notes
                )
            except Exception as parse_error:
                logger.error(
                    f"Failed to parse {persona.value} result: {parse_error}",
                    exc_info=parse_error,
                )
                return PersonaResult(
                    persona=persona,
                    vote=Vote.NO,
                    reason=f"Failed to parse output: {str(parse_error)[:500]}",
                )

        # Fallback
        logger.error(f"Unknown result type for {persona.value}: {type(result)}")
        return PersonaResult(
            persona=persona,
            vote=Vote.NO,
            reason="Failed to parse persona result: unknown result type",
        )

    def _parse_persona_output(self, content: str) -> tuple[Vote, str, Optional[str]]:
        """
        Parse VOTE, REASON, and OPTIONAL_NOTES from LLM output with validation.

        Unified Persona Template (UPT) format:
        - VOTE: YES | NO | CONDITIONAL
        - REASON: (箇条書き)
        - OPTIONAL_NOTES: (optional)

        Case-insensitive, tolerant of order variations and whitespace.
        Defaults to NO vote if parsing fails.
        """
        # 出力長の検証
        if len(content) > 5000:
            logger.warning("LLM output exceeds expected length")
            return Vote.NO, "Output format validation failed: excessive length", None

        content_upper = content.upper()

        # Try to find VOTE with strict pattern matching (case-insensitive)
        vote_pattern = r"VOTE:\s*(YES|NO|CONDITIONAL)"
        vote_match = re.search(vote_pattern, content_upper)
        
        if not vote_match:
            logger.warning("VOTE format not found in LLM output")
            return Vote.NO, "Output format validation failed: VOTE not found", None

        # 投票の解析と検証
        vote_str = vote_match.group(1)
        try:
            vote = Vote[vote_str]
        except KeyError:
            logger.warning(f"Invalid VOTE value: {vote_str}")
            return Vote.NO, "Output format validation failed: invalid VOTE value", None

        # Try to find REASON (flexible pattern, handles whitespace variations)
        # REASON: 以降、OPTIONAL_NOTES: または終端までを取得
        reason_pattern = r"REASON:\s*(.+?)(?:\n\s*OPTIONAL_NOTES:|$)"
        reason_match = re.search(reason_pattern, content, re.DOTALL | re.IGNORECASE)
        
        if reason_match:
            reason = reason_match.group(1).strip()
            # 理由の長さ検証と切り詰め
            if len(reason) > 2000:
                logger.warning("REASON exceeds expected length, truncating")
                reason = reason[:2000] + "..."
        else:
            # Fallback: use content after VOTE line, before OPTIONAL_NOTES if present
            vote_end = vote_match.end()
            optional_start = re.search(r"OPTIONAL_NOTES:", content_upper)
            if optional_start:
                reason = content[vote_end:optional_start.start()].strip()[:500]
            else:
                reason = content[vote_end:].strip()[:500]
            if not reason:
                reason = "No reason provided"
            logger.warning("REASON format not found, using fallback")

        # Try to find OPTIONAL_NOTES (optional, may be missing)
        optional_pattern = r"OPTIONAL_NOTES:\s*(.+?)(?:\n\s*(?:VOTE|REASON):|$)"
        optional_match = re.search(optional_pattern, content, re.DOTALL | re.IGNORECASE)
        
        optional_notes = None
        if optional_match:
            optional_notes = optional_match.group(1).strip()
            # OPTIONAL_NOTESの長さ検証と切り詰め
            if len(optional_notes) > 1000:
                logger.warning("OPTIONAL_NOTES exceeds expected length, truncating")
                optional_notes = optional_notes[:1000] + "..."
            # 空文字列の場合はNoneに変換
            if not optional_notes:
                optional_notes = None

        return vote, reason, optional_notes

    def _aggregate_votes(
        self, persona_results: list[PersonaResult], criticality: str
    ) -> tuple[Decision, str]:
        """
        Aggregate persona votes into final decision.

        Uses weighted voting with criticality-based thresholds.
        """
        # Calculate weighted scores
        scores: Dict[Persona, float] = {}
        for result in persona_results:
            weight = self.weights.get(result.persona, 0.0)
            if result.vote == Vote.YES:
                scores[result.persona] = 1.0 * weight
            elif result.vote == Vote.NO:
                scores[result.persona] = -1.0 * weight
            elif result.vote == Vote.CONDITIONAL:
                scores[result.persona] = self.conditional_weight * weight
            else:
                scores[result.persona] = -1.0 * weight  # Default to NO

        total_score = sum(scores.values())

        # Criticality-based decision logic
        if criticality.upper() == "CRITICAL":
            # For critical changes, require all non-errored personas to vote YES or CONDITIONAL
            # and BALTHASAR MUST NOT be NO
            balthasar_result = next(
                (r for r in persona_results if r.persona == Persona.BALTHASAR), None
            )
            if balthasar_result and balthasar_result.vote == Vote.NO:
                reason = (
                    "CRITICAL change rejected: BALTHASAR (safety) voted NO. "
                    f"Reason: {balthasar_result.reason[:200]}"
                )
                return Decision.REJECTED, reason

            # Check if all non-errored personas approve
            all_approved = all(
                r.vote in (Vote.YES, Vote.CONDITIONAL)
                for r in persona_results
                if "error" not in r.reason.lower()
            )
            if not all_approved:
                reason = "CRITICAL change rejected: Not all personas approved"
                return Decision.REJECTED, reason

            reason = (
                f"CRITICAL change approved. All personas approved. "
                f"Score: {total_score:.2f}"
            )
            return Decision.APPROVED, reason

        # NORMAL or LOW criticality
        balthasar_result = next(
            (r for r in persona_results if r.persona == Persona.BALTHASAR), None
        )

        # If BALTHASAR votes NO, reject unless other personas strongly favor (higher threshold)
        if balthasar_result and balthasar_result.vote == Vote.NO:
            # Check if other personas strongly favor
            other_scores = sum(
                scores.get(p, 0)
                for p in scores.keys()
                if p != Persona.BALTHASAR
            )
            # BALTHASARがNOの場合は、他のペルソナが非常に強く賛成している場合のみ承認
            if other_scores < 0.7:  # より高い閾値が必要
                reason = (
                    f"Rejected: BALTHASAR (safety) voted NO. "
                    f"Reason: {balthasar_result.reason[:200]}"
                )
                return Decision.REJECTED, reason

        # Check for conditional votes first
        has_conditional = any(r.vote == Vote.CONDITIONAL for r in persona_results)
        
        # Normal aggregation
        if total_score >= 0.3:
            # CONDITIONALがある場合は、スコアが高くてもCONDITIONALを返す可能性がある
            # ただし、すべてYESの場合はAPPROVEDを返す
            all_yes = all(r.vote == Vote.YES for r in persona_results)
            if has_conditional and not all_yes:
                # CONDITIONALがある場合は、より低い閾値でCONDITIONALを返す
                if total_score < 0.8:
                    reason = (
                        f"CONDITIONAL approval. Score: {total_score:.2f}. "
                        "Some personas have conditions."
                    )
                    return Decision.CONDITIONAL, reason
            reason = f"Approved. Score: {total_score:.2f}"
            return Decision.APPROVED, reason
        elif total_score >= 0.0:
            # Slightly positive but low
            if has_conditional:
                reason = (
                    f"CONDITIONAL approval. Score: {total_score:.2f}. "
                    "Conditions must be met."
                )
                return Decision.CONDITIONAL, reason
            reason = f"Rejected. Score too low: {total_score:.2f}"
            return Decision.REJECTED, reason
        else:
            reason = f"Rejected. Negative score: {total_score:.2f}"
            return Decision.REJECTED, reason

    def _derive_risk_level(self, persona_results: list[PersonaResult]) -> RiskLevel:
        """Derive risk level from persona results."""
        balthasar_result = next(
            (r for r in persona_results if r.persona == Persona.BALTHASAR), None
        )

        # If BALTHASAR votes NO, risk is HIGH
        if balthasar_result and balthasar_result.vote == Vote.NO:
            return RiskLevel.HIGH

        # If any persona votes CONDITIONAL, risk is MEDIUM
        if any(r.vote == Vote.CONDITIONAL for r in persona_results):
            return RiskLevel.MEDIUM

        # If all vote YES, risk is LOW
        if all(r.vote == Vote.YES for r in persona_results):
            return RiskLevel.LOW

        # Mixed votes (some YES, some NO) -> MEDIUM
        return RiskLevel.MEDIUM

    def _compose_suggested_actions(
        self, persona_results: list[PersonaResult], decision: Decision
    ) -> list[str]:
        """Compose suggested actions based on persona results and decision."""
        actions = []

        balthasar_result = next(
            (r for r in persona_results if r.persona == Persona.BALTHASAR), None
        )

        # If BALTHASAR voted NO, suggest security-related actions
        if balthasar_result and balthasar_result.vote == Vote.NO:
            reason_lower = balthasar_result.reason.lower()
            if "sql" in reason_lower or "injection" in reason_lower:
                actions.append("Use parameterized queries or ORM to prevent SQL injection")
            if "input" in reason_lower or "validation" in reason_lower:
                actions.append("Add input validation and sanitization")
            if "auth" in reason_lower or "authorization" in reason_lower:
                actions.append("Review authentication and authorization logic")
            if "xss" in reason_lower or "cross-site" in reason_lower:
                actions.append("Implement XSS protection (output encoding)")
            if not actions:
                actions.append("Review security concerns raised by BALTHASAR")

        # If decision is CONDITIONAL, suggest fulfilling conditions
        if decision == Decision.CONDITIONAL:
            conditional_results = [
                r for r in persona_results if r.vote == Vote.CONDITIONAL
            ]
            for result in conditional_results:
                # Extract actionable items from reason
                if "test" in result.reason.lower():
                    actions.append("Add tests as suggested")
                if "document" in result.reason.lower():
                    actions.append("Add documentation")
                if "refactor" in result.reason.lower():
                    actions.append("Consider refactoring")

        return actions

    async def _apply_fallbacks(
        self,
        results: list[LLMResult | Exception],
        personas: list[Persona],
        prompts: list[str],
        proposal: str,
        trace_id: str | None,
        verbose: bool,
        logs: list[Dict[str, Any]],
        timeline: list[str],
    ) -> list[LLMResult | Exception]:
        """
        Apply fallback logic for rate-limited LLMs in consensus mode.

        Args:
            results: Initial LLM results
            personas: List of personas (MELCHIOR, BALTHASAR, CASPAR)
            prompts: Original prompts for each persona
            proposal: Original proposal
            trace_id: Trace ID for logging
            verbose: Verbose mode flag
            logs: Logs list to append to
            timeline: Timeline list to append to

        Returns:
            Updated results with fallbacks applied
        """
        if not self.fallback_manager:
            # フォールバックマネージャーが利用できない場合は元の結果を返す
            logger.warning("Fallback manager not available, skipping fallback logic")
            return results
        
        logger.info(f"Applying fallbacks for {len(results)} results")

        updated_results = list(results)
        persona_to_llm = {
            Persona.MELCHIOR: LLMName.GEMINI,
            Persona.BALTHASAR: LLMName.CLAUDE,
            Persona.CASPAR: LLMName.CODEX,
        }
        persona_to_client = {
            Persona.MELCHIOR: self.melchior_client,
            Persona.BALTHASAR: self.balthasar_client,
            Persona.CASPAR: self.caspar_client,
        }

        # 各結果をチェックしてフォールバックを適用
        for i, (result, persona, prompt) in enumerate(zip(results, personas, prompts)):
            logger.debug(f"Checking result {i} for persona {persona.value}: type={type(result)}")
            
            # Exception型の結果もチェック（asyncio.gatherでreturn_exceptions=Trueの場合）
            error_msg = None
            if isinstance(result, LLMFailure):
                error_msg = result.error_message
            elif isinstance(result, Exception):
                error_msg = str(result)
                logger.info(f"Exception detected for {persona.value}: {error_msg[:200]}")
            
            if error_msg:
                llm_name = persona_to_llm[persona]
                logger.info(f"Error detected for {persona.value} ({llm_name}): {error_msg[:200]}")
                
                rate_limit_info = self.fallback_manager.check_rate_limit(error_msg, llm_name)
                logger.info(f"Rate limit check for {persona.value} ({llm_name}): is_rate_limited={rate_limit_info.is_rate_limited}")

                if rate_limit_info.is_rate_limited:
                    # 利用制限に達している場合、フォールバックを試みる
                    self.fallback_manager.mark_rate_limited(llm_name)
                    logger.info(f"{persona.value} ({llm_name}) is rate limited, attempting fallback")

                    # フォールバック先を取得（コンセンサスモードでは役割ベースのフォールバック）
                    # ペルソナの役割に基づいてフォールバック先を決定
                    fallback_client, fallback_info = self._get_fallback_for_persona(persona)

                    if fallback_client and fallback_info:
                        # フォールバック先で再実行（同じペルソナプロンプトを使用）
                        logger.info(
                            f"Using {fallback_info.fallback_llm} as fallback for {persona.value} ({llm_name})"
                        )
                        try:
                            fallback_result = await fallback_client.generate_with_result(
                                prompt, trace_id=trace_id
                            )
                            updated_results[i] = fallback_result

                            if verbose:
                                timeline.append(
                                    f"[{persona.value}] fallback to {fallback_info.fallback_llm} "
                                    f"(rate limit, trace_id={trace_id or 'unknown'})"
                                )
                                logs.append({
                                    "t": datetime.now(timezone.utc).isoformat(),
                                    "persona": persona.value,
                                    "fallback": {
                                        "original_llm": fallback_info.original_llm,
                                        "fallback_llm": fallback_info.fallback_llm,
                                        "reason": fallback_info.reason,
                                    },
                                })
                        except Exception as e:
                            logger.error(f"Fallback failed for {persona.value}: {e}")
                            # フォールバックも失敗した場合は元の結果を保持

        return updated_results

    def _get_fallback_for_persona(self, persona: Persona) -> tuple[Optional[BaseLLMClient], Optional]:
        """
        Get fallback client for a persona in consensus mode.

        In consensus mode, we use a simple fallback strategy:
        - MELCHIOR (Gemini) -> Claude or Codex
        - BALTHASAR (Claude) -> Gemini or Codex
        - CASPAR (Codex) -> Claude or Gemini

        Args:
            persona: The persona that needs fallback

        Returns:
            Tuple of (fallback_client, fallback_info) or (None, None)
        """
        if not self.fallback_manager:
            return None, None

        from magi.fallback_manager import FallbackInfo

        # ペルソナからLLM名を取得
        persona_to_llm = {
            Persona.MELCHIOR: LLMName.GEMINI,
            Persona.BALTHASAR: LLMName.CLAUDE,
            Persona.CASPAR: LLMName.CODEX,
        }
        original_llm = persona_to_llm.get(persona)

        if not original_llm:
            return None, None

        # フォールバック優先順位（Claude優先）
        fallback_candidates = []
        if persona == Persona.MELCHIOR:  # Gemini
            fallback_candidates = [LLMName.CLAUDE, LLMName.CODEX]
        elif persona == Persona.BALTHASAR:  # Claude
            fallback_candidates = [LLMName.GEMINI, LLMName.CODEX]
        elif persona == Persona.CASPAR:  # Codex
            fallback_candidates = [LLMName.CLAUDE, LLMName.GEMINI]

        # 利用可能なフォールバック先を選択
        for candidate in fallback_candidates:
            if not self.fallback_manager.is_rate_limited(candidate):
                client = self.fallback_manager.clients.get(candidate)
                if client:
                    fallback_info = FallbackInfo(
                        original_llm=original_llm,
                        fallback_llm=candidate,
                        role=persona.value,
                        reason=f"{original_llm} is rate limited, using {candidate} as fallback for {persona.value}",
                    )
                    logger.info(f"Selected {candidate} as fallback for {persona.value} (original: {original_llm})")
                    return client, fallback_info

        logger.warning(f"No available fallback for {persona.value} (original: {original_llm})")
        return None, None
