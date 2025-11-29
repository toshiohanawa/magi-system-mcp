#!/usr/bin/env bash
# ホストラッパーを停止するスクリプト

set -euo pipefail

echo "=== ホストラッパーを停止します ==="
echo ""

# PIDファイルから停止
if [ -f /tmp/magi_wrappers.pid ]; then
    PIDS=$(cat /tmp/magi_wrappers.pid)
    echo "PIDファイルから停止: $PIDS"
    kill $PIDS 2>/dev/null || true
    rm /tmp/magi_wrappers.pid
fi

# プロセス名で停止
pkill -f 'uvicorn host_wrappers' 2>/dev/null || true

echo "✅ ホストラッパーを停止しました"
echo ""

# ポートが解放されたか確認
PORTS=(9001 9002 9003 9004)
for port in "${PORTS[@]}"; do
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo "⚠️  ポート $port はまだ使用中です"
    else
        echo "✅ ポート $port は解放されました"
    fi
done


