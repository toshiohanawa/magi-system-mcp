#!/usr/bin/env bash
set -euo pipefail

# Host execution helper for MAGI MCP (uses host CLI binaries)
# Usage: ./scripts/run_host.sh

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT_DIR}/src"
cd "$ROOT_DIR"

exec uvicorn api.server:app --host 127.0.0.1 --port 8787
