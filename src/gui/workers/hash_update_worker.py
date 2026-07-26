"""Фоновый воркер для обновления хешей облачных файлов."""
from PyQt6.QtCore import QThread, pyqtSignal
from typing import List
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from api.common.models import CloudFile
from core.cache_manager import FolderCache


class HashUpdateWorker(QThread):
    finished = pyqtSignal()

    def __init__(self, cloud_bridge, files: List[CloudFile], folder_cache: FolderCache):
        super().__init__()
        self.cloud_bridge = cloud_bridge
        self.files = files
        self.folder_cache = folder_cache
        self._is_interrupted = False

    def run(self) -> None:
        for f in self.files:
            if self._is_interrupted:
                break
            if f.is_dir or not getattr(f, 'is_downloaded', False):
                continue
            try:
                sync_info = self.cloud_bridge.check_file_sync(f.path)
                if sync_info:
                    self.folder_cache.save_hashes(
                        f.path,
                        sync_info.get('remote_hash'),
                        sync_info.get('local_hash')
                    )
            except Exception:
                pass
        self.finished.emit()