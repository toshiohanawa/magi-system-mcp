# MAGI System MCP

ローカル専用のマルチLLMエンジン。**Proposal Battle**と**Consensus**の2つのモードをサポートし、LLM利用制限時の自動フォールバック機能を搭載しています。

## 特徴

- **2つの実行モード**
  - **Proposal Battle**: Codex → Claude → Gemini の順次実行（CursorがJudge）
  - **Consensus**: 3つのペルソナによる並列評価と投票システム
- **自動フォールバック機能**: LLMが利用制限に達した場合、他のLLMが自動的に役割を代行
- **MCPサーバー経由**: Cursorから直接利用可能
- **CLI版のみ対応**: 全LLMはCLI版のみ（HTTP API/SDK呼び出しは全面禁止）

## クイックスタート

### 1. 環境構築

```bash
bash scripts/setup_environment.sh
```

このスクリプトは以下を自動実行します：
- Python仮想環境の作成（uvを使用）
- 依存関係のインストール
- LLM CLIの確認
- Docker環境の確認

### 2. システム起動

```bash
bash scripts/start_magi.sh
```

このスクリプトは以下を自動実行します：
- ホストラッパーの起動（ポート9001-9004）
- Dockerコンテナ（magi-mcp）の起動（ポート8787）

### 3. MCP設定

#### 方法1: プロジェクトローカル設定（推奨）

プロジェクトルートに`.cursor/mcp.json`を作成：

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

#### 方法2: グローバル設定

すべてのプロジェクトでMAGIシステムを使用する場合は、グローバル設定に追加します：

