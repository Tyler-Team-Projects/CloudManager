"""Воркер для загрузки файлов в облако."""
from pathlib import Path
import sys
from PyQt6.QtCore import QThread, pyqtSignal
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from api.common.base_provider import BaseCloudProvider


class UploadWorker(QThread):
    """Фоновая загрузка файла."""

    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(bool, str)  # success, remote_path
    error = pyqtSignal(str)

    def __init__(self, provider: BaseCloudProvider, local_path: Path,
                 remote_path: str):
        super().__init__()
        self.provider = provider
        self.local_path = local_path
        self.remote_path = remote_path

    def run(self) -> None:
        """Выполнение загрузки."""
        try:
            def progress_callback(current: int, total: int):
                self.progress.emit(current, total)

            success = self.provider.upload_file(
                str(self.local_path),
                self.remote_path,
                progress_callback
            )
            self.finished.emit(success, self.remote_path)
        except Exception as e:
            self.error.emit(str(e))