#!/usr/bin/env bash
# ホストラッパーを起動するスクリプト
# 4つのLLM CLIラッパーをバックグラウンドで起動します

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PIDS=()
CLEANUP_REQUIRED=1

cleanup() {
    # スクリプトが途中で失敗/中断した場合も残プロセスを掃除する
    if [ "${CLEANUP_REQUIRED}" -eq 1 ] && [ "${#PIDS[@]}" -gt 0 ]; then
        echo "🧹 中断を検知したためホストラッパーを停止します..."
        kill "${PIDS[@]}" 2>/dev/null || true
        rm -f /tmp/magi_wrappers.pid
    fi
}
trap cleanup EXIT INT TERM

# 仮想環境をアクティベート
if [ -d ".venv" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
else
    echo "⚠️  仮想環境が見つかりません。scripts/setup_environment.sh を実行してください。"
    exit 1
fi

# 依存関係のチェック
if ! command -v uvicorn &> /dev/null; then
    echo "❌ uvicorn が見つかりません。依存関係をインストールしてください:"
    echo "   pip install -r host_wrappers/requirements.txt"
    exit 1
fi

# ホストラッパーモジュールのチェック
if [ ! -f "host_wrappers/codex_wrapper.py" ]; then
    echo "❌ host_wrappers/codex_wrapper.py が見つかりません。"
    exit 1
fi

# 既存のプロセスを確認
check_port() {
    local port=$1
    if lsof -Pi :"$port" -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 0
    else
        return 1
    fi
}

# ポートが使用中の場合は警告
PORTS=(9001 9002 9003 9004)
for port in "${PORTS[@]}"; do
    if check_port "$port"; then
        echo "⚠️  ポート $port は既に使用されています"
    fi
done

echo "=== ホストラッパーを起動します ==="
echo ""

# ラッパー起動関数
start_wrapper() {
    local name=$1
    local port=$2
    local wrapper_file=$3
    local log_file="/tmp/${name}_wrapper.log"
    
    echo "📦 ${name}ラッパーを起動中 (ポート${port})..."
    
    # 既存のログをクリア
    > "$log_file"
    
    # ラッパーをバックグラウンドで起動
    if uvicorn "$wrapper_file":app --host 127.0.0.1 --port "$port" > "$log_file" 2>&1 &
    then
        local pid=$!
        PIDS+=("$pid")
        echo "   PID: $pid"
        
        # 起動確認（最大3秒待機）
        local max_wait=3
        local waited=0
        while [ $waited -lt $max_wait ]; do
            if curl -s "http://127.0.0.1:${port}/health" > /dev/null 2>&1; then
                echo "   ✅ ${name}ラッパーが正常に起動しました"
                echo "$pid"
                return 0
            fi
            sleep 0.5
            waited=$((waited + 1))
        done
        
        # 起動失敗時のエラーチェック
        if [ -s "$log_file" ]; then
            echo "   ⚠️  ${name}ラッパーの起動に時間がかかっています。ログを確認してください:"
            echo "      tail -f $log_file"
        else
            echo "   ⚠️  ${name}ラッパーの起動状態を確認できませんでした"
        fi
        echo "$pid"
        return 1
    else
        echo "   ❌ ${name}ラッパーの起動に失敗しました"
        echo "   ログを確認してください: cat $log_file"
        echo ""
        return 1
    fi
}

run_wrapper() {
    local name=$1
    local port=$2
    local module=$3
    local pid=""
    if ! pid="$(start_wrapper "$name" "$port" "$module")"; then
        echo "❌ ${name}ラッパーの起動中にエラーが発生しました"
        exit 1
    fi
    echo "$pid"
}

# 各ラッパーを起動
CODEX_PID=$(run_wrapper "Codex" 9001 "host_wrappers.codex_wrapper")
CLAUDE_PID=$(run_wrapper "Claude" 9002 "host_wrappers.claude_wrapper")
GEMINI_PID=$(run_wrapper "Gemini" 9003 "host_wrappers.gemini_wrapper")
JUDGE_PID=$(run_wrapper "Judge" 9004 "host_wrappers.judge_wrapper")

echo ""
echo "✅ すべてのラッパーの起動処理を完了しました"
echo ""
echo "📝 ログファイル:"
echo "   - Codex: /tmp/codex_wrapper.log"
echo "   - Claude: /tmp/claude_wrapper.log"
echo "   - Gemini: /tmp/gemini_wrapper.log"
echo "   - Judge: /tmp/judge_wrapper.log"
echo ""
echo "📊 動作確認:"
echo "   各ラッパーのヘルスチェック:"
echo "   curl http://127.0.0.1:9001/health"
echo "   curl http://127.0.0.1:9002/health"
echo "   curl http://127.0.0.1:9003/health"
echo "   curl http://127.0.0.1:9004/health"
echo ""
echo "   ログの確認:"
echo "   tail -f /tmp/codex_wrapper.log"
echo ""
echo "🛑 停止するには:"
echo "   bash scripts/stop_host_wrappers.sh"
echo ""
echo "   または手動で:"
echo "   kill $CODEX_PID $CLAUDE_PID $GEMINI_PID $JUDGE_PID"
echo "   pkill -f 'uvicorn host_wrappers'"
echo ""

# PIDをファイルに保存（後で停止するため）
echo "$CODEX_PID $CLAUDE_PID $GEMINI_PID $JUDGE_PID" > /tmp/magi_wrappers.pid

# 起動状態の最終確認
echo "🔍 起動状態の確認中..."
sleep 1
FAILED=0
# 連想配列の代わりにcase文を使用（set -uとの互換性のため）
for name in "codex" "claude" "gemini" "judge"; do
    case "$name" in
        "codex") port=9001 ;;
        "claude") port=9002 ;;
        "gemini") port=9003 ;;
        "judge") port=9004 ;;
        *) port=0 ;;
    esac
    if curl -s "http://127.0.0.1:${port}/health" > /dev/null 2>&1; then
        echo "   ✅ ${name}: 正常"
    else
        echo "   ❌ ${name}: 起動失敗 (ポート${port})"
        echo "      ログを確認: cat /tmp/${name}_wrapper.log"
        FAILED=$((FAILED + 1))
    fi
done

if [ $FAILED -gt 0 ]; then
    echo ""
    echo "⚠️  ${FAILED}個のラッパーが起動に失敗しました。"
    echo "   ログファイルを確認して問題を解決してください。"
    exit 1
else
    echo ""
    echo "✅ すべてのラッパーが正常に起動しています！"
fi

# 正常完了したのでクリーンアップは不要
CLEANUP_REQUIRED=0
