# Policy Engine (PolisyOS)

**Policy Engine** — AI‑driven система проектирования, валидации, калибровки и исполнения политик. Архитектурно это “компиляторная труба”: от запроса пользователя/LLM до формально типизированных контрактов (IR), далее — компиляция в исполняемые графы, выполнение в JAX‑ядре и фиксация результатов в воспроизводимых артефактах.

**Состояние документа (актуально на 2026‑01‑27):** архитектура v2.1.4 (Trinity Architecture v2.1.4, W3C PROV-O Integration, Evidence-Enhanced Fabric, Legal Validation System, Quality Gate Enforcement, Trust & Uncertainty Quantification, Hierarchical Agent System, Self-Healing Reflexion, Multi-Fidelity Simulation, Enhanced Environment Manifest, Agent Artifacts, Merge Determinism, Quality Indicators System, Fitness Reports, Quality Gate Pass, Conflict Detection, Cost Model, NaN Guard, Agent Simulation, Decision Card System, Run Timeline Tracking, Decision Packet v2), присутствуют переходные зоны/устаревшие интерфейсы (см. раздел "Legacy и переходные зоны").

## Архитектурный обзор

### Компиляторная труба (сверху вниз)

Policy Engine реализует **многоуровневую компиляторную архитектуру** от естественного языка до оптимизированных JAX симуляций:

```
User Request (NL)
    ↓
Scientist (LLM + FSM Workflow)
    ↓
IR (PolicySurfaceIR v2.0 + Kernel Registry)
    ↓
Compilation (ProgramGraph + ExecPlan)
    ↓
Runtime (Fabric UDF + Foundry JAX Engine)
    ↓
Artifacts (CAS + Audit Trail + Evidence)
```

**Детальный поток данных:**
1. **User Request** → Scientist получает запрос на естественном языке
2. **LLM Processing** → Drafter генерирует PolicySurfaceIR через промпты и self-healing циклы
3. **Validation & Linking** → IR валидируется и линкуется с kernel registry (механизмы, слоты, метрики)
4. **Data Views Compilation** → Fabric компилирует UDF запросы для получения baseline состояния
5. **Policy Compilation** → Foundry компилирует PolicySurfaceIR в ProgramGraph и ExecPlan
6. **Simulation Execution** → JAX runtime исполняет политики с patch-based state management
7. **Analysis & Governance** → Governor оценивает результаты и принимает решения
8. **Artifact Persistence** → Runtime сохраняет все артефакты с provenance и audit trail

**Архитектурная метафора**: Policy Engine - это "компилятор политик", где LLM выступает frontend компилятором, IR - промежуточным представлением, Foundry - оптимизирующим бэкендом, а Fabric - runtime системой данных.

### Trinity архитектура IR v2.1.4

Система IR реализует **Trinity архитектуру v2.1.4** - разделение на три независимых артефакта, каждый из которых отвечает за отдельный аспект моделирования политики:

- **ProblemFrame ("Why")**: Определение проблемы, целей, KPI и ограничений (неизменен в рамках эксперимента)
- **PolicySpec ("What")**: Спецификация политики, интервенций и параметров (итерируется при оптимизации)
- **ModelSpec ("How")**: Конфигурация модели мира, агентов, данных и предположений (для sensitivity analysis)

**Trinity Bundle** обеспечивает типизированные ссылки на все три артефакта с валидацией совместимости. PolicySurfaceIR v2.x остается совместимым интерфейсом для обратной совместимости, с поддержкой автоматической миграции в Trinity формат. **Trinity Manifest** предоставляет полные метаданные эксперимента с полями для экспериментального названия, создателя, временных меток и заметок.

### Advanced Foundry Features (Расширенные возможности Foundry)

Современная архитектура включает специализированные компоненты для надежного и эффективного исполнения сложных симуляций:

- **Conflict Detection**: Compile-time анализатор для обнаружения конфликтов записи в слоты перед JAX-компиляцией
- **Cost Model**: Эвристическая модель оценки стоимости выполнения программ с самокалибровкой
- **NaN Guard**: Runtime обнаружение и диагностика NaN/Inf значений для numerical stability
- **Agent Simulation**: Комплексная симуляция поведенчески-гетерогенных агентов с ML, artifact system и environment fingerprinting

### Архитектурные законы (инварианты проекта)

Проект опирается на набор инвариантов. Часть из них формализована инструментами в `tools/`, часть — пока соглашения, поддерживаемые тестами и код‑ревью.

- **Закон A — Import Gate (границы модулей)**: `tools/lint_imports.py` запрещает критические обратные зависимости (`foundry → fabric`, `fabric → scientist`) и репортит циклы (по умолчанию не фейлит; `--fail-on-cycles` включает strict‑mode).
- **Закон B — Foundry как JAX‑ядро без прямого I/O**: `tools/lint_foundry.py` запрещает импорт I/O/DB/network библиотек и вызовы `print()`/`open()` в `polisyos.foundry`. As‑is: сейчас `src/polisyos/foundry/agents.py` является исключением (использует `os`/`pathlib` для загрузки артефактов), поэтому “чистое ядро” следует искать в `src/polisyos/foundry/runtime.py`, `src/polisyos/foundry/executor.py`, `src/polisyos/foundry/patch_vm.py`, `src/polisyos/foundry/calibration/pure_executor.py`, `src/polisyos/foundry/conflict_checker.py`, `src/polisyos/foundry/cost_model.py`, `src/polisyos/foundry/runtime/nan_guard.py`.
- **Закон C — контракты как источник истины**: структуры данных определены в `polisyos.ir` и `polisyos.core.contracts`, экспортируются в JSON Schema (`tools/gen_schema.py` → `policy_ir_schema.json`) и валидируются на границах.
- **Закон D — воспроизводимость и аудит прогонов**: каждый прогон имеет `run_id`, детерминированные seed’ы (Treasury), audit trail (`runs/<run_id>/audit.jsonl`) и воспроизводимые артефакты в CAS.
- **Закон E — evidence и provenance обязательны для данных**: `polisyos.fabric` фиксирует источники/трансформации (EvidenceBundle), а также immutable факты (Fact Log) с provenance/trust/legal метаданными.
- **Закон F — fidelity control**: симуляции/калибровки поддерживают управление точностью (speed/accuracy trade‑off) через `foundry.types.FidelityLevel` и multi‑fidelity механизмы.
- **Закон G — uncertainty quantification**: калибровка и trust‑подсистема возвращают bounds/оценки неопределённости (артефакты + отчёты).
- **Закон H — governance и бюджеты**: `polisyos.scientist` ограничивает вычисления и внешние вызовы (budgets), выполняет preflight/postflight и поддерживает human gates при необходимости.
- **Закон I — trust + privacy**: уровни доступа к данным (AccessTier), privacy passes в UDF компиляции, trust policies (two‑pass compare, uncertainty bounds).
- **Закон J — legal compliance**: политики должны соответствовать юридическим нормам через pluggable rule backends (NormPack, RuleType, LegalPass).
- **Закон K — quality gate enforcement**: данные должны проходить quality validation перед использованием в симуляциях (QualityIndicators, DataFitnessReport, QualityGatePass).

### Архитектурные слои и зависимости

Policy Engine следует строгому **принципу направленных зависимостей** (Закон A), где граф импортов идет только "внутрь" архитектуры. Это обеспечивается автоматизированными проверками через `tools/lint_imports.py`.

#### Архитектурные границы (Import Gate)

**Запрещенные обратные зависимости:**
- `foundry` ↛ `fabric` (математическое ядро не зависит от data layer)
- `fabric` ↛ `scientist` (data layer не зависит от orchestration/LLM)
- Циклические зависимости между любыми модулями

**Разрешенные потоки зависимостей:**
```
scientist → ir, fabric, foundry, runtime, core, common  # orchestration использует все
fabric → ir, core, common                              # data layer зависит от типов и инфраструктуры
foundry → ir, core, common                             # математическое ядро использует только типы
runtime → ir, core, common                             # runtime использует контракты и инфраструктуру
ir → core, common                                      # IR зависит от инфраструктуры сериализации
core → common                                          # инфраструктура зависит от базовых утилит
common → (никого)                                      # фундаментальные утилиты автономны
```

#### Детальная карта зависимостей

