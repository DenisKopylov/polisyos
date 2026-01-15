# Policy Engine (PolisyOS)

**Policy Engine** — AI‑driven система проектирования, валидации, калибровки и исполнения политик. Архитектурно это “компиляторная труба”: от запроса пользователя/LLM до формально типизированных контрактов (IR), далее — компиляция в исполняемые графы, выполнение в JAX‑ядре и фиксация результатов в воспроизводимых артефактах.

**Состояние документа (актуально на 2026‑01):** архитектура v2.1 (Fabric layer, Calibration MVP, Runtime API), присутствуют legacy‑фрагменты после крупных изменений (см. раздел “Legacy и переходные зоны”).

## Архитектурный обзор

### Компиляторная труба (сверху вниз)

```
NL/Request → Scientist (LLM + Workflow) → IR (contracts) → Compilation → Runtime (Fabric UDF + Foundry) → Artifacts
```

Грубо: `scientist` производит/чинит IR, `ir` задаёт контракты, `fabric` обеспечивает данные/доказательства, `foundry` компилирует и исполняет политику, `runtime` фиксирует прогон, `core` даёт инфраструктуру артефактов/контрактов/трассировки.

### Архитектурные законы (инварианты проекта)

Проект опирается на набор инвариантов, которые проверяются линтерами/тестами и позволяют держать систему “как компилятор”:

- **Закон A — направленный граф зависимостей**: верхние слои зависят от нижних; запрещены обратные импорты и циклы. Проверяется `tools/lint_imports.py`.
- **Закон B — Foundry как чистое математическое ядро**: без БД/FS/сети и прочих side‑effects; только JAX‑совместимая логика, контракты, работа с артефактами. Проверяется `tools/lint_foundry.py`.
- **Закон C — контракты как источник истины**: структура данных определена в `ir` (и в `core.contracts` для межслойного обмена), экспортируется в JSON Schema и валидируется на границах. Поддерживается `tools/gen_schema.py`.
- **Закон D — воспроизводимость и аудит**: любой прогон имеет `run_id`, детерминированные seed’ы, протокол артефактов и audit trail.
- **Закон E — evidence обязательны**: результаты data‑провода фиксируют provenance/evidence (важно для доверия к данным).
- **Закон F — fidelity control**: симуляции/калибровки поддерживают управление точностью (speed/accuracy trade‑off).
- **Закон G — uncertainty quantification**: калибровки предоставляют оценки неопределённости (на уровне отчётов/артефактов).

### Слои и зависимости (упрощённо)

Нормативная схема зависимостей (ориентир; фактическую проверяет `tools/lint_imports.py`):

```
core → (никого)
ir → core
fabric → ir (+ core.contracts/core.artifacts; + common.logger)
foundry → ir (+ core.contracts/core.artifacts)
runtime → ir + core
scientist → ir + fabric + foundry + runtime (+ core как инфраструктура)
common → (никого)   # “тонкая” инфраструктура (config/logger/migrations)
```

> Примечание: `polisyos.common` и `polisyos.core` — разные “фундаменты”. `common` — минимальные утилиты (config/logger/migrations) без бизнес‑логики. `core` — инфраструктура артефактов/контрактов/trace/run‑контекстов.

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

## Модули системы (актуальное назначение и контракты)

Ниже — “карта модулей” в терминах **ответственности** и **контрактов**. Детали — в README каждого модуля.

### `polisyos.core` — инфраструктурный фундамент

Что даёт:
- **CAS/артефакты**: `core.artifacts` (FileSystemCAS, ArtifactID/Ref/Manifest, provenance).
- **Канонический JSON**: `core.canon` (детерминированная сериализация, запрет float → Decimal‑first).
- **Контракты между слоями**: `core.contracts` (foundry/fabric/compiler).
- **Трассировка**: `core.trace` (JsonlTraceSink, TraceRecord).
- **Run‑контекст**: `core.run` (RunContext/RunManifest).
- **Реестры**: `core.registry` (сборка/загрузка bundles).

### `polisyos.ir` — канонические контракты политики (IR)

