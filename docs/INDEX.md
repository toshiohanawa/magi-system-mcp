# Documentation Map

このリポジトリの主要ドキュメントと役割をまとめました。まずREADMEを読み、その後必要に応じて詳細を参照してください。

## クイックスタート
- `README.md`: セットアップ、実行方法、MCPエンドポイント、オプション（fallback_policy / verbose / timeline出力、`MAGI_VERBOSE_DEFAULT`でデフォルト可）、ヘルスチェックの例。

## セットアップ関連
- `docs/setup/CURSOR_MCP_SETUP.md`: CursorでのMCP設定手順
- `docs/setup/RESTORE_MCP_CONFIG.md`: MCP設定の復元方法
- `docs/setup/TROUBLESHOOTING_MCP.md`: MCP関連のトラブルシューティング
- `scripts/setup_environment.sh`: 環境構築スクリプト
- `scripts/setup_global_mcp.sh`: グローバルMCP設定スクリプト
- `scripts/setup_real_cli.sh`: 実CLI設定スクリプト

## ユーザーガイド
- `docs/guides/cursor_mcp_usage_guide.md`: CursorでのMCP使用方法
- `docs/guides/MCP_HTTP_PLAN.md`: MCP HTTP実装計画

## 開発者向け
- `docs/development/PHASE1_IMPLEMENTATION.md`: 型安全エラー処理、設定、構造化ロギングなどPhase 1の技術詳細
- `docs/development/ISSUES.md`: 既知の問題と暫定対策（タイムアウト、プロセス掃除など）

## アーカイブ
- `docs/archive/magi_refactoring_history.md`: 過去のリファクタリング提案のログと各LLMの出力
- `docs/archive/magi_refactoring_judge_recommendation.md`: Judgeによる統合推奨案のまとめ
- `docs/archive/folder_refactoring_proposals.md`: フォルダ構造リファクタリング提案
- その他のデバッグログ、調査結果、テスト結果など

## スクリプト
- `scripts/start_magi.sh` / `scripts/stop_magi.sh`: MAGIシステム全体の起動・停止（推奨）
- `scripts/start_host_wrappers.sh` / `scripts/stop_host_wrappers.sh`: ホストラッパー起動・停止
- `scripts/run_host.sh`: ホストラッパー実行

困ったら `README.md` → `docs/development/ISSUES.md` → `docs/setup/TROUBLESHOOTING_MCP.md` の順に確認してください。
