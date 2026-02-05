# Diagnostics - Диагностика и анализ системы Policy Engine

Набор диагностических инструментов для проверки здоровья, производительности и корректности Policy Engine. Диагностика обеспечивает качество системы и помогает в troubleshooting проблем.

## Структура папки

```
diagnostics/
├── check_setup.py          # Комплексная проверка установки
├── check_udf_perf.py       # Профилирование UDF производительности
├── check_perf_regression.py# Проверка регрессий производительности
└── generate_ir_schema.py   # Генерация JSON Schema для IR
```

## Быстрый старт

Все диагностические инструменты запускаются из корня проекта:

```bash
cd policy-engine/

# Проверка установки (начать с этого)
python tools/diagnostics/check_setup.py

# Генерация IR схем
python tools/diagnostics/generate_ir_schema.py

# Профилирование UDF производительности
python tools/diagnostics/check_udf_perf.py
```

## Детальные описания инструментов

### check_setup.py - Комплексная проверка установки

Полная smoke test установка всех компонентов Policy Engine с учетом архитектурных зависимостей и системных требований.

#### Проверяемые компоненты

**JAX экосистема:**
- Версия JAX и совместимость платформы
- Доступные устройства (CPU/GPU/TPU)
- Базовые тензорные операции
- JIT компиляция и оптимизации

**Базы данных:**
- DuckDB: аналитическое хранилище (версия, базовые операции)
- Kuzu: графовая БД (версия, подключение, базовые запросы)

**Python стек:**
- Python 3.11+ (версия и compatibility)
- Pydantic v2 (критическая зависимость)
- Equinox (функциональное программирование)
- Diffrax (дифференциальные уравнения)

**Модули Policy Engine:**
- Импорт всех основных модулей (core, ir, fabric, foundry, scientist, runtime)
- Проверка отсутствия циклических зависимостей
- Валидация конфигурации

#### Интеграция с модулями

- **`polisyos.common.config`** - конфигурация лимитов и настроек
- **`jax_bootstrap.py`** - форсирование CPU на macOS
- **`.env` переменные** - окружение и переменные среды

#### Типичный успешный вывод

```
==================================================
HARDWARE STATUS CHECK
==================================================
✅ JAX Backend: cpu
✅ JAX Devices: [CpuDevice(id=0)]
--- Applied Safeguards ---
🔒 XLA Flags (CPU Cores): --xla_force_host_platform_device_count=8
🔒 RAM Preallocate:       false

✅ Pydantic: OK (Model init: PolicyEngine)
✅ DuckDB: DuckDB is ready
   └── Limits Active: Threads=4, Mem=1.0 GiB
✅ Kuzu: Graph store ready

==================================================
SYSTEM READY FOR DEVELOPMENT
==================================================
```

#### Переменные окружения

- `POLICY_ENGINE_ALLOW_JAX_METAL=0/1` - разрешение JAX Metal на macOS
- `POLICY_ENGINE_LOG_LEVEL=DEBUG/INFO` - уровень детализации логов
- `XLA_FLAGS` - JAX XLA флаги для оптимизации

### check_udf_perf.py - Профилирование UDF производительности

Инструмент для измерения и анализа производительности пользовательских функций в контексте Unified Data Fabric.

#### Типы измерений

**Время выполнения:**
- Latency отдельных запросов
- Throughput (запросов в секунду)
- Время первого запуска vs кешированные запросы

**Ресурсное потребление:**
- CPU использование
- Память (RAM) consumption
- Disk I/O для больших запросов

**Сравнение систем:**
- DuckDB vs Kuzu производительность
- SQL-only vs гибридные запросы
- Разные типы UDF (агрегации, ML, статистика)

#### Режимы работы

**Базовое профилирование:**
```bash
python tools/diagnostics/check_udf_perf.py
```

**Регрессионное тестирование:**
```bash
# Создание baseline
python tools/diagnostics/check_udf_perf.py --write-baseline --baseline data/udf_perf_baseline.json

# Проверка на регрессию
python tools/diagnostics/check_udf_perf.py --baseline data/udf_perf_baseline.json --max-regression 1.2
```

#### Поддерживаемые запросы

- **Panel queries** - временные ряды макропоказателей
- **Snapshot queries** - агрегации по состоянию агентов
- **Network queries** - графовые запросы в Kuzu

#### Интеграция с модулями

- **`polisyos.fabric.udf.engine.UDFEngine`** - движок запросов
- **`polisyos.fabric.io.db.SimulationDB`** - DuckDB бэкенд
- **`polisyos.fabric.io.graph_store.GraphStore`** - Kuzu бэкенд

### generate_ir_schema.py - Генерация IR схем

