#!/usr/bin/env bash
# ホストラッパーを起動するスクリプト
# 4つのLLM CLIラッパーをバックグラウンドで起動します

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# 仮想環境をアクティベート
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "⚠️  仮想環境が見つかりません。setup_environment.sh を実行してください。"
    exit 1
fi

# 既存のプロセスを確認
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 0
    else
        return 1
    fi
}

# ポートが使用中の場合は警告
PORTS=(9001 9002 9003 9004)
for port in "${PORTS[@]}"; do
    if check_port $port; then
        echo "⚠️  ポート $port は既に使用されています"
    fi
done

echo "=== ホストラッパーを起動します ==="
echo ""

# 各ラッパーをバックグラウンドで起動
echo "📦 Codexラッパーを起動中 (ポート9001)..."
uvicorn host_wrappers.codex_wrapper:app --host 127.0.0.1 --port 9001 > /tmp/codex_wrapper.log 2>&1 &
CODEX_PID=$!
echo "   PID: $CODEX_PID"

echo "📦 Claudeラッパーを起動中 (ポート9002)..."
uvicorn host_wrappers.claude_wrapper:app --host 127.0.0.1 --port 9002 > /tmp/claude_wrapper.log 2>&1 &
CLAUDE_PID=$!
echo "   PID: $CLAUDE_PID"

echo "📦 Geminiラッパーを起動中 (ポート9003)..."
uvicorn host_wrappers.gemini_wrapper:app --host 127.0.0.1 --port 9003 > /tmp/gemini_wrapper.log 2>&1 &
GEMINI_PID=$!
echo "   PID: $GEMINI_PID"

echo "📦 Judgeラッパーを起動中 (ポート9004)..."
uvicorn host_wrappers.judge_wrapper:app --host 127.0.0.1 --port 9004 > /tmp/judge_wrapper.log 2>&1 &
JUDGE_PID=$!
echo "   PID: $JUDGE_PID"

echo ""
echo "✅ すべてのラッパーを起動しました"
echo ""
echo "📝 ログファイル:"
echo "   - Codex: /tmp/codex_wrapper.log"
echo "   - Claude: /tmp/claude_wrapper.log"
echo "   - Gemini: /tmp/gemini_wrapper.log"
echo "   - Judge: /tmp/judge_wrapper.log"
echo ""
echo "🛑 停止するには:"
echo "   kill $CODEX_PID $CLAUDE_PID $GEMINI_PID $JUDGE_PID"
echo ""
echo "または、以下のコマンドで停止:"
echo "   pkill -f 'uvicorn host_wrappers'"
echo ""
echo "📊 動作確認:"
echo "   curl http://127.0.0.1:9001/health"
echo "   curl http://127.0.0.1:9002/health"
echo "   curl http://127.0.0.1:9003/health"
echo "   curl http://127.0.0.1:9004/health"
echo ""

# PIDをファイルに保存（後で停止するため）
echo "$CODEX_PID $CLAUDE_PID $GEMINI_PID $JUDGE_PID" > /tmp/magi_wrappers.pid


