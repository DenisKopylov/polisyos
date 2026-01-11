# Policy Engine

**AI-driven Policy Simulation System** - система симуляции экономической политики с использованием дифференцируемых вычислений и унифицированного хранилища данных.

## Архитектурный обзор

Policy Engine представляет собой полнофункциональную систему для проектирования, валидации и оптимизации экономических политик через комбинацию ИИ, симуляций и детерминированных вычислений.

### Компиляторная архитектура

Система построена по принципам компилятора с четким разделением ответственности:

```
NL → LLM → IR (AST) → Compilation → Runtime (UDF + Foundry) → Artifacts
```

**Архитектурные законы:**
- **Закон A**: Граф зависимостей направлен только внутрь (scientist → ir/fabric/foundry → core)
- **Закон B**: Foundry остается чистым математическим ядром (без IO/сетевых операций)
- **Закон C**: Контракты (IR) - единственный источник истины для всех компонентов
- **Закон D**: Любой прогон воспроизводим и аудируем (run_id, seed, детерминированные артефакты)

### Основные компоненты

- **Scientist**: AI-агент для проектирования политик (LLM + оптимизация)
- **IR**: Промежуточное представление (контракты, типы, валидация)
- **Fabric**: Unified Data Fabric (ingestion, storage, UDF запросы)
- **Foundry**: JAX симуляционное ядро (механизмы, patch execution, оптимизация)
- **Runtime**: Управление жизненным циклом прогонов (артефакты, аудит, бюджеты)
- **Core**: Фундаментальные утилиты (конфигурация, логирование, миграции)

## Технологический стек (текущий)

### Язык и вычисления
- **Python 3.11+**: базовый рантайм проекта
- **JAX/JAXlib**: численные вычисления, JIT и autodiff
- **JAX Metal**: опциональный backend для macOS (через `jax-metal`)
- **Equinox**: модульная структура JAX-моделей
- **Optax**: оптимизаторы и градиентная оптимизация политик
- **Jaxtyping + Chex**: типы и проверки форм массивов

### Data Layer (Unified Data Fabric)
- **DuckDB**: аналитическое хранилище временных рядов и срезов
- **Kùzu**: графовая БД для взаимодействий агентов
- **pandas + PyArrow/Parquet**: ETL и columnar storage
- **Pydantic v2**: схемы данных и валидация

### IR & Contracts (Промежуточное представление)
- **Pydantic v2**: строгие контракты и валидация
- **JSON Schema**: экспорт схем для внешних интеграций
- **difflib**: генерация отчетов об изменениях

### Scientist & AI (Интеллектуальное ядро)
- **LangGraph**: state-machine workflow для пайплайна эксперимента
- **MockLLM**: локальный LLM-адаптер для тестов
- **LangChain**: интеграция реальных LLM провайдеров (OpenAI/Anthropic)
- **PyMOO**: многокритериальная оптимизация (NSGA-II)

### Runtime & Infrastructure
- **Loguru**: структурированное логирование
- **python-dotenv**: загрузка `.env` и конфигурации окружения
- **FileSystemCAS**: content-addressable storage для артефактов
- **hashlib**: контроль целостности данных

### Quality & Development Tools
- **Ruff**: быстрый линтер и форматер (замена Black + Flake8 + Isort)
- **MyPy**: строгая статическая типизация
- **Pytest**: unit/integration/contract тесты
- **Pre-commit**: git hooks (dev зависимости)
- **JupyterLab + Matplotlib + Seaborn**: ноутбуки и исследовательская визуализация

### Новые компоненты (после крупных изменений)
- **Fact Log System**: immutable факты с provenance tracking
- **Evidence Bundles**: криптографически verifiable доказательства
- **UDF Compilation Pipeline**: безопасная компиляция SQL/Cypher запросов
- **Patch-based Execution**: декларативные изменения состояния
- **Treasury System**: детерминированное управление RNG
- **Materializer**: восстановление реляционных представлений из фактов

### Подготовлено, но сейчас не задействовано в коде
- **Diffrax**: ODE/SDE solver (для дифференциальных моделей)
- **pydantic-settings**: типизированная конфигурация окружения

## Установка

### Вариант A: Рекомендуемый (uv - быстрый менеджер пакетов)

```bash
# Установка uv (если не установлен)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Синхронизация зависимостей (создает виртуальное окружение автоматически)
uv sync --extra dev

# Активация виртуального окружения
source .venv/bin/activate  # Linux/Mac
# или .venv\Scripts\activate на Windows
```

