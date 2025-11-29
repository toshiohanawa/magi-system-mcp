# 変更履歴

## Phase 1 (2025年1月)

### 追加機能

#### エラーハンドリングの型安全性向上
- `LLMSuccess`クラス: 成功時の結果を型安全に表現
- `LLMFailure`クラス: 失敗時の結果を型安全に表現
  - エラータイプ: `timeout`, `http_error`, `cli_missing`, `exception`
  - 実行時間の自動計測（`duration_ms`）
  - フォールバックコンテンツの明示的な管理
- `generate_with_result()`メソッド: 新しい型安全なメソッドを追加
- 後方互換性: 既存の`generate()`メソッドも引き続き動作

#### 設定管理の簡素化
- `pydantic-settings`を使用した型安全な設定管理
- `.env`ファイル対応
- タイムアウト値のバリデーション（正の値、10分超の場合は警告）
- 環境変数の優先順位を維持（既存の動作を保持）

#### 構造化ロギング
- JSON形式のログ出力
- コンテキスト情報（session_id, trace_id, model等）の自動付与
- 標準出力とファイル出力の両方に対応
- `ContextLoggerAdapter`によるコンテキスト情報の追加

#### 統合テスト
- 6つの統合テストを追加
  - Proposal Battleフロー全体のテスト
  - Claudeスキップ時のテスト
  - 型安全なエラーハンドリングのテスト
  - 後方互換性のテスト
  - step_magiエンドポイントのテスト
  - セッション管理のテスト

### 変更点

#### タイムアウト設定
- デフォルトタイムアウトを120秒から300秒（5分）に変更
- `docker-compose.yml`に環境変数を追加
- `src/magi/config.py`のデフォルト値を300秒に変更
- `src/magi/settings.py`でデフォルト300秒を設定

#### 依存関係
- `pydantic-settings==2.1.0`を追加
- `python-dotenv==1.2.1`が自動的に追加（pydantic-settingsの依存関係）

### 改善点

#### エラーハンドリング
- エラーの種類を型レベルで区別可能に
- 実行時間の計測が自動化
- エラー発生時のフォールバックコンテンツを明示的に管理
- 構造化ログによるデバッグの容易化

#### 設定管理
- 型安全性とバリデーションの向上
- `.env`ファイルによる設定管理が容易に
- 設定値の検証が自動化

#### ロギング
- ログの構造化により、ログ分析ツールとの連携が容易に
- コンテキスト情報の自動付与
- デバッグ時の追跡が容易に

### 後方互換性

すべての変更は後方互換性を維持しています：
- 既存の`generate()`メソッドは引き続き動作
- 既存の`AppConfig.from_env()`は引き続き動作（内部で新しい設定システムを使用）
- 既存のテストはすべて通過

### ファイル変更

#### 新規ファイル
- `src/magi/settings.py`: pydantic-settingsベースの設定管理
- `src/magi/logging_config.py`: 構造化ロギングシステム
- `tests/test_integration.py`: 統合テスト
- `PHASE1_IMPLEMENTATION.md`: Phase 1の実装レポート
- `CHANGELOG.md`: このファイル

#### 更新ファイル
- `requirements.txt`: pydantic-settingsを追加
- `src/magi/models.py`: LLMSuccess/LLMFailureクラスを追加
- `src/magi/clients/base_client.py`: generate_with_result()メソッドを追加
- `src/magi/config.py`: AppConfig.from_env()を更新
- `src/api/server.py`: ロギング設定を初期化
- `tests/conftest.py`: カスタムマーカーを追加
- `README.md`: Phase 1の実装内容を追加
- `ISSUES.md`: Phase 1での改善を反映

### テスト結果

- 既存テスト: 16個すべて通過 ✅
- 統合テスト: 6個すべて通過 ✅
- リンターエラー: なし ✅

## 以前のバージョン

### 初期バージョン
- Proposal Battle型マルチLLMエンジンの実装
- Dockerブリッジとホスト側HTTPラッパーの実装
- MCPサーバーとしての動作
- 基本的なエラーハンドリングとスタブ応答

