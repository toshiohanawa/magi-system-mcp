# Codex/Gemini権限エラーの解消方法

## 概要

新しい端末でセットアップする際に、CodexやGeminiのラッパーで権限エラーが発生する場合があります。このドキュメントでは、エラーの原因と解決方法を説明します。

## エラーの症状

以下のようなエラーメッセージが表示される場合：

- **Codex**: `Operation not permitted (os error 1)`
- **Gemini**: `EPERM: operation not permitted, uv_cwd`

## 原因

ホストラッパーがCLIを実行する際に、以下の設定が不足していることが原因です：

1. **作業ディレクトリ（cwd）**: プロセスが実行される際の作業ディレクトリが適切に設定されていない
2. **環境変数**: `HOME`、`PWD`、`USER`などの環境変数が適切に継承されていない
3. **Node.js環境変数**: Gemini CLI（Node.jsベース）では、`NODE_ENV`などの環境変数も必要

## 解決方法

### 方法1: 最新のコードを使用する（推奨）

この問題は既にコードで修正済みです。最新のコードを使用していることを確認してください：

```bash
# プロジェクトルートに移動
cd /path/to/magi-system-mcp

# 最新のコードを取得（Gitを使用している場合）
git pull

# 修正が含まれているか確認
grep -n "cwd=cwd" host_wrappers/base_wrapper.py
grep -n "cwd=cwd" host_wrappers/gemini_wrapper.py
```

修正が含まれている場合、以下のように表示されます：
```
45:                cwd=cwd,
46:                env=env,
```

### 方法2: ラッパーを再起動

修正が反映されていない場合は、ラッパーを再起動してください：

```bash
# 既存のラッパーを停止
bash scripts/stop_host_wrappers.sh

# ラッパーを再起動
bash scripts/start_host_wrappers.sh
```

### 方法3: 環境変数を確認

新しい端末でセットアップする際は、以下の環境変数が適切に設定されているか確認してください：

```bash
# 環境変数の確認
echo "HOME: $HOME"
echo "USER: $USER"
echo "PWD: $PWD"

# プロジェクトルートで実行しているか確認
pwd
# 出力が /path/to/magi-system-mcp であることを確認
```

## 動作確認

修正後、以下のコマンドで動作を確認してください：

```bash
# 各ラッパーのヘルスチェック
curl http://127.0.0.1:9001/health  # Codex
curl http://127.0.0.1:9003/health  # Gemini

# 実際にテスト実行（Gemini）
curl -X POST http://127.0.0.1:9003/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test"}' | python3 -m json.tool

# MAGIシステム全体のテスト
curl -X POST http://127.0.0.1:8787/magi/start \
  -H "Content-Type: application/json" \
  -d '{"initial_prompt": "test", "mode": "proposal_battle"}' | python3 -m json.tool
```

## 技術的な詳細

### 修正内容

#### 1. `host_wrappers/base_wrapper.py`

`asyncio.create_subprocess_exec`に以下のパラメータを追加：

```python
# 作業ディレクトリを明示的に設定
cwd = os.getenv("WRAPPER_CWD", os.getcwd())
if not os.path.exists(cwd) or not os.access(cwd, os.R_OK | os.X_OK):
    cwd = os.path.expanduser("~")

# 環境変数を適切に継承
env = os.environ.copy()
env.setdefault("HOME", os.path.expanduser("~"))
env.setdefault("USER", os.getenv("USER", "unknown"))
env.setdefault("PWD", cwd)

proc = await asyncio.create_subprocess_exec(
    *command,
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd=cwd,  # 追加
    env=env,   # 追加
)
```

#### 2. `host_wrappers/gemini_wrapper.py`

Node.jsベースのGemini CLI用に、追加の環境変数を設定：

```python
# 作業ディレクトリを明示的に設定
cwd = os.getenv("WRAPPER_CWD", os.getcwd())
if not os.path.exists(cwd) or not os.access(cwd, os.R_OK | os.X_OK):
    cwd = os.path.expanduser("~")

# 環境変数を適切に継承（Node.js用）
env = os.environ.copy()
env.setdefault("HOME", os.path.expanduser("~"))
env.setdefault("USER", os.getenv("USER", "unknown"))
env.setdefault("PWD", cwd)
env.setdefault("NODE_ENV", "production")  # Node.js用

proc = await asyncio.create_subprocess_exec(
    *command,
    req.prompt,
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd=cwd,  # 追加
    env=env,   # 追加
)
```

## 新しい環境でのセットアップ時のチェックリスト

新しい端末でセットアップする際は、以下の点を確認してください：

- [ ] プロジェクトルートでコマンドを実行している
- [ ] `HOME`、`USER`、`PWD`環境変数が適切に設定されている
- [ ] 最新のコードを使用している（修正が含まれている）
- [ ] ラッパーをプロジェクトルートから起動している
- [ ] 各ラッパーのヘルスチェックが正常に応答する

## 関連ドキュメント

- [トラブルシューティングガイド](TROUBLESHOOTING_MCP.md) - その他のトラブルシューティング情報
- [環境構築ガイド](../INDEX.md) - セットアップ手順の全体像

## トラブルシューティング

### 修正後もエラーが発生する場合

1. **ラッパーのログを確認**:
   ```bash
   tail -f /tmp/codex_wrapper.log
   tail -f /tmp/gemini_wrapper.log
   ```

2. **CLIの直接実行テスト**:
   ```bash
   # Codex
   echo "test" | codex exec --skip-git-repo-check
   
   # Gemini
   gemini generate "test"
   ```

3. **環境変数の確認**:
   ```bash
   env | grep -E "HOME|USER|PWD|NODE"
   ```

4. **プロセス権限の確認**:
   ```bash
   ps aux | grep -E "codex|gemini|uvicorn"
   ```

### それでも解決しない場合

GitHubのIssuesに問題を報告するか、開発チームに連絡してください。以下の情報を含めてください：

- エラーメッセージの全文
- 実行環境（OS、Pythonバージョン、Node.jsバージョン）
- 環境変数の値（機密情報を除く）
- ラッパーのログ

