# Common: Инфраструктурный фундамент Policy Engine

Модуль `polisyos.common` — нижний слой архитектуры, не зависящий ни от одного другого модуля проекта. Предоставляет четыре инфраструктурных сервиса: логирование, конфигурацию среды, async-мост и систему миграций артефактов. Содержит только стандартную библиотеку и минимальный набор внешних пакетов (loguru, python-dotenv, opentelemetry-api).

## Структура модуля

```
common/
├── __init__.py              # Пустой — каждый компонент импортируется явно
├── config.py                # Конфигурация JAX/CPU/DuckDB/Torch/логирования (side effects при импорте)
├── jax_env.py               # Защита от Metal backend на macOS
├── logger.py                # get_logger() с OpenTelemetry trace context
├── async_tools.py           # run_coro_sync() — запуск корутин из синхронного кода
└── migrations/
    ├── __init__.py           # Экспорт: migrate_artifact, register_migration, MANIFEST_CURRENT_VERSION
    ├── base.py               # Ядро миграций: реестр, цепочки, обнаружение циклов
    └── manifest.py           # Dataset Manifest: миграция 0.9 → 1.0
```

## Роль в архитектуре

`common` находится в основании графа зависимостей проекта (см. [architecture.md](../../../../architecture.md)):

```
common  ←  core, ir, fabric, foundry, scientist, runtime, lex, scholar
   ↑
   нет зависимостей вверх
```

- Импортируется **всеми** слоями проекта, сам **ничего** не импортирует из polisyos
- Содержит **только инфраструктуру** — конфигурации, утилиты, миграции
- Запрещены тяжёлые зависимости (JAX, DuckDB, pandas, LLM) и бизнес-логика

## Компоненты

### `logger.py` — Структурированное логирование

Единый интерфейс логирования с контекстом модуля и интеграцией OpenTelemetry.

```python
from polisyos.common.logger import get_logger
log = get_logger(__name__)
log.info("Operation completed", extra_data={"key": "value"})
```

**API:**
- `get_logger(module_name)` — возвращает loguru logger с привязкой `module=module_name`. Автоматически добавляет `trace_id` и `span_id` из активного OpenTelemetry span
- `logger` — глобальный экземпляр loguru (используется в 3 файлах fabric)

