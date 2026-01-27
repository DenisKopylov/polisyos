# Логгер настраивается в config.py для избежания циклических импортов
from __future__ import annotations

try:
    from loguru import logger  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    import logging

    logger = logging.getLogger("polisyos")


def get_logger(module_name: str):
    """
    Возвращает логгер с контекстом модуля.

    Предпочтительно использует loguru (если доступен), иначе падает назад на стандартный logging.
    """
    try:
        return logger.bind(module=module_name)
    except AttributeError:  # pragma: no cover
        import logging

        return logging.getLogger(module_name)
