from __future__ import annotations

from typing import Dict, Optional

from magi.clients import ClaudeClient, CodexClient, GeminiClient
from magi.config import AppConfig
from magi.modes import ProposalBattleMode
from magi.models import ModelOutput, MagiDecision
from magi.consensus import MagiConsensusEngine
from magi.session_store import InMemorySessionStore


class MAGIController:
    def __init__(self, session_store: Optional[InMemorySessionStore] = None, config: Optional[AppConfig] = None) -> None:
        self.session_store = session_store or InMemorySessionStore()
        self.config = config or AppConfig.from_env()
        self.fallback_policy = getattr(self.config, "fallback_policy", "lenient")
        self.verbose_default: bool = getattr(self.config, "verbose_default", False)

        self.codex_client = CodexClient(self.config.codex)
        self.claude_client = ClaudeClient(self.config.claude)
        self.gemini_client = GeminiClient(self.config.gemini)

    async def start_magi(
        self,
        initial_prompt: str,
        mode: Optional[str] = None,
        skip_claude: bool = False,
        fallback_policy: Optional[str] = None,
        verbose: Optional[bool] = None,
        criticality: Optional[str] = None,
    ) -> Dict:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[DEBUG] controller.start_magi called with verbose={verbose} (type: {type(verbose)}), verbose_default={self.verbose_default}")
        
        # デフォルトモードを取得
        if mode is None:
            try:
                from magi.settings import Settings
                settings = Settings.from_env()
                mode = settings.get_default_mode()
            except (ImportError, AttributeError):
                mode = "consensus"  # フォールバック
        
        state = self.session_store.create(mode=mode)
        policy = (fallback_policy or self.fallback_policy or "lenient").lower()
        verbose_flag = self.verbose_default if verbose is None else verbose
        logger.info(f"[DEBUG] verbose_flag calculated: {verbose_flag} (type: {type(verbose_flag)})")
        
        # Check if consensus mode
        if mode == "consensus":
            # 設定からdefault criticalityを読み込む
            try:
                from magi.settings import Settings
                settings = Settings.from_env()
                default_criticality = settings.default_criticality
            except (ImportError, AttributeError):
                default_criticality = "NORMAL"
            
            consensus_result = await self._run_consensus_mode(
                initial_prompt,
                criticality=criticality or default_criticality,
                session_id=state.session_id,
                verbose=verbose_flag,
            )
            
            # verboseモードの場合は詳細情報を返す
            if verbose_flag and isinstance(consensus_result, tuple):
                magi_decision, logs, summary, timeline = consensus_result
                result = {
                    "session_id": state.session_id,
                    "results": {},  # Keep for backward compatibility
                    "magi_decision": self._serialize_magi_decision(magi_decision),
                    "logs": logs,
                    "summary": summary,
                    "timeline": timeline,
                }
            else:
                magi_decision = consensus_result
                result = {
                    "session_id": state.session_id,
                    "results": {},  # Keep for backward compatibility
                    "magi_decision": self._serialize_magi_decision(magi_decision),
                }
            return result
        
        outputs, logs, summary, timeline = await self._run_mode(
            mode,
            initial_prompt,
            skip_claude=skip_claude,
            fallback_policy=policy,
            verbose=verbose_flag,
        )
        logger.info(f"[DEBUG] _run_mode returned: logs length={len(logs) if logs else 0}, summary={summary}, timeline length={len(timeline) if timeline else 0}")
        self.session_store.save_outputs(state.session_id, outputs)
        result = {
            "session_id": state.session_id,
            "results": outputs,
            "logs": logs if verbose_flag else None,
            "summary": summary if verbose_flag else None,
            "timeline": timeline if verbose_flag else None,
        }
        logger.info(f"[DEBUG] returning result with logs={result.get('logs')}, summary={result.get('summary')}, timeline={result.get('timeline')}")
        return result

    async def step_magi(self, session_id: str, decision: str) -> Dict:
        state = self.session_store.get(session_id)
        if not state:
            raise ValueError("Invalid session_id")
        if not state.last_outputs:
            raise ValueError("Session has no outputs")

        decision_key = decision.lower()
        if decision_key not in state.last_outputs:
            raise ValueError("Decision must be one of codex/claude/gemini")

        adopted: ModelOutput = state.last_outputs[decision_key]
        return {
            "session_id": session_id,
            "adopted_model": adopted.model,
            "adopted_text": adopted.content,
        }

    def stop_magi(self, session_id: str) -> Dict:
        self.session_store.delete(session_id)
        return {"session_id": session_id, "stopped": True}

    async def get_cli_status(self) -> Dict:
        """全HTTPラッパーの状態を取得する"""
        import asyncio
        codex_status, claude_status, gemini_status = await asyncio.gather(
            self.codex_client.aget_cli_status(),
            self.claude_client.aget_cli_status(),
            self.gemini_client.aget_cli_status(),
        )
        return {
            "codex": codex_status,
            "claude": claude_status,
            "gemini": gemini_status,
        }

    async def _run_consensus_mode(
        self,
        proposal: str,
        criticality: str = "NORMAL",
        session_id: str | None = None,
        verbose: bool = False,
    ) -> MagiDecision | tuple[MagiDecision, list, str, list[str]]:
        """Run consensus mode using MAGI consensus engine."""
        import uuid
        from magi.models import Persona
        
        trace_id = str(uuid.uuid4())
        
        # 設定からpersona weightsとconditional weightを読み込む
        try:
            from magi.settings import Settings
            settings = Settings.from_env()
            weights = {
                Persona.MELCHIOR: settings.melchior_weight,
                Persona.BALTHASAR: settings.balthasar_weight,
                Persona.CASPAR: settings.caspar_weight,
            }
            conditional_weight = settings.conditional_weight
        except (ImportError, AttributeError):
            # 設定が利用できない場合はデフォルト値を使用
            weights = None
            conditional_weight = None
        
        engine = MagiConsensusEngine(
            melchior_client=self.gemini_client,  # Gemini -> Melchior
            balthasar_client=self.claude_client,  # Claude -> Balthasar
            caspar_client=self.codex_client,  # Codex -> Caspar
            weights=weights,
            conditional_weight=conditional_weight,
        )
        return await engine.evaluate(proposal, criticality, persona_overrides=None, session_id=session_id, trace_id=trace_id, verbose=verbose)

    def _serialize_magi_decision(self, decision: MagiDecision) -> Dict:
        """
        Serialize MagiDecision to dict for JSON response.
        
        Optimized for readability and user experience.
        """
        # 各ペルソナの結果を構造化
        persona_results = []
        for r in decision.persona_results:
            persona_results.append({
                "persona": r.persona.value,
                "persona_name": {
                    "melchior": "Melchior (Scientist)",
                    "balthasar": "Balthasar (Safety)",
                    "caspar": "Caspar (Pragmatist)",
                }.get(r.persona.value, r.persona.value),
                "vote": r.vote.value,
                "vote_label": {
                    "YES": "Approved",
                    "NO": "Rejected",
                    "CONDITIONAL": "Conditional Approval",
                }.get(r.vote.value, r.vote.value),
                "reason": r.reason,
            })
        
        # 決定の説明を追加
        decision_label = {
            "APPROVED": "Approved",
            "REJECTED": "Rejected",
            "CONDITIONAL": "Conditional Approval",
        }.get(decision.decision.value, decision.decision.value)
        
        risk_label = {
            "LOW": "Low Risk",
            "MEDIUM": "Medium Risk",
            "HIGH": "High Risk",
        }.get(decision.risk_level.value, decision.risk_level.value)
        
        return {
            "decision": decision.decision.value,
            "decision_label": decision_label,
            "risk_level": decision.risk_level.value,
            "risk_label": risk_label,
            "persona_results": persona_results,
            "aggregate_reason": decision.aggregate_reason,
            "suggested_actions": decision.suggested_actions,
            "summary": self._generate_decision_summary(decision),
        }
    
    def _generate_decision_summary(self, decision: MagiDecision) -> str:
        """Generate a human-readable summary of the decision."""
        votes = {r.vote.value: [] for r in decision.persona_results}
        for r in decision.persona_results:
            votes[r.vote.value].append(r.persona.value)
        
        summary_parts = []
        if votes.get("YES"):
            summary_parts.append(f"{len(votes['YES'])} persona(s) approved: {', '.join(votes['YES'])}")
        if votes.get("NO"):
            summary_parts.append(f"{len(votes['NO'])} persona(s) rejected: {', '.join(votes['NO'])}")
        if votes.get("CONDITIONAL"):
            summary_parts.append(f"{len(votes['CONDITIONAL'])} persona(s) conditionally approved: {', '.join(votes['CONDITIONAL'])}")
        
        summary = f"Decision: {decision.decision.value} ({decision.risk_level.value} risk). " + ". ".join(summary_parts)
        return summary

    async def _run_mode(
        self,
        mode: str,
        prompt: str,
        skip_claude: bool = False,
        fallback_policy: str = "lenient",
        verbose: bool = False,
    ) -> tuple[Dict[str, ModelOutput], list, str, list[str]]:
        if mode != "proposal_battle":
            raise ValueError("Only proposal_battle mode is supported")
        proposal_battle = ProposalBattleMode(
            codex_client=self.codex_client,
            claude_client=self.claude_client,
            gemini_client=self.gemini_client,
            skip_claude=skip_claude,
            fallback_policy=fallback_policy,
        )
        return await proposal_battle.run(prompt, verbose=verbose, return_details=True)
