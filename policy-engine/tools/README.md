# Tools - Инструменты разработчика Policy Engine

Коллекция утилит для разработки, тестирования, диагностики и демонстрации Policy Engine. Инструменты обеспечивают соблюдение архитектурных законов и предоставляют полный спектр возможностей от линтинга кода до end-to-end демонстраций политик.

## Структура папки

```
tools/
├── benchmarks/                 # Бенчмарки производительности системы
│   ├── bench_domain.py         # Тест доменной модели (JAX + Equinox + GlobalState)
│   │   # - Аллокация GlobalState для миллионов агентов
│   │   # - JAX JIT компиляция функциональных обновлений
│   │   # - Векторизованные операции (grants, taxes)
│   │   # - Память эффективность Equinox структур
│   └── bench_simulation.py     # Тест полного симуляционного пайплайна
│       # - Экономический цикл (производство → потребление → рынок)
│       # - Механизмы политик (TaxSubsidy, IncomeTax, Queue)
│       # - JAX JIT оптимизации для больших состояний
│       # - Полная интеграция foundry модуля
├── connectors/                 # Инструменты для работы с коннекторами данных
│   └── scaffold.py             # Генератор скелетов коннекторов
│       # - Автоматическая генерация BaseConnector наследников
│       # - Поддержка REST, CSV, SQL, SDMX типов
│       # - Генерация соответствующих тестов
│       # - Интеграция с ConnectorTestHarness
├── demos/                      # Демонстрационные скрипты возможностей
│   ├── run_export_demo.py      # Экспорт результатов симуляции в разные форматы
│   │   # - Экспорт в Parquet, JSON, CSV, HDF5
│   │   # - Поддержка downstream анализа
│   ├── run_ingest_demo.py      # Полный ingestion пайплайн (CSV → DuckDB + Kuzu)
│   │   # - Генерация тестовых данных (agents, interactions, macro)
│   │   # - Pydantic валидация и Parquet конвертация
│   │   # - Загрузка в DuckDB (аналитическое хранилище)
│   │   # - Загрузка в Kuzu (графовая БД взаимодействий)
│   │   # - Генерация manifests для reproducible runs
│   ├── run_laffer_demo.py      # Демонстрация кривой Лаффера
│   │   # - Классическая кривая Лаффера (налоговые доходы)
│   │   # - Поиск оптимальной налоговой ставки
│   │   # - Экономическая теория в действии
│   ├── run_optimizer_demo.py   # Многокритериальная оптимизация политик (NSGA-II)
│   │   # - Настройка целевых функций (GDP, inequality, unemployment)
│   │   # - PyMOO NSGA-II оптимизация
│   │   # - Pareto front анализ и визуализация
│   ├── run_udf_hybrid_demo.py  # Гибридные запросы (SQL + Python UDF)
│   │   # - Комплексные агрегации с Python функциями
│   │   # - Машинное обучение в SQL запросах
│   │   # - Статистические и временные ряды функции
│   └── run_udf_query_demo.py   # UDF запросы к Unified Data Fabric
│       # - Регистрация Python функций в DuckDB
│       # - Гибридные SQL + Python запросы
│       # - Kuzu графовые запросы с UDF
├── diagnostics/                # Диагностика и анализ системы
│   ├── check_perf_regression.py# Проверка регрессий производительности
│   │   # - Анализ pytest-benchmark JSON результатов
│   │   # - Сравнение с baseline для выявления регрессий
│   │   # - Конфигурируемые thresholds для различных метрик
│   ├── check_setup.py          # Комплексная проверка установки компонентов
│   │   # - JAX экосистема (платформа, устройства, базовые операции)
│   │   # - Базы данных (DuckDB, Kuzu)
│   │   # - Python стек (Python 3.11+, Pydantic v2, Equinox)
│   │   # - Импорт всех основных модулей
│   │   # - Интеграция с polisyos.common.config
│   ├── check_udf_perf.py       # Профилирование производительности UDF
│   │   # - Анализ времени выполнения запросов
│   │   # - Мониторинг памяти и CPU использования
│   │   # - Сравнение DuckDB vs Kuzu производительности
│   │   # - Регрессионное тестирование производительности
│   └── generate_ir_schema.py   # Генерация JSON Schema для IR компонентов
│       # - Автоматическая генерация схем из Pydantic моделей
│       # - Валидация структур данных IR
│       # - Совместимость версий и детерминированность
├── capture_env.py              # Захват и сравнение EnvironmentManifest
│   # - Снимок окружения для воспроизводимости
│   # - Сравнение двух окружений с оценкой риска
│   # - Валидация манифестов
├── check_perf_regression.py    # Проверка регрессий производительности
│   # - Анализ pytest-benchmark JSON результатов
│   # - Сравнение с baseline для выявления регрессий
│   # - Конфигурируемые thresholds для различных метрик
├── gen_schema.py               # Генератор JSON Schema из Pydantic моделей
│   # - Генерация и валидация JSON Schema по Закону C
│   # - Работа с PolicySurfaceIR и всеми IR моделями
│   # - Детерминированная генерация для CI/CD
├── lint_connectors.py          # Линтер коннекторов данных
│   # - Проверка соблюдения архитектурных законов в коннекторах
│   # - Валидация базовых интерфейсов и контрактов
│   # - Анализ зависимостей и изоляции коннекторов
├── lint_connectors.py          # Линтер коннекторов данных
│   # - Проверка соблюдения архитектурных законов в коннекторах
│   # - Валидация базовых интерфейсов и контрактов
│   # - Анализ зависимостей и изоляции коннекторов
├── lint_foundry.py             # Архитектурный линтер foundry модуля
│   # - Обеспечение чистоты математического ядра (Закон B)
│   # - Запрет импортов IO/сетевых библиотек в foundry
│   # - Проверка на недетерминированные операции
├── lint_imports.py             # Линтер межмодульных зависимостей (Закон A)
│   # - Анализ графа импортов между модулями
│   # - Выявление запрещенных обратных зависимостей
│   # - Предотвращение циклических импортов
├── migrate.py                  # Универсальная миграция артефактов
│   # - Миграция dataset_manifest, policy_ir, run_manifest
│   # - Поддержка JSON и YAML форматов
│   # - Семантическое версионирование
├── migrate_ir.py               # Специализированная миграция Policy IR
│   # - Детерминированные миграции между версиями IR
│   # - Безопасные обновления с откатом
│   # - Валидация структуры после миграции
├── migrate_to_trinity.py       # Миграция в Trinity формат
│   # - Конвертация PolicySurfaceIR в Trinity bundle
│   # - Разделение на ProblemFrame, PolicySpec, ModelSpec
│   # - Batch обработка и верификация
├── run_mechanism_design.py     # End-to-end демонстрация механизма дизайна
│   # - Дифференцируемая оптимизация политик через JAX grad
│   # - Обучение агентных политик с reinforcement learning
│   # - Полный цикл: IR → Foundry → градиентная оптимизация
├── scan_fabric.py              # Сканер DuckDB и генератор data contracts
│   # - Сканирование DuckDB файлов и извлечение схем
│   # - Генерация черновых data contracts для Unified Data Fabric
│   # - Автоматическое определение типов, единиц и PII tiers
│   # - Bootstrap утилита для быстрого старта с данными
└── visualize_provenance.py     # Визуализация и верификация provenance графов
    # - Генерация Graphviz DOT файлов для provenance графов
    # - Верификация целостности графов (orphaned nodes, cycles)
    # - Экспорт в JSON и DOT форматы
    # - Интеграция с Evidence Bundles и CAS системой
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
python tools/lint_connectors.py

# Снимок окружения
python -m tools.capture_env capture --output env.json

# Генерация схем
python tools/gen_schema.py --check

# Bootstrap data contracts из существующих DuckDB
python tools/scan_fabric.py data/curated/

# Визуализация provenance графов
python tools/visualize_provenance.py evidence.json --verify

# Проверка регрессий производительности
python tools/check_perf_regression.py benchmark_results.json

# Миграция в Trinity формат
python tools/migrate_to_trinity.py data/policies/ --dry-run

# Демонстрации возможностей
python tools/demos/run_ingest_demo.py  # Полный ingestion пайплайн
python tools/run_mechanism_design.py   # Дифференцируемый механизм дизайна
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

### lint_connectors.py - Линтер коннекторов данных

Специализированный линтер для проверки архитектурной корректности коннекторов данных согласно **Законам A и E**. Обеспечивает изоляцию коннекторов и соблюдение контрактов данных.

**Проверяемые аспекты:**

**Архитектурная изоляция:**
- Коннекторы не могут импортировать scientist.* (LLM нарушает data layer)
- Запрещены прямые импорты fabric.* (кроме типов)
- Соблюдение направленного графа зависимостей (Закон A)

**Интерфейсная корректность:**
- Наследование от BaseConnector
- Реализация обязательных методов (connect, disconnect, fetch, health_check)
- Правильные сигнатуры методов и возвращаемые типы

**Контрактная валидность:**
- Наличие metadata с правильной структурой
- Валидные connector_id и namespace
- Правильные capability declarations
- Соответствие TrustLevel и QualityTier

**Закон E (Evidence и provenance):**
- FetchResult должен содержать provenance_ref
- Корректная генерация DataVersion
- Интеграция с CAS системой для evidence tracking

```bash
# Линтинг всех коннекторов
python tools/lint_connectors.py

