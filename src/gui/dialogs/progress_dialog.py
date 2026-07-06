"""Диалог с прогресс-баром для длительных операций."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar,
    QPushButton, QHBoxLayout, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal


class ProgressDialog(QDialog):
    """Диалог отображения прогресса операции."""

    cancelled = pyqtSignal()

    def __init__(
            self,
            title: str = "Выполнение операции",
            parent: QWidget | None = None
    ) -> None:
        """Инициализация диалога."""
        super().__init__(parent)
        self._title = title
        self._is_cancellable = True
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Настройка UI."""
        self.setWindowTitle(self._title)
        self.setMinimumWidth(500)
        self.setMinimumHeight(250)
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Основная информация
        self.status_label = QLabel("Подготовка...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet("color: #757575; font-size: 11px;")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        layout.addStretch()

        # Кнопки
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)

        button_layout.addStretch()

        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.cancel_button)

        self.close_button = QPushButton("Закрыть")
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)

        layout.addWidget(button_widget)

    def set_status(self, text: str, detail: str = "") -> None:
        """Обновление статуса операции."""
        self.status_label.setText(text)
        if detail:
            self.detail_label.setText(detail)

    def set_progress(self, value: int, maximum: int = 100) -> None:
        """Обновление прогресса."""
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)

    def set_cancellable(self, enabled: bool) -> None:
        """Управление возможностью отмены."""
        self._is_cancellable = enabled
        self.cancel_button.setEnabled(enabled)

    def operation_finished(self, success: bool = True) -> None:
        """Завершение операции."""
        self.cancel_button.setEnabled(False)
        self.close_button.setEnabled(True)
        self.close_button.setFocus()

        if success:
            self.status_label.setText("Операция успешно завершена")
            self.progress_bar.setValue(100)
        else:
            self.status_label.setText("Операция прервана")

    def _on_cancel(self) -> None:
        """Обработка нажатия кнопки отмены."""
        if self._is_cancellable:
            self.cancel_button.setEnabled(False)
            self.status_label.setText("Отмена операции...")
            self.cancelled.emit()
