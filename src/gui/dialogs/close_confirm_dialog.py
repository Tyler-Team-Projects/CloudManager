from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QCheckBox,
    QPushButton, QHBoxLayout, QWidget
)
from PyQt6.QtCore import QSettings


class CloseConfirmDialog(QDialog):
    """Спрашивает, что делать при закрытии окна."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Закрытие приложения")
        self.setMinimumWidth(380)
        self.setModal(True)
        self._settings = QSettings("TeamTyler", "DiscoHack")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        label = QLabel(
            "Что вы хотите сделать?\n"
            "Приложение может быть свёрнуто в системный трей\n"
            "и продолжит работать в фоновом режиме."
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        self.remember_check = QCheckBox("Больше не спрашивать")
        layout.addWidget(self.remember_check)

        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        tray_btn = QPushButton("Свернуть в трей")
        tray_btn.clicked.connect(self._minimize_to_tray)
        exit_btn = QPushButton("Закрыть программу")
        exit_btn.clicked.connect(self._exit_app)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(tray_btn)
        btn_layout.addWidget(exit_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addWidget(btn_widget)

        self._result_action = None  # 'tray' или 'exit'

    def _minimize_to_tray(self):
        self._result_action = 'tray'
        self._save_choice_if_needed()
        self.accept()

    def _exit_app(self):
        self._result_action = 'exit'
        self._save_choice_if_needed()
        self.accept()

    def _save_choice_if_needed(self):
        if self.remember_check.isChecked():
            self._settings.setValue("close_behavior", self._result_action)

    def chosen_action(self) -> str | None:
        """Возвращает 'tray', 'exit' или None."""
        return self._result_action