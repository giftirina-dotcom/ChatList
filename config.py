"""Загрузка .env и проверка API-ключей."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent

PLACEHOLDER_KEYS = {
    "your_openrouter_api_key_here",
    "your-api-key-here",
    "changeme",
    "insert_key_here",
}


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return APP_DIR


def load_app_env() -> Path:
    """Загружает .env из каталога программы и текущей рабочей директории."""
    app_dir = get_app_dir()
    env_path = app_dir / ".env"
    load_dotenv(env_path, override=True)
    load_dotenv(Path.cwd() / ".env", override=True)
    return env_path


def is_valid_api_key(key: str | None) -> bool:
    if key is None:
        return False
    value = key.strip()
    if len(value) < 8:
        return False
    if value.lower() in PLACEHOLDER_KEYS:
        return False
    return True


def resolve_api_key(primary_env: str, model_type: str | None = None) -> str | None:
    """Ищет ключ в primary_env и типовых резервных переменных."""
    candidates: list[str] = [primary_env]
    if (model_type or "").lower() == "openrouter":
        candidates.extend(["OPENROUTER_API_KEY", "OPENAI_API_KEY"])

    seen: set[str] = set()
    for name in candidates:
        if not name or name in seen:
            continue
        seen.add(name)
        value = os.getenv(name)
        if is_valid_api_key(value):
            return value.strip()
    return None


def get_openrouter_key() -> str | None:
    return resolve_api_key("OPENROUTER_API_KEY", "openrouter")
