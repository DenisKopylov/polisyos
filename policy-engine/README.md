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
- **Закон H — evidence обязательны**: data провода фиксируют provenance/evidence (важно для доверия к данным).
- **Закон I — trust policies**: многоуровневые политики доверия к источникам данных с statistical verification.

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
- **Canonical JSON**: детерминированная сериализация для reproducible хешей

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
- **Run Manifest**: паспорт эксперимента с метаданными и артефактами
- **Audit Trail**: JSON Lines логирование всех операций

### Quality & Development Tools
- **Ruff**: быстрый линтер и форматер (замена Black + Flake8 + Isort)
- **MyPy**: строгая статическая типизация
- **Pytest**: unit/integration/contract тесты
- **Pre-commit**: git hooks (dev зависимости)
- **JupyterLab + Matplotlib + Seaborn**: ноутбуки и исследовательская визуализация

### Новые компоненты (после крупных изменений)
- **Fact Log System**: immutable факты с provenance tracking и детерминированные ID
- **Evidence Bundles**: криптографически verifiable доказательства происхождения данных
- **UDF Compilation Pipeline**: многофазная компиляция SQL/Cypher запросов с security passes
- **Patch-based Execution**: декларативные изменения состояния через UpdateOp и Merge Rules
- **Treasury System**: детерминированное управление RNG для воспроизводимости
- **Materializer Engine**: полная материализация реляционных представлений из Fact Log с incremental updates
- **Trust System**: многоуровневые политики доверия с statistical verification
- **Calibration MVP**: полная система калибровки параметров с uncertainty quantification
- **Runtime API**: жизненный цикл прогонов с переносимыми артефактами и audit trail

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
│   │   ├── __init__.py     # Экспорт run_ingestion (главный API)
│   │   ├── ingestion.py    # ETL пайплайн с Fact Log и evidence
│   │   ├── schema.py       # Pydantic схемы данных (AgentRow, InteractionRow, MacroRow)
│   │   ├── manifest.py     # Метаданные и качество данных (DatasetManifest, QualityMetrics)
│   │   ├── registry.py     # Управление манифестами датасетов
│   │   ├── config.py       # Правила нормализации и reconciliation
│   │   ├── evidence.py     # Система доказательств (build_evidence_bundle)
│   │   ├── materializer.py # Полная материализация из Fact Log (incremental updates)
│   │   ├── segment_manifest.py # Управление сегментами Fact Log
│   │   ├── fact_writer.py  # Запись фактов в каноническом формате
│   │   ├── trust.py        # Политики доверия (two_pass_compare, uncertainty bounds)
│   │   ├── io/             # Адаптеры хранилищ (DuckDB, Kuzu)
│   │   │   ├── __init__.py # Экспорт адаптеров хранения
│   │   │   ├── db.py       # DuckDB адаптер (SimulationDB)
│   │   │   └── graph_store.py # Kùzu графовый адаптер (GraphStore)
│   │   └── udf/            # Unified Data Fabric - безопасный слой запросов
│   │       ├── __init__.py # Экспорт UDF компонентов
│   │       ├── engine.py   # UDF движок с CAS интеграцией
│   │       ├── compiler.py # Безопасный компилятор SQL/Cypher
│   │       ├── plan.py     # Планы выполнения запросов (DataViewPlan)
│   │       ├── config.py   # UDF конфигурация и whitelist (UdfSchema)
│   │       ├── schema.py   # Реэкспорт типов из ir.data_views
│   │       └── passes/     # Компиляционный пайплайн запросов
│   │           ├── __init__.py      # Экспорт всех pass-функций
│   │           ├── lowering.py      # Понижение уровня абстракции (SQL/Cypher generation)
│   │           ├── merge.py         # Слияние и оптимизация запросов
│   │           ├── privacy.py       # Контроль приватности и PII-фильтрация
│   │           ├── resolution.py    # Разрешение имен таблиц/колонок
│   │           └── typecheck.py     # Проверка типов данных и единиц измерения
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
│   │   │   ├── workflow.py # LangGraph workflow с 9 узлами
│   │   │   ├── state.py    # ExperimentState (TypedDict с 80+ полями)
│   │   │   ├── flow_nodes.py # Реализации узлов workflow (1450+ строк)
│   │   │   ├── decision_packet.py # DecisionPacket с полной информацией
│   │   │   ├── run_record.py # RunRecord для воспроизводимости
│   │   │   ├── audit.py    # Система аудита и логирования
│   │   │   ├── data_loader.py # Загрузка данных из Fabric
│   │   │   └── publisher.py # Публикация решений
│   │   ├── compute/        # Спецификации вычислительных задач (job_spec, runner)
│   │   ├── doe/            # Design of Experiments (ScenarioSweep, AblationPlan)
│   │   ├── governance/     # Управление качеством (preflight, postflight)
│   │   ├── kernel/         # Ядро управления (FSM, budgets, guards, human_gate)
│   │   │   ├── budgets.py  # Compute/Evidence/Legitimacy/Complexity budgets
│   │   │   ├── fsm.py      # Конечный автомат состояний с 9 фазами
│   │   │   ├── guards.py   # Проверки переходов между состояниями
│   │   │   └── human_gate.py # Асинхронные human gates (GateRequest/GateDecision)
│   │   └── _legacy/        # Legacy код (устаревший компилятор/узлы)
│   ├── runtime/            # Управление жизненным циклом прогонов
│   │   ├── __init__.py     # Публичный API модуля
│   │   ├── api.py          # Основные функции управления жизненным циклом
│   │   ├── manifest.py     # RunManifest, ArtifactRef модели
│   │   └── README.md       # Детальная документация runtime
│   └── common/             # Фундаментальные утилиты
│       ├── __init__.py     # Пустой (модуль не экспортирует публичный API)
│       ├── config.py       # Централизованная конфигурация приложения и JAX
│       ├── jax_env.py      # Безопасная настройка JAX backend для macOS
│       ├── logger.py       # Единый интерфейс структурированного логирования
│       └── migrations/     # Детерминированные миграции схем артефактов
│           ├── __init__.py # Экспорт API миграций
│           ├── base.py     # Ядро системы миграций
│           ├── manifest.py # Миграции Dataset Manifest
│           └── policy_ir.py # Миграции Policy IR
├── examples/               # Примеры и демо-скрипты
├── tests/                  # Комплексная тестовая инфраструктура
│   ├── conftest.py         # Конфигурация pytest и JAX setup
│   ├── contract/           # Тесты контрактов IR и схем
│   ├── core_phase0/        # Тесты фундаментальных компонентов
│   ├── foundry/            # Тесты JAX симуляций
│   ├── integration/        # End-to-end тесты workflow
│   └── scientist/          # Тесты AI компонентов
└── tools/                  # Инструменты разработчика
    ├── benchmarks/         # Бенчмарки производительности (bench_domain.py, bench_simulation.py)
    ├── demos/              # Демонстрации возможностей (run_ingest_demo.py, run_udf_*.py, run_optimizer_demo.py)
    ├── diagnostics/        # Диагностика и анализ (check_setup.py, check_udf_perf.py, generate_ir_schema.py)
    ├── gen_schema.py       # Генератор JSON Schema из Pydantic моделей
    ├── lint_foundry.py     # Архитектурный линтер foundry (Закон B)
    ├── lint_imports.py     # Линтер межмодульных зависимостей (Закон A)
    ├── migrate.py          # Универсальная миграция артефактов
    └── migrate_ir.py       # Специализированная миграция Policy IR
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