**macOSの場合:**
```bash
# グローバル設定ファイルのパス
GLOBAL_MCP="$HOME/Library/Application Support/Cursor/User/globalStorage/cursor.mcp.json"

# 既存の設定がある場合はバックアップ
if [ -f "$GLOBAL_MCP" ]; then
  cp "$GLOBAL_MCP" "${GLOBAL_MCP}.bak"
fi

# magi設定を追加
cat >> "$GLOBAL_MCP" << 'EOF'
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

**Linuxの場合:**
```bash
GLOBAL_MCP="$HOME/.config/Cursor/User/globalStorage/cursor.mcp.json"
# 以下、macOSと同様の手順
```

**Windowsの場合:**
```bash
GLOBAL_MCP="$APPDATA\Cursor\User\globalStorage\cursor.mcp.json"
# 以下、macOSと同様の手順
```

> **注意**: グローバル設定ファイルが既に存在する場合は、JSON形式を維持するため、手動で編集するか、既存の設定に`magi`エントリを追加してください。

Cursorを完全に再起動して設定を反映させます。

### 4. 動作確認

```bash
# ヘルスチェック
curl http://127.0.0.1:8787/health
```

すべてのCLIが`true`で、`wrapper_running`が`true`になっていれば正常です。

## 主要機能

### Consensusモード（デフォルト）

Consensusモードは、3つのペルソナ（Melchior/Gemini、Balthasar/Claude、Caspar/Codex）が**並列**に評価を行い、重み付き投票システムで最終決定を下すモードです。コード変更の評価や意思決定に適しています。

#### 実行フロー

1. **Codex (Execution - 実装者)**
   - 役割: 実装可能性を最優先に、具体的で実行可能な提案を作成
   - 出力内容:
     - 目的の明確化
     - 実行可能な構造案
     - 手順（Step-by-step）
     - 必要な技術/ライブラリ
     - 具体的アウトプット（コード/疑似コード/スキーマなど）
   - 特徴: 曖昧な表現を避け、必要に応じてコードや疑似コードを含める

2. **Claude (Evaluation - 評価者)**
   - 役割: Codexの案を批判的にレビューし、改善点を指摘
   - 入力: Codexの出力
   - 出力内容:
     - 指摘事項
     - リスク評価（Low/Medium/High）
     - 改善案
     - 修正後の推奨構造
   - 評価観点:
     - リスク
     - 不整合
     - 長期保守性
     - セキュリティ/倫理
     - 構造的弱点

3. **Gemini (Exploration - 探索者)**
   - 役割: Claudeの改善案を踏まえて、発散的な提案を提供
   - 入力: Claudeの出力
   - 出力内容:
     - 新規アプローチ
     - 類似領域の参考知識
     - 代替案の Pros/Cons
     - 発散案を実用案へ変換
   - 特徴:
     - 代替アーキテクチャの提案
     - 類推による新しい視点
     - 外部知識の統合

4. **Cursor (Judge - 判定者)**
   - 役割: 3案を比較し、最適な案を選択
   - 判定内容:
     - 3案の要約
     - 比較表
     - 強み・弱み・リスク
     - 最も推奨できる案の選択と理由
     - 合成案の有効性評価
     - ユーザーへのアクション質問（採択・合成・再検討）

#### 使用例

```json
{
  "initial_prompt": "Pythonでリストをソートする関数を作成してください。セキュリティとパフォーマンスの両方を考慮してください。",
  "mode": "proposal_battle",
  "verbose": true,
  "fallback_policy": "lenient"
}
```

#### レスポンス構造

```json
{
  "session_id": "...",
  "results": {
    "codex": {
      "model": "codex",
      "content": "Codexの実装提案...",
      "metadata": {
        "status": "ok",
        "duration_ms": 1234,
        "trace_id": "..."
      }
    },
    "claude": {
      "model": "claude",
      "content": "Claudeの評価と改善案...",
      "metadata": {...}
    },
    "gemini": {
      "model": "gemini",
      "content": "Geminiの探索的提案...",
      "metadata": {...}
    }
  },
  "logs": [...],
  "summary": "codex(ok) -> claude(ok) -> gemini(ok)",
  "timeline": [
    "[start] codex (trace_id=...)",
    "[codex] ok (ok, trace_id=...)",
    "[start] claude (trace_id=...)",
    "[claude] ok (ok, trace_id=...)"
  ]
}
```

#### オプション

- `skip_claude`: ClaudeをスキップしてCodexとGeminiのみで実行（オプション）
- `fallback_policy`: 
  - `lenient` (デフォルト): LLM失敗時もスタブで続行し3案を揃える
  - `strict`: 最初に失敗したLLM以降は実行せず、`status: "skipped"` で返す
- `verbose`: 実行経路ログ `logs`、`summary`、`timeline` を返す（デフォルト: `true`）。`false`で無効化可能

### Proposal Battleモード

Proposal Battleモードは、3つのLLMが順次実行され、それぞれ異なる役割で提案を生成するモードです。最終的にCursorがJudgeとして3案を比較・選択します。

#### 実行フロー

1. **Codex (Execution - 実装者)**
   - 役割: 実装可能性を最優先に、具体的で実行可能な提案を作成
   - 出力内容:
     - 目的の明確化
     - 実行可能な構造案
     - 手順（Step-by-step）
     - 必要な技術/ライブラリ
     - 具体的アウトプット（コード/疑似コード/スキーマなど）
   - 特徴: 曖昧な表現を避け、必要に応じてコードや疑似コードを含める

2. **Claude (Evaluation - 評価者)**
   - 役割: Codexの案を批判的にレビューし、改善点を指摘
   - 入力: Codexの出力
   - 出力内容:
     - 指摘事項
     - リスク評価（Low/Medium/High）
     - 改善案
     - 修正後の推奨構造
   - 評価観点:
     - リスク
     - 不整合
     - 長期保守性
     - セキュリティ/倫理
     - 構造的弱点

3. **Gemini (Exploration - 探索者)**
   - 役割: Claudeの改善案を踏まえて、発散的な提案を提供
   - 入力: Claudeの出力
   - 出力内容:
     - 新規アプローチ
     - 類似領域の参考知識
     - 代替案の Pros/Cons
     - 発散案を実用案へ変換
   - 特徴:
     - 代替アーキテクチャの提案
     - 類推による新しい視点
     - 外部知識の統合

4. **Cursor (Judge - 判定者)**
   - 役割: 3案を比較し、最適な案を選択
   - 判定内容:
     - 3案の要約
     - 比較表
     - 強み・弱み・リスク
     - 最も推奨できる案の選択と理由
     - 合成案の有効性評価
     - ユーザーへのアクション質問（採択・合成・再検討）

#### 使用例

```json
{
  "initial_prompt": "Pythonでリストをソートする関数を作成してください。セキュリティとパフォーマンスの両方を考慮してください。",
  "mode": "proposal_battle",
  "verbose": true,
  "fallback_policy": "lenient"
}
```

#### レスポンス構造

```json
{
  "session_id": "...",
  "results": {
    "codex": {
      "model": "codex",
      "content": "Codexの実装提案...",
      "metadata": {
        "status": "ok",
        "duration_ms": 1234,
        "trace_id": "..."
      }
    },
    "claude": {
      "model": "claude",
      "content": "Claudeの評価と改善案...",
      "metadata": {...}
    },
    "gemini": {
      "model": "gemini",
      "content": "Geminiの探索的提案...",
      "metadata": {...}
    }
  },
  "logs": [...],
  "summary": "codex(ok) -> claude(ok) -> gemini(ok)",
  "timeline": [
    "[start] codex (trace_id=...)",
    "[codex] ok (ok, trace_id=...)",
    "[start] claude (trace_id=...)",
    "[claude] ok (ok, trace_id=...)"
  ]
}
```

#### オプション

- `skip_claude`: ClaudeをスキップしてCodexとGeminiのみで実行（オプション）
- `fallback_policy`: 
  - `lenient` (デフォルト): LLM失敗時もスタブで続行し3案を揃える
  - `strict`: 最初に失敗したLLM以降は実行せず、`status: "skipped"` で返す
- `verbose`: 実行経路ログ `logs`、`summary`、`timeline` を返す（デフォルト: `true`）。`false`で無効化可能

### Consensusモード（デフォルト）

Consensusモードは、3つのペルソナ（Melchior/Gemini、Balthasar/Claude、Caspar/Codex）が**並列**に評価を行い、重み付き投票システムで最終決定を下すモードです。コード変更の評価や意思決定に適しています。

#### 統一ペルソナテンプレート（UPT）

すべてのペルソナは、統一された厳密な出力フォーマット（Unified Persona Template, UPT）に従います：

```
VOTE: YES | NO | CONDITIONAL