### Вариант B: Стандартный pip (если uv недоступен)

```bash
# Создаем виртуальное окружение
python3.11 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или .venv\Scripts\activate на Windows

# Устанавливаем зависимости
pip install -e .[dev]
```

### 2. Специфика JAX

**Mac M1/M2/M3:**
```bash
pip install jax-metal
# или uv add jax-metal
```

По умолчанию на macOS проект форсирует `cpu` (через `jax_bootstrap.py`, импортируй его до `jax`), потому что
`METAL` в некоторых версиях JAX падает даже на `jnp.zeros(...)` с ошибкой
`UNIMPLEMENTED: default_memory_space is not supported.`
Если хочешь попробовать Metal, задай перед запуском:
```bash
POLICY_ENGINE_ALLOW_JAX_METAL=1
JAX_PLATFORMS=metal   # или JAX_PLATFORM_NAME=metal
```

**Linux с NVIDIA:**
```bash
pip install -U "jax[cuda12_pip]" -f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html
# или uv add "jax[cuda12_pip]" --extra-index-url https://storage.googleapis.com/jax-releases/jax_cuda_releases.html
```

### 3. Решение проблем с установкой

**Если возникают ошибки permissions на macOS:**
```bash
# Для pip - используйте флаг user
pip install --user -e .[dev]

# Или настройте pip для игнорирования external management
pip config set global.break-system-packages true
```

**Если Python 3.11 недоступен:**
```bash
# Используйте python3 (работает с 3.11+)
python3 -m venv .venv
```

### 3. Настройка окружения

Скопируйте пример файла окружения и настройте API ключи:

```bash
cp env_example.txt .env
# Отредактируйте .env файл с вашими ключами
```

### 4. Автоматическая установка

Для удобства создан скрипт автоматической установки:

```bash
# Сделать исполняемым и запустить
chmod +x install.sh
./install.sh
```

## Структура проекта

