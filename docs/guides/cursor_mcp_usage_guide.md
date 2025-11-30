# Cursor MCPツール使用ガイド

## `/magi/start` エンドポイントの使い方

### Cursorチャットでの使用方法

Cursorのチャットで、以下のように入力します：

```
@start_magi_magi_start_post
```

または、`@`を押してツール一覧から`start_magi_magi_start_post`を選択します。

### リクエストパラメータ

ツールを選択すると、以下のパラメータを入力できます：

1. **`initial_prompt`** (必須)
   - 型: `string`
   - 説明: MAGIシステムに渡す初期プロンプト
   - 例: "このリポジトリのフォルダ構成をリファクタリングする提案を検討してください"

2. **`mode`** (オプション)
   - 型: `string`
   - デフォルト: `"proposal_battle"`
   - 説明: 実行モード（現在は`proposal_battle`のみサポート）

3. **`skip_claude`** (オプション)
   - 型: `boolean`
   - デフォルト: `false`
   - 説明: Claudeをスキップして、Codexの出力を直接Geminiに渡す

4. **`fallback_policy`** (オプション)
   - 型: `string`
   - デフォルト: `"lenient"`
   - 説明: LLM失敗時のフォールバックポリシー
   - 値: `"lenient"` または `"strict"`
   - `lenient`: LLM失敗時もスタブで続行し3案を揃える
   - `strict`: 最初に失敗したLLM以降は実行せず、`status: "skipped"`で返す

5. **`verbose`** (オプション)
   - 型: `boolean`
   - デフォルト: `false`（環境変数`MAGI_VERBOSE_DEFAULT`で変更可能）
   - 説明: 詳細な実行ログを返すかどうか
   - `true`の場合: `logs`、`summary`、`timeline`が返される
   - `false`の場合: `logs`、`summary`、`timeline`は`null`

### レスポンス

#### 基本レスポンス（`verbose: false`の場合）

```json
{
  "session_id": "uuid",
  "results": {
    "codex": {
      "model": "codex",
      "content": "...",
      "metadata": {
        "status": "ok",
        "cli_type": "real",
        "cli_path": "http://host.docker.internal:9001",
        "trace_id": "uuid"
      }
    },
    "claude": {...},
    "gemini": {...}
  },
  "logs": null,
  "summary": null,
  "timeline": null
}
```

#### Verboseレスポンス（`verbose: true`の場合）

```json
{
  "session_id": "uuid",
  "results": {
    "codex": {...},
    "claude": {...},
    "gemini": {...}
  },
  "logs": [
    {
      "t": "2025-11-29T19:03:44.008232+00:00",
      "step": "codex",
      "trace_id": "uuid",
      "status": "ok",
      "duration_ms": "61928.90902900399",
      "source": "http://host.docker.internal:9001",
      "prompt_preview": "...",
      "content_preview": "...",
      "reason": null
    },
    {
      "t": "2025-11-29T19:03:46.425352+00:00",
      "step": "claude",
      "trace_id": "uuid",
      "status": "error",
      "duration_ms": "2417.1108349983115",
      "source": "http://host.docker.internal:9002",
      "prompt_preview": "...",
      "content_preview": "...",
      "reason": null
    },
    {
      "t": "2025-11-29T19:04:27.654123+00:00",
      "step": "gemini",
      "trace_id": "uuid",
      "status": "ok",
      "duration_ms": "41228.72085299605",
      "source": "http://host.docker.internal:9003",
      "prompt_preview": "...",
      "content_preview": "...",
      "reason": null
    }
  ],
  "summary": "codex(ok) -> claude(error) -> gemini(ok)",
  "timeline": [
    "[start] codex (trace_id=uuid)",
    "[codex] ok (ok, trace_id=uuid)",
    "[start] claude (trace_id=uuid)",
    "[claude] error (ok, trace_id=uuid)",
    "[start] gemini (trace_id=uuid)",
    "[gemini] ok (ok, trace_id=uuid)"
  ]
}
```

### 使用例

#### 例1: 基本的な使用（verbose無効）