REASON:
- 箇条書きで具体的理由を列挙

OPTIONAL_NOTES:
- 必要なら補足を書く（なければ空欄でよい）
```

この統一フォーマットにより、LLM出力の揺らぎに耐性のある堅牢なパースが可能です。詳細は `docs/MAGI_CONSENSUS_PROMPTS.md` を参照してください。

#### 実行フロー

1. **並列評価**
   - 3つのペルソナが同時に評価を実行（`asyncio.gather`を使用）
   - 各ペルソナは統一ペルソナテンプレート（UPT）に従った独立したプロンプトで評価
   - フォールバック機能により、利用制限に達したLLMは自動的に他のLLMに置き換え
   - カスタムペルソナプロファイル（`persona_override`）を指定可能

2. **投票の集約**
   - 各ペルソナは `YES`、`NO`、`CONDITIONAL` のいずれかを投票
   - 重み付きスコア計算:
     - `YES`: +1 × 重み
     - `NO`: -1 × 重み
     - `CONDITIONAL`: +0.3 × 重み（デフォルト）
   - 重み設定（デフォルト）:
     - Melchior (Gemini): 0.4
     - Balthasar (Claude): 0.35
     - Caspar (Codex): 0.25

3. **最終決定**
   - 合計スコアとcriticalityレベルに基づいて決定
   - 決定タイプ: `APPROVED`、`REJECTED`、`CONDITIONAL`
   - リスクレベル: `LOW`、`MEDIUM`、`HIGH`

#### ペルソナの詳細な役割

すべてのペルソナは統一ペルソナテンプレート（UPT）に従い、以下の形式で出力します：
- `VOTE`: YES | NO | CONDITIONAL
- `REASON`: 箇条書きで具体的理由を列挙
- `OPTIONAL_NOTES`: 必要なら補足（空欄可）

**Melchior (Gemini) - 科学者**
- **評価観点**: 論理的整合性・技術的正確性・仕様との整合性のみ
- **評価基準**:
  - 論理的整合性: 提案が論理的に一貫しているか
  - 技術的正確性: 技術的に正しい実装か
  - 仕様との整合性: 既存の仕様やドキュメントと整合しているか
  - 実装可能性: 技術的に実装可能か
- **評価しないもの**: 安全性、セキュリティ、実用性、時間的制約
- **重み**: 0.4（最高）

**Balthasar (Claude) - 安全性重視**
- **評価観点**: 安全性・セキュリティ・安定性・保守性・リスクを最優先
- **評価基準**:
  - セキュリティリスク: SQLインジェクション、XSS、認証・認可の問題
  - 安定性: エラーハンドリング、例外処理、エッジケース
  - 保守性: コードの可読性、テスト可能性、ドキュメント
  - リスク: 将来の技術的負債、拡張性の問題
- **評価しないもの**: 実装の速度や効率
- **重み**: 0.35
- **特別ルール**: `CRITICAL` criticalityでBALTHASARが`NO`の場合、自動的に`REJECTED`

**Caspar (Codex) - 実用主義者**
- **評価観点**: 実用性・速度・「今動くこと」・ユーザー目標の達成を最優先
- **評価基準**:
  - 実用性: 提案が実際に問題を解決するか
  - 速度: 実装が迅速か、即座に使えるか
  - 目標達成: ユーザーの目標を達成できるか
  - 実装の容易さ: シンプルで実装しやすいか
- **許容範囲**: 軽微な技術的負債やルール違反は、結果が有用であれば許容
- **重み**: 0.25

#### persona_override（カスタムペルソナプロファイル）

各ペルソナに追加の評価基準や指示を提供できます：

```json
{
  "initial_prompt": "新しい認証システムの実装",
  "mode": "consensus",
  "persona_overrides": {
    "melchior": "このプロジェクトではPython 3.11以上を必須とする",
    "balthasar": "GDPR準拠を最優先で確認すること",
    "caspar": "MVPとして2週間以内にリリース可能な範囲で評価"
  }
}
```

`persona_override`が指定されていない場合、テンプレート内では「（追加プロファイルなし）」が表示されます。

#### Criticalityレベル

- **`CRITICAL`**: セキュリティ関連の変更など
  - BALTHASARが`NO`の場合は自動的に`REJECTED`
  - より厳格な判定基準が適用される
- **`NORMAL`** (デフォルト): 通常の変更
  - 標準的な判定基準が適用される
- **`LOW`**: 低リスクの変更
  - より緩やかな判定基準が適用される

#### 使用例

```json
{
  "initial_prompt": "このコード変更を評価してください: ユーザー認証システムに新しいパスワード強度チェック機能を追加する",
  "mode": "consensus",
  "criticality": "CRITICAL",
  "verbose": true
}
```

#### レスポンス構造

```json
{
  "session_id": "...",
  "results": {},
  "magi_decision": {
    "decision": "APPROVED | REJECTED | CONDITIONAL",
    "decision_label": "Approved | Rejected | Conditional Approval",
    "risk_level": "LOW | MEDIUM | HIGH",
    "risk_label": "Low Risk | Medium Risk | High Risk",
    "persona_results": [
      {
        "persona": "melchior",
        "persona_name": "Melchior (Scientist)",
        "vote": "YES | NO | CONDITIONAL",
        "vote_label": "Approved | Rejected | Conditional Approval",
        "reason": "技術的な評価理由...",
        "optional_notes": "補足情報（オプション、nullの場合あり）"
      },
      {
        "persona": "balthasar",
        "persona_name": "Balthasar (Safety)",
        "vote": "YES | NO | CONDITIONAL",
        "vote_label": "Approved | Rejected | Conditional Approval",
        "reason": "安全性・リスク評価...",
        "optional_notes": null
      },
      {
        "persona": "caspar",
        "persona_name": "Caspar (Pragmatist)",
        "vote": "YES | NO | CONDITIONAL",
        "vote_label": "Approved | Rejected | Conditional Approval",
        "reason": "実用性・速度評価...",
        "optional_notes": "実装時の注意点など"
      }
    ],
    "aggregate_reason": "集約された判断理由",
    "suggested_actions": [
      "推奨アクション1",
      "推奨アクション2"
    ]
  },
  "logs": [...],
  "summary": "Decision: APPROVED (MEDIUM risk). 2 persona(s) approved: melchior, caspar. 1 persona(s) conditionally approved: balthasar",
  "timeline": [
    "[start] parallel evaluation (trace_id=...)",
    "[melchior] YES - 技術的に正しい実装...",
    "[balthasar] CONDITIONAL - セキュリティリスクは低いが...",
    "[caspar] YES - 実用的で迅速に実装可能..."
  ]
}
```

#### 投票の集約ロジック詳細

1. **スコア計算**
   ```
   合計スコア = Σ(各ペルソナのスコア × 重み)
   
   各ペルソナのスコア:
   - YES: +1.0
   - NO: -1.0
   - CONDITIONAL: +0.3 (デフォルト、設定可能)
   ```

2. **決定ロジック**
   - `CRITICAL` criticality:
     - BALTHASARが`NO` → 自動的に`REJECTED`
     - 合計スコア > 0.3 → `APPROVED`
     - 合計スコア < -0.3 → `REJECTED`
     - それ以外 → `CONDITIONAL`
   - `NORMAL` criticality:
     - 合計スコア > 0.2 → `APPROVED`
     - 合計スコア < -0.2 → `REJECTED`
     - それ以外 → `CONDITIONAL`
   - `LOW` criticality:
     - 合計スコア > 0.1 → `APPROVED`
     - 合計スコア < -0.1 → `REJECTED`
     - それ以外 → `CONDITIONAL`

3. **リスクレベルの導出**
   - 複数のペルソナが`NO`または`CONDITIONAL` → `HIGH`
   - 1つのペルソナが`NO`または`CONDITIONAL` → `MEDIUM`
   - すべてのペルソナが`YES` → `LOW`

#### モードの使い分け

**Proposal Battleモードが適している場合:**
- 新しい機能やシステムの設計提案が必要
- 複数のアプローチを比較検討したい
- 創造的な解決策を探索したい
- 段階的な改善（実装 → 評価 → 探索）が有効

**Consensusモードが適している場合:**
- コード変更やプルリクエストの評価
- 意思決定が必要（承認/却下/条件付き承認）
- リスク評価が重要
- 迅速な並列評価が必要

### フォールバック機能

LLMが利用制限に達した場合、他のLLMが自動的に役割を代行します。

**フォールバック優先順位:**
- Codex制限時: Claude → Gemini
- Claude制限時: Codex → Gemini
- Gemini制限時: Claude → Codex
- 2つのLLM制限時: 残り1つで3役割を独立実行

**動作例:**
- Codexが利用制限に達した場合、ClaudeがExecution役割を代行
- フォールバック情報は`fallback_info`フィールドに記録されます
- タイムラインに`[codex] fallback to claude (rate limit, ...)`が記録されます

**レスポンス例:**
```json
{
  "session_id": "...",
  "results": {
    "codex": {
      "model": "codex",
      "content": "...",
      "metadata": {
        "status": "error",
        "error_type": "http_error"
      },
      "fallback_info": {
        "original_llm": "codex",
        "fallback_llm": "claude",
        "role": "execution",
        "reason": "codex is rate limited, using claude as fallback"
      },
      "rate_limit_info": {
        "is_rate_limited": true
      }
    }
  },
  "timeline": [
    "[codex] fallback to claude (rate limit, trace_id=...)"
  ]
}
```

## システム構成

```
┌─────────────────────────────────────────────────────────┐
│                    Cursor (MCP Client)                   │
│                 (Proposal Battle の Judge)              │
└──────────────────────┬──────────────────────────────────┘
                       │
                       │ MCP Protocol (OpenAPI)
                       │ http://127.0.0.1:8787/openapi.json
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Dockerブリッジ (MCP Server)                  │
│            http://127.0.0.1:8787 (ポート8787)            │
│                                                          │
│  FastAPI Server (src/api/server.py)                     │
│  - /magi/start: Proposal Battle/Consensus開始           │
│  - /magi/step: 採択案取得                               │
│  - /magi/stop: セッション停止                           │
│  - /health: ヘルスチェック                               │
│                                                          │
│  MAGI Controller (src/magi/controller.py)              │
│  - ProposalBattleMode / ConsensusMode実行              │
│  - フォールバック機能統合                                │
└──────────────────────┬──────────────────────────────────┘
                       │
                       │ HTTP (httpx)
                       │ host.docker.internal:9001-9004
                       ▼