```
policy-engine/
├── .env                      # API ключи и конфигурация (не в Git!)
├── .gitignore               # Стандартный gitignore
├── pyproject.toml           # Единый конфиг зависимостей, линтера, тестов
├── policy_ir_schema.json    # JSON Schema для IR контрактов
├── README.md
├── data/                    # Локальное хранилище данных
│   ├── raw/                 # Сырые CSV файлы
│   ├── staging/             # Обработанные данные (Parquet)
│   ├── curated/             # Готовые датасеты (DuckDB, Kuzu)
│   └── facts/               # Fact Log сегменты (immutable факты)
├── runs/                    # Результаты прогонов (создается автоматически)
│   └── <run_id>/            # Структурированные артефакты прогона
│       ├── manifest.json    # RunManifest (паспорт прогона)
│       ├── artifacts/       # Скомпилированные результаты
│       ├── audit.jsonl      # Аудит-лог всех операций
│       └── decision_packet.json # Финальное решение (опционально)
├── src/polisyos/           # Основной исходный код
│   ├── core/               # Фундаментальные компоненты
│   │   ├── artifacts/      # FileSystemCAS, content-addressable storage
│   │   ├── compiler/       # Компиляция политик в исполняемые графы
│   │   ├── contracts/      # Foundry-specific контракты (PatchOp, ProgramGraph)
│   │   ├── registry/       # Управление реестрами компонентов
│   │   └── run/            # Контекст выполнения и метаданные
│   ├── ir/                 # Intermediate Representation (контракты)
│   │   ├── contract.py     # Унаследованные модели (v1.0)
│   │   ├── surface.py      # PolicySurfaceIR (текущая версия v2.0)
│   │   ├── kernel/         # Базовые реестры (механизмы, слоты, единицы)
│   │   ├── data_views.py   # Запросы к данным (PANEL, SNAPSHOT, NETWORK)
│   │   ├── linker.py       # Валидация и линковка политик
│   │   ├── fact_log.py     # Контракты для Fact Log системы
│   │   └── migrations/     # Детерминированные миграции схем
│   ├── fabric/             # Unified Data Fabric
│   │   ├── ingestion.py    # ETL пайплайн с Fact Log
│   │   ├── schema.py       # Pydantic схемы данных
│   │   ├── io/             # Адаптеры хранилищ (DuckDB, Kuzu)
│   │   ├── udf/            # Unified Data Fabric запросы
│   │   │   ├── engine.py   # UDF движок
│   │   │   ├── compiler.py # Безопасная компиляция SQL/Cypher
│   │   │   └── passes/     # Компиляционный пайплайн
│   │   ├── fact_writer.py  # Запись фактов в каноническом формате
│   │   ├── materializer.py # Материализация из Fact Log
│   │   └── evidence.py     # Система доказательств (evidence bundles)
│   ├── foundry/            # JAX симуляционное ядро
│   │   ├── base.py         # Абстрактный класс Mechanism
│   │   ├── compiler.py     # Компиляция политик в ProgramGraph
│   │   ├── runtime.py      # Исполнение ProgramGraph с patch system
│   │   ├── domain/         # Экономическая модель (GlobalState, AgentState)
│   │   ├── fiscal.py       # Налоговые механизмы (IncomeTax, TaxSubsidy)
│   │   ├── queue.py        # Механизмы очередей с multi-fidelity
│   │   ├── treasury.py     # Детерминированное управление RNG
│   │   ├── types.py        # FidelityLevel enum
│   │   ├── specs.py        # Спецификации механизмов
│   │   ├── registry.py     # Регистрация и фабрика механизмов
│   │   └── engine/         # Legacy симуляционный движок
│   ├── scientist/          # AI Policy Scientist
│   │   ├── agent/          # Агенты и генерация (drafter, prompt engineering)
│   │   ├── orchestrator/   # Основная оркестрация (workflow, state, audit)
│   │   ├── compute/        # Спецификации вычислительных задач
│   │   ├── doe/            # Design of Experiments
│   │   ├── governance/     # Управление качеством и безопасностью
│   │   ├── kernel/         # Ядро управления (FSM, budgets, guards)
│   │   └── publisher.py    # Публикация решений
│   ├── runtime/            # Управление жизненным циклом прогонов
│   │   ├── api.py          # Основные функции управления (start_run, log_artifact)
│   │   ├── manifest.py     # RunManifest и ArtifactRef модели
│   │   └── README.md       # Детальная документация runtime
│   └── common/             # Фундаментальные утилиты
│       ├── config.py       # Конфигурация JAX и системных лимитов
│       ├── logger.py       # Структурированное логирование
│       ├── jax_env.py      # JAX backend selection для macOS
│       └── migrations/     # Система миграций артефактов
├── examples/               # Примеры и демо-скрипты
├── tests/                  # Комплексная тестовая инфраструктура
│   ├── conftest.py         # Конфигурация pytest и JAX setup
│   ├── contract/           # Тесты контрактов IR и схем
│   ├── core_phase0/        # Тесты фундаментальных компонентов
│   ├── foundry/            # Тесты JAX симуляций
│   ├── integration/        # End-to-end тесты workflow
│   └── scientist/          # Тесты AI компонентов
└── tools/                  # Инструменты разработчика
    ├── benchmarks/         # Бенчмарки производительности
    ├── demos/              # Демонстрации возможностей
    ├── diagnostics/        # Диагностика и анализ
    ├── lint_foundry.py     # Архитектурный линтер foundry
    ├── lint_imports.py     # Линтер межмодульных зависимостей
    └── gen_schema.py       # Генератор JSON Schema
```

## Архитектурные принципы

Policy Engine построен на четырех фундаментальных архитектурных законах, которые обеспечивают надежность, поддерживаемость и предсказуемость системы:

### Закон A: Направленный граф зависимостей
```
scientist → ir/fabric/foundry → core
```
**Граф зависимостей направлен только внутрь.** Высокоуровневые модули (scientist) могут зависеть от низкоуровневых (ir, fabric, foundry), но не наоборот. Это предотвращает циклические зависимости и обеспечивает четкое разделение ответственности.

**Инструменты проверки:** `tools/lint_imports.py` автоматически обнаруживает нарушения закона A.

### Закон B: Ты строишь компилятор
```
NL → LLM → IR (AST) → Compilation → Runtime → Artifacts
```
**Foundry остается чистым математическим ядром без side effects.** Модуль не знает про файлы, сеть, БД или LLM - только про JAX вычисления и экономические модели. Это обеспечивает предсказуемость и тестируемость симуляций.

**Инструменты проверки:** `tools/lint_foundry.py` запрещает импорты файловой системы, сетевых библиотек и БД в foundry модуле.

### Закон C: Контракты - единственный источник истины
```
IR schemas → JSON Schema export → All components validation
```
**Все структурные определения живут в IR модуле.** Любые изменения в контрактах отражаются в JSON Schema экспорте и автоматически валидируются всеми компонентами системы.