```
┌─────────────────────────────────────────────────────────────────┐
│                    scientist (верхний уровень)                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ orchestrator, agent, kernel, compute, doe, governance      │ │
│  └─────────────────────┬───────────────────────────────────────┘ │
│                        │ (зависит от)                            │
└────────────────────────┼─────────────────────────────────────────┘
                         │
┌────────────────────────┼─────────────────────────────────────────┐
│         runtime        │          fabric           foundry       │
│  ┌─────────────────────┼─────┐  ┌────────────┐  ┌─────────────┐  │
│  │ api, manifest,      │     │  │ ingestion, │  │ compiler,   │  │
│  │ artifacts, audit    │     │  │ udf,       │  │ runtime,    │  │
│  │                     │     │  │ evidence,  │  │ domain,     │  │
│  └─────────────────────┼─────┘  │ trust      │  │ mechanism,  │  │
│                        │        └────────────┘  │ calibration │  │
└────────────────────────┼─────────────┼──────────┼─────────────┘
                         │             │          │
┌────────────────────────┼─────────────┼──────────┼─────────────┐
│           ir           │             │          │             │
│  ┌─────────────────────┼─────────────┼──────────┼─────────────┐ │
│  │ surface, kernel,    │             │          │             │ │
│  │ linker, data_views, │             │          │             │ │
│  │ fact_log, loaders   │             │          │             │ │
│  └─────────────────────┼─────────────┼──────────┼─────────────┘ │
│                        │             │          │             │
└────────────────────────┼─────────────┼──────────┼─────────────┘
                         │             │          │
┌────────────────────────┼─────────────┼──────────┼─────────────┐
│          core          │             │          │             │
│  ┌─────────────────────┼─────────────┼──────────┼─────────────┐ │
│  │ artifacts, canon,   │             │          │             │ │
│  │ contracts, trace,   │             │          │             │ │
│  │ run, registry       │             │          │             │ │
│  └─────────────────────┼─────────────┼──────────┼─────────────┘ │
│                        │             │          │             │
└────────────────────────┼─────────────┼──────────┼─────────────┘
                         │             │          │
┌────────────────────────┴─────────────┴──────────┴─────────────┐
│                       common                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ config, logger, migrations, jax_env                       │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**Принципиальные различия между `common` и `core`:**
- `common`: Фундаментальные утилиты (config, logger, migrations) - используется всеми модулями
- `core`: Инфраструктура артефактов (CAS, contracts, trace) - фундамент для runtime операций

### Язык и вычисления
- **Python 3.11+**: базовый рантайм проекта с полной поддержкой type hints
- **JAX 0.4.x+**: численные вычисления, JIT-компиляция и автоматическое дифференцирование
- **JAXlib**: низкоуровневые примитивы для JAX (CPU/GPU/TPU поддержка)
- **JAX Metal**: опциональный backend для Apple Silicon (macOS M1/M2/M3)
- **Agent Simulation**: Комплексная симуляция агентов с ML, artifact system и environment fingerprinting
- **Equinox**: объектно-ориентированная обертка для JAX-модулей
- **Optax**: градиентная оптимизация и калибровка параметров
- **Jaxtyping**: статическая типизация форм массивов JAX
- **Chex**: дополнительные проверки и утилиты для JAX кода

### Data Layer (Unified Data Fabric)
- **DuckDB 0.9.x+**: встраиваемая аналитическая БД для временных рядов и OLAP запросов
- **Kùzu 0.0.x+**: встраиваемая графовая БД для моделирования взаимодействий агентов
- **PyArrow 10.x+**: эффективная передача и обработка columnar данных с high-performance processing
- **pandas**: ETL трансформации и анализ данных
- **Parquet**: columnar storage формат для больших датасетов
- **Pydantic v2**: строгие схемы данных и валидация
- **W3C PROV-O**: стандартизированная система provenance tracking с entities, activities и agents
- **Data Contract Catalog**: Metric-level система контрактов для type safety с hash-locked bindings
- **Quality Indicators System**: Многофакторная оценка качества данных (missingness, staleness, coverage, outliers)
- **Fact Log System**: Immutable факты с provenance tracking и детерминированные ID

### IR & Contracts (Промежуточное представление)
- **Pydantic v2**: строгие контракты и валидация структур данных
- **JSON Schema**: автоматический экспорт схем для внешних интеграций
- **difflib**: генерация отчетов об изменениях при валидации
- **Canonical JSON**: детерминированная сериализация для reproducible хешей и content addressing
- **Trinity Contracts**: типизированные ссылки на ProblemFrame/PolicySpec/ModelSpec артефакты
- **Legal Contracts**: стабильные контракты для legal validation subsystem (NormPack, NormRule, RuleType)
- **Patch-based Contracts**: UpdateOp, Merge Rules и state management (SUM/OVERRIDE/PRIORITY/ERROR)

### Scientist & AI (Интеллектуальное ядро)
- **LangGraph**: декларативный workflow с конечными автоматами состояний и 9 фазами
- **LangChain**: интеграция с LLM провайдерами (OpenAI, Anthropic, локальные модели)
- **MockLLM**: локальный LLM-адаптер для тестирования без API ключей
- **PyMOO 0.6.x+**: многокритериальная оптимизация (NSGA-II, genetic algorithms)
- **Hierarchical Agent System**: PI → Drafter → Formalizer → Critic с протоколами и runtime поведением
- **Self-Healing Agents**: Reflexion system с FailureCard recovery, ShortTermMemory и intelligent routing с backoff logic
- **Multi-Agent Workflow**: Интегрированная система с critique-based refinement, convergence tracking и memory persistence
- **Legal Validation System**: Pluggable backends для оценки юридических норм с protocol-based architecture

### Runtime & Infrastructure
- **Loguru**: структурированное логирование с JSON сериализацией
- **python-dotenv**: загрузка переменных окружения из `.env` файлов
- **FileSystemCAS**: content-addressable storage с SHA256 addressing
- **hashlib**: контроль целостности данных и детерминированные ID
- **Run Manifest**: паспорт эксперимента с метаданными, бюджетами и артефактами
- **Audit Trail**: JSON Lines логирование всех операций с provenance tracking
- **Environment Manifest**: захват окружения с compatibility scoring и risk assessment
- **Job Specifications**: structured execution с reproducible hashing и distributed backends
- **Decision Packet**: полный артефакт с evidence, uncertainty и provenance tracking

### Quality & Development Tools
- **Ruff**: быстрый линтер и форматер (замена Black + Flake8 + Isort + PyUpgrade)
- **MyPy**: строгая статическая типизация с постепенным внедрением
- **Pytest**: unit/integration/contract тесты с расширенными fixtures и категориями
- **Pre-commit**: git hooks для quality gates (dev зависимости)
- **JupyterLab + Matplotlib + Seaborn + Plotly**: исследовательская визуализация и ноутбуки
- **Quality Indicators**: автоматическая оценка качества данных (missingness, staleness, coverage)
- **Data Fitness Reports**: человекочитаемые отчеты о пригодности данных
- **Legal Validation Tools**: pluggable backends для оценки юридических норм

### Новые компоненты (после крупных изменений)

#### 🏗️ Архитектурная эволюция
- **Trinity Architecture v2.1.4**: Разделение IR на ProblemFrame ("Why"), PolicySpec ("What"), ModelSpec ("How") с типизированными TrinityBundle ссылками и TrinityManifest для метаданных экспериментов
- **W3C PROV-O Integration**: Стандартизированная система provenance tracking с entities, activities и agents
- **Legal Validation System**: Pluggable backends для оценки юридических норм (NormPack, RuleBackend, RuleType)
- **Quality Gate Enforcement**: Автоматическая валидация качества данных перед симуляциями (QualityIndicators, DataFitnessReport, QualityGatePass)
- **Enhanced Environment Manifest**: Захват окружения с compatibility scoring, risk assessment и fingerprinting для reproducible симуляций

#### 🤖 AI & Agent Systems
- **Hierarchical Agent System**: PI декомпозиция → Drafter генерация → Formalizer трансформация → Critic валидация
- **Self-Healing Agents**: Reflexion system с FailureCard recovery, ShortTermMemory и intelligent routing с backoff logic
- **Multi-Agent Workflow**: Интегрированная система агентов с critique-based refinement, convergence tracking и memory persistence
- **Agent Protocols**: Стандартизированные интерфейсы для PI/Drafter/Formalizer/Critic агентов с runtime поведением
- **Agent Artifacts**: Artifact system для политик агентов с environment fingerprinting и hot-swap compatibility

#### 📊 Data Management & Quality
- **Data Contract Catalog**: Metric-level система контрактов для type safety с hash-locked bindings, metric search и disambiguation
- **Quality Indicators System**: Многофакторная оценка качества данных (missingness, staleness, coverage, schema drift, outliers) с configurable thresholds
- **Data Fitness Reports**: Человекочитаемые отчеты о пригодности данных с human-readable summaries и quality gate integration
- **Fact Log System**: Immutable факты с provenance tracking и детерминированные ID
- **Materializer Engine**: Incremental материализация реляционных представлений из Fact Log с consistency guarantees
- **Evidence Bundles**: Криптографически verifiable доказательства происхождения данных с ingestion pipeline integration

#### 🔐 Trust & Evidence
- **Evidence Bundles**: Криптографически verifiable доказательства происхождения данных
- **Trust System**: Statistical verification с two-pass comparison и uncertainty bounds
- **Provenance Tracking**: W3C PROV-O compliant система с entities, activities и agents
- **Evidence-Enhanced Fabric**: Полная интеграция evidence в data pipeline с cryptographic verification

#### ⚡ Simulation & Execution
- **Multi-Fidelity Simulation**: Fluid/relaxed/hard уровни точности с fidelity control
- **Patch-based Execution**: UpdateOp и Merge Rules (SUM/OVERRIDE/PRIORITY/ERROR) для state management с artifact-based патчами
- **Agent Simulation**: Пошаговая симуляция с ML моделями, социальными связями, демографией и artifact system
- **Plugin System**: Capability-based registry с composite executors для domain extensions
- **Calibration MVP**: Полная система калибровки с Hessian uncertainty quantification и merge determinism
- **Conflict Detection**: Compile-time анализатор для обнаружения конфликтов записи в слоты перед JAX-компиляцией
- **Cost Model**: Эвристическая модель оценки стоимости выполнения программ с самокалибровкой
- **NaN Guard**: Runtime обнаружение и диагностика NaN/Inf значений для numerical stability

#### 🎯 Governance & Compliance
- **Budget Controls**: Compute/Evidence/Legitimacy/Complexity бюджеты с runtime enforcement
- **Human Gates**: Асинхронная система GateRequest/GateDecision для approvals
- **FSM Orchestration**: Конечный автомат состояний с 9 фазами и self-healing cycles
- **Governance Pipeline**: Модульная система validation passes с telemetry и tracing
- **Validation Profiles**: Fast/mvp/strict профили валидации с configurable passes
- **Legal Compliance Passes**: Модульная валидация политик против нормативных требований
- **Decision Card System**: Детерминированные human-readable summaries результатов экспериментов с verdict/confidence, key metrics и issues summary
- **Run Timeline Tracking**: Event-based tracking системы для runs с phase/node durations, artifact creation и performance metrics для observability
- **Decision Packet v2**: Обновленная версия decision packet с timeline integration и on-demand decision card generation

#### 🔧 Infrastructure & Runtime
- **Enhanced Environment Manifest**: Захват окружения с compatibility scoring, risk assessment и fingerprinting
- **Treasury System**: Детерминированное RNG управление для reproducible симуляций
- **Runtime API**: Жизненный цикл прогонов с portable artifacts и audit trail
- **Job Specifications**: Structured execution с reproducible hashing и distributed backends
- **Design of Experiments**: ScenarioSweep, AblationPlan, SensitivityPlan для systematic research
- **Decision Packet**: Полный артефакт с evidence, uncertainty и provenance tracking

#### 🛠️ Development Tools
- **UDF Compilation Pipeline**: Безопасная компиляция SQL/Cypher запросов с whitelist и privacy passes
- **Enhanced Kernel Registries**: Расширенная система фундаментальных реестров (механизмы, слоты, units, trust policies)
- **Enhanced Monitoring**: Метрики, трекинг экспериментов и визуализация для agent simulation
- **Failure Card System**: Структурированные артефакты ошибок с recovery mechanisms
- **Agent Artifacts**: Artifact system для политик агентов с environment fingerprinting и hot-swap compatibility
- **Merge Determinism**: Детерминированные операции merge и state consistency для reproducible симуляций
- **Quality Indicators System**: Многофакторная оценка качества данных (missingness, staleness, coverage, outliers)
- **Fitness Reports**: Человекочитаемые отчеты о пригодности данных с configurable thresholds
- **Conflict Detection**: Compile-time валидация программных графов на предмет конфликтов с merge rules
- **Cost Model**: Оценка стоимости выполнения с budget constraints и telemetry-based calibration
- **NaN Guard**: Runtime monitoring численной стабильности с diagnostics и cause detection

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
├── pyproject.toml / uv.lock          # Зависимости проекта и конфигурация сборки
├── README.md                         # Эта документация
├── env_example.txt                   # Шаблон переменных окружения
├── install.sh                        # Скрипт автоматической установки
├── policy_ir_schema.json             # JSON Schema для PolicySurfaceIR (генерируется)
├── .env                              # API ключи и конфигурация окружения (не в Git!)
├── .polisyos/                        # Content-Addressable Storage (CAS) для артефактов
│   └── artifacts/sha256/...          # SHA256-addressed артефакты (blobs, manifests)
├── data/                             # Data pipeline директории
│   ├── raw/                          # Исходные CSV файлы и датасеты
│   ├── staging/                      # Промежуточные Parquet файлы после ETL
│   ├── curated/                      # Финальные обработанные данные
│   │   ├── *.duckdb                  # Аналитические БД (DuckDB)
│   │   ├── *.kuzu                    # Графовые БД (Kùzu)
│   │   ├── fact_log/                 # Immutable факты с provenance
│   │   ├── udf_schema.json           # Конфигурация UDF whitelist и access tiers
│   │   └── manifests/                # Dataset manifests с метаданными качества
│   └── manifests/                    # Глобальные манифесты датасетов
├── logs/                             # Структурированные логи (JSON Lines)
├── runs/                             # Runtime результаты экспериментов
│   └── <run_id>/                     # Каждая директория - отдельный эксперимент
│       ├── manifest.json             # RunManifest с метаданными и артефактами
│       ├── audit.jsonl               # Полный audit trail всех операций
│       └── artifacts/                # Структурированные результаты
│           ├── policy_ir/            # IR политики и конфигурации
│           ├── simulation_results/   # Метрики и результаты симуляции
│           ├── data_views/           # Результаты UDF запросов
│           └── registry_bundle/      # Registry bundles для воспроизводимости
├── src/polisyos/                     # Исходный код модулей системы
│   ├── common/                       # Фундаментальные утилиты (без зависимостей)
│   │   ├── config.py                 # JAX setup, hardware safeguards, logging
│   │   ├── logger.py                 # Структурированное логирование через Loguru
│   │   ├── jax_env.py                # Безопасная настройка JAX backend для macOS
│   │   └── migrations/               # Детерминированные миграции схем
│   ├── core/                         # Инфраструктура артефактов и контрактов
│   │   ├── artifacts/                # Content-Addressable Storage (CAS) + Environment Manifest
│   │   │   ├── ids.py                # ArtifactID с SHA256 хешированием
│   │   │   ├── manifest.py           # ArtifactManifest, ArtifactRef, ProducerInfo
│   │   │   ├── environment.py        # EnvironmentManifest с compatibility scoring
│   │   │   ├── registry.py           # RegistryBundle для компонентов системы
│   │   │   └── store.py              # FileSystemCAS, PutOptions, VerificationReport
│   │   ├── canon/                    # Каноническая JSON сериализация
│   │   │   └── canon_json.py         # CanonSpec, to_canonical_bytes, deterministic хеши
│   │   ├── compiler/                 # Отчеты компиляции и линковки
│   │   │   └── report.py             # CompileReport, put_compile_report, put_link_report
│   │   ├── contracts/                # Контракты между модулями системы
│   │   │   ├── compiler.py           # CompileReportRef, LinkReportRef
│   │   │   ├── fabric.py             # FabricResult, EvidenceBundle, UncertaintyBounds
│   │   │   ├── foundry.py            # ProgramGraph, ExecPlan, StateDelta, TreasurySeed, PatchOp, UpdateOp
│   │   │   ├── scientist.py          # FailureCardRef, PolicyIRRef, CritiqueRef
│   │   │   ├── trinity.py            # TrinityBundle, ProblemFrameRef, PolicySpecRef, ModelSpecRef
│   │   │   └── legal.py              # Legal contracts (NormPack, NormRule, RuleType, RuleBackend)
│   │   ├── registry/                 # Сборка и загрузка реестров компонентов
│   │   │   ├── builder.py            # build_default_registry_bundle, build_registry_bundle
│   │   │   └── loader.py             # load_registry_bundle_content, load_registry_bundle_payload
│   │   ├── run/                      # Контексты и манифесты выполнения
│   │   │   ├── context.py            # RunContext с трассировкой
│   │   │   └── manifest.py           # RunManifest с метаданными прогонов
│   │   └── trace/                    # Распределенная система трассировки
│   │       ├── record.py             # TraceRecord с временными метками
│   │       └── sink.py               # TraceSink, JsonlTraceSink для логирования
│   ├── ir/                           # Intermediate Representation (Trinity контракты)
│   │   ├── trinity.py                # Trinity артефакты: ProblemFrame, PolicySpec, ModelSpec
│   │   ├── problem_frame.py          # ProblemFrame: определение проблемы и целей
│   │   ├── policy_spec.py            # PolicySpec: спецификация политики и интервенций
│   │   ├── model_spec.py             # ModelSpec: конфигурация модели мира
│   │   ├── surface.py                # PolicySurfaceIR v2.0 (совместимый интерфейс)
│   │   ├── kernel/                   # Фундаментальные реестры (механизмы, слоты, units, trust policies)
│   │   ├── data_views.py             # Запросы данных (PANEL/SNAPSHOT/NETWORK)
│   │   ├── linker.py                 # Валидация и линковка политик
│   │   ├── fact_log.py               # Immutable факты с provenance
│   │   ├── loaders.py                # Универсальная загрузка политик с автораспознаванием
│   │   ├── calibration.py            # Контракты калибровки параметров
│   │   ├── norm_pack.py              # Структурированные представления юридических норм
│   │   └── migrations/               # Миграции между версиями IR
│   ├── fabric/                       # Unified Data Fabric (данные + evidence + quality)
│   │   ├── catalog/                  # Metric-level data contract catalog
│   │   │   ├── binding.py            # MetricBinding - hash-locked ссылки на метрики
│   │   │   ├── contract.py           # DataContract модели (DataContract, DataContractCollection)
│   │   │   ├── registry.py           # DataContractRegistry - реестр контрактов с валидацией
│   │   │   ├── search.py             # MetricSearcher - поиск метрик с disambiguation
│   │   │   └── validate.py           # Валидация контрактов (load_contract_collection)
│   │   ├── ingestion.py              # ETL pipeline (CSV → DuckDB + Kùzu)
│   │   ├── schema.py                 # Pydantic модели данных (AgentRow, InteractionRow, MacroRow)
│   │   ├── manifest.py               # Метаданные и качество данных (DatasetManifest, QualityMetrics)
│   │   ├── registry.py               # Управление манифестами датасетов (ManifestRegistry)
│   │   ├── config.py                 # Правила нормализации и reconciliation
│   │   ├── evidence.py               # Криптографически verifiable evidence bundles
│   │   ├── materializer.py           # Incremental материализация из Fact Log
│   │   ├── segment_manifest.py       # Управление сегментами Fact Log
│   │   ├── fact_writer.py            # Запись фактов в каноническом формате
│   │   ├── trust.py                  # Политики доверия с statistical verification
│   │   ├── quality.py                # Система оценки качества данных (QualityIndicators, QualityLevel)
│   │   ├── fitness_report.py         # Отчеты о пригодности данных (DataFitnessReport, MetricFitness)
│   │   ├── provenance/               # W3C PROV-O provenance tracking система
│   │   │   ├── core.py               # Базовые модели provenance (Entity/Activity/Agent)
│   │   │   └── export_provo.py       # Экспорт в W3C PROV-O JSON-LD/N-Quads форматы
│   │   ├── io/                       # Интерфейсы хранения (DuckDB, Kùzu)
│   │   └── udf/                      # Unified Data Fabric - безопасный слой запросов
│   ├── foundry/                      # JAX математическое ядро (симуляция)
│   │   ├── __init__.py               # Пустой инициализатор
│   │   ├── base.py                   # Абстрактный класс Mechanism и ComplexMechanism
│   │   ├── types.py                  # FidelityLevel enum (уровни точности)
│   │   ├── utils.py                  # Дифференцируемые утилиты (soft_step, soft_clamp, gradient_health)
│   │   ├── loss.py                   # Функции потерь для оптимизации политик
│   │   ├── agent_metrics.py          # Метрики для анализа агентов
│   │   ├── compiler.py               # Компиляция IR в ProgramGraph + ExecPlan
│   │   ├── layout.py                 # Slot layout для state management
│   │   ├── treasury.py               # Deterministic RNG management
│   │   ├── patch_vm.py               # Patch-based виртуальная машина и merge rules
│   │   ├── runtime/                  # Runtime модули для исполнения программ
│   │   │   ├── __init__.py           # Чистые JAX функции для исполнения (step, run_scan, execute_program_batch)
│   │   │   └── fingerprint.py        # Environment fingerprinting для воспроизводимости
│   │   ├── executor.py               # Исполнение программ с constraints и state management
│   │   ├── constraints_engine.py     # Движок ограничений и валидации
│   │   ├── trace.py                  # Система трассировки исполнения
│   │   ├── merge_engine.py           # Движок для слияния патчей и состояний
│   │   ├── domain/                   # Экономическая модель (GlobalState, AgentState)
│   │   ├── agents.py                 # Адаптивные агенты с нейронными сетями (AdaptiveAgentMechanism)
│   │   ├── base.py                   # Абстрактный класс Mechanism и ComplexMechanism
│   │   ├── fiscal.py                 # Налоговые механизмы (IncomeTax, TaxSubsidy)
│   │   ├── labor.py                  # Механизм рынка труда (LaborMarketMechanism)
│   │   ├── queue.py                  # Механизм очередей с multi-fidelity (QueueMechanism)
│   │   ├── registry.py               # Регистрация и фабрика механизмов
│   │   ├── specs.py                  # Спецификации механизмов с валидацией
│   │   ├── agent_sim/                # Комплексная симуляция агентов с ML
│   │   │   ├── __init__.py
│   │   │   ├── actor_critic.py       # Actor-Critic архитектуры для RL
│   │   │   ├── analysis.py           # Анализ поведения агентов
│   │   │   ├── credit_assignment.py  # Назначение кредитов в обучении
│   │   │   ├── dashboard.py          # Дашборд для мониторинга
│   │   │   ├── demographics.py       # Демографические метрики
│   │   │   ├── distribution_executor.py # Исполнение распределений
│   │   │   ├── distribution_mechanisms.py # Механизмы распределения
│   │   │   ├── distributions.py      # Метрики неравенства (Gini, Palma ratio)
│   │   │   ├── evolution.py          # Эволюционные алгоритмы (CMA-ES)
│   │   │   ├── executor.py           # Исполнитель для симуляции агентов
│   │   │   ├── experiment.py         # Настройка экспериментов
│   │   │   ├── government_policy.py  # Политики правительства
│   │   │   ├── graph_executor.py     # Исполнение на графах
│   │   │   ├── graph_mechanisms.py   # Механизмы для графов
│   │   │   ├── graph_observations.py # Наблюдения на графах
│   │   │   ├── graphs.py             # Графовые структуры социальных связей
│   │   │   ├── jit_training.py       # JIT-компиляция обучения
│   │   │   ├── mechanism.py          # Базовые механизмы симуляции
│   │   │   ├── mechanisms.py         # Специфические механизмы
│   │   │   ├── artifact.py           # Artifact system для политик агентов
│   │   │   ├── metrics.py            # Сбор метрик обучения
│   │   │   ├── modes.py              # Режимы обучения (bilevel, MPC)
│   │   │   ├── mpc.py                # Model Predictive Control
│   │   │   ├── policy.py             # Политики агентов
│   │   │   ├── population_executor.py # Исполнение для популяции
│   │   │   ├── population_mechanisms.py # Механизмы популяции
│   │   │   ├── population.py         # Управление популяцией
│   │   │   ├── prng.py               # Генерация псевдослучайных чисел
│   │   │   ├── README.md             # Документация симуляции агентов
│   │   │   ├── rewards.py            # Функции вознаграждения
│   │   │   ├── rl.py                 # PPO и другие алгоритмы обучения
│   │   │   ├── state.py              # Расширенные состояния агентов
│   │   │   ├── temporal_executor.py  # Временное исполнение
│   │   │   ├── temporal_mechanisms.py # Временные механизмы
│   │   │   ├── temporal.py           # Временные аспекты
│   │   │   ├── training.py           # Обучение моделей
│   │   │   └── visualization.py      # Визуализация результатов
│   │   ├── calibration/              # Калибровка моделей
│   │   │   ├── __init__.py           # Инициализатор калибровки
│   │   │   ├── bijectors.py          # Биекции для ограничения параметров (sigmoid, softplus)
│   │   │   ├── calibrator.py         # Основной класс Calibrator для оптимизации параметров
│   │   │   ├── loss.py               # Функции потерь (MSE, Huber, weighted loss)
│   │   │   ├── preflight.py          # Подготовка данных и конфигурации для калибровки
│   │   │   ├── pure_executor.py      # Чистый JAX executor для калибровки (без side effects)
│   │   │   └── report.py             # Отчёты калибровки (метрики качества, неопределённости)
│   │   └── plugins/                  # Плагины доменов
│   │       ├── __init__.py           # Инициализатор плагинов
│   │       ├── api.py                # High-level PolisySimulator API
│   │       ├── cli.py                # Command-line interface
│   │       ├── composite.py          # Мульти-доменные симуляции
│   │       ├── core.py               # Протоколы плагинов и реестр
│   │       ├── discovery.py          # Автообнаружение плагинов
│   │       ├── economics/            # Экономический домен
│   │       │   ├── __init__.py
│   │       │   ├── mechanisms.py     # Экономические механизмы
│   │       │   ├── objectives.py     # Целевые функции (GDP, Gini, etc.)
│   │       │   ├── plugin.py         # EconomicsPlugin с механизмами
│   │       │   ├── rewards.py        # Функции вознаграждения
│   │       │   └── state.py          # Состояние экономического домена
│   │       └── README.md             # Документация плагинов
│   ├── scientist/                    # AI оркестрация экспериментов
│   │   ├── agent/                    # Иерархическая система агентов + Self-Healing
│   │   │   ├── protocols.py          # AgentRole, ProblemFrame, SubTask, CritiqueReport
│   │   │   ├── failure_card.py       # FailureCard system для обработки ошибок
│   │   │   ├── memory.py             # ShortTermMemory для conversation tracking
│   │   │   ├── reflexion.py          # ReflexionOrchestrator с intelligent routing
│   │   │   ├── pi.py                 # Principal Investigator agent
│   │   │   ├── drafter.py            # Drafter agent для генерации политик
│   │   │   ├── formalizer.py         # Formalizer agent для IR трансформации
│   │   │   ├── critic.py             # Critic agent для валидации
│   │   │   ├── prompts.py            # Системные промпты для агентов
│   │   │   └── __init__.py           # Экспорт агентов и протоколов
│   │   ├── kernel/                   # FSM, бюджеты, guards, human gates
│   │   │   ├── budgets.py            # ComputeBudget, EvidenceBudget, LegitimacyBudget, ComplexityBudget
│   │   │   ├── fsm.py                # Phase enum, KernelState, ALLOWED_TRANSITIONS
│   │   │   ├── guards.py             # Проверки переходов между состояниями
│   │   │   ├── human_gate.py         # GateRequest, GateDecision система
│   │   │   └── __init__.py           # Экспорт kernel компонентов
│   │   ├── compute/                  # Спецификации задач и execution backends
│   │   │   ├── job_spec.py           # JobSpec, JobKey, JobResult с reproducible hashing
│   │   │   ├── runner.py             # LocalBackend, RayBackend для distributed execution
│   │   │   └── __init__.py           # Экспорт compute компонентов
│   │   ├── doe/                      # Design of Experiments
│   │   │   └── designs.py            # ScenarioSweep, AblationPlan, SensitivityPlan
│   │   ├── governance/               # Preflight/postflight проверки + validation pipeline
│   │   │   ├── legal/                # Legal compliance validation backends
│   │   │   ├── passes/               # Модульные проверки (budget, safety, privacy, schema, legal, quality)
│   │   │   │   ├── budget_pass.py    # Контроль бюджетов (compute, evidence, legitimacy, complexity)
│   │   │   │   ├── safety_pass.py    # Проверка безопасности механизмов и селекторов
│   │   │   │   ├── privacy_pass.py   # Контроль приватности (PII tiers, access control)
│   │   │   │   ├── schema_pass.py    # Валидация структуры IR и PolicySurfaceIR compliance
│   │   │   │   ├── legal_pass.py     # Проверка соответствия политик юридическим нормам
│   │   │   │   ├── quality_gate_pass.py # Валидация качества данных перед симуляцией
│   │   │   │   └── base.py           # Базовые классы ValidatorPass, PassContext, ComplianceIssue
│   │   │   ├── pipeline.py           # Orchestrator for validation passes с short-circuit логикой
│   │   │   ├── profiles.py           # Validation profiles (fast/mvp/strict)
│   │   │   ├── telemetry.py          # Validation tracing и metrics
│   │   │   ├── preflight.py          # Предварительные проверки безопасности
│   │   │   ├── postflight.py         # Пост-запусковые проверки результатов
│   │   │   └── __init__.py           # Экспорт governance компонентов
│   │   ├── orchestrator/             # LangGraph workflow с 9 фазами
│   │   │   ├── workflow.py           # Основной граф состояний LangGraph
│   │   │   ├── state.py              # ExperimentState с 90+ полями
│   │   │   ├── flow_nodes.py         # Реализации всех узлов workflow (1450+ строк)
│   │   │   ├── decision_packet.py    # DecisionPacket с evidence и uncertainty
│   │   │   ├── run_record.py         # RunRecord для воспроизводимости
│   │   │   ├── audit.py              # Комплексная система аудита
│   │   │   ├── data_loader.py        # Загрузка данных из Fabric layer
│   │   │   └── __init__.py           # Экспорт orchestrator компонентов
│   │   └── publisher.py              # Финализация результатов в DecisionPacket
│   └── runtime/                      # Управление жизненным циклом экспериментов
│       ├── api.py                    # start_run, finalize_run, log_artifact
│       ├── manifest.py               # RunManifest, ArtifactRef с переносимыми путями
│       └── README.md                 # Подробная документация runtime API
├── tests/                            # Тестовая инфраструктура
│   ├── conftest.py                   # Конфигурация pytest и JAX setup
│   ├── contract/                     # Тесты контрактов IR (валидация схем, Trinity, миграции)
│   │   ├── test_ir_contract.py       # PolicySurfaceIR, селекторы, валидация, TranslatableString
│   │   ├── test_ir_migrations.py     # Миграции схем IR между версиями
│   │   ├── test_trinity_contracts.py # Trinity артефакты: ProblemFrame, PolicySpec, ModelSpec
│   │   ├── test_trinity_migration.py # Миграция между Surface IR и Trinity форматами
│   │   ├── test_fabric_gates.py      # Входные фильтры и предусловия Fabric layer
│   │   ├── test_kernel_models.py     # Валидация моделей ядра IR (slots, units, merge rules, time semantics)
│   │   └── test_surface_ir.py        # Surface IR, линкер, semantic fingerprinting, validation reports
│   ├── core_phase0/                  # Тесты фундаментальных компонентов core (Phase 0)
│   │   ├── conftest.py               # Специфичная конфигурация для core тестов
│   │   ├── test_artifact_store.py    # FileSystemCAS, дедупликация, верификация integrity
│   │   ├── test_canon_json.py        # Каноническая JSON сериализация, детерминированные хэши
│   │   ├── test_environment_manifest.py # Захват и сравнение environment манифестов
│   │   ├── test_registry_bundle.py   # Сборка и загрузка registry bundles
│   │   └── test_run_context.py       # Контекст выполнения и артефакты producer'а
│   ├── demos/                        # Демо-тесты для проверки функциональности
│   │   └── run_laffer_demo.py        # Тест запуска демо Laffer curve из tools/demos/
│   ├── fabric/                       # Тесты компонентов Fabric layer
│   │   ├── test_data_catalog.py      # Data Contract catalog system, contract validation, metric bindings, search
│   │   ├── test_evidence_bundle.py   # Evidence bundles, ingestion pipeline, provenance tracking
│   │   ├── test_provenance.py        # Provenance subsystem, entities, graphs, PROV-O export, persistence
│   │   ├── test_trust_two_pass.py    # Trust system, uncertainty bounds, двухпроходное сравнение
│   │   └── test_quality_indicators.py # Quality indicators system, fitness reports, quality gate pass integration
│   ├── foundry/                      # Тесты симуляционных компонентов JAX-ядра
│   │   ├── agent_sim/                # Тесты симуляции агентов
│   │   │   └── test_monitoring.py    # MetricsCollector, ExperimentTracker, DashboardGenerator, визуализация
│   │   ├── plugins/                  # Тесты плагинной системы Foundry
│   │   │   └── test_plugin_system.py # PluginRegistry, CompositeExecutor, EconomicsPlugin, domain configs
│   │   ├── test_adaptive_agents.py   # Адаптивные агенты и их поведение
│   │   ├── test_agent_artifact.py    # AgentPolicyArtifact, EnvironmentFingerprint, hot-swap compatibility
│   │   ├── test_agent_simulation_step1.py # Шаг 1 симуляции агентов
│   │   ├── test_agent_simulation_step2.py # Шаг 2 симуляции агентов
│   │   ├── test_agent_simulation_step3.py # Шаг 3 симуляции агентов
│   │   ├── test_agent_simulation_step4.py # Шаг 4 симуляции агентов
│   │   ├── test_agent_simulation_step5.py # Шаг 5 симуляции агентов
│   │   ├── test_agent_simulation_step6.py # Шаг 6 симуляции агентов
│   │   ├── test_calibrator_fidelity.py # Управление fidelity уровнями (fluid/relaxed/hard/temperature)
│   │   ├── test_calibrator_mvp.py    # Полноценная калибровка параметров с оптимизацией
│   │   ├── test_constraints_executor.py # Исполнение ограничений (budget guards, validation)
│   │   ├── test_fiscal.py            # Фискальные механизмы (налоги, субсидии)
│   │   ├── test_global_state.py      # Глобальное состояние симуляции и его эволюция
│   │   ├── test_gradients.py         # Градиенты политик (JAX autodiff, Equinox)
│   │   ├── test_health.py            # Проверки здоровья системы и детекция аномалий
│   │   ├── test_jit_stability.py     # JIT-стабильность PyTree структур
│   │   ├── test_merge_determinism.py # Детерминизм операций merge и state consistency
│   │   ├── test_patch_executor.py    # Patch executor, state delta и snapshot'ы
│   │   ├── test_program_graph_ops.py # Операции с программными графами, execution order
│   │   └── test_runtime_batch.py     # Пакетное выполнение программ с JAX
│   ├── integration/                  # Интеграционные тесты end-to-end сценариев
│   │   ├── test_calibration_udf.py   # Калибровка параметров с UDF движком и историческими данными
│   │   ├── test_workflow_smoke.py    # Полный smoke-test pipeline (draft → simulate → governor → decision)
│   │   └── test_workflow_llm.py      # Интеграция с LLM компонентами и языковыми моделями
│   ├── ir/                           # Тесты компонентов IR layer
│   │   └── test_loaders.py           # Загрузчики политик из различных форматов, norm_pack структуры
│   ├── runtime/                      # Тесты runtime компонентов
│   │   └── test_runtime_manifest_paths.py # Управление runs, артефакты, пути
│   └── scientist/                    # Тесты компонентов scientist
│       ├── governance/               # Тесты governance layer (validation pipeline, legal compliance)
│       │   ├── test_legal_pass.py    # LegalPass, RuleBackend, NormPack validation
│       │   └── test_validation_pipeline.py # ValidationPipeline, profiles, compliance issues
│       ├── test_agent_protocols.py   # Протоколы агентов: PI, Drafter, Formalizer, Critic
│       ├── test_compiler.py          # Компилятор политик из IR
│       ├── test_multi_agent_workflow.py # Multi-agent workflow с critique system и памятью
│       └── test_reflexion_loop.py    # Reflexion loop, failure cards, recovery mechanisms
└── tools/                            # Инструменты разработчика и демонстрации
    ├── benchmarks/                   # Бенчмарки производительности (JAX, симуляции)
    ├── demos/                        # Демонстрационные скрипты возможностей
    ├── diagnostics/                  # Диагностика системы (check_setup, perf analysis)
    ├── capture_env.py                # Захват и сравнение Environment Manifest
    ├── gen_schema.py                 # Генерация JSON Schema из Pydantic
    ├── lint_imports.py               # Линтер архитектурных зависимостей (Закон A)
    ├── lint_foundry.py               # Линтер чистоты математического ядра (Закон B)
    ├── migrate.py                    # Универсальная миграция артефактов
    ├── migrate_ir.py                 # Специализированная миграция Policy IR
    ├── migrate_to_trinity.py         # Миграция в Trinity формат
    ├── run_mechanism_design.py       # End-to-end демонстрация дифференцируемого дизайна
    └── scan_fabric.py                # Сканер DuckDB и генератор data contracts
```
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