**Архитектурная роль**: Самый нижний слой в иерархии зависимостей, предоставляет примитивы для всех модулей системы. Все модули (Fabric, Foundry, IR, Scientist, Runtime) зависят от core, но core не зависит ни от кого.

Что даёт:
- **Artifacts (Артефакты)**: `core.artifacts` (FileSystemCAS, ArtifactID/Ref/Manifest, provenance, content-addressable storage)
- **Canonical JSON**: `core.canon` (детерминированная сериализация, запрет float, сортировка ключей, reproducible хеши)
- **Contracts (Контракты)**: `core.contracts` (foundry/fabric/compiler - типизированные ссылки на артефакты)
- **Trace (Трассировка)**: `core.trace` (JsonlTraceSink, TraceRecord, distributed tracing с span_id)
- **Run (Выполнение)**: `core.run` (RunContext/RunManifest, контексты выполнения с трассировкой)
- **Registry (Реестры)**: `core.registry` (сборка/загрузка registry bundles из IR модуля)

### `polisyos.ir` — канонические контракты политики (IR)

**Архитектурная роль**: Фундаментальный слой контрактов, определяющий единообразие коммуникации между всеми компонентами. IR не имеет зависимостей и используется всеми модулями системы.

Что определяет:
- **Surface IR v2.0**: `ir.surface.PolicySurfaceIR` (semantic/advisory раздельно, исполняемая логика vs человекочитаемые описания)
- **Kernel-реестры**: `ir.kernel` (mechanisms/slots/merge rules/units/time semantics/trust policies/values - фундаментальные типы)
- **Data views**: `ir.data_views` (PANEL/SNAPSHOT/NETWORK, access tiers, фильтры для запросов данных)
- **Linker**: `ir.linker` (валидация/связывание политики с реестрами, проверка корректности интервенций)
- **Fact Log контракты**: `ir.fact_log` (immutable facts, provenance/trust/legal, детерминированные ID)
- **Loaders & Migrations**: `ir.loaders` + `ir.migrations` (автораспознавание версии, коэрция v1→v2, детерминированные миграции)
- **Calibration**: `ir.calibration` (контракты калибровки политик относительно исторических данных)
- **Validation**: `ir.validation` (структурированные отчеты о проблемах, diff между версиями)

