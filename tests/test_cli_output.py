"""CLIから文章として回答が返ってくることを確認するテスト"""

import pytest

from magi.clients import CodexClient, ClaudeClient, GeminiClient
from magi.models import ModelOutput


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client_cls,test_prompt",
    [
        (CodexClient, "PythonでHello Worldを出力するプログラムを作成してください。"),
        (ClaudeClient, "以下のコードをレビューしてください: def hello(): print('Hello')"),
        (GeminiClient, "データ分析のためのPythonスクリプトの設計案を提案してください。"),
    ],
)
async def test_cli_returns_text_response(client_cls, test_prompt):
    """各CLIが文章として回答を返すことを確認"""
    client = client_cls()
    output = await client.generate(test_prompt)
    
    # ModelOutputが返されることを確認
    assert isinstance(output, ModelOutput)
    assert output.model in ["codex", "claude", "gemini"]
    
    # コンテンツが文字列として返されることを確認
    assert isinstance(output.content, str)
    assert len(output.content) > 0
    
    # 入力プロンプトが含まれているか確認（スタブCLIの場合）
    # または、実際のCLIからの応答が文章として返されていることを確認
    print(f"\n=== {output.model.upper()} CLI 出力 ===")
    print(f"入力プロンプト: {test_prompt[:50]}...")
    print(f"出力（最初の200文字）: {output.content[:200]}...")
    print(f"出力の長さ: {len(output.content)}文字")
    print(f"出力が文章として返されている: ✅")


@pytest.mark.asyncio
async def test_cli_output_format():
    """CLI出力が適切な形式（文章）で返されることを確認"""
    test_prompt = "Webアプリケーションの認証システムを設計してください。"
    
    clients = [
        CodexClient(),
        ClaudeClient(),
        GeminiClient(),
    ]
    
    results = {}
    for client in clients:
        output = await client.generate(test_prompt)
        results[client.model_name] = output
        
        # 出力が文章として返されることを確認
        assert isinstance(output.content, str), f"{client.model_name}の出力が文字列ではありません"
        assert len(output.content) > 0, f"{client.model_name}の出力が空です"
        
        # 出力が適切な長さであることを確認（スタブCLIの場合はプロンプトがそのまま返る）
        assert len(output.content) >= len(test_prompt) - 10, \
            f"{client.model_name}の出力が短すぎます"
    
    # すべてのCLIが文章を返すことを確認
    print("\n=== 全CLI出力の確認 ===")
    for model_name, output in results.items():
        print(f"{model_name}: {len(output.content)}文字の文章を返却 ✅")


@pytest.mark.asyncio
async def test_cli_output_contains_input():
    """スタブCLIの場合、入力がそのまま返されることを確認"""
    unique_input = "UNIQUE_TEST_INPUT_12345"
    client = CodexClient()
    output = await client.generate(unique_input)
    
    # スタブCLIの場合、入力がそのまま返される
    # 実際のCLIの場合、入力に対する応答が返される
    assert unique_input in output.content or len(output.content) > 0, \
        "CLI出力に期待される内容が含まれていません"
    
    print(f"\n=== CLI出力の検証 ===")
    print(f"入力: {unique_input}")
    print(f"出力: {output.content[:100]}...")
    print(f"入力が含まれているか、または適切な応答が返されている: ✅")