**Архитектурная роль**: Фундаментальная инфраструктура для всей системы Policy Engine. Core является самым нижним слоем в графе зависимостей, предоставляя примитивы, используемые всеми остальными модулями. Реализует паттерн "Clean Architecture" с четким разделением ответственности и строгой типизацией.

**Ключевые компоненты:**
- **Artifacts**: Content-Addressable Storage (CAS) с SHA256 хешированием, дедупликацией и верификацией целостности
- **Environment Manifest**: Захват и сравнение вычислительных окружений с compatibility scoring (CPU/GPU/OS/Python/JAX)
- **Canonical JSON**: Детерминированная сериализация с запретом float чисел и reproducible хешами
- **Contracts**: Типизированные контракты межмодульного взаимодействия (Trinity, Foundry, Fabric, Scientist, Legal)
- **Compiler Reports**: Управление отчетами компиляции и линковки политик
- **Registry System**: Сборка и загрузка реестров компонентов с artifact persistence
- **Trace**: Распределенная система трассировки с span-based моделированием и JSON Lines
- **Run**: Контексты выполнения экспериментов с метаданными и lifecycle management

**Новые возможности (после обновлений):**
- **Enhanced Environment Manifest**: Захват окружения с compatibility scoring, risk assessment и fingerprinting для reproducible симуляций
- **Trinity Contracts**: Типизированные ссылки на ProblemFrame/PolicySpec/ModelSpec артефакты с TrinityManifest для метаданных
- **Advanced Foundry Features**: Conflict Detection (compile-time анализ), Cost Model (оценка стоимости), NaN Guard (numerical stability)
- **Scientist Contracts**: Контракты для FailureCard, PolicyIR и Critique артефактов
- **Enhanced Registry**: Автоматическая сборка registry bundles из IR модуля
- **Trace Sinks**: JSON Lines логирование с structured events и metadata
- **Legal Contracts**: Стабильные контракты для legal validation subsystem (NormPack, NormRule, RuleBackend, RuleType)
- **Provenance Contracts**: Контракты для W3C PROV-O provenance tracking с entities, activities и agents

