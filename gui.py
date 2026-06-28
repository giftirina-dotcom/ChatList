"""Графический интерфейс ChatList."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFontMetrics
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from export_utils import export_to_json, export_to_markdown
from models import ChatListService, Model, TempResult
from network import format_error_for_user
from workers import SendPromptWorker

OPENROUTER_AUTH_HINT = (
    "Проверьте файл .env в каталоге программы:\n"
    "OPENROUTER_API_KEY=sk-or-v1-ваш_ключ\n\n"
    "Ключ берётся на https://openrouter.ai/keys"
)

MODEL_TYPES = ["openrouter"]
RESPONSE_MIN_LINES = 5
NUMBER_COLUMN = 0
CHECKBOX_COLUMN = 1
MODEL_COLUMN = 2
RESPONSE_COLUMN = 3
RESPONSE_HIGHLIGHT = QColor(255, 248, 180)


def _truncate(text: str, limit: int = 80) -> str:
    one_line = text.replace("\n", " ")
    return one_line if len(one_line) <= limit else one_line[: limit - 3] + "..."


class SearchableTable(QWidget):
    """Таблица с поиском и сортировкой."""

    def __init__(self, columns: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[list[str]] = []
        self._row_ids: list[int | None] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск...")
        self.search_edit.textChanged.connect(self.apply_filter)
        layout.addWidget(self.search_edit)

        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            header.setStretchLastSection(True)
        layout.addWidget(self.table)

    def set_rows(self, rows: list[list[str]], row_ids: list[int | None] | None = None) -> None:
        self._rows = rows
        self._row_ids = row_ids or [None] * len(rows)
        self.apply_filter()

    def apply_filter(self) -> None:
        query = self.search_edit.text().strip().lower()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for row_index, row in enumerate(self._rows):
            if query and not any(query in cell.lower() for cell in row):
                continue
            table_row = self.table.rowCount()
            self.table.insertRow(table_row)
            for col, value in enumerate(row):
                self.table.setItem(table_row, col, QTableWidgetItem(value))
            self.table.item(table_row, 0).setData(Qt.ItemDataRole.UserRole, self._row_ids[row_index])
        self.table.setSortingEnabled(True)

    def selected_row_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None


class ModelDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        model: Model | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Модель" if model is None else "Редактирование модели")
        self.setMinimumWidth(480)

        form = QFormLayout(self)
        self.name_edit = QLineEdit(model.name if model else "")
        self.url_edit = QLineEdit(model.api_url if model else "")
        self.api_id_edit = QLineEdit(model.api_id if model else "")
        self.key_env_edit = QLineEdit(model.api_key_env if model else "OPENROUTER_API_KEY")
        self.type_combo = QComboBox()
        self.type_combo.addItems(MODEL_TYPES)
        if model and model.model_type:
            index = self.type_combo.findText(model.model_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
        self.active_check = QCheckBox("Активна")
        self.active_check.setChecked(model.is_active if model else True)

        form.addRow("Имя:", self.name_edit)
        form.addRow("API URL:", self.url_edit)
        form.addRow("API ID:", self.api_id_edit)
        form.addRow("Переменная .env:", self.key_env_edit)
        form.addRow("Тип API:", self.type_combo)
        form.addRow("", self.active_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def get_data(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "api_url": self.url_edit.text().strip(),
            "api_id": self.api_id_edit.text().strip(),
            "api_key_env": self.key_env_edit.text().strip(),
            "model_type": self.type_combo.currentText(),
            "is_active": self.active_check.isChecked(),
        }


class ResponseViewerDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        model_name: str,
        response_text: str,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Ответ — {model_name}")
        self.resize(760, 560)

        layout = QVBoxLayout(self)
        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setMarkdown(response_text)
        layout.addWidget(viewer)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.accept)
        layout.addWidget(buttons)


class RequestTab(QWidget):
    use_prompt = pyqtSignal(int)
    results_saved = pyqtSignal()

    def __init__(self, service: ChatListService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.current_prompt_id: int | None = None
        self.temp_results: list[TempResult] = []
        self._worker: SendPromptWorker | None = None
        self._loading = False
        self._highlighted_response_row: int | None = None

        layout = QVBoxLayout(self)

        prompt_row = QHBoxLayout()
        prompt_row.addWidget(QLabel("Сохранённый промт:"))
        self.prompt_combo = QComboBox()
        self.prompt_combo.addItem("— новый промт —", None)
        self.prompt_combo.currentIndexChanged.connect(self.on_prompt_selected)
        prompt_row.addWidget(self.prompt_combo, stretch=1)
        layout.addLayout(prompt_row)

        splitter = QSplitter(Qt.Orientation.Vertical)

        prompt_panel = QWidget()
        prompt_panel_layout = QVBoxLayout(prompt_panel)
        prompt_panel_layout.setContentsMargins(0, 0, 0, 0)
        prompt_panel_layout.addWidget(QLabel("Промт:"))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Введите текст запроса...")
        self.prompt_edit.setMinimumHeight(60)
        self.prompt_edit.textChanged.connect(self.on_prompt_text_changed)
        prompt_panel_layout.addWidget(self.prompt_edit)

        tags_row = QHBoxLayout()
        tags_row.addWidget(QLabel("Теги:"))
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("python, test")
        tags_row.addWidget(self.tags_edit, stretch=1)
        prompt_panel_layout.addLayout(tags_row)

        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.on_send_clicked)
        prompt_panel_layout.addWidget(self.send_button)

        results_panel = QWidget()
        results_panel_layout = QVBoxLayout(results_panel)
        results_panel_layout.setContentsMargins(0, 0, 0, 0)
        results_panel_layout.addWidget(QLabel("Результаты:"))
        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["№", "Выбрать", "Модель", "Ответ"])
        header = self.results_table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(NUMBER_COLUMN, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(CHECKBOX_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(MODEL_COLUMN, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(RESPONSE_COLUMN, QHeaderView.ResizeMode.Stretch)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setWordWrap(True)
        self.results_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        vheader = self.results_table.verticalHeader()
        if vheader is not None:
            vheader.setVisible(False)
        self.results_table.itemChanged.connect(self._on_result_checkbox_changed)
        self.results_table.cellClicked.connect(self._on_results_cell_clicked)
        results_panel_layout.addWidget(self.results_table)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        results_panel_layout.addWidget(self.progress)

        buttons_row = QHBoxLayout()
        self.open_button = QPushButton("Открыть")
        self.open_button.clicked.connect(self.open_selected_response)
        self.open_button.setEnabled(False)
        buttons_row.addWidget(self.open_button)

        self.save_button = QPushButton("Сохранить")
        self.save_button.clicked.connect(self.on_save_clicked)
        self.save_button.setEnabled(False)
        buttons_row.addWidget(self.save_button)

        self.export_md_button = QPushButton("Экспорт MD")
        self.export_md_button.clicked.connect(lambda: self.export_results("md"))
        self.export_md_button.setEnabled(False)
        buttons_row.addWidget(self.export_md_button)

        self.export_json_button = QPushButton("Экспорт JSON")
        self.export_json_button.clicked.connect(lambda: self.export_results("json"))
        self.export_json_button.setEnabled(False)
        buttons_row.addWidget(self.export_json_button)
        buttons_row.addStretch()
        results_panel_layout.addLayout(buttons_row)

        prompt_panel.setMinimumHeight(100)
        results_panel.setMinimumHeight(120)
        splitter.addWidget(prompt_panel)
        splitter.addWidget(results_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([220, 380])
        layout.addWidget(splitter, stretch=1)

        self.status_label = QLabel("Готово")
        layout.addWidget(self.status_label)

        self.reload_prompt_combo()

    def reload_prompt_combo(self, select_id: int | None = None) -> None:
        self.prompt_combo.blockSignals(True)
        self.prompt_combo.clear()
        self.prompt_combo.addItem("— новый промт —", None)
        for prompt in self.service.list_prompts():
            self.prompt_combo.addItem(_truncate(prompt.prompt, 60), prompt.id)
        target = select_id if select_id is not None else self.current_prompt_id
        index = self.prompt_combo.findData(target)
        self.prompt_combo.setCurrentIndex(index if index >= 0 else 0)
        self.prompt_combo.blockSignals(False)

    def load_prompt(self, prompt_id: int) -> None:
        prompt = self.service.get_prompt(prompt_id)
        if prompt is None:
            return
        self.prompt_combo.blockSignals(True)
        index = self.prompt_combo.findData(prompt_id)
        if index >= 0:
            self.prompt_combo.setCurrentIndex(index)
        self.prompt_combo.blockSignals(False)
        self.prompt_edit.blockSignals(True)
        self.prompt_edit.setPlainText(prompt.prompt)
        self.tags_edit.setText(prompt.tags or "")
        self.prompt_edit.blockSignals(False)
        self.current_prompt_id = prompt.id
        self.clear_temp_results()
        self.status_label.setText(f"Загружен промт #{prompt.id}")

    def on_prompt_selected(self, index: int) -> None:
        if index <= 0:
            self.current_prompt_id = None
            return
        prompt_id = self.prompt_combo.itemData(index)
        if prompt_id is None:
            return
        self.load_prompt(int(prompt_id))

    def on_prompt_text_changed(self) -> None:
        if self._loading:
            return
        self.clear_temp_results()

    def clear_temp_results(self) -> None:
        self.temp_results.clear()
        self._highlighted_response_row = None
        self.results_table.blockSignals(True)
        self.results_table.setRowCount(0)
        self.results_table.blockSignals(False)
        self.save_button.setEnabled(False)
        self.export_md_button.setEnabled(False)
        self.export_json_button.setEnabled(False)
        self.open_button.setEnabled(False)

    def _ensure_prompt_saved(self) -> int:
        text = self.prompt_edit.toPlainText().strip()
        tags = self.tags_edit.text().strip() or None
        if self.current_prompt_id is not None:
            existing = self.service.get_prompt(self.current_prompt_id)
            if existing and existing.prompt == text and (existing.tags or "") == (tags or ""):
                return self.current_prompt_id
        prompt = self.service.save_prompt(text, tags)
        self.current_prompt_id = prompt.id
        self.reload_prompt_combo(select_id=prompt.id)
        return prompt.id

    def on_send_clicked(self) -> None:
        prompt_text = self.prompt_edit.toPlainText().strip()
        if not prompt_text:
            QMessageBox.warning(self, "ChatList", "Введите текст промта.")
            return

        active_models = self.service.get_active_models()
        if not active_models:
            QMessageBox.information(
                self,
                "ChatList",
                "Нет активных моделей.\nАктивируйте модели на вкладке «Модели».",
            )
            return

        if not self.service.has_usable_openrouter_key():
            QMessageBox.warning(self, "ChatList — API-ключ", OPENROUTER_AUTH_HINT)
            return

        self._ensure_prompt_saved()
        self.clear_temp_results()
        self._set_loading(True)
        self.status_label.setText("Отправка запросов...")

        self._worker = SendPromptWorker(self.service, prompt_text)
        self._worker.finished.connect(self._on_send_finished)
        self._worker.failed.connect(self._on_send_failed)
        self._worker.start()

    def _on_send_finished(self, responses: list) -> None:
        self._set_loading(False)
        self.temp_results = [response.to_temp_result() for response in responses]
        self._fill_results_table()
        self.save_button.setEnabled(bool(self.temp_results))
        self.export_md_button.setEnabled(bool(self.temp_results))
        self.export_json_button.setEnabled(bool(self.temp_results))
        self.open_button.setEnabled(bool(self.temp_results))
        errors = sum(1 for item in self.temp_results if item.error)
        self.status_label.setText(
            f"Получено ответов: {len(self.temp_results)}"
            + (f", ошибок: {errors}" if errors else "")
        )

    def _on_send_failed(self, message: str) -> None:
        self._set_loading(False)
        self.status_label.setText("Ошибка отправки")
        QMessageBox.critical(self, "ChatList", f"Не удалось отправить запрос:\n{message}")

    def _set_loading(self, loading: bool) -> None:
        self._loading = loading
        self.send_button.setEnabled(not loading)
        self.progress.setVisible(loading)

    def on_save_clicked(self) -> None:
        selected = [item for item in self.temp_results if item.selected]
        if not selected:
            QMessageBox.warning(self, "ChatList", "Выберите хотя бы один результат для сохранения.")
            return
        if self.current_prompt_id is None:
            self._ensure_prompt_saved()
        saved = self.service.save_results(self.current_prompt_id, selected)
        self.clear_temp_results()
        self.status_label.setText(f"Сохранено результатов: {len(saved)}")
        self.results_saved.emit()
        QMessageBox.information(self, "ChatList", f"Сохранено результатов: {len(saved)}")

    def export_results(self, fmt: str) -> None:
        items = [item for item in self.temp_results if item.selected] or self.temp_results
        if not items:
            QMessageBox.warning(self, "ChatList", "Нет результатов для экспорта.")
            return
        if fmt == "md":
            path, _ = QFileDialog.getSaveFileName(self, "Экспорт Markdown", "", "Markdown (*.md)")
            if not path:
                return
            export_to_markdown(
                self.service,
                items,
                Path(path),
                self.prompt_edit.toPlainText().strip(),
            )
        else:
            path, _ = QFileDialog.getSaveFileName(self, "Экспорт JSON", "", "JSON (*.json)")
            if not path:
                return
            export_to_json(
                self.service,
                items,
                Path(path),
                self.prompt_edit.toPlainText().strip(),
            )
        QMessageBox.information(self, "ChatList", f"Экспорт выполнен:\n{path}")

    def _clear_response_highlight(self) -> None:
        if self._highlighted_response_row is None:
            return
        item = self.results_table.item(self._highlighted_response_row, RESPONSE_COLUMN)
        if item is not None:
            item.setBackground(QBrush())
        self._highlighted_response_row = None

    def _highlight_response_cell(self, row: int) -> None:
        self._clear_response_highlight()
        item = self.results_table.item(row, RESPONSE_COLUMN)
        if item is None:
            return
        item.setBackground(QBrush(RESPONSE_HIGHLIGHT))
        self._highlighted_response_row = row

    def _on_results_cell_clicked(self, row: int, column: int) -> None:
        if column == RESPONSE_COLUMN:
            self._highlight_response_cell(row)
        else:
            self._clear_response_highlight()

    def _selected_response_row(self) -> int | None:
        if self._highlighted_response_row is not None:
            return self._highlighted_response_row
        row = self.results_table.currentRow()
        return row if row >= 0 else None

    def open_selected_response(self) -> None:
        row = self._selected_response_row()
        if row is None or row >= len(self.temp_results):
            QMessageBox.warning(
                self,
                "ChatList",
                "Выберите ячейку с ответом в таблице результатов.",
            )
            return
        item = self.temp_results[row]
        dialog = ResponseViewerDialog(self, item.model_name, item.response_text)
        dialog.exec()

    def _min_response_row_height(self) -> int:
        metrics = QFontMetrics(self.results_table.font())
        return metrics.lineSpacing() * RESPONSE_MIN_LINES + 12

    def _resize_result_rows(self) -> None:
        min_height = self._min_response_row_height()
        for row in range(self.results_table.rowCount()):
            self.results_table.resizeRowToContents(row)
            if self.results_table.rowHeight(row) < min_height:
                self.results_table.setRowHeight(row, min_height)

    def _update_number_column_width(self) -> None:
        count = max(1, self.results_table.rowCount())
        metrics = QFontMetrics(self.results_table.font())
        width = metrics.horizontalAdvance(str(count)) + 20
        self.results_table.setColumnWidth(NUMBER_COLUMN, max(width, 36))

    def _fill_results_table(self) -> None:
        self._highlighted_response_row = None
        self.results_table.blockSignals(True)
        self.results_table.setRowCount(len(self.temp_results))
        text_top = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        center = Qt.AlignmentFlag.AlignCenter
        for row, item in enumerate(self.temp_results):
            number_item = QTableWidgetItem(str(row + 1))
            number_item.setTextAlignment(center)
            number_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.results_table.setItem(row, NUMBER_COLUMN, number_item)

            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            checkbox_item.setTextAlignment(center)
            checkbox_item.setCheckState(
                Qt.CheckState.Checked if item.selected else Qt.CheckState.Unchecked
            )
            self.results_table.setItem(row, CHECKBOX_COLUMN, checkbox_item)

            name_item = QTableWidgetItem(item.model_name)
            name_item.setTextAlignment(text_top)
            self.results_table.setItem(row, MODEL_COLUMN, name_item)

            display_text = item.response_text
            if item.error:
                display_text = format_error_for_user(item.error)
            response_item = QTableWidgetItem(display_text)
            response_item.setTextAlignment(text_top)
            if item.error:
                response_item.setForeground(QBrush(QColor(160, 40, 40)))
            self.results_table.setItem(row, RESPONSE_COLUMN, response_item)
        self._update_number_column_width()
        self._resize_result_rows()
        self.results_table.blockSignals(False)

    def _on_result_checkbox_changed(self, table_item: QTableWidgetItem) -> None:
        if table_item.column() != CHECKBOX_COLUMN:
            return
        row = table_item.row()
        if row < 0 or row >= len(self.temp_results):
            return
        self.temp_results[row].selected = table_item.checkState() == Qt.CheckState.Checked


class ModelsTab(QWidget):
    def __init__(self, service: ChatListService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service

        layout = QVBoxLayout(self)
        self.table = SearchableTable(
            ["ID", "Имя", "API ID", "Тип", "Переменная .env", "Активна"]
        )
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        add_btn = QPushButton("Добавить")
        add_btn.clicked.connect(self.add_model)
        edit_btn = QPushButton("Изменить")
        edit_btn.clicked.connect(self.edit_model)
        delete_btn = QPushButton("Удалить")
        delete_btn.clicked.connect(self.delete_model)
        toggle_btn = QPushButton("Вкл/Выкл")
        toggle_btn.clicked.connect(self.toggle_active)
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh)
        for btn in (add_btn, edit_btn, delete_btn, toggle_btn, refresh_btn):
            buttons.addWidget(btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.refresh()

    def refresh(self) -> None:
        rows: list[list[str]] = []
        ids: list[int] = []
        for model in self.service.get_all_models():
            rows.append(
                [
                    str(model.id),
                    model.name,
                    model.api_id,
                    model.model_type or "",
                    model.api_key_env,
                    "Да" if model.is_active else "Нет",
                ]
            )
            ids.append(model.id)
        self.table.set_rows(rows, ids)

    def _selected_model(self) -> Model | None:
        model_id = self.table.selected_row_id()
        return self.service.get_model(model_id) if model_id else None

    def add_model(self) -> None:
        dialog = ModelDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        if not all([data["name"], data["api_url"], data["api_id"], data["api_key_env"]]):
            QMessageBox.warning(self, "ChatList", "Заполните все обязательные поля.")
            return
        try:
            self.service.create_model(**data)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "ChatList", f"Не удалось добавить модель:\n{exc}")

    def edit_model(self) -> None:
        model = self._selected_model()
        if model is None:
            QMessageBox.warning(self, "ChatList", "Выберите модель.")
            return
        dialog = ModelDialog(self, model)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        model.name = data["name"]
        model.api_url = data["api_url"]
        model.api_id = data["api_id"]
        model.api_key_env = data["api_key_env"]
        model.model_type = data["model_type"]
        model.is_active = data["is_active"]
        try:
            self.service.update_model(model)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "ChatList", f"Не удалось сохранить модель:\n{exc}")

    def delete_model(self) -> None:
        model = self._selected_model()
        if model is None:
            QMessageBox.warning(self, "ChatList", "Выберите модель.")
            return
        answer = QMessageBox.question(
            self,
            "ChatList",
            f"Удалить модель «{model.name}»?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_model(model.id)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "ChatList", f"Не удалось удалить модель:\n{exc}")

    def toggle_active(self) -> None:
        model = self._selected_model()
        if model is None:
            QMessageBox.warning(self, "ChatList", "Выберите модель.")
            return
        model.is_active = not model.is_active
        self.service.update_model(model)
        self.refresh()


class PromptsTab(QWidget):
    use_prompt = pyqtSignal(int)

    def __init__(self, service: ChatListService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service

        layout = QVBoxLayout(self)
        self.table = SearchableTable(["ID", "Дата", "Промт", "Теги"])
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        use_btn = QPushButton("Использовать")
        use_btn.clicked.connect(self.use_selected)
        delete_btn = QPushButton("Удалить")
        delete_btn.clicked.connect(self.delete_selected)
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh)
        for btn in (use_btn, delete_btn, refresh_btn):
            buttons.addWidget(btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.refresh()

    def refresh(self) -> None:
        rows: list[list[str]] = []
        ids: list[int] = []
        for prompt in self.service.list_prompts():
            rows.append(
                [
                    str(prompt.id),
                    prompt.created_at,
                    _truncate(prompt.prompt, 100),
                    prompt.tags or "",
                ]
            )
            ids.append(prompt.id)
        self.table.set_rows(rows, ids)

    def use_selected(self) -> None:
        prompt_id = self.table.selected_row_id()
        if prompt_id is None:
            QMessageBox.warning(self, "ChatList", "Выберите промт.")
            return
        self.use_prompt.emit(prompt_id)

    def delete_selected(self) -> None:
        prompt_id = self.table.selected_row_id()
        if prompt_id is None:
            QMessageBox.warning(self, "ChatList", "Выберите промт.")
            return
        if QMessageBox.question(self, "ChatList", "Удалить промт?") != QMessageBox.StandardButton.Yes:
            return
        self.service.delete_prompt(prompt_id)
        self.refresh()


class ResultsTab(QWidget):
    def __init__(self, service: ChatListService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service

        layout = QVBoxLayout(self)
        self.table = SearchableTable(["ID", "Дата", "Модель", "Промт", "Ответ"])
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        export_md = QPushButton("Экспорт MD")
        export_md.clicked.connect(lambda: self.export("md"))
        export_json = QPushButton("Экспорт JSON")
        export_json.clicked.connect(lambda: self.export("json"))
        delete_btn = QPushButton("Удалить")
        delete_btn.clicked.connect(self.delete_selected)
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh)
        for btn in (export_md, export_json, delete_btn, refresh_btn):
            buttons.addWidget(btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.refresh()

    def refresh(self) -> None:
        rows: list[list[str]] = []
        ids: list[int] = []
        for row in self.service.get_result_rows():
            rows.append(
                [
                    str(row["id"]),
                    row["created_at"],
                    row["model_name"],
                    _truncate(row["prompt"], 60),
                    _truncate(row["response_text"], 100),
                ]
            )
            ids.append(row["id"])
        self.table.set_rows(rows, ids)

    def _selected_result(self):
        result_id = self.table.selected_row_id()
        if result_id is None:
            return None
        for result in self.service.list_results():
            if result.id == result_id:
                return result
        return None

    def delete_selected(self) -> None:
        result = self._selected_result()
        if result is None:
            QMessageBox.warning(self, "ChatList", "Выберите результат.")
            return
        if QMessageBox.question(self, "ChatList", "Удалить результат?") != QMessageBox.StandardButton.Yes:
            return
        self.service.delete_result(result.id)
        self.refresh()

    def export(self, fmt: str) -> None:
        result = self._selected_result()
        items = [result] if result else [r for r in self.service.list_results()]
        if not items:
            QMessageBox.warning(self, "ChatList", "Нет результатов для экспорта.")
            return
        if fmt == "md":
            path, _ = QFileDialog.getSaveFileName(self, "Экспорт Markdown", "", "Markdown (*.md)")
            if not path:
                return
            export_to_markdown(self.service, items, Path(path))
        else:
            path, _ = QFileDialog.getSaveFileName(self, "Экспорт JSON", "", "JSON (*.json)")
            if not path:
                return
            export_to_json(self.service, items, Path(path))
        QMessageBox.information(self, "ChatList", f"Экспорт выполнен:\n{path}")


class SettingsTab(QWidget):
    settings_saved = pyqtSignal()

    def __init__(self, service: ChatListService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 600)
        self.timeout_spin.setValue(self.service.get_request_timeout())
        form.addRow("Таймаут запроса (сек):", self.timeout_spin)

        self.db_path_edit = QLineEdit(self.service.get_setting("db_path", "chatlist.db") or "")
        self.db_path_edit.setReadOnly(True)
        form.addRow("Файл БД:", self.db_path_edit)

        self.log_check = QCheckBox("Логировать запросы в logs/requests.log")
        self.log_check.setChecked(self.service.is_log_requests_enabled())
        form.addRow("", self.log_check)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Системная", "Fusion", "Windows"])
        theme = self.service.get_setting("theme", "Системная") or "Системная"
        index = self.theme_combo.findText(theme)
        self.theme_combo.setCurrentIndex(index if index >= 0 else 0)
        form.addRow("Тема:", self.theme_combo)

        layout.addLayout(form)

        save_btn = QPushButton("Сохранить настройки")
        save_btn.clicked.connect(self.save)
        layout.addWidget(save_btn)
        layout.addStretch()

    def save(self) -> None:
        self.service.set_setting("request_timeout", str(self.timeout_spin.value()))
        self.service.set_setting("log_requests", "1" if self.log_check.isChecked() else "0")
        self.service.set_setting("theme", self.theme_combo.currentText())
        self.settings_saved.emit()
        QMessageBox.information(self, "ChatList", "Настройки сохранены.")


class MainWindow(QMainWindow):
    def __init__(self, service: ChatListService, db_path: Path, env_path: Path | None = None) -> None:
        super().__init__()
        self.service = service
        self.db_path = db_path
        self.env_path = env_path

        self.setWindowTitle("ChatList")
        self.resize(1000, 700)

        tabs = QTabWidget()
        self.request_tab = RequestTab(service)
        self.models_tab = ModelsTab(service)
        self.prompts_tab = PromptsTab(service)
        self.results_tab = ResultsTab(service)
        self.settings_tab = SettingsTab(service)

        tabs.addTab(self.request_tab, "Запрос")
        tabs.addTab(self.models_tab, "Модели")
        tabs.addTab(self.prompts_tab, "Промты")
        tabs.addTab(self.results_tab, "Результаты")
        tabs.addTab(self.settings_tab, "Настройки")
        self.setCentralWidget(tabs)

        self.prompts_tab.use_prompt.connect(self._use_prompt)
        self.request_tab.results_saved.connect(self.results_tab.refresh)
        self.settings_tab.settings_saved.connect(self._apply_theme)

        self._apply_theme()
        env_info = f"БД: {db_path}"
        if env_path is not None:
            env_info += f" | .env: {env_path}"
        self.statusBar().showMessage(env_info)
        self._warn_if_missing_api_key()

    def _warn_if_missing_api_key(self) -> None:
        if self.service.get_active_models() and not self.service.has_usable_openrouter_key():
            QMessageBox.warning(
                self,
                "ChatList — API-ключ",
                "Не найден действующий OPENROUTER_API_KEY в .env.\n\n"
                + OPENROUTER_AUTH_HINT,
            )

    def _use_prompt(self, prompt_id: int) -> None:
        self.request_tab.load_prompt(prompt_id)
        if self.centralWidget() and isinstance(self.centralWidget(), QTabWidget):
            self.centralWidget().setCurrentIndex(0)

    def _apply_theme(self) -> None:
        theme = self.service.get_setting("theme", "Системная") or "Системная"
        app = QApplication.instance()
        if app is None or not isinstance(app, QApplication):
            return
        if theme == "Fusion":
            app.setStyle("Fusion")
        elif theme == "Windows":
            app.setStyle("windowsvista")
        else:
            app.setStyle("")

    def refresh_all(self) -> None:
        self.request_tab.reload_prompt_combo()
        self.models_tab.refresh()
        self.prompts_tab.refresh()
        self.results_tab.refresh()

