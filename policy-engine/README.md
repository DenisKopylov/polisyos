# Policy Engine (PolisyOS)

**Policy Engine** — AI‑driven система проектирования, валидации, калибровки и исполнения политик. Архитектурно это “компиляторная труба”: от запроса пользователя/LLM до формально типизированных контрактов (IR), далее — компиляция в исполняемые графы, выполнение в JAX‑ядре и фиксация результатов в воспроизводимых артефактах.

**Состояние документа (актуально на 2026‑01‑21):** архитектура v2.1 (Fabric layer, Calibration MVP, Runtime API), присутствуют переходные зоны/устаревшие интерфейсы (см. раздел “Legacy и переходные зоны”).

## Архитектурный обзор

### Компиляторная труба (сверху вниз)

```
NL/Request → Scientist (LLM + Workflow) → IR (contracts) → Compilation → Runtime (Fabric UDF + Foundry) → Artifacts
```

Грубо: `scientist` производит/чинит IR, `ir` задаёт контракты, `fabric` обеспечивает данные/доказательства, `foundry` компилирует и исполняет политику, `runtime` фиксирует прогон, `core` даёт инфраструктуру артефактов/контрактов/трассировки.

### Архитектурные законы (инварианты проекта)

Проект опирается на набор инвариантов. Часть из них формализована инструментами в `tools/`, часть — пока соглашения, поддерживаемые тестами и код‑ревью.

- **Закон A — Import Gate (границы модулей)**: `tools/lint_imports.py` запрещает критические обратные зависимости (`foundry → fabric`, `fabric → scientist`) и репортит циклы (по умолчанию не фейлит; `--fail-on-cycles` включает strict‑mode).
- **Закон B — Foundry как JAX‑ядро без прямого I/O**: `tools/lint_foundry.py` запрещает импорт I/O/DB/network библиотек и вызовы `print()`/`open()` в `polisyos.foundry`. As‑is: сейчас `src/polisyos/foundry/agents.py` является исключением (использует `os`/`pathlib` для загрузки артефактов), поэтому “чистое ядро” следует искать в `src/polisyos/foundry/runtime.py`, `src/polisyos/foundry/executor.py`, `src/polisyos/foundry/patch_vm.py`, `src/polisyos/foundry/calibration/pure_executor.py`.
- **Закон C — контракты как источник истины**: структуры данных определены в `polisyos.ir` и `polisyos.core.contracts`, экспортируются в JSON Schema (`tools/gen_schema.py` → `policy_ir_schema.json`) и валидируются на границах.
- **Закон D — воспроизводимость и аудит прогонов**: каждый прогон имеет `run_id`, детерминированные seed’ы (Treasury), audit trail (`runs/<run_id>/audit.jsonl`) и воспроизводимые артефакты в CAS.
- **Закон E — evidence и provenance обязательны для данных**: `polisyos.fabric` фиксирует источники/трансформации (EvidenceBundle), а также immutable факты (Fact Log) с provenance/trust/legal метаданными.
- **Закон F — fidelity control**: симуляции/калибровки поддерживают управление точностью (speed/accuracy trade‑off) через `foundry.types.FidelityLevel` и multi‑fidelity механизмы.
- **Закон G — uncertainty quantification**: калибровка и trust‑подсистема возвращают bounds/оценки неопределённости (артефакты + отчёты).
- **Закон H — governance и бюджеты**: `polisyos.scientist` ограничивает вычисления и внешние вызовы (budgets), выполняет preflight/postflight и поддерживает human gates при необходимости.
- **Закон I — trust + privacy**: уровни доступа к данным (AccessTier), privacy passes в UDF компиляции, trust policies (two‑pass compare, uncertainty bounds).

### Слои и зависимости (упрощённо)

Импортные границы, которые реально проверяет `tools/lint_imports.py` (Import Gate):

- `polisyos.foundry` не импортирует `polisyos.fabric`
- `polisyos.fabric` не импортирует `polisyos.scientist`
- циклы репортятся, но по умолчанию не фейлят (на текущем коде есть `polisyos.core ↔ polisyos.ir` и др.)

Практическая карта модулей (упрощённо, As‑Is):

```
common:   no deps
runtime:  no deps

ir:    core.canon + common.migrations
core:  ir.kernel + ir.linker      # registry bundles, LinkReport

fabric:   ir + core + common
foundry:  ir + core
scientist: ir + fabric + foundry + runtime + core + common
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
├── pyproject.toml / uv.lock
├── README.md
├── env_example.txt / install.sh
├── policy_ir_schema.json          # JSON Schema snapshot (PolicySurfaceIR)
├── .env                           # API ключи и конфигурация (не в Git!)
├── .polisyos/                     # CAS root (artifacts/sha256/…)
├── data/                          # raw/staging/curated (+ manifests, udf_schema.json, fact_log/)
├── logs/                          # loguru logs
├── runs/                          # runtime результаты прогонов (создаётся автоматически)
├── *.duckdb / *.kuzu              # локальные demo/integration БД
├── src/polisyos/                  # код модулей
│   ├── common/
│   ├── ir/
│   ├── core/
│   ├── fabric/
│   ├── foundry/
│   ├── scientist/
│   └── runtime/
├── tests/                         # pytest suite (contract/fabric/foundry/integration/…)
└── tools/                         # demos/benchmarks/diagnostics + linters + migrations
    ├── benchmarks/
    ├── demos/
    ├── diagnostics/
    ├── gen_schema.py
    ├── lint_foundry.py
    ├── lint_imports.py
    ├── migrate.py
    ├── migrate_ir.py
    └── run_mechanism_design.py
```

