"""Полноценное окно настроек с вкладками."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QCheckBox, QPushButton,
    QHBoxLayout, QWidget, QGroupBox, QRadioButton,
    QTabWidget, QLabel
)
from PyQt6.QtCore import QSettings
from core.autostart import enable_autostart, disable_autostart

class SettingsDialog(QDialog):
    """Окно настроек с вкладками."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumSize(600, 400)
        self._settings = QSettings("TeamTyler", "DiscoHack")

        main_layout = QVBoxLayout(self)

        # Вкладки
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Вкладка "Общие"
        self._setup_general_tab()
        # Вкладка "Пользовательские" (заглушка)
        self._setup_user_tab()
        # Вкладка "Уведомления" (заглушка)
        self._setup_notifications_tab()

        # Кнопки ОК/Отмена
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
        main_layout.addWidget(btn_widget)

    def _setup_general_tab(self):
        """Наполнение вкладки 'Общие'."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Уведомления
        self.notify_check = QCheckBox("Показывать уведомления о завершении операций")
        current_notify = self._settings.value("show_notifications", True, type=bool)
        self.notify_check.setChecked(current_notify)
        layout.addWidget(self.notify_check)

        # Поведение при закрытии окна
        group_box = QGroupBox("При закрытии окна")
        group_layout = QVBoxLayout(group_box)

        self.autostart_check = QCheckBox("Запускать вместе с системой")
        current_autostart = self._settings.value("autostart", False, type=bool)
        self.autostart_check.setChecked(current_autostart)
        layout.addWidget(self.autostart_check)

        self.tray_radio = QRadioButton("Сворачивать в системный трей")
        self.exit_radio = QRadioButton("Полностью закрывать приложение")

        current_behavior = self._settings.value("close_behavior", "ask")
        if current_behavior == "tray":
            self.tray_radio.setChecked(True)
        elif current_behavior == "exit":
            self.exit_radio.setChecked(True)

        group_layout.addWidget(self.tray_radio)
        group_layout.addWidget(self.exit_radio)
        layout.addWidget(group_box)

        layout.addStretch()
        self.tabs.addTab(tab, "Общие")

    def _setup_user_tab(self):
        """Вкладка 'Пользовательские' – заглушка."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        label = QLabel("Здесь пока ничего нет.")
        label.setStyleSheet("color: #757575;")
        layout.addWidget(label)
        layout.addStretch()
        self.tabs.addTab(tab, "Пользовательские")

    def _setup_notifications_tab(self):
        """Вкладка 'Уведомления' – заглушка."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        label = QLabel("Настройки уведомлений появятся позже.")
        label.setStyleSheet("color: #757575;")
        layout.addWidget(label)
        layout.addStretch()
        self.tabs.addTab(tab, "Уведомления")

    def _save_and_close(self):
        """Сохранить настройки и закрыть."""
        self._settings.setValue("show_notifications", self.notify_check.isChecked())

        if self.tray_radio.isChecked():
            self._settings.setValue("close_behavior", "tray")
        elif self.exit_radio.isChecked():
            self._settings.setValue("close_behavior", "exit")
        else:
            self._settings.setValue("close_behavior", "ask")

        self._settings.setValue("autostart", self.autostart_check.isChecked())
        if self.autostart_check.isChecked():
            enable_autostart()
        else:
            disable_autostart()
        self.accept()