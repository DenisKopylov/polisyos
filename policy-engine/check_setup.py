#!/usr/bin/env python3
"""
Smoke test для проверки корректной установки всех компонентов Policy Engine.
Запустите: python check_setup.py
"""

import sys
from pathlib import Path

def test_jax():
    """Проверка JAX"""
    try:
        import jax
        import jax.numpy as jnp

        print("✅ JAX:")
        print(f"   Backend: {jax.default_backend()}")
        print(f"   Devices: {jax.devices()}")

        # Простой тест вычислений
        x = jnp.array([1.0, 2.0, 3.0])
        y = jnp.array([4.0, 5.0, 6.0])
        result = jnp.dot(x, y)
        print(f"   Тест вычислений: {result}")
        return True
    except ImportError as e:
        print(f"❌ JAX не установлен: {e}")
        return False

def test_pydantic():
    """Проверка Pydantic"""
    try:
        from pydantic import BaseModel

        class TestModel(BaseModel):
            id: int
            name: str

        model = TestModel(id=1, name="PolicyEngine")
        print(f"✅ Pydantic: {model.model_dump_json()}")
        return True
    except ImportError as e:
        print(f"❌ Pydantic не установлен: {e}")
        return False

def test_duckdb():
    """Проверка DuckDB"""
    try:
        import duckdb

        con = duckdb.connect(database=':memory:')
        res = con.execute("SELECT 'DuckDB is ready' as status").fetchall()
        print(f"✅ DuckDB: {res[0][0]}")
        return True
    except ImportError as e:
        print(f"❌ DuckDB не установлен: {e}")
        return False

def test_equinox():
    """Проверка Equinox"""
    try:
        import equinox as eqx
        print("✅ Equinox: готов к работе")
        return True
    except ImportError as e:
        print(f"❌ Equinox не установлен: {e}")
        return False

def test_diffrax():
    """Проверка Diffrax"""
    try:
        import diffrax
        print("✅ Diffrax: готов к работе")
        return True
    except ImportError as e:
        print(f"❌ Diffrax не установлен: {e}")
        return False

def test_optax():
    """Проверка Optax"""
    try:
        import optax
        print("✅ Optax: готов к работе")
        return True
    except ImportError as e:
        print(f"❌ Optax не установлен: {e}")
        return False

def main():
    """Основная функция проверки"""
    print("🚀 Policy Engine - Smoke Test\n")
    print("=" * 50)

    tests = [
        test_jax,
        test_pydantic,
        test_duckdb,
        test_equinox,
        test_diffrax,
        test_optax,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print("=" * 50)
    print(f"📊 Результаты: {passed}/{total} тестов пройдено")

    if passed == total:
        print("🎉 Все компоненты установлены корректно!")
        return 0
    else:
        print("⚠️  Некоторые компоненты отсутствуют. Проверьте установку.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
