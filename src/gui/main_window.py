"""Главное окно приложения."""
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter,
    QMenuBar, QMenu, QToolBar, QStatusBar, QMessageBox,
    QFileDialog, QSizePolicy, QInputDialog, QLabel, QProgressBar,
    QSystemTrayIcon, QDialog, QApplication
)
from PyQt6.QtCore import Qt, QSize, QTimer, QSettings
from PyQt6.QtGui import (
    QAction, QIcon, QKeySequence, QIcon, QPixmap,
    QColor, QPainter, QFont
)

# Добавляем путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.common.base_provider import BaseCloudProvider
from api.common.models import CloudFile
from api.common.exceptions import CloudError, CloudNotFoundError

from core.local.local_provider import LocalFileSystemProvider
from core.local.cloud_bridge import CloudBridge
from core.local.cloud_provider_adapter import CloudProviderAdapter

from .views.side_bar import SideBar
from .views.file_table import FileTableView
from .views.address_bar import AddressBar
from .workers import ListDirectoryWorker, DownloadWorker, UploadWorker, SearchWorker, DeleteWorker
from .dialogs.progress_dialog import ProgressDialog
from .dialogs.toast import ToastNotification
from .dialogs.close_confirm_dialog import CloseConfirmDialog
from .dialogs.settings_dialog import SettingsDialog