**Архитектурные особенности:**
- Не зависит ни от одного модуля системы (чистый фундамент)
- Все публичные API используют Pydantic модели с `extra="forbid"`
- Литеральные типы для kind и media_type артефактов обеспечивают compile-time проверки
- Декларативные контракты вместо прямых зависимостей
- Встроенная система трассировки для всех операций
- Environment compatibility scoring для reproducible execution

### `polisyos.ir` — канонические контракты политики (IR)

**Архитектурная роль**: Фундаментальный слой контрактов данных, обеспечивающий единообразие коммуникации между всеми компонентами системы. IR определяет канонические структуры для политик, данных и симуляций, обеспечивая type safety и валидацию на всех уровнях.

**Ключевые компоненты:**
- **Trinity артефакты**: ProblemFrame ("Why"), PolicySpec ("What"), ModelSpec ("How") - разделение ответственности
- **Surface IR v2.0**: Разделение на semantic (исполняемая логика) и advisory (человекочитаемые метаданные) части
- **Kernel Registry**: Фундаментальные реестры типов (механизмы, слоты, merge rules, units, trust policies)
- **Data Views**: Структурированные запросы к данным симуляции (PANEL/SNAPSHOT/NETWORK с access tiers)
- **Linker**: Валидация и связывание политик с реестрами механизмов и слотов
- **Fact Log**: Immutable факты с provenance tracking и детерминированными ID
- **Loaders & Migrations**: Универсальная загрузка политик с автораспознаванием версий
- **Calibration**: Контракты оптимизации параметров относительно исторических данных
- **Validation**: Структурированные отчеты о проблемах с diff между версиями
- **Norm Pack Contracts**: Структурированные представления юридических норм (NormPack, NormRule, NormRef, RuleType)
- **Legal Rule System**: Pluggable backends для оценки юридических норм с protocol-based architecture