# Проверка конкретного коннектора
python tools/lint_connectors.py --connector custom.my_connector

# Детальный вывод с предупреждениями
python tools/lint_connectors.py --verbose

# Проверка только интерфейсов
python tools/lint_connectors.py --check-interfaces-only
```

**Обнаруживаемые нарушения:**
- Неправильные импорты нарушающие архитектуру
- Отсутствующие обязательные методы
- Некорректные metadata declarations
- Нарушения capability contracts
- Отсутствие provenance в fetch результатах

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
- `PolicySurfaceIR` из `polisyos.ir.surface`
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
- Структурная валидность PolicySurfaceIR
- Совместимость версий Pydantic (v2 required)
- Детерминированность генерации схемы
- Совпадение с зафиксированным snapshot

## Захват окружения

### capture_env.py - Захват и сравнение Environment Manifest

Инструмент для захвата, сравнения и валидации Environment Manifest согласно **Закону D** ("Воспроизводимость и аудит"). Позволяет отслеживать изменения в окружении и оценивать риски несовместимости.

**Функциональность:**
- **Захват окружения:** Полный snapshot системного окружения (Python, JAX, OS, hardware)
- **Сравнение окружений:** Детальное сравнение двух манифестов с оценкой рисков
- **Валидация:** Проверка корректности структуры манифеста
- **Риск-оценка:** Автоматическая классификация изменений по уровню риска

**Режимы работы:**

```bash
# Захват текущего окружения
python -m tools.capture_env capture --output env.json