┌─────────────────────────────────────────────────────────┐
│              HTTPラッパー (ホスト側)                      │
│            (FastAPI, ポート9001-9004)                    │
│                                                          │
│  codex_wrapper (ポート9001)                             │
│  claude_wrapper (ポート9002)                            │
│  gemini_wrapper (ポート9003)                            │
│  judge_wrapper (ポート9004)                             │
└──────────────────────┬──────────────────────────────────┘
                       │
                       │ CLI実行
                       ▼
┌─────────────────────────────────────────────────────────┐
│                 実LLM CLI (ホスト側)                      │
│                                                          │
│  - codex exec --skip-git-repo-check                    │
│  - claude generate                                      │
│  - gemini generate                                      │
│  - judge generate                                       │
└─────────────────────────────────────────────────────────┘
```

## 詳細ドキュメント

- **セットアップ関連**: `docs/setup/` - Cursor MCP設定、トラブルシューティング
- **ユーザーガイド**: `docs/guides/` - Cursorでの使用方法
- **開発者向け**: `docs/development/` - 既知課題、実装詳細
- **Consensusモード**: `docs/MAGI_CONSENSUS_PROMPTS.md` - 統一ペルソナテンプレート（UPT）仕様、persona_override利用方法
- **アーカイブ**: `docs/archive/` - 過去のリファクタリングログ、デバッグ記録
- **ドキュメントマップ**: `docs/INDEX.md` - すべてのドキュメントへのリンク一覧

## 使い方

### Cursorチャットでの使い方

Cursorのチャット欄では、自然言語で指示を出すだけでMAGIシステムを使用できます。

**例1: シンプルなリクエスト**
```
このコードをリファクタリングする提案を3つのLLMで比較して
```

**例2: Consensusモードで評価**
```
このコード変更をConsensusモードで評価して
```

**例3: 詳細な実行ログを確認**
```
verboseモードで実行して、各LLMの出力を確認したい
```

### APIエンドポイント

#### POST /magi/start

Proposal BattleまたはConsensusを開始します。

**リクエスト例:**
```json
{
  "initial_prompt": "your prompt",
  "mode": "proposal_battle",
  "fallback_policy": "lenient",
  "verbose": true,
  "criticality": "NORMAL"
}
```

**パラメータ:**
- `initial_prompt` (必須): プロンプト
- `mode` (オプション): `"proposal_battle"` または `"consensus"` (デフォルト)
- `fallback_policy` (オプション): `"lenient"` (デフォルト) または `"strict"`
  - `lenient`: LLM失敗時もスタブで続行し3案を揃える
  - `strict`: 最初に失敗したLLM以降は実行せず、`status: "skipped"` で返す
- `verbose` (オプション): 実行経路ログ `logs`、`summary`、`timeline` を返す（デフォルト: `true`）。`false`で無効化可能
- `criticality` (オプション): Consensusモード用。`"CRITICAL"`, `"NORMAL"` (デフォルト), `"LOW"`
- `persona_overrides` (オプション): Consensusモード用。各ペルソナに追加の評価基準を指定する辞書
  - 例: `{"melchior": "Python 3.11以上を必須", "balthasar": "GDPR準拠を最優先"}`

**レスポンス例:**
```json
{
  "session_id": "...",
  "results": {
    "codex": {
      "model": "codex",
      "content": "...",
      "metadata": {
        "status": "ok",
        "duration_ms": 1234,
        "trace_id": "..."
      },
      "fallback_info": null
    },
    "claude": {...},
    "gemini": {...}
  },
  "logs": [...],
  "summary": "codex(ok) -> claude(ok) -> gemini(ok)",
  "timeline": [
    "[start] codex (trace_id=...)",
    "[codex] ok (ok, trace_id=...)",
    "[codex] fallback to claude (rate limit, trace_id=...)"
  ]
}
```

#### POST /magi/step

採択案を取得します。

**リクエスト:**
```json
{
  "session_id": "...",
  "decision": "codex|claude|gemini|judge"
}
```

#### POST /magi/stop

セッションを停止します。

**リクエスト:**
```json
{
  "session_id": "..."
}
```

#### GET /health

ヘルスチェック（CLI状態を取得）します。

**レスポンス例:**
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
      "wrapper_running": true,
      "wrapper_message": "Host wrapper is available"
    }
  }
}
```

