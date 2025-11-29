#!/bin/bash
# CursorのグローバルMCP設定にmagiを追加するスクリプト

set -e

MCP_CONFIG_DIR="$HOME/.cursor"
MCP_CONFIG_FILE="$MCP_CONFIG_DIR/mcp.json"

echo "=== CursorグローバルMCP設定への追加 ==="
echo ""

# .cursorディレクトリが存在しない場合は作成
if [ ! -d "$MCP_CONFIG_DIR" ]; then
    echo "📁 $MCP_CONFIG_DIR ディレクトリを作成します"
    mkdir -p "$MCP_CONFIG_DIR"
fi

# 既存の設定ファイルがあるか確認
if [ -f "$MCP_CONFIG_FILE" ]; then
    echo "✅ 既存の設定ファイルが見つかりました: $MCP_CONFIG_FILE"
    echo ""
    echo "現在の設定内容:"
    cat "$MCP_CONFIG_FILE" | python3 -m json.tool || echo "JSONの解析に失敗しました"
    echo ""
    
    # magiが既に存在するか確認
    if python3 -c "import json, sys; d=json.load(open('$MCP_CONFIG_FILE')); sys.exit(0 if 'tools' in d and 'magi' in d.get('tools', {}) else 1)" 2>/dev/null; then
        echo "⚠️  'magi'は既に設定に含まれています"
        echo "上書きしますか？ (y/N)"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            echo "キャンセルしました"
            exit 0
        fi
    fi
    
    # バックアップを作成
    echo "📋 バックアップを作成: ${MCP_CONFIG_FILE}.bak"
    cp "$MCP_CONFIG_FILE" "${MCP_CONFIG_FILE}.bak"
    
    # Pythonスクリプトでmagiを追加
    python3 << 'PYTHON_SCRIPT'
import json
import os
from pathlib import Path

config_file = Path(os.path.expanduser("~/.cursor/mcp.json"))

# 既存の設定を読み込み
with open(config_file, 'r') as f:
    config = json.load(f)

# versionが存在しない場合は追加
if 'version' not in config:
    config['version'] = '1.0'

# toolsが存在しない場合は作成
if 'tools' not in config:
    config['tools'] = {}

# magiを追加/更新（既存のmcpServersのmagiはそのまま保持）
config['tools']['magi'] = {
    "type": "openapi",
    "server": { "url": "http://127.0.0.1:8787" },
    "schema": "http://127.0.0.1:8787/openapi.json"
}

# 設定を保存
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)

print("✅ magiをtoolsセクションに追加しました")
print("   既存のmcpServersの設定は保持されています")
PYTHON_SCRIPT
    
else
    echo "📝 新規設定ファイルを作成します: $MCP_CONFIG_FILE"
    cat > "$MCP_CONFIG_FILE" << 'EOF'
{
  "version": "1.0",
  "tools": {
    "magi": {
      "type": "openapi",
      "server": { "url": "http://127.0.0.1:8787" },
      "schema": "http://127.0.0.1:8787/openapi.json"
    }
  }
}
EOF
    echo "✅ 設定ファイルを作成しました"
fi

echo ""
echo "=== 設定完了 ==="
echo ""
echo "更新後の設定内容:"
cat "$MCP_CONFIG_FILE" | python3 -m json.tool
echo ""
echo "📝 次のステップ:"
echo "1. Dockerブリッジを起動: docker-compose up"
echo "2. Cursorを完全に再起動"
echo "3. ツール一覧で 'magi' 関連のツールを確認"

