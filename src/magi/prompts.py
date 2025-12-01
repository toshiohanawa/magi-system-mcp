from __future__ import annotations

CODEX_PROMPT = (
    """あなたの役割は Execution（実装者）です。\n- 実装可能性を最優先してください。\n- 手順を分解し、具体的に書いてください。\n- 曖昧な表現は避け、必要があればコードまたは疑似コードを書いてください。\n\n【課題】\n{task}\n\n【出力フォーマット】\n1. 目的の明確化\n2. 実行可能な構造案\n3. 手順（Step-by-step）\n4. 必要な技術/ライブラリ\n5. 具体的アウトプット（コード/疑似コード/スキーマなど）"""
)

CLAUDE_PROMPT = (
    """あなたの役割は Evaluation（評価者）です。\nCodex の案を批判的にレビューしてください。\n- リスク\n- 不整合\n- 長期保守性\n- セキュリティ/倫理\n- 構造的弱点\n\n【評価対象】\n{codex_output}\n\n【出力フォーマット】\n1. 指摘\n2. リスク評価（Low/Medium/High）\n3. 改善案\n4. 修正後の推奨構造"""
)

GEMINI_PROMPT = (
    """あなたの役割は Exploration（探索者）です。\nClaude の改善案を踏まえて、発散的な提案をしてください。\n- 代替アーキテクチャ\n- 類推\n- 外部知識統合\n\n【前提】\n{claude_output}\n\n【出力フォーマット】\n1. 新規アプローチ\n2. 類似領域の参考知識\n3. 代替案の Pros/Cons\n4. 発散案を実用案へ変換"""
)

JUDGE_PROMPT = (
    """以下は Codex / Claude / Gemini の3案です。\nJudge として比較し、推奨案を1つに絞ってください。\n\n【Codex】\n{codex_output}\n\n【Claude】\n{claude_output}\n\n【Gemini】\n{gemini_output}\n\n【実行内容】\n1. 3案の要約\n2. 比較表\n3. 強み・弱み・リスク\n4. 最も推奨できる案を1つ選び理由を説明\n5. 合成案が有効かどうか\n6. 最後にユーザーにアクションを質問（採択・合成・再検討）"""
)

# フォールバック役割プロンプト（他のLLMが役割を代行する際に使用）

# ClaudeがExecution役割を代行する場合
CLAUDE_AS_CODEX_PROMPT = (
    """あなたの役割は Execution（実装者）です。\n通常はCodexが担当する役割ですが、Codexが利用制限に達したため、あなたが代行します。\n- 実装可能性を最優先してください。\n- 手順を分解し、具体的に書いてください。\n- 曖昧な表現は避け、必要があればコードまたは疑似コードを書いてください。\n\n【課題】\n{task}\n\n【出力フォーマット】\n1. 目的の明確化\n2. 実行可能な構造案\n3. 手順（Step-by-step）\n4. 必要な技術/ライブラリ\n5. 具体的アウトプット（コード/疑似コード/スキーマなど）"""
)

# GeminiがExecution役割を代行する場合
GEMINI_AS_CODEX_PROMPT = (
    """あなたの役割は Execution（実装者）です。\n通常はCodexが担当する役割ですが、Codexが利用制限に達したため、あなたが代行します。\n- 実装可能性を最優先してください。\n- 手順を分解し、具体的に書いてください。\n- 曖昧な表現は避け、必要があればコードまたは疑似コードを書いてください。\n\n【課題】\n{task}\n\n【出力フォーマット】\n1. 目的の明確化\n2. 実行可能な構造案\n3. 手順（Step-by-step）\n4. 必要な技術/ライブラリ\n5. 具体的アウトプット（コード/疑似コード/スキーマなど）"""
)

# CodexがEvaluation役割を代行する場合
CODEX_AS_CLAUDE_PROMPT = (
    """あなたの役割は Evaluation（評価者）です。\n通常はClaudeが担当する役割ですが、Claudeが利用制限に達したため、あなたが代行します。\n以下の提案を批判的にレビューしてください。\n- リスク\n- 不整合\n- 長期保守性\n- セキュリティ/倫理\n- 構造的弱点\n\n【評価対象】\n{codex_output}\n\n【出力フォーマット】\n1. 指摘\n2. リスク評価（Low/Medium/High）\n3. 改善案\n4. 修正後の推奨構造"""
)

