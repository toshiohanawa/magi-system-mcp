# フォルダ構成リファクタリング提案

## 実行日時
2024年12月（verboseモードで実行）

## 実行結果サマリー

### Timeline（実行タイムライン）
各LLMの実行順序とステータスを時系列で記録。

### Summary（実行サマリー）
各ステップの実行結果を簡潔にまとめたもの。

### 各LLMの提案

## Codexの提案

**目的の明確化**
- Docker内のMCPブリッジとホスト側FastAPIラッパーを分離しつつ、MAGIコア（コントローラー/モード/クライアント）を独立させ、責務境界を明確化する。
- 依存関係（コア vs ブリッジ vs ラッパー）を層ごとに切り分け、テストとドキュメントも対応する階層に整理する。
- 将来のモード追加・LLMクライアント追加を容易にし、CI/テストスイートを層ごとに回せる構造にする。

**実行可能な構造案**
```
/docs
  /architecture      # アーキ概要、フロー図、依存関係
  /operations        # セットアップ/運用手順
  /history           # 既存historyをここへ
  INDEX.md, ISSUES.md, ...（目次を更新）
/infra
  /docker            # Dockerfile, docker-compose.yml, envサンプル
  /scripts           # setup_*.sh, run_host.sh など運用系
  /config            # mcp.json, openapi.json など生成物は明示的に管理
/src
  /magi_core
    /config          # settings.py, logging_config.py, config.py
    /domain          # models.py, prompts.py
    /services        # controller.py, session_store.py
    /modes           # proposal_battle.py（追加モードもここ）
    /clients         # base_client.py, codex_client.py, claude_client.py, gemini_client.py, judge_client.py
    __init__.py
  /bridge_api        # Docker内MCPブリッジ FastAPI（現 server.py を分離）
    app.py           # create_app(), ルーター登録
    routes.py        # /magi/start /step /stop /health
    dependencies.py  # DI/設定読み込み
  /host_wrappers     # ホスト側FastAPIラッパー（現 host_wrappers をモジュール化）
    base_wrapper.py, codex_wrapper.py, ...
    settings.py      # ラッパー専用設定
    requirements.txt # 依存はコアと分離
/tests
  /unit/magi_core    # controller, modes, clients, settings など
  /unit/host_wrappers
  /integration/bridge_api
  /integration/e2e   # end-to-end（現 test_integration.py）
  conftest.py
/requirements
  base.txt           # magi_core + bridge_api
  dev.txt            # lint/testツール
  host_wrappers.txt  # ホストラッパー専用
  ci.txt             # CI用統合セット
/.gitignore          # __pycache__ など不要物を除外（現 tracked pycache を掃除）
/README.md           # ルート構造とセットアップの入口を更新
```

**手順（Step-by-step）**
1) `__pycache__` を gitignore に追加し、追跡中のものを削除（`find . -name "__pycache__" -type d -prune -exec rm -rf {} +`）。  
2) `infra/` を作成し、`Dockerfile`・`docker-compose.yml`・`setup_*.sh`・`scripts/*.sh`・`mcp.json`・`openapi.json` を `infra/docker` / `infra/scripts` / `infra/config` に移動。`README.md` と `docs/INDEX.md` で新パスを案内。  
3) `src/bridge_api/` を作成し、`src/api/server.py` を `bridge_api/app.py` に分割移動。FastAPIアプリのエントリ関数 `create_app()` を新設し、ルーター/依存を `routes.py` `dependencies.py` に切り出す。  
4) `src/magi` を `src/magi_core` にリネームし、サブフォルダ分割（config/domain/services/modes/clients）。`import` パスを一括置換（`magi.` -> `magi_core.`）。  
5) `host_wrappers/` を `src/host_wrappers/` に移動して Python パッケージ化（`__init__.py`追加）。`requirements.txt` を `requirements/host_wrappers.txt` に置き換え。  
6) 依存ファイルを分割：`requirements/base.txt`（FastAPI, httpx, pydantic 等）、`requirements/dev.txt`（pytest, any lint/format）、`requirements/host_wrappers.txt`。`requirements.txt` を `-r requirements/base.txt` などの集約ファイルに変更。  
7) テストを新階層へ再配置：単体テストは `tests/unit/...`、ブリッジAPIは `tests/integration/bridge_api`、既存E2Eは `tests/integration/e2e/test_integration.py`。`conftest.py` で `sys.path` 参照を新パスに修正。  
8) ドキュメントを整理：`docs/architecture/` にフロー図説明・依存関係、`docs/operations/` にセットアップ/トラブルシュート、`docs/history/` に既存ログ。`docs/INDEX.md` を更新し、`README.md` に簡易マップを掲載。  
9) CI/起動スクリプトを更新：`setup_environment.sh` 内のパスを `infra/` 新構造に合わせる。`docker-compose.yml` のビルドコンテキスト/パスも更新。  
10) 移動後、`python -m pytest`（unit+integration）と `uv pip compile` または `pip install -r requirements/base.txt` で依存解決確認。必要なら `openapi.json` 再生成タスクを `infra/scripts` に定義。

