import os

import pytest
from loguru import logger

# --- FORCE SETTINGS FOR TESTS ---
# Эти настройки должны сработать до любых других импортов в тестах

# 1. Жестко запрещаем аллокацию памяти
os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"

# 2. Для тестов всегда форсируем CPU (даже если есть GPU), чтобы избежать конфликтов драйверов в CI/CD
os.environ["JAX_PLATFORM_NAME"] = "cpu"


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Настройка окружения перед запуском всех тестов."""

    # Убираем лишний шум логов, оставляем только ошибки
    logger.remove()
    logger.add(lambda msg: print(msg), level="ERROR")

    yield
