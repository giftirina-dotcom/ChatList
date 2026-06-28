"""Модуль доступа к SQLite для ChatList."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
DEFAULT_DB_FILENAME = "chatlist.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS prompts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT    NOT NULL,
    prompt     TEXT    NOT NULL,
    tags       TEXT
);

CREATE TABLE IF NOT EXISTS models (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    api_url     TEXT    NOT NULL,
    api_id      TEXT    NOT NULL,
    api_key_env TEXT    NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1,
    model_type  TEXT
);

CREATE TABLE IF NOT EXISTS results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id     INTEGER NOT NULL,
    model_id      INTEGER NOT NULL,
    response_text TEXT    NOT NULL,
    created_at    TEXT    NOT NULL,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE,
    FOREIGN KEY (model_id)  REFERENCES models(id)  ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_prompts_created_at ON prompts(created_at);
CREATE INDEX IF NOT EXISTS idx_models_is_active    ON models(is_active);
CREATE INDEX IF NOT EXISTS idx_results_prompt_id   ON results(prompt_id);
CREATE INDEX IF NOT EXISTS idx_results_model_id    ON results(model_id);
CREATE INDEX IF NOT EXISTS idx_results_created_at  ON results(created_at);
"""

SEED_SETTINGS: list[tuple[str, str]] = [
    ("request_timeout", "30"),
    ("db_path", DEFAULT_DB_FILENAME),
    ("log_requests", "0"),
]

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# name, api_url, api_id, api_key_env, is_active, model_type
SEED_MODELS: list[tuple[str, str, str, str, int, str | None]] = [
    (
        "Qwen3 Next 80B (free)",
        OPENROUTER_URL,
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "OPENROUTER_API_KEY",
        1,
        "openrouter",
    ),
    (
        "Gemma 4 31B (free)",
        OPENROUTER_URL,
        "google/gemma-4-31b-it:free",
        "OPENROUTER_API_KEY",
        1,
        "openrouter",
    ),
    (
        "OpenAI: gpt-oss-20b (free)",
        OPENROUTER_URL,
        "openai/gpt-oss-20b:free",
        "OPENROUTER_API_KEY",
        1,
        "openrouter",
    ),
    (
        "OpenAI: gpt-oss-120b (free)",
        OPENROUTER_URL,
        "openai/gpt-oss-120b:free",
        "OPENROUTER_API_KEY",
        1,
        "openrouter",
    ),
    (
        "Nemotron 3 Nano 30B (free)",
        OPENROUTER_URL,
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "OPENROUTER_API_KEY",
        1,
        "openrouter",
    ),
    (
        "Llama 3.2 3B (free)",
        OPENROUTER_URL,
        "meta-llama/llama-3.2-3b-instruct:free",
        "OPENROUTER_API_KEY",
        1,
        "openrouter",
    ),
]

ALLOWED_MODEL_API_IDS = tuple(row[2] for row in SEED_MODELS)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_default_db_path() -> Path:
    return APP_DIR / DEFAULT_DB_FILENAME


