# Tools - Инструменты разработчика Policy Engine

Коллекция утилит для разработки, тестирования, диагностики и демонстрации Policy Engine. Все инструменты следуют принципам архитектуры проекта и обеспечивают соблюдение [Законов системы](https://github.com/your-repo/architecture.md).

## Структура папки

```
tools/
├── benchmarks/           # Бенчмарки производительности системы
│   ├── bench_domain.py   # Тест доменной модели (JAX + Equinox + GlobalState)
│   └── bench_simulation.py # Тест полного симуляционного пайплайна
├── demos/               # Демонстрационные скрипты возможностей
│   ├── run_export_demo.py      # Экспорт результатов симуляции в разные форматы
│   ├── run_ingest_demo.py      # Полный ingestion пайплайн (CSV → DuckDB + Kuzu)
│   ├── run_optimizer_demo.py   # Многокритериальная оптимизация политик (NSGA-II)
│   ├── run_udf_hybrid_demo.py  # Гибридные запросы (SQL + Python UDF)
│   └── run_udf_query_demo.py   # UDF запросы к Unified Data Fabric
├── diagnostics/         # Диагностика и анализ системы
│   ├── check_setup.py           # Проверка установки всех компонентов
│   ├── check_udf_perf.py        # Профилирование производительности UDF
│   └── generate_ir_schema.py    # Генерация JSON Schema для IR компонентов
├── gen_schema.py        # Генератор JSON Schema из Pydantic моделей
├── lint_foundry.py      # Архитектурный линтер foundry модуля
├── lint_imports.py      # Линтер межмодульных зависимостей (Закон A)
├── migrate.py           # Миграция dataset manifests и policy IR
└── migrate_ir.py        # Специализированная миграция Policy IR артефактов
```

## Быстрый старт

Все инструменты запускаются из корня проекта с корректным PYTHONPATH:

```bash
cd policy-engine/

# Проверка установки
python tools/diagnostics/check_setup.py

# Линтинг архитектуры
python tools/lint_imports.py
python tools/lint_foundry.py

# Генерация схем
python tools/gen_schema.py --check
```

## Архитектурные линтеры

### lint_imports.py - Линтер межмодульных зависимостей

Проверяет соблюдение **Закона A** (направленный граф зависимостей только внутрь) и выявляет архитектурные нарушения:

**Разрешенные зависимости:**
- `scientist` → {`ir`, `fabric`, `foundry`} (orchestration использует все)
- `fabric` → {`ir`} (data fabric зависит от типов/контрактов)
- `foundry` → {`ir`} (математическое ядро использует только типы)
- `ir` → {`core`} (IR зависит от базовых утилит)
- `runtime` → {`ir`, `core`} (runtime использует контракты)
- `core` → никого (фундаментальные утилиты)

**Анализ связей:**
- Парсит все Python файлы в `src/polisyos/`
- Строит граф импортов между модулями
- Выявляет запрещенные обратные зависимости
- Проверяет циклы в зависимостях

```bash
# Полная проверка архитектуры
python tools/lint_imports.py

# Детальный вывод с топ-10 "богатых" файлов
python tools/lint_imports.py --verbose --top 10

# Проверка только runtime зависимостей (без TYPE_CHECKING)
python tools/lint_imports.py --fail-on-type-checking
```

**Запрещенные паттерны:**
- Foundry не может импортировать fabric (БД/IO нарушает чистоту математического ядра)
- Fabric не может импортировать scientist (LLM/orchestration нарушает data layer)
- Обратные зависимости нарушают Закон A
- Циклические импорты между пакетами

### lint_foundry.py - Архитектурный линтер foundry модуля

Обеспечивает чистоту математического ядра согласно **Закону B** ("Ты строишь компилятор") - foundry должно быть чистым функциональным ядром без side effects.

**Категории запрещенных импортов:**

**Базы данных и IO:**
- `duckdb`, `kuzu`, `sqlite3`, `sqlalchemy`
- `pandas`, `polars`, `pyarrow`

**Сетевые операции:**
- `requests`, `httpx`, `urllib`

**Файловая система:**
- `os`, `pathlib`, `shutil`, `glob`, `tempfile`
- `open`, встроенные file operations

**Недетерминированность:**
- `random`, `time` (кроме `time.perf_counter` для профилирования)
- `print`, `logging` (кроме структурированного логирования через loguru)

**Разрешено в foundry:**
- `jax`, `jax.numpy`, `equinox`, `optax`
- `typing`, `dataclasses`, `functools`
- Собственные модули: `ir.*` (только типы), `core.*`

```bash
# Линтинг всего foundry модуля
python tools/lint_foundry.py

# С указанием пути к репозиторию
python tools/lint_foundry.py --repo-root /path/to/policy-engine

# Детальный вывод всех нарушений
python tools/lint_foundry.py --verbose
```

## Генерация схем

### gen_schema.py - Генератор JSON Schema из Pydantic моделей

Генерирует и валидирует JSON Schema согласно **Закону C** ("Контракты - единственный источник истины").

**Работает с:**
- `PolicyRequestIR` из `polisyos.ir.contract`
- Все Pydantic модели в IR модуле
- Автоматическая генерация из type hints

**Режимы работы:**

```bash
# Генерация новой схемы
python tools/gen_schema.py --output policy_ir_schema.json

# Проверка соответствия существующей схеме (CI gate)
python tools/gen_schema.py --check --output policy_ir_schema.json

# Сравнение с текущей схемой (diff output)
python tools/gen_schema.py --check --output policy_ir_schema.json 2>&1 | head -20
```

**Что проверяется:**
- Структурная валидность PolicyRequestIR
- Совместимость версий Pydantic (v2 required)
- Детерминированность генерации схемы
- Совпадение с зафиксированным snapshot

## Миграции

### migrate_ir.py - Миграция Policy IR артефактов

Специализированный инструмент для миграции Policy IR между версиями согласно **Закону C**.

**Поддерживает:**
- JSON и YAML форматы (опционально PyYAML)
- Семантическое версионирование (major.minor.patch)
- Безопасные миграции с откатом
- Валидация структуры после миграции

```bash
# Базовая миграция с валидацией
python tools/migrate_ir.py input_ir.json output_ir.json --to v3.0.0

# Миграция с major изменениями (breaking changes)
python tools/migrate_ir.py input_ir.json output_ir.json --to v4.0.0 --allow-major

# Конвертация форматов
python tools/migrate_ir.py policy_v1.yml migrated_policy.json --to v2.1.0
```

**Интеграция с:**
- `polisyos.ir.migrations.migrate_policy_ir`
- `polisyos.ir.migrations.IR_CURRENT_VERSION`
- Pydantic модели для валидации

### migrate.py - Универсальная миграция артефактов

Обобщенный инструмент для миграции различных типов артефактов Policy Engine.

**Поддерживаемые типы:**
- `dataset_manifest` - Dataset manifests
- `policy_ir` - Policy IR (делегирует migrate_ir.py)
- `run_manifest` - Run manifests

```bash
# Миграция dataset manifest
python tools/migrate.py dataset_manifest data/manifest_v1.json data/manifest_v2.json --to v2.1.0

# Миграция policy IR (через migrate_ir.py)
python tools/migrate.py policy_ir old_ir.json new_ir.json --to v3.0.0

# С поддержкой YAML
python tools/migrate.py policy_ir policy.yml migrated_policy.json --to v2.5.0
```

## Диагностика

### check_setup.py - Проверка установки компонентов

Комплексный smoke test установки всех компонентов Policy Engine с учетом архитектурных зависимостей.

**Проверяет интеграцию:**
- **JAX экосистема:** загрузка JAX, устройств, базовые операции
- **Базы данных:** DuckDB (аналитическое хранилище), Kuzu (графовая БД)
- **Python стек:** Python 3.11+, Pydantic v2, Equinox
- **Модули:** импорт всех основных модулей (core, ir, fabric, foundry, scientist, runtime)

**Интеграция с:**
- `polisyos.common.config` (конфигурация лимитов)
- `jax_bootstrap.py` (форсирование CPU на macOS)
- `.env` переменные окружения

```bash
# Полная проверка установки
python tools/diagnostics/check_setup.py

# С детальным логированием
POLICY_ENGINE_LOG_LEVEL=DEBUG python tools/diagnostics/check_setup.py
```

**Вывод при успехе:**
```
🟢 JAX Environment: OK (platform=cpu, devices=1)
🟢 Database Connections: OK (DuckDB + Kuzu)
🟢 Core Imports: OK (Pydantic, Equinox, Diffrax)
🟢 Basic Operations: OK (tensor creation, random gen)
🚀 Policy Engine is ready for development!
```

**Переменные окружения:**
- `POLICY_ENGINE_ALLOW_JAX_METAL=0/1` - разрешение JAX Metal на macOS
- `POLICY_ENGINE_LOG_LEVEL=DEBUG/INFO` - уровень логирования

### check_udf_perf.py - Анализ производительности UDF

Профилирование и анализ производительности пользовательских функций в контексте Unified Data Fabric.

```bash
# Анализ UDF производительности
python tools/diagnostics/check_udf_perf.py

# Метрики:
# - Время выполнения запросов
# - Память использования
# - CPU нагрузка
# - DuckDB vs Kuzu сравнение
```

### generate_ir_schema.py - Генератор IR схем

Автоматическая генерация схем для всех IR компонентов с валидацией структуры.

```bash
# Генерация полной IR схемы
python tools/diagnostics/generate_ir_schema.py

# Вывод:
# - JSON Schema для всех Pydantic моделей
# - Валидация структур данных
# - Совместимость версий
```

## Бенчмарки

### bench_domain.py - Бенчмарк доменной модели

Производительность JAX доменной модели foundry - тестирование масштабируемости на больших состояниях.

**Тестирует:**
- `GlobalState` аллокацию для миллионов агентов
- JAX JIT компиляцию функциональных обновлений
- Векторизованные операции (grants, taxes)
- Память эффективность Equinox структур

**Интеграция с:**
- `polisyos.foundry.domain.state.GlobalState`
- `polisyos.common.logger`
- JAX JIT и векторизация

```bash
# Тест на 1M агентов (рекомендуемый)
python tools/benchmarks/bench_domain.py

# С кастомным размером
python tools/benchmarks/bench_domain.py --n-agents 500000
```

**Типичный вывод:**
```
🚀 Starting Domain Model Check...
Allocating state for 1,000,000 agents...
✅ Memory allocation: 2.3GB
✅ JIT compilation: 1.2s
✅ Vectorized operations: 45ms per step
✅ Domain Layer is JAX-compatible!
```

### bench_simulation.py - Бенчмарк симуляционного ядра

Полносистемный бенчмарк симуляционного пайплайна foundry - от доменной модели до экономической логики.

**Тестирует полный цикл:**
- Экономический цикл (производство → потребление → рынок)
- Механизмы политик (TaxSubsidy, IncomeTax, Queue)
- JAX JIT оптимизации
- Память эффективность на больших состояниях

**Интеграция с:**
- `polisyos.foundry.engine.kernel.SimulationKernel`
- `polisyos.foundry.domain.*` (экономическая логика)
- Полный foundry стек

```bash
# Полный симуляционный бенчмарк
python tools/benchmarks/bench_simulation.py

# С кастомными параметрами
python tools/benchmarks/bench_simulation.py --n-steps 100 --n-agents 10000
```

## Демонстрации

### run_ingest_demo.py - Демонстрация ingestion пайплайна

Полная демонстрация Unified Data Fabric ingestion: от сырых CSV до готовых баз данных.

**Этапы пайплайна:**
1. **Генерация тестовых данных** - CSV файлы (agents, interactions, macro)
2. **Pydantic валидация** - проверка структуры данных
3. **Parquet конвертация** - columnar storage для аналитики
4. **Загрузка в DuckDB** - аналитическое хранилище временных рядов
5. **Загрузка в Kuzu** - графовая БД для взаимодействий агентов
6. **Генерация manifests** - JSON метаданные для reproducible runs

**Интеграция с:**
- `polisyos.fabric.ingestion.run_ingestion`
- `polisyos.fabric.io.db.SimulationDB`
- `polisyos.fabric.io.graph_store.GraphStore`
- `polisyos.ir.data_views.*` (UDF запросы)

```bash
# Запуск полного ingestion пайплайна
python tools/demos/run_ingest_demo.py

# Создает файлы:
# - data/raw/*.csv (исходные данные)
# - data/staging/*.parquet (обработанные)
# - demo_udf.duckdb (аналитическая БД)
# - demo_udf.kuzu (графовая БД)
```

### run_udf_query_demo.py - UDF запросы

Демонстрация гибридных запросов с пользовательскими функциями (SQL + Python UDF).

```bash
# Запуск UDF демонстрации
python tools/demos/run_udf_query_demo.py

# Показывает:
# - Регистрацию Python функций в DuckDB
# - Гибридные SQL + Python запросы
# - Kuzu графовые запросы с UDF
```

### run_optimizer_demo.py - Оптимизация политик

Демонстрация многокритериальной оптимизации политик с PyMOO (NSGA-II).

```bash
# Запуск оптимизации
python tools/demos/run_optimizer_demo.py

# Процесс:
# 1. Настройка целевых функций (GDP, inequality, unemployment)
# 2. Определение параметров политик
# 3. NSGA-II оптимизация
# 4. Pareto front анализ
# 5. Визуализация результатов
```

### run_udf_hybrid_demo.py - Гибридные UDF

Продвинутая демонстрация комбинации SQL запросов и Python функций.

```bash
# Гибридная UDF демонстрация
python tools/demos/run_udf_hybrid_demo.py

# Возможности:
# - Комплексные агрегации
# - Машинное обучение в запросах
# - Статистические функции
# - Временные ряды анализ
```

### run_export_demo.py - Экспорт симуляционных данных

Демонстрация экспорта результатов симуляции в различные форматы для downstream анализа.

```bash
# Экспорт симуляционных данных
python tools/demos/run_export_demo.py

# Поддерживаемые форматы:
# - Parquet (columnar, аналитика)
# - JSON (метаданные, конфигурация)
# - CSV (legacy совместимость)
# - HDF5 (большие числовые массивы)
```

## Архитектурная интеграция

Инструменты `tools/` обеспечивают качество и надежность всей системы Policy Engine, интегрируясь со всеми основными модулями:

### Связи с модулями проекта

| Инструмент | Зависимости от модулей | Проверяет/Тестирует |
|------------|----------------------|---------------------|
| `lint_imports.py` | `core.*` | Закон A (направленные зависимости) |
| `lint_foundry.py` | - | Закон B (чистота математического ядра) |
| `gen_schema.py` | `ir.contract` | Закон C (контракты как источник истины) |
| `migrate_ir.py` | `ir.migrations` | Закон C (детерминированные миграции) |
| `check_setup.py` | `common.config`, все модули | Системная интеграция |
| `check_udf_perf.py` | `fabric.*`, `ir.data_views` | Производительность Data Fabric |
| `bench_domain.py` | `foundry.domain.*` | Масштабируемость JAX модели |
| `bench_simulation.py` | `foundry.*` | Полный симуляционный пайплайн |
| `run_ingest_demo.py` | `fabric.*`, `ir.*` | Unified Data Fabric |
| `run_udf_*_demo.py` | `fabric.udf.*` | Гибридные запросы |
| `run_optimizer_demo.py` | `scientist.*` | Многокритериальная оптимизация |

### Архитектурные гарантии

**Закон A (Направленный граф зависимостей):**
- `lint_imports.py` предотвращает обратные зависимости
- Обеспечивает чистоту слоев архитектуры

**Закон B (Компиляторная архитектура):**
- `lint_foundry.py` защищает математическое ядро от IO/сетевых операций
- Foundry остается чистым функциональным ядром

**Закон C (Контракты как источник истины):**
- `gen_schema.py` и `migrate_*` обеспечивают эволюцию схем
- Детерминированные миграции между версиями

**Закон D (Воспроизводимость и аудит):**
- Все инструменты имеют `--seed`, `--run-id` для reproducible runs
- Полная трассировка артефактов и версий

## Использование в CI/CD

Рекомендуемый pipeline качества для Policy Engine:

```yaml
# .github/workflows/ci.yml
- name: System readiness check
  run: |
    python tools/diagnostics/check_setup.py

- name: Architecture compliance (Законы A, B, C)
  run: |
    python tools/lint_imports.py --fail-on-cycles
    python tools/lint_foundry.py
    python tools/gen_schema.py --check --output policy_ir_schema.json

- name: Performance regression gate
  run: |
    python tools/benchmarks/bench_domain.py
    python tools/benchmarks/bench_simulation.py
    python tools/diagnostics/check_udf_perf.py --baseline data/curated/udf_perf_baseline.json

- name: Integration smoke tests
  run: |
    python tools/demos/run_ingest_demo.py
    python tools/demos/run_udf_query_demo.py
```

## Архитектурные принципы

Все инструменты следуют core принципам Policy Engine:

### Закон A: Направленный граф зависимостей
- Инструменты проверяют и обеспечивают правильные импорты между модулями
- Предотвращают циклические зависимости

### Закон B: Компиляторная архитектура
- Foundry остается чистым математическим ядром
- Runtime не знает про LLM, IR не знает про JAX/DuckDB

### Закон C: Контракты как источник истины
- Все артефакты имеют schema_version
- Детерминированные миграции между версиями

### Закон D: Воспроизводимость и аудит
- Все прогоны имеют run_id, seed, repro_mode
- Полная трассировка артефактов и версий

## Разработка и расширение

### Добавление нового инструмента

1. **Следуйте паттернам:**
   - Импорт sys.path manipulation для PYTHONPATH
   - Использование polisyos.common.logger
   - Argparse для CLI интерфейса
   - Docstrings на русском

2. **Категоризация:**
   - `diagnostics/` - проверки и анализ
   - `demos/` - демонстрации возможностей
   - `benchmarks/` - производительность
   - Корень - core утилиты

3. **Качество кода:**
   - Строгая типизация
   - Линтеры проходят все проверки
   - README обновляется

### Отладка инструментов

```bash
# Детальный вывод
python tools/lint_imports.py --verbose

# Сохранение логов
POLICY_ENGINE_LOG_LEVEL=DEBUG python tools/diagnostics/check_setup.py 2>&1 | tee setup.log

# Профилирование
python -m cProfile tools/benchmarks/bench_domain.py
```

## Troubleshooting

### Import errors
```bash
# Проверь PYTHONPATH
export PYTHONPATH="/path/to/policy-engine/src:$PYTHONPATH"
python tools/diagnostics/check_setup.py
```

### JAX/Metal issues (macOS)
```bash
# Принудительно CPU
export POLICY_ENGINE_ALLOW_JAX_METAL=0
python tools/diagnostics/check_setup.py
```

### Permission issues
```bash
# Используй --user для pip
pip install --user -e .[dev]
```

### Schema validation fails
```bash
# Перегенерируй схему
python tools/gen_schema.py --output policy_ir_schema.json

# Проверь diff с текущей версией
python tools/gen_schema.py --check --output policy_ir_schema.json 2>&1 | head -20
```

### Import violations detected
```bash
# Детальный анализ нарушений
python tools/lint_imports.py --verbose --top 20

# Проверь конкретный файл
python tools/lint_imports.py --src-root src | grep "problematic_file.py"
```

### Foundry linting fails
```bash
# Проверь запрещенные импорты
python tools/lint_foundry.py --verbose

# Исключи тестовые файлы если нужно
python tools/lint_foundry.py --exclude "test_*"
```

## Разработка новых инструментов

### Принципы дизайна

1. **Следуйте архитектуре:** Каждый инструмент должен соответствовать одному из архитектурных законов
2. **Интегрируйтесь с модулями:** Используйте публичные API модулей, не нарушайте инкапсуляцию
3. **CLI интерфейс:** Argparse с --help, структурированный вывод
4. **Логирование:** Используйте `polisyos.common.logger`
5. **Обработка ошибок:** Четкие exit codes, информативные сообщения

### Категоризация инструментов

- **`diagnostics/`** - анализ и проверка системы
- **`demos/`** - демонстрация возможностей (создают тестовые данные)
- **`benchmarks/`** - измерение производительности
- **Корень** - core утилиты для разработки

### Тестирование

```bash
# Добавьте тесты в tests/tools/
# Следуйте паттернам существующих тестов
pytest tests/tools/ -v
```

### Документация

1. **Обновите этот README** - добавьте описание, примеры использования
2. **Добавьте docstrings** - на русском, с примерами
3. **Убедитесь в линтинге** - все инструменты проходят свои же проверки

## Поддержка и совместимость

- **Python:** 3.11+ (тестировано на 3.11, 3.12)
- **JAX:** 0.4.x+ с JAXlib
- **Pydantic:** v2 only ( breaking changes в v1→v2)
- **Операционные системы:** Linux, macOS, Windows (через WSL)

### Известные ограничения

- **macOS + JAX Metal:** Может требовать `POLICY_ENGINE_ALLOW_JAX_METAL=0`
- **PyYAML:** Опционально для YAML поддержки в миграциях
- **Kuzu:** Требует C++ компилятор для установки

### Версионирование

Инструменты следуют семантическому версионированию основного проекта. Критические изменения в API инструментов помечаются в changelog.

---

*Инструменты протестированы на Python 3.11+ с JAX, DuckDB, Kuzu и полным технологическим стеком Policy Engine.*