**必要な技術/ライブラリ**
- Python 3.12, FastAPI, httpx, pydantic-settings（既存を維持）
- pytest（既存）、uv/pip-tools（依存分割時のoptionalサポート）
- Docker / docker-compose（パス変更のみ、追加なし）
- bash（既存スクリプト修正のみ）

## Claudeの評価（評価者）レビュー

### 1. 指摘

#### 1.1 構造的弱点

**A. 過剰な抽象化リスク**
- `src/magi_core` 内の細分化（config/domain/services/modes/clients）が現状の規模に対して過剰
- 各ディレクトリに1-2ファイルしか入らない可能性が高く、ナビゲーションコストが増大
- 特に `domain/models.py` と `domain/prompts.py` を分離する明確な理由が不明

**B. 依存関係の循環リスク**
- `bridge_api` が `magi_core` に依存し、`magi_core` が設定を `bridge_api/dependencies.py` 経由で受け取る可能性
- DI層（`dependencies.py`）の責務が不明確で、設定管理が分散する恐れ

**C. テスト構造の不整合**
- `tests/unit/magi_core` と `tests/unit/host_wrappers` で単体テストを分けているが、`bridge_api` の単体テストが `integration` に配置されている
- 単体テスト vs 統合テストの境界定義が曖昧

**D. 生成物管理の矛盾**
- `openapi.json` を `infra/config` で管理するが、これは `bridge_api` のコードから生成されるべきもの
- 生成物をバージョン管理に含めるか否かの方針が不明

#### 1.2 長期保守性の問題

**A. インポートパス変更の影響範囲**
- `magi.` → `magi_core.` の一括置換は、外部統合・ドキュメント・テストに広範な影響
- 特に `host_wrappers` は現在 `magi` をインポートしているため、Docker内外で動作確認が必要

**B. requirements 分割の複雑性**
- 4分割（base/dev/host_wrappers/ci）は管理コストが高い
- `ci.txt` が他のファイルを参照する場合、依存解決の順序問題が発生する
- `host_wrappers` の独立性が本当に必要か疑問（共通依存が多い場合は無駄）

**C. 移行手順の段階性欠如**
- 10ステップすべてを一度に実行する必要があり、途中で問題が発生した場合のロールバックが困難
- 特にステップ4（`magi` → `magi_core` リネーム）とステップ3（`server.py` 分割）の同時実行は危険

#### 1.3 セキュリティ/倫理

**A. 設定ファイルの配置**
- `infra/config` に `mcp.json` を配置すると、機密情報（APIキー等）が含まれる可能性
- `.env` ファイルの管理方針が示されていない

**B. Docker内外の境界**
- `bridge_api` と `host_wrappers` の責務分離は良いが、認証・認可層の設計が欠落
- 将来の外部公開時にセキュリティレビューが必要

#### 1.4 不整合

**A. ネーミングの一貫性**
- `magi_core` はアンダースコア、`bridge_api` もアンダースコア、しかし `host_wrappers` は複数形
- `controller.py` は `services` 配下だが、`modes` と同列であるべきでは？

**B. ドキュメント構造**
- `/docs/history` に既存ログを置くが、`CHANGELOG.md` はルートに残る前提か？
- `INDEX.md` と `README.md` の役割分担が不明確

**C. スクリプト配置**
- `infra/scripts` に運用スクリプトを集約するが、開発用スクリプト（テスト実行等）の配置先が未定義

### 2. リスク評価

| カテゴリ | リスク | レベル |
|---------|--------|--------|
| **過剰な抽象化** | 小規模コードベースでディレクトリ階層が深すぎる | **Medium** |
| **一括移行の失敗** | 10ステップを一度に実行して途中で失敗 | **High** |
| **依存関係の複雑化** | requirements 4分割による管理コスト増 | **Medium** |
| **インポートパス変更** | 既存の動作している統合を破壊 | **High** |
| **テスト分類の混乱** | 単体/統合テストの境界が曖昧 | **Low** |
| **設定ファイル管理** | 機密情報の誤commit | **Medium** |
| **openapi.json 配置** | 生成物をバージョン管理に含める矛盾 | **Low** |

### 3. 改善案