def resolve_db_path(path: str | Path | None = None) -> Path:
    if path is None:
        return get_default_db_path()
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = APP_DIR / resolved
    return resolved


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = resolve_db_path(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def open_db(db_path: str | Path | None = None):
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _purge_extra_models(conn: sqlite3.Connection) -> None:
    """Удаляет из БД все модели, не входящие в ALLOWED_MODEL_API_IDS."""
    placeholders = ",".join("?" * len(ALLOWED_MODEL_API_IDS))
    params = list(ALLOWED_MODEL_API_IDS)
    conn.execute(
        f"""
        DELETE FROM results
        WHERE model_id IN (
            SELECT id FROM models WHERE api_id NOT IN ({placeholders})
        )
        """,
        params,
    )
    conn.execute(
        f"DELETE FROM models WHERE api_id NOT IN ({placeholders})",
        params,
    )


def _dedupe_models_by_api_id(conn: sqlite3.Connection) -> None:
    """Оставляет одну запись на api_id (с минимальным id)."""
    conn.execute(
        """
        DELETE FROM models
        WHERE id NOT IN (
            SELECT MIN(id) FROM models GROUP BY api_id
        )
        """
    )


def init_db(db_path: str | Path | None = None) -> Path:
    path = resolve_db_path(db_path)
    with open_db(path) as conn:
        conn.executescript(SCHEMA_SQL)
        for key, value in SEED_SETTINGS:
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        _dedupe_models_by_api_id(conn)
        for name, api_url, api_id, api_key_env, is_active, model_type in SEED_MODELS:
            existing = conn.execute(
                "SELECT id FROM models WHERE api_id = ?",
                (api_id,),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO models
                        (name, api_url, api_id, api_key_env, is_active, model_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (name, api_url, api_id, api_key_env, is_active, model_type),
                )
            else:
                conn.execute(
                    """
                    UPDATE models
                    SET name = ?,
                        api_url = ?,
                        api_key_env = ?,
                        is_active = ?,
                        model_type = ?
                    WHERE api_id = ?
                    """,
                    (name, api_url, api_key_env, is_active, model_type, api_id),
                )
        _purge_extra_models(conn)
        conn.commit()
    return path


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


# --- prompts ---


def create_prompt(
    prompt: str,
    tags: str | None = None,
    created_at: str | None = None,
    db_path: str | Path | None = None,
) -> int:
    created_at = created_at or utc_now_iso()
    with open_db(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO prompts (created_at, prompt, tags) VALUES (?, ?, ?)",
            (created_at, prompt, tags),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_prompt(prompt_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with open_db(db_path) as conn:
        row = conn.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,)).fetchone()
        return _row_to_dict(row)


def list_prompts(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with open_db(db_path) as conn:
        rows = conn.execute("SELECT * FROM prompts ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]


def update_prompt(
    prompt_id: int,
    prompt: str,
    tags: str | None = None,
    db_path: str | Path | None = None,
) -> None:
    with open_db(db_path) as conn:
        conn.execute(
            "UPDATE prompts SET prompt = ?, tags = ? WHERE id = ?",
            (prompt, tags, prompt_id),
        )
        conn.commit()


def delete_prompt(prompt_id: int, db_path: str | Path | None = None) -> None:
    with open_db(db_path) as conn:
        conn.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
        conn.commit()


# --- models ---


def create_model(
    name: str,
    api_url: str,
    api_id: str,
    api_key_env: str,
    is_active: bool = True,
    model_type: str | None = None,
    db_path: str | Path | None = None,
) -> int:
    with open_db(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO models (name, api_url, api_id, api_key_env, is_active, model_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, api_url, api_id, api_key_env, int(is_active), model_type),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_model(model_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with open_db(db_path) as conn:
        row = conn.execute("SELECT * FROM models WHERE id = ?", (model_id,)).fetchone()
        return _row_to_dict(row)


def list_models(
    active_only: bool = False,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM models"
    params: tuple[Any, ...] = ()
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY name"
    with open_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def update_model(
    model_id: int,
    name: str,
    api_url: str,
    api_id: str,
    api_key_env: str,
    is_active: bool,
    model_type: str | None = None,
    db_path: str | Path | None = None,
) -> None:
    with open_db(db_path) as conn:
        conn.execute(
            """
            UPDATE models
            SET name = ?, api_url = ?, api_id = ?, api_key_env = ?,
                is_active = ?, model_type = ?
            WHERE id = ?
            """,
            (name, api_url, api_id, api_key_env, int(is_active), model_type, model_id),
        )
        conn.commit()


def delete_model(model_id: int, db_path: str | Path | None = None) -> None:
    with open_db(db_path) as conn:
        conn.execute("DELETE FROM models WHERE id = ?", (model_id,))
        conn.commit()


# --- results ---


def create_result(
    prompt_id: int,
    model_id: int,
    response_text: str,
    created_at: str | None = None,
    db_path: str | Path | None = None,
) -> int:
    created_at = created_at or utc_now_iso()
    with open_db(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO results (prompt_id, model_id, response_text, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (prompt_id, model_id, response_text, created_at),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_result(result_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with open_db(db_path) as conn:
        row = conn.execute("SELECT * FROM results WHERE id = ?", (result_id,)).fetchone()
        return _row_to_dict(row)


def list_results(
    prompt_id: int | None = None,
    model_id: int | None = None,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM results WHERE 1 = 1"
    params: list[Any] = []
    if prompt_id is not None:
        query += " AND prompt_id = ?"
        params.append(prompt_id)
    if model_id is not None:
        query += " AND model_id = ?"
        params.append(model_id)
    query += " ORDER BY created_at DESC"
    with open_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def delete_result(result_id: int, db_path: str | Path | None = None) -> None:
    with open_db(db_path) as conn:
        conn.execute("DELETE FROM results WHERE id = ?", (result_id,))
        conn.commit()


# --- settings ---


def get_setting(
    key: str,
    default: str | None = None,
    db_path: str | Path | None = None,
) -> str | None:
    with open_db(db_path) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        return str(row["value"])


def set_setting(key: str, value: str, db_path: str | Path | None = None) -> None:
    with open_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        conn.commit()


def list_settings(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with open_db(db_path) as conn:
        rows = conn.execute("SELECT * FROM settings ORDER BY key").fetchall()
        return [dict(row) for row in rows]
