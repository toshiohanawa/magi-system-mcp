# Cursor MCPツールが表示されない問題

## 問題

Cursorのチャットで`@`を押して`magi`と入力すると、ファイルやディレクトリの候補は表示されるが、MCPツール（`@start_magi_magi_start_post`など）が表示されない。

## 確認済み事項

### ✅ 正常に動作しているもの

1. **MCP設定ファイル**
   - `.cursor/mcp.json`が正しく存在し、`tools.magi`が定義されている
   - グローバル設定ファイルも存在

2. **OpenAPIスキーマ**
   - `http://127.0.0.1:8787/openapi.json`が正常に取得できる
   - `operationId`が正しく設定されている（`start_magi_magi_start_post`など）

3. **サーバー**
   - Dockerコンテナが正常に起動している
   - エンドポイントが正常に応答している

### ❌ 問題点

- Cursorのチャットで`@magi`と入力すると、ファイル/ディレクトリのみが表示される
- MCPツールが表示されない

## 考えられる原因

### 1. CursorのMCPツール表示方法の違い

Cursorは、`@`でファイル検索とMCPツールを別々に表示する可能性があります。

**確認方法**:
- `@`を押した後、ファイル候補の上または下に「Tools」や「MCP」セクションがあるか確認
- キーボードショートカットでMCPツール一覧を表示できるか確認

### 2. Cursorのバージョンや設定の問題

**確認方法**:
- Cursorのバージョンを確認
- Cursorの設定（`Cmd + ,`）で「MCP」または「Model Context Protocol」を検索
- MCP設定が有効になっているか確認

### 3. OpenAPIツールの認識方法

CursorがOpenAPIツールを認識する方法が異なる可能性があります。

**確認方法**:
- OpenAPIスキーマの形式がCursorの期待と一致しているか
- `operationId`の命名規則が正しいか

### 4. MCP設定の読み込みタイミング

**確認方法**:
- Cursorを完全に再起動したか
- 設定ファイルを変更した後、Cursorを再起動したか

## 解決方法

### 方法1: Cursorの設定UIから確認

1. `Cmd + ,`で設定を開く
2. 「MCP」または「Model Context Protocol」で検索
3. MCP設定が表示されるか確認
4. `magi`ツールがリストに表示されるか確認

### 方法2: コマンドパレットから確認

1. `Cmd + Shift + P`でコマンドパレットを開く
2. 「MCP」で検索
3. MCP関連のコマンドが表示されるか確認

### 方法3: 開発者ツールで確認

1. `Cmd + Shift + P`でコマンドパレットを開く
2. 「Developer: Toggle Developer Tools」を選択
3. Consoleタブでエラーメッセージを確認
4. Networkタブで`openapi.json`へのリクエストを確認

### 方法4: 直接API呼び出し

MCPツールが表示されなくても、直接APIを呼び出すことは可能です：

```bash
curl -X POST http://127.0.0.1:8787/magi/start \
  -H "Content-Type: application/json" \
  -d '{
    "initial_prompt": "テスト",
    "verbose": true
  }'
```

### 方法5: CursorのMCP設定形式の確認

Cursorが期待するMCP設定の形式が異なる可能性があります。

**現在の設定**:
```json
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
```

**試すべき設定**:
- `mcpServers`ブロックを完全に削除
- `tools`ブロックのみを使用
- スキーマURLを絶対パスで指定

## 次のステップ

1. Cursorの設定UIでMCP設定を確認
2. 開発者ツールでエラーを確認
3. CursorのバージョンとMCPサポート状況を確認
4. 必要に応じて、Cursorの公式ドキュメントやサポートに問い合わせ

## 参考情報

- MCP設定ファイル: `.cursor/mcp.json`
- OpenAPIスキーマ: `http://127.0.0.1:8787/openapi.json`
- デバッグログ: `docker compose logs magi-mcp`