## 環境構築

### 推奨システム環境

#### オペレーティングシステム
- **macOS**: 10.15 (Catalina) 以上（推奨: macOS 12以上）
- **Linux**: Ubuntu 20.04以上、または同等のディストリビューション
- **Windows**: Windows 10/11（WSL2推奨）

#### ハードウェア要件
- **CPU**: 2コア以上（4コア以上推奨）
- **メモリ**: 4GB以上（8GB以上推奨）
- **ディスク容量**: 2GB以上の空き容量（Dockerイメージ含む）

#### ソフトウェア要件
- **Python**: 3.11以上（3.12推奨）
- **uv**: 最新版（Pythonパッケージマネージャー）
  - インストール: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Docker Desktop**: 最新版
  - macOS/Windows: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
  - Linux: Docker Engine 20.10以上
- **LLM CLI**: 以下のCLIがインストール済みであること
  - `codex` - OpenAI Codex CLI
  - `claude` - Anthropic Claude CLI
  - `gemini` - Google Gemini CLI
  - `judge` - オプション（CursorがJudgeとして動作する場合は不要）

#### ネットワーク要件
- インターネット接続（LLM APIへのアクセス用）
- ローカルポートの利用可能性:
  - `8787`: MCPサーバー
  - `9001-9004`: ホストラッパー（Codex, Claude, Gemini, Judge）

