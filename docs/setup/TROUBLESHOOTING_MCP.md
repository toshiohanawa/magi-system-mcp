# MCPツールが表示されない場合のトラブルシューティング

## 確認事項

### 1. 設定ファイルの場所

Cursorは以下の場所からMCP設定を読み込みます：

#### プロジェクトローカル（推奨）
- **場所**: `<プロジェクトルート>/.cursor/mcp.json`
- **現在の状態**: ✅ 作成済み

#### グローバル設定
- **場所（Mac）**: `~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp.json`
- **現在の状態**: 確認が必要

### 2. 設定ファイルの形式

正しい形式：
```json
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
```

**重要**: `mcpServers`ブロックは使用しないでください。`tools`ブロックのみを使用します。

### 3. サーバーの状態

- ✅ Dockerコンテナが起動中
- ✅ OpenAPIスキーマが取得可能: `curl http://127.0.0.1:8787/openapi.json`

## 解決手順

### ステップ1: グローバル設定ファイルの作成/更新

以下のコマンドを実行して、グローバル設定ファイルに`magi`を追加します：

```bash
cd /Users/toshiohanawa/Documents/projects/magi-system-mcp
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
    json.dump(config, f, indent=2, ensure_ascii=False)

print("✅ magiをtoolsセクションに追加しました")
PYTHON_SCRIPT
```

### ステップ2: Cursorの設定UIから確認

1. Cursorを開く
2. `Cmd + ,` (設定) を開く
3. 「MCP」または「Model Context Protocol」で検索
4. MCP設定が表示されるか確認

### ステップ3: Cursorを完全に再起動

1. Cursorを完全終了（⌘+Q）
2. 再起動
3. `@`を押してツール一覧を確認

### ステップ4: ツール一覧の確認方法

`@`を押した後、以下の方法でツールを探してください：

1. **検索ボックスで検索**: `magi`、`start`、`health`などで検索
2. **ツール名で検索**: `start_magi_magi_start_post`、`health_health_get`など

OpenAPIツールは自動生成された名前で表示されるため、`magi`という名前では表示されない場合があります。

### ステップ5: デバッグ情報の確認

Cursorの開発者ツールでエラーを確認：

1. `Cmd + Shift + P` でコマンドパレットを開く
2. 「Developer: Toggle Developer Tools」を選択
3. Consoleタブでエラーメッセージを確認

## よくある問題

### 問題1: `.cursor/mcp.json`が読み込まれない

**原因**: Cursorのバージョンや設定によって、プロジェクトローカルの設定が読み込まれない場合があります。

**解決策**: グローバル設定ファイルを使用してください。

### 問題2: `mcpServers`ブロックが残っている

**原因**: 旧形式の`mcpServers`ブロックが残っていると、ツール解決が混乱します。

**解決策**: `mcpServers`ブロックを削除し、`tools`ブロックのみを使用してください。

### 問題3: スキーマURLにアクセスできない

**原因**: Dockerコンテナが起動していない、またはネットワークの問題。

**解決策**: 
```bash
# サーバーが起動しているか確認
docker compose ps

# OpenAPIスキーマが取得できるか確認
curl http://127.0.0.1:8787/openapi.json
```

### 問題4: ツール名が表示されない

**原因**: OpenAPIツールは自動生成された名前で表示されるため、期待した名前と異なる場合があります。

**解決策**: `@`を押した後、検索ボックスで`magi`、`start`、`health`などで検索してください。

## 確認コマンド

以下のコマンドで現在の状態を確認できます：

```bash
# プロジェクトローカル設定
cat .cursor/mcp.json

# グローバル設定（Mac）
cat ~/Library/Application\ Support/Cursor/User/globalStorage/cursor.mcp.json

# サーバーの状態
curl http://127.0.0.1:8787/openapi.json | python3 -m json.tool | head -20

# Dockerコンテナの状態
docker compose ps
```



