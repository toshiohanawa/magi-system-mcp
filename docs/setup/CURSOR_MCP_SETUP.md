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
  "magi": {
    "command": "npx",
    "args": ["-y", "@ivotoby/openapi-mcp-server"],
    "env": {
      "API_BASE_URL": "http://127.0.0.1:8787",
      "OPENAPI_SPEC_PATH": "http://127.0.0.1:8787/openapi.json"
    }
  }
}
EOF
```

その後、**Cursorを完全に再起動**してください。

#### 方法2: グローバル設定

すべてのプロジェクトでMAGIシステムを使用する場合は、グローバル設定に追加します。

**macOSの場合:**
```bash
# グローバル設定ファイルのパス
GLOBAL_MCP="$HOME/Library/Application Support/Cursor/User/globalStorage/cursor.mcp.json"

# 既存の設定がある場合はバックアップ
if [ -f "$GLOBAL_MCP" ]; then
  cp "$GLOBAL_MCP" "${GLOBAL_MCP}.bak"
fi

# 既存の設定を読み込んでmagiを追加
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
    config = {}

# magiを追加/更新
config['magi'] = {
    "command": "npx",
    "args": ["-y", "@ivotoby/openapi-mcp-server"],
    "env": {
        "API_BASE_URL": "http://127.0.0.1:8787",
        "OPENAPI_SPEC_PATH": "http://127.0.0.1:8787/openapi.json"
    }
}

# 設定を保存
config_file.parent.mkdir(parents=True, exist_ok=True)
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)

print("✅ magi設定を追加しました")
PYTHON_SCRIPT
```

**Linuxの場合:**
```bash
GLOBAL_MCP="$HOME/.config/Cursor/User/globalStorage/cursor.mcp.json"
# 以下、macOSと同様の手順（パスのみ変更）
```

**Windowsの場合:**
```bash
GLOBAL_MCP="$APPDATA\Cursor\User\globalStorage\cursor.mcp.json"
# 以下、macOSと同様の手順（パスのみ変更）
```

> **注意**: グローバル設定ファイルが既に存在する場合は、JSON形式を維持するため、手動で編集するか、上記のPythonスクリプトを使用して既存の設定に`magi`エントリを追加してください。

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
- ✅ 設定形式が正しいか確認（`tools`ブロックではなく、直接サーバー名をキーとして設定）

#### 問題2: スキーマ取得エラー
- ✅ `curl http://127.0.0.1:8787/openapi.json`で確認
- ✅ Dockerコンテナが正常に起動しているか確認
- ✅ ファイアウォール設定を確認

#### 問題3: 接続エラー
- ✅ ポート8787が他のプロセスで使用されていないか確認
- ✅ Dockerコンテナのログを確認: `docker compose logs magi-mcp`

### 注意事項

- **設定形式**: `tools`ブロックではなく、直接サーバー名（`magi`）をキーとして設定します。`command`、`args`、`env`を使用します。
- **プロジェクトルートの`mcp.json`は無視される**: Cursorはこのファイルを自動的に読み込みません。`.cursor/mcp.json`またはグローバル設定を使用してください。
- **グローバル設定の場所**:
  - macOS: `~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp.json`
  - Linux: `~/.config/Cursor/User/globalStorage/cursor.mcp.json`
  - Windows: `%APPDATA%\Cursor\User\globalStorage\cursor.mcp.json`

