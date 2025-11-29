# MAGI System MCP

ローカル専用の Proposal Battle 型マルチ LLM エンジン。Codex (Execution) / Claude (Evaluation) / Gemini (Exploration) を順番実行し、CursorがJudgeとして3案を比較・選択します。MCPサーバー経由で利用できます。

**全LLMはCLI版のみ対応**（HTTP API/SDK呼び出しは全面禁止）

**新構成**: ホスト側でCLIを実行するHTTPラッパー（FastAPI）を起動し、Dockerコンテナ内のブリッジはHTTP経由で接続します。これにより、macOS用バイナリの問題を回避できます。

## 処理フロー

```
┌─────────────────────────────────────────────────────────────────┐
│                         Cursor (MCP Client)                      │
│                    (Proposal Battle の Judge)                     │
└────────────────────────────┬──────────────────────────────────────┘
                             │
                             │ MCP Protocol (OpenAPI)
                             │ http://127.0.0.1:8787/openapi.json
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Dockerブリッジ (MCP Server)                    │
│              http://127.0.0.1:8787 (ポート8787)                   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  FastAPI Server (src/api/server.py)                      │   │
│  │  - /magi/start: Proposal Battle開始                      │   │
│  │  - /magi/step: 採択案取得                                │   │
│  │  - /magi/stop: セッション停止                            │   │
│  │  - /health: ヘルスチェック                                │   │
│  └────────────────────┬─────────────────────────────────────┘   │
│                       │                                          │
│  ┌────────────────────▼─────────────────────────────────────┐   │
│  │  MAGI Controller (src/magi/controller.py)               │   │
│  │  - ProposalBattleMode実行                                │   │
│  │  - 3つのLLMクライアントを順次実行                         │   │
│  └────────────────────┬─────────────────────────────────────┘   │
│                       │                                          │
│  ┌────────────────────▼─────────────────────────────────────┐   │
│  │  HTTP Clients (src/magi/clients/*.py)                    │   │
│  │  - CodexClient → http://host.docker.internal:9001        │   │
│  │  - ClaudeClient → http://host.docker.internal:9002       │   │
│  │  - GeminiClient → http://host.docker.internal:9003       │   │
│  │  - JudgeClient → http://host.docker.internal:9004        │   │
│  └────────────────────┬─────────────────────────────────────┘   │
└────────────────────────┼──────────────────────────────────────────┘
                         │
                         │ HTTP (httpx)
                         │ host.docker.internal:9001-9004
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ホスト側 HTTPラッパー                           │
│              (FastAPI, ポート9001-9004)                           │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  codex_wrapper (ポート9001)                               │   │
│  │  - /generate: CLI実行エンドポイント                        │   │
│  │  - /health: ヘルスチェック                                 │   │
│  └────────────────────┬─────────────────────────────────────┘   │
│                       │                                          │
│  ┌────────────────────▼─────────────────────────────────────┐   │
│  │  base_wrapper.py (共通実装)                                │   │
│  │  - CLIコマンド実行 (asyncio.subprocess)                    │   │
│  │  - 標準入力からプロンプトを受け取り                         │   │
│  │  - 標準出力に結果を返す                                     │   │
│  └────────────────────┬─────────────────────────────────────┘   │
└────────────────────────┼──────────────────────────────────────────┘
                         │
                         │ CLI実行
                         │ (環境変数 CODEX_COMMAND などで設定)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    実LLM CLI (ホスト側)                            │
│                                                                   │
│  - codex exec --skip-git-repo-check                              │
│  - claude generate                                               │
│  - gemini generate (Autoモード)                                  │
│  - judge generate                                                │
│                                                                   │
│  ※ macOS用バイナリもホスト側で実行されるため問題なく動作          │
└─────────────────────────────────────────────────────────────────┘
```

### フロー詳細

1. **Cursor (MCP Client)**
   - `mcp.json`を読み込み、OpenAPIスキーマを参照
   - Proposal BattleのJudgeとして動作

2. **Dockerブリッジ (MCP Server)**
   - FastAPIサーバーがMCPリクエストを受信
   - MAGI ControllerがProposal Battleモードを実行
   - 3つのLLMクライアント（Codex, Claude, Gemini）を順次実行

3. **HTTPクライアント**
   - `httpx`を使用してホスト側のHTTPラッパーに接続
   - `host.docker.internal:9001-9004`経由でアクセス

4. **ホスト側HTTPラッパー**
   - FastAPIアプリケーションとして各LLM CLIをラップ
   - `/generate`エンドポイントでCLIを実行
   - 標準入力からプロンプトを受け取り、標準出力に結果を返す

5. **実LLM CLI**
   - ホスト側で直接実行されるため、macOS用バイナリも問題なく動作
   - 環境変数でCLIコマンドをカスタマイズ可能

