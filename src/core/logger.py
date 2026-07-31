"""Настройка логирования для приложения."""
import logging
import sys
from pathlib import Path


def setup_logger(name: str = "cloud_manager") -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Файл: все уровни (DEBUG, INFO, WARNING, ERROR)
    log_dir = Path.home() / '.cloud_manager'
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / 'cloud.log'
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


# Создаём основной логгер для всего приложения
logger = setup_logger('cloud_manager')


def get_logger(name: str) -> logging.Logger:
    """Получить логгер с именем модуля."""
    return logging.getLogger(f'cloud_manager.{name}')