**Архитектурные особенности:**
- Не имеет зависимостей от других модулей (чистый контракт)
- Pydantic v2 модели с анти-runaway лимитами (максимальные размеры и глубина)
- Поддержка многоязычных интерфейсов (en/ua/ru локализации)
- Детерминированные ID для артефактов через canonical JSON
- Безопасность типов через строгие ограничения и валидации

### `polisyos.fabric` — Unified Data Fabric (данные + evidence + quality)

**Архитектурная роль**: Единая система обработки и хранения данных для AI-driven симуляции политик. Fabric обеспечивает полный жизненный цикл данных от сырых CSV до высокопроизводительных UDF запросов с криптографической верификацией происхождения и quality gate enforcement.

**Ключевые компоненты:**
- **Data Contract Catalog**: Metric-level система контрактов для type safety с hash-locked bindings, metric search и disambiguation
- **Quality Indicators System**: Многофакторная оценка качества данных (missingness, staleness, coverage, schema drift, outliers) с configurable thresholds
- **Data Fitness Reports**: Человекочитаемые отчеты о пригодности данных с human-readable summaries и quality gate integration
- **Quality Gate Pass**: Интеграция с governance system для блокировки низкокачественных данных
- **Data Ingestion Pipeline**: Полный ETL-конвейер (raw → staging → curated) с evidence tracking
- **UDF Engine**: Безопасный компилируемый слой запросов с multi-pass compilation и Arrow support
- **Fact Log System**: Immutable факты с provenance tracking и детерминированные ID
- **Materializer Engine**: Incremental материализация реляционных представлений из Fact Log
- **Evidence Bundles**: Криптографически verifiable доказательства с trust policies
- **Trust System**: Statistical verification с two-pass comparison и uncertainty bounds
- **Provenance System**: W3C PROV-O compliant система с entities, activities и agents
- **Entity Resolution**: Нормализация идентификаторов агентов с confidence scoring

**Технологии:**
- DuckDB (аналитическое хранилище временных рядов)
- Kùzu (графовая БД для взаимодействий агентов)
- PyArrow/Parquet (эффективная передача columnar данных)
- Pandas (ETL трансформации)
- Pydantic (строгая типизация и валидация)
- W3C PROV-O (стандартизированная provenance система)

**Архитектурные особенности:**
- Multi-backend storage (реляционное + графовое)
- Evidence обязательны для всех результатов (Law E enforcement)
- Quality gate enforcement перед симуляциями (Law K)
- UDF whitelist с privacy passes и access tiers
- Lazy materialization из Fact Log для производительности
- Cryptographic verification всех evidence bundles

### `polisyos.foundry` — JAX‑ядро исполнения (compiler + runtime + calibration)

