"""Диалог настроек приложения."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QCheckBox, QPushButton,
    QHBoxLayout, QLabel, QWidget
)
from PyQt6.QtCore import QSettings


class SettingsDialog(QDialog):
    """Окно настроек."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(350)
        self._settings = QSettings("TeamTyler", "CloudManager")

        layout = QVBoxLayout(self)

        # Уведомления
        self.notify_check = QCheckBox("Показывать уведомления о завершении операций")
        # Загружаем сохранённое значение (по умолчанию True)
        current = self._settings.value("show_notifications", True, type=bool)
        self.notify_check.setChecked(current)
        layout.addWidget(self.notify_check)

        layout.addStretch()

        # Кнопки
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._save_and_close)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addWidget(btn_widget)

    def _save_and_close(self):
        """Сохранить настройки и закрыть."""
        self._settings.setValue("show_notifications", self.notify_check.isChecked())
        self.accept()