# GeminiがEvaluation役割を代行する場合
GEMINI_AS_CLAUDE_PROMPT = (
    """あなたの役割は Evaluation（評価者）です。\n通常はClaudeが担当する役割ですが、Claudeが利用制限に達したため、あなたが代行します。\n以下の提案を批判的にレビューしてください。\n- リスク\n- 不整合\n- 長期保守性\n- セキュリティ/倫理\n- 構造的弱点\n\n【評価対象】\n{codex_output}\n\n【出力フォーマット】\n1. 指摘\n2. リスク評価（Low/Medium/High）\n3. 改善案\n4. 修正後の推奨構造"""
)

# CodexがExploration役割を代行する場合
CODEX_AS_GEMINI_PROMPT = (
    """あなたの役割は Exploration（探索者）です。\n通常はGeminiが担当する役割ですが、Geminiが利用制限に達したため、あなたが代行します。\n以下の改善案を踏まえて、発散的な提案をしてください。\n- 代替アーキテクチャ\n- 類推\n- 外部知識統合\n\n【前提】\n{claude_output}\n\n【出力フォーマット】\n1. 新規アプローチ\n2. 類似領域の参考知識\n3. 代替案の Pros/Cons\n4. 発散案を実用案へ変換"""
)

# ClaudeがExploration役割を代行する場合
CLAUDE_AS_GEMINI_PROMPT = (
    """あなたの役割は Exploration（探索者）です。\n通常はGeminiが担当する役割ですが、Geminiが利用制限に達したため、あなたが代行します。\n以下の改善案を踏まえて、発散的な提案をしてください。\n- 代替アーキテクチャ\n- 類推\n- 外部知識統合\n\n【前提】\n{claude_output}\n\n【出力フォーマット】\n1. 新規アプローチ\n2. 類似領域の参考知識\n3. 代替案の Pros/Cons\n4. 発散案を実用案へ変換"""
)


def build_codex_prompt(task: str) -> str:
    return CODEX_PROMPT.format(task=task)


def build_claude_prompt(codex_output: str) -> str:
    return CLAUDE_PROMPT.format(codex_output=codex_output)


def build_gemini_prompt(claude_output: str) -> str:
    return GEMINI_PROMPT.format(claude_output=claude_output)


def build_judge_prompt(codex_output: str, claude_output: str, gemini_output: str) -> str:
    return JUDGE_PROMPT.format(
        codex_output=codex_output,
        claude_output=claude_output,
        gemini_output=gemini_output,
    )


# フォールバック役割プロンプトビルダー

def build_fallback_prompt(
    fallback_llm: str,  # "codex", "claude", "gemini"
    original_role: str,  # "execution", "evaluation", "exploration"
    context: str,  # タスクまたは前の出力
) -> str:
    """
    Build a prompt for a fallback LLM to take over a role.

    Args:
        fallback_llm: The LLM that will take over the role ("codex", "claude", "gemini")
        original_role: The role to take over ("execution", "evaluation", "exploration")
        context: The task (for execution) or previous output (for evaluation/exploration)

    Returns:
        Formatted prompt string
    """
    if original_role == "execution":
        if fallback_llm == "claude":
            return CLAUDE_AS_CODEX_PROMPT.format(task=context)
        elif fallback_llm == "gemini":
            return GEMINI_AS_CODEX_PROMPT.format(task=context)
    elif original_role == "evaluation":
        if fallback_llm == "codex":
            return CODEX_AS_CLAUDE_PROMPT.format(codex_output=context)
        elif fallback_llm == "gemini":
            return GEMINI_AS_CLAUDE_PROMPT.format(codex_output=context)
    elif original_role == "exploration":
        if fallback_llm == "codex":
            return CODEX_AS_GEMINI_PROMPT.format(claude_output=context)
        elif fallback_llm == "claude":
            return CLAUDE_AS_GEMINI_PROMPT.format(claude_output=context)

    # フォールバックが見つからない場合は元のプロンプトを使用
    if original_role == "execution":
        return CODEX_PROMPT.format(task=context)
    elif original_role == "evaluation":
        return CLAUDE_PROMPT.format(codex_output=context)
    elif original_role == "exploration":
        return GEMINI_PROMPT.format(claude_output=context)

    raise ValueError(f"Unknown role: {original_role} or fallback LLM: {fallback_llm}")