**Инструменты проверки:** `tools/gen_schema.py` генерирует JSON Schema из Pydantic моделей для валидации.

### Закон D: Любой прогон воспроизводим и аудируем
```
RunManifest + seed + artifacts → Full reproducibility
```
**Каждый эксперимент имеет уникальный run_id, детерминированные seed'ы и полную трассировку.** Runtime модуль обеспечивает аудит всех операций через JSON Lines логи.

**Инструменты поддержки:** Runtime API (`start_run`, `log_artifact`, `append_audit`) обеспечивает соблюдение закона D.

## Модули системы

### Core Layer (Фундамент)
**Обеспечивает базовую инфраструктуру для всех компонентов:**

- **`core/artifacts/`**: FileSystemCAS - content-addressable storage для immutable артефактов
- **`core/compiler/`**: Компиляция политик IR в исполняемые ProgramGraph структуры
- **`core/contracts/`**: Foundry-specific контракты (PatchOp, ProgramGraph, ExecutionPlan)
- **`core/registry/`**: Управление реестрами компонентов и их версиями
- **`core/run/`**: Контекст выполнения, метаданные producer'а и артефакты

### IR Layer (Intermediate Representation)
**Канонические контракты и типы для всей системы:**

- **`ir/surface.py`**: PolicySurfaceIR v2.0 - основной контракт системы с semantic/advisory разделением
- **`ir/kernel/`**: Базовые реестры (механизмы, слоты, единицы измерения, merge rules)
- **`ir/data_views.py`**: Унифицированные запросы к данным (PANEL/SNAPSHOT/NETWORK)
- **`ir/linker.py`**: Валидация и линковка политик с реестрами компонентов
- **`ir/fact_log.py`**: Контракты для Fact Log системы (immutable факты с provenance)
- **`ir/migrations/`**: Детерминированные миграции между версиями схем

### Fabric Layer (Unified Data Fabric)
**Полный жизненный цикл данных от сырых CSV до аналитических запросов:**

- **`fabric/ingestion.py`**: ETL пайплайн с entity resolution, reconciliation и Fact Log
- **`fabric/io/`**: Адаптеры хранилищ (DuckDB для аналитики, Kuzu для графов)
- **`fabric/udf/`**: Unified Data Fabric с безопасной компиляцией SQL/Cypher запросов
- **`fabric/fact_writer.py`**: Запись immutable фактов в каноническом формате
- **`fabric/materializer.py`**: Восстановление реляционных представлений из Fact Log
- **`fabric/evidence.py`**: Система доказательств (evidence bundles) для верификации данных

### Foundry Layer (JAX Simulation Core)
**Высокопроизводительное симуляционное ядро с patch-based execution:**

- **`foundry/compiler.py`**: Компиляция политик в ProgramGraph с топологической сортировкой
- **`foundry/runtime.py`**: Исполнение программ с patch system и merge rules
- **`foundry/domain/`**: Экономическая модель (GlobalState, AgentState, FirmState, MarketState)
- **`foundry/fiscal.py`**: Налоговые механизмы (IncomeTax, TaxSubsidy) с multi-fidelity
- **`foundry/treasury.py`**: Детерминированное управление RNG для воспроизводимости
- **`foundry/base.py`**: Абстрактный класс Mechanism с emit_patches() методом

### Scientist Layer (AI Policy Scientist)
**Интеллектуальная оркестрация экспериментов с LLM и оптимизацией:**

- **`scientist/orchestrator/`**: LangGraph workflow с 9 узлами (draft_ir → analyze → governor)
- **`scientist/agent/`**: LLM интеграция (drafter, prompt engineering, MockLLM для тестов)
- **`scientist/kernel/`**: Управление состоянием (FSM, budgets, guards, human gates)
- **`scientist/compute/`**: Спецификации вычислительных задач (JobSpec, JobKey, JobResult)
- **`scientist/doe/`**: Design of Experiments (ScenarioSweep, AblationPlan, SensitivityPlan)
- **`scientist/governance/`**: Preflight/postflight проверки и бюджетный контроль

### Runtime Layer (Experiment Lifecycle)
**Управление жизненным циклом прогонов с аудитом и артефактами:**

