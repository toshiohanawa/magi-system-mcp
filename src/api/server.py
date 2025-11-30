from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel

from magi.controller import MAGIController
from magi.models import ModelOutput
from magi.logging_config import setup_logging

# Phase 1: 構造化ロギングの設定
setup_logging(level="INFO", use_json=True)

app = FastAPI(title="MAGI System MCP Server", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

controller = MAGIController()


class StartRequest(BaseModel):
    initial_prompt: str
    mode: str = "proposal_battle"
    skip_claude: bool = False
    fallback_policy: str | None = None
    verbose: bool | None = None
    criticality: str | None = None  # "CRITICAL" | "NORMAL" | "LOW"


class StartResponse(BaseModel):
    session_id: str
    results: Dict[str, Dict[str, Any]]
    logs: list[Dict[str, Any]] | None = None
    summary: str | None = None
    timeline: list[str] | None = None
    magi_decision: Dict[str, Any] | None = None  # MAGI consensus decision


class StepRequest(BaseModel):
    session_id: str
    decision: str


class StepResponse(BaseModel):
    session_id: str
    adopted_model: str
    adopted_text: str


class StopRequest(BaseModel):
    session_id: str


class StopResponse(BaseModel):
    session_id: str
    stopped: bool


class HealthResponse(BaseModel):
    status: str
    commands: Dict[str, bool]
    details: Dict[str, Dict[str, Any]]


@app.post("/magi/start", response_model=StartResponse)
async def start_magi(req: StartRequest) -> StartResponse:
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[DEBUG] start_magi called with verbose={req.verbose} (type: {type(req.verbose)})")
    try:
        result = await controller.start_magi(
            req.initial_prompt,
            mode=req.mode,
            skip_claude=req.skip_claude,
            fallback_policy=req.fallback_policy,
            verbose=req.verbose,
            criticality=req.criticality,
        )
        logger.info(f"[DEBUG] start_magi result: logs={result.get('logs')}, summary={result.get('summary')}, timeline={result.get('timeline')}")
        serialized = {k: serialize_output(v) for k, v in result.get("results", {}).items()}
        return StartResponse(
            session_id=result["session_id"],
            results=serialized,
            logs=result.get("logs"),
            summary=result.get("summary"),
            timeline=result.get("timeline"),
            magi_decision=result.get("magi_decision"),
        )
    except ValueError as e:
        # 入力検証エラーなど、ユーザーが修正可能なエラー
        logger.warning(f"Input validation error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}") from e
    except Exception as e:
        # 予期しないエラー
        logger.exception(f"Unexpected error in start_magi: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}. Please check logs for details."
        ) from e


@app.post("/magi/step", response_model=StepResponse)
async def step_magi(req: StepRequest) -> StepResponse:
    try:
        result = await controller.step_magi(req.session_id, req.decision)
        return StepResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/magi/stop", response_model=StopResponse)
async def stop_magi(req: StopRequest) -> StopResponse:
    controller.stop_magi(req.session_id)
    return StopResponse(session_id=req.session_id, stopped=True)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    import httpx
    import logging
    
    logger = logging.getLogger(__name__)
    status_dict = await controller.get_cli_status()
    
    # ホストラッパーの起動状態を詳細にチェック
    wrapper_urls = {
        "codex": "http://127.0.0.1:9001",
        "claude": "http://127.0.0.1:9002",
        "gemini": "http://127.0.0.1:9003",
    }
    
    # Dockerコンテナ内からはhost.docker.internalを使用
    import os
    if os.path.exists("/.dockerenv"):
        wrapper_urls = {
            "codex": "http://host.docker.internal:9001",
            "claude": "http://host.docker.internal:9002",
            "gemini": "http://host.docker.internal:9003",
        }
    
    # 各ホストラッパーの起動状態をチェック
    for name, url in wrapper_urls.items():
        if name in status_dict:
            status_info = status_dict[name]
            # 既存の情報に起動状態を追加
            if status_info.get("type") == "stub" or not status_info.get("available", False):
                # 直接接続を試みて起動状態を確認
                try:
                    async with httpx.AsyncClient(timeout=2.0) as client:
                        resp = await client.get(f"{url}/health")
                        if resp.status_code == 200:
                            status_dict[name]["wrapper_running"] = True
                            status_dict[name]["wrapper_message"] = "Host wrapper is running"
                        else:
                            status_dict[name]["wrapper_running"] = False
                            status_dict[name]["wrapper_message"] = f"Host wrapper returned status {resp.status_code}"
                except httpx.ConnectError:
                    status_dict[name]["wrapper_running"] = False
                    status_dict[name]["wrapper_message"] = f"Host wrapper is not running at {url}. Please start it with: bash scripts/start_host_wrappers.sh"
                except httpx.TimeoutException:
                    status_dict[name]["wrapper_running"] = False
                    status_dict[name]["wrapper_message"] = f"Host wrapper connection timeout at {url}"
                except Exception as exc:
                    status_dict[name]["wrapper_running"] = False
                    status_dict[name]["wrapper_message"] = f"Error checking host wrapper: {str(exc)}"
            else:
                status_dict[name]["wrapper_running"] = True
                status_dict[name]["wrapper_message"] = "Host wrapper is available"
    
    command_status = {
        "codex": status_dict["codex"].get("available", False) and status_dict["codex"].get("wrapper_running", False),
        "claude": status_dict["claude"].get("available", False) and status_dict["claude"].get("wrapper_running", False),
        "gemini": status_dict["gemini"].get("available", False) and status_dict["gemini"].get("wrapper_running", False),
    }
    overall = "ok" if all(command_status.values()) else "degraded"
    return HealthResponse(status=overall, commands=command_status, details=status_dict)


def serialize_output(output: ModelOutput) -> Dict[str, Any]:
    return {
        "model": output.model,
        "content": output.content,
        "metadata": output.metadata,
    }


def generate_openapi_schema() -> None:
    target_path = Path(__file__).resolve().parents[2] / "openapi.json"
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    target_path.write_text(json.dumps(schema, indent=2))


# Generate schema on import so MCP can read it without server running
try:
    app.openapi = lambda: get_openapi(title=app.title, version=app.version, routes=app.routes)
    target = Path(__file__).resolve().parents[2] / "openapi.json"
    target.write_text(  # noqa: PTH122
        json.dumps(get_openapi(title=app.title, version=app.version, routes=app.routes), indent=2)
    )
except Exception:
    # Keep import safe even if file writing fails
    pass
