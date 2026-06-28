"""Ручная проверка модуля db.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

import db


def run_checks() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test_chatlist.db"
        print(f"БД: {db_path}")

        path = db.init_db(db_path)
        assert path == db_path.resolve()

        settings = db.list_settings(db_path=db_path)
        assert len(settings) >= 3
        print(f"Настройки: {len(settings)}")

        models = db.list_models(db_path=db_path)
        assert len(models) == 5
        print(f"Модели: {len(models)} шт.")

        active = db.list_models(active_only=True, db_path=db_path)
        assert len(active) == 5
        print(f"Активных бесплатных моделей: {len(active)}")

        prompt_id = db.create_prompt("Тестовый промт", tags="test", db_path=db_path)
        prompt = db.get_prompt(prompt_id, db_path=db_path)
        assert prompt is not None
        assert prompt["prompt"] == "Тестовый промт"
        print(f"Промт создан: id={prompt_id}")

        assert all(m["is_active"] for m in models)
        print("Все 5 моделей активны")

        result_id = db.create_result(
            prompt_id=prompt_id,
            model_id=models[0]["id"],
            response_text="Тестовый ответ",
            db_path=db_path,
        )
        results = db.list_results(prompt_id=prompt_id, db_path=db_path)
        assert len(results) == 1
        assert results[0]["id"] == result_id
        print(f"Результат сохранён: id={result_id}")

        db.set_setting("request_timeout", "45", db_path=db_path)
        assert db.get_setting("request_timeout", db_path=db_path) == "45"
        print("Настройка обновлена: request_timeout=45")

        db.delete_result(result_id, db_path=db_path)
        assert db.list_results(db_path=db_path) == []
        print("Результат удалён")

        db.delete_prompt(prompt_id, db_path=db_path)
        assert db.get_prompt(prompt_id, db_path=db_path) is None
        print("Промт удалён")

    print("Все проверки db.py пройдены успешно.")


if __name__ == "__main__":
    run_checks()
