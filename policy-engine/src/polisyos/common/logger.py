# Логгер настраивается в config.py для избежания циклических импортов
from __future__ import annotations


def get_logger(module_name: str):
    """
    Возвращает логгер с контекстом модуля.

    Предпочтительно использует loguru (если доступен), иначе падает назад на стандартный logging.
    """
    try:
        from loguru import logger  # type: ignore

        return logger.bind(module=module_name)
    except ModuleNotFoundError:  # pragma: no cover
        import logging

        return logging.getLogger(module_name)
