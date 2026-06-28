"""Точка входа ChatList."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from config import get_openrouter_key, load_app_env
from gui import MainWindow
from models import ChatListService


def main() -> None:
    env_path = load_app_env()

    service = ChatListService()
    db_path = service.initialize()

    app = QApplication(sys.argv)
    window = MainWindow(service, db_path, env_path)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
