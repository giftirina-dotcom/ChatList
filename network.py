"""HTTP-запросы к API нейросетей."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable

import httpx

from models import ChatListService, Model, TempResult

OPENAI_COMPATIBLE_TYPES = {"openai", "deepseek", "groq", "openrouter"}


@dataclass
class ModelResponse:
    model_id: int
    model_name: str
    response_text: str
    error: str | None = None

    def to_temp_result(self, selected: bool = False) -> TempResult:
        text = self.response_text if self.error is None else f"[Ошибка] {self.error}"
        return TempResult(
            model_id=self.model_id,
            model_name=self.model_name,
            response_text=text,
            selected=selected,
            error=self.error,
        )


def _extract_openai_content(data: dict) -> str:
    try:
        return str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Неожиданный формат ответа API") from exc


def _build_openai_payload(model: Model, prompt: str) -> dict:
    return {
        "model": model.api_id,
        "messages": [{"role": "user", "content": prompt}],
    }


def _build_headers(model: Model, api_key: str) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if (model.model_type or "").lower() == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/chatlist"
        headers["X-Title"] = "ChatList"
    return headers


def _send_openai_compatible(
    model: Model,
    prompt: str,
    api_key: str,
    timeout: float,
) -> str:
    headers = _build_headers(model, api_key)
    payload = _build_openai_payload(model, prompt)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(model.api_url, headers=headers, json=payload)
        response.raise_for_status()
        return _extract_openai_content(response.json())


def send_prompt_to_model(
    model: Model,
    prompt: str,
    api_key: str | None,
    timeout: float = 30.0,
    logger: logging.Logger | None = None,
) -> ModelResponse:
    if not prompt.strip():
        return ModelResponse(
            model_id=model.id,
            model_name=model.name,
            response_text="",
            error="Промт пустой",
        )

    if api_key is None:
        error = f"API-ключ не найден в .env ({model.api_key_env})"
        if logger:
            from app_logger import log_request

            log_request(logger, model.name, prompt, "error", error)
        return ModelResponse(
            model_id=model.id,
            model_name=model.name,
            response_text="",
            error=error,
        )

    model_type = (model.model_type or "openai").lower()
    if model_type not in OPENAI_COMPATIBLE_TYPES:
        error = f"Неподдерживаемый тип модели: {model_type}"
        if logger:
            from app_logger import log_request

            log_request(logger, model.name, prompt, "error", error)
        return ModelResponse(
            model_id=model.id,
            model_name=model.name,
            response_text="",
            error=error,
        )

    try:
        text = _send_openai_compatible(model, prompt, api_key, timeout)
        if logger:
            from app_logger import log_request

            log_request(logger, model.name, prompt, "ok")
        return ModelResponse(
            model_id=model.id,
            model_name=model.name,
            response_text=text,
        )
    except httpx.TimeoutException:
        error = "Превышено время ожидания ответа"
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip()
        if len(detail) > 200:
            detail = detail[:200] + "..."
        error = f"HTTP {exc.response.status_code}: {detail or exc.response.reason_phrase}"
    except httpx.RequestError as exc:
        error = f"Ошибка сети: {exc}"
    except ValueError as exc:
        error = str(exc)

    if logger:
        from app_logger import log_request

        log_request(logger, model.name, prompt, "error", error)
    return ModelResponse(
        model_id=model.id,
        model_name=model.name,
        response_text="",
        error=error,
    )


def send_prompt_to_all(
    models: list[Model],
    prompt: str,
    get_api_key: Callable[[Model], str | None],
    timeout: float = 30.0,
    parallel: bool = True,
    logger: logging.Logger | None = None,
) -> list[ModelResponse]:
    if not models:
        return []

    if not parallel:
        return [
            send_prompt_to_model(model, prompt, get_api_key(model), timeout, logger)
            for model in models
        ]

    results: list[ModelResponse] = []
    with ThreadPoolExecutor(max_workers=min(len(models), 8)) as executor:
        futures = {
            executor.submit(
                send_prompt_to_model,
                model,
                prompt,
                get_api_key(model),
                timeout,
                logger,
            ): model
            for model in models
        }
        for future in as_completed(futures):
            results.append(future.result())

    order = {model.id: index for index, model in enumerate(models)}
    results.sort(key=lambda item: order.get(item.model_id, 0))
    return results


def send_prompt_via_service(
    service: ChatListService,
    prompt: str,
    parallel: bool = True,
    logger: logging.Logger | None = None,
) -> list[ModelResponse]:
    models = service.get_active_models()
    timeout = float(service.get_request_timeout())
    return send_prompt_to_all(
        models=models,
        prompt=prompt,
        get_api_key=service.get_api_key,
        timeout=timeout,
        parallel=parallel,
        logger=logger,
    )