Что определяет:
- **Surface IR v2.0**: `ir.surface.PolicySurfaceIR` (semantic/advisory раздельно).
- **Kernel‑реестры**: `ir.kernel` (mechanisms/slots/merge rules/units/time semantics/values).
- **Data views**: `ir.data_views` (PANEL/SNAPSHOT/NETWORK, access tiers, фильтры).
- **Linker**: `ir.linker` (валидация/связывание политики с реестрами).
- **Fact Log контракты**: `ir.fact_log` (immutable facts, provenance/trust/legal).
- **Миграции**: `ir.migrations` + loaders (авто‑распознавание версии и коэрция v1→v2).

### `polisyos.fabric` — Unified Data Fabric (данные + evidence)

Что делает:
- **Ingestion pipeline**: raw CSV → staging (Parquet) → curated (DuckDB/Kùzu) + manifests.
- **UDF**: компилируемый безопасный слой запросов (passes: resolution/typecheck/merge/privacy/lowering).
- **Fact Log**: запись immutable фактов + сегменты/манифесты.
- **Evidence bundles**: provenance трансформаций и источников, хранение в CAS через `core`.
- **Entity resolution / reconciliation**: нормализация ID, балансовые проверки транзакций.

Важно по статусу:
- `materializer` сейчас описан как **placeholder** (есть каркас/логирование, полная материализация ещё в разработке).

### `polisyos.foundry` — JAX‑ядро исполнения (compiler + runtime + calibration)

Что делает:
- **Компиляция**: IR → ProgramGraph + ExecPlan (топологический порядок).
- **Patch‑based execution**: механизмы генерируют патчи в слоты; применяется merge rules.
- **Deterministic RNG**: Treasury plan (узлам выдаются детерминированные соли/ключи).
- **Calibration MVP**: калибровка параметров по целям, отчёты, uncertainty (на уровне репортов).
- **Multi‑fidelity**: уровни точности (fluid/relaxed/hard) для trade‑off скорость/реализм.

### `polisyos.scientist` — AI Policy Scientist (оркестрация эксперимента)

Что делает:
- **Workflow**: LangGraph + FSM (фазы), узлы: draft → validate → repair → compile_data_views → compile_model → run_sim → analyze → governor → pack_decision.
- **Governance**: preflight/postflight, human gates.
- **Budgets**: compute/evidence/legitimacy/complexity бюджеты и их enforcement.
- **Optimization**: градиентная оптимизация (Optax) и multi‑objective (PyMOO).
- **DecisionPacket**: финальный “пакет решения” с IR, артефактами, аудитом, результатами.

### `polisyos.runtime` — жизненный цикл прогонов (runs/<run_id>)

Что делает:
- **start_run / finalize_run**: создание и финализация прогона.
- **log_artifact**: стандартизированная запись артефактов в `runs/<run_id>/artifacts/...`.
- **append_audit**: JSONL audit trail.
- **budget_usage**: фиксация использования бюджета.

Ключевая особенность: **переносимость** — рекомендуем `ArtifactRef.relative_path` (поле `path` считается устаревшим).

### `polisyos.common` — минимальная инфраструктура (без бизнес‑логики)

Что делает:
- **config/jax_env**: безопасные настройки JAX (особенно macOS/Metal).
- **logger/get_logger**: единое структурированное логирование.
- **migrations**: детерминированные миграции некоторых артефактов (на уровне инфраструктуры).

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
- **[`src/polisyos/core/README.md`](src/polisyos/core/README.md)**: CAS/артефакты, канонический JSON, contracts, trace, run‑контекст, registry

### Intermediate Representation
- **[`src/polisyos/ir/README.md`](src/polisyos/ir/README.md)**: PolicySurfaceIR, kernel‑реестры, linker, loaders/migrations, fact log контракты

### Unified Data Fabric
- **[`src/polisyos/fabric/README.md`](src/polisyos/fabric/README.md)**: ingestion, DuckDB/Kùzu, UDF compiler pipeline, Fact Log, evidence