#### 3.1 段階的移行戦略

**Phase 1: クリーンアップ（リスク: Low）**
```bash
# .gitignore に __pycache__ 追加
# 既存 tracked cache を削除
# CHANGELOG.md など不要削除済みファイルをコミット
```

**Phase 2: インフラ分離（リスク: Low）**
```
/infra
  /docker       # Dockerfile, docker-compose.yml
  /scripts      # setup_*.sh, run_host.sh
# mcp.json と openapi.json は別途処理
```

**Phase 3: ブリッジAPI分離（リスク: Medium）**
```
/src
  /api          # 現状維持（server.py）
  /magi         # 現状維持
  /bridge       # 新設：server.py を段階的に移動
    app.py      # create_app() のみ
```
→ 動作確認後に `/api` を削除

**Phase 4: コアモジュール整理（リスク: Medium）**
```
/src/magi
  /core         # controller, models, settings
  /modes        # proposal_battle
  /clients      # 全クライアント
  config.py, logging_config.py  # ルートに残す
```
→ `magi_core` への完全移行は保留（必要性が証明されてから）

**Phase 5: テスト整理（リスク: Low）**
```
/tests
  /unit         # magi, bridge, wrappers の単体テスト
  /integration  # E2E のみ
```

#### 3.2 依存関係管理の簡素化

```
# requirements/core.txt
fastapi>=0.104.0
uvicorn>=0.24.0
httpx>=0.25.0
pydantic>=2.5.0
pydantic-settings>=2.1.0

# requirements/dev.txt
-r core.txt
pytest>=7.4.0
pytest-asyncio>=0.21.0
ruff>=0.1.0

# requirements/host.txt  # host_wrappers が本当に独立依存を持つ場合のみ
-r core.txt
```

#### 3.3 生成物管理の明確化

```
# バージョン管理に含めない
.gitignore に追加：
  openapi.json
  __pycache__/
  .pytest_cache/

# 生成スクリプト
infra/scripts/generate_openapi.sh:
  #!/bin/bash
  python -c "from src.api.server import app; import json; ..."
```

#### 3.4 設定ファイルのセキュリティ

```
/config             # ルートに配置（infra ではなく）
  mcp.json.example  # テンプレート
  .env.example      # テンプレート
  
.gitignore:
  /config/mcp.json
  /config/.env
  .env
```

#### 3.5 ネーミング統一

- `magi_core` → `magi`（既存を維持）
- `bridge_api` → `bridge`（簡潔に）
- `host_wrappers` → `wrappers`（簡潔に）

### 4. 修正後の推奨構造

```
/
├── .gitignore              # __pycache__, .env, openapi.json を追加
├── README.md               # 簡潔なセットアップガイド
├── CHANGELOG.md            # 既存を維持
│
├── config/                 # 設定ファイル（機密情報含む）
│   ├── .env.example
│   └── mcp.json.example
│
├── docs/
│   ├── INDEX.md            # ドキュメント目次
│   ├── architecture/       # システム設計
│   │   ├── overview.md
│   │   └── dependencies.md
│   ├── operations/         # 運用手順
│   │   ├── setup.md
│   │   └── troubleshooting.md
│   └── decisions/          # ADR（Architectural Decision Records）
│       └── 001-monorepo-structure.md
│
├── infra/
│   ├── docker/
│   │   ├── Dockerfile
│   │   ├── docker-compose.yml
│   │   └── .dockerignore
│   └── scripts/
│       ├── setup_environment.sh
│       ├── run_host.sh
│       └── generate_openapi.sh
│
├── requirements/
│   ├── base.txt            # FastAPI, httpx, pydantic
│   └── dev.txt             # -r base.txt + pytest, ruff
│
├── src/
│   ├── magi/               # コアロジック（リネーム不要）
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── logging_config.py
│   │   ├── models.py
│   │   ├── controller.py
│   │   ├── modes/
│   │   │   └── proposal_battle.py
│   │   └── clients/
│   │       ├── base_client.py
│   │       ├── codex_client.py
│   │       ├── claude_client.py
│   │       ├── gemini_client.py
│   │       └── judge_client.py
│   │
│   ├── bridge/             # Docker内MCPブリッジ
│   │   ├── __init__.py
│   │   ├── app.py          # create_app()
│   │   └── routes.py
│   │
│   └── wrappers/           # ホスト側ラッパー
│       ├── __init__.py
│       ├── base.py
│       ├── codex.py
│       ├── claude.py
│       ├── gemini.py
│       └── judge.py
│
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_controller.py
    │   ├── test_clients.py
    │   ├── test_bridge.py
    │   └── test_wrappers.py
    └── integration/
        └── test_e2e.py
```

