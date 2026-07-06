import io
import time
import yadisk
from typing import List, Optional, Dict
from loguru import logger

from .client import YandexDiskClient
from ...common.base_provider import BaseCloudProvider
from ...common.models import CloudFile
from ...common.exceptions import CloudAPIError, CloudQuotaError


class YandexDiskProvider(BaseCloudProvider):

    def __init__(self, token: str = None):
        self.client = YandexDiskClient(token)
        self._cache: Dict[str, tuple] = {}
        self._cache_ttl = 30

    def login(self, token: str) -> bool:
        if not token:
            return False
        clean_token = token.strip()
        self.client.api.token = clean_token
        try:
            is_valid = self.client.api.check_token()
            if is_valid:
                logger.info("Успешный вход в Яндекс.Диск")
            return is_valid
        except Exception as e:
            logger.error(f"Ошибка входа: {e}")
            return False

    def list_files(self, path: str = "/") -> List[CloudFile]:
        now = time.time()

        if path in self._cache:
            ts, data = self._cache[path]
            if now - ts < self._cache_ttl:
                return data

        try:
            resources = self.client.list_dir(path)
            result = [
                CloudFile(
                    name=res.name,
                    path=res.path.replace("disk:", ""),
                    is_dir=res.type == "dir",
                    size=res.size or 0,
                    modified_at=res.modified,
                    mime_type=getattr(res, 'mime_type', None),
                    file_id=getattr(res, 'resource_id', None),
                    hash=getattr(res, 'md5', None),
                    hash_type="md5"
                ) for res in resources
            ]
            self._cache[path] = (now, result)
            return result
        except Exception as e:
            raise CloudAPIError(f"Ошибка при получении списка файлов: {e}")

    def create_folder(self, remote_path: str) -> bool:
        try:
            self.client.mkdir(remote_path)
            self._cache.clear()
            return True
        except yadisk.exceptions.DirectoryExistsError:
            return True
        except Exception as e:
            raise CloudAPIError(f"Не удалось создать папку: {e}")

    def upload_file(self, local_path: str, remote_path: str, progress_callback=None) -> bool:
        try:
            logger.info(f"Загрузка файла: {local_path} -> {remote_path}")
            self.client.upload(local_path, remote_path, callback=progress_callback)
            self._cache.clear()
            return True
        except yadisk.exceptions.InsufficientStorageError:
            raise CloudQuotaError("Недостаточно места на Яндекс.Диске")
        except Exception as e:
            raise CloudAPIError(f"Ошибка загрузки файла: {e}")

    def create_text_file(self, content: str, remote_path: str) -> bool:

        try:
            logger.info(f"Создание текстового файла в облаке: {remote_path}")
            file_data = io.BytesIO(content.encode('utf-8'))

            self.client.api.upload(file_data, remote_path, overwrite=True)
            self._cache.clear()
            return True
        except Exception as e:
            raise CloudAPIError(f"Ошибка при создании текстового файла: {e}")

    def download_file(self, remote_path: str, local_path: str, progress_callback=None) -> bool:
        try:
            logger.info(f"Скачивание файла: {remote_path} -> {local_path}")
            self.client.download(remote_path, local_path, callback=progress_callback)
            return True
        except Exception as e:
            raise CloudAPIError(f"Ошибка при скачивании файла: {e}")


    def delete_file(self, remote_path: str) -> bool:
        try:
            self.client.delete(remote_path)
            self._cache.clear()
            return True
        except Exception as e:
            raise CloudAPIError(f"Ошибка при удалении: {e}")

    def move_file(self, src: str, dst: str) -> bool:
        try:
            self.client.move(src, dst)
            self._cache.clear()
            return True
        except Exception as e:
            raise CloudAPIError(f"Ошибка при перемещении: {e}")

    def get_public_link(self, remote_path: str) -> Optional[str]:
        return self.client.publish(remote_path)

    def delete_public_link(self, remote_path: str) -> bool:
        self.client.unpublish(remote_path)
        return True

    def get_thumbnail(self, remote_path: str, size: str = "S") -> Optional[bytes]:
        return self.client.get_preview(remote_path, size)

    def rename_file(self, old_path: str, new_path: str) -> bool:
        """Переименование файла."""
        try:
            self.client.move(old_path, new_path)
            self._cache.clear()
            return True
        except Exception as e:
            logger.error(f"Ошибка переименования: {e}")
            return False

    def copy_file(self, src: str, dst: str) -> bool:

        try:
            self.client.copy(src, dst)
            self._cache.clear()
            return True
        except Exception as e:
            logger.error(f"Ошибка копирования: {e}")
            return False