**Особенности:**
- Если loguru не установлен — fallback на stdlib `logging`
- Если OpenTelemetry не сконфигурирован — trace context опускается
- Настройка логгера (handler'ы, форматы) выполняется в `config.py`, не здесь — для избежания циклических импортов

### `config.py` — Конфигурация среды выполнения

Выполняется при импорте через side effects: устанавливает переменные окружения и настраивает loguru.

**Критично:** должен быть импортирован **ДО** любого `import jax`.

```python
from polisyos.common import config  # side effects на os.environ
```

**Группы настроек:**

| Переменная | Значение | Назначение |
|-----------|----------|------------|
| `JAX_PLATFORM_NAME` | `cpu` | Принудительно CPU |
| `JAX_ENABLE_X64` | `false` | Отключение 64-bit |
| `JAX_DISABLE_MOST_OPTIMIZATIONS` | `true` | Стабильность |
| `XLA_PYTHON_CLIENT_PREALLOCATE` | `false` | Без жадной аллокации |
| `XLA_FLAGS` | `--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads={N}` | CPU параллелизм |
| `SCIENTIST_TORCH_DEVICE` | `cpu` | PyTorch на CPU |
| `SCIENTIST_TORCH_NUM_THREADS` | `{N}` | Потоки PyTorch |
| `OMP_NUM_THREADS` | `{N}` | OpenMP потоки |
| `OPENBLAS_NUM_THREADS` | `{N}` | OpenBLAS потоки |
| `VECLIB_MAXIMUM_THREADS` | `{N}` | vecLib потоки |
| `NUMEXPR_NUM_THREADS` | `{N}` | NumExpr потоки |
| `DUCKDB_MEMORY_LIMIT` | `4GB` | Лимит памяти DuckDB |
| `DUCKDB_THREADS` | `{N}` | Потоки DuckDB |
| `LOG_LEVEL` | `DEBUG` | Уровень логирования |

`{N}` = `max(1, cpu_count - ceil(cpu_count * 0.2))` — 80% ядер CPU, минимум 1.

**Логирование:** консоль (stderr, цветной формат) + файл (`logs/system.log`, JSON, ротация 10MB, хранение 10 дней).

### `jax_env.py` — macOS Metal защита

На macOS JAX может автоматически выбрать Metal backend, который падает на базовых операциях. Функция `apply_jax_env_defaults()` принудительно переключает на CPU.

```python
from polisyos.common.jax_env import apply_jax_env_defaults
apply_jax_env_defaults()  # Используется в jax_bootstrap.py
```

- Срабатывает только на macOS (`sys.platform == "darwin"`)
- Opt-in для Metal: `POLICY_ENGINE_ALLOW_JAX_METAL=1`
- Не импортируется модулями внутри `src/polisyos/` — используется только через `jax_bootstrap.py` в корне проекта

### `async_tools.py` — Асинхронный мост

Единственная функция `run_coro_sync(coro)` — безопасный запуск корутины из синхронного кода.

```python
from polisyos.common.async_tools import run_coro_sync
result = run_coro_sync(some_async_operation())
```

- Если event loop уже запущен — делегирует в `ThreadPoolExecutor(max_workers=1)`
- Если нет — вызывает `asyncio.run()` напрямую
- Типизирован через `TypeVar[T]` для корректного вывода типов

## Подсистема миграций

Детерминированная система версионирования артефактов с обнаружением циклов.

**Архитектура:** глобальный реестр `_MIGRATIONS[artifact][from_version] = (to_version, fn)`, декораторная регистрация, цепочечное применение.

**Публичный API (`migrations/__init__.py`):**

| Экспорт | Назначение |
|---------|------------|
| `migrate_artifact(data, artifact, target_version)` | Мигрирует dict от текущей `schema_version` до target. Требует поле `schema_version` в data |
| `register_migration(artifact, from_ver, to_ver)` | Декоратор: регистрирует функцию `(dict) -> dict` в реестре |
| `MANIFEST_CURRENT_VERSION` | `"1.0"` — текущая версия Dataset Manifest |

**Текущие миграции:**

| Артефакт | Версии | Что делает |
|----------|--------|------------|
| `dataset_manifest` | 0.9 → 1.0 | Нормализация полей: `datasetName` → `dataset_name`, `rawHash` → `raw_hash` |

**Пример:**
```python
from polisyos.common.migrations import migrate_artifact

data = {"schema_version": "0.9", "datasetName": "test", "rawHash": "abc"}
result = migrate_artifact(data, "dataset_manifest", "1.0")
# {"schema_version": "1.0", "dataset_name": "test", "raw_hash": "abc"}
```

**Добавление новой миграции:**
1. Создать функцию в существующем или новом файле в `migrations/`
2. Декорировать `@register_migration("artifact_name", "from", "to")`
3. Экспортировать константу версии через `__init__.py`
4. Добавить тест

> **Примечание:** модуль `ir/migrations` содержит независимую копию фреймворка миграций и **не** импортирует из `common/migrations`.

## Использование в проекте

Верифицированная карта импортов (33 импорта в 30 файлах):

### `get_logger` — 22 файла

**fabric/connectors/** (15 файлов):
- `registry.py`, `discovery.py`, `pool.py`
- `contracts/inference.py`, `contracts/registry.py`
- `resilience/__init__.py`, `resilience/circuit_breaker.py`, `resilience/fallback.py`, `resilience/rate_limiter.py`, `resilience/retry.py`
- `federation/composer.py`, `federation/planner.py`, `federation/ranker.py`, `federation/resolver.py`
- `cache/store.py`, `cache/proxy.py`, `cache/prefetch.py`, `cache/invalidation.py`

**fabric/** (4 файла): `ingestion.py`, `_connector_bridge.py`, `world/store/segments.py`

**foundry/** (3 файла): `executor.py`, `agent_sim/training.py`, `agent_sim/artifact.py`

**core/** (1 файл): `observability/logs.py`

### `logger` (глобальный экземпляр) — 3 файла
`fabric/io/db.py`, `fabric/catalog/registry.py`, `fabric/catalog/search.py`

### `run_coro_sync` — 2 файла
`fabric/_connector_bridge.py`, `fabric/ingestion.py`

### `apply_jax_env_defaults` — 1 файл
`jax_bootstrap.py` (корень проекта, вне `src/polisyos/`)

### `config.py` — 0 прямых импортов
Активируется через side effects при `from polisyos.common import config`.

### `migrations` — 0 внешних импортов
Не импортируется модулями за пределами `common/`.

## Зависимости

**Runtime:**
- `loguru` — структурированное логирование с JSON сериализацией
- `python-dotenv` — загрузка переменных из `.env`
- `opentelemetry-api` — trace context для логов (опционально, graceful degradation)

**Stdlib:** `asyncio`, `concurrent.futures`, `multiprocessing`, `os`, `sys`, `logging`

## Проверка актуальности

```bash
# Все внешние импорты common (кто использует)
grep -rn "from polisyos.common" src/polisyos/ --include="*.py" | grep -v "common/"

# Проверка изоляции (common НЕ должен импортировать другие слои)
grep -rn "from polisyos\.\(scientist\|fabric\|foundry\|runtime\|ir\|core\|lex\|scholar\)" src/polisyos/common/
```
