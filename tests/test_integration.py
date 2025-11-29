"""
Phase 1: 統合テストの追加

実際のLLMクライアントとの統合をテストします。
"""
from __future__ import annotations

import pytest
from magi.controller import MAGIController
from magi.models import ModelOutput, LLMResult, LLMSuccess, LLMFailure


@pytest.mark.integration
@pytest.mark.asyncio
async def test_proposal_battle_full_chain():
    """実際のCodex→Claude→Geminiフローをテスト"""
    controller = MAGIController()
    
    result = await controller.start_magi(
        initial_prompt="簡単なテスト: PythonでHello Worldを出力するコードを書いてください",
        mode="proposal_battle",
        skip_claude=False,
    )
    
    assert "session_id" in result
    assert "results" in result
    
    results = result["results"]
    assert "codex" in results
    assert "claude" in results
    assert "gemini" in results
    
    # 各LLMの結果を確認（controllerはModelOutputオブジェクトを返す）
    codex_output = results["codex"]
    claude_output = results["claude"]
    gemini_output = results["gemini"]
    
    # ModelOutputオブジェクトであることを確認
    from magi.models import ModelOutput
    assert isinstance(codex_output, ModelOutput)
    assert isinstance(claude_output, ModelOutput)
    assert isinstance(gemini_output, ModelOutput)
    
    assert codex_output.model == "codex"
    assert claude_output.model == "claude"
    assert gemini_output.model == "gemini"
    
    # コンテンツが存在することを確認
    assert codex_output.content
    assert claude_output.content
    assert gemini_output.content
    
    # メタデータが存在することを確認
    assert codex_output.metadata
    assert claude_output.metadata
    assert gemini_output.metadata


@pytest.mark.integration
@pytest.mark.asyncio
async def test_proposal_battle_with_skip_claude():
    """Claudeをスキップした場合のフローをテスト"""
    controller = MAGIController()
    
    result = await controller.start_magi(
        initial_prompt="簡単なテスト",
        mode="proposal_battle",
        skip_claude=True,
    )
    
    assert "session_id" in result
    assert "results" in result
    
    results = result["results"]
    assert "codex" in results
    assert "claude" in results
    assert "gemini" in results
    
    # Claudeがスキップされていることを確認
    from magi.models import ModelOutput
    claude_output = results["claude"]
    assert isinstance(claude_output, ModelOutput)
    assert claude_output.metadata.get("skipped") is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_llm_client_type_safety():
    """新しい型安全なLLMクライアントメソッドをテスト"""
    from magi.clients import CodexClient
    from magi.config import LLMConfig
    
    client = CodexClient(LLMConfig.for_codex())
    
    # 新しい型安全なメソッドをテスト
    result = await client.generate_with_result("簡単なテスト", trace_id="test-trace-123")
    
    assert isinstance(result, (LLMSuccess, LLMFailure))
    
    if isinstance(result, LLMSuccess):
        assert result.model == "codex"
        assert result.content
        assert result.duration_ms >= 0
        assert result.source
    elif isinstance(result, LLMFailure):
        assert result.model == "codex"
        assert result.error_type in ["timeout", "http_error", "cli_missing", "exception"]
        assert result.error_message
        assert result.duration_ms >= 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_backward_compatibility():
    """後方互換性をテスト（既存のgenerateメソッドが動作することを確認）"""
    from magi.clients import CodexClient
    from magi.config import LLMConfig
    
    client = CodexClient(LLMConfig.for_codex())
    
    # 既存のメソッドが動作することを確認
    result = await client.generate("簡単なテスト")
    
    assert isinstance(result, ModelOutput)
    assert result.model == "codex"
    assert result.content


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_partial_failure_recovery():
    """一部のLLMが失敗した場合の動作をテスト"""
    # このテストは、実際のラッパーが利用できない場合の動作を確認
    # 現時点では、スタブ応答が返されることを確認
    controller = MAGIController()
    
    # 存在しないラッパーURLを使用してテスト（実際の環境では難しいため、スキップ可能）
    result = await controller.start_magi(
        initial_prompt="テスト",
        mode="proposal_battle",
        skip_claude=False,
    )
    
    # 結果が返されることを確認（スタブでもOK）
    assert "session_id" in result
    assert "results" in result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_step_magi():
    """step_magiエンドポイントの動作をテスト"""
    controller = MAGIController()
    
    # まずセッションを開始
    start_result = await controller.start_magi(
        initial_prompt="テスト",
        mode="proposal_battle",
        skip_claude=True,
    )
    
    session_id = start_result["session_id"]
    
    # 各案を取得
    for decision in ["codex", "gemini"]:
        step_result = await controller.step_magi(session_id, decision)
        
        assert step_result["session_id"] == session_id
        assert step_result["adopted_model"] == decision
        assert step_result["adopted_text"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_management():
    """セッション管理の動作をテスト"""
    controller = MAGIController()
    
    # セッションを作成
    result1 = await controller.start_magi("テスト1", mode="proposal_battle")
    session_id1 = result1["session_id"]
    
    result2 = await controller.start_magi("テスト2", mode="proposal_battle")
    session_id2 = result2["session_id"]
    
    # セッションIDが異なることを確認
    assert session_id1 != session_id2
    
    # セッションを停止
    stop_result = controller.stop_magi(session_id1)
    assert stop_result["session_id"] == session_id1
    assert stop_result["stopped"] is True

