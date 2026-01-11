# Common: Общие компоненты Policy Engine

Модуль `polisyos.common` содержит фундаментальные утилиты и конфигурации, используемые во всех слоях архитектуры Policy Engine. Эти компоненты обеспечивают базовую инфраструктуру без зависимостей от бизнес-логики.

## Роль в архитектуре

Согласно [архитектуре проекта](../architecture.md), `common` является фундаментальным инфраструктурным слоем, который:

- **Не имеет зависимостей** от других слоев (scientist, fabric, foundry, ir)
- **Предоставляет сервисы** всем слоям проекта
- **Содержит только инфраструктуру** - конфигурации, логирование, миграции, JAX настройка
- **Избегает тяжелых зависимостей** - только стандартная библиотека + минимальный набор пакетов (loguru, python-dotenv)

### Текущие связи с модулями проекта

Модуль `common` активно используется в следующих компонентах:

- **fabric/io/db.py** - логирование операций с базой данных
- **fabric/io/graph_store.py** - логирование операций с графовым хранилищем
- **ir/migrations/** - система миграций для Policy IR артефактов
- **scientist/orchestrator/** - логирование и миграции в оркестраторе экспериментов
- **fabric/udf/** - логирование в UDF движке
- **jax_bootstrap.py** - настройка JAX окружения перед импортом JAX
- **run_experiment.py** - конфигурация и логирование основного экспериментального пайплайна

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

## Модули

### `config.py` - Конфигурация приложения и инфраструктуры

**Цель:** Централизованная настройка всех зависимостей проекта с защитой от перегрузки системы.

#### Функциональность:

1. **JAX Environment Setup (Критично - выполняется ДО импорта JAX)**
   - Принудительная установка CPU как платформы: `JAX_PLATFORM_NAME=cpu`
   - Отключение 64-битных вычислений: `JAX_ENABLE_X64=false`
   - Отключение большинства оптимизаций: `JAX_DISABLE_MOST_OPTIMIZATIONS=true`
   - Отключение проверки утечек трассировщиков: `JAX_CHECK_TRACER_LEAKS=false`

2. **Hardware Safeguards (Защита железа)**
   - Автоматическое определение физических ядер CPU
   - Резерв 20% ядер для системы (минимум 1 ядро)
   - Расчет безопасного количества ядер: `max(1, total_cores - reserved_cores)`

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

# Memory & CPU
XLA_PYTHON_CLIENT_PREALLOCATE=false
XLA_FLAGS=--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads={auto}

# DuckDB
DUCKDB_MEMORY_LIMIT=4GB
DUCKDB_THREADS={auto}                # Автоматически = доступным ядрам CPU

# Логирование
LOG_LEVEL=DEBUG
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
   - Текущая версия: `POLICY_IR_CURRENT_VERSION = "1.0"`
   - Миграция `0.9 → 1.0`: нормализация полей (`projectName` → `project_name`, `globalConstraints` → `global_constraints`)

#### Пример использования:

```python
from polisyos.common.migrations import migrate_artifact

# Миграция Dataset Manifest
manifest_data = {"schema_version": "0.9", "datasetName": "test"}
migrated = migrate_artifact(manifest_data, "dataset_manifest", "1.0")
# Результат: {"schema_version": "1.0", "dataset_name": "test"}

# Миграция Policy IR
policy_data = {"schema_version": "0.9", "projectName": "policy"}
migrated = migrate_artifact(policy_data, "policy_ir", "1.0")
# Результат: {"schema_version": "1.0", "project_name": "policy"}
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
apply_jax_env_defaults()  # Применяет безопасные JAX настройки

# Затем в коде проекта:
from polisyos.common import config  # Импорт config после jax_bootstrap
from polisyos.common.logger import get_logger
log = get_logger(__name__)
```

### Использование в модулях проекта:

```python
# В fabric/io/db.py (логирование операций БД)
from polisyos.common.logger import get_logger
log = get_logger(__name__)

def save_simulation_data(self, data):
    log.info("Saving simulation data", run_id=self.run_id)
    # ... операции с БД ...

# В ir/migrations/__init__.py (миграции Policy IR)
from polisyos.common.migrations import migrate_artifact, POLICY_IR_CURRENT_VERSION

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

- **`jax_bootstrap.py`** - применение JAX настроек перед импортом JAX
- **`run_experiment.py`** - конфигурация и логирование основного экспериментального пайплайна
- **`fabric/io/db.py`** - логирование операций с DuckDB
- **`fabric/io/graph_store.py`** - логирование операций с графовым хранилищем
- **`fabric/materializer.py`** - логирование операций материализации
- **`fabric/udf/engine.py`** - логирование UDF движка
- **`scientist/orchestrator/compiler.py`** - логирование компиляции экспериментов
- **`scientist/orchestrator/data_loader.py`** - логирование загрузки данных
- **`ir/migrations/__init__.py`** - обертка над системой миграций для Policy IR

### Архитектурные связи:

- **runtime:** Использует логирование и миграции для артефактов
- **ir:** Зависит от миграций для версионирования Policy IR схем
- **scientist/fabric/foundry:** Используют конфигурации, логирование и JAX настройки

## Контрибьютинг

При добавлении новых компонентов в `common`:

1. **Проверить зависимости:** Не добавлять тяжелые импорты
2. **Тестировать изоляцию:** Работает без других слоев
3. **Документировать:** Обновить этот README
4. **Следовать принципам:** Инфраструктура, не бизнес-логика
