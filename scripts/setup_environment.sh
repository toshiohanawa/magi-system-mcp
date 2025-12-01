#!/bin/bash
# MAGI System MCP 環境構築スクリプト

set -e

echo "=== MAGI System MCP 環境構築 ==="
echo ""

# プロジェクトルートに移動
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "📁 プロジェクトルート: $PROJECT_ROOT"
echo ""

# 1. Python仮想環境の作成
echo "1️⃣  Python仮想環境の作成..."
if [ ! -d ".venv" ]; then
    echo "   uv venv を実行中..."
    uv venv
    echo "   ✅ 仮想環境を作成しました"
else
    echo "   ✅ 仮想環境は既に存在します"
fi
echo ""

# 2. 依存関係のインストール
echo "2️⃣  依存関係のインストール..."
source .venv/bin/activate

echo "   requirements.txt をインストール中..."
uv pip install -r requirements.txt

echo "   host_wrappers/requirements.txt をインストール中..."
uv pip install -r host_wrappers/requirements.txt

echo "   ✅ 依存関係のインストールが完了しました"
echo ""

# 3. LLM CLIの確認
echo "3️⃣  LLM CLIの確認..."
MISSING_CLIS=()

check_cli() {
    local cli_name=$1
    if command -v "$cli_name" > /dev/null 2>&1; then
        local cli_path=$(command -v "$cli_name")
        echo "   ✅ $cli_name: $cli_path"
        return 0
    else
        echo "   ⚠️  $cli_name: 見つかりません"
        MISSING_CLIS+=("$cli_name")
        return 1
    fi
}

check_cli "codex"
check_cli "claude"
check_cli "gemini"
check_cli "judge"

echo ""

if [ ${#MISSING_CLIS[@]} -gt 0 ]; then
    echo "⚠️  以下のCLIが見つかりませんでした:"
    for cli in "${MISSING_CLIS[@]}"; do
        echo "   - $cli"
    done
    echo ""
    echo "   これらのCLIは後でインストールするか、環境変数でパスを指定できます:"
    echo "   - CODEX_COMMAND"
    echo "   - CLAUDE_COMMAND"
    echo "   - GEMINI_COMMAND"
    echo "   - JUDGE_COMMAND"
    echo ""
    echo "   judge CLIは必須ではありません（CursorがJudgeとして動作します）"
    echo ""
fi

# 4. Docker環境の確認
echo "4️⃣  Docker環境の確認..."
if command -v docker > /dev/null 2>&1 && command -v docker-compose > /dev/null 2>&1; then
    echo "   ✅ Docker: $(docker --version)"
    echo "   ✅ Docker Compose: $(docker-compose --version)"
else
    echo "   ⚠️  DockerまたはDocker Composeが見つかりません"
    echo "   Docker Desktopをインストールしてください: https://www.docker.com/products/docker-desktop"
    exit 1
fi
echo ""

# 5. Jupyterカーネルの設定（オプション）
echo "5️⃣  Jupyterカーネルの設定..."
if command -v ipykernel > /dev/null 2>&1 || uv pip show ipykernel > /dev/null 2>&1; then
    echo "   ipykernelをインストール中..."
    uv pip install ipykernel
    echo "   Jupyterカーネルを登録中..."
    python -m ipykernel install --user --name=magi-system-mcp --display-name "Python (magi-system-mcp)"
    echo "   ✅ Jupyterカーネルを設定しました"
else
    echo "   ⚠️  ipykernelが見つかりません（スキップ）"
fi
echo ""

# 6. セットアップ完了メッセージ
echo "=== 環境構築完了 ==="
echo ""
echo "📝 次のステップ:"
echo ""
echo "1. ホストラッパーを起動（推奨方法）:"
echo "   bash scripts/start_host_wrappers.sh"
echo ""
echo "   または、手動で起動（別ターミナルで実行）:"
echo "   source .venv/bin/activate"
echo "   uvicorn host_wrappers.codex_wrapper:app --host 127.0.0.1 --port 9001 &"
echo "   uvicorn host_wrappers.claude_wrapper:app --host 127.0.0.1 --port 9002 &"
echo "   uvicorn host_wrappers.gemini_wrapper:app --host 127.0.0.1 --port 9003 &"
echo "   uvicorn host_wrappers.judge_wrapper:app --host 127.0.0.1 --port 9004 &"
echo ""
echo "2. Dockerブリッジを起動:"
echo "   docker-compose up --build"
echo ""
echo "   または、MAGIシステム全体を起動:"
echo "   bash scripts/start_magi.sh"
echo ""
echo "3. 動作確認:"
echo "   curl http://127.0.0.1:8787/health"
echo ""
echo "4. CursorのMCP設定（オプション）:"
echo "   bash scripts/setup_global_mcp.sh"
echo ""
echo "⚠️  トラブルシューティング:"
echo "   Codex/Geminiで権限エラーが発生する場合:"
echo "   - docs/setup/PERMISSION_ERROR_FIX.md を参照してください"
echo "   - ラッパーを再起動: bash scripts/stop_host_wrappers.sh && bash scripts/start_host_wrappers.sh"
echo ""
echo "✅ 環境構築が完了しました！"