### JAX Simulation Core
- **[`src/polisyos/foundry/README.md`](src/polisyos/foundry/README.md)**: compile→ProgramGraph, patch VM, механизмы, treasury, calibration, legacy слой

### AI Policy Scientist
- **[`src/polisyos/scientist/README.md`](src/polisyos/scientist/README.md)**: LangGraph workflow, budgets/governance, DoE, publisher, legacy слой

### Runtime & Lifecycle
- **[`src/polisyos/runtime/README.md`](src/polisyos/runtime/README.md)**: runs/<run_id>, audit.jsonl, log_artifact, budget usage, переносимость путей

### Common Utilities
- **[`src/polisyos/common/README.md`](src/polisyos/common/README.md)**: config/jax_env, logger, migrations

### Testing Framework
- **[`tests/README.md`](tests/README.md)**: структура тестов, категории, архитектурные гейты, интеграция CI

### Developer Tools
- **[`tools/README.md`](tools/README.md)**: линтеры законов, диагностика, миграции, схемы, бенчмарки, демо

## Архитектурные принципы проекта

- **[`architecture.md`](../architecture.md)**: Подробное описание архитектурных законов и принципов
- **Закон A**: Направленный граф зависимостей (только внутрь)
- **Закон B**: Компиляторная архитектура (чистота математического ядра)
- **Закон C**: Контракты - единственный источник истины
- **Закон D**: Воспроизводимость и аудит всех прогонов
- **Закон E**: Evidence обязательны для data‑провода (provenance/доверие к данным)
- **Закон F**: Fidelity control (управление точностью симуляций/калибровок)
- **Закон G**: Uncertainty quantification (оценки неопределённости в калибровке/отчётах)

## Контрибьютинг

При работе с проектом следуйте архитектурным принципам:

1. **Соблюдайте архитектурные законы** - используйте линтеры для проверки
2. **Обновляйте контракты в IR** - любые изменения структур данных
3. **Добавляйте тесты** - unit для новых функций, integration для workflow
4. **Обновляйте документацию** - README модулей при изменениях API
5. **Используйте runtime API** - для логирования артефактов и аудита

## Лицензия и поддержка

Проект находится в активной разработке. Для вопросов и предложений используйте issue tracker или связывайтесь с командой разработки.

## Legacy и переходные зоны (после крупных изменений)

Система активно эволюционировала; часть кода/контрактов сохраняется для совместимости и миграций. Важно явно понимать, что “новое”, а что “поддерживается, но не развиваем”.

### Legacy в `ir`

- **`ir/contract.py` (IR v1.0)**: устаревшие модели (`PolicyIR`, иерархические `PolicyEntity`, старые селекторы). Сохраняются для обратной совместимости и миграции.
- **Переход на v2**: основной контракт — `ir/surface.py` (`PolicySurfaceIR`). Загрузчики (`ir/loaders.py`) умеют распознавать версии и коэрсить v1→v2.

### Legacy в `foundry`

- **`foundry/_legacy/engine/*` и `basic_simulation.py`**: старый симуляционный движок и демо. Новая линия — ProgramGraph + patch‑based runtime.
- **Механизмы “step()” vs “emit_patches()”**: новые механизмы должны использовать patch‑first подход; `step()` остаётся как совместимость/переходный слой.

### Legacy в `scientist`

- **`scientist/_legacy/*`**: старый компилятор/узлы workflow. Актуальная линия — `scientist/orchestrator/*` (LangGraph + `flow_nodes.py` + FSM/guards).

### Переходные зоны в `fabric`

- **Materializer**: в документации обозначен как placeholder — каркас есть, но полная материализация DuckDB/Kùzu из Fact Log ещё не доведена до конечного состояния.

### Переходные зоны в `runtime`

- **`ArtifactRef.path`**: поддерживается для старых артефактов, но для новых следует использовать `relative_path` (переносимость runs/).

---

*Policy Engine (PolisyOS) — компиляторная система симуляции политик: контракты → компиляция → JAX‑исполнение → артефакты с аудитом и воспроизводимостью.*
