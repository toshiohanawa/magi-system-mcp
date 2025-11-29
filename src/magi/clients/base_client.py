from __future__ import annotations

import abc
import asyncio
import httpx
import logging
import time
from typing import Optional, Dict, List

from magi.config import command_available
from magi.models import ModelOutput, LLMResult, LLMSuccess, LLMFailure


logger = logging.getLogger(__name__)


class BaseLLMClient(abc.ABC):
    def __init__(
        self,
        model_name: str,
        base_url: Optional[str] = None,
        cli_command: Optional[List[str]] = None,
        timeout: float = 120.0,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url
        self.cli_command = cli_command
        self.timeout = timeout

    @abc.abstractmethod
    def _build_url(self) -> Optional[str]:
        ...

    def _cli_path(self) -> Optional[str]:
        if self.cli_command:
            return " ".join(self.cli_command)
        return None

    async def generate(self, prompt: str) -> ModelOutput:
        """後方互換性のための既存メソッド（段階的移行のため保持）"""
        result = await self.generate_with_result(prompt)
        if isinstance(result, LLMSuccess):
            return result.to_model_output()
        else:
            return result.to_model_output()

    async def generate_with_result(self, prompt: str, trace_id: Optional[str] = None) -> LLMResult:
        """
        Phase 1: 型安全なLLM呼び出しメソッド
        
        Returns:
            LLMSuccess: 成功時
            LLMFailure: 失敗時
        """
        start_time = time.perf_counter()
        url = self._build_url()
        source = url or self._cli_path() or "unknown"
        
        if not url:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return LLMFailure(
                model=self.model_name,
                error_type="cli_missing",
                error_message="wrapper url not configured",
                duration_ms=duration_ms,
                source=source,
                fallback_content=f"Stub response for {self.model_name}: {prompt[:200]}",
            )
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{url}/generate", json={"prompt": prompt})
                resp.raise_for_status()
                data = resp.json()
                content = data.get("content") or data
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                metadata = {
                    "status": data.get("status", "ok"),
                    "cli_type": "real",
                }
                
                return LLMSuccess(
                    model=self.model_name,
                    content=content,
                    duration_ms=duration_ms,
                    source=url,
                    metadata=metadata,
                )
        except httpx.TimeoutException as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            detail = str(exc)
            logger.error(
                "Timeout from %s wrapper at %s: %s",
                self.model_name,
                url,
                detail,
            )
            return LLMFailure(
                model=self.model_name,
                error_type="timeout",
                error_message=f"Request timeout after {self.timeout}s: {detail}",
                duration_ms=duration_ms,
                source=url,
                fallback_content=f"Stub response for {self.model_name} (timeout): {prompt[:200]}",
            )
        except httpx.HTTPStatusError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            detail = exc.response.text if exc.response else ""
            logger.error(
                "HTTP error from %s wrapper at %s: %s %s",
                self.model_name,
                url,
                exc,
                detail.strip()[:500],
            )
            error_msg = f"HTTP {exc.response.status_code if exc.response else 'error'}: {detail.strip() or exc}"
            return LLMFailure(
                model=self.model_name,
                error_type="http_error",
                error_message=error_msg,
                duration_ms=duration_ms,
                source=url,
                fallback_content=f"Stub response for {self.model_name} ({error_msg}): {prompt[:200]}",
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.exception("Failed to call %s wrapper at %s", self.model_name, url)
            return LLMFailure(
                model=self.model_name,
                error_type="exception",
                error_message=str(exc),
                duration_ms=duration_ms,
                source=url,
                fallback_content=f"Stub response for {self.model_name} (exception): {prompt[:200]}",
            )

    async def aget_cli_status(self) -> Dict[str, str]:
        """Async wrapper for get_cli_status to keep controller interfaces unchanged."""
        return await asyncio.to_thread(self.get_cli_status)

    def get_cli_status(self) -> Dict[str, str]:
        """
        HTTPラッパーの状態を取得する

        Returns:
            CLIの状態情報を含む辞書
        """
        url = self._build_url()
        cli_path = self._cli_path() or url

        if command_available(self.cli_command):
            return {
                "available": True,
                "type": "real",
                "path": cli_path,
                "message": "CLI command detected",
            }

        if url:
            try:
                with httpx.Client(timeout=3.0) as client:
                    resp = client.get(f"{url}/health")
                    resp.raise_for_status()
                    data = resp.json()
                    if data.get("status") == "ok":
                        return {
                            "available": True,
                            "type": "real",
                            "path": url,
                            "message": "wrapper available",
                        }
            except Exception:
                # Ignore errors and fall back to stub status
                pass

        return {
            "available": True,
            "type": "stub",
            "path": cli_path,
            "message": "using stub response",
        }

    async def _stubbed_output(
        self,
        prompt: str,
        note: Optional[str] = None,
        cli_path: Optional[str] = None,
        cli_type: str = "stub",
    ) -> ModelOutput:
        suffix = f" ({note})" if note else ""
        preview = prompt[:200]
        metadata = {
            "cli_type": cli_type,
            "cli_path": cli_path,
        }
        if note:
            metadata["note"] = note
            metadata["error"] = note
        return ModelOutput(
            model=self.model_name,
            content=f"Stub response for {self.model_name}{suffix}: {preview}",
            metadata=metadata,
        )
