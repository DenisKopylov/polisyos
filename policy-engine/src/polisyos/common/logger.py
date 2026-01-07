# Логгер настраивается в config.py для избежания циклических импортов
from loguru import logger


def get_logger(module_name: str):
    """
    Возвращает логгер с контекстом модуля.
    Пример: log = get_logger(__name__)
    """
    return logger.bind(module=module_name)
