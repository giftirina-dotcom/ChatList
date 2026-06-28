"""Фоновая отправка промта в нейросети."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from app_logger import setup_request_logger
from models import ChatListService
from network import ModelResponse, send_prompt_via_service


class SendPromptWorker(QThread):
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, service: ChatListService, prompt: str) -> None:
        super().__init__()
        self.service = service
        self.prompt = prompt

    def run(self) -> None:
        try:
            logger = None
            if self.service.is_log_requests_enabled():
                logger = setup_request_logger(True)
            responses: list[ModelResponse] = send_prompt_via_service(
                self.service,
                self.prompt,
                parallel=True,
                logger=logger,
            )
            self.finished.emit(responses)
        except Exception as exc:
            self.failed.emit(str(exc))
