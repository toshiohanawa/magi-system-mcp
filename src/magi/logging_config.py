"""
Phase 1: 構造化ロギングの導入

標準ライブラリのみを使用して構造化ロギングを実装します。
"""
from __future__ import annotations

import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any


class JSONFormatter(logging.Formatter):
    """JSON形式でログを出力するフォーマッター"""
    
    def format(self, record: logging.LogRecord) -> str:
        """ログレコードをJSON形式に変換"""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # コンテキスト情報を追加
        if hasattr(record, "session_id"):
            log_data["session_id"] = record.session_id
        if hasattr(record, "trace_id"):
            log_data["trace_id"] = record.trace_id
        if hasattr(record, "model"):
            log_data["model"] = record.model
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "source"):
            log_data["source"] = record.source
        
        # 例外情報を追加
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # 追加のフィールドを追加
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs", "message",
                "pathname", "process", "processName", "relativeCreated", "thread",
                "threadName", "exc_info", "exc_text", "stack_info",
            }:
                log_data[key] = value
        
        return json.dumps(log_data, ensure_ascii=False)


class ContextLoggerAdapter(logging.LoggerAdapter):
    """コンテキスト情報を追加できるロガーアダプター"""
    
    def __init__(self, logger: logging.Logger, context: Optional[Dict[str, Any]] = None):
        super().__init__(logger, context or {})
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """ログメッセージとキーワード引数にコンテキスト情報を追加"""
        if "extra" not in kwargs:
            kwargs["extra"] = {}
        kwargs["extra"].update(self.extra)
        return msg, kwargs


def setup_logging(
    level: str = "INFO",
    use_json: bool = True,
    log_file: Optional[str] = None,
) -> None:
    """
    ロギングを設定する
    
    Args:
        level: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        use_json: JSON形式で出力するかどうか
        log_file: ログファイルのパス（Noneの場合は標準出力のみ）
    """
    # ルートロガーを設定
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # 既存のハンドラーをクリア
    root_logger.handlers.clear()
    
    # フォーマッターを選択
    if use_json:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    # 標準出力ハンドラー
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # ファイルハンドラー（指定されている場合）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # サードパーティライブラリのログレベルを調整
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)


def get_logger(name: str, context: Optional[Dict[str, Any]] = None) -> ContextLoggerAdapter:
    """
    コンテキスト情報付きのロガーを取得する
    
    Args:
        name: ロガー名
        context: コンテキスト情報（session_id, trace_id, model等）
    
    Returns:
        コンテキスト情報付きのロガーアダプター
    """
    logger = logging.getLogger(name)
    return ContextLoggerAdapter(logger, context)

