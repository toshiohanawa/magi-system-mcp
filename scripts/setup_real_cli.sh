#!/bin/bash
# 実際のCLIバイナリのパスを環境変数として設定

echo "=== 実際のCLIバイナリのパス設定 ==="

# 実際のCLIパスを取得（command -vを使用、見つからない場合は空文字列）
CODEX_PATH=$(command -v codex 2>/dev/null || echo "")
CLAUDE_PATH=$(command -v claude 2>/dev/null || echo "")
GEMINI_PATH=$(command -v gemini 2>/dev/null || echo "")
JUDGE_PATH=$(command -v judge 2>/dev/null || echo "")

# 環境変数を設定（パスが存在する場合のみ設定、存在しない場合はデフォルト）
export CODEX_CLI_PATH=${CODEX_PATH:-/usr/local/bin/codex}
export CLAUDE_CLI_PATH=${CLAUDE_PATH:-/usr/local/bin/claude}
export GEMINI_CLI_PATH=${GEMINI_PATH:-/usr/local/bin/gemini}
export JUDGE_CLI_PATH=${JUDGE_PATH:-/usr/local/bin/judge}

echo "CODEX_CLI_PATH=$CODEX_CLI_PATH"
echo "CLAUDE_CLI_PATH=$CLAUDE_CLI_PATH"
echo "GEMINI_CLI_PATH=$GEMINI_CLI_PATH"
echo "JUDGE_CLI_PATH=$JUDGE_CLI_PATH"

echo ""
echo "=== 設定完了 ==="
echo "これらの環境変数が設定されました。"
echo "次に docker compose up --build を実行してください。"
