from __future__ import annotations

import asyncio
import os
import shlex
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from host_wrappers.base_wrapper import _command_available


class GenerateRequest(BaseModel):
    prompt: str


class GenerateResponse(BaseModel):
    content: str
    status: str


# Gemini CLIは位置引数でプロンプトを受け取るため、専用のラッパーを実装
app = FastAPI(title="Gemini wrapper", version="1.0.0")
command_str = os.getenv("GEMINI_COMMAND", "gemini generate")
command: List[str] = shlex.split(command_str) if command_str else ["gemini", "generate"]
timeout = float(os.getenv("WRAPPER_TIMEOUT", "120"))


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
        # Gemini CLIは位置引数でプロンプトを受け取る（one-shotモード）
        # 一部の環境で対話モードに入らないよう、位置引数と標準入力の両方にプロンプトを渡す
        
        # 作業ディレクトリを明示的に設定（Node.jsのuv_cwdエラーを防ぐため）
        cwd = os.getenv("WRAPPER_CWD", os.getcwd())
        if not os.path.exists(cwd) or not os.access(cwd, os.R_OK | os.X_OK):
            # アクセスできない場合はホームディレクトリを使用
            cwd = os.path.expanduser("~")
        
        # 環境変数を継承し、Node.jsに必要な変数を明示的に設定
        env = os.environ.copy()
        env.setdefault("HOME", os.path.expanduser("~"))
        env.setdefault("USER", os.getenv("USER", "unknown"))
        env.setdefault("PWD", cwd)
        # Node.js関連の環境変数も設定
        env.setdefault("NODE_ENV", "production")
        
        proc = await asyncio.create_subprocess_exec(
            *command,
            req.prompt,  # 位置引数としてプロンプトを渡す
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=req.prompt.encode("utf-8")),
            timeout=timeout,
        )
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=stderr.decode().strip() or "CLI failed")
        return GenerateResponse(content=stdout.decode().strip(), status="ok")
    except asyncio.TimeoutError:
        if proc is not None:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
        raise HTTPException(status_code=504, detail="CLI timeout")
    except HTTPException:
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
        raise
    except Exception as exc:  # noqa: BLE001
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=str(exc))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=9003)
