# MAGI System MCP

ローカル専用の Proposal Battle 型マルチ LLM エンジン。Codex (Execution) / Claude (Evaluation) / Gemini (Exploration) を順番実行し、CursorがJudgeとして3案を比較・選択します。MCPサーバー経由で利用できます。

**全LLMはCLI版のみ対応**（HTTP API/SDK呼び出しは全面禁止）

**構成**: デフォルトではホスト側でFastAPIラッパーを起動し、CLIバイナリ（codex, claude, gemini, judge）をホスト側で実行します。DockerfileにはCLIは同梱されていません（イメージを軽量化するため）。コンテナ内でCLIを動かす場合は、README記載のスニペットをDockerfileに追記してCLIをインストールしてください。その後、`USE_CONTAINER_WRAPPERS=1 scripts/start_magi.sh` でコンテナ化ラッパーに切り替え可能です。

## ドキュメントマップ
- まずは本READMEの「クイックセットアップ」と「MCP設定」を確認。
- **セットアップ関連**: `docs/setup/` - Cursor MCP設定、トラブルシューティング
- **ユーザーガイド**: `docs/guides/` - Cursorでの使用方法、MCP HTTP実装計画
- **開発者向け**: `docs/development/` - 既知課題、Phase1実装詳細
- **アーカイブ**: `docs/archive/` - 過去のリファクタリングログ、デバッグ記録
- すべてのドキュメントへのリンク一覧は `docs/INDEX.md` を参照。

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
│  │  - CodexClient → http://codex-wrapper:9001（ホストモード時はhost.docker.internal）│
│  │  - ClaudeClient → http://claude-wrapper:9002（同上）      │   │
│  │  - GeminiClient → http://gemini-wrapper:9003（同上）      │   │
│  │  - JudgeClient → http://judge-wrapper:9004（同上）        │   │
│  └────────────────────┬─────────────────────────────────────┘   │
└────────────────────────┼──────────────────────────────────────────┘
                         │
                         │ HTTP (httpx)
                         │ host.docker.internal:9001-9004
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    HTTPラッパー (コンテナ/ホスト)                       │
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
  - `models.py`: データモデル（`ModelOutput`, `LLMSuccess`, `LLMFailure`, `MagiDecision`, `Persona`, `Vote`, `Decision`, `RiskLevel`）
  - `clients/`: LLMクライアント実装（型安全なエラーハンドリング対応）
  - `config.py`: 設定管理（後方互換性維持）
  - `settings.py`: pydantic-settingsベースの設定管理（Phase 1）
  - `logging_config.py`: 構造化ロギングシステム（Phase 1）
  - `personas.py`: ペルソナプロンプト定義（Melchior, Balthasar, Caspar）
  - `prompt_builder.py`: ペルソナプロンプトビルダー
  - `consensus.py`: MAGI Consensus Engine（並列評価、投票、リスク評価）
- `src/api/server.py`: FastAPI MCP サーバー (`/magi/start`, `/magi/step`, `/magi/stop`)
- `mcp.json`: Cursor からの MCP 接続設定（OpenAPIツールとして http://127.0.0.1:8787 と /openapi.json を参照）
- `openapi.json`: OpenAPI スキーマ（サーバー読み込み時にも再生成、ローカル確認用）
- `Dockerfile` / `docker-compose.yml`: 非 root・127.0.0.1 バインドでのコンテナ実行
- `tests/test_integration.py`: 統合テスト（Phase 1）

## LLM CLI設定
全LLMはHTTPラッパー経由でCLIコマンドを実行します。デフォルトではホストラッパーを使用し、環境変数で上書き可能です（コンテナ化ラッパーを使う場合は `USE_CONTAINER_WRAPPERS=1` を指定）：
- Codex: `CODEX_COMMAND` (デフォルト: `codex exec --skip-git-repo-check`)
- Claude: `CLAUDE_COMMAND` (デフォルト: `claude generate`)
- Gemini: `GEMINI_COMMAND` (デフォルト: `gemini generate` - Autoモード)
- Judge: `JUDGE_COMMAND` (デフォルト: `judge generate`)