**Архитектурная роль**: Высокопроизводительный execution engine для дифференцируемого исполнения экономических политик. Foundry компилирует политики в JAX-программы, выполняет симуляции с patch-based state management и калибрует параметры через градиентную оптимизацию.

**Ключевые компоненты:**
- **Compiler Layer**: Компиляция IR в ProgramGraph и ExecPlan с топологической сортировкой
- **Runtime Layer**: Patch-based execution с UpdateOp и Merge Rules (SUM/OVERRIDE/PRIORITY/ERROR)
- **Domain Layer**: Экономическая модель (GlobalState, AgentState, FirmState, MarketState) с Jaxtyping
- **Mechanism Layer**: Экономические механизмы с multi-fidelity (fluid/relaxed/hard уровни точности)
- **Calibration Layer**: Полная система калибровки параметров с Optax, bijectors, uncertainty quantification и Hessian analysis
- **Treasury System**: Детерминированное управление RNG для reproducible симуляций
- **Agent Simulation**: Гетерогенные агенты с нейронными сетями, социальными связями, демографией и artifact system с environment fingerprinting

**Технологии:**
- JAX/Equinox (дифференцируемые вычисления и JIT-компиляция)
- Jaxtyping/Chex (строгая типизация массивов)
- Optax (градиентная оптимизация и калибровка)
- Pydantic (конфигурация и валидация)

**Архитектурные особенности:**
- Чистое математическое ядро без I/O зависимостей (Закон B)
- Patch-based state management вместо прямых изменений
- Multi-fidelity механизмы для trade-off точность/производительность
- Agent-based симуляции с reinforcement learning

### `polisyos.scientist` — AI Policy Scientist (оркестрация + governance + agents)

**Архитектурная роль**: "Мозг" Policy Engine - система оркестрации полного жизненного цикла экспериментов с экономическими политиками. Scientist интегрирует иерархическую систему LLM-агентов, дифференцируемые симуляции, governance controls и legal compliance для автоматического проектирования, валидации и оптимизации политик.

**Ключевые компоненты:**
- **Agent Layer (protocols.py)**: Иерархическая система агентов (PI → Drafter → Formalizer → Critic) с self-healing через Reflexion
- **Self-Healing System**: FailureCard, ShortTermMemory, ReflexionOrchestrator с intelligent routing и backoff logic
- **Kernel Layer**: FSM с 9 фазами, бюджеты (Compute/Evidence/Legitimacy/Complexity), guards, human gates
- **Compute Layer**: Job specifications (JobSpec/JobKey/JobResult), distributed backends (LocalBackend/RayBackend)
- **Design of Experiments**: ScenarioSweep, AblationPlan, SensitivityPlan для systematic research
- **Governance Layer**: Validation pipeline с модульными passes (budget/safety/privacy/schema/legal/quality), profiles (fast/mvp/strict)
- **Legal Validation System**: Pluggable backends для оценки юридических норм (NormPack, RuleBackend, RuleType)
- **Orchestrator Layer**: LangGraph workflow с 9 узлами, self-healing циклами и conditional routing, DecisionPacket v2
- **Decision Card System**: Human-readable summaries результатов экспериментов с verdict/confidence, key metrics, issues summary
- **Run Timeline Tracking**: Event-based tracking системы для runs с phase/node durations, artifact creation, performance metrics
- **Publisher**: Финализация результатов с comprehensive audit trail

**Новые возможности (после обновлений):**
- **Hierarchical Agent System**: PI декомпозиция → Drafter генерация → Formalizer трансформация → Critic валидация
- **Self-Healing & Reflexion**: FailureCard recovery, ShortTermMemory, intelligent routing с backoff logic и escalation logic
- **Multi-Agent Workflow**: Интегрированная система с critique-based refinement, convergence tracking и memory persistence
- **Budget Controls**: Compute/Evidence/Legitimacy/Complexity бюджеты с runtime enforcement
- **FSM Orchestration**: Конечный автомат с 9 фазами и self-healing cycles
- **Human Gates**: Асинхронная система GateRequest/GateDecision для approvals
- **Job Specifications**: Structured execution с reproducible hashing и distributed execution
- **Decision Packet v2**: Comprehensive артефакт с fabric_result, evidence_ref, uncertainty quantification и timeline integration
- **Decision Card System**: Детерминированные human-readable summaries с verdict/confidence, key metrics и issues summary
- **Run Timeline Tracking**: Event-based tracking для observability с phase/node durations и performance metrics
- **Governance Pipeline**: Модульная система validation passes с telemetry и short-circuit логикой
- **Legal Validation System**: Pluggable backends (NormPack, RuleBackend, RuleType) с protocol-based architecture
- **Quality Gate Pass**: Интеграция с Fabric quality indicators для data validation и gate enforcement
- **Validation Profiles**: Fast/mvp/strict профили с configurable passes и profile-based execution

**Технологии:**
- LangGraph (декларативный workflow с FSM и 9 фазами)
- LangChain (интеграция LLM провайдеров)
- PyMOO (multi-objective оптимизация)
- Optax (градиентная оптимизация политик)
- Pydantic (строгая типизация экспериментального state)

**Архитектурные особенности:**
- Self-healing циклы для исправления ошибок через Reflexion pattern
- Multi-fidelity симуляции с adjustable precision и uncertainty quantification
- Budget enforcement на всех уровнях (LLM calls, sim runs, wall time, evidence queries)
- Human gates для критических решений с approval workflow
- End-to-end audit trail с provenance tracking и structured events
- Hierarchical agent coordination с failure recovery и memory persistence
- Legal compliance integration с pluggable rule backends
- Quality gate enforcement перед симуляциями

### `polisyos.runtime` — жизненный цикл прогонов (runs/<run_id>)

**Архитектурная роль**: Инфраструктура управления жизненным циклом экспериментов и артефактов. Runtime является единственной точкой входа для создания и управления запусками, обеспечивая воспроизводимость и аудит согласно Закону D.

**Ключевые компоненты:**
- **API**: `start_run()`, `finalize_run()`, `log_artifact()`, `append_audit()`, `update_budget_usage()`
- **Run Manifest**: Паспорт эксперимента с метаданными, бюджетами и артефактами
- **Artifact Management**: Структурированное хранение с переносимыми относительными ссылками
- **Audit Trail**: Полный JSON Lines лог всех операций с временными метками
- **Budget Tracking**: Отслеживание использования ресурсов (compute, memory, time, LLM calls)

**Архитектурные особенности:**
- Переносимость директорий `runs/` без потери ссылок через `relative_path`
- Структурированное хранение артефактов по типам (policy_ir, simulation_results, etc.)
- Идемпотентные операции с graceful error handling
- Полная traceability через audit trail и provenance tracking

### `polisyos.common` — минимальная инфраструктура (без бизнес‑логики)

**Архитектурная роль**: Фундаментальные утилиты и конфигурации, используемые во всех слоях архитектуры. Common является самым базовым уровнем, не имеющим зависимостей от других модулей и предоставляющим сервисы всем компонентам системы.

**Ключевые компоненты:**
- **Config**: Централизованная конфигурация с JAX environment setup и hardware safeguards
- **JAX Environment**: Безопасная настройка JAX backend для macOS (CPU по умолчанию, опциональный Metal)
- **Logger**: Единый интерфейс структурированного логирования с контекстом модуля через Loguru
- **Migrations**: Детерминированные миграции схем артефактов с обнаружением циклов

**Архитектурные особенности:**
- Не имеет зависимостей от других модулей (чистый фундамент)
- Hardware safeguards для автоматической настройки ресурсов
- JSON сериализация логов для аудита
- Детерминированные миграции с cycle detection

## Связи между модулями

### Архитектурные принципы зависимостей

Policy Engine строго следует **Закону A** (направленный граф зависимостей только внутрь), что обеспечивает модульность, тестируемость и эволюцию системы. Каждый модуль имеет четко определенную ответственность и интерфейсы взаимодействия.

#### Core Layer - фундамент для всех модулей

**Core** предоставляет инфраструктуру всем модулям системы:

- **IR**: Использует `core.canon` для детерминированных хешей, `core.contracts` для типизированных ссылок
- **Fabric**: Зависит от `core.artifacts` (CAS), `core.contracts.fabric` (типы), `core.trace` (логирование)
- **Foundry**: Использует `core.contracts.foundry` (ProgramGraph, ExecPlan), `core.run` (RunContext)
- **Scientist**: Зависит от `core.registry` (реестры), `core.artifacts` (хранение результатов)
- **Runtime**: Интегрируется с `core.artifacts` через CAS, использует `core.trace` для логирования

#### IR Layer - Trinity контракты и типы данных

**IR** определяет Trinity артефакты и канонические структуры данных, используемые всеми модулями:

- **Trinity Architecture**: ProblemFrame ("Why"), PolicySpec ("What"), ModelSpec ("How") - разделение ответственности
- **Fabric**: `ir.data_views` (DataViewRequest, DataViewType), `ir.fact_log` (Fact, FactBatch), `ir.trinity` (Trinity артефакты)
- **Foundry**: `ir.surface` (PolicySurfaceIR), `ir.kernel` (механизмы, слоты, merge rules), `ir.trinity` (ModelSpec для конфигурации)
- **Scientist**: `ir.trinity` (ProblemFrame для декомпозиции, PolicySpec для генерации), `ir.loaders` (универсальная загрузка), `ir.calibration` (CalibrationConfig)
- **Runtime**: `ir.types` (TranslatableString, EntityType) для метаданных, `ir.trinity` (артефакты экспериментов)

#### Fabric Layer - данные и evidence

**Fabric** обеспечивает data layer для симуляций и анализа:

- **Data Contract Catalog**: `fabric.catalog.*` (DataContractRegistry, MetricBinding, MetricSearcher) - type safety для метрик
- **Scientist**: `fabric.udf.engine` (UDFEngine для запросов данных), `fabric.catalog` (contract validation), `fabric.registry` (ManifestRegistry)
- **Foundry**: Косвенная зависимость через scientist (данные для симуляций)
- **Runtime**: Косвенная интеграция через логирование результатов UDF запросов

#### Foundry Layer - математическое ядро и симуляции

**Foundry** реализует execution engine, изолированный от data layer согласно **Закону B**. Детальные зависимости согласно `src/polisyos/core/README.md`:

