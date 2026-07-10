import yadisk
from loguru import logger
from ...common.exceptions import (
    CloudAuthError, CloudNotFoundError, CloudQuotaError,
    CloudRateLimitError, CloudAPIError
)


class YandexDiskClient:
    def __init__(self, token: str = None):
        if token:
            token = token.strip()
        self.api = yadisk.YaDisk(token=token)

    def _handle_exception(self, e: Exception):
        if isinstance(e, yadisk.exceptions.UnauthorizedError):
            raise CloudAuthError("Невалидный токен")
        if isinstance(e, yadisk.exceptions.NotFoundError):
            raise CloudNotFoundError("Объект не найден")
        if isinstance(e, yadisk.exceptions.InsufficientStorageError):
            raise CloudQuotaError("Нет места на диске")
        if isinstance(e, yadisk.exceptions.TooManyRequestsError):
            raise CloudRateLimitError("Превышен лимит запросов")

        logger.error(f"YandexDisk API Error: {e}")
        raise CloudAPIError(str(e))

    def list_dir(self, path: str):
        try:
            return self.api.listdir(path, timeout=30)
        except Exception as e:
            self._handle_exception(e)

    def upload(self, local_path, remote_path, callback=None):
        try:
            self.api.upload(local_path, remote_path, overwrite=True, callback=callback, timeout=30)
        except Exception as e:
            self._handle_exception(e)

    def download(self, remote_path, local_path, callback=None):
        try:
            self.api.download(remote_path, local_path, callback=callback, timeout=30)
        except Exception as e:
            self._handle_exception(e)

    def delete(self, path: str):
        try:
            self.api.remove(path, permanently=True, timeout=30)
        except Exception as e:
            self._handle_exception(e)

    def move(self, src: str, dst: str):
        try:
            self.api.move(src, dst, overwrite=True, timeout=30)
        except Exception as e:
            self._handle_exception(e)

    def mkdir(self, path: str):
        try:
            self.api.mkdir(path, timeout=30)
        except Exception as e:
            self._handle_exception(e)

    def publish(self, path: str) -> str:
        try:
            self.api.publish(path, timeout=30)
            return self.api.get_meta(path).public_url
        except Exception as e:
            self._handle_exception(e)

    def unpublish(self, path: str):
        try:
            self.api.unpublish(path, timeout=30)
        except Exception as e:
            self._handle_exception(e)

    def get_preview(self, path: str, size: str) -> bytes:
        try:
            response = self.api.get_preview(path, size=size, timeout=30)
            return response.read()
        except Exception as e:
            self._handle_exception(e)