from __future__ import annotations

from typing import Dict

from magi.clients import ClaudeClient, CodexClient, GeminiClient
from magi.models import ModelOutput
from magi import prompts


class ProposalBattleMode:
    """Sequentially executes Codex -> Claude -> Gemini. Judge is handled by Cursor."""

    def __init__(
        self,
        codex_client: CodexClient,
        claude_client: ClaudeClient,
        gemini_client: GeminiClient,
        skip_claude: bool = False,
    ) -> None:
        self.codex_client = codex_client
        self.claude_client = claude_client
        self.gemini_client = gemini_client
        self.skip_claude = skip_claude

    async def run(self, task: str) -> Dict[str, ModelOutput]:
        codex_prompt = prompts.build_codex_prompt(task)
        codex_output = await self.codex_client.generate(codex_prompt)

        if self.skip_claude:
            # Claudeをスキップして、Codexの出力を直接Geminiに渡す
            claude_output = ModelOutput(
                model="claude",
                content="[Claude skipped - using Codex output directly]",
                metadata={"skipped": True},
            )
            # Codexの出力を直接Geminiに渡す（Claudeの評価をスキップ）
            gemini_prompt = prompts.build_gemini_prompt(codex_output.content)
        else:
            claude_prompt = prompts.build_claude_prompt(codex_output.content)
            claude_output = await self.claude_client.generate(claude_prompt)
            gemini_prompt = prompts.build_gemini_prompt(claude_output.content)

        gemini_output = await self.gemini_client.generate(gemini_prompt)

        # JudgeはCursorが担当するため、3案を返す
        return {
            "codex": codex_output,
            "claude": claude_output,
            "gemini": gemini_output,
        }
