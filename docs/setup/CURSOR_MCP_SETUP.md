# Cursor MCP設定ガイド

## 問題: `/magi/start`がCursorのツール一覧に表示されない

### 原因
Cursorはプロジェクトルートの`mcp.json`を自動的に読み込みません。以下のいずれかの場所に設定ファイルを配置する必要があります：

1. **プロジェクトローカル**: `<repo>/.cursor/mcp.json`
2. **グローバル**: `~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp.json` (Mac)

### 解決方法

#### 方法1: プロジェクトローカル設定（推奨）

プロジェクトルートに`.cursor/mcp.json`を作成します：

```bash
mkdir -p .cursor
cat > .cursor/mcp.json << 'EOF'
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
```

その後、**Cursorを完全に再起動**してください。

#### 方法2: グローバル設定

グローバル設定ファイルに追加する場合：

```bash
# Macの場合
GLOBAL_MCP="$HOME/Library/Application Support/Cursor/User/globalStorage/cursor.mcp.json"

# 既存の設定がある場合はバックアップ
if [ -f "$GLOBAL_MCP" ]; then
  cp "$GLOBAL_MCP" "${GLOBAL_MCP}.bak"
fi

# magi設定を追加（既存のtoolsブロックに追加）
python3 << 'PYTHON_SCRIPT'
import json
import os
from pathlib import Path

config_file = Path(os.path.expanduser("~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp.json"))

# 既存の設定を読み込み（存在しない場合は新規作成）
if config_file.exists():
    with open(config_file, 'r') as f:
        config = json.load(f)
else:
    config = {"version": "1.0", "tools": {}}

# versionが存在しない場合は追加
if 'version' not in config:
    config['version'] = '1.0'

# toolsが存在しない場合は作成
if 'tools' not in config:
    config['tools'] = {}

# magiを追加/更新
config['tools']['magi'] = {
    "type": "openapi",
    "server": { "url": "http://127.0.0.1:8787" },
    "schema": "http://127.0.0.1:8787/openapi.json"
}

# 設定を保存
config_file.parent.mkdir(parents=True, exist_ok=True)
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)

print("✅ magiをtoolsセクションに追加しました")
PYTHON_SCRIPT
```

その後、**Cursorを完全に再起動**してください。

### 確認手順

1. **サーバーが起動しているか確認**
   ```bash
   curl http://127.0.0.1:8787/openapi.json
   ```
   200レスポンスが返ればOK

2. **Dockerコンテナが起動しているか確認**
   ```bash
   docker compose ps
   ```
   `magi-mcp`コンテナが`Up`状態であればOK

3. **設定ファイルの場所を確認**
   ```bash
   # プロジェクトローカル
   cat .cursor/mcp.json
   
   # グローバル（Mac）
   cat ~/Library/Application\ Support/Cursor/User/globalStorage/cursor.mcp.json
   ```

4. **Cursorを完全に再起動**
   - Cursorを完全終了（⌘+Q）
   - 再起動
   - `@`を押してツール一覧を確認

### ツール名について

OpenAPIツールは自動生成された名前で表示されます：
- `start_magi_magi_start_post` - `/magi/start`エンドポイント
- `step_magi_magi_step_post` - `/magi/step`エンドポイント
- `stop_magi_magi_stop_post` - `/magi/stop`エンドポイント
- `health_health_get` - `/health`エンドポイント

`@`を押した後、`start_magi`や`magi`で検索すると見つかります。

### トラブルシューティング

#### 問題1: ツールが表示されない
- ✅ サーバーが起動しているか確認
- ✅ 設定ファイルが正しい場所にあるか確認
- ✅ Cursorを完全に再起動したか確認
- ✅ `mcpServers`ブロックが残っていないか確認（`tools`ブロックのみを使用）

#### 問題2: スキーマ取得エラー
- ✅ `curl http://127.0.0.1:8787/openapi.json`で確認
- ✅ Dockerコンテナが正常に起動しているか確認
- ✅ ファイアウォール設定を確認

#### 問題3: 接続エラー
- ✅ ポート8787が他のプロセスで使用されていないか確認
- ✅ Dockerコンテナのログを確認: `docker compose logs magi-mcp`

### 注意事項

- **`mcpServers`ブロックは使用しない**: 旧形式の`mcpServers`が残っているとツール解決が混乱します。`tools`ブロックのみを使用してください。
- **プロジェクトルートの`mcp.json`は無視される**: Cursorはこのファイルを自動的に読み込みません。`.cursor/mcp.json`またはグローバル設定を使用してください。

