# MCP設定がCursorの設定UIに表示されない問題

## 問題

Cursorの設定UI（`Cmd + ,`）で「MCP」または「Model Context Protocol」を検索しても、MCP設定が表示されない。

## 確認事項

### 1. 設定ファイルの場所と形式

Cursorは以下の場所からMCP設定を読み込みます：

#### プロジェクトローカル設定
- **場所**: `<プロジェクトルート>/.cursor/mcp.json`
- **必須フィールド**: `version`, `tools`

#### グローバル設定
- **場所（Mac）**: `~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp.json`
- **必須フィールド**: `version`, `tools`

### 2. 正しい設定ファイル形式

```json
{
  "version": "1.0",
  "tools": {
    "magi": {
      "type": "openapi",
      "server": {
        "url": "http://127.0.0.1:8787"
      },
      "schema": "http://127.0.0.1:8787/openapi.json"
    }
  }
}
```

**重要**:
- `version`フィールドは必須です
- `tools`ブロックは必須です
- `mcpServers`ブロックは不要です（OpenAPIツールの場合）

### 3. Cursorの設定UIでの確認方法

1. **設定を開く**: `Cmd + ,`
2. **検索**: 「MCP」または「Model Context Protocol」と入力
3. **確認**: MCPセクションが表示されるか確認

### 4. 開発者ツールでの確認

1. **開発者ツールを開く**: `Cmd + Shift + P` → 「Developer: Toggle Developer Tools」
2. **Consoleタブ**: エラーメッセージを確認
3. **Networkタブ**: `openapi.json`へのリクエストを確認

## 解決方法

### ステップ1: 設定ファイルの確認と修正

以下のコマンドで設定ファイルを確認・修正します：

```bash
cd /Users/toshiohanawa/Documents/projects/magi-system-mcp

# .cursor/mcp.jsonを確認
cat .cursor/mcp.json

# グローバル設定を確認
cat ~/Library/Application\ Support/Cursor/User/globalStorage/cursor.mcp.json
```

### ステップ2: versionフィールドの追加

設定ファイルに`version`フィールドがない場合、追加します：

```json
{
  "version": "1.0",
  "tools": {
    ...
  }
}
```

### ステップ3: Cursorの完全再起動

設定ファイルを修正した後、Cursorを完全に再起動します：

1. `Cmd + Q`でCursorを完全終了
2. Cursorを再起動
3. 設定UIでMCP設定を確認

### ステップ4: Cursorのバージョン確認

CursorのバージョンがMCPをサポートしているか確認します：

1. `Cmd + ,`で設定を開く
2. 「About」セクションでバージョンを確認
3. 必要に応じてCursorを最新版に更新

## 考えられる原因

### 1. Cursorのバージョンが古い

MCP機能は比較的新しい機能です。Cursorを最新版に更新してください。

### 2. 設定ファイルの形式が正しくない

- `version`フィールドが欠落している
- `tools`ブロックが欠落している
- JSONの構文エラーがある

### 3. Cursorが設定ファイルを読み込めていない

- ファイルの場所が間違っている
- ファイルの権限が正しくない
- Cursorが設定ファイルを認識していない

### 4. MCP機能が無効になっている

- Cursorの設定でMCP機能が無効になっている可能性
- 実験的機能として有効化が必要な可能性

## 代替方法

### 方法1: 直接API呼び出し

MCPツールが表示されなくても、直接APIを呼び出すことは可能です：

```bash
curl -X POST http://127.0.0.1:8787/magi/start \
  -H "Content-Type: application/json" \
  -d '{
    "initial_prompt": "テスト",
    "verbose": true
  }'
```

### 方法2: Cursorのコマンドパレットから確認

1. `Cmd + Shift + P`でコマンドパレットを開く
2. 「MCP」で検索
3. MCP関連のコマンドが表示されるか確認

### 方法3: 開発者ツールで確認

1. `Cmd + Shift + P`でコマンドパレットを開く
2. 「Developer: Toggle Developer Tools」を選択
3. Consoleタブでエラーメッセージを確認
4. Networkタブで`openapi.json`へのリクエストを確認

## 参考情報

- Cursor公式ドキュメント: https://docs.cursor.com/ja/context/mcp
- MCP設定ファイル: `.cursor/mcp.json`
- OpenAPIスキーマ: `http://127.0.0.1:8787/openapi.json`
- デバッグログ: `docker compose logs magi-mcp`



