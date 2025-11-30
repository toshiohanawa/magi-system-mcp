#!/usr/bin/env bash
# MAGIシステム全体を起動するスクリプト
# デフォルトではホストラッパーを使用し、USE_CONTAINER_WRAPPERS=1でコンテナ化ラッパーに切り替え可能

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# デフォルトはホストラッパーを使用（USE_CONTAINER_WRAPPERS=1でコンテナ化ラッパーに切り替え）
USE_CONTAINER_WRAPPERS=${USE_CONTAINER_WRAPPERS:-0}
USE_HOST_WRAPPERS=$([ "${USE_CONTAINER_WRAPPERS}" = "1" ] && echo "0" || echo "1")
AUTO_CLEANUP=1
WRAPPERS_STARTED=0
DOCKER_STARTED=0

cleanup() {
    if [ "${AUTO_CLEANUP}" -ne 1 ]; then
        return
    fi
    if [ "${DOCKER_STARTED}" -eq 1 ]; then
        docker compose down || true
    fi
    if [ "${WRAPPERS_STARTED}" -eq 1 ]; then
        bash scripts/stop_host_wrappers.sh || true
    fi
}
trap cleanup EXIT INT TERM

echo "=== MAGIシステムを起動します ==="
echo ""

if [ "${USE_CONTAINER_WRAPPERS}" = "1" ]; then
    echo "📦 ステップ1: コンテナ化ラッパーを使用します"
    echo "   注意: コンテナ内でCLIバイナリ（codex, claude, gemini, judge）が利用可能である必要があります"
    # コンテナ化ラッパー使用時はコンテナ内のURLを使用
    export CODEX_WRAPPER_URL=${CODEX_WRAPPER_URL:-http://codex-wrapper:9001}
    export CLAUDE_WRAPPER_URL=${CLAUDE_WRAPPER_URL:-http://claude-wrapper:9002}
    export GEMINI_WRAPPER_URL=${GEMINI_WRAPPER_URL:-http://gemini-wrapper:9003}
    export JUDGE_WRAPPER_URL=${JUDGE_WRAPPER_URL:-http://judge-wrapper:9004}
    echo ""
else
    echo "📦 ステップ1: ホストラッパーを起動中（デフォルト）..."
    echo "   USE_CONTAINER_WRAPPERS=1 でコンテナ化ラッパーに切り替え可能"
    # ホストラッパーを使う場合はコンテナ側の接続先もホスト向けに上書きする
    export CODEX_WRAPPER_URL=${CODEX_WRAPPER_URL:-http://host.docker.internal:9001}
    export CLAUDE_WRAPPER_URL=${CLAUDE_WRAPPER_URL:-http://host.docker.internal:9002}
    export GEMINI_WRAPPER_URL=${GEMINI_WRAPPER_URL:-http://host.docker.internal:9003}
    export JUDGE_WRAPPER_URL=${JUDGE_WRAPPER_URL:-http://host.docker.internal:9004}
    bash scripts/start_host_wrappers.sh
    WRAPPERS_STARTED=1
    echo "✅ ホストラッパーの起動が完了しました"
    echo ""
fi

echo "🐳 ステップ2: Docker Composeを起動中..."
COMPOSE_ARGS=(up -d --build)
COMPOSE_TARGETS=()
if [ "${USE_CONTAINER_WRAPPERS}" != "1" ]; then
    # ホストラッパー利用時はAPIコンテナのみ起動（ラッパーサービスは起動しない）
    COMPOSE_ARGS+=(--no-deps)
    COMPOSE_TARGETS+=(magi-mcp)
else
    # コンテナ化ラッパー使用時は全サービスを起動
    COMPOSE_TARGETS=(magi-mcp codex-wrapper claude-wrapper gemini-wrapper judge-wrapper)
fi

if docker compose "${COMPOSE_ARGS[@]}" "${COMPOSE_TARGETS[@]}" ; then
    DOCKER_STARTED=1
    echo "✅ Docker Composeの起動が完了しました"
    echo ""
else
    echo "❌ Docker Composeの起動に失敗しました"
    exit 1
fi

echo "🔍 ステップ3: 起動状態を確認中..."
sleep 2

# Dockerコンテナの状態確認
if docker compose ps | grep -q "magi-mcp.*Up"; then
    echo "✅ Dockerコンテナが正常に起動しています"
else
    echo "⚠️  Dockerコンテナの起動状態を確認できませんでした"
fi

# MAGIシステムのヘルスチェック
echo ""
echo "📊 MAGIシステムのヘルスチェック:"
if curl -s http://127.0.0.1:8787/health > /dev/null 2>&1; then
    echo "✅ MAGIシステムが正常に応答しています"
    echo ""
    echo "詳細な状態を確認:"
    echo "   curl http://127.0.0.1:8787/health | jq"
else
    echo "⚠️  MAGIシステムが応答していません（起動中かもしれません）"
    echo "   数秒後に再確認してください: curl http://127.0.0.1:8787/health"
fi

# 正常完了したのでクリーンアップは不要
AUTO_CLEANUP=0
trap - EXIT INT TERM

echo ""
echo "✅ MAGIシステムの起動が完了しました！"
echo ""
echo "📝 便利なコマンド:"
echo "   状態確認: curl http://127.0.0.1:8787/health | jq"
echo "   ログ確認: docker compose logs -f"
echo "   停止:     bash scripts/stop_magi.sh"
echo ""