# Сравнение двух окружений
python -m tools.capture_env compare baseline.json current.json

# Валидация манифеста
python -m tools.capture_env validate env.json
```

**Что захватывается:**
- Версии Python, pip, системных библиотек
- JAX конфигурация (платформа, устройства, версии)
- Операционная система и архитектура
- Аппаратные характеристики (CPU, память, GPU)
- Переменные окружения (отфильтрованные)
- Установленные пакеты Python

**Уровни риска:**
- **CRITICAL:** Изменения, гарантированно ломающие совместимость
- **HIGH:** Высокий риск несовместимости
- **MEDIUM:** Возможные проблемы совместимости
- **LOW:** Минорные изменения
- **INFO:** Информационные изменения

## Проверка регрессий производительности

### check_perf_regression.py - Анализ регрессий производительности

Инструмент для анализа результатов pytest-benchmark и выявления регрессий производительности согласно **Закону D** ("Воспроизводимость и аудит"). Сравнивает текущие результаты бенчмарков с baseline для автоматического выявления degradation производительности.

**Функциональность:**
- **Загрузка результатов:** Чтение JSON файлов из pytest-benchmark
- **Сравнение с baseline:** Автоматический поиск последнего baseline файла
- **Анализ регрессий:** Выявление замедлений выше заданного threshold
- **Конфигурируемые thresholds:** Настраиваемый процент регрессии

**Режимы работы:**

```bash
# Проверка регрессий с автоматическим поиском baseline
python tools/check_perf_regression.py benchmark_results.json

# С явным указанием baseline файла
python tools/check_perf_regression.py benchmark_results.json --baseline baseline.json

# Кастомный threshold регрессии (по умолчанию 5%)
python tools/check_perf_regression.py benchmark_results.json --threshold 0.10
```

**Вывод при регрессии:**
```
Performance regressions detected:
- test_simulation_step: 1.2500s vs 1.0000s (+25.00%)
- test_data_ingestion: 0.8500s vs 0.8000s (+6.25%)
```

**Интеграция с:**
- `pytest-benchmark` JSON формат результатов
- CI/CD пайплайны для автоматического мониторинга
- `polisyos.common.logger` для структурированного логирования

### diagnostics/check_perf_regression.py - Альтернативная версия в diagnostics

Расширенная версия инструмента проверки регрессий производительности, интегрированная в папку diagnostics. Предоставляет дополнительные возможности анализа и интеграции с другими диагностическими инструментами.

```bash
# Использование версии из diagnostics
python tools/diagnostics/check_perf_regression.py benchmark_results.json --verbose
```

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

### migrate_to_trinity.py - Миграция в Trinity формат

Специализированный инструмент для миграции PolicySurfaceIR в новый Trinity формат согласно **Закону C**. Trinity разделяет монолитный PolicySurfaceIR на три независимых компонента: ProblemFrame, PolicySpec и ModelSpec.

**Trinity формат:**
- **ProblemFrame:** "Что" - определение проблемы и критерии успеха
- **PolicySpec:** "Как" - спецификация политик и интервенций
- **ModelSpec:** "С чем" - модельные предположения и данные

**Возможности:**
- Batch миграция директорий с политиками
- Верификация через round-trip сравнение семантических отпечатков
- Создание резервных копий перед миграцией
- Детальная отчетность о процессе миграции

**Режимы работы:**

```bash
# Dry-run миграция директории (без изменений)
python tools/migrate_to_trinity.py data/policies/ --dry-run

# Миграция с резервным копированием и верификацией
python tools/migrate_to_trinity.py data/policies/ --backup --verify

# Миграция одиночного файла
python tools/migrate_to_trinity.py policy.yaml --output trinity_policy.yaml

# Batch миграция с отчетом
python tools/migrate_to_trinity.py data/policies/ --report migration_report.json
```

**Верификация миграции:**
- Семантическое сравнение отпечатков (fingerprint matching)
- Проверка структурной целостности Trinity bundle
- Валидация обратной совместимости (merge back to SurfaceIR)
- Генерация детальных отчетов о преобразованиях

**Интеграция с модулями:**
- `polisyos.ir.trinity.*` - Trinity формат структуры
- `polisyos.ir.migrations.trinity_migration` - логика миграции
- `polisyos.ir.loaders` - загрузка и сохранение политик
- Pydantic модели для валидации

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

### check_perf_regression.py - Проверка регрессий производительности

Инструмент для анализа результатов pytest-benchmark и выявления регрессий производительности в CI/CD пайплайнах.

#### Функциональность

**Анализ результатов:**
- Загрузка JSON файлов из pytest-benchmark
- Сравнение с baseline (автоматический поиск или явное указание)
- Выявление замедлений выше заданного threshold
- Конфигурируемые thresholds для различных метрик

**Режимы работы:**

```bash
# Проверка с автоматическим поиском baseline
python tools/diagnostics/check_perf_regression.py benchmark_results.json

# С явным указанием baseline файла
python tools/diagnostics/check_perf_regression.py current.json --baseline baseline.json

