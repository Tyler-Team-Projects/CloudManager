"""Полноценное окно настроек с вкладками."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QCheckBox, QPushButton,
    QHBoxLayout, QWidget, QGroupBox, QRadioButton,
    QTabWidget, QLabel, QLineEdit, QSpinBox, QFileDialog
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

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self._setup_general_tab()
        self._setup_interface_tab()
        self._setup_sync_tab()

        # Кнопки ОК/Отмена
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addStretch()

        reset_btn = QPushButton("Восстановить умолчания")
        reset_btn.clicked.connect(self._reset_to_defaults)
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._save_and_close)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)


        btn_layout.addWidget(reset_btn)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addWidget(btn_widget)

    def _setup_general_tab(self):
        """Наполнение вкладки 'Общие'."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Уведомления (существующее)
        self.notify_check = QCheckBox("Показывать уведомления о завершении операций")
        self.notify_check.setChecked(self._settings.value("show_notifications", True, type=bool))
        layout.addWidget(self.notify_check)

        # Длительность уведомлений
        toast_label = QLabel("Длительность уведомлений (сек):")
        self.toast_duration_spin = QSpinBox()
        self.toast_duration_spin.setRange(5, 30)
        self.toast_duration_spin.setValue(self._settings.value("toast_duration", 10, type=int))
        layout.addWidget(toast_label)
        layout.addWidget(self.toast_duration_spin)

        # Папка для загрузок
        download_label = QLabel("Папка для скачивания:")
        self.download_path_edit = QLineEdit()
        self.download_path_edit.setReadOnly(True)
        self.download_path_edit.setText(self._settings.value("download_folder", ""))
        browse_btn = QPushButton("Обзор...")
        browse_btn.clicked.connect(self._browse_download_folder)

        dl_layout = QHBoxLayout()
        dl_layout.addWidget(self.download_path_edit)
        dl_layout.addWidget(browse_btn)
        layout.addWidget(download_label)
        layout.addLayout(dl_layout)

        # Поведение при закрытии окна
        group_box = QGroupBox("При закрытии окна")
        group_layout = QVBoxLayout(group_box)

        self.autostart_check = QCheckBox("Запускать вместе с системой")
        current_autostart = self._settings.value("autostart", False, type=bool)
        self.autostart_check.setChecked(current_autostart)
        layout.addWidget(self.autostart_check)

        self.tray_radio = QRadioButton("Сворачивать в системный трей")
        self.exit_radio = QRadioButton("Полностью закрывать приложение")

        behavior = self._settings.value("close_behavior", "ask")
        if behavior == "tray":
            self.tray_radio.setChecked(True)
        elif behavior == "exit":
            self.exit_radio.setChecked(True)

        group_layout.addWidget(self.tray_radio)
        group_layout.addWidget(self.exit_radio)
        layout.addWidget(group_box)

        # Автозапуск
        self.autostart_check = QCheckBox("Запускать вместе с системой")
        self.autostart_check.setChecked(self._settings.value("autostart", False, type=bool))
        layout.addWidget(self.autostart_check)

        layout.addStretch()
        self.tabs.addTab(tab, "Общие")

    def _setup_interface_tab(self):
        """Наполнение вкладки 'Интерфейс'."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Режим отображения по умолчанию
        view_group = QGroupBox("Режим отображения по умолчанию")
        view_layout = QVBoxLayout(view_group)
        self.icons_radio = QRadioButton("Иконки")
        self.table_radio = QRadioButton("Таблица")
        current_view = self._settings.value("default_view_mode", "icons")
        if current_view == "table":
            self.table_radio.setChecked(True)
        else:
            self.icons_radio.setChecked(True)
        view_layout.addWidget(self.icons_radio)
        view_layout.addWidget(self.table_radio)
        layout.addWidget(view_group)

        # Показ скрытых файлов
        self.hidden_files_check = QCheckBox("Показывать скрытые файлы")
        self.hidden_files_check.setChecked(self._settings.value("show_hidden_files", False, type=bool))
        layout.addWidget(self.hidden_files_check)

        layout.addStretch()
        self.tabs.addTab(tab, "Интерфейс")

    def _setup_sync_tab(self):
        """Наполнение вкладки 'Синхронизация'."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Включение синхронизации
        self.sync_enabled_check = QCheckBox("Включить фоновую синхронизацию")
        self.sync_enabled_check.setChecked(self._settings.value("sync_enabled", True, type=bool))
        layout.addWidget(self.sync_enabled_check)

        # Интервал проверки
        interval_label = QLabel("Интервал проверки (сек):")
        self.sync_interval_spin = QSpinBox()
        self.sync_interval_spin.setRange(5, 300)
        self.sync_interval_spin.setValue(self._settings.value("sync_interval", 30, type=int))
        # Доступность зависит от чекбокса
        self.sync_interval_spin.setEnabled(self.sync_enabled_check.isChecked())
        self.sync_enabled_check.toggled.connect(self.sync_interval_spin.setEnabled)

        layout.addWidget(interval_label)
        layout.addWidget(self.sync_interval_spin)

        layout.addStretch()
        self.tabs.addTab(tab, "Синхронизация")

    def _browse_download_folder(self):
        """Диалог выбора папки для загрузок."""
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для загрузок")
        if folder:
            self.download_path_edit.setText(folder)

    def _save_and_close(self):
        """Сохранить все настройки и закрыть."""
        # Общие
        self._settings.setValue("show_notifications", self.notify_check.isChecked())
        self._settings.setValue("toast_duration", self.toast_duration_spin.value())
        self._settings.setValue("download_folder", self.download_path_edit.text())
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

        # Интерфейс
        view_mode = "table" if self.table_radio.isChecked() else "icons"
        self._settings.setValue("default_view_mode", view_mode)
        self._settings.setValue("show_hidden_files", self.hidden_files_check.isChecked())

        # Синхронизация
        self._settings.setValue("sync_enabled", self.sync_enabled_check.isChecked())
        self._settings.setValue("sync_interval", self.sync_interval_spin.value())

        self.accept()

    def _reset_to_defaults(self):
        """Сброс всех настроек к значениям по умолчанию."""
        self._settings.clear()  # удаляем все ключи нашего приложения
        # Принудительно записываем умолчания на диск
        self._settings.sync()
        self.accept()  # закрываем с принятием, чтобы MainWindow применил настройки
