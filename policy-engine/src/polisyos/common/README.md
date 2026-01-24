# Common: Общие компоненты Policy Engine

> **Последнее обновление:** 24 января 2026 г. (обновление документации)

Модуль `polisyos.common` содержит фундаментальные утилиты и конфигурации, используемые во всех слоях архитектуры Policy Engine. Эти компоненты обеспечивают базовую инфраструктуру без зависимостей от бизнес-логики.

## Структура модуля

```
common/
├── __init__.py              # Пустой - модуль не экспортирует публичный API
├── config.py                # Централизованная конфигурация приложения
├── jax_env.py               # Безопасная настройка JAX backend для macOS
├── logger.py                # Единый интерфейс структурированного логирования
├── migrations/              # Система версионирования артефактов
│   ├── __init__.py         # Экспорт API миграций
│   ├── base.py             # Ядро системы миграций
│   ├── manifest.py         # Миграции Dataset Manifest
│   └── policy_ir.py        # Миграции Policy IR
└── README.md               # Эта документация
```

## Роль в архитектуре

Согласно [архитектуре проекта](../architecture.md), `common` является фундаментальным инфраструктурным слоем, который:

- **Не имеет зависимостей** от других слоев (scientist, fabric, foundry, ir)
- **Предоставляет сервисы** всем слоям проекта
- **Содержит только инфраструктуру** - конфигурации, логирование, миграции, JAX настройка
- **Избегает тяжелых зависимостей** - только стандартная библиотека + минимальный набор пакетов (loguru, python-dotenv)

### Текущие связи с модулями проекта

Модуль `common` активно используется в следующих компонентах:

#### Логирование (`logger.py`, `get_logger`):
- **fabric/ingestion.py** - логирование операций ingestion данных
- **fabric/io/db.py** - логирование операций с DuckDB через `logger`
- **fabric/io/graph_store.py** - логирование операций с графовым хранилищем через `get_logger`
- **fabric/materializer.py** - логирование операций материализации данных
- **fabric/udf/engine.py** - логирование в UDF движке через `logger`
- **fabric/udf/compiler.py** - логирование компиляции UDF через `logger`
- **scientist/orchestrator/data_loader.py** - логирование загрузки данных экспериментов

