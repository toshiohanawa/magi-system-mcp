from __future__ import annotations

import abc
import asyncio
import httpx
import logging
from typing import Optional, Dict, List

from magi.config import command_available
from magi.models import ModelOutput


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
        url = self._build_url()
        if not url:
            return await self._stubbed_output(prompt, note="wrapper url not configured", cli_path=self._cli_path())
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{url}/generate", json={"prompt": prompt})
                resp.raise_for_status()
                data = resp.json()
                content = data.get("content") or data
                metadata = {
                    "status": data.get("status", "ok"),
                    "cli_type": "real",
                    "cli_path": url,
                }
                return ModelOutput(model=self.model_name, content=content, metadata=metadata)
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text if exc.response else ""
            logger.error(
                "HTTP error from %s wrapper at %s: %s %s",
                self.model_name,
                url,
                exc,
                detail.strip()[:500],
            )
            note = f"HTTP {exc.response.status_code if exc.response else 'error'}: {detail.strip() or exc}"
            return await self._stubbed_output(prompt, note=note, cli_path=url, cli_type="real")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to call %s wrapper at %s", self.model_name, url)
            return await self._stubbed_output(prompt, note=str(exc), cli_path=url, cli_type="real")

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
