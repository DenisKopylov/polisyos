#!/usr/bin/env python3
"""Smoke test для проверки корректной установки всех компонентов Policy Engine."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from tools._lib.imports import ensure_repo_import_roots

REPO_ROOT, SRC_ROOT = ensure_repo_import_roots(__file__, include_repo_root=False)

# --- CRITICAL SETUP ORDER ---
# Мы специально нарушаем порядок импортов (E402, I001),
# чтобы применить настройки среды (.env) ДО загрузки тяжелых библиотек.
# Теперь безопасные импорты
import duckdb  # noqa: E402
import jax  # noqa: E402

# Используем логгер из конфига или создаем локальный
from loguru import logger  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from polisyos.common import config  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    logger.info("\n" + "=" * 50)
    logger.info("HARDWARE STATUS CHECK")
    logger.info("=" * 50)

    logger.info(f"JAX Backend: {jax.default_backend()}")
    logger.info(f"JAX Devices: {jax.devices()}")

    logger.info("\n--- Applied Safeguards ---")
    logger.info(f"XLA Flags (CPU Cores): {os.environ.get('XLA_FLAGS', 'Not Set')}")
    logger.info(
        f"RAM Preallocate:       {os.environ.get('XLA_PYTHON_CLIENT_PREALLOCATE', 'Not Set')}"
    )

    class TestModel(BaseModel):
        id: int
        name: str

    model = TestModel(id=1, name="PolicyEngine")
    logger.info(f"\nPydantic: OK (Model init: {model.name})")

    con = None
    try:
        con = duckdb.connect(database=":memory:")
        con.execute(f"SET memory_limit='{config.DUCKDB_MEMORY_LIMIT}'")
        con.execute(f"SET threads={config.DUCKDB_THREADS}")

        res = con.execute("SELECT 'DuckDB is ready' as status").fetchall()
        actual_threads = con.execute("SELECT current_setting('threads')").fetchall()[0][0]
        actual_mem = con.execute("SELECT current_setting('memory_limit')").fetchall()[0][0]

        logger.info(f"DuckDB: {res[0][0]}")
        logger.info(f"   Limits Active: Threads={actual_threads}, Mem={actual_mem}")
    except Exception as exc:
        logger.error(f"DuckDB Error: {exc}")
        return 1
    finally:
        if con is not None:
            con.close()

    logger.info("\n" + "=" * 50)
    logger.info("SYSTEM READY FOR DEVELOPMENT")
    logger.info("=" * 50 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
