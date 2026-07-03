"""Немодальное уведомление с кнопкой действия."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QApplication
)
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QFont


class ToastNotification(QWidget):
    """Всплывающее окно в правом нижнем углу экрана."""

    def __init__(self, title: str, message: str, button_text: str,
                 callback, parent=None):
        super().__init__(parent)
        self._callback = callback
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Общие стили
        self.setStyleSheet("""
            QWidget#toast {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            QLabel#title {
                font-weight: bold;
                font-size: 13px;
                color: #212121;
            }
            QLabel#message {
                color: #424242;
                font-size: 12px;
            }
            QPushButton#actionBtn {
                background-color: #1976d2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton#actionBtn:hover {
                background-color: #1565c0;
            }
        """)
        self.setObjectName("toast")
        self.setFixedWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("title")
        layout.addWidget(title_label)

        msg_label = QLabel(message)
        msg_label.setObjectName("message")
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        action_btn = QPushButton(button_text)
        action_btn.setObjectName("actionBtn")
        action_btn.clicked.connect(self._on_action)
        btn_layout.addWidget(action_btn)
        layout.addLayout(btn_layout)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.close)
        self._timer.start(10000)

        self.adjustSize()

    def _on_action(self):
        """Нажата кнопка действия."""
        self._timer.stop()
        self.close()
        if self._callback:
            self._callback()

    def show_at_bottom_right(self):
        """Показать в правом нижнем углу экрана."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geom = screen.availableGeometry()
            x = screen_geom.right() - self.width() - 20
            y = screen_geom.bottom() - self.height() - 40
            self.move(QPoint(x, y))
        self.show()