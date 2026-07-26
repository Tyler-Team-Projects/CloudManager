"""Точка входа в приложение."""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from gui.main_window import MainWindow

#тест
def main() -> None:
    """Запуск приложения."""

    app = QApplication(sys.argv)

    font = app.font()
    font.setPointSize(14)
    app.setFont(font)
    app.setApplicationName("Cloud Manager")
    app.setOrganizationName("Hackathon Team")

    window = MainWindow()
    if not window._start_minimized:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()