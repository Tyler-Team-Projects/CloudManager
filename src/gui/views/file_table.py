"""Таблица/иконки с файлами и папками."""
from typing import List, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QHeaderView,
    QAbstractItemView, QMenu, QListWidget, QListWidgetItem,
    QStackedWidget, QInputDialog, QStyle, QApplication
)

from PyQt6.QtCore import pyqtSignal, Qt, QPoint, QModelIndex, QSize, QSortFilterProxyModel, QMimeData
from PyQt6.QtGui import (
    QAction, QIcon, QStandardItemModel, QStandardItem, QKeySequence,
    QDragEnterEvent, QDragMoveEvent, QDropEvent
)
from core.local.local_provider import LocalFileSystemProvider
from api.common.models import CloudFile
from api.common.base_provider import BaseCloudProvider


class FileSortFilterProxyModel(QSortFilterProxyModel):
    def lessThan(self, left, right):
        if self.sortColumn() == 1:  # размер
            left_val = left.data(Qt.ItemDataRole.UserRole + 1)
            right_val = right.data(Qt.ItemDataRole.UserRole + 1)
            return left_val < right_val
        return super().lessThan(left, right)

class FileTableModel(QStandardItemModel):
    """Модель для отображения файлов в таблице."""

    def __init__(self):
        super().__init__()
        self.setHorizontalHeaderLabels(["Имя", "Размер", "Статус"]) # "Тип",
        self._items: List[CloudFile] = []

    def set_items(self, items: List[CloudFile]) -> None:
        """Полная замена модели (используется при первой загрузке)."""
        self._items = items
        self.removeRows(0, self.rowCount())
        for item in items:
            self._append_item(item)

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Корректная сортировка по размеру и имени."""
        if column == 1:  # колонка размера
            self.setSortRole(Qt.ItemDataRole.UserRole + 1)
        else:
            self.setSortRole(Qt.ItemDataRole.DisplayRole)
        super().sort(column, order)

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

    def update_items(self, new_items: List[CloudFile]) -> None:
        """
        Частичное обновление модели: сравнивает с текущим списком,
        обновляет только изменившиеся элементы.
        """
        old_items = self._items
        old_paths = {item.path: item for item in old_items}
        new_paths = {item.path: item for item in new_items}

        # 1. Удаляем строки, которых нет в новом списке (с конца к началу)
        for row in range(self.rowCount() - 1, -1, -1):
            item = self.get_item(row)
            if item and item.path not in new_paths:
                self.removeRow(row)

        # 2. Обновляем существующие строки и добавляем новые
        for i, new_item in enumerate(new_items):
            if new_item.path in old_paths:
                # Обновить существующую строку
                old_item = old_paths[new_item.path]
                # Найти строку с этим элементом в модели
                for row in range(self.rowCount()):
                    if self.get_item(row) == old_item:
                        # Обновить имя, размер, статус
                        name_item = self.item(row, 0)
                        name_item.setText(new_item.name)
                        name_item.setIcon(
                            self._get_file_icon(new_item.name) if not new_item.is_dir else self._get_icon("folder"))
                        size_item = self.item(row, 1)
                        if new_item.is_dir:
                            size_item.setText("")
                            size_item.setData(-1, Qt.ItemDataRole.UserRole + 1)
                        else:
                            size_item.setText(self._format_size(new_item.size))
                            size_item.setData(new_item.size, Qt.ItemDataRole.UserRole + 1)
                        status_item = self.item(row, 2)
                        # Обновить статус аналогично set_items
                        self._update_status_item(status_item, new_item)
                        break
            else:
                # Добавить новую строку
                self._append_item(new_item)

        # 3. Обновить внутренний список
        self._items = new_items

    def _append_item(self, item: CloudFile):
        """Добавить одну строку в модель."""
        name_item = QStandardItem(item.name)
        name_item.setData(item, Qt.ItemDataRole.UserRole)
        name_item.setEditable(False)
        if item.is_dir:
            name_item.setIcon(self._get_icon("folder"))
            size_str = ""
            numeric_size = -1
        else:
            name_item.setIcon(self._get_file_icon(item.name))
            size_str = self._format_size(item.size)
            numeric_size = item.size

        size_item = QStandardItem(size_str)
        size_item.setEditable(False)
        size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        size_item.setData(numeric_size, Qt.ItemDataRole.UserRole + 1)

        status_item = QStandardItem()
        self._update_status_item(status_item, item)

        self.appendRow([name_item, size_item, status_item])

    def _update_status_item(self, status_item: QStandardItem, item: CloudFile):
        status_item.setEditable(False)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if item.is_dir:
            status_item.setText("")
            status_item.setToolTip("Папка")
        else:
            is_downloaded = getattr(item, 'is_downloaded', False)
            is_synced = getattr(item, 'is_synced', False)
            if is_downloaded and is_synced:
                status_item.setText("✅")
                status_item.setToolTip("Синхронизирован ✓")
                status_item.setForeground(Qt.GlobalColor.green)
            elif is_downloaded and not is_synced:
                status_item.setText("⚠️")
                status_item.setToolTip("Не синхронизирован! Требуется обновление")
                status_item.setForeground(Qt.GlobalColor.darkYellow)
            else:
                status_item.setText("⬇️")
                status_item.setToolTip("Не скачан локально")
                status_item.setForeground(Qt.GlobalColor.gray)

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
    new_folder_requested = pyqtSignal()
    public_link_requested = pyqtSignal(str)
    files_dropped = pyqtSignal(list)
    save_as_requested = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_provider: Optional[BaseCloudProvider] = None
        self._current_items: List[CloudFile] = []
        self._view_mode = "icons"
        self._current_display_path = ""
        self._clipboard_items: List[CloudFile] = []
        self._is_cloud_provider = False
        self._setup_ui()
        self._last_icon_path = None
        self._icon_view_initialized = False
        self._setup_context_menu()

    def _setup_ui(self) -> None:
        """Настройка UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.stacked_widget = QStackedWidget()

        self.setAcceptDrops(True)

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

        self.icon_view.setAcceptDrops(True)
        self.icon_view.dragEnterEvent = self.dragEnterEvent
        self.icon_view.dragMoveEvent = self.dragMoveEvent
        self.icon_view.dropEvent = self.dropEvent

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
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table_view.setAcceptDrops(True)
        self.table_view.dragEnterEvent = self.dragEnterEvent
        self.table_view.dragMoveEvent = self.dragMoveEvent
        self.table_view.dropEvent = self.dropEvent

        self.table_model = FileTableModel()

        # --- Создаём свою прокси для сортировки ---
        self.sort_proxy = FileSortFilterProxyModel()
        self.sort_proxy.setSourceModel(self.table_model)
        self.table_view.setModel(self.sort_proxy)

        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table_view.setColumnWidth(1, 120)
        self.table_view.setColumnWidth(2, 80)

        # Подключаем сортировку по клику на заголовок
        header = self.table_view.horizontalHeader()
        header.sectionClicked.connect(self._on_header_clicked)

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

        self.save_as_action = QAction(QIcon.fromTheme("document-save-as"), "Сохранить как...", self)
        self.save_as_action.triggered.connect(self._on_save_as)

        self.sync_action = QAction(QIcon.fromTheme("view-refresh"), "Проверить синхронизацию", self)
        self.sync_action.triggered.connect(self._on_check_sync)

        self.update_action = QAction(QIcon.fromTheme("document-save"), "Обновить локальную копию", self)
        self.update_action.triggered.connect(self._on_update)

        # Публичная ссылка
        self.public_link_action = QAction(QIcon.fromTheme("emblem-shared"), "Публичная ссылка", self)
        self.public_link_action.triggered.connect(self._on_public_link)

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
        self.context_menu.addAction(self.save_as_action)
        self.context_menu.addAction(self.sync_action)
        self.context_menu.addAction(self.update_action)
        self.context_menu.addAction(self.public_link_action)
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
        """Обновить отображение иконок (полная перерисовка)."""
        self.icon_view.clear()
        for item in self._current_items:
            self._add_icon_item(item)

    def _update_icon_view_incremental(self, new_items: List[CloudFile], old_items_list: List[CloudFile]) -> None:
        """Частичное обновление иконок – только изменившиеся элементы."""
        old_items = {item.path: item for item in old_items_list}
        new_paths = {item.path for item in new_items}

        # Удаляем исчезнувшие элементы (с конца к началу)
        for i in range(self.icon_view.count() - 1, -1, -1):
            list_item = self.icon_view.item(i)
            data = list_item.data(Qt.ItemDataRole.UserRole)
            if data and data.path not in new_paths:
                self.icon_view.takeItem(i)

        # Обновляем существующие и добавляем новые
        for new_item in new_items:
            if new_item.path in old_items:
                # Обновить текст и статус у существующего элемента
                for i in range(self.icon_view.count()):
                    existing = self.icon_view.item(i)
                    existing_data = existing.data(Qt.ItemDataRole.UserRole)
                    if existing_data and existing_data.path == new_item.path:
                        # Обновить отображаемое имя и статус
                        display_name = self._build_icon_display_name(new_item)
                        existing.setText(display_name)
                        # Обновить тултип
                        tip = self._build_icon_tooltip(new_item)
                        existing.setToolTip(tip)
                        # Иконка для существующего элемента не меняется (только если файл стал папкой или наоборот – маловероятно)
                        break
            else:
                # Добавить новый элемент
                self._add_icon_item(new_item)

        self._current_items = new_items

    def _add_icon_item(self, item: CloudFile) -> None:
        """Добавить один элемент в QListWidget."""
        from core.local.local_provider import LocalFileSystemProvider

        list_item = QListWidgetItem()
        list_item.setData(Qt.ItemDataRole.UserRole, item)

        display_name = self._build_icon_display_name(item)
        list_item.setText(display_name)
        list_item.setToolTip(self._build_icon_tooltip(item))

        # Иконка
        if item.is_dir:
            list_item.setIcon(self._get_icon("folder"))
        else:
            ext = Path(item.name).suffix.lower()
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
            if ext in image_extensions and isinstance(self._current_provider, LocalFileSystemProvider):
                icon = self._get_thumbnail(item.path, 128)
                list_item.setIcon(icon)
            else:
                list_item.setIcon(self._get_icon("file"))

        self.icon_view.addItem(list_item)

    def _build_icon_display_name(self, item: CloudFile) -> str:
        """Сформировать отображаемое имя с учётом статуса."""
        if self._is_cloud_provider and not item.is_dir:
            is_downloaded = getattr(item, 'is_downloaded', False)
            is_synced = getattr(item, 'is_synced', False)
            if is_downloaded and is_synced:
                return "✅ " + item.name
            elif is_downloaded and not is_synced:
                return "⚠️ " + item.name
            else:
                return "⬇️ " + item.name
        return item.name

    def _build_icon_tooltip(self, item: CloudFile) -> str:
        """Сформировать тултип для элемента."""
        if self._is_cloud_provider and not item.is_dir:
            is_downloaded = getattr(item, 'is_downloaded', False)
            is_synced = getattr(item, 'is_synced', False)
            if is_downloaded and is_synced:
                status = "✅ Синхронизирован"
            elif is_downloaded and not is_synced:
                status = "⚠️ Требуется обновление"
            else:
                status = "⬇️ Не скачан локально"
        else:
            status = "📁 Папка" if item.is_dir else ""

        tip = item.name + "\n" + status
        if not item.is_dir:
            size_text = self._format_size(item.size)
            tip += f"\nРазмер: {size_text}"
        return tip
    def _format_size(self, size: int) -> str:
        """Форматирование размера."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def set_files(self, files: List[CloudFile], provider: BaseCloudProvider, is_cloud: bool = False,
                  path: str = None) -> None:
        self._current_provider = provider

        old_items_for_icons = self._current_items
        self._current_items = files
        provider_changed = (self._is_cloud_provider != is_cloud)
        self._is_cloud_provider = is_cloud

        # Определяем, изменился ли путь
        path_changed = (path is not None and self._last_icon_path != path)
        if path is not None:
            self._last_icon_path = path

        if self.table_model.rowCount() == 0:
            self.table_model.set_items(files)
        else:
            self.table_model.update_items(files)
            if self.sort_proxy.sortColumn() >= 0:
                self.sort_proxy.sort(self.sort_proxy.sortColumn(), self.sort_proxy.sortOrder())

        self._update_status_column_visibility()

        if self._view_mode == "icons":
            if not self._icon_view_initialized or provider_changed or path_changed:
                self._update_icon_view()
                self._icon_view_initialized = True
            else:
                self._update_icon_view_incremental(files, old_items_for_icons)

    def _update_status_column_visibility(self) -> None:
        self.table_view.setColumnHidden(2, not self._is_cloud_provider)

    def get_selected_items(self) -> List[CloudFile]:
        items = []
        if self._view_mode == "table":
            for index in self.table_view.selectionModel().selectedRows(0):
                src_index = self.sort_proxy.mapToSource(index)
                item = self.table_model.get_item(src_index.row())
                if item:
                    items.append(item)
        else:
            for list_item in self.icon_view.selectedItems():
                item = list_item.data(Qt.ItemDataRole.UserRole)
                if item:
                    items.append(item)
        return items

    def add_file(self, file_item: CloudFile) -> None:
        """Мгновенно добавляет один файл в таблицу и иконки (для облачной загрузки)."""
        # Добавляем в модель таблицы
        self.table_model._append_item(file_item)
        # Если активна сортировка, пересортируем
        if self.sort_proxy.sortColumn() >= 0:
            self.sort_proxy.sort(self.sort_proxy.sortColumn(), self.sort_proxy.sortOrder())
        # Добавляем иконку, если режим иконок
        if self._view_mode == "icons":
            self._add_icon_item(file_item)
        # Обновляем внутренний список
        self._current_items.append(file_item)

    def _source_index(self, index: QModelIndex) -> QModelIndex:
        model = self.table_view.model()
        print(f"[DEBUG] model type: {type(model).__name__}")
        if isinstance(model, QSortFilterProxyModel):
            return model.mapToSource(index)
        return index

    def _on_table_double_click(self, index: QModelIndex) -> None:
        # index – из прокси, преобразуем к исходной модели
        src_index = self.sort_proxy.mapToSource(index)
        item = self.table_model.get_item(src_index.row())
        if item:
            self.file_double_clicked.emit(item)

    def _on_header_clicked(self, logical_index):
        """Переключает сортировку при клике на заголовок."""
        proxy = self.sort_proxy
        if proxy.sortColumn() == logical_index:
            # Переключаем порядок
            new_order = Qt.SortOrder.DescendingOrder if proxy.sortOrder() == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
        else:
            new_order = Qt.SortOrder.AscendingOrder
        proxy.sort(logical_index, new_order)

    def _on_icon_double_click(self, index) -> None:
        """Обработка двойного клика в иконках."""
        list_item = self.icon_view.itemFromIndex(index)
        if list_item:
            item = list_item.data(Qt.ItemDataRole.UserRole)
            if item:
                self.file_double_clicked.emit(item)

    def _show_context_menu(self, pos: QPoint) -> None:
        """Показ контекстного меню с динамическими опциями."""
        # Сбрасываем состояние публичной ссылки перед каждым показом меню
        self.public_link_action.setVisible(False)
        self.public_link_action.setEnabled(False)

        items = self.get_selected_items()
        has_selection = len(items) > 0

        # Определяем, кликнули ли на пустом месте
        is_empty_area = False
        if self._view_mode == "icons":
            if self.icon_view.itemAt(pos) is None:
                is_empty_area = True
        else:  # table
            index = self.table_view.indexAt(pos)
            if not index.isValid():
                is_empty_area = True

        # Если клик на пустом месте (и не в mounts:// корне)
        if is_empty_area and not self._is_mounts_root():
            empty_menu = QMenu(self)
            new_folder_action = QAction(QIcon.fromTheme("folder-new"), "Новая папка", self)
            new_folder_action.triggered.connect(self.new_folder_requested.emit)
            empty_menu.addAction(new_folder_action)

            paste_action = QAction(QIcon.fromTheme("edit-paste"), "Вставить", self)
            paste_action.setEnabled(len(self._clipboard_items) > 0)
            paste_action.triggered.connect(self._on_paste)
            empty_menu.addAction(paste_action)

            if self._view_mode == "table":
                empty_menu.exec(self.table_view.viewport().mapToGlobal(pos))
            else:
                empty_menu.exec(self.icon_view.viewport().mapToGlobal(pos))
            return

        # Иначе – стандартное меню для выделенных элементов (без изменений)
        has_downloaded = any(getattr(item, 'is_downloaded', False) for item in items)
        has_not_downloaded = any(not getattr(item, 'is_downloaded', False) for item in items)
        has_outdated = any(
            getattr(item, 'is_downloaded', False) and not getattr(item, 'is_synced', False) for item in items)
        has_folder = any(item.is_dir for item in items)

        is_local = self._is_local_provider()
        is_root = self._is_mounts_root()

        if is_root or is_local:
            self.download_action.setEnabled(False)
            self.sync_action.setEnabled(False)
            self.update_action.setEnabled(False)
        else:
            has_files = any(not item.is_dir for item in items)
            self.download_action.setEnabled(has_selection and has_files)
            self.download_action.setVisible(has_selection)
            self.save_as_action.setEnabled(has_selection and has_files)
            self.save_as_action.setVisible(has_selection)
            self.sync_action.setEnabled(has_selection and has_downloaded)
            self.sync_action.setVisible(has_selection)
            self.update_action.setEnabled(has_selection and has_outdated)
            self.update_action.setVisible(has_selection)
            self.public_link_action.setVisible(not is_local and not is_root)
            self.public_link_action.setEnabled(not is_local and not is_root and len(items) == 1)

        if is_root:
            self.copy_action.setEnabled(False)
            self.paste_action.setEnabled(False)
            self.rename_action.setEnabled(False)
            self.delete_action.setEnabled(False)
        else:
            self.copy_action.setEnabled(has_selection and not has_folder)
            self.paste_action.setEnabled(has_selection)
            self.rename_action.setEnabled(has_selection and len(items) == 1)
            self.delete_action.setEnabled(has_selection)

        if self._view_mode == "table":
            self.context_menu.exec(self.table_view.viewport().mapToGlobal(pos))
        else:
            self.context_menu.exec(self.icon_view.viewport().mapToGlobal(pos))

    def _on_public_link(self):
        items = self.get_selected_items()
        if len(items) == 1:
            self.public_link_requested.emit(items[0].path)

    def _on_save_as(self):
        """Обработчик для сохранить как """
        items = self.get_selected_items()
        # Фильтруем только файлы (не папки)
        files_to_save = [item for item in items if not item.is_dir]
        if files_to_save:
            self.save_as_requested.emit(files_to_save)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Проверяем, что перетаскивают именно локальные файлы."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        """Обрабатываем сброс файлов"""
        mime_data = event.mimeData()

        if mime_data.hasUrls():
            event.acceptProposedAction()

            local_paths = []
            for url in mime_data.urls():
                if url.isLocalFile():
                    local_paths.append(url.toLocalFile())

            if local_paths:
                print(f"DEBUG: Dropped {len(local_paths)} files: {local_paths}")
                self.files_dropped.emit(local_paths)
        else:
            event.ignore()
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