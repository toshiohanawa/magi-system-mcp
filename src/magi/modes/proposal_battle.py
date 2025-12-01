from __future__ import annotations

from typing import Dict, Optional, Tuple

import uuid
from datetime import datetime, timezone

from magi.clients import ClaudeClient, CodexClient, GeminiClient
from magi.clients.base_client import BaseLLMClient
from magi.models import ModelOutput, LLMFailure
from magi import prompts
from magi.fallback_manager import FallbackManager, Role, LLMName
from magi.rate_limit import check_rate_limit


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
        self.fallback_manager = FallbackManager(codex_client, claude_client, gemini_client)

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

        # フォールバックマネージャーをリセット
        self.fallback_manager.reset()

        # 2つのLLMが利用制限に達している場合、1つのLLMで3役割を独立実行
        # このチェックは事前に実行（既に制限されていることが分かっている場合）
        # 実際の実行中に制限が検出された場合は、_call_with_fallback内で処理される

        # Execution役割（Codex）の実行
        codex_prompt = prompts.build_codex_prompt(task)
        codex_output, codex_fallback_info = await self._call_with_fallback(
            self.codex_client,
            codex_prompt,
            logs,
            timeline,
            "codex",
            Role.EXECUTION,
            task,
            verbose,
        )
        logger.info(f"[DEBUG] after codex call: logs length={len(logs)}, timeline length={len(timeline)}")

        # 利用制限をチェック
        if codex_output.metadata.get("status") == "error":
            error_msg = codex_output.metadata.get("error", "")
            rate_limit_info = self.fallback_manager.check_rate_limit(error_msg, LLMName.CODEX)
            if rate_limit_info.is_rate_limited:
                self.fallback_manager.mark_rate_limited(LLMName.CODEX)
                if codex_fallback_info:
                    codex_output.fallback_info = {
                        "original_llm": codex_fallback_info.original_llm,
                        "fallback_llm": codex_fallback_info.fallback_llm,
                        "role": codex_fallback_info.role,
                        "reason": codex_fallback_info.reason,
                    }
                if rate_limit_info.retry_time:
                    codex_output.rate_limit_info = {
                        "is_rate_limited": True,
                        "retry_time": rate_limit_info.retry_time.isoformat() if rate_limit_info.retry_time else None,
                    }

        # 2つのLLMが利用制限に達した場合、残りの1つで3役割を独立実行
        available_llms = self.fallback_manager.get_available_llms()
        if len(available_llms) == 0:
            # 全てのLLMが利用制限に達している場合
            logger.error("All LLMs are rate limited")
            retry_times = {}
            for llm_name in [LLMName.CODEX, LLMName.CLAUDE, LLMName.GEMINI]:
                # 各LLMのリトライ時間を取得（可能な場合）
                retry_times[llm_name] = None  # 実際の実装では、エラーメッセージから抽出

            error_output = ModelOutput(
                model="system",
                content="All LLMs (Codex, Claude, Gemini) have reached their usage limits. Please try again later.",
                metadata={
                    "status": "error",
                    "error": "all_llms_rate_limited",
                    "trace_id": str(uuid.uuid4()),
                },
                rate_limit_info={
                    "is_rate_limited": True,
                    "retry_times": retry_times,
                },
            )

            outputs = {
                "codex": error_output,
                "claude": error_output,
                "gemini": error_output,
            }
            return finalize(outputs)

        if len(available_llms) == 1:
            # 1つのLLMのみが利用可能な場合、そのLLMで3役割を独立実行
            single_llm_client, fallback_infos = self.fallback_manager.get_single_llm_for_all_roles()
            if single_llm_client and fallback_infos:
                logger.info(f"Only {single_llm_client.model_name} is available, executing all 3 roles independently")
                return await self._run_single_llm_all_roles(
                    single_llm_client, task, logs, timeline, fallback_infos, verbose, return_details, finalize
                )

        # strictポリシーでCodexが失敗した場合の処理（フォールバック後も失敗した場合）
        if self._should_stop_on_failure(codex_output) and not codex_fallback_info:
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

        # Evaluation役割（Claude）の実行
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
            claude_output, claude_fallback_info = await self._call_with_fallback(
                self.claude_client,
                claude_prompt,
                logs,
                timeline,
                "claude",
                Role.EVALUATION,
                codex_output.content,
                verbose,
            )

            # 利用制限をチェック
            if claude_output.metadata.get("status") == "error":
                error_msg = claude_output.metadata.get("error", "")
                rate_limit_info = self.fallback_manager.check_rate_limit(error_msg, LLMName.CLAUDE)
                if rate_limit_info.is_rate_limited:
                    self.fallback_manager.mark_rate_limited(LLMName.CLAUDE)
                    if claude_fallback_info:
                        claude_output.fallback_info = {
                            "original_llm": claude_fallback_info.original_llm,
                            "fallback_llm": claude_fallback_info.fallback_llm,
                            "role": claude_fallback_info.role,
                            "reason": claude_fallback_info.reason,
                        }
                    if rate_limit_info.retry_time:
                        claude_output.rate_limit_info = {
                            "is_rate_limited": True,
                            "retry_time": rate_limit_info.retry_time.isoformat() if rate_limit_info.retry_time else None,
                        }

            # strictポリシーでClaudeが失敗した場合の処理（フォールバック後も失敗した場合）
            if self._should_stop_on_failure(claude_output) and not claude_fallback_info:
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

        # Exploration役割（Gemini）の実行
        gemini_output, gemini_fallback_info = await self._call_with_fallback(
            self.gemini_client,
            gemini_prompt,
            logs,
            timeline,
            "gemini",
            Role.EXPLORATION,
            claude_output.content,
            verbose,
        )

        # 利用制限をチェック
        if gemini_output.metadata.get("status") == "error":
            error_msg = gemini_output.metadata.get("error", "")
            rate_limit_info = self.fallback_manager.check_rate_limit(error_msg, LLMName.GEMINI)
            if rate_limit_info.is_rate_limited:
                self.fallback_manager.mark_rate_limited(LLMName.GEMINI)
                if gemini_fallback_info:
                    gemini_output.fallback_info = {
                        "original_llm": gemini_fallback_info.original_llm,
                        "fallback_llm": gemini_fallback_info.fallback_llm,
                        "role": gemini_fallback_info.role,
                        "reason": gemini_fallback_info.reason,
                    }
                if rate_limit_info.retry_time:
                    gemini_output.rate_limit_info = {
                        "is_rate_limited": True,
                        "retry_time": rate_limit_info.retry_time.isoformat() if rate_limit_info.retry_time else None,
                    }

        # JudgeはCursorが担当するため、3案を返す
        outputs = {
            "codex": codex_output,
            "claude": claude_output,
            "gemini": gemini_output,
        }
        return finalize(outputs)

    async def _call_with_fallback(
        self,
        client: BaseLLMClient,
        prompt: str,
        logs: list,
        timeline: list[str],
        step: str,
        role: str,
        context: str,
        verbose: bool,
    ) -> Tuple[ModelOutput, Optional[object]]:
        """
        Call LLM with fallback support for rate limits.

        Returns:
            Tuple of (ModelOutput, FallbackInfo or None)
        """
        import logging
        logger = logging.getLogger(__name__)

        # まず元のLLMで試行
        result = await client.generate_with_result(prompt, trace_id=str(uuid.uuid4()))
        logger.info(f"[DEBUG] {step} result type: {type(result).__name__}, isinstance(result, LLMFailure): {isinstance(result, LLMFailure)}")
        output = result.to_model_output()

        # エラーが発生した場合、利用制限をチェック
        if isinstance(result, LLMFailure):
            error_msg = result.error_message
            llm_name = step  # "codex", "claude", "gemini"
            logger.warning(f"[FALLBACK] LLMFailure detected for {llm_name}: {error_msg[:200]}")
            rate_limit_info = self.fallback_manager.check_rate_limit(error_msg, llm_name)
            logger.warning(f"[FALLBACK] Rate limit check for {llm_name}: is_rate_limited={rate_limit_info.is_rate_limited}")

            if rate_limit_info.is_rate_limited:
                # 利用制限に達している場合、フォールバックを試みる
                self.fallback_manager.mark_rate_limited(llm_name)

                # フォールバック先を取得
                fallback_client, fallback_info = self.fallback_manager.get_fallback_client(role, llm_name)
                logger.info(f"Fallback client lookup for {llm_name} (role={role}): client={fallback_client is not None}, info={fallback_info is not None}")

                if fallback_client and fallback_info:
                    # フォールバック先で再試行
                    logger.info(
                        f"Rate limit detected for {llm_name}, using {fallback_info.fallback_llm} as fallback for {role}"
                    )
                    fallback_prompt = self.fallback_manager.build_fallback_prompt(
                        role, fallback_info.fallback_llm, context
                    )
                    fallback_result = await fallback_client.generate_with_result(
                        fallback_prompt, trace_id=str(uuid.uuid4())
                    )
                    fallback_output = fallback_result.to_model_output()

                    # フォールバック情報を設定
                    fallback_output.fallback_info = {
                        "original_llm": fallback_info.original_llm,
                        "fallback_llm": fallback_info.fallback_llm,
                        "role": fallback_info.role,
                        "reason": fallback_info.reason,
                    }
                    if rate_limit_info.retry_time:
                        fallback_output.rate_limit_info = {
                            "is_rate_limited": True,
                            "retry_time": rate_limit_info.retry_time.isoformat() if rate_limit_info.retry_time else None,
                        }

                    # ログとタイムラインに記録
                    if verbose:
                        trace_id = fallback_output.metadata.get("trace_id", str(uuid.uuid4()))
                        status = fallback_output.metadata.get("status", "unknown")
                        self._append_log_entry(
                            logs=logs,
                            step=f"{step}(fallback:{fallback_info.fallback_llm})",
                            trace_id=trace_id,
                            status=status,
                            duration_ms=fallback_output.metadata.get("duration_ms"),
                            source=fallback_output.metadata.get("source"),
                            prompt=fallback_prompt,
                            content=fallback_output.content,
                            reason=f"fallback from {llm_name} due to rate limit",
                        )
                        timeline.append(
                            f"[{step}] fallback to {fallback_info.fallback_llm} (rate limit, trace_id={trace_id})"
                        )

                    return fallback_output, fallback_info

        # フォールバックが不要な場合、通常のログ記録
        if verbose:
            trace_id = output.metadata.get("trace_id", str(uuid.uuid4()))
            timeline.append(f"[start] {step} (trace_id={trace_id})")
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

        return output, None

    async def _run_single_llm_all_roles(
        self,
        client: BaseLLMClient,
        task: str,
        logs: list,
        timeline: list[str],
        fallback_infos: list,
        verbose: bool,
        return_details: bool,
        finalize,
    ) -> Dict[str, ModelOutput] | tuple[Dict[str, ModelOutput], list, str, list[str]]:
        """
        Run all three roles using a single LLM independently.

        This is used when 2 out of 3 LLMs are rate limited.
        Each role is executed as an independent request to maintain objectivity.
        """
        import logging
        logger = logging.getLogger(__name__)

        # Execution役割を独立実行
        execution_prompt = self.fallback_manager.build_fallback_prompt(Role.EXECUTION, client.model_name, task)
        execution_result = await client.generate_with_result(execution_prompt, trace_id=str(uuid.uuid4()))
        execution_output = execution_result.to_model_output()
        execution_output.fallback_info = {
            "original_llm": fallback_infos[0].original_llm if fallback_infos else client.model_name,
            "fallback_llm": client.model_name,
            "role": Role.EXECUTION,
            "reason": f"Executing {Role.EXECUTION} role independently",
        }

        if verbose:
            trace_id = execution_output.metadata.get("trace_id", str(uuid.uuid4()))
            timeline.append(f"[start] {client.model_name}(execution) (trace_id={trace_id})")
            self._append_log_entry(
                logs=logs,
                step=f"{client.model_name}(execution)",
                trace_id=trace_id,
                status=execution_output.metadata.get("status", "unknown"),
                duration_ms=execution_output.metadata.get("duration_ms"),
                source=execution_output.metadata.get("source"),
                prompt=execution_prompt,
                content=execution_output.content,
                reason="independent execution",
            )

        # Evaluation役割を独立実行（Executionの出力をコンテキストとして使用）
        evaluation_prompt = self.fallback_manager.build_fallback_prompt(
            Role.EVALUATION, client.model_name, execution_output.content
        )
        evaluation_result = await client.generate_with_result(evaluation_prompt, trace_id=str(uuid.uuid4()))
        evaluation_output = evaluation_result.to_model_output()
        evaluation_output.fallback_info = {
            "original_llm": fallback_infos[1].original_llm if len(fallback_infos) > 1 else client.model_name,
            "fallback_llm": client.model_name,
            "role": Role.EVALUATION,
            "reason": f"Executing {Role.EVALUATION} role independently",
        }

        if verbose:
            trace_id = evaluation_output.metadata.get("trace_id", str(uuid.uuid4()))
            timeline.append(f"[start] {client.model_name}(evaluation) (trace_id={trace_id})")
            self._append_log_entry(
                logs=logs,
                step=f"{client.model_name}(evaluation)",
                trace_id=trace_id,
                status=evaluation_output.metadata.get("status", "unknown"),
                duration_ms=evaluation_output.metadata.get("duration_ms"),
                source=evaluation_output.metadata.get("source"),
                prompt=evaluation_prompt,
                content=evaluation_output.content,
                reason="independent execution",
            )

        # Exploration役割を独立実行（Evaluationの出力をコンテキストとして使用）
        exploration_prompt = self.fallback_manager.build_fallback_prompt(
            Role.EXPLORATION, client.model_name, evaluation_output.content
        )
        exploration_result = await client.generate_with_result(exploration_prompt, trace_id=str(uuid.uuid4()))
        exploration_output = exploration_result.to_model_output()
        exploration_output.fallback_info = {
            "original_llm": fallback_infos[2].original_llm if len(fallback_infos) > 2 else client.model_name,
            "fallback_llm": client.model_name,
            "role": Role.EXPLORATION,
            "reason": f"Executing {Role.EXPLORATION} role independently",
        }

        if verbose:
            trace_id = exploration_output.metadata.get("trace_id", str(uuid.uuid4()))
            timeline.append(f"[start] {client.model_name}(exploration) (trace_id={trace_id})")
            self._append_log_entry(
                logs=logs,
                step=f"{client.model_name}(exploration)",
                trace_id=trace_id,
                status=exploration_output.metadata.get("status", "unknown"),
                duration_ms=exploration_output.metadata.get("duration_ms"),
                source=exploration_output.metadata.get("source"),
                prompt=exploration_prompt,
                content=exploration_output.content,
                reason="independent execution",
            )

        # 出力を構築（元のLLM名を保持）
        outputs = {
            "codex": execution_output if client.model_name != LLMName.CODEX else execution_output,
            "claude": evaluation_output if client.model_name != LLMName.CLAUDE else evaluation_output,
            "gemini": exploration_output if client.model_name != LLMName.GEMINI else exploration_output,
        }

        # モデル名を元の役割に合わせて調整
        if client.model_name == LLMName.GEMINI:
            outputs["codex"].model = "codex"
            outputs["claude"].model = "claude"
            outputs["gemini"].model = "gemini"
        elif client.model_name == LLMName.CLAUDE:
            outputs["codex"].model = "codex"
            outputs["claude"].model = "claude"
            outputs["gemini"].model = "gemini"
        elif client.model_name == LLMName.CODEX:
            outputs["codex"].model = "codex"
            outputs["claude"].model = "claude"
            outputs["gemini"].model = "gemini"

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
