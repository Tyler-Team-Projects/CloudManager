"""Таблица/иконки с файлами и папками."""
from typing import List, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QHeaderView,
    QAbstractItemView, QMenu, QListWidget, QListWidgetItem,
    QStackedWidget, QInputDialog, QStyle, QApplication
)
from PyQt6.QtCore import pyqtSignal, Qt, QPoint, QModelIndex, QSize

from PyQt6.QtGui import QAction, QIcon, QStandardItemModel, QStandardItem, QKeySequence
from core.local.local_provider import LocalFileSystemProvider
from api.common.models import CloudFile
from api.common.base_provider import BaseCloudProvider


class FileTableModel(QStandardItemModel):
    """Модель для отображения файлов в таблице."""

    def __init__(self):
        super().__init__()
        self.setHorizontalHeaderLabels(["Статус", "Имя", "Размер", "Тип"])
        self._items: List[CloudFile] = []

    def set_items(self, items: List[CloudFile]) -> None:
        """Установка элементов с отображением статуса синхронизации."""
        self._items = items
        self.removeRows(0, self.rowCount())

        for item in items:
            # --- КОЛОНКА 0: СТАТУС ---
            status_item = QStandardItem()
            status_item.setEditable(False)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if item.is_dir:
                # Для папок — пустая ячейка (иконка будет в колонке "Имя")
                status_item.setIcon(QIcon())
                status_item.setText("")
                status_item.setToolTip("Папка")
                status_item.setData("folder", Qt.ItemDataRole.UserRole + 1)
            else:
                is_downloaded = getattr(item, 'is_downloaded', False)
                is_synced = getattr(item, 'is_synced', False)

                if is_downloaded and is_synced:
                    status_item.setIcon(QIcon())
                    status_item.setText("✅")
                    status_item.setToolTip("Синхронизирован ✓")
                    status_item.setData("synced", Qt.ItemDataRole.UserRole + 1)
                    status_item.setForeground(Qt.GlobalColor.green)
                elif is_downloaded and not is_synced:
                    status_item.setIcon(QIcon())
                    status_item.setText("⚠️")
                    status_item.setToolTip("Не синхронизирован! Требуется обновление")
                    status_item.setData("outdated", Qt.ItemDataRole.UserRole + 1)
                    status_item.setForeground(Qt.GlobalColor.darkYellow)
                else:
                    status_item.setIcon(QIcon())
                    status_item.setText("⬇️")
                    status_item.setToolTip("Не скачан локально")
                    status_item.setData("not_downloaded", Qt.ItemDataRole.UserRole + 1)
                    status_item.setForeground(Qt.GlobalColor.gray)

            # --- КОЛОНКА 1: ИМЯ ---
            name_item = QStandardItem(item.name)
            name_item.setData(item, Qt.ItemDataRole.UserRole)
            name_item.setEditable(False)

            if item.is_dir:
                name_item.setIcon(self._get_icon("folder"))
            else:
                name_item.setIcon(self._get_file_icon(item.name))

            # --- КОЛОНКА 2: РАЗМЕР ---
            if item.is_dir:
                size_str = ""
            else:
                size_str = self._format_size(item.size)

            size_item = QStandardItem(size_str)
            size_item.setEditable(False)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            # --- КОЛОНКА 3: ТИП ---
            if item.is_dir:
                type_str = "Папка"
            else:
                type_str = item.mime_type or "Файл"

            type_item = QStandardItem(type_str)
            type_item.setEditable(False)

            self.appendRow([status_item, name_item, size_item, type_item])

    def _format_size(self, size: int) -> str:
        """Форматирование размера."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def _get_file_icon(self, filename: str) -> QIcon:
        """Получить иконку по расширению файла."""
        ext = Path(filename).suffix.lower()

        icon_map = {
            '.jpg': QIcon.fromTheme("image-x-generic"),
            '.jpeg': QIcon.fromTheme("image-x-generic"),
            '.png': QIcon.fromTheme("image-x-generic"),
            '.gif': QIcon.fromTheme("image-x-generic"),
            '.bmp': QIcon.fromTheme("image-x-generic"),
            '.webp': QIcon.fromTheme("image-x-generic"),
            '.pdf': QIcon.fromTheme("application-pdf"),
            '.doc': QIcon.fromTheme("application-msword"),
            '.docx': QIcon.fromTheme("application-msword"),
            '.xls': QIcon.fromTheme("application-vnd.ms-excel"),
            '.xlsx': QIcon.fromTheme("application-vnd.ms-excel"),
            '.mp3': QIcon.fromTheme("audio-x-generic"),
            '.mp4': QIcon.fromTheme("video-x-generic"),
            '.avi': QIcon.fromTheme("video-x-generic"),
            '.mkv': QIcon.fromTheme("video-x-generic"),
            '.mov': QIcon.fromTheme("video-x-generic"),
            '.zip': QIcon.fromTheme("package-x-generic"),
            '.rar': QIcon.fromTheme("package-x-generic"),
            '.7z': QIcon.fromTheme("package-x-generic"),
            '.tar': QIcon.fromTheme("package-x-generic"),
            '.gz': QIcon.fromTheme("package-x-generic"),
        }

        icon = icon_map.get(ext, QIcon.fromTheme("text-x-generic"))

        if icon.isNull():
            style = QApplication.style()
            return style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)

        return icon

    def _get_icon(self, name: str) -> QIcon:
        """Получить иконку (работает на всех платформах)."""
        icon = QIcon.fromTheme(name)
        if not icon.isNull():
            return icon

        style = QApplication.style()

        if name == "folder":
            return style.standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        elif name == "file":
            return style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        else:
            return style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)

    def get_item(self, row: int) -> Optional[CloudFile]:
        """Получить элемент по строке."""
        if 0 <= row < len(self._items):
            return self._items[row]
        return None


class FileTableView(QWidget):
    """Виджет таблицы/иконок файлов."""

    file_double_clicked = pyqtSignal(CloudFile)
    delete_requested = pyqtSignal(list)
    download_requested = pyqtSignal(list)
    update_requested = pyqtSignal(list)
    sync_check_requested = pyqtSignal(list)
    rename_requested = pyqtSignal(object, str)
    copy_requested = pyqtSignal(list)
    paste_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_provider: Optional[BaseCloudProvider] = None
        self._current_items: List[CloudFile] = []
        self._view_mode = "icons"
        self._current_display_path = ""
        self._clipboard_items: List[CloudFile] = []
        self._is_cloud_provider = False
        self._setup_ui()
        self._setup_context_menu()

    def _setup_ui(self) -> None:
        """Настройка UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.stacked_widget = QStackedWidget()

        # ============ ИКОНКИ (индекс 0) ============
        self.icon_view = QListWidget()
        self.icon_view.setViewMode(QListWidget.ViewMode.IconMode)
        self.icon_view.setIconSize(QSize(64, 64))
        self.icon_view.setGridSize(QSize(160, 160))
        self.icon_view.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.icon_view.setMovement(QListWidget.Movement.Static)
        self.icon_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.icon_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.icon_view.setSpacing(12)
        self.icon_view.setWordWrap(True)
        self.icon_view.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.icon_view.setFlow(QListWidget.Flow.LeftToRight)
        self.icon_view.setWrapping(True)

        self.icon_view.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                outline: none;
                border: none;
            }
            QListWidget::item {
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 8px 4px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
            }
            QListWidget::item:selected {
                background-color: #1976d2;
                color: white;
            }
            QListWidget::item:selected:hover {
                background-color: #1565c0;
            }
        """)

        self.icon_view.doubleClicked.connect(self._on_icon_double_click)
        self.icon_view.customContextMenuRequested.connect(self._show_context_menu)

        self.stacked_widget.addWidget(self.icon_view)

        # ============ ТАБЛИЦА (индекс 1) ============
        self.table_view = QTableView()
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_view.setAlternatingRowColors(False)
        self.table_view.setSortingEnabled(True)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table_model = FileTableModel()
        self.table_view.setModel(self.table_model)

        self.table_view.doubleClicked.connect(self._on_table_double_click)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)

        self.stacked_widget.addWidget(self.table_view)

        layout.addWidget(self.stacked_widget)

    def _setup_context_menu(self) -> None:
        """Настройка контекстного меню."""
        self.context_menu = QMenu(self)

        # Действия для файлов
        self.download_action = QAction(QIcon.fromTheme("document-save"), "Скачать", self)
        self.download_action.triggered.connect(self._on_download)

        self.sync_action = QAction(QIcon.fromTheme("view-refresh"), "Проверить синхронизацию", self)
        self.sync_action.triggered.connect(self._on_check_sync)

        self.update_action = QAction(QIcon.fromTheme("document-save"), "Обновить локальную копию", self)
        self.update_action.triggered.connect(self._on_update)

        self.rename_action = QAction(QIcon.fromTheme("edit-rename"), "Переименовать", self)
        self.rename_action.triggered.connect(self._on_rename)

        # Копировать
        self.copy_action = QAction(QIcon.fromTheme("edit-copy"), "Копировать", self)
        self.copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.copy_action.triggered.connect(self._on_copy)

        # Вставить
        self.paste_action = QAction(QIcon.fromTheme("edit-paste"), "Вставить", self)
        self.paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        self.paste_action.triggered.connect(self._on_paste)

        self.delete_action = QAction(QIcon.fromTheme("edit-delete"), "Удалить", self)
        self.delete_action.triggered.connect(self._on_delete)

        self.context_menu.addAction(self.download_action)
        self.context_menu.addAction(self.sync_action)
        self.context_menu.addAction(self.update_action)
        self.context_menu.addSeparator()
        self.context_menu.addAction(self.copy_action)
        self.context_menu.addAction(self.paste_action)
        self.context_menu.addSeparator()
        self.context_menu.addAction(self.rename_action)
        self.context_menu.addAction(self.delete_action)

    def set_view_mode(self, mode: str) -> None:
        """Переключение между таблицей и иконками."""
        self._view_mode = mode
        if mode == "table":
            self.stacked_widget.setCurrentIndex(1)
        else:
            self.stacked_widget.setCurrentIndex(0)
            self._update_icon_view()

    def _update_icon_view(self) -> None:
        """Обновить отображение иконок со статусом синхронизации."""
        from core.local.local_provider import LocalFileSystemProvider

        self.icon_view.clear()
        for item in self._current_items:
            list_item = QListWidgetItem()
            list_item.setData(Qt.ItemDataRole.UserRole, item)

            # Формируем отображаемое имя с индикатором статуса
            display_name = item.name

            if not item.is_dir:
                is_downloaded = getattr(item, 'is_downloaded', False)
                is_synced = getattr(item, 'is_synced', False)

                if is_downloaded and is_synced:
                    display_name = "✅ " + display_name
                    list_item.setToolTip(f"{item.name}\n✅ Синхронизирован")
                elif is_downloaded and not is_synced:
                    display_name = "⚠️ " + display_name
                    list_item.setToolTip(f"{item.name}\n⚠️ Требуется обновление")
                else:
                    display_name = "⬇️ " + display_name
                    list_item.setToolTip(f"{item.name}\n⬇️ Не скачан локально")
            else:
                list_item.setToolTip(f"{item.name}\n📁 Папка")

            list_item.setText(display_name)

            # Иконка
            if item.is_dir:
                list_item.setIcon(self._get_icon("folder"))
            else:
                # Для изображений показываем миниатюру
                ext = Path(item.name).suffix.lower()
                image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']

                if ext in image_extensions and isinstance(self._current_provider, LocalFileSystemProvider):
                    # Для локальных файлов - реальная миниатюра
                    icon = self._get_thumbnail(item.path, 128)
                    list_item.setIcon(icon)
                else:
                    # Для облачных файлов или других типов - стандартная иконка
                    list_item.setIcon(self._get_icon("file"))

            # Добавляем размер под иконкой
            if not item.is_dir:
                size_text = self._format_size(item.size)
                list_item.setToolTip(f"{list_item.toolTip()}\nРазмер: {size_text}")

            self.icon_view.addItem(list_item)

    def _format_size(self, size: int) -> str:
        """Форматирование размера."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def set_files(self, files: List[CloudFile], provider: BaseCloudProvider) -> None:
        """Установка файлов."""
        self._current_provider = provider
        self._current_items = files
        self.table_model.set_items(files)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Принудительно показываем иконки
        if self._view_mode == "icons":
            self._update_icon_view()
        else:
            # Для таблицы данные уже обновлены через table_model.set_items
            pass

    def get_selected_items(self) -> List[CloudFile]:
        """Получить выбранные элементы (работает в обоих режимах)."""
        items = []

        if self._view_mode == "table":
            for index in self.table_view.selectionModel().selectedRows(0):
                item = self.table_model.get_item(index.row())
                if item:
                    items.append(item)
        else:
            for list_item in self.icon_view.selectedItems():
                item = list_item.data(Qt.ItemDataRole.UserRole)
                if item:
                    items.append(item)

        return items

    def _on_table_double_click(self, index: QModelIndex) -> None:
        """Обработка двойного клика в таблице."""
        item = self.table_model.get_item(index.row())
        if item:
            self.file_double_clicked.emit(item)

    def _on_icon_double_click(self, index) -> None:
        """Обработка двойного клика в иконках."""
        list_item = self.icon_view.itemFromIndex(index)
        if list_item:
            item = list_item.data(Qt.ItemDataRole.UserRole)
            if item:
                self.file_double_clicked.emit(item)

    def _show_context_menu(self, pos: QPoint) -> None:
        """Показ контекстного меню с динамическими опциями."""
        items = self.get_selected_items()
        has_selection = len(items) > 0

        has_downloaded = any(getattr(item, 'is_downloaded', False) for item in items)
        has_not_downloaded = any(not getattr(item, 'is_downloaded', False) for item in items)
        has_outdated = any(
            getattr(item, 'is_downloaded', False) and not getattr(item, 'is_synced', False) for item in items)
        has_folder = any(item.is_dir for item in items)

        is_local = self._is_local_provider()
        is_root = self._is_mounts_root()

        if is_root or is_local:
            # На локальном диске или в mounts:// облачные операции НЕДОСТУПНЫ
            self.download_action.setEnabled(False)
            self.sync_action.setEnabled(False)
            self.update_action.setEnabled(False)
        else:
            # В облачной папке облачные операции доступны
            self.download_action.setEnabled(has_selection)
            self.download_action.setVisible(has_selection)

            self.sync_action.setEnabled(has_selection and has_downloaded)
            self.sync_action.setVisible(has_selection)

            self.update_action.setEnabled(has_selection and has_outdated)
            self.update_action.setVisible(has_selection)

        if is_root:
            # В корне mounts:// локальные операции блокируем
            self.copy_action.setEnabled(False)
            self.paste_action.setEnabled(False)
            self.rename_action.setEnabled(False)
            self.delete_action.setEnabled(False)
        else:
            # На локальном диске И в облачной папке локальные операции доступны
            self.copy_action.setEnabled(has_selection and not has_folder)
            self.paste_action.setEnabled(has_selection)
            self.rename_action.setEnabled(has_selection and len(items) == 1)
            self.delete_action.setEnabled(has_selection)

        if self._view_mode == "table":
            self.context_menu.exec(self.table_view.viewport().mapToGlobal(pos))
        else:
            self.context_menu.exec(self.icon_view.viewport().mapToGlobal(pos))

    def _on_download(self) -> None:
        """Скачивание выбранных файлов."""
        if self._is_mounts_root():
            print("Скачивание запрещено в mounts://")
            return

        if self._is_local_provider():
            print("Скачивание запрещено на локальном диске")
            return

        items = self.get_selected_items()
        to_download = [item for item in items if not item.is_dir]
        if to_download:
            self.download_requested.emit(to_download)

    def _on_check_sync(self) -> None:
        """Проверка синхронизации выбранных файлов."""
        if self._is_mounts_root():
            print("Проверка синхронизации запрещена в mounts://")
            return

        if self._is_local_provider():
            print("Проверка синхронизации доступна только в облачной папке")
            return

        items = self.get_selected_items()
        # Фильтруем только скачанные файлы
        to_check = [item for item in items if not item.is_dir and getattr(item, 'is_downloaded', False)]
        if to_check:
            self.sync_check_requested.emit(to_check)

    def _on_update(self) -> None:
        """Обновление локальной копии из облака (перезапись)."""
        if self._is_mounts_root():
            print("Обновление запрещено в mounts://")
            return

        if self._is_local_provider():
            print("Обновление доступно только в облачной папке")
            return

        items = self.get_selected_items()
        # Фильтруем только несинхронизированные файлы
        to_update = [item for item in items if not item.is_dir and
                     getattr(item, 'is_downloaded', False) and
                     not getattr(item, 'is_synced', False)]

        if to_update:
            self.update_requested.emit(to_update)

    def _on_delete(self) -> None:
        """Удаление."""
        if self._is_mounts_root():
            print("Удаление запрещено в mounts://")
            return

        items = self.get_selected_items()
        if items:
            self.delete_requested.emit(items)

        # Проверяем, находимся ли в корне mounts://
        if self._current_provider and hasattr(self._current_provider, 'get_root_path'):
            root_path = self._current_provider.get_root_path()
            current_path = getattr(self, '_current_path', "")
            if root_path == "mounts://" and current_path == "mounts://":
                print("Нельзя удалять в корневой директории")
                return

        # Проверяем, нет ли корневых элементов
        for item in items:
            if self._is_root_item(item):
                print("Нельзя удалить корневой элемент")
                return

        # self.delete_requested.emit(items)

    def _on_rename(self) -> None:
        """Переименование выбранного элемента."""
        items = self.get_selected_items()
        if len(items) != 1:
            return

        file_item = items[0]

        # Запрещаем переименование корневых элементов
        if self._is_root_item(file_item):
            return

        old_name = file_item.name

        new_name, ok = QInputDialog.getText(
            self,
            "Переименовать",
            f"Введите новое имя для '{old_name}':",
            text=old_name
        )

        if ok and new_name and new_name != old_name:
            self.rename_requested.emit(file_item, new_name)

    def _is_root_item(self, file_item: CloudFile) -> bool:
        """Проверить, является ли элемент корневым диском."""
        # Корневые элементы имеют специальные имена или пути
        root_names = ["Домашняя папка", "Корень (/)", "/home"]
        root_paths = ["mounts://", "/"]
        if file_item.path == "mounts://":
            return True
        if file_item.name in root_names:
            return True
        if file_item.path in root_paths:
            return True
        return False

    def _is_local_provider(self) -> bool:
        """Проверить, является ли текущий провайдер локальным."""
        if not self._current_provider:
            return False
        return hasattr(self._current_provider, 'get_mounts_root')

    def _is_mounts_root(self) -> bool:
        """Проверить, находимся ли в корне mounts://."""
        return self._current_display_path == "mounts://"

    def keyPressEvent(self, event) -> None:
        """Обработка нажатий клавиш."""
        if event.key() == Qt.Key.Key_Delete:
            self._on_delete()
            event.accept()
            return

        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_C:
                # Ctrl+C - копировать
                self._on_copy()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_V:
                # Ctrl+V - вставить
                self._on_paste()
                event.accept()
                return

        super().keyPressEvent(event)

    def _on_copy(self) -> None:
        """Копирование."""
        if self._is_mounts_root():
            print("Копирование запрещено в mounts://")
            return

        items = self.get_selected_items()
        if items:
            self._clipboard_items = items.copy()
            self.copy_requested.emit(items)

    def _on_paste(self) -> None:
        """Вставить файлы из буфера."""
        print(f"DEBUG: _on_paste вызван, буфер содержит {len(self._clipboard_items)} элементов")

        if not self._clipboard_items:
            print("DEBUG: Буфер пуст")
            return

        self.paste_requested.emit()

    def _is_current_path_root(self) -> bool:
        """Проверить, находится ли пользователь в корневом пути mounts://."""
        if hasattr(self._current_provider, 'get_root_path'):
            root_path = self._current_provider.get_root_path()
            if root_path == "mounts://":
                # Нужно знать текущий путь
                pass
        return False

    def set_current_path(self, path: str) -> None:
        """Установить текущий путь (для проверки mounts://)."""
        self._current_display_path = path

    def _get_icon(self, name: str) -> QIcon:
        """Получить иконку (работает на всех платформах)."""
        # пробуем из темы
        icon = QIcon.fromTheme(name)
        if not icon.isNull():
            return icon

        # иначе используем стандартную Qt
        style = QApplication.style()

        if name == "folder":
            return style.standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        elif name == "file":
            return style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        else:
            return style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)

    def _get_thumbnail(self, file_path: str, size: int = 128) -> QIcon:
        """Получить миниатюру изображения."""
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import QSize

        # Проверяем расширение
        ext = Path(file_path).suffix.lower()
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']

        if ext not in image_extensions:
            return QIcon.fromTheme("text-x-generic")

        # Пытаемся загрузить миниатюру
        try:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                # Масштабируем с сохранением пропорций
                scaled_pixmap = pixmap.scaled(size, size,
                                              Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)
                return QIcon(scaled_pixmap)
        except Exception as e:
            print(f"Не удалось создать миниатюру для {file_path}: {e}")

        return QIcon.fromTheme("image-x-generic")