## 構成
- `src/magi`: モード・クライアント・コントローラー実装
- `src/api/server.py`: FastAPI MCP サーバー (`/magi/start`, `/magi/step`, `/magi/stop`)
- `mcp.json`: Cursor からの MCP 接続設定（OpenAPIツールとして http://127.0.0.1:8787 と /openapi.json を参照）
- `openapi.json`: OpenAPI スキーマ（サーバー読み込み時にも再生成、ローカル確認用）
- `Dockerfile` / `docker-compose.yml`: 非 root・127.0.0.1 バインドでのコンテナ実行

## LLM CLI設定
全LLMはホスト側のHTTPラッパー経由でCLIコマンドを実行します。環境変数で上書き可能です：
- Codex: `CODEX_COMMAND` (デフォルト: `codex exec --skip-git-repo-check`)
- Claude: `CLAUDE_COMMAND` (デフォルト: `claude generate`)
- Gemini: `GEMINI_COMMAND` (デフォルト: `gemini generate` - Autoモード)
- Judge: `JUDGE_COMMAND` (デフォルト: `judge generate`)

各CLIは標準入力からプロンプトを受け取り、標準出力に結果を返します。タイムアウトはデフォルト120秒（`WRAPPER_TIMEOUT` で変更可）、エラー時はスタブ応答を返します。

タイムアウト調整:
- HTTPクライアント側: `LLM_TIMEOUT` または個別に `CODEX_TIMEOUT` / `CLAUDE_TIMEOUT` / `GEMINI_TIMEOUT` / `JUDGE_TIMEOUT`
- ラッパー側: `WRAPPER_TIMEOUT`（FastAPI側でCLI実行を待つ上限）

HTTPラッパーのURLは環境変数で上書き可能です（デフォルト: `http://host.docker.internal:900{1-4}`）：
- `CODEX_WRAPPER_URL`, `CLAUDE_WRAPPER_URL`, `GEMINI_WRAPPER_URL`, `JUDGE_WRAPPER_URL`

### 動作確認

ホストラッパーとブリッジが正しく動作しているか確認します：

```bash
# ヘルスチェックで確認
curl http://127.0.0.1:8787/health
```

レスポンス例（すべてのラッパーが利用可能な場合）:
```json
{
  "status": "ok",
  "commands": {
    "codex": true,
    "claude": true,
    "gemini": true
  }
}
```

すべてのコマンドが `true` になっていれば、HTTPラッパーが正常に動作しています。

**注意**: 
- ホストラッパーが起動していない場合、スタブ応答が返されます。
- macOS用バイナリ（claude/gemini）もホスト側で実行されるため、問題なく動作します。

## 使い方

### ホストラッパーの起動（推奨）
1. 依存インストール: `pip install -r host_wrappers/requirements.txt`
2. 別ターミナルでそれぞれ起動（ポート: codex=9001, claude=9002, gemini=9003, judge=9004）
   ```bash
   uvicorn host_wrappers.codex_wrapper:app --host 127.0.0.1 --port 9001
   uvicorn host_wrappers.claude_wrapper:app --host 127.0.0.1 --port 9002
   uvicorn host_wrappers.gemini_wrapper:app --host 127.0.0.1 --port 9003
   uvicorn host_wrappers.judge_wrapper:app --host 127.0.0.1 --port 9004
   ```
   CLIコマンドは環境変数 `CODEX_COMMAND` などで上書き可。

### MCPブリッジ（Docker）起動
ホストラッパーを起動した状態で、ブリッジをDockerで立ち上げます：
```bash
docker-compose up --build
```
コンテナ内のクライアントは `http://host.docker.internal:900{1-4}` にHTTPで接続します。

### スキーマ確認
```bash
curl http://127.0.0.1:8787/openapi.json
```

### MCP設定
プロジェクトルートの `mcp.json` を使用（OpenAPI参照）。Cursor等のクライアントに読み込ませれば、起動中のサーバーに接続できます。

### 運用・トラブルシュート（LLM実行）
- 接続先: Docker内からは `host.docker.internal`、ホストから直接走らせる場合は自動で `127.0.0.1` にフォールバック。必要なら `*_WRAPPER_URL` で固定。
- 起動順: 1) ホストでラッパー起動 → 2) `docker-compose up`。ラッパー未起動ならスタブ応答になります。
- タイムアウト: Codex/Gemini は重いので `WRAPPER_TIMEOUT` と `CODEX_TIMEOUT` / `GEMINI_TIMEOUT` を120〜180秒に調整推奨。全体に効かせる場合は `LLM_TIMEOUT`。
- 504/ReadTimeout: CLI完了待ち。タイムアウトを延長し、`ps` 等でハング確認、短いプロンプトで所要時間を計測すると切り分けやすいです。
- スタブ応答: `/health` が ok か、`CODEX_COMMAND` などコマンドパスが正しいか、ラッパーがリッスンしているかを確認。