#### その他の要件
- **Cursor**: 最新版（MCPクライアントとして使用）
- **Git**: バージョン管理用（オプション）

### 前提条件の確認

以下のコマンドで環境を確認できます：

```bash
# Pythonバージョン確認
python3 --version  # 3.11以上であることを確認

# uvの確認
uv --version

# Dockerの確認
docker --version
docker compose version

# LLM CLIの確認
codex --version
claude --version
gemini --version
```

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

#### 3. LLM CLIの確認

以下のCLIがインストールされていることを確認：
- `codex` - Codex CLI
- `claude` - Claude CLI
- `gemini` - Gemini CLI

環境変数でCLIコマンドをカスタマイズ可能：
- `CODEX_COMMAND` (デフォルト: `codex exec --skip-git-repo-check`)
- `CLAUDE_COMMAND` (デフォルト: `claude generate`)
- `GEMINI_COMMAND` (デフォルト: `gemini generate`)

## 運用

### ラッパーの起動・停止

#### 方法1: スクリプトを使用（推奨）

```bash
bash scripts/start_host_wrappers.sh
```

このスクリプトは4つのラッパーをバックグラウンドで起動し、起動状態を確認します。

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

**起動順序:**
1. ラッパーを起動（ホストまたはコンテナ）
2. Dockerコンテナ（magi-mcp）を起動
3. CursorでMCPツールを使用

### スキーマ確認
```bash
curl http://127.0.0.1:8787/openapi.json
```

### 運用時の注意事項

- **接続先**: Docker内からは `host.docker.internal`、ホストから直接走らせる場合は自動で `127.0.0.1` にフォールバック。必要なら `*_WRAPPER_URL` で固定。
- **起動順**: 1) ホストでラッパー起動 → 2) `docker-compose up`。ラッパー未起動ならスタブ応答になります。
- **タイムアウト**: デフォルトは600秒（10分）。必要に応じて `WRAPPER_TIMEOUT` と `CODEX_TIMEOUT` / `GEMINI_TIMEOUT` を調整可能。全体に効かせる場合は `LLM_TIMEOUT`。
- **504/ReadTimeout**: CLI完了待ち。タイムアウトを延長し、`ps` 等でハング確認、短いプロンプトで所要時間を計測すると切り分けやすいです。
- **スタブ応答**: `/health` が ok か、`CODEX_COMMAND` などコマンドパスが正しいか、ラッパーがリッスンしているかを確認。
- **権限エラー（Codex/Gemini）**: `Operation not permitted` や `EPERM: operation not permitted, uv_cwd` が発生する場合、最新のコードが使用されているか確認し、ラッパーを再起動してください。詳細は `docs/setup/TROUBLESHOOTING_MCP.md` の「問題5: Codex/Geminiの権限エラー」を参照。

## トラブルシューティング

### よくある問題