# Кастомный threshold регрессии (по умолчанию 5%)
python tools/diagnostics/check_perf_regression.py results.json --threshold 0.10
```

**Вывод при регрессии:**
```
Performance regressions detected:
- test_simulation_step: 1.2500s vs 1.0000s (+25.00%)
- test_data_ingestion: 0.8500s vs 0.8000s (+6.25%)
```

#### Интеграция с модулями

- `pytest-benchmark` JSON формат результатов
- CI/CD пайплайны для автоматического мониторинга
- `polisyos.common.logger` для структурированного логирования

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

### run_laffer_demo.py - Кривая Лаффера

Демонстрация классической экономической кривой Лаффера - зависимости налоговых доходов от ставки налога. Показывает, как поведенческая экономика и теория рационального выбора объясняют нелинейные эффекты налоговой политики.

**Экономическая модель:**
- **Агенты:** 10,000 агентов с гетерогенными доходами и aversion к риску
- **Поведение:** Агенты могут скрывать доходы, балансируя между налогами и риском обнаружения
- **Обучение:** Дифференцируемая оптимизация через JAX градиенты

**Что демонстрируется:**
- Нелинейная зависимость доходов от налоговой ставки
- Поведенческая реакция агентов на налоговую политику
- Поиск оптимальной ставки через градиентный спуск
- Влияние параметров модели на форму кривой

```bash
# Запуск демонстрации кривой Лаффера
python tools/demos/run_laffer_demo.py

# Вывод:
# - Таблица налоговых ставок и соответствующих доходов
# - График кривой Лаффера с пиком доходов
# - Корреляция между риск-aversion и compliance
# - Оптимальная ставка налога (~30-55%)
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

### run_mechanism_design.py - Дифференцируемый механизм дизайна

Полнофункциональная демонстрация end-to-end механизма дизайна с дифференцируемой оптимизацией политик через JAX градиенты. Показывает полный цикл от спецификации политики до оптимизации через градиентный спуск.

**Ключевые возможности:**
- Обучение агентных политик с reinforcement learning (5000 агентов)
- Дифференцируемая оптимизация налоговой ставки через градиентный спуск
- Полный цикл: PolicySurfaceIR → Foundry компиляция → JAX оптимизация
- Демонстрация кривой Лаффера с автоматическим поиском оптимума
- Стабилизированные градиенты для надежной сходимости

**Модель поведения агентов:**
- Агенты с гетерогенными предпочтениями к риску
- Рациональный выбор между compliance и tax evasion
- Поведенческая реакция на изменения налоговой политики
- Обучение через reinforcement learning с JAX градиентами

**Интеграция с модулями:**
- `polisyos.foundry.compiler.compile_surface_policy` - компиляция IR в executable
- `polisyos.foundry.agents.AgentPolicy` - агентные политики
- `polisyos.foundry.domain.state.GlobalState` - симуляционное состояние
- JAX градиенты и автоматическое дифференцирование
- `polisyos.core.artifacts.store.FileSystemCAS` - хранение артефактов

**Примеры использования:**

```bash
# Полная демонстрация механизма дизайна
python tools/run_mechanism_design.py

# С кастомными параметрами
python tools/run_mechanism_design.py --n-agents 10000 --learning-rate 0.01

# Вывод включает:
# - Обучение агентных политик (500 итераций)
# - Таблица рациональности агентов (риск ↔ налоговая стратегия)
# - Оптимизация налоговой ставки через градиенты
# - Финальный оптимум (~30-55% по кривой Лаффера)
# - Метрики сходимости и стабильности обучения
```

**Архитектурное значение:**
Демонстрирует **Закон B** (компиляторная архитектура) в действии - полный цикл от высокоуровневой спецификации политики до оптимизации через градиенты, с чистым разделением между IR, компилятором и математическим ядром.

### scan_fabric.py - Сканер DuckDB и генератор data contracts

Bootstrap утилита для быстрого старта работы с Unified Data Fabric. Автоматически сканирует существующие DuckDB файлы, извлекает схемы таблиц и генерирует черновые data contracts с автоматическим определением типов, единиц измерения и уровней PII.

**Функциональность:**
- **Сканирование схем:** Автоматическое извлечение структуры таблиц из DuckDB файлов
- **Маппинг типов:** Преобразование DuckDB типов в стандартные типы данных (int, float, string, array, json)
- **Интеллектное определение:** Автоматическое определение единиц измерения и PII tiers на основе названий колонок
- **Генерация контрактов:** Создание полных data contract структур с метаданными
- **Bootstrap workflow:** Разработчик аннотирует черновики описаниями и проверяет автоматически определенные параметры

**Алгоритмы определения:**
- **PII tier:** Эвристический анализ названий колонок (high: ssn, password; medium: email, phone; low: age, income)
- **Единицы измерения:** Паттерн-матчинг (usd для цен, ratio для ставок, count для количества)
- **Отображаемые имена:** Автоматическое преобразование snake_case в Title Case
- **Канонические ID:** Формат `{db}.{table}.{column}` с нормализацией

**Интеграция с:**
- `polisyos.fabric.catalog.*` - система data contracts
- DuckDB read-only соединения
- `polisyos.ir.contracts.DataContract` - структура контрактов
- JSON Schema валидация

**Примеры использования:**

```bash
# Сканирование директории с DuckDB файлами
python tools/scan_fabric.py data/curated/

# Сканирование с verbose выводом и деталями
python tools/scan_fabric.py data/curated/ -v

# Вывод в конкретный файл
python tools/scan_fabric.py data/curated/ -o my_contracts.json

# Использование кастомного glob паттерна
python tools/scan_fabric.py data/ -glob "**/*.duckdb"

# Сканирование с интерактивным режимом
python tools/scan_fabric.py data/curated/ --interactive
```

