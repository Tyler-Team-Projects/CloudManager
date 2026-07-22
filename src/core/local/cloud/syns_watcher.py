"""Фоновая синхронизация локальной папки с облаком."""
import time
import threading
from pathlib import Path
from typing import Optional, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


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

            print(f"[SYNC] Uploading: {file_path.name}")
            self.cloud_bridge.upload_file(file_path, remote_path)

            with self._lock:
                self._pending_uploads.discard(remote_path)

        except ValueError as e:
            print(f"[SYNC] Path error: {e}")
        except Exception as e:
            print(f"[SYNC] Error uploading {path}: {e}")
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

    def __init__(self, cloud_bridge, local_path: Path, refresh_callback=None):
        self.cloud_bridge = cloud_bridge
        self.local_path = local_path
        self.refresh_callback = refresh_callback
        self.observer: Optional[Observer] = None
        self.handler: Optional[CloudSyncHandler] = None
        self.running = False
        self.cloud_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _check_cloud_loop(self):
        """Фоновый цикл проверки облака."""
        while not self._stop_event.is_set():
            time.sleep(30)

            if not self.cloud_bridge.has_token():
                continue

            try:
                result = self.cloud_bridge.sync_cloud_to_local("/")
                if result.get('new'):
                    print(f"[SYNC] New files: {result['new']}")
                if result.get('updated'):
                    print(f"[SYNC] Updated files: {result['updated']}")

                # Если есть изменения - вызываем callback для обновления GUI
                if (result.get('new') or result.get('updated')) and self.refresh_callback:
                    self.refresh_callback()

            except Exception as e:
                print(f"[SYNC] Cloud check error: {e}")
                time.sleep(10)

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

        print("[SYNC] Background sync started")

    def stop(self):
        """Остановка синхронизации."""
        self.running = False
        self._stop_event.set()

        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2)

        print("[SYNC] Background sync stopped")

    def is_running(self) -> bool:
        """Проверка статуса."""
        return self.running