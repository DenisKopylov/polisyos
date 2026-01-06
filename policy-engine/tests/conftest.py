import os
import sys
from pathlib import Path

import pytest
from loguru import logger

# Ensure `policy-engine/` is on sys.path so imports like `import src...` work under pytest.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