**Вывод:**
```
Scanning database.duckdb...
  Found 15 columns in 3 tables
Generated 15 draft contracts to draft_contracts.json

Next steps:
  1. Review and edit the generated contracts
  2. Fill in TODO descriptions
  3. Verify units and PII tiers
  4. Move to production: mv draft_contracts.json data/curated/data_contracts.json
```

**Структура генерируемого контракта:**
```json
{
  "metric_id": "demo_db.agents.income",
  "display_name": "Income",
  "description": "TODO: Describe income from agents",
  "dtype": "float",
  "unit": "usd",
  "pii_tier": "low",
  "source_system": "/path/to/database.duckdb",
  "source_table": "agents",
  "source_column": "income"
}
```

**Архитектурное значение:**
Инструмент реализует **Закон E** (Evidence и provenance обязательны), предоставляя автоматизированную генерацию data contracts - основы для provenance tracking и evidence collection в Unified Data Fabric.

### visualize_provenance.py - Визуализация и верификация provenance графов

Инструмент для визуализации и верификации provenance графов согласно **Закону E** ("Evidence и provenance обязательны"). Позволяет анализировать происхождение данных, выявлять проблемы в графах зависимостей и генерировать визуализации для отладки.

**Функциональность:**

**Загрузка графов:**
- Загрузка из файлов JSON или evidence bundles
- Разрешение provenance_ref через CAS систему
- Поддержка различных форматов хранения

**Верификация целостности:**
- Проверка на orphaned nodes (узлы без связей)
- Выявление dangling references (ссылки на несуществующие узлы)
- Детекция циклов в wasDerivedFrom отношениях
- Валидация всех обязательных полей

**Визуализация:**
- Экспорт в Graphviz DOT формат для визуализации
- Цветовое кодирование по типам узлов (entities, activities, agents)
- Стилизация отношений (derived, generated, used, attributed, associated)
- Генерация PNG/SVG через Graphviz

**Экспорт:**
- JSON дамп графов с форматированием
- DOT файлы для Graphviz визуализации
- Поддержка stdout и файлового вывода

**Примеры использования:**

```bash
# Генерация DOT файла из evidence bundle
python tools/visualize_provenance.py evidence.json --format dot > graph.dot
dot -Tpng graph.dot -o graph.png

# Верификация графа с CAS разрешением
python tools/visualize_provenance.py provenance.json --cas-root .polisyos --verify

# Экспорт в JSON формат
python tools/visualize_provenance.py graph.json --format json --output graph_pretty.json

# Детальная верификация с verbose выводом
python tools/visualize_provenance.py evidence.json --verify --verbose
```

**Типы отношений в provenance:**
- `wasDerivedFrom` - трансформация данных (синие сплошные линии)
- `wasGeneratedBy` - генерация данных активностью (зеленые пунктирные)
- `used` - использование данных активностью (оранжевые точечные)
- `wasAttributedTo` - атрибуция агенту (фиолетовые сплошные)
- `wasAssociatedWith` - ассоциация агента с активностью (фиолетовые пунктирные)

**Интеграция с модулями:**
- `polisyos.core.artifacts.ids.ArtifactID` - идентификаторы артефактов
- `polisyos.core.artifacts.store.FileSystemCAS` - Content Addressable Storage
- JSON Schema валидация provenance структур

**Примеры вывода верификации:**
```
VERIFICATION FAILED:
  - ORPHANED: Node 'data_entity_123' not connected to any edge
  - DANGLING: Edge source 'activity_456' not found in nodes
  - CYCLE: Circular dependency detected in wasDerivedFrom edges
```

**Архитектурное значение:**
Критический инструмент для **Закона E**, обеспечивающий целостность и traceability данных в системе. Позволяет визуально анализировать и верифицировать provenance графы, выявляя проблемы в data lineage и evidence collection.

### visualize_provenance.py - Визуализация и верификация provenance графов

Инструмент для визуализации и верификации provenance графов согласно **Закону E** ("Evidence и provenance обязательны"). Позволяет анализировать происхождение данных, выявлять проблемы в графах зависимостей и генерировать визуализации для отладки.

**Функциональность:**

**Загрузка графов:**
- Загрузка из файлов JSON или evidence bundles
- Разрешение provenance_ref через CAS систему
- Поддержка различных форматов хранения

**Верификация целостности:**
- Проверка на orphaned nodes (узлы без связей)
- Выявление dangling references (ссылки на несуществующие узлы)
- Детекция циклов в wasDerivedFrom отношениях
- Валидация всех обязательных полей

**Визуализация:**
- Экспорт в Graphviz DOT формат для визуализации
- Цветовое кодирование по типам узлов (entities, activities, agents)
- Стилизация отношений (derived, generated, used, attributed, associated)
- Генерация PNG/SVG через Graphviz

**Экспорт:**
- JSON дамп графов с форматированием
- DOT файлы для Graphviz визуализации
- Поддержка stdout и файлового вывода

```bash
# Генерация DOT файла из evidence bundle
python tools/visualize_provenance.py evidence.json --format dot > graph.dot
dot -Tpng graph.dot -o graph.png

# Верификация графа с CAS разрешением
python tools/visualize_provenance.py provenance.json --cas-root .polisyos --verify

# Экспорт в JSON формат
python tools/visualize_provenance.py graph.json --format json --output graph_pretty.json
```

