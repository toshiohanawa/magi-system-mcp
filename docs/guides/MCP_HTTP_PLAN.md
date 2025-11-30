# MCP HTTP MCP 対応（Claude デスクトップ向け）構想メモ

目的: 既存の FastAPI/OpenAPI（Cursor 用）を維持したまま、Claude デスクトップが扱える MCP 標準 (JSON-RPC over HTTP/SSE) 入口を追加する。

## 方針
- 既存ロジック (MAGIController/ProposalBattle/clients/settings) を再利用し、入口だけ増やす。
- `/mcp` に MCP JSON-RPC エンドポイントを追加。必要に応じて `/mcp/stream` で SSE による progress/timeline push を提供。
- 同一コンテナ・同一サービスで FastAPI にルートを足すだけ。別イメージは不要。

## 追加するメソッド（例）
- `tools/list`: `start`, `step`, `stop`, `health`
- `tools/call`:
  - `start`: `{initial_prompt, mode?, skip_claude?, fallback_policy?, verbose?}` → 既存と同じシグネチャ
  - `step`: `{session_id, decision}`
  - `stop`: `{session_id}`
  - `health`: `{}`
- （任意）`events/subscribe`: `session_id` を渡し、SSE で timeline/logs を逐次送信

## 実装手順（案）
1) `src/magi/mcp_http.py` 追加
   - `@app.post("/mcp")`: JSON-RPC ディスパッチ（method→controller 呼び出し）
   - `@app.get("/mcp/stream")`: SSE で timeline/logs を push（`verbose` または `MAGI_VERBOSE_DEFAULT` 有効時）
   - エラーは JSON-RPC の `code/message/data` で返却
2) 依存は増やさず、FastAPI 標準で JSON/SSE を実装
3) 設定共有: `.env`/Settings/AppConfig をそのまま使用。`MAGI_VERBOSE_DEFAULT` も有効。
4) Claude 用設定例: `mcp.json` に
   ```json
   {
     "mcpServers": {
       "magi": { "transport": "http", "uri": "http://127.0.0.1:8787/mcp" }
     }
   }
   ```
5) Docker: 既存サービスに `/mcp` を追加するだけ。別サービスを立てる場合は同イメージ流用で `command` を変えるだけでも可。

## テスト
- `tests/test_mcp_http.py` を追加して JSON-RPC リクエストの 200/エラー応答を確認。
- SSE は最小限の接続確認または手動手順を README に記載。

## ドキュメント更新
- README: Claude デスクトップ用の `transport=http` 設定例、SSE 受信方法、verbose/timeline 連携の注意。
- docs/INDEX.md: MCP HTTP 対応を追記。