各CLIは標準入力からプロンプトを受け取り、標準出力に結果を返します。タイムアウトはデフォルト600秒（10分）で、`MAGI_TIMEOUT_DEFAULT` を基準に全コンポーネントで共有できます。

タイムアウト調整（値を1カ所で揃える場合は `MAGI_TIMEOUT_DEFAULT` を設定）:
- HTTPクライアント側: `LLM_TIMEOUT` または個別に `CODEX_TIMEOUT` / `CLAUDE_TIMEOUT` / `GEMINI_TIMEOUT` / `JUDGE_TIMEOUT`（デフォルト: `MAGI_TIMEOUT_DEFAULT` から継承）
- ラッパー側: `WRAPPER_TIMEOUT`（FastAPI側でCLI実行を待つ上限、デフォルト: `MAGI_TIMEOUT_DEFAULT`）

**Phase 1の改善点**:
- エラーハンドリングの型安全性向上（`LLMSuccess`/`LLMFailure`）
- pydantic-settingsによる設定管理（`.env`ファイル対応、バリデーション）
- 構造化ロギング（JSON形式、コンテキスト情報の自動付与）

HTTPラッパーのURLは環境変数で上書き可能です（デフォルト: ホストラッパーモードは `http://host.docker.internal:900{1-4}`、コンテナ化ラッパーモードは `http://<llm>-wrapper:900{1-4}`）：
- `CODEX_WRAPPER_URL`, `CLAUDE_WRAPPER_URL`, `GEMINI_WRAPPER_URL`, `JUDGE_WRAPPER_URL`

### 動作確認

ホストラッパーとブリッジが正しく動作しているか確認します（ホストラッパーモードの例。コンテナ化ラッパー利用時は `codex-wrapper:9001` などに差し替えてください）：

```bash
# 1. ホストラッパーの起動状態を確認
curl http://127.0.0.1:9001/health  # Codex
curl http://127.0.0.1:9002/health  # Claude
curl http://127.0.0.1:9003/health  # Gemini
curl http://127.0.0.1:9004/health  # Judge

# 2. MAGIシステムのヘルスチェック（ホストラッパーの状態も含む）
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
  },
  "details": {
    "codex": {
      "available": true,
      "type": "real",
      "path": "http://host.docker.internal:9001",
      "message": "wrapper available",
      "wrapper_running": true,
      "wrapper_message": "Host wrapper is running"
    },
    "claude": {
      "available": true,
      "type": "real",
      "path": "http://host.docker.internal:9002",
      "message": "wrapper available",
      "wrapper_running": true,
      "wrapper_message": "Host wrapper is running"
    },
    "gemini": {
      "available": true,
      "type": "real",
      "path": "http://host.docker.internal:9003",
      "message": "wrapper available",
      "wrapper_running": true,
      "wrapper_message": "Host wrapper is running"
    }
  }
}
```

**ホストラッパーが起動していない場合のレスポンス例:**
```json
{
  "status": "degraded",
  "commands": {
    "codex": false,
    "claude": false,
    "gemini": false
  },
  "details": {
    "codex": {
      "available": false,
      "type": "stub",
      "wrapper_running": false,
      "wrapper_message": "Host wrapper is not running at http://host.docker.internal:9001. Please start it with: bash scripts/start_host_wrappers.sh"
    }
  }
}
```

すべてのコマンドが `true` で、`wrapper_running` が `true` になっていれば、HTTPラッパーが正常に動作しています。

**注意**: 
- ホストラッパーが起動していない場合、`wrapper_running` が `false` になり、起動方法がメッセージに表示されます。
- macOS用バイナリ（claude/gemini）もホスト側で実行されるため、問題なく動作します。

## 環境構築

### クイックセットアップ