**Типы отношений в provenance:**
- `wasDerivedFrom` - трансформация данных (синие сплошные линии)
- `wasGeneratedBy` - генерация данных активностью (зеленые пунктирные)
- `used` - использование данных активностью (оранжевые точечные)
- `wasAttributedTo` - атрибуция агенту (фиолетовые сплошные)
- `wasAssociatedWith` - ассоциация агента с активностью (фиолетовые пунктирные)

**Интеграция с модулями:**
- `polisyos.core.artifacts.ids.ArtifactID` - идентификаторы артефактов
- `polisyos.core.artifacts.store.FileSystemCAS` - Content Addressable Storage
- JSON Schema валидация provenance структур

**Примеры вывода верификации:**
```
VERIFICATION FAILED:
  - ORPHANED: Node 'data_entity_123' not connected to any edge
  - DANGLING: Edge source 'activity_456' not found in nodes
  - CYCLE: Circular dependency detected in wasDerivedFrom edges
```

## Архитектурная интеграция

Инструменты `tools/` обеспечивают качество и надежность всей системы Policy Engine, интегрируясь со всеми основными модулями:

### Связи с модулями проекта

| Инструмент | Зависимости от модулей | Проверяет/Тестирует | Архитектурный закон |
|------------|----------------------|---------------------|---------------------|
| `lint_imports.py` | `core.*` | Закон A (направленный граф зависимостей) | A (направленные зависимости) |
| `lint_foundry.py` | `foundry.*` (только структура) | Закон B (чистота математического ядра) | B (компиляторная архитектура) |
| `lint_connectors.py` | `fabric.connectors.*` | Законы A, E (изоляция коннекторов и provenance) | A, E |
| `gen_schema.py` | `ir.contract` | Закон C (контракты как источник истины) | C (контракты) |
| `migrate_ir.py` | `ir.migrations`, `common.migrations` | Закон C (детерминированные миграции) | C (контракты) |
| `migrate.py` | `common.migrations` | Закон C (миграции артефактов) | C (контракты) |
| `migrate_to_trinity.py` | `ir.trinity`, `ir.migrations.trinity_migration` | Закон C (Trinity формат миграции) | C (контракты) |
| `check_setup.py` | `common.config`, все модули | Системная интеграция и готовность | - |
| `check_udf_perf.py` | `fabric.*`, `ir.data_views` | Производительность Unified Data Fabric | - |
| `check_perf_regression.py` | - | Закон D (регрессионное тестирование производительности) | D (воспроизводимость) |
| `diagnostics/check_perf_regression.py` | - | Закон D (расширенная проверка регрессий) | D (воспроизводимость) |
| `generate_ir_schema.py` | `ir.*` (все Pydantic модели) | Валидность IR структур данных | C (контракты) |
| `bench_domain.py` | `foundry.domain.*`, `common.logger` | Масштабируемость JAX доменной модели | - |
| `bench_simulation.py` | `foundry.*` | Полный симуляционный пайплайн | - |
| `run_ingest_demo.py` | `fabric.*`, `ir.*` | Unified Data Fabric ingestion | - |
| `run_udf_*_demo.py` | `fabric.udf.*`, `ir.data_views` | Гибридные SQL + Python запросы | - |
| `run_optimizer_demo.py` | `scientist.*` | Многокритериальная оптимизация | - |
| `run_export_demo.py` | `core.*`, `fabric.*` | Экспорт симуляционных данных | - |
| `run_laffer_demo.py` | `foundry.*` | Экономическая теория (кривая Лаффера) | - |
| `run_mechanism_design.py` | `foundry.*`, `core.artifacts` | Дифференцируемый механизм дизайна | B (компиляторная архитектура) |
| `scan_fabric.py` | `fabric.catalog.*`, `ir.contracts` | Bootstrap data contracts для Unified Data Fabric | E (evidence и provenance) |
| `visualize_provenance.py` | `core.artifacts.*` | Визуализация provenance графов | E (evidence и provenance) |
| `capture_env.py` | `core.artifacts.environment` | Закон D (воспроизводимость окружения) | D (воспроизводимость) |

### Детальные архитектурные связи

**Модули проекта и их роли:**

- **`core`**: Фундаментальные утилиты (артефакты, контракты, registry, trace, environment manifests)
- **`ir`**: Intermediate Representation (контракты, data views, калибровка, типы, Trinity формат)
- **`fabric`**: Unified Data Fabric (ingestion, DB, graph store, UDF engine)
- **`foundry`**: Математическое ядро (JAX симуляции, доменная модель, engine, merge engine)
- **`scientist`**: AI/ML оркестрация (оптимизация, DOE, governance, агенты: critic, drafter, formalizer, pi)
- **`runtime`**: Исполнение (API, manifests)
- **`common`**: Общие утилиты (config, logger, migrations)

### Архитектурные гарантии

**Закон A (Направленный граф зависимостей только внутрь):**
- `lint_imports.py` анализирует все Python файлы в `src/polisyos/`
- Строит граф импортов между модулями и выявляет нарушения
- Обеспечивает, что зависимости идут только в одном направлении
- Предотвращает циклические импорты и обратные зависимости

**Разрешенные зависимости (согласно архитектуре):**
```
scientist → ir, fabric, foundry  (orchestration использует все)
fabric → ir                      (data fabric зависит от типов/контрактов)
foundry → ir                     (математическое ядро использует только типы)
ir → core                        (IR зависит от базовых утилит)
runtime → ir, core               (runtime использует контракты)
core → (никого)                  (фундаментальные утилиты)
```

