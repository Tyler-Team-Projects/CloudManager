from PyQt6.QtCore import QThread, pyqtSignal
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from api.common.base_provider import BaseCloudProvider


class DeleteWorker(QThread):
    """Фоновое удаление файла."""

    finished = pyqtSignal(bool, str, int)  # success, path
    error = pyqtSignal(str, str)      # error_message, path

    def __init__(self, provider: BaseCloudProvider, remote_path: str, file_size: int = 0):
        super().__init__()
        self.provider = provider
        self.remote_path = remote_path
        self.file_size = file_size

    def run(self) -> None:
        """Выполнение удаления."""
        try:
            success = self.provider.delete_file(self.remote_path)
            self.finished.emit(success, self.remote_path, self.file_size)
        except Exception as e:
            self.error.emit(str(e), self.remote_path)