```
@start_magi_magi_start_post

initial_prompt: "このリポジトリのフォルダ構成をリファクタリングする提案を検討してください"
```

#### 例2: Verboseモードで実行

```
@start_magi_magi_start_post

initial_prompt: "このリポジトリのフォルダ構成をリファクタリングする提案を検討してください"
verbose: true
```

#### 例3: Strictポリシーで実行

```
@start_magi_magi_start_post

initial_prompt: "テストプロンプト"
fallback_policy: "strict"
verbose: true
```

#### 例4: Claudeをスキップ

```
@start_magi_magi_start_post

initial_prompt: "テストプロンプト"
skip_claude: true
verbose: true
```

### Verbose情報の確認方法

#### 1. Cursorチャットでの確認

Cursorのチャットで`@start_magi_magi_start_post`を使用し、`verbose: true`を指定すると、レスポンスに`logs`、`summary`、`timeline`が含まれます。

ただし、CursorのUIがこれらのフィールドをどのように表示するかは、Cursorの実装に依存します。

#### 2. 直接API呼び出しでの確認

```bash
curl -X POST http://127.0.0.1:8787/magi/start \
  -H "Content-Type: application/json" \
  -d '{
    "initial_prompt": "テスト",
    "verbose": true
  }' | jq '.logs, .summary, .timeline'
```

#### 3. レスポンス全体の確認

```bash
curl -X POST http://127.0.0.1:8787/magi/start \
  -H "Content-Type: application/json" \
  -d '{
    "initial_prompt": "テスト",
    "verbose": true
  }' > response.json

cat response.json | jq '.logs | length'  # logsの件数
cat response.json | jq '.summary'        # summary
cat response.json | jq '.timeline'       # timeline
```

### Verbose情報の内容

#### `logs`
各LLM呼び出しの詳細ログ：
- `t`: タイムスタンプ（ISO 8601形式）
- `step`: ステップ名（`codex`、`claude`、`gemini`）
- `trace_id`: トレースID（各呼び出しを追跡可能）
- `status`: ステータス（`ok`、`error`、`skipped`）
- `duration_ms`: 実行時間（ミリ秒）
- `source`: 呼び出し元（URLまたはCLIコマンド）
- `prompt_preview`: プロンプトのプレビュー（最初の200文字）
- `content_preview`: コンテンツのプレビュー（最初の200文字）
- `reason`: スキップ理由（スキップされた場合）

#### `summary`
実行サマリー（文字列）：
- 形式: `codex(status) -> claude(status) -> gemini(status)`
- 例: `"codex(ok) -> claude(error) -> gemini(ok)"`

#### `timeline`
人間可読な進行表示（文字列の配列）：
- 各ステップの開始と完了を時系列で表示
- 形式: `"[step] status (reason, trace_id=uuid)"`
- 例: `"[start] codex (trace_id=uuid)"`, `"[codex] ok (ok, trace_id=uuid)"`

### トラブルシューティング

#### Verbose情報が表示されない場合

1. **リクエストで`verbose: true`を指定しているか確認**
   - CursorのMCPツールで`verbose`フィールドに`true`を入力

2. **環境変数`MAGI_VERBOSE_DEFAULT`を確認**
   - `MAGI_VERBOSE_DEFAULT=true`に設定すると、`verbose`を省略しても有効になる

3. **直接API呼び出しで確認**
   - `curl`コマンドで直接APIを呼び出し、レスポンスを確認

4. **サーバーログを確認**
   - `docker compose logs magi-mcp`でデバッグログを確認

5. **CursorのMCPツールの制限を確認**
   - Cursorが`Optional`フィールドを表示しない可能性
   - レスポンスサイズが大きすぎて省略されている可能性

### 注意事項

- `verbose: true`を指定すると、レスポンスサイズが大きくなります
- `logs`配列には各LLM呼び出しの詳細情報が含まれます
- `timeline`は人間可読な形式で、CursorチャットでSequential thinking風に表示できます
- `summary`は簡潔な実行サマリーです