1. **ホストラッパーが起動していない**
   - 症状: `wrapper_running: false` が表示される、"All connection attempts failed" エラー
   - 解決方法:
     ```bash
     # プロセス確認
     ps aux | grep uvicorn | grep host_wrappers
     
     # ポート確認
     lsof -i :9001 -i :9002 -i :9003 -i :9004
     
     # ホストラッパーを起動
     bash scripts/start_host_wrappers.sh
     
     # 起動状態を確認
     curl http://127.0.0.1:9001/health
     curl http://127.0.0.1:9002/health
     curl http://127.0.0.1:9003/health
     ```

2. **Codex/Geminiの権限エラー**
   - 症状: `Operation not permitted` や `EPERM: operation not permitted, uv_cwd` が発生
   - 解決: `docs/setup/PERMISSION_ERROR_FIX.md` を参照
   - **新しい端末でのセットアップ時に重要**: 必ず `docs/setup/PERMISSION_ERROR_FIX.md` を確認してください

3. **MCPツールが表示されない**
   - 症状: CursorでMCPツールが表示されない
   - 解決方法:
     1. Dockerコンテナが起動しているか確認: `docker compose ps`
     2. MCPサーバーが応答するか確認: `curl http://127.0.0.1:8787/openapi.json`
     3. `.cursor/mcp.json`の設定が正しいか確認（コンテナ経由のURL参照 `http://127.0.0.1:8787/openapi.json` を使用）
     4. Cursorを完全に再起動
   - 詳細: `docs/setup/CURSOR_MCP_SETUP.md` を参照

4. **利用制限エラー**
   - 症状: LLMが利用制限に達している
   - 解決: フォールバック機能が自動的に動作します。`fallback_info`フィールドで確認可能
   - 動作確認: タイムラインに`[codex] fallback to claude (rate limit, ...)`が記録されます

5. **スキーマが見つからない**
   - 症状: スキーマエラーが発生
   - 解決方法:
     - `schema`がコンテナ経由のURL（`http://127.0.0.1:8787/openapi.json`）になっているか確認
     - Dockerコンテナが正常に起動しているか確認
     - `curl http://127.0.0.1:8787/openapi.json` でスキーマが取得できるか確認

6. **接続エラー**
   - 症状: 接続できない
   - 解決方法:
     - Dockerコンテナが`127.0.0.1:8787`でリッスンしているか確認
     - ファイアウォール設定を確認
     - ポート8787が他のプロセスで使用されていないか確認
     - **ホストラッパーが起動しているか確認（必須）**

### 詳細なトラブルシューティング

- **MCP関連**: `docs/setup/TROUBLESHOOTING_MCP.md`
- **権限エラー**: `docs/setup/PERMISSION_ERROR_FIX.md`（**新しい端末でのセットアップ時に必ず確認**）
- **既知の問題**: `docs/development/ISSUES.md`

**困ったら**: `README.md` → `docs/development/ISSUES.md` → `docs/setup/TROUBLESHOOTING_MCP.md` → `docs/setup/PERMISSION_ERROR_FIX.md` の順に確認してください。

## プロジェクト構成

```
magi-system-mcp/
├── src/
│   ├── api/
│   │   └── server.py          # FastAPI MCPサーバー
│   └── magi/
│       ├── clients/           # LLMクライアント実装
│       ├── modes/             # ProposalBattleMode実装
│       ├── consensus.py       # Consensus Engine
│       ├── fallback_manager.py # フォールバック管理
│       ├── rate_limit.py      # 利用制限検出
│       ├── models.py          # データモデル
│       ├── controller.py      # MAGI Controller
│       └── prompts.py         # プロンプト定義
├── host_wrappers/             # HTTPラッパー（FastAPI）
├── scripts/                    # 起動・停止スクリプト
├── docs/                       # ドキュメント
└── tests/                      # テスト
```

## テスト

```bash
# すべてのテストを実行
pytest

# 統合テストのみ実行
pytest -m integration

# 統合テストを除外して実行（高速）
pytest -m "not integration"
```

## 詳細な設定

### LLM CLI設定

全LLMはHTTPラッパー経由でCLIコマンドを実行します。デフォルトではホストラッパーを使用し、環境変数で上書き可能です（コンテナ化ラッパーを使う場合は `USE_CONTAINER_WRAPPERS=1` を指定）：

- Codex: `CODEX_COMMAND` (デフォルト: `codex exec --skip-git-repo-check`)
- Claude: `CLAUDE_COMMAND` (デフォルト: `claude generate`)
- Gemini: `GEMINI_COMMAND` (デフォルト: `gemini generate`)
- Judge: `JUDGE_COMMAND` (デフォルト: `judge generate`)

各CLIは標準入力からプロンプトを受け取り、標準出力に結果を返します。

### タイムアウト設定

デフォルトは600秒（10分）。`MAGI_TIMEOUT_DEFAULT` を基準に全コンポーネントで共有できます。

