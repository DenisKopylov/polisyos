"""
Конфигурация приложения Policy Engine.
Загружает настройки из переменных окружения и файлов конфигурации.
"""

import os
from pathlib import Path
from typing import Optional

from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """Основная конфигурация приложения"""

    # Базовые настройки
    app_name: str = Field(default="Policy Engine", description="Название приложения")
    version: str = Field(default="0.1.0", description="Версия приложения")
    debug: bool = Field(default=False, description="Режим отладки")

    # Настройки логирования
    log_level: str = Field(default="INFO", description="Уровень логирования")
    log_file: Optional[str] = Field(default=None, description="Файл для логирования")

    # Настройки JAX
    jax_platform: str = Field(default="cpu", description="Платформа JAX (cpu, gpu, metal)")

    # Настройки данных
    data_dir: str = Field(default="./data", description="Директория для данных")
    cache_dir: str = Field(default="./.cache", description="Директория для кэша")

    # API ключи (опционально)
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API ключ")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API ключ")

    # Настройки симуляции
    default_population_size: int = Field(
        default=1000, gt=0, description="Размер популяции по умолчанию"
    )
    default_time_steps: int = Field(
        default=100, gt=0, description="Количество шагов по умолчанию"
    )
    random_seed: int = Field(default=42, description="Seed для воспроизводимости")

    class Config:
        """Конфигурация Pydantic Settings"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Глобальный экземпляр конфигурации
config = AppConfig()


def setup_logging():
    """Настройка логирования"""
    # Удаляем стандартный handler
    logger.remove()

    # Добавляем handler в stdout
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level=config.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
    )

    # Добавляем handler в файл, если указан
    if config.log_file:
        log_path = Path(config.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            sink=str(log_path),
            level=config.log_level,
            rotation="10 MB",
            retention="1 week",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
        )

    logger.info("🚀 Policy Engine v{} запущен", config.version)
    logger.info(
        "📋 Конфигурация загружена: debug={}, platform={}",
        config.debug, config.jax_platform
    )


def ensure_directories():
    """Создание необходимых директорий"""
    dirs_to_create = [
        Path(config.data_dir) / "raw",
        Path(config.data_dir) / "curated",
        Path(config.cache_dir),
    ]

    for dir_path in dirs_to_create:
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.debug("📁 Директория создана/проверена: {}", dir_path)


# Инициализация при импорте
setup_logging()
ensure_directories()


if __name__ == "__main__":
    print("🔧 Конфигурация Policy Engine:")
    print(f"   App Name: {config.app_name}")
    print(f"   Version: {config.version}")
    print(f"   Debug: {config.debug}")
    print(f"   JAX Platform: {config.jax_platform}")
    print(f"   Data Dir: {config.data_dir}")
    print(f"   Population Size: {config.default_population_size}")

    print("\n📋 Переменные окружения:")
    for key, value in os.environ.items():
        if key.startswith(('OPENAI', 'ANTHROPIC', 'LOG_', 'JAX_')):
            print(f"   {key}: {'*' * len(value) if 'KEY' in key else value}")
