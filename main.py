"""Точка входа и графический интерфейс ChatList."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models import ChatListService, TempResult

APP_DIR = Path(__file__).resolve().parent


class MainWindow(QMainWindow):
    def __init__(self, service: ChatListService) -> None:
        super().__init__()
        self.service = service
        self.current_prompt_id: int | None = None
        self.temp_results: list[TempResult] = []

        self.setWindowTitle("ChatList")
        self.resize(960, 640)

        tabs = QTabWidget()
        tabs.addTab(self._build_request_tab(), "Запрос")
        tabs.addTab(self._build_placeholder_tab("Управление моделями"), "Модели")
        tabs.addTab(self._build_placeholder_tab("История промтов"), "Промты")
        tabs.addTab(self._build_placeholder_tab("Сохранённые результаты"), "Результаты")
        tabs.addTab(self._build_placeholder_tab("Настройки программы"), "Настройки")
        self.setCentralWidget(tabs)

    def _build_placeholder_tab(self, title: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        label = QLabel(f"{title} — будет реализовано на следующих этапах.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        return widget

    def _build_request_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        prompt_row = QHBoxLayout()
        prompt_row.addWidget(QLabel("Сохранённый промт:"))
        self.prompt_combo = QComboBox()
        self.prompt_combo.addItem("— новый промт —", None)
        self.prompt_combo.currentIndexChanged.connect(self.on_prompt_selected)
        prompt_row.addWidget(self.prompt_combo, stretch=1)
        layout.addLayout(prompt_row)

        layout.addWidget(QLabel("Промт:"))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Введите текст запроса...")
        self.prompt_edit.setMinimumHeight(120)
        layout.addWidget(self.prompt_edit)

        tags_row = QHBoxLayout()
        tags_row.addWidget(QLabel("Теги:"))
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("python, test")
        tags_row.addWidget(self.tags_edit, stretch=1)
        layout.addLayout(tags_row)

        buttons_row = QHBoxLayout()
        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.on_send_clicked)
        buttons_row.addWidget(self.send_button)

        self.save_button = QPushButton("Сохранить")
        self.save_button.clicked.connect(self.on_save_clicked)
        self.save_button.setEnabled(False)
        buttons_row.addWidget(self.save_button)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        layout.addWidget(QLabel("Результаты:"))
        self.results_table = QTableWidget(0, 3)
        self.results_table.setHorizontalHeaderLabels(["Модель", "Ответ", "Выбрать"])
        header = self.results_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.itemChanged.connect(self._on_result_checkbox_changed)
        layout.addWidget(self.results_table)

        self.status_label = QLabel("Готово")
        layout.addWidget(self.status_label)

        self._reload_prompt_combo()
        return widget

    def _reload_prompt_combo(self) -> None:
        current_data = self.prompt_combo.currentData()
        self.prompt_combo.blockSignals(True)
        self.prompt_combo.clear()
        self.prompt_combo.addItem("— новый промт —", None)
        for prompt in self.service.list_prompts():
            label = prompt.prompt.replace("\n", " ")
            if len(label) > 60:
                label = label[:60] + "..."
            self.prompt_combo.addItem(label, prompt.id)
        index = self.prompt_combo.findData(current_data)
        self.prompt_combo.setCurrentIndex(index if index >= 0 else 0)
        self.prompt_combo.blockSignals(False)

    def on_prompt_selected(self, index: int) -> None:
        if index <= 0:
            return
        prompt_id = self.prompt_combo.itemData(index)
        if prompt_id is None:
            return
        prompt = self.service.get_prompt(int(prompt_id))
        if prompt is None:
            return
        self.prompt_edit.setPlainText(prompt.prompt)
        self.tags_edit.setText(prompt.tags or "")
        self.current_prompt_id = prompt.id
        self.status_label.setText(f"Выбран сохранённый промт #{prompt.id}")

    def on_send_clicked(self) -> None:
        prompt_text = self.prompt_edit.toPlainText().strip()
        if not prompt_text:
            QMessageBox.warning(self, "ChatList", "Введите текст промта.")
            return

        self.status_label.setText("Отправка запроса (заглушка)...")
        self.temp_results.clear()
        self._clear_results_table()
        self.save_button.setEnabled(False)

        # Заглушка: реальная отправка будет на этапе 7.
        active_models = self.service.get_active_models()
        if not active_models:
            self.status_label.setText("Нет активных моделей. Настройте их на вкладке «Модели».")
            QMessageBox.information(
                self,
                "ChatList",
                "Нет активных моделей.\n"
                "Активируйте модели на вкладке «Модели» (этап 10).",
            )
            return

        for model in active_models:
            self.temp_results.append(
                TempResult(
                    model_id=model.id,
                    model_name=model.name,
                    response_text="[Заглушка] Ответ будет получен на этапе 7",
                    selected=False,
                )
            )

        self._fill_results_table()
        self.save_button.setEnabled(True)
        self.status_label.setText(
            f"Получено заглушек ответов: {len(self.temp_results)} (этап 7 — реальные запросы)"
        )

    def on_save_clicked(self) -> None:
        selected = [item for item in self.temp_results if item.selected]
        if not selected:
            QMessageBox.warning(self, "ChatList", "Выберите хотя бы один результат для сохранения.")
            return

        if self.current_prompt_id is None:
            prompt = self.service.save_prompt(
                self.prompt_edit.toPlainText().strip(),
                tags=self.tags_edit.text().strip() or None,
            )
            self.current_prompt_id = prompt.id
            self._reload_prompt_combo()

        saved = self.service.save_results(self.current_prompt_id, selected)
        self.temp_results.clear()
        self._clear_results_table()
        self.save_button.setEnabled(False)
        self.status_label.setText(f"Сохранено результатов: {len(saved)}")
        QMessageBox.information(self, "ChatList", f"Сохранено результатов: {len(saved)}")

    def _clear_results_table(self) -> None:
        self.results_table.setRowCount(0)

    def _fill_results_table(self) -> None:
        self.results_table.blockSignals(True)
        self.results_table.setRowCount(len(self.temp_results))
        for row, item in enumerate(self.temp_results):
            self.results_table.setItem(row, 0, QTableWidgetItem(item.model_name))
            self.results_table.setItem(row, 1, QTableWidgetItem(item.response_text))

            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            checkbox_item.setCheckState(
                Qt.CheckState.Checked if item.selected else Qt.CheckState.Unchecked
            )
            self.results_table.setItem(row, 2, checkbox_item)
        self.results_table.blockSignals(False)

    def _on_result_checkbox_changed(self, table_item: QTableWidgetItem) -> None:
        if table_item.column() != 2:
            return
        row = table_item.row()
        if row < 0 or row >= len(self.temp_results):
            return
        self.temp_results[row].selected = table_item.checkState() == Qt.CheckState.Checked


def main() -> None:
    load_dotenv(APP_DIR / ".env")

    service = ChatListService()
    db_path = service.initialize()

    app = QApplication(sys.argv)
    window = MainWindow(service)
    window.show()
    window.statusBar().showMessage(f"БД: {db_path}")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
