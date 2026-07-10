"""Воркер для скачивания файлов в фоне."""
import os
import time
import threading
import requests
from PyQt6.QtCore import QThread, pyqtSignal
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from api.common.base_provider import BaseCloudProvider


class DownloadWorker(QThread):
    """Фоновое скачивание файла."""

    progress = pyqtSignal(int, int)  # current_size, total_size
    finished = pyqtSignal(bool, str, str)  # success, local_path, remote_path  # ← ИЗМЕНЕНО
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, provider: BaseCloudProvider, remote_path: str,
                 local_path: str, total_size: int = 0):
        super().__init__()
        self.provider = provider
        self.remote_path = remote_path
        self.local_path = local_path
        self.total_size = total_size
        self._is_cancelled = False

    def run(self) -> None:
        try:
            download_result = {"success": False, "error": None, "done": False}

            def do_download():
                try:
                    self.provider.download_file(
                        self.remote_path,
                        self.local_path,
                        None
                    )
                    if not self._is_cancelled:
                        download_result["success"] = True
                except Exception as e:
                    # Не эмитим error здесь, просто сохраняем ошибку
                    download_result["error"] = str(e)
                    # Удаляем частично скачанный файл
                    if os.path.exists(self.local_path):
                        try:
                            os.remove(self.local_path)
                        except OSError:
                            pass
                finally:
                    download_result["done"] = True

            download_thread = threading.Thread(target=do_download, daemon=True)
            download_thread.start()

            # Отслеживаем размер файла
            last_size = 0
            while not download_result["done"] and not self._is_cancelled:
                if os.path.exists(self.local_path):
                    current_size = os.path.getsize(self.local_path)
                    if current_size != last_size:
                        self.progress.emit(current_size, self.total_size)
                        last_size = current_size
                time.sleep(0.3)

            if self._is_cancelled:
                self._force_stop_download()
                if os.path.exists(self.local_path):
                    try:
                        os.remove(self.local_path)
                    except:
                        pass
                self.cancelled.emit()
                return

            download_thread.join(timeout=2)

            if not download_result["error"] and download_result["success"] and self.total_size > 0:
                if os.path.exists(self.local_path):
                    actual_size = os.path.getsize(self.local_path)
                    if actual_size < self.total_size:
                        download_result["error"] = f"Неполное скачивание: {actual_size}/{self.total_size} байт"
                        download_result["success"] = False
                        # Удаляем недокачанный файл
                        try:
                            os.remove(self.local_path)
                        except OSError:
                            pass

            if os.path.exists(self.local_path) and not self._is_cancelled and download_result["success"]:
                final_size = os.path.getsize(self.local_path)
                self.progress.emit(final_size, self.total_size)

            # Эмитируем сигнал в зависимости от результата
            if download_result["error"]:
                self.error.emit(download_result["error"])
            elif not self._is_cancelled and download_result["success"]:
                self.finished.emit(True, self.local_path, self.remote_path)

        except Exception as e:
            if not self._is_cancelled:
                self.error.emit(str(e))

    def _force_stop_download(self):
        """Принудительная остановка скачивания."""
        # Удаляем файл во время скачивания - это может прервать операцию
        if os.path.exists(self.local_path):
            try:
                os.remove(self.local_path)
            except:
                pass

        # Пытаемся закрыть все открытые соединения
        try:
            import gc
            gc.collect()
        except:
            pass

    def cancel(self):
        """Отменить скачивание."""
        self._is_cancelled = True