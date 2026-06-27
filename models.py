"""Бизнес-логика ChatList: промты, модели, результаты, настройки."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import db


@dataclass
class Prompt:
    id: int
    created_at: str
    prompt: str
    tags: str | None

    @classmethod
    def from_row(cls, row: dict) -> Prompt:
        return cls(
            id=row["id"],
            created_at=row["created_at"],
            prompt=row["prompt"],
            tags=row.get("tags"),
        )


@dataclass
class Model:
    id: int
    name: str
    api_url: str
    api_id: str
    api_key_env: str
    is_active: bool
    model_type: str | None

    @classmethod
    def from_row(cls, row: dict) -> Model:
        return cls(
            id=row["id"],
            name=row["name"],
            api_url=row["api_url"],
            api_id=row["api_id"],
            api_key_env=row["api_key_env"],
            is_active=bool(row["is_active"]),
            model_type=row.get("model_type"),
        )


@dataclass
class Result:
    id: int
    prompt_id: int
    model_id: int
    response_text: str
    created_at: str

    @classmethod
    def from_row(cls, row: dict) -> Result:
        return cls(
            id=row["id"],
            prompt_id=row["prompt_id"],
            model_id=row["model_id"],
            response_text=row["response_text"],
            created_at=row["created_at"],
        )


@dataclass
class Setting:
    key: str
    value: str

    @classmethod
    def from_row(cls, row: dict) -> Setting:
        return cls(key=row["key"], value=row["value"])


@dataclass
class TempResult:
    """Временный результат в памяти (не сохраняется в SQLite)."""

    model_id: int
    model_name: str
    response_text: str
    selected: bool = False
    error: str | None = None


class ChatListService:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db.resolve_db_path(db_path) if db_path else db.get_default_db_path()

    def initialize(self) -> Path:
        return db.init_db(self.db_path)

    # --- models ---

    def get_active_models(self) -> list[Model]:
        rows = db.list_models(active_only=True, db_path=self.db_path)
        return [Model.from_row(row) for row in rows]

    def get_all_models(self) -> list[Model]:
        rows = db.list_models(active_only=False, db_path=self.db_path)
        return [Model.from_row(row) for row in rows]

    def get_model(self, model_id: int) -> Model | None:
        row = db.get_model(model_id, db_path=self.db_path)
        return Model.from_row(row) if row else None

    def create_model(
        self,
        name: str,
        api_url: str,
        api_id: str,
        api_key_env: str,
        is_active: bool = True,
        model_type: str | None = None,
    ) -> Model:
        model_id = db.create_model(
            name=name,
            api_url=api_url,
            api_id=api_id,
            api_key_env=api_key_env,
            is_active=is_active,
            model_type=model_type,
            db_path=self.db_path,
        )
        model = self.get_model(model_id)
        assert model is not None
        return model

    def update_model(self, model: Model) -> None:
        db.update_model(
            model_id=model.id,
            name=model.name,
            api_url=model.api_url,
            api_id=model.api_id,
            api_key_env=model.api_key_env,
            is_active=model.is_active,
            model_type=model.model_type,
            db_path=self.db_path,
        )

    def delete_model(self, model_id: int) -> None:
        db.delete_model(model_id, db_path=self.db_path)

    def get_api_key(self, model: Model) -> str | None:
        value = os.getenv(model.api_key_env)
        if value is None or not value.strip():
            return None
        return value.strip()

    # --- prompts ---

    def save_prompt(self, text: str, tags: str | None = None) -> Prompt:
        prompt_id = db.create_prompt(prompt=text, tags=tags, db_path=self.db_path)
        row = db.get_prompt(prompt_id, db_path=self.db_path)
        assert row is not None
        return Prompt.from_row(row)

    def get_prompt(self, prompt_id: int) -> Prompt | None:
        row = db.get_prompt(prompt_id, db_path=self.db_path)
        return Prompt.from_row(row) if row else None

    def list_prompts(self) -> list[Prompt]:
        rows = db.list_prompts(db_path=self.db_path)
        return [Prompt.from_row(row) for row in rows]

    def update_prompt(self, prompt: Prompt) -> None:
        db.update_prompt(
            prompt_id=prompt.id,
            prompt=prompt.prompt,
            tags=prompt.tags,
            db_path=self.db_path,
        )

    def delete_prompt(self, prompt_id: int) -> None:
        db.delete_prompt(prompt_id, db_path=self.db_path)

    # --- results ---

    def save_results(
        self,
        prompt_id: int,
        temp_results: list[TempResult],
    ) -> list[Result]:
        saved: list[Result] = []
        for item in temp_results:
            if not item.selected or item.error:
                continue
            result_id = db.create_result(
                prompt_id=prompt_id,
                model_id=item.model_id,
                response_text=item.response_text,
                db_path=self.db_path,
            )
            row = db.get_result(result_id, db_path=self.db_path)
            assert row is not None
            saved.append(Result.from_row(row))
        return saved

    def list_results(
        self,
        prompt_id: int | None = None,
        model_id: int | None = None,
    ) -> list[Result]:
        rows = db.list_results(
            prompt_id=prompt_id,
            model_id=model_id,
            db_path=self.db_path,
        )
        return [Result.from_row(row) for row in rows]

    def delete_result(self, result_id: int) -> None:
        db.delete_result(result_id, db_path=self.db_path)

    # --- settings ---

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        return db.get_setting(key, default=default, db_path=self.db_path)

    def set_setting(self, key: str, value: str) -> None:
        db.set_setting(key, value, db_path=self.db_path)

    def list_settings(self) -> list[Setting]:
        rows = db.list_settings(db_path=self.db_path)
        return [Setting.from_row(row) for row in rows]

    def get_request_timeout(self) -> int:
        raw = self.get_setting("request_timeout", "30")
        try:
            return max(1, int(raw or "30"))
        except ValueError:
            return 30
