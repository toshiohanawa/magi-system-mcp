#!/usr/bin/env bash
# MAGIシステム全体を停止するスクリプト
# Docker Composeとホストラッパーを自動的に停止します

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== MAGIシステムを停止します ==="
echo ""

# 1. Docker Composeを停止
echo "🐳 ステップ1: Docker Composeを停止中..."
if docker compose down; then
    echo "✅ Docker Composeの停止が完了しました"
    echo ""
else
    echo "⚠️  Docker Composeの停止中にエラーが発生しました（既に停止している可能性があります）"
    echo ""
fi

# 2. ホストラッパーを停止
echo "📦 ステップ2: ホストラッパーを停止中..."
if bash scripts/stop_host_wrappers.sh; then
    echo "✅ ホストラッパーの停止が完了しました"
    echo ""
else
    echo "⚠️  ホストラッパーの停止中にエラーが発生しました（既に停止している可能性があります）"
    echo ""
fi

echo "✅ MAGIシステムの停止が完了しました"
echo ""

