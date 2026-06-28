"""Логирование HTTP-запросов ChatList."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
LOG_DIR = APP_DIR / "logs"


def setup_request_logger(enabled: bool) -> logging.Logger:
    logger = logging.getLogger("chatlist.requests")
    logger.handlers.clear()
    logger.setLevel(logging.INFO if enabled else logging.CRITICAL)
    if enabled:
        LOG_DIR.mkdir(exist_ok=True)
        log_file = LOG_DIR / "requests.log"
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )
        logger.addHandler(handler)
    return logger


def log_request(
    logger: logging.Logger,
    model_name: str,
    prompt: str,
    status: str,
    detail: str = "",
) -> None:
    preview = prompt.replace("\n", " ")
    if len(preview) > 120:
        preview = preview[:120] + "..."
    message = f"model={model_name} | status={status} | prompt={preview}"
    if detail:
        message += f" | detail={detail}"
    logger.info(message)
