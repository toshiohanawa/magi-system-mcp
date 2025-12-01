"""
Rate limit detection and retry time extraction for LLM CLI services.

This module provides utilities to detect when an LLM service has hit its usage limit
and extract retry time information from error messages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class RateLimitInfo:
    """Information about rate limit status for an LLM service."""

    is_rate_limited: bool
    retry_time: Optional[datetime] = None
    error_message: str = ""
    service_name: str = ""


# 利用制限を示すキーワードパターン
RATE_LIMIT_PATTERNS = [
    r"usage limit",
    r"quota exceeded",
    r"rate limit",
    r"credits",
    r"upgrade to pro",
    r"usage limit reached",
    r"quota",
    r"billing",
    r"subscription",
    r"plan upgrade",
]

# リトライ時間を抽出するパターン
RETRY_TIME_PATTERNS = [
    # "try again at Dec 5th, 2025 4:05 PM"
    r"try again at (.+?)(?:\.|$)",
    # "retry after 2025-12-05 16:05:00"
    r"retry after (.+?)(?:\.|$)",
    # "available at 2025-12-05T16:05:00Z"
    r"available at (.+?)(?:\.|$)",
    # "reset at Dec 5, 2025"
    r"reset at (.+?)(?:\.|$)",
]


def is_rate_limited(error_message: str) -> bool:
    """
    Check if an error message indicates a rate limit or usage limit.

    Args:
        error_message: The error message from the LLM service

    Returns:
        True if the error indicates a rate/usage limit, False otherwise
    """
    if not error_message:
        return False

    error_lower = error_message.lower()

    # パターンマッチング
    for pattern in RATE_LIMIT_PATTERNS:
        if re.search(pattern, error_lower, re.IGNORECASE):
            return True

    return False


def extract_retry_time(error_message: str) -> Optional[datetime]:
    """
    Extract retry time from error message if available.

    Args:
        error_message: The error message from the LLM service

    Returns:
        datetime object if retry time is found, None otherwise
    """
    if not error_message:
        return None

    # 各パターンでリトライ時間を抽出
    for pattern in RETRY_TIME_PATTERNS:
        match = re.search(pattern, error_message, re.IGNORECASE)
        if match:
            time_str = match.group(1).strip()
            try:
                # 一般的な日時形式を試す
                # "Dec 5th, 2025 4:05 PM" 形式
                if "pm" in time_str.lower() or "am" in time_str.lower():
                    # dateutilを使うか、手動でパース
                    # 簡易版: 主要な形式をサポート
                    parsed = _parse_datetime_string(time_str)
                    if parsed:
                        return parsed
                else:
                    # ISO形式やその他の形式
                    parsed = _parse_datetime_string(time_str)
                    if parsed:
                        return parsed
            except Exception:
                # パースに失敗した場合は次のパターンを試す
                continue

    return None


def _parse_datetime_string(time_str: str) -> Optional[datetime]:
    """
    Parse various datetime string formats.

    Args:
        time_str: String containing datetime information

    Returns:
        datetime object if parsing succeeds, None otherwise
    """
    # 簡易的なパース（主要な形式をサポート）
    # より完全な実装には dateutil を使用することを推奨

    # ISO形式: "2025-12-05T16:05:00Z"
    iso_pattern = r"(\d{4}-\d{2}-\d{2})T?(\d{2}:\d{2}:\d{2})Z?"
    iso_match = re.match(iso_pattern, time_str)
    if iso_match:
        date_part = iso_match.group(1)
        time_part = iso_match.group(2)
        try:
            return datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            pass

    # "Dec 5th, 2025 4:05 PM" 形式（簡易版）
    # 完全な実装には dateutil が必要
    # ここでは基本的な形式のみをサポート

    return None


def check_rate_limit(error_message: str, service_name: str = "") -> RateLimitInfo:
    """
    Check if an error indicates rate limiting and extract retry time.

    Args:
        error_message: The error message from the LLM service
        service_name: Name of the service (e.g., "codex", "claude", "gemini")

    Returns:
        RateLimitInfo object with rate limit status and retry time
    """
    is_limited = is_rate_limited(error_message)
    retry_time = extract_retry_time(error_message) if is_limited else None

    return RateLimitInfo(
        is_rate_limited=is_limited,
        retry_time=retry_time,
        error_message=error_message,
        service_name=service_name,
    )