## Архитектурные принципы

Policy Engine поддерживает архитектурные гарантии через набор проверок/инструментов (см. также `../architecture.md`).

### Закон A: Import Gate (границы модулей)
```
# Запрещены runtime-imports:
foundry → fabric
fabric → scientist

# Циклы репортятся (на текущем коде есть core ↔ ir и др.)
```
Import‑gate фокусируется на ключевых границах: Foundry не должен тянуть DB/data‑слой, а Fabric не должен тянуть orchestration/LLM‑слой. Циклы на package‑уровне показываются в отчёте и могут быть сделаны fatal через `--fail-on-cycles`.

**Инструменты проверки:** `tools/lint_imports.py` (см. `python tools/lint_imports.py --help`).

### Закон B: Foundry как JAX‑ядро без прямого I/O
```
NL → LLM → IR (AST) → Compilation → Runtime → Artifacts
```
Foundry проектируется как “ядро вычислений”: компиляция IR → JAX‑исполнение + калибровка. Прямые импорты I/O/DB/network и вызовы `print()`/`open()` запрещены в `polisyos.foundry` (ban‑list линтер).

**Инструменты проверки:** `tools/lint_foundry.py`. As‑is: линтер сейчас репортит известное исключение в `src/polisyos/foundry/agents.py` (I/O для загрузки артефактов).

### Закон C: Контракты - единственный источник истины
```
IR schemas → JSON Schema export → All components validation
```
Контракты данных задаются Pydantic‑моделями в `polisyos.ir` и типизированными ссылками в `polisyos.core.contracts`. `policy_ir_schema.json` — зафиксированный snapshot JSON Schema для `PolicySurfaceIR`.

**Инструменты проверки:** `tools/gen_schema.py` (генерация/`--check` snapshot).

### Закон D: Любой прогон воспроизводим и аудируем
```
RunManifest + seed + artifacts → Full reproducibility
```
Каждый эксперимент имеет уникальный `run_id`, детерминированные seed’ы (Treasury), audit trail и артефакты. В текущей реализации используются два “хранилища”:

- `runs/<run_id>/` — run‑ориентированное хранилище (runtime manifest + audit + человекочитаемые артефакты)
- `.polisyos/` — content‑addressable storage (CAS) для неизменяемых артефактов (sha256 addressing)

**Инструменты поддержки:** Runtime API (`polisyos.runtime.*`) + CAS (`polisyos.core.artifacts.store.FileSystemCAS`).

## Модули системы (актуальное назначение и контракты)

Ниже — “карта модулей” в терминах **ответственности** и **контрактов**. Детали — в README каждого модуля.

### `polisyos.core` — инфраструктурный фундамент

**Архитектурная роль**: Инфраструктурный слой артефактов/контрактов/трассировки. В текущем коде `core` и `ir` взаимосвязаны (package‑cycle): IR использует `core.canon` для детерминированного хеширования, а core использует IR‑типы для сборки registry bundle и отчётов линковки.

Что даёт:
- **Artifacts (Артефакты)**: `core.artifacts` (FileSystemCAS, ArtifactID/Ref/Manifest, provenance, content-addressable storage)
- **Canonical JSON**: `core.canon` (детерминированная сериализация, запрет float, сортировка ключей, reproducible хеши)
- **Contracts (Контракты)**: `core.contracts` (foundry/fabric/compiler - типизированные ссылки на артефакты)
- **Trace (Трассировка)**: `core.trace` (JsonlTraceSink, TraceRecord, distributed tracing с span_id)
- **Run (Выполнение)**: `core.run` (RunContext/RunManifest, контексты выполнения с трассировкой)
- **Registry (Реестры)**: `core.registry` (сборка/загрузка registry bundles поверх `ir.kernel` реестров)

### `polisyos.ir` — канонические контракты политики (IR)

**Архитектурная роль**: Слой контрактов данных для всей системы (LLM → data → execution). As‑is IR в основном “чистый контракт”, но использует `core.canon` (детерминированные ID) и `common.migrations` (обёртки миграций артефактов).

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

**Архитектурная роль**: Data backend (ingestion + UDF + evidence/trust). Зависит от `ir` (контракты), `core` (CAS/контракты) и `common` (logger/config), предоставляет данные для `scientist` и `foundry`.

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

