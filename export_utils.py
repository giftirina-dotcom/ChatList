"""Экспорт результатов в Markdown и JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from models import ChatListService, Result, TempResult


def _result_payload(
    service: ChatListService,
    result: Result | TempResult,
    prompt_text: str | None = None,
) -> dict:
    if isinstance(result, Result):
        prompt = service.get_prompt(result.prompt_id)
        model = service.get_model(result.model_id)
        return {
            "prompt_id": result.prompt_id,
            "prompt": prompt.prompt if prompt else prompt_text or "",
            "model_id": result.model_id,
            "model_name": model.name if model else "",
            "response_text": result.response_text,
            "created_at": result.created_at,
        }
    return {
        "model_id": result.model_id,
        "model_name": result.model_name,
        "response_text": result.response_text,
        "prompt": prompt_text or "",
        "error": result.error,
    }


def export_to_json(
    service: ChatListService,
    items: list[Result | TempResult],
    path: Path,
    prompt_text: str | None = None,
) -> None:
    data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "results": [_result_payload(service, item, prompt_text) for item in items],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def export_to_markdown(
    service: ChatListService,
    items: list[Result | TempResult],
    path: Path,
    prompt_text: str | None = None,
) -> None:
    lines = [
        "# ChatList — экспорт результатов",
        "",
        f"Дата экспорта: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    for index, item in enumerate(items, start=1):
        payload = _result_payload(service, item, prompt_text)
        lines.extend(
            [
                f"## {index}. {payload.get('model_name', 'Модель')}",
                "",
                f"**Промт:** {payload.get('prompt', '')}",
                "",
                payload.get("response_text", ""),
                "",
                "---",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")