**Закон B (Компиляторная архитектура - "Ты строишь компилятор"):**
- `lint_foundry.py` обеспечивает чистоту математического ядра
- Foundry должно быть функциональным ядром без side effects
- Запрещены: базы данных, IO операции, сеть, недетерминированность
- Разрешены: JAX, Equinox, typing, собственные модули (только типы)

**Запрещенные импорты в foundry:**
- Базы данных: `duckdb`, `kuzu`, `pandas`, `sqlite3`, `sqlalchemy`
- IO операции: `os`, `pathlib`, `shutil`, `glob`, `tempfile`, `open`
- Сеть: `requests`, `httpx`, `urllib`
- Недетерминированность: `random`, `time` (кроме профилирования)

**Закон C (Контракты как источник истины):**
- `gen_schema.py` генерирует JSON Schema из Pydantic моделей
- `migrate_ir.py` и `migrate.py` обеспечивают детерминированные миграции
- Все артефакты имеют `schema_version` для версионирования
- Контракты эволюционируют безопасно между версиями

**Закон D (Воспроизводимость и аудит):**
- Все инструменты поддерживают `--seed`, `--run-id` для воспроизводимости
- Полная трассировка артефактов через `polisyos.core.trace`
- Manifest файлы для reproducible runs
- Аудит через `polisyos.core.artifacts`

## Использование в CI/CD

Рекомендуемый pipeline качества для Policy Engine с учетом архитектурных законов:

```yaml
# .github/workflows/ci.yml
jobs:
  quality-gate:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -e .[dev,test]

    - name: System readiness check
      run: |
        python tools/diagnostics/check_setup.py

    - name: Architecture compliance (Законы A, B, C)
      run: |
        # Закон A: направленный граф зависимостей
        python tools/lint_imports.py --fail-on-cycles --verbose

        # Закон B: чистота математического ядра
        python tools/lint_foundry.py --verbose

        # Закон C: контракты как источник истины
        python tools/gen_schema.py --check --output policy_ir_schema.json

    - name: Schema validation
      run: |
        python tools/diagnostics/generate_ir_schema.py
        python tools/migrate.py policy_ir tests/data/policy_v1.json /tmp/migrated.json --to v2.0.0

    - name: Performance regression gate
      run: |
        python tools/benchmarks/bench_domain.py --n-agents 10000
        python tools/benchmarks/bench_simulation.py --n-steps 50 --n-agents 1000
        python tools/diagnostics/check_udf_perf.py
        python tools/check_perf_regression.py benchmark_results.json --threshold 0.05

    - name: Integration smoke tests
      run: |
        python tools/demos/run_ingest_demo.py
        python tools/demos/run_udf_query_demo.py
        python tools/scan_fabric.py data/demo_udf.duckdb --output /tmp/test_contracts.json
        python tools/visualize_provenance.py /tmp/test_provenance.json --verify || echo "No provenance file for testing"
        python tools/demos/run_optimizer_demo.py --quick
        python tools/migrate_to_trinity.py /tmp/test_policy.yaml --dry-run || echo "Trinity migration test skipped"

  nightly-benchmarks:
    runs-on: ubuntu-latest
    schedule:
      - cron: '0 2 * * *'  # Каждый день в 2:00 UTC
    steps:
    - uses: actions/checkout@v4

    - name: Full performance benchmark
      run: |
        python tools/benchmarks/bench_domain.py --n-agents 1000000
        python tools/benchmarks/bench_simulation.py --n-steps 1000 --n-agents 10000

    - name: Upload benchmark results
      uses: actions/upload-artifact@v4
      with:
        name: benchmark-results
        path: benchmark_*.json
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

### scan_fabric.py не находит DuckDB файлы
```bash
# Проверь наличие файлов
ls -la data/curated/*.duckdb

# Используй кастомный glob паттерн
python tools/scan_fabric.py data/ -glob "**/*.duckdb"

# Проверь права доступа
python -c "import duckdb; print('DuckDB OK')"
```

### Некорректное определение типов/единиц
```bash
# Просмотри сгенерированные контракты
python tools/scan_fabric.py data/curated/ -v

# Ручная аннотация после генерации
# Отредактируй draft_contracts.json вручную
# Проверь units и pii_tiers
```

### visualize_provenance.py не может загрузить граф
```bash
# Проверь существование файла
ls -la evidence.json

# Для CAS артефактов проверь путь к .polisyos
ls -la .polisyos/

# Попробуй с verbose выводом
python tools/visualize_provenance.py evidence.json --cas-root .polisyos --verify -v

# Проверь JSON структуру
python -c "import json; print(json.load(open('evidence.json'))['provenance_ref'])" 2>/dev/null || echo "No provenance_ref"
```

### DOT визуализация не работает
```bash
# Установи Graphviz
# macOS: brew install graphviz
# Ubuntu: apt-get install graphviz

# Проверь установку
dot -V

# Сгенерируй и визуализируй
python tools/visualize_provenance.py evidence.json --format dot | dot -Tpng -o graph.png
```

### check_perf_regression.py не может загрузить benchmark JSON
```bash
# Проверь существование файла
ls -la benchmark_results.json

# Проверь JSON структуру
python -c "import json; data=json.load(open('benchmark_results.json')); print('benchmarks' in data)"