### `polisyos.fabric` — Unified Data Fabric (данные + evidence)

**Архитектурная роль**: Обработка данных и агрегация в Runtime Backend. Зависит от `ir` (контракты) и `core` (артефакты), предоставляет данные для `scientist` и `foundry`.

Что делает:
- **Data Ingestion Pipeline**: Полный ETL (raw CSV → staging Parquet → curated DuckDB/Kùzu) с evidence tracking
- **UDF Engine**: Безопасный компилируемый слой запросов с whitelist (passes: resolution/typecheck/merge/privacy/lowering)
- **Fact Log System**: Immutable факты с provenance tracking, детерминированные ID, сегментация
- **Evidence Bundles**: Криптографически verifiable доказательства происхождения, хранение в CAS
- **Entity Resolution**: Нормализация идентификаторов агентов с confidence scoring
- **Financial Reconciliation**: Балансовая проверка транзакций с tolerance
- **Materializer Engine**: Полная материализация реляционных представлений из Fact Log с incremental updates
- **Trust System**: Многоуровневые политики доверия с statistical verification и uncertainty bounds

**Технологии**: DuckDB (реляционное), Kùzu (графовое), PyArrow (columnar), Pydantic (валидация), Pandas (ETL)

### `polisyos.foundry` — JAX‑ядро исполнения (compiler + runtime + calibration)

**Архитектурная роль**: Policy execution backend с JAX-симуляциями. Зависит только от `ir` (типы) и `core` (артефакты), является чистым математическим ядром без side effects.

Что делает:
- **Compiler Layer**: Компиляция IR → ProgramGraph + ExecPlan (топологический порядок, registry-driven compilation)
- **Runtime Layer**: Patch-based execution с UpdateOp, Merge Rules (SUM/OVERRIDE/PRIORITY/ERROR), constraints validation
- **Domain Layer**: Экономическая модель (GlobalState, AgentState, FirmState, MarketState) с Jaxtyping
- **Mechanism Layer**: Механизмы политик (IncomeTax, TaxSubsidy, LaborMarket, Queue) с multi-fidelity (fluid/relaxed/hard)
- **Calibration Layer**: Полная система калибровки параметров с Optax, bijectors, loss functions, uncertainty quantification через Hessian
- **Treasury System**: Детерминированное управление RNG для reproducible симуляций

