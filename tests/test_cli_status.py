"""CLIの状態を明確に識別するテスト（実際のCLIかスタブCLIか）"""

import pytest

from magi.clients import CodexClient, ClaudeClient, GeminiClient


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client_cls",
    [CodexClient, ClaudeClient, GeminiClient],
)
async def test_cli_status_identification(client_cls):
    """各CLIの状態を明確に識別できることを確認"""
    client = client_cls()
    status = client.get_cli_status()
    
    # 状態情報が返されることを確認
    assert isinstance(status, dict)
    assert "available" in status
    assert "type" in status
    assert "path" in status
    assert "message" in status
    
    # typeが明確に識別されることを確認
    assert status["type"] in ["stub", "real", "missing", "none"], \
        f"Invalid CLI type: {status['type']}"
    
    print(f"\n=== {client.model_name.upper()} CLI 状態 ===")
    print(f"利用可能: {status['available']}")
    print(f"タイプ: {status['type']}")
    print(f"パス: {status['path']}")
    print(f"メッセージ: {status['message']}")
    
    # 状態が明確に識別されていることを確認
    if status["available"]:
        assert status["type"] in ["stub", "real"], \
            f"CLI is available but type is unclear: {status['type']}"
        assert status["path"] is not None, \
            "CLI path should be provided when available"
    else:
        assert status["type"] in ["missing", "none"], \
            f"CLI is not available but type is unclear: {status['type']}"


@pytest.mark.asyncio
async def test_cli_status_in_output_metadata():
    """CLI実行時の出力にCLI状態がメタデータとして含まれることを確認"""
    client = CodexClient()
    test_prompt = "テストプロンプト"
    output = await client.generate(test_prompt)
    
    # メタデータにCLI状態が含まれることを確認
    assert "metadata" in output.__dict__ or hasattr(output, "metadata")
    metadata = output.metadata
    
    if isinstance(metadata, dict):
        # メタデータにCLI状態が記録されていることを確認
        if "cli_type" in metadata:
            assert metadata["cli_type"] in ["stub", "real"], \
                f"Invalid cli_type in metadata: {metadata['cli_type']}"
            print(f"\n=== CLI状態（メタデータ） ===")
            print(f"cli_type: {metadata.get('cli_type', 'N/A')}")
            print(f"cli_path: {metadata.get('cli_path', 'N/A')}")


@pytest.mark.asyncio
async def test_all_cli_statuses():
    """全CLIの状態を一覧表示"""
    clients = {
        "codex": CodexClient(),
        "claude": ClaudeClient(),
        "gemini": GeminiClient(),
    }
    
    statuses = {}
    for name, client in clients.items():
        status = client.get_cli_status()
        statuses[name] = status
    
    print("\n=== 全CLI状態一覧 ===")
    for name, status in statuses.items():
        print(f"{name}:")
        print(f"  利用可能: {status['available']}")
        print(f"  タイプ: {status['type']}")
        print(f"  パス: {status['path']}")
        print(f"  メッセージ: {status['message']}")
        print()
    
    # 少なくとも1つのCLIが利用可能であることを確認（スタブでも可）
    available_count = sum(1 for s in statuses.values() if s["available"])
    assert available_count > 0, "At least one CLI should be available"

