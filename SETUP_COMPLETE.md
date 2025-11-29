# 環境構築完了

## 実行された作業

✅ **Python仮想環境の作成**
- `.venv` ディレクトリに仮想環境を作成しました
- Python 3.12.11を使用

✅ **依存関係のインストール**
- `requirements.txt` から20パッケージをインストール
- `host_wrappers/requirements.txt` から必要なパッケージをインストール

✅ **LLM CLIの確認**
- ✅ codex: `/Users/toshiohanawa/.nvm/versions/node/v22.17.1/bin/codex`
- ✅ claude: `/Users/toshiohanawa/.nvm/versions/node/v22.17.1/bin/claude`
- ✅ gemini: `/Users/toshiohanawa/.nvm/versions/node/v22.17.1/bin/gemini`
- ⚠️  judge: 見つかりません（オプション、CursorがJudgeとして動作する場合は不要）

✅ **Docker環境の確認**
- Docker Compose v2.40.3が利用可能
- Dockerイメージのビルドが完了

✅ **セットアップスクリプトの作成**
- `setup_environment.sh`: 環境構築スクリプト
- `scripts/start_host_wrappers.sh`: ホストラッパー起動スクリプト
- `scripts/stop_host_wrappers.sh`: ホストラッパー停止スクリプト

## 次のステップ

### 1. ホストラッパーの起動

```bash
# 仮想環境をアクティベート
source .venv/bin/activate

# ホストラッパーを起動（バックグラウンド）
bash scripts/start_host_wrappers.sh
```

または、手動で起動：

```bash
uvicorn host_wrappers.codex_wrapper:app --host 127.0.0.1 --port 9001 &
uvicorn host_wrappers.claude_wrapper:app --host 127.0.0.1 --port 9002 &
uvicorn host_wrappers.gemini_wrapper:app --host 127.0.0.1 --port 9003 &
uvicorn host_wrappers.judge_wrapper:app --host 127.0.0.1 --port 9004 &
```

### 2. Dockerブリッジの起動

```bash
docker-compose up --build
```

### 3. 動作確認

```bash
# ヘルスチェック
curl http://127.0.0.1:8787/health

# OpenAPIスキーマの確認
curl http://127.0.0.1:8787/openapi.json
```

### 4. CursorのMCP設定（オプション）

```bash
bash setup_global_mcp.sh
```

その後、Cursorを再起動してください。

## トラブルシューティング

### ポートが使用中の場合

```bash
# ポートの使用状況を確認
lsof -i :9001
lsof -i :9002
lsof -i :9003
lsof -i :9004
lsof -i :8787

# 既存のプロセスを停止
bash scripts/stop_host_wrappers.sh
```

### Dockerコンテナの確認

```bash
# コンテナの状態を確認
docker compose ps

# ログを確認
docker compose logs -f

# コンテナを停止
docker compose down
```

### 仮想環境の再作成

```bash
# 仮想環境を削除
rm -rf .venv

# 再作成
bash setup_environment.sh
```

## 環境変数

必要に応じて、以下の環境変数を設定できます：

- `CODEX_COMMAND`: Codex CLIコマンド（デフォルト: `codex exec --skip-git-repo-check`）
- `CLAUDE_COMMAND`: Claude CLIコマンド（デフォルト: `claude generate`）
- `GEMINI_COMMAND`: Gemini CLIコマンド（デフォルト: `gemini generate`）
- `JUDGE_COMMAND`: Judge CLIコマンド（デフォルト: `judge generate`）
- `WRAPPER_TIMEOUT`: ラッパーのタイムアウト（デフォルト: 300秒、Phase 1で変更）
- `LLM_TIMEOUT`: LLM全体のタイムアウト（デフォルト: 300秒、Phase 1で変更）
- `CODEX_TIMEOUT`: Codex専用のタイムアウト（デフォルト: 300秒、Phase 1で変更）
- `CLAUDE_TIMEOUT`: Claude専用のタイムアウト（デフォルト: 300秒、Phase 1で変更）
- `GEMINI_TIMEOUT`: Gemini専用のタイムアウト（デフォルト: 300秒、Phase 1で変更）

**Phase 1の改善**: `.env`ファイルを使用した設定管理も可能になりました。詳細は`README.md`を参照してください。

## 参考

詳細な使用方法は `README.md` を参照してください。