環境構築スクリプトを実行します：

```bash
bash scripts/setup_environment.sh
```

このスクリプトは以下を自動的に実行します：
1. Python仮想環境の作成（uvを使用）
2. 依存関係のインストール（requirements.txtとhost_wrappers/requirements.txt）
3. LLM CLIの確認（codex, claude, gemini, judge）
4. Docker環境の確認
5. Jupyterカーネルの設定（オプション）

### 手動セットアップ

#### 1. Python仮想環境の作成

```bash
uv venv
source .venv/bin/activate
```

#### 2. 依存関係のインストール

```bash
uv pip install -r requirements.txt
uv pip install -r host_wrappers/requirements.txt
```

#### 3. LLM CLIのインストール確認

以下のCLIがインストールされていることを確認してください：
- `codex` - Codex CLI
- `claude` - Claude CLI
- `gemini` - Gemini CLI
- `judge` - Judge CLI（オプション、CursorがJudgeとして動作する場合は不要）

環境変数でCLIコマンドをカスタマイズできます：
- `CODEX_COMMAND` (デフォルト: `codex exec --skip-git-repo-check`)
- `CLAUDE_COMMAND` (デフォルト: `claude generate`)
- `GEMINI_COMMAND` (デフォルト: `gemini generate`)
- `JUDGE_COMMAND` (デフォルト: `judge generate`)

#### 4. Docker環境の準備

Docker Desktopがインストールされていることを確認してください。

## 使い方

### ラッパーの動作モード

MAGIシステムは2つのモードで動作します：

1. **ホストラッパーモード（デフォルト）**: ホスト側でラッパーを起動し、ホストにインストール済みのCLIバイナリ（codex, claude, gemini, judge）を実行
2. **コンテナ化ラッパーモード（オプション）**: Dockerコンテナ内でラッパーを起動（CLIバイナリがコンテナ内で利用可能な場合のみ）

**デフォルトはホストラッパーモードです。** 既存のホスト前提ワークフローはそのまま動作します。コンテナ内でCLIを動かしたい場合のみ、DockerfileにCLIインストールを追加してから `USE_CONTAINER_WRAPPERS=1` を指定してください。

### ホストラッパーの起動

#### 方法1: スクリプトを使用（推奨）

```bash
bash scripts/start_host_wrappers.sh
```

このスクリプトは4つのラッパーをバックグラウンドで起動し、起動状態を確認します。

**起動確認:**
```bash
# 各ラッパーのヘルスチェック
curl http://127.0.0.1:9001/health  # Codex
curl http://127.0.0.1:9002/health  # Claude
curl http://127.0.0.1:9003/health  # Gemini
curl http://127.0.0.1:9004/health  # Judge
```

停止するには：
```bash
bash scripts/stop_host_wrappers.sh
```

#### 方法2: 手動で起動

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

#### 方法1: 自動起動スクリプトを使用（推奨）

**デフォルト（ホストラッパーモード）:**
```bash
bash scripts/start_magi.sh
```

このスクリプトは以下を自動的に実行します：
1. ホストラッパーを起動（`scripts/start_host_wrappers.sh`）
2. Dockerコンテナ（magi-mcpのみ）を起動（`docker-compose up -d --build --no-deps magi-mcp`）
3. 起動状態を確認

**コンテナ化ラッパーモード（オプション）:**
```bash
USE_CONTAINER_WRAPPERS=1 bash scripts/start_magi.sh
```

この場合、以下が実行されます：
1. コンテナ化ラッパーサービス（codex-wrapper, claude-wrapper, gemini-wrapper, judge-wrapper）を起動
2. Dockerコンテナ（全サービス）を起動
3. 起動状態を確認（`codex-wrapper:9001` などに接続）

**注意**: コンテナ化ラッパーモードでは、コンテナ内でCLIバイナリ（codex, claude, gemini, judge）が利用可能である必要があります。デフォルトのDockerfileにはCLIは同梱されていません。コンテナでCLIを動かす場合は、以下のスニペットをDockerfileに追記してCLIをインストールしてください。