# Для pytest-benchmark файлов проверь формат
python -c "import json; data=json.load(open('benchmark_results.json')); print(data.keys())"
```

### Нет baseline файла для сравнения
```bash
# Создай baseline вручную
cp benchmark_results.json .benchmarks/baseline.json

# Или укажи явный путь
python tools/check_perf_regression.py current.json --baseline path/to/baseline.json

# Автоматический поиск baseline в стандартных директориях:
# - .benchmarks/*.json (отсортировано по времени модификации)
# - benchmarks/*.json
```

### Ложные регрессии из-за шума
```bash
# Увеличь threshold для нестабильных тестов
python tools/check_perf_regression.py results.json --threshold 0.15  # 15% вместо 5%

# Проверь статистику в benchmark JSON
python -c "import json; data=json.load(open('results.json')); print(data['benchmarks'][0]['stats'])"
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

### Системные требования

- **Python:** 3.11+ (рекомендуется 3.11 или 3.12)
- **JAX:** 0.4.x+ с соответствующими JAXlib
- **Pydantic:** v2 only (критические изменения в v1→v2)
- **Операционные системы:** Linux, macOS (Intel/Apple Silicon), Windows (WSL2)

### Зависимости

| Компонент | Версия | Примечание |
|------------|--------|------------|
| `jax` | 0.4.x+ | С JAXlib для целевой платформы |
| `jaxlib` | Совместимая с JAX | CPU или GPU версия |
| `equinox` | 0.11.x+ | Функциональное программирование |
| `pydantic` | 2.x | Только v2, v1 не поддерживается |
| `duckdb` | 0.9.x+ | Аналитическое хранилище |
| `kuzu` | 0.0.x+ | Графовая база данных |
| `pymoo` | 0.6.x+ | Многокритериальная оптимизация |

### Известные ограничения и решения

#### JAX и Apple Silicon (macOS)
```bash
# Принудительное использование CPU (рекомендуется для стабильности)
export POLICY_ENGINE_ALLOW_JAX_METAL=0
python tools/diagnostics/check_setup.py
```

#### PyYAML для YAML поддержки
```bash
# Опционально для миграций YAML файлов
pip install PyYAML
```

#### Kuzu установка
```bash
# Требует C++ компилятора
# На macOS: xcode-select --install
# На Ubuntu: apt-get install build-essential
pip install kuzu
```

#### Windows поддержка
- Полная поддержка через WSL2
- Native Windows: экспериментальная, возможны проблемы с JAX GPU

### Тестирование совместимости

```bash
# Полная проверка системной совместимости
python tools/diagnostics/check_setup.py

# Проверка с детальным логированием
POLICY_ENGINE_LOG_LEVEL=DEBUG python tools/diagnostics/check_setup.py
```

### Версионирование

Инструменты следуют семантическому версионированию основного проекта. Критические изменения в API инструментов помечаются в changelog.

---

## Архитектурная актуальность

Данная документация отражает текущее состояние Policy Engine на **2026-01-30** и соответствует принципам, описанным в `architecture.md`.

### Ключевые архитектурные достижения

- **Закон A**: Гарантированная направленность зависимостей через автоматизированное тестирование
- **Закон B**: Чистота математического ядра foundry с запретом IO операций
- **Закон C**: Контракты как источник истины с детерминированными миграциями
- **Закон D**: Полная воспроизводимость через manifests и trace систему
- **Закон E**: Evidence и provenance обязательны для всех данных (новая система data contracts)

### Интеграция с модулями

Инструменты `tools/` обеспечивают качество всей экосистемы Policy Engine:

- **Диагностика**: `diagnostics/` - проверка готовности системы
- **Качество**: `lint_*.py` - соблюдение архитектурных законов
- **Эволюция**: `migrate_*.py`, `gen_schema.py` - безопасные изменения
- **Производительность**: `benchmarks/` - регрессионное тестирование
- **Демонстрация**: `demos/` - валидация функциональности
- **Bootstrap**: `scan_fabric.py` - быстрая генерация data contracts из существующих данных

### Новые возможности (2026-02-01)

- **Data Catalog System**: Новая подсистема data contracts в `fabric.catalog/`
- **scan_fabric.py**: Bootstrap утилита для автоматической генерации data contracts
- **Enhanced Evidence Tracking**: Улучшенная система provenance и evidence bundles
- **Trinity Migration**: Поддержка миграции в новый Trinity формат (ProblemFrame, PolicySpec, ModelSpec)
- **migrate_to_trinity.py**: Специализированный инструмент для batch миграции политик в Trinity формат
- **visualize_provenance.py**: Инструмент для визуализации и верификации provenance графов
- **check_perf_regression.py**: Автоматическая проверка регрессий производительности на основе pytest-benchmark результатов
- **capture_env.py**: CLI инструмент для захвата и сравнения Environment Manifest
- **run_mechanism_design.py**: End-to-end демонстрация дифференцируемого механизма дизайна
- **diagnostics/check_perf_regression.py**: Расширенная версия проверки регрессий в diagnostics
- **lint_connectors.py**: Архитектурный линтер для коннекторов данных с проверкой Законов A и E
- **connectors/scaffold.py**: Генератор скелетов коннекторов с автоматической поддержкой REST, CSV, SQL, SDMX типов

---

*Инструменты протестированы на Python 3.11+ с JAX 0.4.x, DuckDB, Kuzu и полным технологическим стеком Policy Engine. Документация обновлена для отражения актуального состояния на 2026-02-01.*
