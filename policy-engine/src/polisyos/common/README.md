# `polisyos.common` — инфраструктурный слой без доменной логики

`common` содержит минимальные кросс-модульные утилиты: bootstrap окружения, логирование, сериализацию, время, async-мост и локальные миграции артефактов.  
Это базовый слой, который можно импортировать из `core/fabric/foundry/scientist/scholar/tools`, но который сам не должен зависеть от этих директорий.

## Роль в системе

```text
polisyos.common
  ├─ runtime bootstrap (config, jax_env)
  ├─ observability glue (logger)
  ├─ utility helpers (async_tools, serialization, timestamps)
  └─ artifact migrations (common/migrations)
```

Ключевые инварианты:
- `common` не импортирует `polisyos.core`, `polisyos.fabric`, `polisyos.foundry`, `polisyos.scientist`, `polisyos.ir`, `polisyos.runtime`, `polisyos.lex`, `polisyos.scholar`.
- В `common` нет бизнес-правил, только инфраструктурные примитивы.
- API должен оставаться небольшим и предсказуемым, потому что это нижний слой графа зависимостей.

## Структура директории

```text
common/
├── __init__.py         # Lazy facade через __getattr__ для подмодулей common.*
├── async_tools.py      # run_coro_sync()
├── config.py           # side-effects: env defaults + logger sinks
├── jax_env.py          # apply_jax_env_defaults() для macOS/JAX
├── logger.py           # get_logger() + OTel trace context
├── serialization.py    # to_python_data(), stable_json_dumps(), strip_none()
├── timestamps.py       # UTC helpers (iso/epoch/parse)
├── migrations/
│   ├── __init__.py     # migrate_artifact, register_migration, MANIFEST_CURRENT_VERSION
│   ├── base.py         # migration registry + chain executor
│   └── manifest.py     # dataset_manifest 0.9 -> 1.0
└── README.md
```

## Модули и назначение

| Модуль | Что делает | Где используется |
|---|---|---|
| `__init__.py` | Ленивая загрузка подмодулей `common.*` через `__getattr__` | Импорт `from polisyos.common import config` в `tools/diagnostics/check_setup.py` |
| `config.py` | На импорте грузит `.env`, задает безопасные env defaults (JAX/threads/Torch/DuckDB), конфигурирует `loguru` sinks | Bootstrap-скрипты и окружение разработки |
| `logger.py` | `get_logger()` с добавлением `trace_id/span_id` из OpenTelemetry; fallback на stdlib `logging` | Широко в `fabric`, точечно в `core` и `foundry`, плюс `tools/*` |
| `jax_env.py` | Принудительно выставляет CPU на macOS (если не включен Metal opt-in) | `jax_bootstrap.py` |
| `async_tools.py` | Безопасный вызов корутины из sync-кода (`run_coro_sync`) | `fabric/ingestion.py`, `fabric/_connector_bridge.py` |
| `serialization.py` | Нормализация сложных структур в python/json-friendly вид | `scientist`, `foundry` |
| `timestamps.py` | Единые UTC-утилиты: `utc_now`, parse/format ISO, epoch conversion | `scholar`, `scientist` |
| `migrations/*` | Реестр миграций и применение цепочки по `schema_version` | CLI/утилиты миграций |

## Функциональные особенности

### 1) Bootstrap конфигурация (`config.py`)
- Исполняется через side effects при импорте.
- Должен загружаться до `import jax`, если нужна гарантированная фиксация backend/threads.
- Выставляет безопасные дефолты по CPU-потокам и памяти (JAX, BLAS/OpenMP, Torch, DuckDB).
- Конфигурирует 2 sink-а логов: консоль и `logs/system.log` (JSON, rotation/retention).

### 2) Логирование и трейсинг (`logger.py`)
- `get_logger(module_name)` возвращает контекстный логгер.
- Если доступен OTel span, в `extra` добавляются `trace_id` и `span_id`.
- При отсутствии `loguru`/OTel модуль деградирует без падения процесса.

### 3) Сериализация для стабильных payload-ов (`serialization.py`)
- Поддерживает `Enum`, dataclass, Pydantic `model_dump`, mapping/list/set.
- Пытается аккуратно нормализовать объекты с `.tolist()`/`.item()` (например array/scalar wrappers).
- `stable_json_dumps()` дает компактный стабильный JSON для fingerprint/idempotency задач.

### 4) Единое UTC-время (`timestamps.py`)
- `utc_now()` и `ensure_utc()` убирают разночтения naive/aware datetime.
- `to_iso_utc(..., z_suffix=True)` приводит формат к `...Z`.
- `parse_iso_datetime()` безопасно парсит `str|datetime` и возвращает `datetime | None`.

### 5) Миграции в `common/migrations`
- Базовый движок: `_MIGRATIONS[artifact][from_version] -> (to_version, fn)`.
- `migrate_artifact()` идет по цепочке версий, проверяет `schema_version`, защищен от циклов.
- Сейчас в `common` зарегистрирована миграция только для `dataset_manifest` (`0.9 -> 1.0`).
- Миграции `policy_ir` поддерживаются отдельно в `polisyos.ir.migrations`.

## Связь с другими директориями

`common` связан с системой в основном как shared-инфраструктура:
- `fabric/` — основной потребитель `logger` и `run_coro_sync`.
- `scientist/` — потребитель `serialization` и `timestamps`.
- `foundry/` — использует `logger` и `serialization`.
- `scholar/` — использует `timestamps`.
- `core/` — точечно использует `get_logger`.
- `tools/` и корневые скрипты — используют `config`, `logger`, `migrations`, `jax_env`.

Смежные зоны ответственности:
- `polisyos.ir.migrations` — миграции IR-контрактов (`policy_ir`), не слой `common`.
- `polisyos.core.canon` — строгая канонизация/байтовая сериализация для CAS; `common.serialization` предназначен для более общего runtime-представления данных.

## Практические правила использования

- Для логов в прод-коде использовать `get_logger(__name__)`, а не глобальный `logger`, когда нужен модульный контекст.
- Импортировать `config` только в bootstrap-скриптах/entrypoints, где side effects ожидаемы.
- В доменных пакетах не добавлять зависимости на тяжелые библиотеки через `common`.
- Новые миграции регистрировать только для артефактов, владельцем схемы которых является `common`.

## Быстрая проверка актуальности

```bash
# Кто использует common
rg -n "from polisyos\\.common|import polisyos\\.common" src tools *.py

# Проверка, что common не тянет верхние слои
rg -n "from polisyos\\.(core|fabric|foundry|scientist|ir|runtime|lex|scholar)" src/polisyos/common
```