**DockerfileにCLIを追加する場合の例**（`RUN pip install ...` の後に追記）:
```Dockerfile
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && npm install -g @openai/codex @anthropic-ai/claude-code @google/gemini-cli \
 && apt-get clean && rm -rf /var/lib/apt/lists/*
```

停止するには：
```bash
bash scripts/stop_magi.sh
```

#### 方法2: 手動で起動

**ホストラッパーモード（デフォルト）:**
```bash
# 1. ホストラッパーを起動
bash scripts/start_host_wrappers.sh

# 2. Dockerコンテナ（magi-mcpのみ）を起動
USE_CONTAINER_WRAPPERS=0 docker-compose up -d --build --no-deps magi-mcp
```

**コンテナ化ラッパーモード:**
```bash
# 1. 全サービス（ラッパー含む）を起動
USE_CONTAINER_WRAPPERS=1 docker-compose up -d --build
```

コンテナ内のクライアントは、モードに応じて以下のURLに接続します：
- ホストラッパーモード: `http://host.docker.internal:900{1-4}`
- コンテナ化ラッパーモード: `http://{llm}-wrapper:900{1-4}`

**起動順序:**
1. ラッパーを起動（ホストまたはコンテナ）
2. Dockerコンテナ（magi-mcp）を起動
3. CursorでMCPツールを使用

### スキーマ確認
```bash
curl http://127.0.0.1:8787/openapi.json
```

### MCP設定
**重要**: Cursorはプロジェクトルートの`mcp.json`を自動的に読み込みません。以下のいずれかの場所に設定ファイルを配置する必要があります：

1. **プロジェクトローカル**: `.cursor/mcp.json`（推奨）
2. **グローバル**: `~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp.json` (Mac)

詳細は「MCP設定方法（Cursor）」セクションを参照してください。

