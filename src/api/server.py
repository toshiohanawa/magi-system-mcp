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


class StartResponse(BaseModel):
    session_id: str
    results: Dict[str, Dict[str, Any]]


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


@app.post("/magi/start", response_model=StartResponse)
async def start_magi(req: StartRequest) -> StartResponse:
    result = await controller.start_magi(req.initial_prompt, mode=req.mode, skip_claude=req.skip_claude)
    serialized = {k: serialize_output(v) for k, v in result["results"].items()}
    return StartResponse(session_id=result["session_id"], results=serialized)


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
    status_dict = await controller.get_cli_status()
    command_status = {
        "codex": status_dict["codex"].get("available", False),
        "claude": status_dict["claude"].get("available", False),
        "gemini": status_dict["gemini"].get("available", False),
    }
    overall = "ok" if all(command_status.values()) else "degraded"
    return HealthResponse(status=overall, commands=command_status)


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
