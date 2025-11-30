# MCP設定の復元方法

## 問題

Cursorの設定変更により、既存のMCP設定が消失した可能性があります。

## 復元方法

### 1. バックアップファイルの確認

以下の場所にバックアップファイルがあるか確認してください：

```bash
# グローバル設定のバックアップ
ls -la ~/Library/Application\ Support/Cursor/User/globalStorage/*.bak

# プロジェクトローカル設定のバックアップ
ls -la .cursor/*.bak
```

### 2. Time Machineバックアップから復元（Mac）

Time Machineを使用している場合：

1. Time Machineを開く
2. `~/Library/Application Support/Cursor/User/globalStorage/` に移動
3. `cursor.mcp.json` の以前のバージョンを探す
4. 復元する

### 3. 手動で設定を再構築

既存のMCP設定を覚えている場合、以下の形式で再作成できます：

#### グローバル設定ファイル

```bash
cat > ~/Library/Application\ Support/Cursor/User/globalStorage/cursor.mcp.json << 'EOF'
{
  "mcpServers": {
    "your-existing-server": {
      "command": "your-command",
      "args": ["arg1", "arg2"],
      "env": {}
    }
  },
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

#### プロジェクトローカル設定ファイル

```bash
cat > .cursor/mcp.json << 'EOF'
{
  "mcpServers": {},
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

### 4. Cursorの設定UIから確認

1. Cursorを開く
2. `Cmd + ,` で設定を開く
3. 「MCP」または「Model Context Protocol」で検索
4. 既存の設定が表示されるか確認

### 5. 設定ファイルの形式について

CursorのMCP設定ファイルには2つの形式があります：

#### `mcpServers`形式
MCPサーバーを直接起動する場合に使用：

```json
{
  "mcpServers": {
    "server-name": {
      "command": "command-to-run",
      "args": ["arg1", "arg2"],
      "env": {}
    }
  }
}
```

#### `tools`形式
OpenAPIツールなどの外部ツールを定義する場合に使用：

```json
{
  "tools": {
    "tool-name": {
      "type": "openapi",
      "server": { "url": "http://127.0.0.1:8787" },
      "schema": "http://127.0.0.1:8787/openapi.json"
    }
  }
}
```

**重要**: エラーメッセージ「mcpServers must be an object」が表示される場合、`mcpServers`ブロックを空のオブジェクト`{}`として追加する必要があります。

### 6. 現在の設定確認

```bash
# プロジェクトローカル設定
cat .cursor/mcp.json

# グローバル設定
cat ~/Library/Application\ Support/Cursor/User/globalStorage/cursor.mcp.json
```

## 今後の対策

1. **定期的なバックアップ**: 設定ファイルを定期的にバックアップする
2. **バージョン管理**: `.cursor/mcp.json`をGitにコミットする（機密情報を含まない場合）
3. **設定の記録**: 使用しているMCPサーバーとツールのリストを保持する


