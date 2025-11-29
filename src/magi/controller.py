from __future__ import annotations

from typing import Dict, Optional

from magi.clients import ClaudeClient, CodexClient, GeminiClient
from magi.config import AppConfig
from magi.modes import ProposalBattleMode
from magi.models import ModelOutput
from magi.session_store import InMemorySessionStore


class MAGIController:
    def __init__(self, session_store: Optional[InMemorySessionStore] = None, config: Optional[AppConfig] = None) -> None:
        self.session_store = session_store or InMemorySessionStore()
        self.config = config or AppConfig.from_env()

        self.codex_client = CodexClient(self.config.codex)
        self.claude_client = ClaudeClient(self.config.claude)
        self.gemini_client = GeminiClient(self.config.gemini)

    async def start_magi(self, initial_prompt: str, mode: str = "proposal_battle", skip_claude: bool = False) -> Dict:
        state = self.session_store.create(mode=mode)
        outputs = await self._run_mode(mode, initial_prompt, skip_claude=skip_claude)
        self.session_store.save_outputs(state.session_id, outputs)
        return {
            "session_id": state.session_id,
            "results": outputs,
        }

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

    async def _run_mode(self, mode: str, prompt: str, skip_claude: bool = False) -> Dict[str, ModelOutput]:
        if mode != "proposal_battle":
            raise ValueError("Only proposal_battle mode is supported")
        proposal_battle = ProposalBattleMode(
            codex_client=self.codex_client,
            claude_client=self.claude_client,
            gemini_client=self.gemini_client,
            skip_claude=skip_claude,
        )
        return await proposal_battle.run(prompt)