## Docker設定
- ポート: `127.0.0.1:8787`（外部公開なし）
- ボリューム:
  - プロジェクトルート: `.` (read-write)
- 非rootユーザー (`mcp`) で実行
- セキュリティ: 127.0.0.1バインド、APIキー/秘密情報をログ出力しない
- **注意**: Dockerコンテナ内でLLM CLIは実行しません。ホスト側のHTTPラッパー経由で接続します。

### ヘルスチェック
```bash
curl http://127.0.0.1:8787/health
```

レスポンス例:
```json
{
  "status": "ok",
  "commands": {
    "codex": true,
    "claude": true,
    "gemini": true
  }
}
```

- `status: "ok"`: すべてのCLIが利用可能
- `status: "degraded"`: 1つ以上のCLIが利用不可

## MCP設定方法（Cursor）

### 前提条件
1. Dockerコンテナが起動していること
   ```bash
   docker-compose up -d
   ```

2. MCPサーバーが`http://127.0.0.1:8787`で動作していること
   ```bash
   curl http://127.0.0.1:8787/openapi.json
   ```

### Cursorでの設定手順

#### 1. プロジェクトルートの`mcp.json`を使用（推奨）

プロジェクトルートに`mcp.json`が存在する場合、Cursorは自動的にこの設定を使用します（OpenAPI MCPツールとしてコンテナの `/openapi.json` を参照）：

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

#### 2. グローバル設定に追加（オプション）

`~/.cursor/mcp.json` に追加する場合も同じ形式で `tools.magi` を追加します：

```json
{
  "version": "1.0",
  "tools": {
    "existing-tool": { },
    "magi": {
      "type": "openapi",
      "server": { "url": "http://127.0.0.1:8787" },
      "schema": "http://127.0.0.1:8787/openapi.json"
    }
  }
}
```

**重要**: 既存の `mcpServers` に `magi` が含まれている場合は、削除してください。`tools` 形式の設定が優先されますが、`mcpServers` の設定が残っていると混乱の原因になります。

#### 3. Cursorの再起動
設定を反映するために、Cursorを完全に再起動します。

#### 4. 動作確認
Cursorのチャットで、MCPサーバーが利用可能か確認します：
- ツール一覧に以下が表示される：
  - `start_magi_magi_start_post`: Proposal Battleを開始
  - `step_magi_magi_step_post`: 採択案を取得
  - `stop_magi_magi_stop_post`: セッションを停止
  - `health_health_get`: ヘルスチェック（CLI状態を取得）

**注意**: `magi`はOpenAPIツールのため、MCPサーバー一覧には表示されません。ツール一覧で確認してください。

### トラブルシューティング

#### 問題: MCPツールが表示されない
1. Dockerコンテナが起動しているか確認
   ```bash
   docker compose ps
   ```

2. MCPサーバーが応答するか確認
   ```bash
   curl http://127.0.0.1:8787/openapi.json
   ```

3. `mcp.json`の設定が正しいか確認（コンテナ経由のURL参照 `http://127.0.0.1:8787/openapi.json` を使用）

4. Cursorを完全に再起動

#### 問題: スキーマが見つからない
- `schema`がコンテナ経由のURL（`http://127.0.0.1:8787/openapi.json`）になっているか確認
- Dockerコンテナが正常に起動しているか確認
- `curl http://127.0.0.1:8787/openapi.json` でスキーマが取得できるか確認

#### 問題: 接続エラー
- Dockerコンテナが`127.0.0.1:8787`でリッスンしているか確認
- ファイアウォール設定を確認
- ポート8787が他のプロセスで使用されていないか確認

### 利用可能なエンドポイント

MCPツールとして利用可能なエンドポイント：

1. **`POST /magi/start`** - Proposal Battleを開始
   - リクエスト: `{"initial_prompt": "your prompt", "mode": "proposal_battle"}`
   - レスポンス: `{"session_id": "...", "results": {...}}`

2. **`POST /magi/step`** - 採択案を取得
   - リクエスト: `{"session_id": "...", "decision": "codex|claude|gemini|judge"}`
   - レスポンス: `{"session_id": "...", "adopted_model": "...", "adopted_text": "..."}`

3. **`POST /magi/stop`** - セッションを停止
   - リクエスト: `{"session_id": "..."}`
   - レスポンス: `{"session_id": "...", "stopped": true}`

4. **`GET /health`** - ヘルスチェック（CLI状態を取得）
   - レスポンス: `{"status": "ok|degraded", "commands": {"codex": true, "claude": true, "gemini": true}}`

## テスト
```
pytest
```
