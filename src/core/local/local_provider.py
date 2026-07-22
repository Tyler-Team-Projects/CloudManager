"""Реализация BaseCloudProvider для локальной файловой системы."""
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Optional
from datetime import datetime

import psutil

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.common.base_provider import BaseCloudProvider
from api.common.models import CloudFile
from api.common.exceptions import CloudNotFoundError, CloudError

class LocalFileSystemProvider(BaseCloudProvider):
    """Провайдер локальной ФС, реализующий интерфейс BaseCloudProvider."""

    MOUNTS_ROOT = "mounts://"

    def __init__(self):
        """Инициализация провайдера."""
        self._current_path = str(Path.home())
        self._mounts_cache = None
        self._mounts_cache_time = 0
        self._show_hidden = False

    def set_show_hidden(self, show: bool):
        self._show_hidden = show

    def refresh(self) -> None:
        """Принудительное обновление кэша."""
        self._mounts_cache = None
        self._mounts_cache_time = 0

    # ============ Реализация абстрактных методов BaseCloudProvider ============

    def login(self, token: str = None) -> bool:
        """Локальная ФС всегда доступна."""
        return True

    def list_files(self, path: str = "/") -> List[CloudFile]:
        """Получить список файлов."""
        if path == self.MOUNTS_ROOT:
            return self._list_mount_points()

        # Нормализуем путь
        if path == "/":
            path = str(Path.home())

        p = Path(path)
        if not p.exists():
            raise CloudNotFoundError(f"Путь не найден: {path}")

        items = []
        try:
            for entry in p.iterdir():
                stat = entry.stat()
            for entry in p.iterdir():
                if not self._show_hidden and entry.name.startswith('.'):
                    continue

                # Определяем MIME-тип
                mime_type = None
                if entry.is_dir():
                    mime_type = "inode/directory"
                else:
                    ext = entry.suffix.lower()
                    mime_map = {
                        '.pdf': 'application/pdf',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.png': 'image/png',
                        '.txt': 'text/plain',
                        '.py': 'text/x-python',
                        '.mp4': 'video/mp4',
                        '.mp3': 'audio/mpeg',
                    }
                    mime_type = mime_map.get(ext, 'application/octet-stream')

                items.append(CloudFile(
                    name=entry.name,
                    path=str(entry),
                    is_dir=entry.is_dir(),
                    size=stat.st_size if not entry.is_dir() else 0,
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                    mime_type=mime_type,
                    file_id=str(entry)
                ))
        except PermissionError:
            pass

        # Сортировка: папки первые, потом по имени
        items.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        return items

    def upload_file(self, local_path: str, remote_path: str,
                    progress_callback=None) -> bool:
        """Копирование файла (локально)."""
        try:
            # Создаём родительскую папку, если нужно
            Path(remote_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local_path, remote_path)
            if progress_callback:
                total = Path(local_path).stat().st_size
                progress_callback(total, total)
            return True
        except Exception as e:
            raise CloudError(f"Ошибка копирования: {e}")

    def download_file(self, remote_path: str, local_path: str,
                      progress_callback=None) -> bool:
        """Копирование файла (симметрично upload)."""
        return self.upload_file(remote_path, local_path, progress_callback)

    def delete_file(self, remote_path: str) -> bool:
        """Удаление файла/папки."""
        p = Path(remote_path)
        if not p.exists():
            raise CloudNotFoundError(f"Файл не найден: {remote_path}")

        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            return True
        except Exception as e:
            raise CloudError(f"Ошибка удаления: {e}")

    def move_file(self, src: str, dst: str) -> bool:
        """Перемещение файла."""
        try:
            shutil.move(src, dst)
            return True
        except Exception as e:
            raise CloudError(f"Ошибка перемещения: {e}")

    def create_folder(self, remote_path: str) -> bool:
        """Создание папки."""
        try:
            Path(remote_path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            raise CloudError(f"Ошибка создания папки: {e}")

    def get_public_link(self, remote_path: str) -> Optional[str]:
        """Для локальной ФС не поддерживается."""
        return None

    def delete_public_link(self, remote_path: str) -> bool:
        """Для локальной ФС не поддерживается."""
        return False

    def get_thumbnail(self, remote_path: str, size: str = "S") -> Optional[bytes]:
        """Для локальной ФС не поддерживается."""
        return None

    # ============ Вспомогательные методы ============

    def _get_mount_points(self) -> List[dict]:
        """Получить список точек монтирования."""
        now = time.time()

        # Кэш на 2 секунды
        if self._mounts_cache and (now - self._mounts_cache_time) < 2:
            return self._mounts_cache

        mounts = []
        for partition in psutil.disk_partitions():
            if partition.fstype in ['squashfs', 'tmpfs', 'devtmpfs', 'proc', 'sysfs']:
                continue
            if partition.mountpoint.startswith('/snap'):
                continue
            if partition.mountpoint.startswith('/boot'):
                continue

            try:
                usage = psutil.disk_usage(partition.mountpoint)
                mounts.append({
                    'mountpoint': partition.mountpoint,
                    'device': partition.device,
                    'fstype': partition.fstype,
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free
                })
            except (PermissionError, OSError):
                continue

        def sort_key(m):
            mp = m['mountpoint']
            if mp == '/':
                return (0, mp)
            elif mp == '/home':
                return (1, mp)
            elif mp.startswith('/home/'):
                return (2, mp)
            elif mp.startswith('/media/'):
                return (3, mp)
            else:
                return (4, mp)

        mounts.sort(key=sort_key)
        self._mounts_cache = mounts
        self._mounts_cache_time = now
        return mounts

    def _list_mount_points(self) -> List[CloudFile]:
        """Список точек монтирования как CloudFile."""
        items = []

        # Домашняя папка
        home = Path.home()
        items.append(CloudFile(
            name="🏠 Домашняя папка",
            path=str(home),
            is_dir=True,
            size=0,
            modified_at=None,
            mime_type="inode/directory",
            file_id=str(home)
        ))

        # Точки монтирования
        for mount in self._get_mount_points():
            mp = mount['mountpoint']
            if mp == '/':
                name = "💻 Корень (/)"
            elif mp == '/home':
                name = "👥 /home"
            elif mp.startswith('/media/'):
                name = f"💾 {Path(mp).name}"
            else:
                name = f"📁 {mp}"

            items.append(CloudFile(
                name=name,
                path=mp,
                is_dir=True,
                size=mount['total'],
                modified_at=None,
                mime_type="inode/directory",
                file_id=mp
            ))

        return items

    # ============ Дополнительные методы для UI ============

    def get_mounts_root(self) -> str:
        """Вернуть специальный путь для списка дисков."""
        return self.MOUNTS_ROOT

    def open_file(self, path: str) -> bool:
        """Открыть файл в системном приложении."""
        try:
            subprocess.run(['xdg-open', path], check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Для Windows используем os.startfile
            try:
                os.startfile(path)
                return True
            except:
                return False

    def is_directory(self, path: str) -> bool:
        """Проверить, является ли путь директорией."""
        if path == self.MOUNTS_ROOT:
            return True
        return Path(path).is_dir()

    def get_parent_path(self, path: str) -> Optional[str]:
        """Получить родительский путь."""
        if path == self.MOUNTS_ROOT:
            return None

        for mount in self._get_mount_points():
            if path == mount['mountpoint']:
                return self.MOUNTS_ROOT

        parent = str(Path(path).parent)
        return parent if parent != path else None

    def get_provider_name(self) -> str:
        """Имя провайдера для UI."""
        return "Локальные диски"

    def get_root_path(self) -> str:
        """Корневой путь провайдера."""
        return self.MOUNTS_ROOT

    def search_files(self, path: str, query: str, recursive: bool = True) -> List[CloudFile]:
        """Рекурсивный поиск файлов."""
        if path == self.MOUNTS_ROOT:
            return []

        p = Path(path)
        if not p.exists():
            return []

        results = []
        query_lower = query.lower()

        try:
            if recursive:
                # Рекурсивный обход
                for root, dirs, files in os.walk(p):
                    # Ограничиваем глубину для производительности
                    depth = len(Path(root).relative_to(p).parts)
                    if depth > 5:  # Максимальная глубина поиска
                        continue

                    # Проверяем папки
                    for dir_name in dirs:
                        if query_lower in dir_name.lower():
                            full_path = Path(root) / dir_name
                            results.append(self._create_cloud_file(full_path))

                    # Проверяем файлы
                    for file_name in files:
                        if query_lower in file_name.lower():
                            full_path = Path(root) / file_name
                            results.append(self._create_cloud_file(full_path))
            else:
                # Только текущая директория
                for entry in p.iterdir():
                    if query_lower in entry.name.lower():
                        results.append(self._create_cloud_file(entry))

        except (PermissionError, OSError):
            pass

        # Сортировка: папки первые
        results.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        return results

    def _create_cloud_file(self, entry: Path) -> CloudFile:
        """Создание CloudFile из Path."""
        stat = entry.stat() if entry.exists() else None

        mime_type = "inode/directory" if entry.is_dir() else None
        if not entry.is_dir():
            ext = entry.suffix.lower()
            mime_map = {
                '.pdf': 'application/pdf',
                '.jpg': 'image/jpeg',
                '.png': 'image/png',
                '.txt': 'text/plain',
                '.py': 'text/x-python',
            }
            mime_type = mime_map.get(ext, 'application/octet-stream')

        return CloudFile(
            name=entry.name,
            path=str(entry),
            is_dir=entry.is_dir(),
            size=stat.st_size if stat and not entry.is_dir() else 0,
            modified_at=datetime.fromtimestamp(stat.st_mtime) if stat else None,
            mime_type=mime_type,
            file_id=str(entry)
        )

    def rename_file(self, old_path: str, new_path: str) -> bool:

        Path(old_path).rename(Path(new_path))
        return True

    def copy_file(self, src: str, dst: str) -> bool:
        """Скопировать файл локально."""
        import shutil
        src_path = Path(src)
        dst_path = Path(dst)

        if src_path.is_dir():
            shutil.copytree(src_path, dst_path)
        else:
            shutil.copy2(src_path, dst_path)
        return True