- **Core**: `core.contracts.foundry` (ProgramGraph, ExecPlan, StateDelta, PatchOp, UpdateOp, Patch, PatchSet, PatchMeta), `core.artifacts` (CAS для всех артефактов симуляции), `core.artifacts.environment` (EnvironmentManifest с fingerprinting), `core.run.RunContext` (контексты выполнения), `core.trace` (детальная трассировка), `core.canon` (каноническая сериализация для reproducible результатов), `core.contracts.foundry` (расширенные контракты: ConflictDetection, CostModel, NaN Guard)
- **IR**: `ir.kernel` (реестры механизмов, слотов, merge rules), `ir.calibration` (CalibrationConfig), `ir.trinity` (ModelSpec)
- **Scientist**: `foundry.compiler` (compile_surface_policy), `foundry.executor` (execute_program_graph), `foundry.calibration` (parameter optimization), `foundry.agent_sim` (artifact system), `foundry.runtime.nan_guard` (numerical stability), `foundry.conflict_checker` (compile-time validation), `foundry.cost_model` (performance estimation)

#### Scientist Layer - оркестрация

**Scientist** координирует работу всех компонентов согласно детальной информации из `src/polisyos/scientist/README.md`:

- **Core**: `core.run` (RunContext), `core.artifacts` (CAS storage), `core.contracts.trinity/scientist/legal` (типизированные контракты), `core.trace` (audit trail), `core.registry` (реестры компонентов), `core.contracts.foundry` (ProgramGraph, ExecPlan), `core.canon` (каноническая сериализация)
- **IR**: `ir.trinity` (ProblemFrame/PolicySpec/ModelSpec), `ir.loaders` (универсальная загрузка), `ir.calibration` (CalibrationConfig), `ir.norm_pack` (NormPack, NormRule)
- **Fabric**: `fabric.udf.engine` (UDFEngine), `fabric.catalog` (contract validation), `fabric.registry` (ManifestRegistry), `fabric.quality` (quality indicators), `fabric.evidence` (evidence bundles), `fabric.trust` (uncertainty bounds)
- **Foundry**: `foundry.compiler` (compile_surface_policy), `foundry.executor` (execute_program_graph), `foundry.calibration` (parameter optimization), `foundry.agent_sim` (artifact system), `foundry.runtime.nan_guard` (numerical stability), `foundry.conflict_checker` (compile-time validation), `foundry.cost_model` (performance estimation)
- **Runtime**: Управление жизненным циклом экспериментов через API (start_run, log_artifact, finalize_run)

#### Runtime Layer - управление жизненным циклом

**Runtime** обеспечивает инфраструктуру для всех экспериментов:

- **Scientist**: Основной потребитель API (start_run, log_artifact, finalize_run)
- **Fabric**: Логирование результатов UDF через runtime artifacts
- **Foundry**: Логирование результатов симуляций через runtime artifacts

#### Legal Layer - compliance и валидация норм

**Legal** обеспечивает проверку соответствия политик юридическим нормам:

- **IR**: Определяет контракты нормативных документов (`ir.norm_pack`: NormPack, NormRule, NormRef, RuleType)
- **Core**: Предоставляет стабильные контракты legal subsystem (`core.contracts.legal`)
- **Scientist**: Реализует legal validation passes (`scientist.governance.passes.legal_pass`)
- **Runtime**: Логирует результаты legal compliance в audit trail

#### Common Layer - фундаментальные утилиты

**Common** предоставляет базовые сервисы всем модулям согласно информации из `src/polisyos/common/README.md`:

- **Логирование (`logger.py`, `get_logger`)**: Активно используется в fabric/ingestion.py, fabric/io/db.py, fabric/io/graph_store.py, fabric/materializer.py, fabric/udf/engine.py, fabric/udf/compiler.py, scientist/orchestrator/data_loader.py, foundry/compiler.py, foundry/agent_sim/artifact.py, foundry/agent_sim/training.py, foundry/executor.py
- **Конфигурация (`config.py`)**: JAX environment setup, hardware safeguards, logging infrastructure - используется через jax_bootstrap.py и во всем проекте
- **Миграции (`migrations/`)**: Используется в ir/migrations/ для миграций Policy IR и Trinity форматов
- **Все модули**: Структурированное логирование с контекстом модуля через Loguru, JAX backend selection для macOS

#### Legal Layer - compliance и валидация норм

**Legal** обеспечивает проверку соответствия политик юридическим нормам:

- **IR**: Определяет контракты нормативных документов (`ir.norm_pack`: NormPack, NormRule, NormRef, RuleType)
- **Core**: Предоставляет стабильные контракты legal subsystem (`core.contracts.legal`)
- **Scientist**: Реализует legal validation passes (`scientist.governance.passes.legal_pass`)
- **Runtime**: Логирует результаты legal compliance в audit trail

### Поток данных в компиляторной трубе (с Trinity архитектурой)

```
User Request → Scientist.orchestrator → IR.trinity → Fabric.quality → Fabric.udf → Foundry.compiler → Foundry.calibration → Runtime.api → Artifacts
    ↓              ↓                      ↓            ↓             ↓                ↓              ↓              ↓
   Agent Pipeline ExperimentState     ProblemFrame QualityGate     DataViewRequest  ProgramGraph    ExecResult    RunManifest
    ↓              ↓                      ↓            ↓             ↓                ↓              ↓              ↓
   Hierarchical   LangGraph 9-phase   PolicySpec   DataFitnessReport UDF Result     StateDelta     Metrics       Audit Trail
   Agents         Workflow             ↓            ↓             ↓                ↓              ↓              ↓
   ↓              ↓                    ModelSpec   Evidence Bundle Uncertainty Bounds DecisionPacket ← Fabric Result
   Self-Healing   ↓                    ↓            ↓             ↓                ↓              ↓
   Reflexion      Governance           TrinityBundle Provenance    Trust Policies   Patch-based    Evidence Ref
    ↓              ↓                    ↓            ↓             ↓                ↓              ↓
   FailureCard    Budget Controls      Migration    W3C PROV-O    Legal Validation  Execution      Uncertainty
```

### Архитектурные гарантии

- **Закон A**: Направленный граф зависимостей (scientist → ir/fabric/foundry/runtime/core → common)
- **Закон B**: Foundry как чистое математическое ядро (без I/O зависимостей)
- **Закон C**: Контракты как источник истины (IR определяет все структуры данных)
- **Закон D**: Воспроизводимость через runtime manifests и CAS artifacts
- **Закон E**: Evidence обязательны для всех data результатов
- **Закон F**: Multi-fidelity control для trade-off точность/производительность
- **Закон G**: Uncertainty quantification в калибровке и результатах
- **Закон H**: Governance через budgets и human gates
- **Закон I**: Trust policies с statistical verification

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

# Foundry тесты (JAX, симуляции, калибровка, agent simulation, conflict detection, cost model, nan guard)
pytest tests/foundry/ -v

# Integration тесты (workflow, scientist + fabric + foundry)
pytest tests/integration/ -v
```

## Новые возможности (после крупных изменений)

### 🏗️ Архитектурная эволюция

- **Trinity Architecture**: Разделение IR на ProblemFrame ("Why"), PolicySpec ("What"), ModelSpec ("How")
- **Agent Protocols**: Стандартизированные интерфейсы для PI/Drafter/Formalizer/Critic агентов с runtime поведением
- **Enhanced Environment Manifest**: Захват окружения с compatibility scoring, risk assessment и fingerprinting для reproducible симуляций
- **Enhanced Monitoring**: Метрики, трекинг экспериментов и визуализация для agent simulation
- **Runtime модуль**: Полное управление жизненным циклом прогонов с аудитом и артефактами
- **Fact Log система**: Immutable факты с provenance tracking и evidence bundles
- **UDF Compilation Pipeline**: Безопасная компиляция SQL/Cypher запросов с whitelist
- **Patch-based Execution**: Декларативные изменения состояния вместо прямых модификаций
- **Treasury System**: Детерминированное управление RNG для воспроизводимости
- **Plugin System**: Модульная архитектура с capability-based registry и composite executors
- **Provenance Tracking System**: W3C PROV-O compliant система отслеживания происхождения данных
- **Evidence-Enhanced Fabric**: Криптографически verifiable evidence bundles с provenance графами

### 📊 Расширенная система данных

- **Data Contract Catalog**: Metric-level система контрактов с hash-locked bindings для предотвращения hallucination имен метрик
- **Materializer**: Полноценная система восстановления реляционных представлений из Fact Log с incremental updates
- **Evidence Bundles**: Криптографически verifiable доказательства происхождения данных
- **Provenance Tracking**: W3C PROV-O compliant система отслеживания происхождения с entities, activities и agents
- **Multi-tier Access Control**: PII classification (public/internal/sensitive)
- **Entity Resolution**: Нормализация идентификаторов агентов с confidence scoring
- **Financial Reconciliation**: Балансовая проверка транзакций с tolerance

### 🤖 Улучшенный AI Scientist

- **Hierarchical Agent System**: PI декомпозиция → Drafter генерация → Formalizer трансформация → Critic валидация
- **Self-Healing & Reflexion**: FailureCard recovery, ShortTermMemory, intelligent routing с backoff logic
- **Multi-Agent Workflow**: Интегрированная система с critique-based refinement и convergence tracking
- **FSM-based Orchestration**: Конечный автомат состояний с 9 фазами для надежного workflow
- **Budget Controls**: Compute/Evidence/Legitimacy/Complexity бюджеты с runtime enforcement
- **Human Gates**: Асинхронная система GateRequest/GateDecision для approvals
- **Job Specifications**: Structured execution с reproducible hashing и distributed backends
- **Design of Experiments**: ScenarioSweep, AblationPlan, SensitivityPlan для systematic research
- **Self-healing Policies**: Автоматическое исправление ошибок валидации через Reflexion pattern
- **Decision Packet**: Полный артефакт с evidence, uncertainty и provenance tracking
- **Governance Pipeline**: Модульная система validation passes с short-circuit логикой и telemetry
- **Validation Profiles**: Fast/mvp/strict профили валидации с configurable passes
- **Legal Validation System**: Pluggable backends для оценки юридических норм с protocol-based architecture
- **Norm Pack Contracts**: Структурированные представления юридических норм (NormPack, NormRule, NormRef)

### 🔬 Продвинутое симуляционное ядро

- **Agent Simulation**: Пошаговая симуляция гетерогенных агентов с ML моделями, социальными связями и демографией
- **Program Graph Compilation**: Топологическая сортировка и execution plans с registry-driven линковкой
- **Patch-based Execution**: UpdateOp и Merge Rules (SUM/OVERRIDE/PRIORITY/ERROR) для state management
- **Multi-fidelity Mechanisms**: Fluid/relaxed/hard уровни точности с fidelity control
- **Calibration MVP**: Полная система калибровки параметров с uncertainty quantification через Hessian
- **Constraints Engine**: Runtime валидация ограничений с enforcement
- **Treasury System**: Детерминированное управление RNG для reproducible симуляций
- **Plugin Architecture**: Composite executors и capability-based plugin registry для расширения доменов

### 🛡️ Governance & Compliance

- **Preflight/Postflight Checks**: Автоматические проверки безопасности с validation pipeline
- **Validation Passes**: Модульные проверки (budget/safety/privacy/schema) с telemetry
- **Validation Profiles**: Fast/mvp/strict профили с configurable passes и short-circuit логикой
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

Проект имеет комплексную тестовую инфраструктуру, охватывающую все архитектурные слои согласно принципам из `tests/README.md`. Тесты обеспечивают качество кода, валидируют архитектурные границы и проверяют корректность работы всех компонентов системы.

#### Категории тестов по архитектурным слоям:

**Contract Tests (`contract/`)**: Валидация контрактов IR и схем, включая Trinity артефакты, миграции, kernel models и fabric gates
**Core Phase 0 Tests (`core_phase0/`)**: Тестирование фундаментальных компонентов core layer - artifact store, канонической сериализации и registry систем
**Fabric Tests (`fabric/`)**: Комплексная валидация Data Contract catalog, evidence bundles, provenance system, trust two-pass comparison и quality indicators
**Foundry Tests (`foundry/`)**: Тестирование JAX-ядра с agent simulation, plugin system, conflict detection, cost model, NaN guard, merge determinism и calibration
**IR Tests (`ir/`)**: Валидация загрузчиков и трансформаций PolicySurfaceIR структур
**Runtime Tests (`runtime/`)**: Тестирование runtime API, manifest paths и artifact management
**Scientist Tests (`scientist/`)**: Тестирование agent protocols, governance pipeline, legal compliance, decision card system, run timeline tracking и multi-agent workflow

#### Запуск тестов:

```bash
# Полный тест-свит с категориями (быстрые unit + медленные integration)
pytest tests/ -x --tb=short

