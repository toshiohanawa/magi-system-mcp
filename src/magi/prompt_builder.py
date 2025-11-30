"""
Prompt builder for persona-based evaluation.

Builds prompts that inject persona instructions into LLM CLI calls.
"""

import re
import unicodedata
import logging

from magi.personas import MELCHIOR_PROMPT, BALTHASAR_PROMPT, CASPAR_PROMPT

logger = logging.getLogger(__name__)

# 入力検証の設定
MAX_PROPOSAL_LENGTH = 10000
MAX_TAG_COUNT = 10


class Persona:
    """Persona enumeration matching LLM clients."""

    MELCHIOR = "melchior"  # Gemini
    BALTHASAR = "balthasar"  # Claude
    CASPAR = "caspar"  # Codex


PERSONA_PROMPTS = {
    Persona.MELCHIOR: MELCHIOR_PROMPT,
    Persona.BALTHASAR: BALTHASAR_PROMPT,
    Persona.CASPAR: CASPAR_PROMPT,
}


def normalize_input(text: str) -> str:
    """
    Unicode正規化と基本的な文字検証。

    Args:
        text: 入力テキスト

    Returns:
        正規化されたテキスト

    Raises:
        ValueError: 許可されていない文字が含まれている場合
    """
    # Unicode正規化（NFKC形式）
    normalized = unicodedata.normalize('NFKC', text)

    # 許可する文字のホワイトリスト（日本語、英数字、基本的な記号）
    # より寛容なパターンを使用（ほとんどの実用的な文字を許可）
    allowed_chars = set(
        ' \n\t'  # 空白文字
        + ''.join(chr(i) for i in range(0x0020, 0x007F))  # ASCII印刷可能文字
        + ''.join(chr(i) for i in range(0x3040, 0x309F))  # ひらがな
        + ''.join(chr(i) for i in range(0x30A0, 0x30FF))  # カタカナ
        + ''.join(chr(i) for i in range(0x4E00, 0x9FAF))  # CJK統合漢字
        + ''.join(chr(i) for i in range(0x3400, 0x4DBF))  # CJK拡張A
    )

    # 許可されていない文字を検出
    disallowed_chars = set(normalized) - allowed_chars
    if disallowed_chars:
        # 制御文字や特殊文字のみをエラーとする（一般的な記号は許可）
        control_chars = {c for c in disallowed_chars if unicodedata.category(c).startswith('C')}
        if control_chars:
            logger.warning(f"Proposal contains control characters: {control_chars}")
            # 制御文字を削除
            normalized = ''.join(c for c in normalized if c not in control_chars)

    return normalized


def validate_proposal(proposal: str) -> None:
    """
    提案の入力検証。

    Args:
        proposal: ユーザーの提案

    Raises:
        ValueError: 検証に失敗した場合
    """
    # 長さ制限
    if len(proposal) > MAX_PROPOSAL_LENGTH:
        raise ValueError(f"Proposal exceeds maximum length ({MAX_PROPOSAL_LENGTH} characters)")

    # ネストされたタグの検出（区切り文字の検出より先に実行）
    tag_pattern = r'<[^>]+>'
    tags = re.findall(tag_pattern, proposal)
    if len(tags) > MAX_TAG_COUNT:
        raise ValueError(f"Proposal contains excessive tags ({len(tags)} > {MAX_TAG_COUNT})")

    # 区切り文字の検出（大文字小文字、空白を考慮）
    forbidden_patterns = [
        r'<PERSONA_INSTRUCTION>',
        r'</PERSONA_INSTRUCTION>',
        r'<USER_PROPOSAL>',
        r'</USER_PROPOSAL>',
    ]

    proposal_upper = proposal.upper()
    for pattern in forbidden_patterns:
        # 空白とアンダースコアを除去してから検出
        pattern_clean = pattern.replace(' ', '').replace('_', '').replace('-', '').replace('<', '').replace('>', '').replace('/', '')
        proposal_clean = proposal_upper.replace(' ', '').replace('_', '').replace('-', '').replace('<', '').replace('>', '').replace('/', '')
        if pattern_clean in proposal_clean:
            raise ValueError(f"Proposal contains forbidden delimiter: {pattern}")


def escape_structural_tags(text: str) -> str:
    """
    構造タグのエスケープ。

    Args:
        text: エスケープするテキスト

    Returns:
        エスケープされたテキスト
    """
    # 既存の構造タグをエスケープ
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


def build_persona_prompt(persona: str, proposal: str) -> str:
    """
    Build a prompt that combines persona instructions with user proposal.

    For CLI wrappers that don't support explicit system/user separation,
    we use a simple concatenation format with clear delimiters.

    Args:
        persona: One of "melchior", "balthasar", "caspar"
        proposal: The user's proposal to evaluate

    Returns:
        Combined prompt string ready for CLI input

    Raises:
        ValueError: 入力検証に失敗した場合、または不明なペルソナの場合
    """
    # 入力検証と正規化
    try:
        proposal = normalize_input(proposal)
        validate_proposal(proposal)
    except ValueError as e:
        logger.error(f"Input validation failed for persona {persona}: {e}")
        raise ValueError(f"Invalid proposal: {e}") from e
    # エスケープは区切り文字を使用するため、提案部分のみエスケープしない
    # 代わりに、区切り文字で明確に分離することで安全性を確保

    persona_instruction = PERSONA_PROMPTS.get(persona)
    if not persona_instruction:
        error_msg = f"Unknown persona: {persona}. Available personas: {list(PERSONA_PROMPTS.keys())}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # 明確な区切り文字を使用
    return f"""<PERSONA_INSTRUCTION>
{persona_instruction}
</PERSONA_INSTRUCTION>

<USER_PROPOSAL>
{proposal}
</USER_PROPOSAL>

上記の提案を評価し、VOTEとREASONのみを出力してください。"""