### 主要な変更点

1. **段階的移行を前提**：一度に全変更せず、Phase 1-5 で分割
2. **過剰な細分化を回避**：`magi` 配下は `modes/` と `clients/` のみサブディレクトリ化
3. **依存関係を2分割に簡素化**：`base.txt` と `dev.txt` のみ
4. **設定ファイルをルート `/config` に集約**：`.example` でテンプレート管理
5. **生成物を `.gitignore` に追加**：`openapi.json` は `infra/scripts` で再生成
6. **テストを2層に簡素化**：`unit/` と `integration/`
7. **ネーミングを簡潔化**：`bridge`, `wrappers`（アンダースコア不要）

### 実装優先順位

```
Priority 1 (即実行可能):
  - .gitignore に __pycache__, .env, openapi.json 追加
  - tracked __pycache__ を削除
  - infra/ ディレクトリ作成と移動

Priority 2 (動作確認後):
  - src/bridge/ 作成と server.py の段階的移動
  - tests/ の再編成

Priority 3 (必要性確認後):
  - requirements/ 分割
  - docs/ の詳細整備
  - ADR（Architectural Decision Records）導入
```

### 却下する提案

- `magi` → `magi_core` リネーム（破壊的変更、利益不明）
- `domain/` サブディレクトリ（過剰抽象化）
- requirements 4分割（管理コスト > 利益）
- `bridge_api/dependencies.py`（DI層の過剰設計）

---

**総評**: Codex の提案は方向性は正しいが、**規模に対して過剰な抽象化と一括移行リスクが高い**。段階的移行と簡素化を優先すべき。特に `magi` のリネームとディレクトリ細分化は現時点で不要。

## Geminiの提案（探索者）

Claudeの堅実な改善案を踏まえ、私はExploration（探索者）として、より大胆で未来志向の代替案を発散的に提案します。

### 1. 新規アプローチ：システムを進化させるための抜本的な改革案

Claudeの提案が「現状の負債を整理し、安定性を高める」アプローチであるのに対し、こちらは「将来の拡張性と開発者体験を最大化する」ためのアーキテクチャ転換を提案します。

**A. "MAGI as a Platform": プラグイン・アーキテクチャへの転換**

現状の `magi` は一体化したアプリケーションですが、これを「コアエンジン」と「プラグイン」の集合体として再設計します。

- **コアエンジン (`magi-core`)**: 思考のフレームワーク（例: `proposal_battle` の基本ロジック）、セッション管理、プラグインローダーのみに責務を限定します。極めて小さく、安定した状態を保ちます。
- **プラグイン (`magi-plugins/`)**:
    - **`clients`**: 各LLMクライアント（`gemini`, `claude`）は、独立したプラグインとなります。新しいLLMの追加は、新しいプラグインパッケージを作成するだけで完了します。
    - **`modes`**: `proposal_battle` のような思考モードもプラグイン化します。これにより、「Reflexionモード」「ToTモード」など、新しい思考アルゴリズムを容易に追加・交換できるようになります。
    - **`tools`**: ファイル操作やWeb検索などの「ツール」もプラグインとして提供し、実行時に動的に能力を獲得させます。

**B. イベント駆動による超疎結合アーキテクチャ**

コンポーネント間の直接呼び出しを廃止し、非同期的なメッセージパッシングに置き換えます。

- `bridge` はリクエストを受け取ると `RequestReceived` イベントをメッセージブローカー（例: Redis Pub/Sub, RabbitMQ）に発行します。
- `magi-core` はイベントを購読し、適切な `mode` プラグインに処理を委譲します。
- `mode` プラグインは、思考の各ステップで `InvokeLLM` イベントを発行し、`client` プラグインがこれを処理します。
- すべてのコンポーネントはログを標準出力に吐き出すのではなく、`LogEmitted` のような構造化イベントを発行します。

**C. Python開発体験の近代化：`Poetry` と `pyproject.toml` への完全移行**

`requirements.txt` による手動の依存関係管理を廃止し、`Poetry` または `PDM` を導入します。

- **単一の設定ファイル**: プロジェクトの依存関係、メタデータ、スクリプト、設定が `pyproject.toml` に集約され、見通しが格段に向上します。
- **決定的ビルド**: `poetry.lock` ファイルにより、誰がいつインストールしても全く同じ環境が再現されることを保証します。
- **ワークスペース機能**: `Poetry` の `add --editable` や `PDM` のワークスペース機能を活用し、`magi` と `wrappers` のような複数パッケージをMonorepo内でシームレスに開発できます。

### 2. 類似領域の参考知識：巨人の肩の上に立つ