### 運用・トラブルシュート（LLM実行）
- 接続先: Docker内からは `host.docker.internal`、ホストから直接走らせる場合は自動で `127.0.0.1` にフォールバック。必要なら `*_WRAPPER_URL` で固定。
- 起動順: 1) ホストでラッパー起動 → 2) `docker-compose up`。ラッパー未起動ならスタブ応答になります。
- タイムアウト: デフォルトは600秒（10分）。必要に応じて `WRAPPER_TIMEOUT` と `CODEX_TIMEOUT` / `GEMINI_TIMEOUT` を調整可能。全体に効かせる場合は `LLM_TIMEOUT`。
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
  },
  "details": {
    "codex": { "available": true, "type": "real", "path": "http://host.docker.internal:9001", "message": "wrapper available" },
    "claude": { "available": true, "type": "real", "path": "http://host.docker.internal:9002", "message": "wrapper available" },
    "gemini": { "available": true, "type": "real", "path": "http://host.docker.internal:9003", "message": "wrapper available" }
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

#### 1. プロジェクトローカル設定（推奨）

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

**注意**: プロジェクトルートの`mcp.json`はCursorが自動的に読み込みません。`.cursor/mcp.json`を使用してください。

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

グローバル設定ファイル（Mac: `~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp.json`）に追加する場合も同じ形式で `tools.magi` を追加します：

**注意**: グローバル設定の場所はOSによって異なります：
- Mac: `~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp.json`
- Windows: `%APPDATA%\Cursor\User\globalStorage\cursor.mcp.json`
- Linux: `~/.config/Cursor/User/globalStorage/cursor.mcp.json`

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

#### 問題: "All connection attempts failed" エラー

このエラーは、ホストラッパーが起動していない場合に発生します。

**解決方法:**
1. ホストラッパーが起動しているか確認
   ```bash
   # プロセス確認
   ps aux | grep uvicorn | grep host_wrappers
   
   # ポート確認
   lsof -i :9001 -i :9002 -i :9003 -i :9004
   ```

2. ホストラッパーを起動
   ```bash
   bash scripts/start_host_wrappers.sh
   ```

3. 起動状態を確認
   ```bash
   # 各ラッパーのヘルスチェック
   curl http://127.0.0.1:9001/health
   curl http://127.0.0.1:9002/health
   curl http://127.0.0.1:9003/health
   curl http://127.0.0.1:9004/health
   ```

4. ログを確認（起動に失敗している場合）
   ```bash
   cat /tmp/codex_wrapper.log
   cat /tmp/claude_wrapper.log
   cat /tmp/gemini_wrapper.log
   ```

5. MAGIシステムのヘルスチェックで詳細を確認
   ```bash
   curl http://127.0.0.1:8787/health
   ```
   レスポンスの`details`フィールドに、各ホストラッパーの起動状態が表示されます。

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
- **ホストラッパーが起動しているか確認（必須）**

### Cursorチャットでの使い方

Cursorのチャット欄では、自然言語で指示を出すだけでMAGIシステムを使用できます。Cursorが自動的に適切なMCPツールを呼び出します。

#### 基本的な使い方

**例1: シンプルなリクエスト**
```
このコードをリファクタリングする提案を3つのLLMで比較して
```

**例2: 詳細な実行ログを確認したい場合**
```
MAGIシステムを使って、このリポジトリのコードをリファクタリングする提案を検討して。verboseモードで実行して、各LLMの出力を確認したい
```

**例3: 特定のLLMをスキップしたい場合**
```
Claudeをスキップして、CodexとGeminiだけで提案を比較して
```

**例4: 厳格なフォールバックポリシーで実行**
```
strictポリシーで実行して、最初のLLMが失敗したら停止して
```

#### ツールを明示的に指定する場合

Cursorが自動的にツールを選択しますが、明示的に指定することもできます：

- `@start_magi_magi_start_post` を選択して、Proposal Battleを開始
- `@health_health_get` を選択して、システムの状態を確認

### 利用可能なエンドポイント

MCPツールとして利用可能なエンドポイント：

1. **`POST /magi/start`** - Proposal Battleを開始
   - リクエスト例: `{"initial_prompt": "your prompt", "mode": "proposal_battle", "fallback_policy": "lenient|strict", "verbose": true}`
   - レスポンス例: `{"session_id": "...", "results": {...}, "logs": [...], "summary": "codex(ok) -> claude(ok) -> gemini(ok)", "timeline": ["[start] codex (...)", "[codex] ok (...)", "..."]}`
   - オプション:
     - `fallback_policy`:
       - `lenient` (デフォルト): LLM失敗時もスタブで続行し3案を揃える
       - `strict`: 最初に失敗したLLM以降は実行せず、`status: "skipped"` で返す
     - `verbose`:
       - `true` で実行経路ログ `logs`、短い `summary`、人間可読な進行表示 `timeline` を返す（CursorチャットでSequential thinking表示を再現）
       - 未指定の場合は環境変数 `MAGI_VERBOSE_DEFAULT` が `true/1/on` なら有効化（デフォルトは false）
   - 各`results.*.metadata`には`status/duration_ms/source/trace_id`など実行情報が含まれる

2. **`POST /magi/step`** - 採択案を取得
   - リクエスト: `{"session_id": "...", "decision": "codex|claude|gemini|judge"}`
   - レスポンス: `{"session_id": "...", "adopted_model": "...", "adopted_text": "..."}`

3. **`POST /magi/stop`** - セッションを停止
   - リクエスト: `{"session_id": "..."}`
   - レスポンス: `{"session_id": "...", "stopped": true}`

4. **`GET /health`** - ヘルスチェック（CLI状態を取得）
   - レスポンス: `{"status": "ok|degraded", "commands": {"codex": true, "claude": true, "gemini": true}}`

## MAGI Consensus Overview

MAGI Consensusは、3つのペルソナ（Melchior/Gemini、Balthasar/Claude、Caspar/Codex）による並列評価と投票システムです。

### モードの選択

`/magi/start`エンドポイントで`mode`パラメータを指定できます：

- `mode: "proposal_battle"` (デフォルト): 従来のProposal Battleモード（順次実行）
- `mode: "consensus"`: MAGI Consensusモード（並列評価、投票、リスク評価）

### Consensusモードの使用例

```json
{
  "initial_prompt": "このコード変更を評価してください: ...",
  "mode": "consensus",
  "criticality": "NORMAL"
}
```

### レスポンス構造

Consensusモードでは、`magi_decision`フィールドに以下の情報が含まれます：

```json
{
  "session_id": "...",
  "results": {},
  "magi_decision": {
    "decision": "APPROVED | REJECTED | CONDITIONAL",
    "risk_level": "LOW | MEDIUM | HIGH",
    "persona_results": [
      {
        "persona": "melchior",
        "vote": "YES | NO | CONDITIONAL",
        "reason": "技術的な評価理由..."
      },
      {
        "persona": "balthasar",
        "vote": "YES | NO | CONDITIONAL",
        "reason": "安全性・リスク評価..."
      },
      {
        "persona": "caspar",
        "vote": "YES | NO | CONDITIONAL",
        "reason": "実用性・速度評価..."
      }
    ],
    "aggregate_reason": "集約された判断理由",
    "suggested_actions": [
      "推奨アクション1",
      "推奨アクション2"
    ]
  }
}
```

### ペルソナの役割

- **Melchior (Gemini)**: 科学者。論理的整合性・技術的正確性・仕様との整合性を評価
- **Balthasar (Claude)**: 安全性重視。セキュリティ・安定性・保守性・リスクを評価
- **Caspar (Codex)**: 実用主義者。実用性・速度・「今動くこと」を評価

### Criticalityレベル

- `CRITICAL`: セキュリティ関連の変更など。BALTHASARがNOの場合は自動的にREJECTED
- `NORMAL`: 通常の変更（デフォルト）
- `LOW`: 低リスクの変更

### 投票の集約ロジック

- 重み付き投票: MELCHIOR=0.4, BALTHASAR=0.35, CASPAR=0.25
- YES → +1 × 重み, NO → -1 × 重み, CONDITIONAL → +0.3 × 重み
- 合計スコアとcriticalityに基づいて最終決定

## テスト

### ユニットテストと統合テスト
```bash
# すべてのテストを実行
pytest

# 統合テストのみ実行（実際のLLMとの統合を検証）
pytest -m integration

# 統合テストを除外して実行（高速）
pytest -m "not integration"
```

### テスト構成
- **ユニットテスト**: 個別コンポーネントのテスト（`tests/test_clients.py`, `tests/test_proposal_battle.py`など）
- **統合テスト**: 実際のLLMとの統合を検証（`tests/test_integration.py`）
  - Proposal Battleフロー全体のテスト
  - 型安全なエラーハンドリングのテスト
  - 後方互換性のテスト
  - セッション管理のテスト

## Phase 1の実装内容

### エラーハンドリングの型安全性向上
- `LLMSuccess`: 成功時の結果を型安全に表現
- `LLMFailure`: 失敗時の結果を型安全に表現（エラータイプ: timeout, http_error, cli_missing, exception）
- `generate_with_result()`: 新しい型安全なメソッド（後方互換性のため既存の`generate()`も保持）

### 設定管理の簡素化
- `pydantic-settings`を使用した型安全な設定管理
- `.env`ファイル対応
- タイムアウト値のバリデーション
- 環境変数の優先順位を維持（既存の動作を保持）

### 構造化ロギング
- JSON形式のログ出力
- コンテキスト情報（session_id, trace_id, model等）の自動付与
- 標準出力とファイル出力の両方に対応

詳細は `docs/PHASE1_IMPLEMENTATION.md` を参照してください。