- **`runtime/api.py`**: Основные функции (start_run, log_artifact, append_audit, finalize_run)
- **`runtime/manifest.py`**: RunManifest (паспорт прогона) и ArtifactRef модели
- **Структура runs/**: Стандартизированное хранение результатов (`manifest.json`, `artifacts/`, `audit.jsonl`)

### Common Layer (Shared Infrastructure)
**Фундаментальные утилиты без зависимостей:**

- **`common/config.py`**: Конфигурация JAX, системных лимитов и логирования
- **`common/logger.py`**: Структурированное логирование с контекстом модуля
- **`common/jax_env.py`**: JAX backend selection для macOS (предотвращение Metal падений)
- **`common/migrations/`**: Детерминированные миграции артефактов между версиями

## Рабочая директория и артефакты

- **CAS (Content-Addressable Storage)**: Артефакты хранятся в `runs/<run_id>/` директории с SHA256-based addressing
- **Рабочая директория**: Все инструменты предполагают запуск из корня `policy-engine/`
- **Runtime артефакты**: Каждый прогон создает структурированную директорию с `manifest.json`, `artifacts/` и `audit.jsonl`
- **Fact Log**: Immutable факты хранятся в `data/facts/` с сегментацией для эффективного хранения

## Быстрый старт

### 1. Установка и проверка

```bash
# Установка зависимостей
uv sync --extra dev

# Проверка установки всех компонентов
python tools/diagnostics/check_setup.py
```

### 2. Первый эксперимент

```bash
# Полный ingestion пайплайн (CSV → DuckDB + Kuzu)
python tools/demos/run_ingest_demo.py

# UDF запросы к данным
python tools/demos/run_udf_query_demo.py

# Оптимизация политики через LLM + JAX
python tools/demos/run_optimizer_demo.py
```

### 3. Разработка и тестирование

```bash
# Архитектурные проверки
python tools/lint_imports.py    # Закон A (направленные зависимости)
python tools/lint_foundry.py    # Закон B (чистота математического ядра)

# Качество кода
ruff check . && ruff format .
mypy src/

# Полный тест-свит
pytest tests/ -x --tb=short
```

## Новые возможности (после крупных изменений)

### 🏗️ Архитектурная эволюция

- **Runtime модуль**: Полное управление жизненным циклом прогонов с аудитом и артефактами
- **Fact Log система**: Immutable факты с provenance tracking и evidence bundles
- **UDF Compilation Pipeline**: Безопасная компиляция SQL/Cypher запросов с whitelist
- **Patch-based Execution**: Декларативные изменения состояния вместо прямых модификаций
- **Treasury System**: Детерминированное управление RNG для воспроизводимости

### 📊 Расширенная система данных

- **Materializer**: Восстановление реляционных представлений из Fact Log
- **Evidence Bundles**: Криптографически verifiable доказательства происхождения данных
- **Multi-tier Access Control**: PII classification (public/internal/sensitive)
- **Entity Resolution**: Нормализация идентификаторов агентов с confidence scoring
- **Financial Reconciliation**: Балансовая проверка транзакций с tolerance

### 🤖 Улучшенный AI Scientist

- **FSM-based Orchestration**: Конечный автомат состояний для надежного workflow
- **Budget Controls**: Многоуровневые бюджеты (compute, evidence, legitimacy, complexity)
- **Human Gates**: Система GateRequest/GateDecision для человеческого одобрения
- **Design of Experiments**: ScenarioSweep, AblationPlan, SensitivityPlan
- **Self-healing Policies**: Автоматическое исправление ошибок валидации через LLM

### 🔬 Продвинутое симуляционное ядро

- **Program Graph Compilation**: Топологическая сортировка и execution plans
- **Multi-fidelity Mechanisms**: Fluid/relaxed/hard уровни точности симуляции
- **Merge Rules**: Стратегии разрешения конфликтов патчей (SUM/OVERRIDE/PRIORITY/ERROR)
- **Registry-driven Compilation**: Динамическая линковка механизмов из реестров
- **State Snapshots**: Детерминированные срезы состояния для отладки

### 🛡️ Governance & Compliance

- **Preflight/Postflight Checks**: Автоматические проверки безопасности
- **Audit Trail**: Полная JSON Lines трассировка всех операций
- **Policy Safety**: Валидация запрещенных механизмов и селекторов
- **Version Control**: Миграции артефактов с backward compatibility
- **Run Manifest**: "Паспорт прогона" с полной метадатой для воспроизводимости

### 🧰 Инструменты разработчика

- **Architectural Linters**: `lint_imports.py` (Закон A), `lint_foundry.py` (Закон B)
- **Schema Generation**: `gen_schema.py` для JSON Schema экспорта из Pydantic
- **Migration Tools**: `migrate_ir.py`, `migrate.py` для версионирования артефактов
- **Performance Benchmarks**: `bench_domain.py`, `bench_simulation.py` для регрессии
- **Comprehensive Diagnostics**: `check_setup.py`, `check_udf_perf.py`

## Качество кода и архитектурные гарантии

Проект обеспечивает качество через многоуровневую систему проверок:

### Архитектурные линтеры (Законы A, B, C)

```bash
# Закон A: Направленный граф зависимостей
python tools/lint_imports.py --verbose

# Закон B: Чистота математического ядра (foundry)
python tools/lint_foundry.py

# Закон C: Контракты как источник истины
python tools/gen_schema.py --check --output policy_ir_schema.json
```

### Качество кода

```bash
# Линтинг и форматирование
ruff check . && ruff format .

# Статическая типизация
mypy src/

# Запрещены print statements в продакшн коде (src/)
# Используйте loguru через polisyos.common.logger
```

### Тестирование

```bash
# Полный тест-свит с категориями
pytest tests/ -x --tb=short

# Только быстрые unit тесты
pytest -m "not integration"

# Только интеграционные тесты
pytest -m integration

# Тесты контрактов (IR и схемы)
pytest tests/contract/

# Тесты симуляционного ядра
pytest tests/foundry/

# Производительность и регрессии
python tools/benchmarks/bench_domain.py
python tools/benchmarks/bench_simulation.py
```

### Диагностика системы

```bash
# Полная проверка компонентов
python tools/diagnostics/check_setup.py

# Профилирование UDF производительности
python tools/diagnostics/check_udf_perf.py

# Генерация схем для валидации
python tools/diagnostics/generate_ir_schema.py
```

## Документация модулей

Для детального понимания архитектуры и API каждого модуля обратитесь к специализированной документации:

### Core Infrastructure
- **[`src/polisyos/core/`](../core/README.md)**: Фундаментальные компоненты (CAS, compiler, registry, contracts)

### Intermediate Representation
- **[`src/polisyos/ir/README.md`](../ir/README.md)**: Контракты данных, PolicySurfaceIR, kernel реестры, линкер, миграции

### Unified Data Fabric
- **[`src/polisyos/fabric/README.md`](../fabric/README.md)**: Ingestion, storage, UDF запросы, Fact Log, evidence bundles

### JAX Simulation Core
- **[`src/polisyos/foundry/README.md`](../foundry/README.md)**: Компиляция, patch execution, механизмы, экономическая модель

### AI Policy Scientist
- **[`src/polisyos/scientist/README.md`](../scientist/README.md)**: LLM интеграция, workflow, governance, DOE

### Runtime & Lifecycle
- **[`src/polisyos/runtime/README.md`](../runtime/README.md)**: Управление прогонами, артефакты, аудит

### Common Utilities
- **[`src/polisyos/common/README.md`](../common/README.md)**: Конфигурация, логирование, JAX setup, миграции

### Testing Framework
- **[`tests/README.md`](../tests/README.md)**: Архитектура тестов, категории, CI/CD интеграция

### Developer Tools
- **[`tools/README.md`](../tools/README.md)**: Линтеры, диагностика, бенчмарки, демонстрации

## Архитектурные принципы проекта

- **[`architecture.md`](../architecture.md)**: Подробное описание архитектурных законов и принципов
- **Закон A**: Направленный граф зависимостей (только внутрь)
- **Закон B**: Компиляторная архитектура (чистота математического ядра)
- **Закон C**: Контракты - единственный источник истины
- **Закон D**: Воспроизводимость и аудит всех прогонов

## Контрибьютинг

При работе с проектом следуйте архитектурным принципам:

1. **Соблюдайте архитектурные законы** - используйте линтеры для проверки
2. **Обновляйте контракты в IR** - любые изменения структур данных
3. **Добавляйте тесты** - unit для новых функций, integration для workflow
4. **Обновляйте документацию** - README модулей при изменениях API
5. **Используйте runtime API** - для логирования артефактов и аудита

## Лицензия и поддержка

Проект находится в активной разработке. Для вопросов и предложений используйте issue tracker или связывайтесь с командой разработки.

---

*Policy Engine - AI-driven Policy Simulation System с гарантированной воспроизводимостью и аудитом.*
