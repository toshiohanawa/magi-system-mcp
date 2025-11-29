from __future__ import annotations

from magi.clients.base_client import BaseLLMClient
from magi.config import LLMConfig


class CodexClient(BaseLLMClient):
    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig.for_codex()
        super().__init__(
            model_name="codex",
            base_url=self.config.base_url,
            cli_command=self.config.cli_command,
            timeout=self.config.timeout,
        )

    def _build_url(self) -> str | None:
        return self.config.base_url
