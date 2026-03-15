import os
import sys
from pathlib import Path

import pytest
try:
    from loguru import logger  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    import logging

    class _LoggerShim:
        def remove(self) -> None:
            return None

        def add(self, _sink, level: str = "ERROR") -> None:
            logging.basicConfig(level=getattr(logging, level, logging.ERROR))

    logger = _LoggerShim()

# Ensure `policy-engine/src` is on sys.path so imports like `import polisyos...` work under pytest.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
TESTS_ROOT = Path(__file__).resolve().parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

pytest_plugins = (
    "fixtures.artifacts",
    "fixtures.observability",
)

# --- FORCE SETTINGS FOR TESTS ---
# Эти настройки должны сработать до любых других импортов в тестах

# 1. Жестко запрещаем аллокацию памяти
os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"

# 2. Для тестов всегда форсируем CPU (даже если есть GPU), чтобы избежать конфликтов драйверов в CI/CD
# JAX 0.4+ предпочитает JAX_PLATFORMS; JAX_PLATFORM_NAME оставляем для совместимости.
os.environ["JAX_PLATFORMS"] = "cpu"
os.environ["JAX_PLATFORM_NAME"] = "cpu"


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Настройка окружения перед запуском всех тестов."""

    # Убираем лишний шум логов, оставляем только ошибки
    logger.remove()
    logger.add(lambda msg: print(msg), level="ERROR")

    yield
