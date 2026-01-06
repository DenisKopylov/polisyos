#!/usr/bin/env python3
"""
Smoke test для проверки корректной установки всех компонентов Policy Engine.
Запустите: python check_setup.py
"""

import os  # noqa: I001

# --- CRITICAL SETUP ORDER ---
# Мы специально нарушаем порядок импортов (E402, I001),
# чтобы применить настройки среды (.env) ДО загрузки тяжелых библиотек.
from src.utils import config  # noqa: E402

# Теперь безопасные импорты
import duckdb  # noqa: E402
import jax  # noqa: E402
from pydantic import BaseModel  # noqa: E402

# Используем логгер из конфига или создаем локальный
from loguru import logger  # noqa: E402

logger.info("\n" + "=" * 50)
logger.info("HARDWARE STATUS CHECK")
logger.info("=" * 50)

# --- Проверка JAX ---
logger.info(f"✅ JAX Backend: {jax.default_backend()}")
# Важно: devices() покажет 'cpu', но реальное кол-во потоков скрыто внутри XLA
logger.info(f"✅ JAX Devices: {jax.devices()}")

logger.info("\n--- Applied Safeguards ---")
logger.info(f"🔒 XLA Flags (CPU Cores): {os.environ.get('XLA_FLAGS', 'Not Set')}")
logger.info(
    f"🔒 RAM Preallocate:       {os.environ.get('XLA_PYTHON_CLIENT_PREALLOCATE', 'Not Set')}"
)


# --- Проверка Pydantic ---
class TestModel(BaseModel):
    id: int
    name: str


model = TestModel(id=1, name="PolicyEngine")
logger.info(f"\n✅ Pydantic: OK (Model init: {model.name})")

# --- Проверка DuckDB с лимитами ---
try:
    # Передаем настройки лимитов при подключении
    con = duckdb.connect(database=":memory:")

    # Применяем лимиты из config
    con.execute(f"SET memory_limit='{config.DUCKDB_MEMORY_LIMIT}'")
    con.execute(f"SET threads={config.DUCKDB_THREADS}")

    res = con.execute("SELECT 'DuckDB is ready' as status").fetchall()

    # Проверяем, применились ли настройки
    actual_threads = con.execute("SELECT current_setting('threads')").fetchall()[0][0]
    actual_mem = con.execute("SELECT current_setting('memory_limit')").fetchall()[0][0]

    logger.info(f"✅ DuckDB: {res[0][0]}")
    logger.info(f"   └── Limits Active: Threads={actual_threads}, Mem={actual_mem}")

except Exception as e:
    logger.error(f"❌ DuckDB Error: {e}")

logger.info("\n" + "=" * 50)
logger.info("SYSTEM READY FOR DEVELOPMENT")
logger.info("=" * 50 + "\n")
