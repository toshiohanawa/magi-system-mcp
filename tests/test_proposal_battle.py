import pytest

from magi.clients import CodexClient, ClaudeClient, GeminiClient
from magi.modes import ProposalBattleMode


@pytest.mark.asyncio
async def test_proposal_battle_runs_one_round():
    codex = CodexClient()
    claude = ClaudeClient()
    gemini = GeminiClient()

    mode = ProposalBattleMode(codex, claude, gemini)
    outputs = await mode.run("Test the MAGI system")

    assert set(outputs.keys()) == {"codex", "claude", "gemini"}
    assert all(output.content for output in outputs.values())