**A. VSCode vs The World：拡張機能エコシステムの力**

VSCodeが成功した理由は、軽量なコアと強力な拡張機能APIにあります。本提案の「プラグイン・アーキテクチャ」はこれに倣うものです。`magi-core` はVSCode本体、`client` や `mode` プラグインはユーザーがインストールする拡張機能に相当します。これにより、コア開発チームは安定性に集中でき、コミュニティ（あるいは他の開発者）がエコシステムを拡大できます。

**B. OSカーネル：マイクロカーネル vs モノリシックカーネル**

Linuxのようなモノリシックカーネルは高性能ですが、一部の変更がシステム全体を不安定にするリスクがあります。一方、MachやQNXのようなマイクロカーネルは、最小限の機能（IPC、スケジューリング）だけをカーネルに持ち、ドライバやファイルシステムはユーザー空間のサーバーとして実行します。本提案は `magi` をマイクロカーネル化し、安定性を確保しつつ、機能を「サーバー」（プラグイン）として分離するアプローチです。

**C. Webフロントエンドの潮流：コンポーネントベースと状態管理**

ReactやVueのコンポーネントベース開発は、UIを独立した再利用可能な部品に分割します。これをバックエンドに適用し、`magi` の機能を独立したコンポーネント（プラグイン）として捉えます。また、ReduxやZustandのような状態管理ライブラリは、アプリケーション全体の状態を単一の信頼できる情報源で管理します。イベント駆動アーキテクチャは、これのバックエンド版と考えることができます。

### 3. 代替案の Pros/Cons

| アプローチ | Pros | Cons |
| :--- | :--- | :--- |
| **プラグイン・アーキテクチャ** | - **圧倒的な拡張性**: 新機能追加がコアに影響しない<br>- **疎結合**: プラグインは独立して開発・テスト可能<br>- **安定性**: コアが小さく安定するため、リグレッションが少ない | - **初期実装コスト**: プラグイン機構の設計と実装が複雑<br>- **規約の学習**: プラグイン開発者はAPI規約を学ぶ必要がある<br>- **パフォーマンス**: 動的ロードによるわずかなオーバーヘッド |
| **イベント駆動** | - **究極の疎結合**: コンポーネントは互いの存在を知る必要がない<br>- **回復力とスケーラビリティ**: 一部が停止しても全体は動き続ける<br>- **非同期処理**: 時間のかかる処理を待たずに次のタスクへ進む | - **トレーサビリティの低下**: 処理の流れを追うのが難しい<br>- **インフラ依存**: メッセージブローカーが必須になる<br>- **結果整合性**: 即時整合性が保証されにくくなる |
| **Poetry/PDMへの移行** | - **依存関係の堅牢性**: 常に再現可能な環境<br>- **優れた開発者体験**: コマンド一つで環境構築・実行が可能<br>- **設定の集約**: `pyproject.toml` ですべてを管理 | - **移行コスト**: 既存の `requirements.txt` ベースのフローを変更<br>- **学習曲線**: チームメンバーが新しいツールに慣れる必要がある |

### 4. 発散案を実用案へ変換：未来へのロードマップ

Claudeの提案する現実的なリファクタリングと、私の発散的な提案は両立可能です。以下に段階的な移行ロードマップを示します。

**Phase 1: 基盤の近代化 (Claude案 + Poetry)**

1. Claude案の「クリーンアップ」「インフラ分離」を実施します。
2. 同時に、`requirements.txt` 群を `Poetry` に移行し、`pyproject.toml` と `poetry.lock` を生成します。CI/CDも `poetry install` を使うように変更します。

**Phase 2: プラグイン化のプロトタイピング (`clients`)**

1. `src/magi/clients` を最初のプラグイン候補とします。
2. Pythonの `importlib.metadata` (entry_points) を利用して、インストールされているクライアントを動的に発見・ロードする仕組みを `MagiController` に実装します。
3. これにより、`magi` のコアコードを変更することなく、`pip install magi-client-ollama` のようなコマンドで新しいLLMクライアントを追加できる未来への道筋が立ちます。

**Phase 3: アーキテクチャの転換 (`modes` と `bridge`)**

1. `clients` のプラグイン化で得た知見を元に、`modes` も同様にプラグイン化します。
2. (オプション) `bridge` と `magi` の通信を、まずはRESTのまま疎結合にします。将来的には、パフォーマンスや型安全性が問題になれば gRPC へ、非同期性が重要になればイベント駆動へと移行を検討します。

このロードマップにより、目の前の安定性を確保しつつ、システムを硬直化させることなく、未来の拡張性を確保するアーキテクチャへと進化させることができます。