#### Миграции (`migrations/`):
- **ir/migrations/** - расширенная обертка над `common.migrations` для Policy IR артефактов

#### Конфигурация (`config.py`):
- **jax_bootstrap.py** - применение JAX настроек через side effects при импорте
- **Весь проект** - косвенное использование через переменные окружения и настройки логирования

## Архитектурные принципы

### Закон B: Ты строишь компилятор

Common поддерживает компиляторную архитектуру, обеспечивая:
- Детерминированные конфигурации (предсказуемость сред выполнения)
- Структурированное логирование (аудит и трассировка)
- Версионирование артефактов (миграции без потери данных)

### Закон D: Любой прогон воспроизводим и аудируем

Common обеспечивает:
- Логирование всех операций с контекстом модуля
- Сериализацию артефактов в JSON для машинного парсинга
- Миграции для обратной совместимости схем

## Структура модуля

### Корневые файлы:

- **`__init__.py`** - пустой (модуль не экспортирует публичный API напрямую)
- **`config.py`** - централизованная конфигурация приложения
- **`jax_env.py`** - безопасная настройка JAX backend для macOS
- **`logger.py`** - единый интерфейс структурированного логирования

### Подмодуль `migrations/`:

- **`__init__.py`** - экспорт API миграций
- **`base.py`** - ядро системы миграций
- **`manifest.py`** - миграции Dataset Manifest
- **`policy_ir.py`** - миграции Policy IR

## Детальное описание модулей

### `config.py` - Конфигурация приложения и инфраструктуры

**Цель:** Централизованная настройка всех зависимостей проекта с защитой от перегрузки системы.

#### Функциональность:

1. **JAX Environment Setup (Критично - выполняется ДО импорта JAX)**
   - Принудительная установка CPU как платформы: `JAX_PLATFORM_NAME=cpu`
   - Отключение 64-битных вычислений: `JAX_ENABLE_X64=false`
   - Отключение большинства оптимизаций: `JAX_DISABLE_MOST_OPTIMIZATIONS=true`
   - Отключение проверки утечек трассировщиков: `JAX_CHECK_TRACER_LEAKS=false`
   - Отключение жадной аллокации памяти XLA: `XLA_PYTHON_CLIENT_PREALLOCATE=false`
   - Автоматическая настройка CPU потоков: `intra_op_parallelism_threads={auto_cores}`

2. **Hardware Safeguards (Защита железа)**
   - Автоматическое определение количества ядер CPU через `multiprocessing.cpu_count()`
   - Резерв 20% ядер для системы (минимум 1 ядро)
   - Расчет безопасного количества ядер: `max(1, total_cores - reserved_cores)`
   - Логирование выбранной конфигурации CPU для отладки

3. **Memory Management**
   - Отключение жадной аллокации памяти: `XLA_PYTHON_CLIENT_PREALLOCATE=false`
   - Настройка параллелизма CPU: `intra_op_parallelism_threads={allowed_cores}`

4. **Database Configuration**
   - DuckDB память: 4GB по умолчанию (`DUCKDB_MEMORY_LIMIT`)
   - DuckDB потоки: автоматически на основе доступных ядер CPU (`DUCKDB_THREADS`)

5. **Logging Infrastructure**
   - **Консоль:** Читаемый вывод для разработчиков с цветами и форматированием
   - **Файл:** JSON сериализация в `logs/system.log` для аудита
   - Ротация: 10MB с хранением 10 дней
   - Уровни: DEBUG по умолчанию, настраивается через `LOG_LEVEL`

#### Переменные окружения:

```bash
# JAX (автоматически устанавливаются)
JAX_PLATFORM_NAME=cpu
JAX_ENABLE_X64=false
JAX_DISABLE_MOST_OPTIMIZATIONS=true
JAX_CHECK_TRACER_LEAKS=false

# Memory & CPU (автоматически настраиваются)
XLA_PYTHON_CLIENT_PREALLOCATE=false
XLA_FLAGS=--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads={auto_cores}

# DuckDB
DUCKDB_MEMORY_LIMIT=4GB              # Дефолт: 4GB
DUCKDB_THREADS={auto_cores}          # Автоматически = доступным ядрам CPU

# Логирование
LOG_LEVEL=DEBUG                      # Уровень логирования (DEBUG, INFO, WARNING, ERROR)
```

#### Важные детали:

- **Импорт до JAX:** Должен быть импортирован ДО любого `import jax`
- **Side effects:** Мутирует `os.environ` глобально для стабильности JAX
- **Автокоррекция:** Сам определяет безопасные лимиты на основе доступного железа
- **.env поддержка:** Загружает переменные из `.env` файла через `python-dotenv`

### `jax_env.py` - JAX Backend Selection для macOS

**Цель:** Предотвращение падений JAX на macOS с экспериментальным Metal backend.

#### Проблема:

На macOS JAX автоматически выбирает Metal backend, который в текущей версии вызывает падения даже на базовых операциях:
```
UNIMPLEMENTED: default_memory_space is not supported.
```

#### Решение:

```python
def apply_jax_env_defaults() -> None:
    """Применяет безопасные настройки JAX для macOS."""
    if sys.platform != "darwin":
        return  # Только для macOS

    # Если пользователь явно не разрешил Metal
    if os.environ.get("POLICY_ENGINE_ALLOW_JAX_METAL") != "1":
        # Принудительно CPU, если не запрошена другая платформа или Metal
        requested = (os.environ.get("JAX_PLATFORMS") or
                    os.environ.get("JAX_PLATFORM_NAME") or "").lower()
        if not requested or "metal" in requested:
            os.environ.setdefault("JAX_PLATFORMS", "cpu")
            os.environ.setdefault("JAX_PLATFORM_NAME", "cpu")
```

#### Опциональное включение Metal:

```bash
# Явное разрешение Metal backend
POLICY_ENGINE_ALLOW_JAX_METAL=1
JAX_PLATFORMS=metal
# или
JAX_PLATFORM_NAME=metal
```

#### Использование:

```python
# В jax_bootstrap.py (импортируется перед любым JAX)
from polisyos.common.jax_env import apply_jax_env_defaults
apply_jax_env_defaults()
```

### `logger.py` - Структурированное логирование с контекстом модуля

**Цель:** Единый интерфейс логирования с автоматическим контекстом модуля.

#### API:

```python
from polisyos.common.logger import get_logger

# Получение логгера с контекстом модуля
log = get_logger(__name__)

# Использование
log.info("Operation completed", extra_data={"key": "value"})
log.error("Something went wrong", error_details={"code": 500})
```

#### Особенности:

- **Контекст модуля:** Автоматически привязывает имя модуля через `logger.bind(module=module_name)`
- **Loguru backend:** Мощная система логирования с уровнями, форматированием и сериализацией
- **JSON сериализация:** Файловые логи сериализуются в JSON для машинного парсинга
- **Настройка в config.py:** Логгер настраивается в `config.py` для избежания циклических импортов

### `migrations/` - Система версионирования артефактов

**Цель:** Детерминированные преобразования артефактов между версиями схем с обнаружением циклов.

#### Архитектура:

- **Базовый фреймворк** (`base.py`): Регистрация и выполнение миграций
- **Декораторная система:** `@register_migration(artifact, from_version, to_version)`
- **Глобальный реестр:** `_MIGRATIONS` - словарь артефакт → версия → (целевая_версия, функция)
- **Цикл обнаружения:** Предотвращает бесконечные циклы миграций через множество `visited`

#### Компоненты:

1. **`base.py` - Ядро системы миграций**
   ```python
   def register_migration(artifact: str, from_version: str, to_version: str):
       def decorator(fn: MigrationFn) -> MigrationFn:
           _MIGRATIONS.setdefault(artifact, {})[from_version] = (to_version, fn)
           return fn
       return decorator

   def migrate_artifact(data: dict, artifact: str, target_version: str) -> dict:
       # Миграция с проверкой циклов и версий
   ```

2. **`manifest.py` - Миграции Dataset Manifest**
   - Текущая версия: `MANIFEST_CURRENT_VERSION = "1.0"`
   - Миграция `0.9 → 1.0`: нормализация полей (`datasetName` → `dataset_name`, `rawHash` → `raw_hash`)

3. **`policy_ir.py` - Миграции Policy IR**
   - Текущая версия: `POLICY_IR_CURRENT_VERSION = "2.0"`
   - Миграции: отсутствуют (текущая версия является основной стабильной версией)

#### Пример использования:

```python
from polisyos.common.migrations import migrate_artifact

# Миграция Dataset Manifest
manifest_data = {"schema_version": "0.9", "datasetName": "test"}
migrated = migrate_artifact(manifest_data, "dataset_manifest", "1.0")
# Результат: {"schema_version": "1.0", "dataset_name": "test"}

# Policy IR использует версию 2.0 как основную и не имеет миграций из предыдущих версий
```

## Использование в проекте

### Порядок инициализации (критично для стабильности):

```python
# 1. КРИТИЧНО: Конфигурация ДО любого импорта JAX!
from polisyos.common import config  # Side effects на os.environ (JAX настройки)

# 2. JAX backend (опционально, для дополнительной защиты на macOS)
from polisyos.common.jax_env import apply_jax_env_defaults
apply_jax_env_defaults()  # Только если нужна дополнительная настройка

# 3. Логирование (теперь доступно через config)
from polisyos.common.logger import get_logger
log = get_logger(__name__)
```

### Альтернативная инициализация через jax_bootstrap:

```python
# В jax_bootstrap.py (рекомендуемый способ для проектов с JAX)
from polisyos.common.jax_env import apply_jax_env_defaults
apply_jax_env_defaults()  # Применяет безопасные JAX настройки для macOS

# Затем в коде проекта:
from polisyos.common import config  # Импорт config после jax_bootstrap
from polisyos.common.logger import get_logger
log = get_logger(__name__)
```

#### jax_bootstrap.py в проекте

Файл `jax_bootstrap.py` в корне проекта выполняет инициализацию JAX перед любым импортом JAX:

```python
# jax_bootstrap.py
from polisyos.common.jax_env import apply_jax_env_defaults
apply_jax_env_defaults()  # Безопасная настройка JAX backend
```

### Использование в модулях проекта:

#### Логирование в fabric модулях:

```python
# В fabric/io/db.py (операции с DuckDB)
from polisyos.common.logger import logger

def save_simulation_data(self, data):
    logger.info("Saving simulation data", run_id=self.run_id)
    # ... операции с БД ...

# В fabric/materializer.py (материализация данных)
from polisyos.common.logger import get_logger
log = get_logger(__name__)

def materialize(self, request):
    log.info("Starting materialization", request_id=request.id)
    # ... логика материализации ...
```

#### Миграции в ir модуле:

```python
# В ir/migrations/__init__.py (расширенная обертка над common.migrations)
from polisyos.common.migrations.base import migrate_artifact
from polisyos.common.migrations.base import register_migration as _register_migration
from polisyos.common.migrations.policy_ir import POLICY_IR_CURRENT_VERSION

def migrate_policy_ir(data: dict, target_version: str | None = None) -> dict:
    return migrate_artifact(data, "policy_ir", target_version or POLICY_IR_CURRENT_VERSION)
```

## Зависимости

### Runtime:
- `loguru` - структурированное логирование с JSON сериализацией
- `python-dotenv` - загрузка переменных окружения из `.env` файла
- `multiprocessing` - определение количества CPU ядер для автонастройки

### Development:
- Все зависимости определены в `pyproject.toml` корневой директории проекта

## Тестирование

Модуль тестируется через:
- **Unit тесты:** `tests/common/` (если существуют)
- **Integration:** `tools/diagnostics/check_setup.py`
- **Contract тесты:** Проверка конфигураций и миграций

## Безопасность и производительность

### Hardware Safeguards:
- Автоматическое ограничение ресурсов
- Предотвращение перегрузки системы
- Адаптация под доступное железо

### Logging Security:
- JSON сериализация для аудита
- Ротация логов (не растут бесконечно)
- Структурированные сообщения для анализа

### Migration Safety:
- Детерминированные преобразования
- Обнаружение циклов
- Версионирование схем

## Архитектурные ограничения

### Запрещено:
- **Бизнес-логика:** Только инфраструктура и утилиты
- **Тяжелые зависимости:** JAX, DuckDB, LLM, pandas, etc. (кроме базовых: loguru, python-dotenv)
- **Слой-specific код:** Нейтральные компоненты, используемые всеми слоями

### Разрешено:
- **Конфигурации:** Настройки окружения и системных параметров
- **Утилиты:** Логирование, миграции, JAX настройки
- **Инфраструктура:** Базовые сервисы для всех компонентов проекта

## Связанные компоненты

### Активное использование в модулях проекта:

#### Логирование (logger/get_logger):
- **`fabric/ingestion.py`** - операции ingestion данных
- **`fabric/io/db.py`** - операции с DuckDB
- **`fabric/io/graph_store.py`** - операции с графовым хранилищем
- **`fabric/materializer.py`** - операции материализации данных
- **`fabric/udf/engine.py`** - UDF движок
- **`fabric/udf/compiler.py`** - компиляция UDF
- **`scientist/orchestrator/data_loader.py`** - загрузка данных экспериментов
- **`scientist/_legacy/compiler.py`** - компиляция экспериментов (legacy)

#### Миграции (migrations):
- **`ir/migrations/__init__.py`** - расширенная обертка для миграций Policy IR с дополнительной логикой версий

### Архитектурные связи:

- **core:** Использует логирование для операций с артефактами и регистрами
- **fabric:** Зависит от логирования для всех I/O операций и UDF движка
- **foundry:** Использует логирование в симуляциях и калибровке
- **ir:** Зависит от миграций для версионирования схем Policy IR
- **runtime:** Использует логирование для аудита прогонов
- **scientist:** Зависит от логирования в оркестрации экспериментов и агентов

## Проверка актуальности документации

Для поддержания актуальности этого README рекомендуется:

1. **Проверка импортов:** Регулярно проверять использование `common` в проекте:
   ```bash
   grep -r "from polisyos.common" src/polisyos/
   ```

2. **Анализ зависимостей:** Убедиться, что `common` не импортирует другие слои:
   ```bash
   grep -r "from polisyos\.\(scientist\|fabric\|foundry\|runtime\)" src/polisyos/common/
   ```

3. **Тестирование изоляции:** `common` должен работать автономно без зависимостей от других модулей

## Контрибьютинг

При добавлении новых компонентов в `common`:

1. **Проверить зависимости:** Не добавлять тяжелые импорты (JAX, DuckDB, LLM и т.д.)
2. **Тестировать изоляцию:** Работает без других слоев проекта
3. **Обновить документацию:** Добавить описание нового компонента в этот README
4. **Следовать принципам:** Только инфраструктура и утилиты, не бизнес-логика
5. **Обновить связи:** Добавить информацию о новом использовании в раздел "Связанные компоненты"