Автоматическая генерация JSON Schema для всех IR компонентов с валидацией структур данных и совместимости версий.

#### Функциональность

**Генерация схем:**
- Автоматическая генерация из Pydantic моделей
- JSON Schema draft 2020-12
- Детерминированные результаты для CI/CD

**Валидация структур:**
- Проверка корректности PolicySurfaceIR
- Валидация вложенных структур (interventions, constraints)
- Semantic validation (бизнес-логика)

**Совместимость версий:**
- Проверка эволюции схем между версиями
- Детерминированная генерация
- Отсутствие случайности в схемах

#### Примеры использования

```bash
# Генерация схемы в текущую директорию
python tools/diagnostics/generate_ir_schema.py

# Результат: policy_ir_schema.json
```

#### Self-healing validation

Инструмент также тестирует "self-healing" - способность LLM исправлять ошибки валидации на основе описательных сообщений об ошибках.

#### Интеграция с модулями

- **`polisyos.ir.surface.PolicySurfaceIR`** - основная IR модель
- **`polisyos.ir.validation.build_validation_report`** - отчеты об ошибках
- **Pydantic v2** - генерация схем из type hints

## Архитектурная интеграция

Диагностические инструменты обеспечивают качество всей экосистемы Policy Engine согласно архитектурным законам.

### Архитектурные гарантии

**Закон A (Направленный граф зависимостей):**
- `check_setup.py` проверяет корректность импортов
- Выявляет циклические зависимости
- Подтверждает архитектурную чистоту

**Закон B (Компиляторная архитектура):**
- Диагностика подтверждает чистоту foundry
- Проверяет отсутствие запрещенных импортов
- Тестирует JAX совместимость

**Закон C (Контракты как источник истины):**
- `generate_ir_schema.py` генерирует схемы из Pydantic
- `migrate_*.py` обеспечивают детерминированные миграции
- Все артефакты имеют schema_version

**Закон D (Воспроизводимость и аудит):**
- Все диагностические прогоны имеют run_id
- Полная трассировка через `polisyos.core.trace`
- Детерминированные результаты

### CI/CD интеграция

Диагностика является core частью quality gate:

```yaml
# .github/workflows/ci.yml
jobs:
  quality-gate:
    steps:
    - name: System readiness check
      run: python tools/diagnostics/check_setup.py

    - name: Schema validation
      run: |
        python tools/diagnostics/generate_ir_schema.py
        python tools/gen_schema.py --check

    - name: Performance regression check
      run: |
        python tools/diagnostics/check_udf_perf.py \
          --baseline data/udf_perf_baseline.json \
          --max-regression 1.2
```

## Troubleshooting

### Import ошибки
```bash
# Проверить PYTHONPATH
export PYTHONPATH="/path/to/policy-engine/src:$PYTHONPATH"
python tools/diagnostics/check_setup.py
```

### JAX Metal проблемы (macOS)
```bash
# Принудительно CPU
export POLICY_ENGINE_ALLOW_JAX_METAL=0
POLICY_ENGINE_LOG_LEVEL=DEBUG python tools/diagnostics/check_setup.py
```

### Kuzu подключение
```bash
# Проверить версию
python -c "import kuzu; print(kuzu.__version__)"

# Переустановить
pip install kuzu --upgrade
```

### Память переполнена
```bash
# Уменьшить лимиты в config
# polisyos/common/config.py
DUCKDB_MEMORY_LIMIT = "512MB"
DUCKDB_THREADS = 2
```

### Schema генерация падает
```bash
# Проверить Pydantic версию
python -c "import pydantic; print(pydantic.VERSION)"

# Должен быть 2.x, не 1.x
pip install 'pydantic>=2.0'
```

## Разработка новых диагностических инструментов

### Принципы дизайна

1. **Быстрый фидбек** - результаты за секунды, не минуты
2. **Четкие сообщения** - понятные ошибки и успех
3. **Неинвазивность** - не изменять состояние системы
4. **CI/CD готовность** - exit codes и структурированный вывод

### Категоризация диагностики

- **`check_*.py`** - проверки готовности и корректности
- **`profile_*.py`** - измерение производительности
- **`validate_*.py`** - проверки структур данных
- **`audit_*.py`** - анализ зависимостей и архитектуры

### Шаблон нового инструмента

```python
#!/usr/bin/env python3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

def main() -> int:
    """Diagnostic tool description."""
    print("🔍 Running diagnostic...")

    # Проверки и тесты...

    print("✅ Diagnostic passed!")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

---

*Диагностические инструменты протестированы на Python 3.11+ с полным стеком Policy Engine. Документация актуальна на 2026-02-05.*