**タイムアウト調整:**
- HTTPクライアント側: `LLM_TIMEOUT` または個別に `CODEX_TIMEOUT` / `CLAUDE_TIMEOUT` / `GEMINI_TIMEOUT` / `JUDGE_TIMEOUT`（デフォルト: `MAGI_TIMEOUT_DEFAULT` から継承）
- ラッパー側: `WRAPPER_TIMEOUT`（FastAPI側でCLI実行を待つ上限、デフォルト: `MAGI_TIMEOUT_DEFAULT`）

### デフォルトモード設定

MAGIシステムのデフォルトモードを環境変数で設定できます：

- `MAGI_DEFAULT_MODE`: デフォルトモードを指定（`consensus` または `proposal_battle`）
  - デフォルト値: `consensus`
  - 例: `MAGI_DEFAULT_MODE=proposal_battle` でProposal Battleモードをデフォルトに設定

APIリクエストで `mode` パラメータを明示的に指定した場合は、その値が優先されます。

### Verboseモード設定

verboseモードはデフォルトで有効になっています。環境変数でデフォルト値を変更できます：

- `MAGI_VERBOSE_DEFAULT`: verboseモードのデフォルト値を指定（`true`、`false`、`1`、`0`、`yes`、`no`、`on`、`off`）
  - デフォルト値: `true`（verboseモードが有効）
  - 例: `MAGI_VERBOSE_DEFAULT=false` でverboseモードをデフォルトで無効化

APIリクエストで `verbose` パラメータを明示的に指定した場合は、その値が優先されます。

### ラッパーの動作モード

MAGIシステムは2つのモードで動作します：

1. **ホストラッパーモード（デフォルト）**: ホスト側でラッパーを起動し、ホストにインストール済みのCLIバイナリ（codex, claude, gemini, judge）を実行
2. **コンテナ化ラッパーモード（オプション）**: Dockerコンテナ内でラッパーを起動（CLIバイナリがコンテナ内で利用可能な場合のみ）

**デフォルトはホストラッパーモードです。** 既存のホスト前提ワークフローはそのまま動作します。コンテナ内でCLIを動かしたい場合のみ、DockerfileにCLIインストールを追加してから `USE_CONTAINER_WRAPPERS=1` を指定してください。

**コンテナ化ラッパーモードの使用:**
```bash
USE_CONTAINER_WRAPPERS=1 bash scripts/start_magi.sh
```

**DockerfileにCLIを追加する場合の例**（`RUN pip install ...` の後に追記）:
```Dockerfile
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && npm install -g @openai/codex @anthropic-ai/claude-code @google/gemini-cli \
 && apt-get clean && rm -rf /var/lib/apt/lists/*
```

### HTTPラッパーのURL設定

環境変数で上書き可能（デフォルト: ホストラッパーモードは `http://host.docker.internal:900{1-4}`、コンテナ化ラッパーモードは `http://<llm>-wrapper:900{1-4}`）：

- `CODEX_WRAPPER_URL`
- `CLAUDE_WRAPPER_URL`
- `GEMINI_WRAPPER_URL`
- `JUDGE_WRAPPER_URL`

### 動作確認

ホストラッパーとブリッジが正しく動作しているか確認します：

```bash
# 1. ホストラッパーの起動状態を確認
curl http://127.0.0.1:9001/health  # Codex
curl http://127.0.0.1:9002/health  # Claude
curl http://127.0.0.1:9003/health  # Gemini
curl http://127.0.0.1:9004/health  # Judge

# 2. MAGIシステムのヘルスチェック（ホストラッパーの状態も含む）
curl http://127.0.0.1:8787/health
```

すべてのコマンドが `true` で、`wrapper_running` が `true` になっていれば、HTTPラッパーが正常に動作しています。

**注意**: 
- ホストラッパーが起動していない場合、`wrapper_running` が `false` になり、起動方法がメッセージに表示されます。
- macOS用バイナリ（claude/gemini）もホスト側で実行されるため、問題なく動作します。

## プロジェクト構成

```
magi-system-mcp/
├── src/
│   ├── api/
│   │   └── server.py          # FastAPI MCPサーバー
│   └── magi/
│       ├── clients/           # LLMクライアント実装
│       ├── modes/             # ProposalBattleMode実装
│       ├── consensus.py       # Consensus Engine
│       ├── fallback_manager.py # フォールバック管理
│       ├── rate_limit.py      # 利用制限検出
│       ├── models.py          # データモデル
│       ├── controller.py      # MAGI Controller
│       └── prompts.py         # プロンプト定義
├── host_wrappers/             # HTTPラッパー（FastAPI）
├── scripts/                    # 起動・停止スクリプト
├── docs/                       # ドキュメント
└── tests/                      # テスト
```

## 開発者向け情報

実装の詳細、技術的な改善内容、既知の問題については、以下のドキュメントを参照してください：

- **実装詳細**: `docs/development/PHASE1_IMPLEMENTATION.md` - 型安全エラー処理、設定管理、構造化ロギングなど
- **既知の問題**: `docs/development/ISSUES.md` - タイムアウト、プロセス掃除など