from PyQt6.QtWidgets import QProgressBar, QPushButton
class MainWindow(QMainWindow):
    """Главное окно облачного менеджера."""

    def __init__(self) -> None:
        """Инициализация главного окна."""
        super().__init__()
        self._current_provider: Optional[BaseCloudProvider] = None
        self._current_path: str = ""
        self._providers: Dict[str, BaseCloudProvider] = {}
        self._list_worker: Optional[ListDirectoryWorker] = None
        self._search_mode = False
        self._pre_search_path = ""
        self._clipboard = []
        self._operation_in_progress = False

        self._upload_queue = []
        self._upload_success = 0
        self._upload_total = 0
        self._upload_provider = None
        self._upload_dest_path = ""
        self._download_queue = []
        self._download_success = 0
        self._download_total = 0
        self._cloud_provider = None
        self._download_worker = None
        self._upload_worker = None
        self._delete_queue = []
        self._delete_success = 0
        self._delete_total = 0
        self._delete_provider = None

        self._init_providers()
        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()
        self._load_stylesheet()
        self._update_auth_status()
        self._update_sync_status()
        self._tray_icon = None
        self._setup_tray()


        # Начальная загрузка
        self._navigate_to_provider('local', self._providers['local'].get_mounts_root())

        cloud_provider = self._providers.get('cloud')
        if cloud_provider and hasattr(cloud_provider, '_bridge'):
            if cloud_provider._bridge.has_token() and cloud_provider._bridge._sync_watcher:
                cloud_provider._bridge._sync_watcher.refresh_callback = self._on_sync_refresh
    def _init_providers(self) -> None:
        """Инициализация провайдеров."""
        self._providers['local'] = LocalFileSystemProvider()

        cloud_path = Path.home() / 'YandexDisk'
        cloud_path.mkdir(parents=True, exist_ok=True)
        cloud_bridge = CloudBridge(cloud_path)

        cloud_adapter = CloudProviderAdapter(cloud_bridge)

        # Устанавливаем callback позже, когда UI будет готов
        if cloud_bridge.has_token():
            # Сохраняем callback для later
            self._pending_sync_callback = True

        self._providers['cloud'] = cloud_adapter


    def _setup_ui(self) -> None:
        """Настройка основного UI."""
        self.setWindowTitle("Cloud Manager")
        self.setMinimumSize(1400, 600)
        self.resize(1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        # Левая панель
        self.side_bar = SideBar()
        self.side_bar.setMinimumWidth(240)
        self.side_bar.setMaximumWidth(400)
        splitter.addWidget(self.side_bar)

        # Правая часть (таблица файлов)
        self.file_table = FileTableView()
        splitter.addWidget(self.file_table)

        splitter.setSizes([280, 920])
        main_layout.addWidget(splitter, stretch=1)

        # Передаём провайдеры в боковую панель
        self.side_bar.set_providers(self._providers)

    def _setup_menu(self) -> None:
        """Настройка главного меню."""
        menubar = self.menuBar()

        # Файл
        file_menu = menubar.addMenu("&Файл")

        new_folder_action = QAction(QIcon.fromTheme("folder-new"), "Новая папка", self)
        new_folder_action.setShortcut(QKeySequence.StandardKey.New)
        new_folder_action.triggered.connect(self._on_new_folder)
        file_menu.addAction(new_folder_action)

        file_menu.addSeparator()

        upload_action = QAction(QIcon.fromTheme("document-open"), "Загрузить файлы...", self)
        upload_action.setShortcut(QKeySequence("Ctrl+U"))
        upload_action.triggered.connect(self._on_upload)
        file_menu.addAction(upload_action)

        download_action = QAction(QIcon.fromTheme("document-save"), "Скачать выбранное", self)
        download_action.setShortcut(QKeySequence.StandardKey.Save)
        download_action.triggered.connect(self._on_download)
        file_menu.addAction(download_action)

        file_menu.addSeparator()

        delete_action = QAction(QIcon.fromTheme("edit-delete"), "Удалить", self)
        delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        delete_action.triggered.connect(self._on_delete)
        file_menu.addAction(delete_action)

        file_menu.addSeparator()

        exit_action = QAction("Выход", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self._exit_app)
        file_menu.addAction(exit_action)

        account_menu = menubar.addMenu("&Аккаунт")

        self.login_action = QAction("Войти в Яндекс.Диск", self)
        self.login_action.triggered.connect(self._on_login)
        account_menu.addAction(self.login_action)

        self.logout_action = QAction("Выйти из Яндекс.Диска", self)
        self.logout_action.triggered.connect(self._on_logout)
        self.logout_action.setEnabled(False)
        account_menu.addAction(self.logout_action)

        account_menu.addSeparator()

        # Статус в меню
        self.status_action = QAction("Статус: не авторизован", self)
        self.status_action.setEnabled(False)
        account_menu.addAction(self.status_action)

        # Справка
        help_menu = menubar.addMenu("&Справка")

        about_action = QAction("О программе", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

        # Настройки
        settings_action = QAction("Настройки", self)
        settings_action.triggered.connect(self._on_settings)
        menubar.addAction(settings_action)
    def _setup_tray(self):
        """Настройка системного трея."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self._tray_icon = QSystemTrayIcon(self)

        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor("#1976d2"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "C")
        painter.end()
        self._tray_icon.setIcon(QIcon(pixmap))

        self._tray_icon.setToolTip("Cloud Manager")

        tray_menu = QMenu()
        restore_action = tray_menu.addAction("Открыть приложение")
        restore_action.triggered.connect(self._restore_from_tray)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Выход")
        quit_action.triggered.connect(self._exit_app)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _setup_toolbar(self) -> None:
        """Настройка панели инструментов."""
        self.toolbar = QToolBar("Панель инструментов")
        self.toolbar.setIconSize(QSize(24, 24))
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.addSeparator()

        # Адресная строка
        self.address_bar = AddressBar()
        self.address_bar.setMaximumWidth(600)
        self.toolbar.addWidget(self.address_bar)

        self.toolbar.addSeparator()

        # Растягиваем тулбар
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.toolbar.addWidget(spacer)

        # Операции с файлами
        new_folder_action = QAction(QIcon.fromTheme("folder-new"), "Новая папка", self)
        new_folder_action.triggered.connect(self._on_new_folder)
        self.toolbar.addAction(new_folder_action)

        self.upload_action = QAction(QIcon.fromTheme("document-open"), "Загрузить", self)
        self.upload_action.triggered.connect(self._on_upload)
        self.toolbar.addAction(self.upload_action)

        self.download_action = QAction(QIcon.fromTheme("document-save"), "Скачать", self)
        self.download_action.triggered.connect(self._on_download)
        self.toolbar.addAction(self.download_action)

        self.delete_action = QAction(QIcon.fromTheme("edit-delete"), "Удалить", self)
        self.delete_action.triggered.connect(self._on_delete)
        self.toolbar.addAction(self.delete_action)

        # Кнопка переключения вида
        self.toggle_view_btn = QAction(QIcon.fromTheme("view-list-details"), "Вид таблицей", self)
        self.toggle_view_btn.setCheckable(True)
        self.toggle_view_btn.setChecked(False)
        self.toggle_view_btn.triggered.connect(self._toggle_view)
        self.toolbar.addAction(self.toggle_view_btn)

    def _restore_from_tray(self):
        """Восстановить окно из трея."""
        self.show()
        self.raise_()
        self.activateWindow()
        if self._tray_icon:
            self._tray_icon.hide()

    def _on_tray_activated(self, reason):
        """Обработка активации иконки трея (двойной клик)."""
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick,
                        QSystemTrayIcon.ActivationReason.Trigger,):
            self._restore_from_tray()

    def _exit_app(self):
        """Полный выход из приложения."""
        if self._tray_icon:
            self._tray_icon.hide()
        QApplication.instance().quit()

    def closeEvent(self, event):
        """Обработка закрытия окна (крестик)."""
        settings = QSettings("TeamTyler", "DiscoHack")
        behavior = settings.value("close_behavior", "ask")

        if behavior == "tray":
            if self._tray_icon and QSystemTrayIcon.isSystemTrayAvailable():
                self.hide()
                self._tray_icon.show()
                event.ignore()
                return
            else:
                # Трей недоступен – просто выходим
                self._exit_app()
                event.accept()
                return
        elif behavior == "exit":
            self._exit_app()
            event.accept()
            return
        else:  # 'ask' – показать диалог
            dialog = CloseConfirmDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                action = dialog.chosen_action()
                if action == 'tray':
                    if self._tray_icon and QSystemTrayIcon.isSystemTrayAvailable():
                        self.hide()
                        self._tray_icon.show()
                        event.ignore()
                    else:
                        self._exit_app()
                        event.accept()
                elif action == 'exit':
                    self._exit_app()
                    event.accept()
                else:
                    event.ignore()  # Отмена
            else:
                event.ignore()  # Отмена

    def _on_settings(self):
        """Открыть окно настроек."""
        dlg = SettingsDialog(self)
        dlg.exec()

    def _toggle_view(self, checked):
        """Переключение между таблицей и иконками."""
        if checked:
            # Переключаем на таблицу
            self.file_table.set_view_mode("table")
            self.toggle_view_btn.setIcon(QIcon.fromTheme("view-list-icons"))
            self.toggle_view_btn.setText("Вид иконками")
        else:
            # Переключаем на иконки
            self.file_table.set_view_mode("icons")
            self.toggle_view_btn.setIcon(QIcon.fromTheme("view-list-details"))
            self.toggle_view_btn.setText("Вид таблицей")

    def _setup_statusbar(self) -> None:
        """Настройка статус-бара."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готово")

        # Добавить прогресс-бар в статус-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        self.status_bar.addPermanentWidget(self.progress_bar)

        self.sync_label = QLabel("Синхр: выкл")
        self.sync_label.setStyleSheet("color: #757575; padding: 0 8px;")
        self.status_bar.addPermanentWidget(self.sync_label)

        self.items_label = QLabel("Элементов: 0")
        self.status_bar.addPermanentWidget(self.items_label)

    def _connect_signals(self) -> None:
        """Подключение сигналов."""

        self.side_bar.provider_selected.connect(self._on_provider_selected)
        self.address_bar.search_requested.connect(self._on_search)
        self.address_bar.path_changed.connect(self._on_path_changed)
        self.address_bar.refresh_clicked.connect(self._on_refresh)
        self.address_bar.go_up_clicked.connect(self._on_go_up)
        self.file_table.file_double_clicked.connect(self._on_file_double_clicked)
        self.file_table.delete_requested.connect(self._on_delete)
        self.file_table.download_requested.connect(self._on_files_download)
        self.file_table.update_requested.connect(self._on_files_update)
        self.file_table.rename_requested.connect(self._on_file_rename)
        self.file_table.copy_requested.connect(self._on_copy_files)
        self.file_table.paste_requested.connect(self._on_paste_files)
        self.file_table.sync_check_requested.connect(self._on_sync_check)


    def _load_stylesheet(self) -> None:
        """Загрузка стилей."""
        try:
            style_path = Path(__file__).parent / "resources" / "style.qss"
            if style_path.exists():
                with open(style_path, "r", encoding="utf-8") as f:
                    self.setStyleSheet(f.read())

        except Exception:
            pass

    # ============ Навигация ============

    def _navigate_to_provider(self, provider_key: str, path: str) -> None:
        """Переход к провайдеру и пути."""
        self._current_provider = self._providers.get(provider_key)
        if not self._current_provider:
            return

        self._current_path = path
        self._load_directory(path)

    def _load_directory(self, path: str) -> None:
        """Загрузка содержимого директории."""
        if not self._current_provider:
            return

        self.status_bar.showMessage(f"Загрузка {path}...")

        # Отменяем предыдущий воркер
        if self._list_worker and self._list_worker.isRunning():
            self._list_worker.terminate()
            self._list_worker.wait(2000)

        self._list_worker = ListDirectoryWorker(self._current_provider, path)
        self._list_worker.finished.connect(self._on_directory_loaded)
        self._list_worker.error.connect(self._on_directory_error)
        self._list_worker.start()

    def _on_directory_loaded(self, files: list) -> None:
        """Обработка загрузки директории."""
        # Проверяем и дополняем статусы для файлов
        if self._current_provider == self._providers.get('cloud'):
            cloud_provider = self._current_provider
            if hasattr(cloud_provider, '_bridge'):
                bridge = cloud_provider._bridge
                for file_item in files:
                    if not file_item.is_dir:
                        # Проверяем наличие файла в Downloads
                        local_file = bridge.downloads_path / file_item.name
                        file_item.is_downloaded = local_file.exists()

                        if file_item.is_downloaded:
                            sync_info = bridge.check_file_sync(file_item.path)
                            file_item.is_synced = sync_info.get('is_synced', False)
                        else:
                            file_item.is_synced = False

        self.file_table.set_files(files, self._current_provider)
        self.file_table.set_current_path(self._current_path)
        self.address_bar.set_path(self._current_path)
        self.items_label.setText(f"Элементов: {len(files)}")
        self.status_bar.showMessage(f"Загружено {len(files)} элементов")
        self._update_toolbar_buttons()

    def _update_toolbar_buttons(self) -> None:
        """Обновление состояния кнопок тулбара."""
        is_root = self._current_path == "mounts://"
        is_local = self._is_local_provider()

        # На локальном диске нельзя скачивать и загружать
        if hasattr(self, 'download_action'):
            self.download_action.setEnabled(not is_root and not is_local)

        if hasattr(self, 'upload_action'):
            self.upload_action.setEnabled(not is_root and not is_local)

        if hasattr(self, 'delete_action'):
            self.delete_action.setEnabled(not is_root)

    def _on_directory_error(self, error: str) -> None:
        """Обработка ошибки загрузки."""
        self.status_bar.showMessage(f"Ошибка: {error}")
        self.items_label.setText("Элементов: 0")

    # ============ Обработчики сигналов ============

    def _on_provider_selected(self, provider: BaseCloudProvider, path: str) -> None:
        """Выбор провайдера в боковой панели."""
        self._current_provider = provider
        self._current_path = path
        self.file_table.set_current_path(path)
        self._load_directory(path)
        self._update_toolbar_buttons()
        self._update_menu_buttons()

    def _on_path_changed(self, path: str) -> None:
        """Изменение пути в адресной строке."""
        self._current_path = path
        self.file_table.set_current_path(path)
        self._load_directory(path)
        self._update_toolbar_buttons()

    def _on_refresh(self) -> None:
        """Обновление текущей папки."""
        if self._current_provider and self._current_path:
            self._load_directory(self._current_path)

    def _on_search(self, query: str) -> None:
        """Поиск файлов рекурсивно."""
        if not self._current_provider or not self._current_path:
            return

        if not query:
            self._load_directory(self._current_path)
            return

        # Показываем прогресс-бар
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Бесконечный прогресс
        self.status_bar.showMessage(f"🔍 Поиск '{query}'...")

        # Блокируем кнопку поиска
        self.address_bar.search_btn.setEnabled(False)

        # Запускаем поиск в отдельном потоке
        self._search_worker = SearchWorker(self._current_provider, self._current_path, query)
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()

    def _on_go_up(self) -> None:
        """Переход на уровень выше."""
        if not self._current_provider:
            return

        # Если мы в режиме поиска, выход из него
        if hasattr(self, '_search_mode') and self._search_mode:
            self._search_mode = False
            self._current_path = self._pre_search_path
            self._load_directory(self._current_path)
            self.address_bar.set_path(self._current_path)
            self.status_bar.showMessage(f"Выход из поиска")
            return

        parent_path = None

        if hasattr(self._current_provider, 'get_parent_path'):
            parent_path = self._current_provider.get_parent_path(self._current_path)

        if parent_path and parent_path != self._current_path:
            self._current_path = parent_path
            self._load_directory(parent_path)
            self.address_bar.set_path(parent_path)

    def _on_file_double_clicked(self, file_item: CloudFile) -> None:
        """Двойной клик по файлу/папке."""
        if file_item.is_dir:
            self._current_path = file_item.path
            self._load_directory(file_item.path)
        else:
            self._open_file(file_item)

    def _on_new_folder(self) -> None:
        """Создание новой папки."""
        if not self._current_provider:
            return

        name, ok = QInputDialog.getText(self, "Новая папка", "Имя папки:")
        if ok and name:
            try:
                path = self._current_path.rstrip('/') + '/' + name
                self._current_provider.create_folder(path)
                self._on_refresh()
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось создать папку: {e}")

    def _finish_upload(self) -> None:
        """Завершение процесса загрузки: обновление таблицы и очистка статус-бара."""
        self._on_refresh()
        self.status_bar.clearMessage()

    def _on_upload(self) -> None:
        """Асинхронная загрузка файлов на диск (в облако)."""
        # Наши проверки
        if self._is_local_provider():
            QMessageBox.warning(self, "Ошибка", "Загрузка доступна только в облачной папке")
            return

        if self._current_path == "mounts://":
            QMessageBox.warning(self, "Ошибка", "Загрузка запрещена в корневой директории")
            return

        if not self._current_provider:
            return

        files, _ = QFileDialog.getOpenFileNames(self, "Выберите файлы для загрузки")
        if not files:
            return

        self._operation_in_progress = True
        # Асинхронная загрузка
        self._upload_queue = [Path(f) for f in files]
        self._upload_success = 0
        self._upload_total = len(self._upload_queue)
        self._upload_provider = self._current_provider
        self._upload_dest_path = self._current_path  # Для уведомления

        if self._upload_queue:
            self._upload_dest_path = self._current_path
            self.status_bar.showMessage(f"Загрузка 0 из {self._upload_total}...")
            self._upload_next()

    def _upload_next(self) -> None:
        """Обработка очереди загрузки – запуск следующего файла."""
        if not self._upload_queue:
            self._operation_in_progress = False
            self.status_bar.showMessage(
                f"Загружено {self._upload_success} из {self._upload_total} файлов"
            )
            self._notify_upload_complete()
            QTimer.singleShot(10000, self._finish_upload)
            return

        local_path = self._upload_queue[0]
        file_name = local_path.name
        current = self._upload_success + 1
        remote_path = self._current_path.rstrip('/') + '/' + file_name

        self.status_bar.showMessage(
            f"Загрузка: {file_name} ({current} из {self._upload_total})"
        )
        self._upload_worker = UploadWorker(
            self._upload_provider,
            local_path,
            remote_path
        )
        self._upload_worker.progress.connect(self._on_upload_progress)
        self._upload_worker.finished.connect(self._on_upload_finished)
        self._upload_worker.error.connect(self._on_upload_error)
        self._upload_worker.start()

    def _on_upload_progress(self, current: int, total: int) -> None:
        """Обновление прогресса загрузки."""
        if total > 0:
            current_mb = current / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            percent = int(current / total * 100)
            file_name = self._upload_queue[0].name if self._upload_queue else ""
            self.status_bar.showMessage(
                f"Загрузка: {file_name} - {current_mb:.1f}/{total_mb:.1f} МБ ({percent}%)"
            )
        else:
            current_mb = current / (1024 * 1024)
            file_name = self._upload_queue[0].name if self._upload_queue else ""
            self.status_bar.showMessage(f"Загрузка: {file_name} - {current_mb:.1f} МБ")

    def _on_upload_finished(self, success: bool, remote_path: str) -> None:
        """Файл успешно загружен."""
        if self._upload_queue:
            self._upload_queue.pop(0)
        if success:
            self._upload_success += 1
        self._upload_next()

    def _on_upload_error(self, error: str) -> None:
        """Ошибка загрузки файла."""
        print(f"[ERROR] Upload failed: {error}")
        if self._upload_queue:
            self._upload_queue.pop(0)
        self._upload_next()

    def _on_download(self) -> None:
        """Скачивание выбранных файлов."""
        if self._current_path == "mounts://":
            QMessageBox.warning(self, "Ошибка", "Скачивание запрещено в корневой директории")
            return

        if self._is_local_provider():
            QMessageBox.warning(self, "Ошибка", "Скачивание доступно только в облачной папке")
            return

        selected = self.file_table.get_selected_items()
        if not selected:
            QMessageBox.information(self, "Инфо", "Выберите файлы для скачивания")
            return

        cloud_provider = self._providers.get('cloud')
        if not cloud_provider or not hasattr(cloud_provider, '_bridge'):
            QMessageBox.warning(self, "Ошибка", "Облачный провайдер не доступен")
            return

        self._operation_in_progress = True

        # Очищаем очередь загрузки
        self._upload_queue = []
        self._upload_success = 0
        self._upload_total = 0
        self._upload_provider = None

        self._download_queue = [f for f in selected if not f.is_dir]
        self._download_success = 0
        self._download_total = len(self._download_queue)
        self._cloud_provider = cloud_provider

        if self._download_queue:
            self.status_bar.showMessage(f"Скачивание 0 из {self._download_total}...")
            self._download_next()
        else:
            self.progress_bar.setVisible(False)
            QMessageBox.information(self, "Инфо", "Нет файлов для скачивания")

    def _download_next(self) -> None:
        """Скачивание следующего файла из очереди."""
        if not self._download_queue:
            self._operation_in_progress = False
            self.status_bar.showMessage(f"Скачано {self._download_success} из {self._download_total} файлов")
            self._notify_download_complete()
            QTimer.singleShot(10000, lambda: (self._on_refresh(), self.status_bar.clearMessage()))
            return

        file_item = self._download_queue[0]
        current = self._download_success + 1

        self.status_bar.showMessage(f"Скачивание: {file_item.name} ({current} из {self._download_total})")

        local_path = self._cloud_provider._bridge._get_download_path(file_item.path)

        self._download_worker = DownloadWorker(
            self._cloud_provider,
            file_item.path,
            str(local_path),
            file_item.size
        )
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_worker.error.connect(self._on_download_error)
        self._download_worker.start()

    def _on_download_progress(self, current: int, total: int) -> None:
        """Обновление прогресса."""
        if total > 0:
            current_mb = current / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            percent = int(current / total * 100)
            file_name = self._download_queue[0].name if self._download_queue else ""
            self.status_bar.showMessage(
                f"Скачивание: {file_name} - {current_mb:.1f}/{total_mb:.1f} МБ ({percent}%)"
            )
        else:
            current_mb = current / (1024 * 1024)
            file_name = self._download_queue[0].name if self._download_queue else ""
            self.status_bar.showMessage(f"Скачивание: {file_name} - {current_mb:.1f} МБ")

    def _on_download_finished(self, success: bool, local_path: str, remote_path: str) -> None:
        """Завершение скачивания одного файла."""
        if self._download_queue:
            downloaded_item = self._download_queue.pop(0)

            if success:
                self._download_success += 1
                # Обновляем статус скачанного файла
                cloud_provider = self._providers.get('cloud')
                if cloud_provider and hasattr(cloud_provider, '_bridge'):
                    bridge = cloud_provider._bridge
                    sync_info = bridge.check_file_sync(remote_path)
                    downloaded_item.is_downloaded = True
                    downloaded_item.is_synced = sync_info.get('is_synced', False)

                    # Сохраняем метаданные
                    import os
                    from datetime import datetime
                    if os.path.exists(local_path):
                        bridge.download_metadata[local_path] = {
                            'remote_path': remote_path,
                            'downloaded_at': datetime.now().isoformat(),
                            'size': os.path.getsize(local_path),
                            'name': Path(local_path).name,
                            'remote_hash': sync_info.get('remote_hash'),
                            'local_hash': sync_info.get('local_hash'),
                            'is_synced': sync_info.get('is_synced', False)
                        }
                        bridge._save_metadata()

                    self._update_file_status(remote_path, downloaded_item)

        self._download_next()

    def _update_file_status(self, remote_path: str, updated_item: CloudFile) -> None:
        """Обновить статус конкретного файла в таблице."""
        # Находим файл в текущем списке
        if hasattr(self.file_table, '_current_items'):
            for i, item in enumerate(self.file_table._current_items):
                if item.path == remote_path:
                    # Обновляем статусы
                    item.is_downloaded = updated_item.is_downloaded
                    item.is_synced = updated_item.is_synced
                    # Переустанавливаем файлы в таблице
                    self.file_table.set_files(
                        self.file_table._current_items,
                        self._current_provider
                    )
                    break

    def _on_download_error(self, error: str) -> None:
        """Ошибка скачивания."""
        print(f"[ERROR] Download failed: {error}")
        self._download_next()

    def _on_sync_check(self, items: list) -> None:
        """Проверка синхронизации выбранных файлов."""
        if not items:
            QMessageBox.information(self, "Инфо", "Выберите файлы для проверки")
            return

        cloud_provider = self._providers.get('cloud')
        if not cloud_provider or not hasattr(cloud_provider, '_bridge'):
            QMessageBox.warning(self, "Ошибка", "Облачный провайдер не доступен")
            return

        bridge = cloud_provider._bridge

        # Показываем диалог прогресса
        progress = ProgressDialog("Проверка синхронизации", self)
        progress.set_cancellable(False)
        progress.show()

        try:
            total = len(items)
            synced_count = 0
            outdated_count = 0
            not_downloaded_count = 0

            for i, item in enumerate(items):
                if item.is_dir:
                    continue

                progress.set_progress(i + 1, total)
                progress.set_status(f"Проверка: {item.name}", f"{i + 1} из {total}")

                # Проверяем синхронизацию
                sync_info = bridge.check_file_sync(item.path)

                # Обновляем статус в объекте
                item.is_downloaded = sync_info.get('is_downloaded', False)
                item.is_synced = sync_info.get('is_synced', False)

                if sync_info.get('is_synced', False):
                    synced_count += 1
                elif sync_info.get('is_downloaded', False):
                    outdated_count += 1
                else:
                    not_downloaded_count += 1

            # Обновляем отображение
            self._on_refresh()

            # Показываем результат
            result_msg = (
                f"Проверка завершена:\n"
                f"Синхронизировано: {synced_count}\n"
                f"Требуют обновления: {outdated_count}\n"
                f"Не скачаны: {not_downloaded_count}"
            )

            progress.set_status("Проверка завершена", result_msg)
            progress.operation_finished(True)

            self.status_bar.showMessage(result_msg)

        except Exception as e:
            progress.set_status(f"Ошибка: {str(e)}")
            progress.operation_finished(False)
            QMessageBox.warning(self, "Ошибка", f"Не удалось проверить синхронизацию: {e}")

    def _on_files_update(self, files: list) -> None:
        """Обновление файлов (перезапись локальной копии из облака)."""
        if not files:
            return

        # Проверка: нельзя обновлять в mounts://
        if self._current_path == "mounts://":
            QMessageBox.warning(self, "Ошибка", "Обновление запрещено в корневой директории")
            return

        # Проверка: обновление только в облачной папке
        if self._is_local_provider():
            QMessageBox.warning(self, "Ошибка", "Обновление доступно только в облачной папке")
            return

        cloud_provider = self._providers.get('cloud')
        if not cloud_provider or not hasattr(cloud_provider, '_bridge'):
            QMessageBox.warning(self, "Ошибка", "Облачный провайдер не доступен")
            return

        bridge = cloud_provider._bridge

        # Подтверждение обновления
        names = [f.name for f in files]
        reply = QMessageBox.question(
            self,
            "Подтверждение обновления",
            f"Обновить локальные копии файлов?\n\n{', '.join(names[:5])}"
            + (f"\n... и ещё {len(names) - 5}" if len(names) > 5 else ""),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Показываем прогресс
        progress = ProgressDialog("Обновление файлов", self)
        progress.set_cancellable(False)
        progress.show()

        success_count = 0
        for i, file_item in enumerate(files):
            progress.set_status(
                f"Обновление: {file_item.name}",
                f"{i + 1} из {len(files)}"
            )

            try:
                # Скачиваем с перезаписью
                local_path = bridge.downloads_path / file_item.name
                success = bridge.download_file(
                    file_item.path,
                    local_path,
                    force_overwrite=True  # ← КЛЮЧЕВОЙ ПАРАМЕТР!
                )

                if success:
                    # Обновляем статус
                    sync_info = bridge.check_file_sync(file_item.path)
                    file_item.is_downloaded = True
                    file_item.is_synced = sync_info.get('is_synced', False)
                    success_count += 1

            except Exception as e:
                print(f"Ошибка обновления {file_item.name}: {e}")
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    f"Не удалось обновить {file_item.name}: {e}"
                )

        progress.operation_finished(True)
        self.status_bar.showMessage(f"Обновлено {success_count} из {len(files)} файлов")

        # Обновляем список
        self._on_refresh()

    def _on_files_download(self, files: list) -> None:
        """Скачивание файлов через сигнал."""
        self._on_download()

    def _on_delete(self, items=None) -> None:
        """Асинхронное удаление выбранных файлов."""
        # Если items не передан (кнопка тулбара / Del), берём выделенные
        self._operation_in_progress = True
        if items is None or isinstance(items, bool):
            if self._current_path == "mounts://":
                QMessageBox.warning(self, "Ошибка", "Удаление запрещено в корневой директории")
                return
            items = self.file_table.get_selected_items()
        # Если передан список – используем его
        elif isinstance(items, list):
            pass
        else:
            # Пришёл bool или другой тип – игнорируем (защита от сигнала QAction)
            return

        if not items:
            return

        # Защита от удаления системных элементов
        for item in items:
            if item.path == "mounts://" or item.name in ["Домашняя папка", "Корень (/)", "/home"]:
                QMessageBox.warning(self, "Ошибка", f"Нельзя удалить системный элемент: {item.name}")
                return

        names = [f.name for f in items]
        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Удалить выбранные элементы?\n\n{', '.join(names[:5])}"
            + (f"\n... и ещё {len(names) - 5}" if len(names) > 5 else ""),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._delete_queue = items.copy()
        self._delete_success = 0
        self._delete_total = len(items)
        self._delete_provider = self._current_provider
        self._delete_next()

    def _delete_next(self) -> None:
        """Запуск удаления следующего файла из очереди."""
        if not self._delete_queue:
            self._operation_in_progress = False
            # Сразу обновляем таблицу
            self._on_refresh()
            # Показываем итог в статус-баре
            QTimer.singleShot(
               750,
                lambda: self.status_bar.showMessage(
                    f"Удалено {self._delete_success} из {self._delete_total} элементов"
                )
            )
            # Через 10 секунд очищаем статус-бар
            QTimer.singleShot(10000, self.status_bar.clearMessage)
            return

        file_item = self._delete_queue.pop(0)
        self._delete_worker = DeleteWorker(self._delete_provider, file_item.path)
        self._delete_worker.finished.connect(self._on_delete_finished)
        self._delete_worker.error.connect(self._on_delete_error)
        self._delete_worker.start()

    def _on_delete_finished(self, success: bool, path: str) -> None:
        """Обработка успешного удаления одного файла."""
        if success:
            self._delete_success += 1
        self._delete_next()

    def _on_delete_error(self, error: str, path: str) -> None:
        """Ошибка удаления файла."""
        print(f"[ERROR] Delete failed for {path}: {error}")
        self._delete_next()

    def _open_file(self, file_item: CloudFile) -> None:
        """Открытие файла."""
        if hasattr(self._current_provider, 'open_file'):
            success = self._current_provider.open_file(file_item.path)
            if not success:
                QMessageBox.warning(self, "Ошибка", f"Не удалось открыть {file_item.name}")
        else:
            QMessageBox.information(self, "Инфо", f"Открытие: {file_item.name}")

    def _on_about(self) -> None:
        """О программе."""
        QMessageBox.about(
            self,
            "О программе",
            "Cloud Manager\n\n"
            "Нативный клиент для облачных хранилищ\n"
            "Предполагаемая система использования ALT Linux\n\n"
            "Версия 0.1"
        )

    def _on_search_finished(self, results: list) -> None:
        """Обработка завершения поиска."""
        self.progress_bar.setVisible(False)
        self.address_bar.search_btn.setEnabled(True)

        if results:
            # Сохраняем исходный путь для кнопки "вверх"
            self._search_mode = True
            self._search_results = results
            self._pre_search_path = self._current_path  # Запоминаем путь до поиска

            self.file_table.set_files(results, self._current_provider)
            self.items_label.setText(f"Найдено: {len(results)}")
            self.status_bar.showMessage(f"Найдено {len(results)} элементов")
            self.address_bar.set_path(f"Результаты поиска ({len(results)})")

            # Кнопка "вверх" должна возвращать к папке, где был поиск
            self.address_bar.up_btn.setEnabled(True)
        else:
            QMessageBox.information(self, "Поиск", "Ничего не найдено")
            self.status_bar.showMessage("Ничего не найдено")

    def _on_search_error(self, error: str) -> None:
        """Обработка ошибки поиска."""
        self.progress_bar.setVisible(False)
        self.address_bar.search_btn.setEnabled(True)
        self.status_bar.showMessage(f" Ошибка поиска: {error}")
        QMessageBox.warning(self, "Ошибка поиска", error)

    def _on_login(self) -> None:
        """Вход в Яндекс.Диск."""
        from gui.dialogs.login_dialog import LoginDialog

        dialog = LoginDialog(self)
        if dialog.exec():
            token = dialog.get_token()
            if token:
                from api.providers.yadisk.auth_manager import AuthManager
                AuthManager.save_token(token)

                cloud_provider = self._providers.get('cloud')
                if cloud_provider and hasattr(cloud_provider, 'setup_token'):
                    # Передаём callback для обновления
                    cloud_provider.setup_token(token, self._on_sync_refresh)

                self._update_auth_status()
                self.side_bar.refresh_tree()
                self._update_sync_status()

                QMessageBox.information(self, "Успех", "Вход выполнен успешно")

    def _on_sync_refresh(self) -> None:
        """Callback для обновления GUI при синхронизации."""
        # Обновляем только если сейчас в облаке
        if self._operation_in_progress:
            return
        cloud_provider = self._providers.get('cloud')
        if self._current_provider == cloud_provider and self._current_path:
            # Используем тот же механизм, что и кнопка обновления
            self._load_directory(self._current_path)

    def _update_sync_status(self) -> None:
        """Обновление индикатора синхронизации."""
        cloud_provider = self._providers.get('cloud')
        if cloud_provider and hasattr(cloud_provider, '_bridge'):
            if cloud_provider._bridge.is_sync_running():
                self.sync_label.setText("Синхр: вкл")
                self.sync_label.setStyleSheet("color: #4caf50; padding: 0 8px;")
            else:
                self.sync_label.setText("Синхр: выкл")
                self.sync_label.setStyleSheet("color: #757575; padding: 0 8px;")
        else:
            self.sync_label.setText("Синхр: выкл")
            self.sync_label.setStyleSheet("color: #757575; padding: 0 8px;")

    def _update_auth_status(self) -> None:
        """Обновление статуса авторизации в меню."""
        if not hasattr(self, 'status_action'):
            return

        cloud_provider = self._providers.get('cloud')
        is_authorized = False

        if cloud_provider and hasattr(cloud_provider, 'has_token'):
            is_authorized = cloud_provider.has_token()

        if is_authorized:
            self.status_action.setText("Статус: авторизован")
            self.login_action.setEnabled(False)
            self.logout_action.setEnabled(True)
        else:
            self.status_action.setText("Статус: не авторизован")
            self.login_action.setEnabled(True)
            self.logout_action.setEnabled(False)

    def _on_logout(self) -> None:
        """Выход из Яндекс.Диска."""
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Выйти из аккаунта Яндекс.Диска?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            cloud_provider = self._providers.get('cloud')

            # Останавливаем синхронизацию перед выходом
            if cloud_provider and hasattr(cloud_provider, '_bridge'):
                cloud_provider._bridge.stop_sync()

            if hasattr(self, 'sync_label'):
                self.sync_label.setText("Синхр: выкл")
                self.sync_label.setStyleSheet("color: #757575; padding: 0 8px;")
            # Удаляем токен из keyring
            try:
                import keyring
                keyring.delete_password("DiscoHack", "yandex_token")
            except Exception as e:
                print(f"Ошибка удаления из keyring: {e}")

            # Удаляем файл с токеном
            token_file = Path.home() / '.core-disko' / 'yandex.token'
            if token_file.exists():
                token_file.unlink()

            # Сбрасываем провайдер
            if cloud_provider:
                if hasattr(cloud_provider, '_bridge'):
                    cloud_provider._bridge.provider = None

            # Обновляем UI
            self._update_auth_status()
            self.side_bar.refresh_tree()

            # Если сейчас в облаке, переключаемся на локальные диски
            if self._current_provider == cloud_provider:
                local_provider = self._providers.get('local')
                if local_provider:
                    self._current_provider = local_provider
                    self._current_path = local_provider.get_root_path()
                    self._load_directory(self._current_path)
                    self.address_bar.set_path(self._current_path)

            self.status_bar.showMessage("Выход выполнен")
            QMessageBox.information(self, "Успех", "Выход выполнен")

    def _can_show_notifications(self) -> bool:
        """Проверяет, разрешены ли уведомления."""
        settings = QSettings("TeamTyler", "CloudManager")
        settings.sync()
        return settings.value("show_notifications", True, type=bool)

    def _notify_upload_complete(self):
        """Уведомление о завершении загрузки на диск."""
        if not self._can_show_notifications():
            return
        msg = f"Загружено {self._upload_success} из {self._upload_total} файлов"
        dest_path = getattr(self, '_upload_dest_path', '/')
        toast = ToastNotification(
            "Загрузка завершена",
            msg,
            "Открыть папку в облаке",
            callback=lambda: self._navigate_to_provider('cloud', dest_path),
            parent=self
        )
        toast.show_at_bottom_right()

    def _notify_download_complete(self):
        """Уведомление о завершении скачивания."""
        if not self._can_show_notifications():
            return
        msg = f"Скачано {self._download_success} из {self._download_total} файлов"
        downloads_path = str(self._cloud_provider._bridge.downloads_path) if self._cloud_provider else ""
        toast = ToastNotification(
            "Скачивание завершено",
            msg,
            "Открыть папку Downloads",
            callback=lambda: self._navigate_to_provider('local', downloads_path),
            parent=self
        )
        toast.show_at_bottom_right()

    def _on_file_rename(self, file_item, new_name: str) -> None:
        """Переименование файла/папки."""
        # Защита: нельзя переименовывать в mounts://
        if self._current_path == "mounts://":
            QMessageBox.warning(self, "Ошибка", "Переименование запрещено в корневой директории")
            return

        print(f"DEBUG: _on_file_rename вызван: {file_item.name} -> {new_name}")

        if not self._current_provider:
            QMessageBox.warning(self, "Ошибка", "Нет активного провайдера")
            return

        old_path = file_item.path
        parent_path = str(Path(old_path).parent)

        # Формируем новый путь
        if parent_path == "." or parent_path == "/":
            new_path = f"/{new_name}"
        else:
            new_path = f"{parent_path}/{new_name}"

        try:
            # Вызываем переименование у провайдера
            self._current_provider.rename_file(old_path, new_path)
            self.status_bar.showMessage(f"Переименовано: {file_item.name} -> {new_name}")
            self._on_refresh()  # Обновляем список
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось переименовать: {e}")

    def _on_copy_files(self, items: list) -> None:
        """Копирование файлов (сохраняем в буфер)."""
        print(f"DEBUG: _on_copy_files получил {len(items)} элементов")
        self._clipboard = items
        for item in items:
            print(f"  - {item.name}")
        self.status_bar.showMessage(f"Скопировано {len(items)} элементов")

    def _on_paste_files(self) -> None:
        """Вставка скопированных файлов."""
        if not self._clipboard:
            QMessageBox.information(self, "Инфо", "Нет скопированных файлов")
            return

        if not self._current_provider:
            QMessageBox.warning(self, "Ошибка", "Нет активного провайдера")
            return

        dest_path = self._current_path

        progress = ProgressDialog("Копирование файлов", self)
        progress.set_cancellable(False)
        progress.show()

        success_count = 0
        for i, item in enumerate(self._clipboard):
            src_path = item.path
            name = Path(src_path).name
            dest = f"{dest_path.rstrip('/')}/{name}"

            progress.set_status(f"Копирование: {name}", f"{i + 1} из {len(self._clipboard)}")

            try:
                # Пытаемся использовать copy_file если есть
                if hasattr(self._current_provider, 'copy_file'):
                    self._current_provider.copy_file(src_path, dest)
                else:
                    # Fallback: download + upload
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False) as tmp:
                        self._current_provider.download_file(src_path, tmp.name)
                        self._current_provider.upload_file(tmp.name, dest)
                success_count += 1
            except Exception as e:
                print(f"Ошибка копирования {name}: {e}")
                QMessageBox.warning(self, "Ошибка", f"Не удалось скопировать {name}: {e}")

        progress.operation_finished(True)
        self.status_bar.showMessage(f"Скопировано {success_count} из {len(self._clipboard)} файлов")
        self._on_refresh()

    def _can_show_notifications(self) -> bool:
        """Проверяет, разрешены ли уведомления."""
        settings = QSettings("TeamTyler", "CloudManager")
        settings.sync()
        return settings.value("show_notifications", True, type=bool)

    def _notify_upload_complete(self):
        """Уведомление о завершении загрузки на диск."""
        if not self._can_show_notifications():
            return
        msg = f"Загружено {self._upload_success} из {self._upload_total} файлов"
        dest_path = getattr(self, '_upload_dest_path', '/')
        toast = ToastNotification(
            "Загрузка завершена",
            msg,
            "Открыть папку в облаке",
            callback=lambda: self._navigate_to_provider('cloud', dest_path),
            parent=self
        )
        toast.show_at_bottom_right()

    def _notify_download_complete(self):
        """Уведомление о завершении скачивания."""
        if not self._can_show_notifications():
            return
        msg = f"Скачано {self._download_success} из {self._download_total} файлов"
        downloads_path = str(self._cloud_provider._bridge.downloads_path) if self._cloud_provider else ""
        toast = ToastNotification(
            "Скачивание завершено",
            msg,
            "Открыть папку Downloads",
            callback=lambda: self._navigate_to_provider('local', downloads_path),
            parent=self
        )
        toast.show_at_bottom_right()
    def _is_local_provider(self) -> bool:
        """Проверить, является ли текущий провайдер локальным."""
        if not self._current_provider:
            return False
        cloud_provider = self._providers.get('cloud')
        return self._current_provider != cloud_provider

    def _update_menu_buttons(self) -> None:
        """Обновление состояния кнопок в меню."""
        is_local = self._is_local_provider()

        if hasattr(self, 'upload_menu_action'):
            self.upload_menu_action.setEnabled(not is_local)
        if hasattr(self, 'download_menu_action'):
            self.download_menu_action.setEnabled(not is_local)

