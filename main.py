import sys

from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ChatList")
        self.resize(400, 300)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        self.label = QLabel("Добро пожаловать в ChatList")
        layout.addWidget(self.label)

        button = QPushButton("Нажми меня")
        button.clicked.connect(self.on_button_clicked)
        layout.addWidget(button)

    def on_button_clicked(self) -> None:
        self.label.setText("Кнопка нажата!")


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
