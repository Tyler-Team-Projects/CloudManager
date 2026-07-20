"""Диалог управления публичной ссылкой."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QHBoxLayout, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication


class PublicLinkDialog(QDialog):
    def __init__(self, url: str | None, delete_callback, parent=None):
        super().__init__(parent)
        self.url = url
        self.delete_callback = delete_callback
        self.setWindowTitle("Публичная ссылка")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        if self.url:
            label = QLabel("Ссылка на файл/папку:")
            self.url_edit = QLineEdit(self.url)
            self.url_edit.setReadOnly(True)
            layout.addWidget(label)
            layout.addWidget(self.url_edit)

            buttons_layout = QHBoxLayout()
            copy_btn = QPushButton("Копировать в буфер")
            copy_btn.clicked.connect(self._copy_to_clipboard)
            open_btn = QPushButton("Открыть в браузере")
            open_btn.clicked.connect(self._open_in_browser)
            delete_btn = QPushButton("Удалить публичную ссылку")
            delete_btn.clicked.connect(self._delete_link)
            close_btn = QPushButton("Закрыть")
            close_btn.clicked.connect(self.accept)

            buttons_layout.addWidget(copy_btn)
            buttons_layout.addWidget(open_btn)
            buttons_layout.addWidget(delete_btn)
            buttons_layout.addWidget(close_btn)
            layout.addLayout(buttons_layout)
        else:
            error_label = QLabel("Не удалось получить публичную ссылку.\n"
                                 "Возможно, файл ещё не загружен или отсутствует доступ.")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)
            close_btn = QPushButton("Закрыть")
            close_btn.clicked.connect(self.reject)
            layout.addWidget(close_btn)

    def _copy_to_clipboard(self):
        QApplication.clipboard().setText(self.url)
        QMessageBox.information(self, "Готово", "Ссылка скопирована в буфер обмена.")

    def _open_in_browser(self):
        QDesktopServices.openUrl(QUrl(self.url))

    def _delete_link(self):
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Удалить публичную ссылку? Файл останется в облаке, но станет недоступен по этой ссылке.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            success = self.delete_callback()
            if success:
                QMessageBox.information(self, "Успех", "Публичная ссылка удалена.")
                self.accept()
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось удалить публичную ссылку.")