**Технологии**: JAX/Equinox (вычисления), Jaxtyping/Chex (типизация), Optax (оптимизация), Pydantic (конфигурация)

### `polisyos.scientist` — AI Policy Scientist (оркестрация эксперимента)

Что делает:
- **Workflow**: LangGraph + FSM (фазы), узлы: draft → validate → repair → compile_data_views → compile_model → run_sim → analyze → governor → pack_decision.
- **Governance**: preflight/postflight, human gates.
- **Budgets**: compute/evidence/legitimacy/complexity бюджеты и их enforcement.
- **Optimization**: градиентная оптимизация (Optax) и multi‑objective (PyMOO).
- **DecisionPacket**: финальный “пакет решения” с IR, артефактами, аудитом, результатами.

### `polisyos.runtime` — жизненный цикл прогонов (runs/<run_id>)

**Архитектурная роль**: Инфраструктура управления жизненным циклом экспериментов. Единственная точка входа для создания и управления запусками (Закон D).

Что делает:
- **API**: `start_run()`, `finalize_run()`, `log_artifact()`, `append_audit()`, `update_budget_usage()`
- **Run Manifest**: Паспорт эксперимента с метаданными, бюджетами, артефактами
- **Artifact Management**: Структурированное хранение в `runs/<run_id>/` с переносимыми ссылками
- **Audit Trail**: Полный JSON Lines лог всех операций с временными метками
- **Budget Tracking**: Отслеживание использования ресурсов (compute, memory, time)

Ключевая особенность: **переносимость** — `ArtifactRef.relative_path` для перемещения директорий без потери ссылок.

### `polisyos.common` — минимальная инфраструктура (без бизнес‑логики)

**Архитектурная роль**: Фундаментальные утилиты и конфигурации, используемые во всех слоях. Не имеет зависимостей от других модулей, предоставляет сервисы всем компонентам системы.

Что делает:
- **Config**: Централизованная конфигурация приложения, JAX environment setup, hardware safeguards (CPU cores, memory limits)
- **JAX Environment**: Безопасная настройка JAX backend для macOS (отключение Metal по умолчанию)
- **Logger**: Единый интерфейс структурированного логирования с контекстом модуля через Loguru
- **Migrations**: Детерминированные миграции схем артефактов (Dataset Manifest, Policy IR) с обнаружением циклов

**Принцип**: Только инфраструктура и утилиты, без бизнес-логики.

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

# UDF запросы к данным (PANEL/SNAPSHOT/NETWORK views)
python tools/demos/run_udf_query_demo.py

# Гибридные UDF запросы (SQL + Python functions)
python tools/demos/run_udf_hybrid_demo.py

# Полный scientist workflow с LLM (требует API ключей)
python -m polisyos.scientist.orchestrator.workflow

# Калибровка параметров политики на исторических данных
python tools/demos/run_calibration_udf_demo.py
```

### 3. Разработка и тестирование

```bash
# Архитектурные проверки
python tools/lint_imports.py    # Закон A (направленные зависимости)
python tools/lint_foundry.py    # Закон B (чистота математического ядра)

# Качество кода
ruff check . && ruff format .
mypy src/

# Полный тест-свит с категориями
pytest tests/ -x --tb=short

# Только contract тесты (быстрые, без зависимостей)
pytest tests/contract/ -v

# Foundry тесты (JAX, симуляции, калибровка)
pytest tests/foundry/ -v

# Integration тесты (workflow, scientist + fabric + foundry)
pytest tests/integration/ -v
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

- **FSM-based Orchestration**: Конечный автомат состояний с 9 фазами для надежного workflow
- **Budget Controls**: Compute/Evidence/Legitimacy/Complexity бюджеты с enforcement
- **Human Gates**: Асинхронная система GateRequest/GateDecision для человеческого одобрения
- **Design of Experiments**: ScenarioSweep, AblationPlan, SensitivityPlan
- **Self-healing Policies**: Автоматическое исправление ошибок валидации через LLM
- **Decision Packet**: Полный артефакт с IR, результатами, аудитом и evidence

### 🔬 Продвинутое симуляционное ядро