**Архитектурная роль**: Policy execution backend с JAX‑симуляциями: компиляция IR в ProgramGraph/ExecPlan, patch‑based runtime, калибровка/оптимизация параметров. Import‑gate гарантирует, что Foundry не зависит от Fabric (`foundry → fabric` запрещён).

> Примечание: `tools/lint_foundry.py` задуман как enforcement “без прямого I/O”, но на текущем коде флагирует известное исключение в `src/polisyos/foundry/agents.py` (I/O для загрузки артефактов).

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
- **Workflow**: LangGraph + FSM (фазы), узлы (as‑is): `draft_ir` → `validate_ir` → `repair_ir` (loop) → `compile_data_views` → `compile_model` → `train_agents` → `run_sim` → `analyze` → `governor` → `pack_decision`.
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

- **CAS (Content‑Addressable Storage)**: по умолчанию в `.polisyos/` (layout: `artifacts/sha256/ab/cd/<hex>.{blob,manifest.json}`); может быть перенесён через `POLISYOS_CAS_ROOT` или параметр `cas_root`.
- **Runtime runs/**: `polisyos.runtime` пишет “человекочитаемые” артефакты и аудит в `runs/<run_id>/` (`manifest.json`, `audit.jsonl`, `artifacts/*`). В эти файлы часто логируются *ссылки* на CAS‑артефакты (refs), а не сами бинарные payload’ы.
- **Данные**: ingestion/UDF работают вокруг `data/` (`raw/`, `staging/`, `curated/`). Fact Log сегменты по умолчанию создаются в `data/curated/fact_log/`; UDF также умеет резолвить альтернативные пути (`curated/facts`, `data/facts`, `data/fact_log`).
- **Два вида ссылок**: CAS‑ссылки (`polisyos.core.artifacts.manifest.ArtifactRef`) и runtime‑ссылки (`polisyos.runtime.manifest.ArtifactRef`, с `relative_path`).

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

# Scientist workflow (as-is использует MockLLM; не требует API ключей)
python run_experiment.py "Reduce poverty through targeted subsidies"

# Foundry-only демо: обучение агентной политики и “кривая Лаффера”
python tools/demos/run_laffer_demo.py
```

### 3. Разработка и тестирование

```bash
# Архитектурные проверки
python tools/lint_imports.py    # Закон A (import-gate + отчёт о циклах)
python tools/lint_foundry.py    # Закон B (ban-list; сейчас репортит исключение в foundry/agents.py)

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
python tools/lint_imports.py
# (опционально) strict-mode: python tools/lint_imports.py --fail-on-cycles

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
- **Закон A**: Import Gate (границы модулей)
- **Закон B**: Foundry ban‑list (JAX‑ядро без прямого I/O)
- **Закон C**: Контракты - единственный источник истины
- **Закон D**: Воспроизводимость и аудит всех прогонов
- **Закон E**: Evidence обязательны для data‑провода (provenance/доверие к данным)
- **Закон F**: Fidelity control (управление точностью симуляций/калибровок)
- **Закон G**: Uncertainty quantification (оценки неопределённости в калибровке/отчётах)
- **Закон H**: Governance и бюджеты (FSM, guards, human gates)
- **Закон I**: Trust + privacy (access tiers, privacy passes, trust policies)

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

- **`ir/contract.py` (IR v1.0)**: Устаревшие модели и селекторы. Сохраняются для обратной совместимости.
- **Актуальная линия**: `ir/surface.py` (`PolicySurfaceIR`, v2.x). `ir/loaders.py` распознаёт версии и при необходимости конвертирует v1 → v2.

### Legacy в `foundry`

- **Ban‑list vs практика**: `tools/lint_foundry.py` сейчас флагирует известное исключение в `src/polisyos/foundry/agents.py` (I/O для загрузки артефактов). Для чистых JAX‑функций ориентируйтесь на `src/polisyos/foundry/runtime.py` и `src/polisyos/foundry/calibration/pure_executor.py`.

### Legacy в `scientist`

- **Deprecated stubs**: `src/polisyos/scientist/orchestrator/nodes.py` и `src/polisyos/scientist/orchestrator/compiler.py` оставлены как предупреждающие заглушки.
- **Актуальная линия**: `src/polisyos/scientist/orchestrator/workflow.py` (LangGraph) + `src/polisyos/scientist/orchestrator/flow_nodes.py` (узлы).

### Переходные зоны в `fabric`

- **Materializer**: Полноценная система материализации реляционных представлений из Fact Log с incremental updates (раньше был placeholder)

### Переходные зоны в `runtime`

- **`ArtifactRef.path`**: Поддерживается для старых артефактов, но для новых рекомендуется `relative_path` для переносимости директорий `runs/`

---

*Policy Engine (PolisyOS) — компиляторная система симуляции политик: контракты → компиляция → JAX‑исполнение → артефакты с аудитом и воспроизводимостью.*
