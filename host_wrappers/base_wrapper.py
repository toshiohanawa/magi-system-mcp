from __future__ import annotations

import asyncio
import os
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


class GenerateRequest(BaseModel):
    prompt: str


class GenerateResponse(BaseModel):
    content: str
    status: str


def create_wrapper_app(command_env: str, default_cmd: str) -> FastAPI:
    import shlex
    command_str = os.getenv(command_env, default_cmd)
    command: List[str] = shlex.split(command_str)
    timeout = float(
        os.getenv(
            "WRAPPER_TIMEOUT",
            os.getenv("LLM_TIMEOUT", os.getenv("MAGI_TIMEOUT_DEFAULT", "300")),
        )
    )

    app = FastAPI(title=f"{command_env} wrapper", version="1.0.0")

    @app.get("/health")
    async def health() -> dict:
        exists = await _command_available(command)
        return {"status": "ok" if exists else "missing", "command": command}

    @app.post("/generate", response_model=GenerateResponse)
    async def generate(req: GenerateRequest) -> GenerateResponse:
        exists = await _command_available(command)
        if not exists:
            raise HTTPException(status_code=500, detail="CLI missing")
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=req.prompt.encode("utf-8")), timeout=timeout
            )
            if proc.returncode != 0:
                raise HTTPException(status_code=500, detail=stderr.decode().strip() or "CLI failed")
            return GenerateResponse(content=stdout.decode().strip(), status="ok")
        except asyncio.TimeoutError:
            # タイムアウト時はプロセスを確実に終了させる
            if proc is not None:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            raise HTTPException(status_code=504, detail="CLI timeout")
        except HTTPException:
            # HTTPException発生時もプロセスをクリーンアップ
            if proc is not None and proc.returncode is None:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            raise
        except Exception as exc:  # noqa: BLE001
            # その他の例外時もプロセスをクリーンアップ
            if proc is not None and proc.returncode is None:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            raise HTTPException(status_code=500, detail=str(exc))

    return app


async def _command_available(command: List[str]) -> bool:
    if not command:
        return False
    program = command[0]
    return os.path.isabs(program) and os.path.exists(program) or await _which(program)


async def _which(program: str) -> bool:
    proc = await asyncio.create_subprocess_exec(
        "which",
        program,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return bool(stdout.strip())
