"""
Мост между консольным проводником и облачным API
Обеспечивает работу с облаком как с обычной папкой
"""
import shutil
from datetime import datetime
import sys
import subprocess
from pathlib import Path

from .cloud.syns_watcher import SyncWatcher

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from api.manager import CloudManager
from api.providers.yadisk.provider import YandexDiskProvider
from api.common.exceptions import CloudAuthError, CloudNotFoundError


class CloudBridge:
    """Мост для работы с облачным диском как с обычной папкой"""

    def __init__(self, local_path: Path):
        """
        local_path: Локальная папка, где будут кэшироваться файлы (например, /home/user/YandexDisk)
        """
        self.local_path = local_path
        self.downloads_path = local_path / 'Downloads'
        self.downloads_path.mkdir(parents=True, exist_ok=True)
        self.manager = CloudManager()
        self.provider = None
        self.current_path = "/"
        self._sync_watcher: Optional[SyncWatcher] = None
        self._init_provider()

        self.metadata_file = local_path / '.download_metadata.json'
        self.download_metadata = self._load_metadata()

        if self.has_token():
            print("[SYNC] Token found, starting sync from __init__")
            self.start_sync()

    def _init_provider(self):
        """Инициализация провайдера Яндекс Диска"""
        self.manager.register_provider("yandex", YandexDiskProvider)
        # self.manager = CloudManager
        token = self._load_token()

        if token:
            try:
                provider = YandexDiskProvider()
                if provider.login(token):
                    self.provider = provider
                    print("Яндекс Диск подключен")
                else:
                    print("Не удалось подключиться к Яндекс Диску")
                    self.provider = None
                    self._delete_token_file()
            except Exception as e:
                print(f"Ошибка подключения: {e}")
                self.provider = None
        else:
            self.provider = None

    def _delete_token_file(self):
        """Удаление файла с токеном."""
        token_file = Path.home() / '.core-disko' / 'yandex.token'
        if token_file.exists():
            token_file.unlink()

    def _load_token(self) -> str:
        """Загрузить токен из файла"""
        token_file = Path.home() / '.core-disko' / 'yandex.token'
        if token_file.exists():
            return token_file.read_text().strip()
        return None

    def save_token(self, token: str):
        """Сохранить токен"""
        token_file = Path.home() / '.core-disko' / 'yandex.token'
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(token.strip())
        token_file.chmod(0o600)

        # Переподключаем провайдера
        self._init_provider()

        # if self.has_token():
        #     self.start_sync()
    def has_token(self) -> bool:
        """Проверить наличие токена и подключения"""
        return self.provider is not None

    def _format_size(self, size: int) -> str:
        """Форматирование размера"""
        if size == 0:
            return ""

        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    def list_directory(self, path: str = None) -> list:
        """
        Получить содержимое облачной папки (без скачивания файлов)
        Returns:
            Список словарей с ключами: name, type, size, is_dir, downloaded, path
        """
        if not self.provider:
            return [{
                'name': 'Токен не настроен. Выполните: token_setup',
                'type': '[???]',
                'size': '',
                'is_dir': False,
                'downloaded': False,
                'path': ''
            }]

        target_path = path if path else self.current_path

        try:
            files = self.provider.list_files(target_path)

            result = []
            for f in files:

                local_file = self.local_path / f.path.lstrip('/')

                result.append({
                    'name': f.name,
                    'type': '[DIR]' if f.is_dir else '[FILE]',
                    'size': self._format_size(f.size) if not f.is_dir else '',
                    'is_dir': f.is_dir,
                    'downloaded': local_file.exists() if not f.is_dir else False,
                    'path': f.path
                })

            # Сортировка: папки первые
            result.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
            return result

        except CloudNotFoundError:
            return [{
                'name': 'Папка не найдена',
                'type': '[???]',
                'size': '',
                'is_dir': False,
                'downloaded': False,
                'path': ''
            }]
        except Exception as e:
            return [{
                'name': f'Ошибка: {e}',
                'type': '[???]',
                'size': '',
                'is_dir': False,
                'downloaded': False,
                'path': ''
            }]

    def change_directory(self, path: str) -> bool:
        """
        Переход в другую облачную папку
        """
        if not self.provider:
            return False

        # Переход в корень
        if path == '/' or path == '':
            self.current_path = '/'
            return True

        # Переход на уровень выше
        if path == '..':
            if self.current_path == '/':
                return True
            # Поднимаемся на уровень выше
            parts = self.current_path.rstrip('/').split('/')
            if len(parts) <= 2:
                self.current_path = '/'
            else:
                self.current_path = '/' + '/'.join(parts[:-1])
            return True

        # Переход в подпапку
        if path.startswith('/'):
            new_path = path
        else:
            new_path = self.current_path.rstrip('/') + '/' + path.lstrip('/')

        new_path = new_path.replace('//', '/')

        # Проверяем, что папка существует
        try:
            files = self.provider.list_files(new_path)
            self.current_path = new_path
            return True
        except CloudNotFoundError:
            return False
        except Exception:
            return False

    def get_current_path(self) -> str:
        """Вернуть текущий путь в облаке"""
        return self.current_path if self.current_path != '/' else '/'

    def download_file(self, remote_path: str, local_path: Path = None, progress_callback=None) -> bool:
        """
        Скачать файл из облака в папку Downloads
        """
        if not self.provider:
            print("Облако не подключено")
            return False

        # Если путь не указан - сохраняем в Downloads
        if local_path is None:
            local_path = self._get_download_path(remote_path)

        # Создаём родительские папки
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Для GUI не спрашиваем перезапись
        if local_path.exists():
            # Просто перезаписываем в GUI режиме
            pass

        try:
            print(f"Скачивание {remote_path}...")
            print(f"Сохранение в: {local_path}")

            # Используем переданный callback или внутренний
            callback = progress_callback if progress_callback else self._progress_callback

            # Скачиваем с прогрессом
            self.provider.download_file(remote_path, str(local_path), callback)

            # Сохраняем метаданные
            file_size = local_path.stat().st_size if local_path.exists() else 0
            self.download_metadata[str(local_path)] = {
                'remote_path': remote_path,
                'downloaded_at': datetime.now().isoformat(),
                'size': file_size,
                'name': local_path.name
            }
            self._save_metadata()

            print(f"\nСкачано: {local_path}")
            return True
        except Exception as e:
            print(f"\nОшибка скачивания: {e}")
            return False

    def _get_download_path(self, remote_path: str) -> Path:
        """
        Определить путь для сохранения файла в Downloads
        """
        filename = Path(remote_path).name

        download_path = self.downloads_path / filename
        if download_path.exists():
            name_without_ext = filename.rsplit('.', 1)[0]
            ext = f".{filename.rsplit('.', 1)[1]}" if '.' in filename else ''
            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"{name_without_ext}_{date_str}{ext}"
            download_path = self.downloads_path / new_filename

        return download_path

    def _progress_callback(self, current: int, total: int):
        """Callback для отображения прогресса скачивания"""
        if total > 0:
            percent = int(current / total * 100)
            # Используем \r для обновления в одной строке
            print(f"\rПрогресс: [{percent}%] {current}/{total} байт", end="", flush=True)

    def show_downloads(self) -> str:
        """Показать список скачанных файлов"""
        if not self.downloads_path.exists():
            return "Папка Downloads пуста"

        files = [f for f in self.downloads_path.iterdir() if f.is_file()]
        if not files:
            return "Папка Downloads пуста"

        result = "\nСКАЧАННЫЕ ФАЙЛЫ (YandexDisk/Downloads):\n"
        result += "-" * 70 + "\n"

        for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True):
            size = self._format_size(f.stat().st_size)
            modified = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

            meta = self.download_metadata.get(str(f), {})
            source = meta.get('remote_path', 'неизвестно')

            result += f"{f.name:<35} {size:>10}  {modified}\n"
            result += f"   └─ источник: {source}\n"

        result += "-" * 70
        result += f"\nПапка: {self.downloads_path}"
        result += f"\nВсего файлов: {len(files)}"
        return result

    def clear_downloads(self, older_than_days: int = None) -> str:
        """Очистить папку Downloads"""
        files = [f for f in self.downloads_path.iterdir() if f.is_file()]

        if not files:
            return "Папка Downloads уже пуста"

        if older_than_days:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=older_than_days)
            deleted = 0
            for f in files:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < cutoff:
                    # Удаляем из метаданных
                    if str(f) in self.download_metadata:
                        del self.download_metadata[str(f)]
                    f.unlink()
                    deleted += 1
            self._save_metadata()
            return f"Удалено {deleted} файлов старше {older_than_days} дней"

        # Запрос подтверждения
        count = len(files)
        response = input(f"Удалить все {count} файлов из Downloads? (y/N): ")
        if response.lower() == 'y':
            for f in files:
                if str(f) in self.download_metadata:
                    del self.download_metadata[str(f)]
                f.unlink()
            self._save_metadata()
            return f"Удалено {count} файлов"
        return "Отменено"

    def _load_metadata(self) -> dict:
        """Загрузить метаданные о скачанных файлах"""
        if self.metadata_file.exists():
            import json
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_metadata(self):
        """Сохранить метаданные"""
        import json
        with open(self.metadata_file, 'w') as f:
            json.dump(self.download_metadata, f, indent=2, default=str)

    def open_file(self, filename: str) -> bool:
        """
        Открыть файл из облака (скачать если нужно)
        """
        if not self.provider:
            print("Облако не подключено")
            return False

        # Полный путь в облаке
        remote_path = self.current_path.rstrip('/') + '/' + filename.lstrip('/')
        remote_path = remote_path.replace('//', '/')

        # Локальный путь
        local_file = self.local_path / remote_path.lstrip('/')

        # Скачиваем если нет
        if not local_file.exists():
            if not self.download_file(remote_path, local_file):
                return False

        # Открываем файл
        try:
            subprocess.run(['xdg-open', str(local_file)], check=True)
            return True
        except FileNotFoundError:
            print("xdg-open не найден. Установите: sudo apt install xdg-utils")
            return False
        except Exception as e:
            print(f"Не удалось открыть {filename}: {e}")
            return False

    def upload_file(self, local_path: Path, remote_path: str = None, progress_callback = None) -> bool:
        """
        Загрузить файл в облако
        """
        if not self.provider:
            print("Облако не подключено")
            return False

        if remote_path is None:
            remote_path = self.current_path.rstrip('/') + '/' + local_path.name

        try:
            print(f"Загрузка {local_path} -> {remote_path}...")
            self.provider.upload_file(str(local_path), remote_path, progress_callback)
            print("Загружено")
            return True
        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            return False

    def create_folder(self, folder_name: str) -> bool:
        """
        Создать папку в облаке
        """
        if not self.provider:
            print("Облако не подключено")
            return False

        remote_path = self.current_path.rstrip('/') + '/' + folder_name.lstrip('/')
        remote_path = remote_path.replace('//', '/')

        try:
            self.provider.create_folder(remote_path)
            print(f"Папка '{folder_name}' создана")
            return True
        except Exception as e:
            print(f"Ошибка создания папки: {e}")
            return False

    def delete_file(self, filename: str) -> bool:
        """
        Удалить файл/папку в облаке
        """
        if not self.provider:
            print("Облако не подключено")
            return False

        remote_path = self.current_path.rstrip('/') + '/' + filename.lstrip('/')
        remote_path = remote_path.replace('//', '/')

        # Удаляем локальный кэш если есть
        local_file = self.local_path / remote_path.lstrip('/')
        if local_file.exists():
            if local_file.is_dir():
                import shutil
                shutil.rmtree(local_file)
            else:
                local_file.unlink()

        try:
            self.provider.delete_file(remote_path)
            print(f"'{filename}' удалён")
            return True
        except Exception as e:
            print(f"Ошибка удаления: {e}")
            return False

    def rename_file(self, old_path: str, new_path: str) -> bool:
        """Переименовать файл/папку в облаке."""
        if not self.provider:
            print("Облако не подключено")
            return False

        try:
            # Используем move_file для переименования
            self.provider.move_file(old_path, new_path)

            # Обновляем локальный кэш
            local_old = self.local_path / old_path.lstrip('/')
            local_new = self.local_path / new_path.lstrip('/')
            if local_old.exists():
                local_old.rename(local_new)

            print(f"Renamed '{old_path}' -> '{new_path}' in cloud")
            return True
        except Exception as e:
            print(f"Rename error: {e}")
            return False

    def sync_cloud_to_local(self, remote_path: str = "/") -> dict:
        """Проверить изменения в облаке (без скачивания)."""
        result = {'new': [], 'updated': [], 'deleted': []}

        if not self.has_token():
            return result

        try:
            remote_items = self.provider.list_files(remote_path)
            remote_files = {item.path: item for item in remote_items if not item.is_dir}

            # Проверяем новые и изменённые
            for path, item in remote_files.items():
                local_file = self.local_path / path.lstrip('/')

                if 'Downloads' in local_file.parts:
                    continue

                if not local_file.exists():
                    result['new'].append(item.name)
                else:
                    local_size = local_file.stat().st_size
                    if local_size != item.size:
                        result['updated'].append(item.name)

            return result
        except Exception as e:
            print(f"[SYNC] Cloud check error: {e}")
            return result

    def start_sync(self, refresh_callback=None) -> None:
        """Запуск фоновой синхронизации."""
        if not self.has_token():
            return

        from .cloud.syns_watcher import SyncWatcher

        if self._sync_watcher is None:
            self._sync_watcher = SyncWatcher(self, self.local_path, refresh_callback)

        if not self._sync_watcher.is_running():
            self._sync_watcher.start_background()
            print("[SYNC] Фоновая синхронизация запущена")

    def stop_sync(self) -> None:
        """Остановка фоновой синхронизации."""
        if self._sync_watcher:
            self._sync_watcher.stop()
            self._sync_watcher = None
            print("[SYNC] Фоновая синхронизация остановлена")

    def is_sync_running(self) -> bool:
        """Проверка статуса синхронизации."""
        return self._sync_watcher is not None and self._sync_watcher.is_running()