# Только быстрые unit тесты (foundry + contract + core)
pytest -m "not integration"

# Только интеграционные тесты (end-to-end с БД)
pytest -m integration

# По категориям модулей
pytest tests/contract/ -v         # Contract тесты (IR, Trinity, migrations)
pytest tests/core_phase0/ -v      # Core infrastructure (CAS, canon, manifests)
pytest tests/fabric/ -v           # Fabric layer (evidence, trust, provenance, quality)
pytest tests/foundry/ -v          # Foundry JAX core (agent sim, plugins, conflict detection, cost model, nan guard)
pytest tests/ir/ -v               # IR layer (loaders, transformations)
pytest tests/runtime/ -v          # Runtime API (manifests, artifacts)
pytest tests/scientist/ -v        # Scientist layer (agents, governance, legal, decision systems)

# Новые компоненты scientist
pytest tests/scientist/test_decision_card.py -v      # Decision card system
pytest tests/scientist/test_decision_packet_v2.py -v # Decision packet v2
pytest tests/scientist/test_run_timeline.py -v       # Run timeline tracking

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

Для детального понимания архитектуры и API каждого модуля обратитесь к специализированной документации в соответствующих директориях:

### 🔧 Core Infrastructure (Инфраструктурный фундамент)
- **[`src/polisyos/core/README.md`](src/polisyos/core/README.md)**: Content-Addressable Storage (CAS), каноническая JSON сериализация, типизированные контракты межмодульного взаимодействия, распределенная трассировка, контексты выполнения, управление реестрами компонентов

### 📋 Intermediate Representation (Промежуточное представление)
- **[`src/polisyos/ir/README.md`](src/polisyos/ir/README.md)**: Trinity архитектура (ProblemFrame/PolicySpec/ModelSpec), PolicySurfaceIR v2.0 (semantic/advisory), kernel-реестры (механизмы, слоты, merge rules, units, trust policies), линкер политик, загрузчики с автораспознаванием версий, Fact Log контракты, калибровка параметров

### 🏗️ Unified Data Fabric (Единая система данных)
- **[`src/polisyos/fabric/README.md`](src/polisyos/fabric/README.md)**: ETL pipeline (CSV → DuckDB + Kùzu), UDF compilation с security passes, Fact Log система, evidence bundles, entity resolution, materializer engine, trust policies с statistical verification

### ⚡ JAX Simulation Core (Математическое ядро)
- **[`src/polisyos/foundry/README.md`](src/polisyos/foundry/README.md)**: Агентная симуляция с ML, plugin система, компиляция IR в ProgramGraph, patch-based execution, multi-fidelity механизмы, calibration через Optax с uncertainty quantification, constraints engine, treasury RNG

### 🤖 AI Policy Scientist (Интеллектуальная оркестрация)
- **[`src/polisyos/scientist/README.md`](src/polisyos/scientist/README.md)**: Agent protocols (PI/Drafter/Formalizer/Critic), LangGraph workflow с 9 фазами, FSM orchestration, budget controls, human gates, Design of Experiments, DecisionPacket с evidence и uncertainty quantification

### 🔄 Runtime & Lifecycle (Управление жизненным циклом)
- **[`src/polisyos/runtime/README.md`](src/polisyos/runtime/README.md)**: RunManifest API, audit trail в JSON Lines, artifact logging с переносимыми путями, budget tracking, lifecycle management экспериментов

### 🛠️ Common Utilities (Фундаментальные утилиты)
- **[`src/polisyos/common/README.md`](src/polisyos/common/README.md)**: JAX environment setup (CPU-first для macOS), структурированное логирование через Loguru, детерминированные миграции схем, hardware safeguards

### 🧪 Testing Framework (Тестовая инфраструктура)
- **[`tests/README.md`](tests/README.md)**: Contract тесты (IR валидация, Trinity, legal norms), core phase 0 (CAS, canonical JSON, environment manifests), fabric (evidence, trust, provenance, quality indicators, fitness reports), foundry (JAX, calibration, agent simulation, plugins, conflict detection, cost model, nan guard, merge determinism), integration (end-to-end workflows, UDF calibration), runtime (artifact management), scientist (governance, legal compliance, agent protocols, reflexion)

### 🔨 Developer Tools (Инструменты разработчика)
- **[`tools/README.md`](tools/README.md)**: Архитектурные линтеры (lint_imports.py - Закон A, lint_foundry.py - Закон B), генерация JSON Schema, миграции артефактов, бенчмарки производительности, демонстрационные скрипты, диагностика системы, scan_fabric.py (bootstrap data contracts), migrate_to_trinity.py (миграция в Trinity формат), capture_env.py (environment manifests), visualize_provenance.py (визуализация provenance графов)

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
- **Закон J**: Legal compliance (norm packs, rule backends, validation passes)

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

### Новые компоненты (активно развиваемые)

- **Legal Validation System**: Полноценная система проверки соответствия политик юридическим нормам с pluggable backends (RuleBackend, NormPack, NormRule)
- **Trinity Architecture**: Активно используется в scientist модуле для структурирования экспериментов (ProblemFrame, PolicySpec, ModelSpec)
- **Enhanced Kernel Registries**: Расширенная система фундаментальных реестров с новыми типами (механизмы, слоты, trust policies, legal norms)
- **Provenance Tracking System**: W3C PROV-O compliant система отслеживания происхождения данных с entities, activities и agents
- **Evidence-Enhanced Fabric**: Криптографически verifiable evidence bundles с provenance графами и trust policies

### Новые возможности (2026-01-27)

#### 🏗️ Архитектурные улучшения
- **Trinity Architecture v2.1.4**: Полная поддержка ProblemFrame/PolicySpec/ModelSpec с типизированными ссылками и TrinityManifest
- **W3C PROV-O Integration**: Стандартизированная система provenance tracking с entities, activities и agents
- **Legal Validation System**: Pluggable backends для оценки юридических норм с protocol-based architecture
- **Quality Gate Enforcement**: Автоматическая валидация качества данных перед симуляциями с QualityGatePass
- **Enhanced Environment Manifest**: Захват окружения с compatibility scoring, risk assessment и fingerprinting

#### 📊 Data Management & Quality
- **Data Contract Catalog**: Metric-level система контрактов с hash-locked bindings
- **Quality Indicators System**: Многофакторная оценка качества данных (missingness, staleness, coverage, outliers)
- **Data Fitness Reports**: Человекочитаемые отчеты о пригодности данных с configurable thresholds
- **Fact Log System**: Immutable факты с provenance tracking и детерминированные ID
- **Materializer Engine**: Incremental материализация реляционных представлений из Fact Log
- **Enhanced Environment Manifest**: Захват окружения с compatibility scoring и risk assessment

#### 🤖 AI & Agent Systems
- **Hierarchical Agent System**: PI → Drafter → Formalizer → Critic с протоколами
- **Self-Healing Agents**: Reflexion system с FailureCard recovery и intelligent routing
- **Multi-Agent Workflow**: Интегрированная система с critique-based refinement
- **Agent Protocols**: Стандартизированные интерфейсы с runtime поведением

#### 🔐 Trust & Evidence
- **Evidence Bundles**: Криптографически verifiable доказательства происхождения
- **Trust System**: Statistical verification с two-pass comparison и uncertainty bounds
- **Provenance Tracking**: W3C PROV-O compliant система с entities, activities и agents
- **Evidence-Enhanced Fabric**: Полная интеграция evidence в data pipeline

#### ⚡ Simulation & Execution
- **Multi-Fidelity Simulation**: Fluid/relaxed/hard уровни точности с fidelity control
- **Patch-based Execution**: UpdateOp и Merge Rules для state management
- **Agent Simulation**: Пошаговая симуляция с ML моделями и социальными связями
- **Plugin System**: Capability-based registry с composite executors

#### 🎯 Governance & Compliance
- **Budget Controls**: Compute/Evidence/Legitimacy/Complexity бюджеты
- **Human Gates**: Асинхронная система GateRequest/GateDecision
- **FSM Orchestration**: Конечный автомат с 9 фазами и self-healing cycles
- **Governance Pipeline**: Модульная система validation passes
- **Legal Compliance Passes**: Валидация политик против нормативных требований

#### 🛠️ Development Tools
- **UDF Compilation Pipeline**: Безопасная компиляция SQL/Cypher запросов
- **Enhanced Kernel Registries**: Расширенная система фундаментальных реестров
- **Enhanced Monitoring**: Метрики, трекинг экспериментов и визуализация
- **Failure Card System**: Структурированные артефакты ошибок с recovery
- **scan_fabric.py**: Bootstrap утилита для генерации data contracts
- **visualize_provenance.py**: Инструмент для визуализации provenance графов

---

*Policy Engine (PolisyOS) — компиляторная система симуляции политик: контракты → компиляция → JAX‑исполнение → артефакты с аудитом и воспроизводимостью.*