- **Program Graph Compilation**: Топологическая сортировка и execution plans с registry-driven линковкой
- **Patch-based Execution**: UpdateOp и Merge Rules (SUM/OVERRIDE/PRIORITY/ERROR) для state management
- **Multi-fidelity Mechanisms**: Fluid/relaxed/hard уровни точности с fidelity control
- **Calibration MVP**: Полная система калибровки параметров с uncertainty quantification через Hessian
- **Constraints Engine**: Runtime валидация ограничений с enforcement
- **Treasury System**: Детерминированное управление RNG для reproducible симуляций

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
- **[`src/polisyos/core/README.md`](src/polisyos/core/README.md)**: Content-Addressable Storage, канонический JSON, типизированные контракты, distributed tracing, run contexts, registry bundles

### Intermediate Representation
- **[`src/polisyos/ir/README.md`](src/polisyos/ir/README.md)**: PolicySurfaceIR v2.0, kernel-реестры (mechanisms/slots/merge rules), linker, loaders/migrations, Fact Log контракты, calibration configs

### Unified Data Fabric
- **[`src/polisyos/fabric/README.md`](src/polisyos/fabric/README.md)**: ETL pipeline, DuckDB/Kùzu storage, UDF compilation pipeline, Fact Log system, evidence bundles, materializer, trust policies

### JAX Simulation Core
- **[`src/polisyos/foundry/README.md`](src/polisyos/foundry/README.md)**: ProgramGraph compilation, patch-based execution, multi-fidelity mechanisms, calibration MVP, constraints engine, treasury RNG

### AI Policy Scientist
- **[`src/polisyos/scientist/README.md`](src/polisyos/scientist/README.md)**: LangGraph workflow, FSM orchestration, budget controls, human gates, DoE, DecisionPacket, audit trail

### Runtime & Lifecycle
- **[`src/polisyos/runtime/README.md`](src/polisyos/runtime/README.md)**: RunManifest, audit.jsonl, artifact logging, budget tracking, relative paths для portability

### Common Utilities
- **[`src/polisyos/common/README.md`](src/polisyos/common/README.md)**: JAX environment setup, structured logging, schema migrations, hardware safeguards

### Testing Framework
- **[`tests/README.md`](tests/README.md)**: Contract/IR/core_phase0/fabric/foundry/integration тесты, calibration, evidence bundles, trust policies

### Developer Tools
- **[`tools/README.md`](tools/README.md)**: Architecture linters (Законы A/B), schema generation, migrations, benchmarks, demos, diagnostics

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

- **`ir/contract.py` (IR v1.0)**: Устаревшие модели (`PolicyIR`, иерархические `PolicyEntity`, старые селекторы). Сохраняются для обратной совместимости
- **Переход на v2**: Основной контракт — `ir/surface.py` (`PolicySurfaceIR` с разделением semantic/advisory). Загрузчики (`ir/loaders.py`) автоматически распознают версии и конвертируют v1→v2

### Legacy в `foundry`

- **`foundry/_legacy/engine/*` и `basic_simulation.py`**: старый симуляционный движок и демо. Новая линия — ProgramGraph + patch‑based runtime.
- **Механизмы “step()” vs “emit_patches()”**: новые механизмы должны использовать patch‑first подход; `step()` остаётся как совместимость/переходный слой.

### Legacy в `scientist`

- **`scientist/_legacy/*`**: Старый компилятор и узлы workflow. Актуальная линия — `scientist/orchestrator/*` (LangGraph + flow_nodes.py + FSM/guards/budgets)

### Переходные зоны в `fabric`

- **Materializer**: Полноценная система материализации реляционных представлений из Fact Log с incremental updates (раньше был placeholder)

### Переходные зоны в `runtime`

- **`ArtifactRef.path`**: Поддерживается для старых артефактов, но для новых рекомендуется `relative_path` для переносимости директорий `runs/`

---

*Policy Engine (PolisyOS) — компиляторная система симуляции политик: контракты → компиляция → JAX‑исполнение → артефакты с аудитом и воспроизводимостью.*
