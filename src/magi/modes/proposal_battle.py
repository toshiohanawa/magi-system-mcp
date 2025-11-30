from __future__ import annotations

from typing import Dict

import uuid
from datetime import datetime, timezone

from magi.clients import ClaudeClient, CodexClient, GeminiClient
from magi.models import ModelOutput
from magi import prompts


class ProposalBattleMode:
    """Sequentially executes Codex -> Claude -> Gemini. Judge is handled by Cursor."""

    def __init__(
        self,
        codex_client: CodexClient,
        claude_client: ClaudeClient,
        gemini_client: GeminiClient,
        skip_claude: bool = False,
        fallback_policy: str = "lenient",
    ) -> None:
        self.codex_client = codex_client
        self.claude_client = claude_client
        self.gemini_client = gemini_client
        self.skip_claude = skip_claude
        self.fallback_policy = fallback_policy if fallback_policy in {"strict", "lenient"} else "lenient"

    async def run(
        self,
        task: str,
        verbose: bool = False,
        return_details: bool = False,
    ) -> Dict[str, ModelOutput] | tuple[Dict[str, ModelOutput], list, str, list[str]]:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[DEBUG] proposal_battle.run called with verbose={verbose} (type: {type(verbose)})")
        logs: list[dict] = []
        timeline: list[str] = []

        def finalize(outputs: Dict[str, ModelOutput]):
            logs_out = logs if verbose else []
            timeline_out = timeline if verbose else []
            summary_out = self._build_summary(logs_out)
            if return_details:
                return outputs, logs_out, summary_out, timeline_out
            return outputs

        codex_prompt = prompts.build_codex_prompt(task)
        codex_output = await self._call_with_trace(
            self.codex_client, codex_prompt, logs, timeline, "codex", verbose
        )
        logger.info(f"[DEBUG] after codex call: logs length={len(logs)}, timeline length={len(timeline)}")

        if self._should_stop_on_failure(codex_output):
            if verbose:
                self._append_skip_log(
                    logs, timeline, "claude", "strict_policy_due_to_codex_failure", codex_output.metadata.get("trace_id")
                )
                self._append_skip_log(
                    logs, timeline, "gemini", "strict_policy_due_to_codex_failure", codex_output.metadata.get("trace_id")
                )
            outputs = {
                "codex": codex_output,
                "claude": self._skipped_output("claude", "strict_policy_due_to_codex_failure"),
                "gemini": self._skipped_output("gemini", "strict_policy_due_to_codex_failure"),
            }
            return finalize(outputs)

        if self.skip_claude:
            # Claudeをスキップして、Codexの出力を直接Geminiに渡す
            claude_output = ModelOutput(
                model="claude",
                content="[Claude skipped - using Codex output directly]",
                metadata={
                    "status": "skipped",
                    "reason": "skip_claude_flag",
                    "trace_id": str(uuid.uuid4()),
                    "skipped": True,
                },
            )
            if verbose:
                self._append_skip_log(
                    logs,
                    timeline,
                    "claude",
                    "skip_claude_flag",
                    claude_output.metadata.get("trace_id"),
                )
            # Codexの出力を直接Geminiに渡す（Claudeの評価をスキップ）
            gemini_prompt = prompts.build_gemini_prompt(codex_output.content)
        else:
            claude_prompt = prompts.build_claude_prompt(codex_output.content)
            claude_output = await self._call_with_trace(
                self.claude_client, claude_prompt, logs, timeline, "claude", verbose
            )
            if self._should_stop_on_failure(claude_output):
                if verbose:
                    self._append_skip_log(
                        logs,
                        timeline,
                        "gemini",
                        "strict_policy_due_to_claude_failure",
                        claude_output.metadata.get("trace_id"),
                    )
                outputs = {
                    "codex": codex_output,
                    "claude": claude_output,
                    "gemini": self._skipped_output("gemini", "strict_policy_due_to_claude_failure"),
                }
                return finalize(outputs)
            gemini_prompt = prompts.build_gemini_prompt(claude_output.content)

        gemini_output = await self._call_with_trace(
            self.gemini_client, gemini_prompt, logs, timeline, "gemini", verbose
        )

        # JudgeはCursorが担当するため、3案を返す
        outputs = {
            "codex": codex_output,
            "claude": claude_output,
            "gemini": gemini_output,
        }
        return finalize(outputs)

    async def _call_with_trace(
        self,
        client,
        prompt: str,
        logs: list,
        timeline: list[str],
        step: str,
        verbose: bool,
    ) -> ModelOutput:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[DEBUG] _call_with_trace called for {step} with verbose={verbose} (type: {type(verbose)})")
        trace_id = str(uuid.uuid4())
        logger.info(f"[DEBUG] verbose check (if verbose:): {verbose} -> {bool(verbose)}")
        if verbose:
            logger.info(f"[DEBUG] Adding timeline entry for {step}")
            timeline.append(f"[start] {step} (trace_id={trace_id})")
        result = await client.generate_with_result(prompt, trace_id=trace_id)
        output = result.to_model_output()
        # ensure trace_id present even if underlying metadata missing
        output.metadata.setdefault("trace_id", trace_id)
        if verbose:
            logger.info(f"[DEBUG] Adding log entry and timeline step for {step}")
            status = output.metadata.get("status", "unknown")
            reason = output.metadata.get("reason")
            self._append_log_entry(
                logs=logs,
                step=step,
                trace_id=trace_id,
                status=status,
                duration_ms=output.metadata.get("duration_ms"),
                source=output.metadata.get("source"),
                prompt=prompt,
                content=output.content,
                reason=reason,
            )
            timeline.append(self._render_timeline_step(step, status, reason, trace_id))
            logger.info(f"[DEBUG] After adding log: logs length={len(logs)}, timeline length={len(timeline)}")
        else:
            logger.info(f"[DEBUG] verbose is False, skipping log/timeline addition")
        return output

    def _should_stop_on_failure(self, output: ModelOutput) -> bool:
        if self.fallback_policy != "strict":
            return False
        return output.metadata.get("status") == "error"

    def _skipped_output(self, model: str, reason: str) -> ModelOutput:
        return ModelOutput(
            model=model,
            content=f"[{model} skipped - {reason}]",
            metadata={
                "status": "skipped",
                "reason": reason,
                "trace_id": str(uuid.uuid4()),
                "skipped": True,
            },
        )

    def _append_log_entry(
        self,
        logs: list,
        step: str,
        trace_id: str,
        status: str,
        duration_ms: int | None,
        source: str | None,
        prompt: str,
        content: str,
        reason: str | None = None,
    ) -> None:
        logs.append(
            {
                "t": datetime.now(timezone.utc).isoformat(),
                "step": step,
                "trace_id": trace_id,
                "status": status,
                "duration_ms": duration_ms,
                "source": source,
                "prompt_preview": prompt[:200],
                "content_preview": content[:200],
                "reason": reason,
            }
        )

    def _append_skip_log(
        self, logs: list, timeline: list[str], step: str, reason: str, trace_id: str | None
    ) -> None:
        trace = trace_id or str(uuid.uuid4())
        self._append_log_entry(
            logs=logs,
            step=step,
            trace_id=trace,
            status="skipped",
            duration_ms=None,
            source=None,
            prompt=reason,
            content="",
            reason=reason,
        )
        timeline.append(self._render_timeline_step(step, "skipped", reason, trace))

    def _render_timeline_step(self, step: str, status: str, reason: str | None, trace_id: str) -> str:
        suffix = f"reason={reason}" if reason else "ok"
        return f"[{step}] {status} ({suffix}, trace_id={trace_id})"

    def _build_summary(self, logs: list) -> str:
        if not logs:
            return "No verbose logs recorded."
        parts = []
        for entry in logs:
            step = entry.get("step", "?")
            status = entry.get("status", "?")
            parts.append(f"{step}({status})")
        return " -> ".join(parts)
