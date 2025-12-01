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

## 問題5: Codex/Geminiの権限エラー

### 症状

以下のようなエラーメッセージが表示される場合：

- **Codex**: `Operation not permitted (os error 1)`
- **Gemini**: `EPERM: operation not permitted, uv_cwd`

### 原因

ホストラッパーがCLIを実行する際に、作業ディレクトリ（cwd）と環境変数が適切に設定されていないことが原因です。特にNode.jsベースのGemini CLIでは、`HOME`、`PWD`、`USER`などの環境変数が必須です。

### 解決策

この問題は既にコードで修正済みです（`host_wrappers/base_wrapper.py`と`host_wrappers/gemini_wrapper.py`）。以下の確認を行ってください：

#### 1. 最新のコードが使用されているか確認

```bash
# プロジェクトルートで最新のコードを確認
cd /path/to/magi-system-mcp
git pull  # リモートから最新を取得する場合

# 修正が含まれているか確認
grep -n "cwd=cwd" host_wrappers/base_wrapper.py
grep -n "cwd=cwd" host_wrappers/gemini_wrapper.py
```

#### 2. ホストラッパーを再起動

修正が反映されていない場合は、ホストラッパーを再起動してください：

```bash
# 既存のラッパーを停止
bash scripts/stop_host_wrappers.sh

# ラッパーを再起動
bash scripts/start_host_wrappers.sh
```

#### 3. 動作確認

```bash
# 各ラッパーのヘルスチェック
curl http://127.0.0.1:9001/health  # Codex
curl http://127.0.0.1:9003/health  # Gemini

# 実際にテスト実行
curl -X POST http://127.0.0.1:9003/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test"}' | python3 -m json.tool
```

### 技術的な詳細

修正内容：

1. **`host_wrappers/base_wrapper.py`**:
   - `asyncio.create_subprocess_exec`に`cwd`パラメータを追加
   - `env`パラメータで環境変数を明示的に設定（`HOME`、`USER`、`PWD`）

2. **`host_wrappers/gemini_wrapper.py`**:
   - `asyncio.create_subprocess_exec`に`cwd`パラメータを追加
   - `env`パラメータでNode.jsに必要な環境変数を設定（`NODE_ENV`を含む）

### 新しい環境でのセットアップ時の注意

新しい端末でセットアップする際は、以下の点に注意してください：

1. **環境変数の確認**: `HOME`、`USER`、`PWD`が適切に設定されているか確認
   ```bash
   echo $HOME
   echo $USER
   echo $PWD
   ```

2. **作業ディレクトリの確認**: プロジェクトルートでコマンドを実行しているか確認
   ```bash
   pwd
   # プロジェクトルートであることを確認
   ```

3. **ラッパーの起動**: 必ずプロジェクトルートからラッパーを起動
   ```bash
   cd /path/to/magi-system-mcp
   bash scripts/start_host_wrappers.sh
   ```

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

# ラッパーの状態
curl http://127.0.0.1:9001/health  # Codex
curl http://127.0.0.1:9002/health  # Claude
curl http://127.0.0.1:9003/health  # Gemini
curl http://127.0.0.1:9004/health  # Judge
```



