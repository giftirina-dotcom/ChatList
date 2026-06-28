"""Точка входа ChatList."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from PyQt6.QtWidgets import QApplication

from gui import MainWindow
from models import ChatListService

APP_DIR = Path(__file__).resolve().parent


def main() -> None:
    load_dotenv(APP_DIR / ".env")

    service = ChatListService()
    db_path = service.initialize()

    app = QApplication(sys.argv)
    window = MainWindow(service, db_path)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
