"""Фоновая синхронизация локальной папки с облаком."""
import time
import threading
from pathlib import Path
from typing import Optional, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from core.cache_manager import FolderCache
from core.logger import get_logger
from core.constants import App, Settings, Timeouts, Providers, Views

logger = get_logger('syns_watcher')


class CloudSyncHandler(FileSystemEventHandler):
    """Обработчик изменений файловой системы."""

    def __init__(self, cloud_bridge, debounce_sec: float = 2.0):
        self.cloud_bridge = cloud_bridge
        self.debounce_sec = debounce_sec
        self._pending_uploads: Set[str] = set()
        self._lock = threading.Lock()

    def _handle_change(self, path: str):
        """Обработка изменения файла с debounce."""
        time.sleep(self.debounce_sec)
        file_path = Path(path)

        if not file_path.exists():
            return

        if file_path.is_dir():
            return

        # Игнорируем скрытые файлы и временные
        if file_path.name.startswith('.') or file_path.name.endswith('~'):
            return

        # Игнорируем файлы в Downloads
        if 'Downloads' in file_path.parts:
            return

        try:
            rel_path = file_path.relative_to(self.cloud_bridge.local_path)
            remote_path = "/" + str(rel_path).replace("\\", "/")

            with self._lock:
                if remote_path in self._pending_uploads:
                    return
                self._pending_uploads.add(remote_path)

            # print(f"[SYNC] Uploading: {file_path.name}")
            self.cloud_bridge.upload_file(file_path, remote_path)

            with self._lock:
                self._pending_uploads.discard(remote_path)


        except ValueError as e:
            logger.error(f"[SYNC] Path error: {e}")
        except Exception as e:
            logger.error(f"[SYNC] Error uploading {path}: {e}")
            with self._lock:
                self._pending_uploads.discard(remote_path)

    def on_created(self, event):
        if not event.is_directory:
            threading.Thread(target=self._handle_change, args=(event.src_path,), daemon=True).start()

    def on_modified(self, event):
        if not event.is_directory:
            threading.Thread(target=self._handle_change, args=(event.src_path,), daemon=True).start()


class SyncWatcher:
    """Наблюдатель за изменениями и синхронизацией."""

    def __init__(self, cloud_bridge, local_path: Path, refresh_callback=None,
                 hash_update_callback=None):
        self.cloud_bridge = cloud_bridge
        self.local_path = local_path
        self.refresh_callback = refresh_callback
        self.observer: Optional[Observer] = None
        self.handler: Optional[CloudSyncHandler] = None
        self.running = False
        self.cloud_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.hash_update_callback = hash_update_callback
        self.check_interval = Timeouts.SYNC_DEFAULT


    def set_interval(self, seconds: int):
        """Изменить интервал проверки облака."""
        self.check_interval = seconds

    def start_background(self):
        """Запуск фоновой синхронизации."""
        if self.running:
            return

        self.running = True
        self._stop_event.clear()

        self.handler = CloudSyncHandler(self.cloud_bridge)
        self.observer = Observer()
        self.observer.schedule(self.handler, str(self.local_path), recursive=True)
        self.observer.start()

        self.cloud_thread = threading.Thread(target=self._check_cloud_loop, daemon=True)
        self.cloud_thread.start()

        logger.info("[SYNC] Background sync started")

    def stop(self):
        """Остановка синхронизации."""
        self.running = False
        self._stop_event.set()

        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2)

        logger.info("[SYNC] Background sync stopped")

    def is_running(self) -> bool:
        """Проверка статуса."""
        return self.running

    def _preload_subfolders(self):
        """Фоновая предзагрузка кеша для подпапок облака."""
        if not self.cloud_bridge.has_token():
            return
        cache = FolderCache()
        try:
            root_items = self.cloud_bridge.provider.list_files("/")
            folders = [item for item in root_items if item.is_dir]
            for folder in folders:
                sub_items = self.cloud_bridge.provider.list_files(folder.path)
                cache.save(folder.path, Providers.CLOUD, sub_items)
                logger.debug(f"[SYNC] Preloaded {len(sub_items)} items into cache for {folder.path}")
        except Exception as e:
            logger.error(f"[SYNC] Preload error: {e}")

    def _check_cloud_loop(self):
        """Фоновый цикл проверки облака."""
        last_preload = 0
        while not self._stop_event.is_set():
            time.sleep(self.check_interval)
            if not self.cloud_bridge.has_token():
                continue
            try:
                # Обычная синхронизация
                result = self.cloud_bridge.sync_cloud_to_local("/")
                # Раз в 5 минут предзагружаем подпапки
                now = time.time()
                if now - last_preload > Timeouts.PRELOAD:
                    self._preload_subfolders()
                    last_preload = now
            except Exception as e:
                logger.error(f"[SYNC] Cloud check error: {e}")
                time.sleep(Timeouts.SYNC_RETRY_DELAY)