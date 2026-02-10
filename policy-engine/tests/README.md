# Policy Engine — Tests

Тестовая инфраструктура Policy Engine. Покрывает все слои компилятора — от базовых артефактов до AI-оркестрации экспериментов.

**Масштаб:** ~200 Python-файлов, ~37 700 строк кода.

## Обзор

Тесты организованы зеркально слоистой архитектуре движка:

```
core → runtime → ir → fabric → foundry → scientist
```

| Каталог | Файлов | ~Строк | Покрытие |
|---------|-------:|-------:|----------|
| `core/phase0/` | 21 | 2 500 | Artifact store, observability, signing, CLI |
| `runtime/` | 3 | 180 | Replay verification, manifest paths |
| `ir/` | 8 | 620 | Policy loaders, registry fragments, uncertainty |
| `contract/` | 20 | 2 800 | IR-контракты, ABI-совместимость, миграции |
| `fabric/` | 36 | 10 000 | Data catalog, connectors, provenance, trust, quality |
| `foundry/` | 61 | 14 000 | JAX-симуляция, calibration, methods framework |
| `scientist/` | 50 | 7 500 | AI-оркестрация, governance, search, backtesting |
| `lex/` | 3 | 140 | Симулятор правовых норм |
| `integration/` | 5 | 600 | End-to-end workflows, human gates |
| `performance/` | 2 | 330 | Benchmark-baseline regression checks |
| `demos/` | 1 | 15 | Laffer curve demo |
| корень | 7 | 440 | Arch gates, component discovery, API facades |

## Структура каталогов

```
tests/
├── conftest.py                             # JAX CPU-mode, loguru → ERROR only
├── test_arch_import_gate.py                # Lint imports по import_policy.toml
├── test_public_api_facades.py              # __all__, запрет star-imports
├── test_components_*_phase19.py            # Component discovery, bridge, semver (4 файла)
│
├── contract/                               # IR-контракты и ABI
│   ├── conftest.py
│   ├── golden_records.json                 # Фикстура стабильности хэшей
│   ├── test_trinity_contracts.py           # TrinityBundle, селекторы
│   ├── test_trinity_linker_contract.py     # Semantic fingerprinting
│   ├── test_abi_diff_tool.py               # ABI diff между версиями
│   ├── test_golden_record_ids.py           # Golden record стабильность
│   ├── test_world_abi_contract.py          # World ABI
│   ├── test_fabric_gates.py               # Fabric gate protocol
│   ├── test_run_experiment_slo.py          # Experiment SLO
│   └── ...                                 # kernel_models, migrations, slo_metrics и др.
│
├── core/phase0/                            # Базовые компоненты
│   ├── conftest.py                         # OTel in-memory exporter, CAS fixtures
│   ├── test_artifact_store.py              # FileSystemCAS, дедупликация, integrity
│   ├── test_store_signing.py               # Cryptographic signing артефактов
│   ├── test_signing.py                     # Ed25519
│   ├── test_canon_json.py                  # Каноническая JSON-сериализация
│   ├── test_tracer.py                      # PolicyOSTracer singleton, spans
│   ├── test_observability.py               # Workflow tracing integration
│   ├── test_environment_manifest.py        # Env manifest (deps, platform, git)
│   ├── test_cli_*.py                       # CLI signing, resume
│   └── ...                                 # metrics, logs, decorators, propagation
│
├── fabric/                                 # Data Fabric
│   ├── connectors/                         # 16 файлов — Connector Protocol
│   │   ├── conftest.py
│   │   ├── test_protocol_compliance.py     # Capabilities, lifecycle
│   │   ├── test_registry.py               # Connector registry (1 128 строк)
│   │   ├── test_type_system.py            # Type coercion (1 155 строк)
│   │   ├── test_schema_system.py          # Schema inference, evolution
│   │   ├── test_transform_pipeline.py     # ETL chains
│   │   ├── test_quality_system.py         # Data quality
│   │   ├── test_cache_system.py           # TTL, invalidation
│   │   ├── test_federation.py             # Cross-source join
│   │   ├── test_resilience.py             # Error recovery, retries
│   │   ├── test_harness.py               # Test harness utilities
│   │   ├── test_integration.py            # Connector integration
│   │   └── reference/                     # Reference: CSV, REST JSON, SDMX
│   ├── test_data_catalog.py               # Data contracts, metric bindings
│   ├── test_provenance.py                 # PROV-O export, lineage
│   ├── test_evidence_bundle.py            # Evidence ingestion pipeline
│   ├── test_trust_two_pass.py             # Optimistic/pessimistic → bounds
│   ├── test_trust_adapter.py              # Trust → uncertainty envelope
│   ├── test_conflict_uncertainty_adapter.py # Conflict → uncertainty
│   ├── test_quality_indicators.py         # Missingness, staleness, coverage
│   ├── test_world_*.py                    # World store, materialization, Kuzu
│   ├── test_normpack.py           # NormPack pipeline
│   ├── test_legal_evaluation.py   # Legal evaluation
│   ├── test_claims_pipeline.py    # Claims extraction
│   └── ...                                # lex_corpus, docs_pipeline, scholar
│
├── foundry/                                # Simulation Engine
│   ├── methods/                            # 25 файлов — Methods Framework
│   │   ├── conftest.py                     # Shared units, slots
│   │   ├── test_protocol.py               # FoundryMethod protocol
│   │   ├── test_registry.py               # Method registry (1 025 строк)
│   │   ├── test_compiler.py               # Method compilation (937 строк)
│   │   ├── test_linker.py                 # Method linking (850 строк)
│   │   ├── test_discovery.py              # Method discovery (1 239 строк)
│   │   ├── test_composer.py               # Method composition
│   │   ├── test_artifacts.py              # Method artifact persistence
│   │   ├── test_base.py                   # Base method classes
│   │   ├── backends/
│   │   │   └── test_backends.py           # JAX / NumPy backends
│   │   └── catalog/
│   │       ├── causal/                    # 7 файлов: DID, RDD, SCM, HTE, time series
│   │       └── econometrics/              # 5 файлов: IV (2SLS/GMM), panel, time series
│   ├── agent_sim/
│   │   └── test_monitoring.py             # MetricsCollector, ExperimentTracker
│   ├── analysis/
│   │   └── test_distributional.py         # Gini, Palma ratio, cohort breakdown
│   ├── plugins/
│   │   └── test_plugin_system.py          # PluginRegistry, CompositeExecutor
│   ├── test_calibrator_mvp.py             # Calibration + оптимизация (457 строк)
│   ├── test_calibrator_fidelity.py        # Fidelity: fluid / relaxed / hard
│   ├── test_calibration_uncertainty_adapter.py # Calibration → uncertainty envelope
│   ├── test_adaptive_agents.py            # Адаптивные агенты
│   ├── test_agent_simulation_step*.py     # Пошаговая симуляция (6 файлов)
│   ├── test_conflict_detection.py         # Compile-time conflicts
│   ├── test_cost_model.py                 # Execution cost estimation
│   ├── test_gradients.py                  # JAX autodiff
│   ├── test_nan_guard.py                  # NaN/Inf detection
│   ├── test_merge_determinism.py          # Deterministic merge
│   ├── test_jit_stability.py             # JIT + PyTree
│   ├── test_no_io_kernel.py               # Kernel purity (запрет I/O)
│   └── ...                                # batch, patch_executor, health и др.
│
├── scientist/                              # AI Orchestration
│   ├── conftest.py                         # OTel + singleton reset
│   ├── search/                             # 14 файлов — Search & Optimization
│   │   ├── test_search_loop.py            # SearchController, two-stage filtering
│   │   ├── test_adversarial.py            # Adversarial/stress testing
│   │   └── strategies/                    # 9 файлов
│   │       ├── conftest.py                # Space fixtures, evaluation helpers
│   │       ├── test_bayesian.py           # Bayesian optimization (BoTorch/Sobol)
│   │       ├── test_multi_objective.py    # Multi-objective, Pareto front
│   │       ├── test_random_grid.py        # Random / grid search
│   │       ├── test_controller_batch.py   # Batch generation
│   │       ├── test_adapter.py            # Strategy → controller adapter
│   │       ├── test_space_codec.py        # Parameter space encoding
│   │       └── test_resource_arbiter.py   # Memory limits, process mgmt
│   ├── governance/                         # 6 файлов — Governance layer
│   │   ├── test_norm_execution.py         # Safe expression eval (AST policy)
│   │   ├── test_validation_pipeline.py    # Multi-pass validation
│   │   ├── test_legal_pass.py             # NormPack compliance
│   │   ├── test_equity_pass.py            # Distributional equity
│   │   └── test_confidence_pass.py        # Statistical confidence
│   ├── doe/                                # 2 файла — Design of Experiments
│   │   ├── test_sensitivity_plan.py       # Morris, Sobol, guardrails
│   │   └── test_sampling.py              # Adversarial sampling strategies
│   ├── compute/
│   │   └── test_runner_polyglot.py        # Polyglot job execution
│   ├── integration/
│   │   ├── test_checkpoint_resume.py      # Checkpoint/resume workflow
│   │   └── test_workflow_tracing.py       # End-to-end tracing
│   ├── test_agent_protocols.py            # PI, Drafter, Formalizer, Critic
│   ├── test_decision_packet_v2.py         # DecisionPacket v2
│   ├── test_decision_packet_node_v3.py    # DecisionPacket v3
│   ├── test_decision_packet_distributional_econometrics.py
│   ├── test_decision_card.py              # DecisionCard system
│   ├── test_reflexion_loop.py             # Failure cards, recovery
│   ├── test_multi_agent_workflow.py       # Multi-agent critique
│   ├── test_backtesting.py               # Backtesting orchestrator, trust scoring
│   ├── test_causal_evaluation_node.py     # Causal effect estimation
│   ├── test_distributional_analysis_node.py
│   ├── test_propagate_uncertainty_node.py
│   ├── test_instrumentation.py            # Flow node / LLM client tracing
│   ├── test_compiler.py                   # Scientist compiler
│   ├── test_checkpoint.py                 # Checkpoint system
│   ├── test_idempotency.py               # Idempotent execution
│   └── ...                                # engine_executor, registry, replay и др.
│
├── integration/                            # End-to-end сценарии
│   ├── test_workflow_smoke.py             # IR → compilation → simulation → DecisionPacket
│   ├── test_human_gate_audit.py           # Human approval gate, audit trail
│   └── test_workflow_llm.py               # LLM integration
│
├── ir/                                     # IR Layer
│   ├── test_loaders.py                    # Policy loaders
│   ├── test_trinity_loaders.py            # TrinityBundle loading
│   ├── test_registry_fragments.py         # Fragment persistence
│   ├── test_registry_fragments_components.py
│   ├── test_hte_backtest.py               # HTE result + backtest report persistence
│   ├── test_uncertainty.py                # UncertaintyEnvelope, CAS round-trip
│   └── test_queries_contracts.py          # Query contracts
│
├── lex/simulator/                          # Legal Norm Simulator
│   ├── test_engine.py                     # NormImpactAnalyzer, report persistence
│   ├── test_mutator.py                    # NormPack mutations, determinism
│   └── test_diff.py                       # NormPack diff (added/removed/modified)
│
├── performance/
│   └── test_overhead.py                   # Benchmark-baseline budgets for simulation/CAS/calibration
│
├── runtime/
│   ├── test_replay_runtime.py             # Replay verification
│   └── test_runtime_manifest_paths.py     # Relative path portability
│
└── demos/
    └── run_laffer_demo.py                 # Запуск из tools/demos/
```

## Описание модулей

### Корневые тесты — архитектурные гейты (7 файлов)

Валидация архитектурных границ и компонентной системы Phase 19.

- **test_arch_import_gate** — прогоняет `lint_imports.py` с `import_policy.toml`; предотвращает нарушение слоистой архитектуры (core не импортирует fabric и т.д.)
- **test_public_api_facades** — каждый публичный модуль определяет `__all__`, star-imports запрещены
- **test_components_discovery_phase19** — entry-point discovery загружает IR-фрагменты и foundry-методы из установленных пакетов
- **test_packs_discovery_phase19** — dev-scan и entry-point обнаружение pack-компонентов (IR, methods, extractors, evaluators, norm providers)
- **test_components_bridge_phase19** — bootstrap: component metadata → method registry с resolution policies
- **test_components_id_semver_phase19** — парсинг `namespace.name@version`, SemVer comparison, range matching

### contract/ — IR-контракты и ABI (20 файлов)

Валидация структурных контрактов на всех уровнях IR. Гарантирует, что изменения в схемах не ломают совместимость.

**Ключевые области:**
- **TrinityBundle** — структура, селекторы, транслируемые строки, semantic fingerprinting; линкер создаёт validation reports для broken references
- **ABI compatibility** — `test_abi_diff_tool` автоматически обнаруживает несовместимые изменения; `golden_records.json` фиксирует эталонные хэши
- **Schema migrations** — безопасные переходы между версиями IR
- **Gate protocol** — контракты fabric gates и foundry facades
- **SLO contracts** — метрики и SLO для experiment runs, kernel models (slots, units, merge rules)

### core/phase0/ — Базовые компоненты (21 файл)

Фундамент всей системы: immutable storage, cryptographic integrity, distributed observability.

**Artifact Store:** `FileSystemCAS` — content-addressable storage с дедупликацией и integrity verification. Ed25519 signing артефактов, export/import, artifact graph и зависимости.

**Observability (OpenTelemetry):** `PolicyOSTracer` singleton с lazy initialization; span hierarchy и context propagation через все слои; `MetricsRegistry` (histograms, timers, counters); log-trace correlation; `@traced` decorator для автоматической инструментации.

**Прочее:** каноническая JSON-сериализация для стабильных хэшей; environment manifest (deps, platform, git); registry bundle persistence; CLI (signing, resume).

### fabric/ — Data Fabric (36 файлов)

Unified Data Fabric: от подключения источников до оценки качества и доверия.

**Connectors Protocol (16 файлов)** — самая объёмная подсистема тестов (~5 500 строк):
- Protocol compliance, capabilities, lifecycle management
- Registry — регистрация, discovery, version management (1 128 строк)
- Type system — coercion, validation, inference (1 155 строк)
- Schema — inference, evolution, compatibility checking
- Transform pipeline — ETL chains с промежуточными преобразованиями
- Quality / Cache / Federation / Resilience
- Reference implementations: Static CSV, REST JSON, SDMX

**Data Catalog & Evidence:** data contract catalog с metric bindings и search; evidence bundles с ingestion pipeline; provenance — PROV-O export, lineage chain.

**Trust & Uncertainty:** two-pass comparison (optimistic/pessimistic → bounds); адаптеры trust → uncertainty envelope и conflict → uncertainty envelope; quality indicators — missingness, staleness, coverage, fitness reports.

**Domain pipelines:** world store / materialization / Kuzu graph; NormPack pipeline; lex corpus; legal evaluation; claims extraction; documentation pipeline; scholar extractors.

### foundry/ — Simulation Engine (61 файл)

JAX-based simulation: extensible methods framework, calibration, agent simulation.

**Methods Framework (25 файлов, ~7 000 строк)** — ядро computation:
- Core infrastructure: protocol, registry, compiler, linker, composer, discovery, artifacts — крупнейшие тест-файлы проекта (discovery 1 239 строк, registry 1 025)
- **Causal catalog** (7 файлов): Difference-in-Differences, Regression Discontinuity Design, Structural Causal Models, Structural Time Series, HTE (Causal Forest, Policy Tree)
- **Econometrics catalog** (5 файлов): Instrumental Variables (2SLS, GMM), Panel Data, Time Series
- Backends (JAX, NumPy), type system, units, testing infrastructure

**Calibration:** MVP calibrator — parameter optimization с convergence; fidelity control (fluid/relaxed/hard); calibration → uncertainty envelope adapter.

**Agent Simulation:** пошаговая симуляция (6 step-файлов); адаптивные агенты; agent artifact persistence; MetricsCollector + ExperimentTracker (agent_sim/); plugin system — PluginRegistry, CompositeExecutor.

**Distributional Analysis:** Gini coefficient, Palma ratio; cohort impact breakdown; negative value flagging.

**Числовая стабильность:** NaN/Inf guard; gradient health (JAX autodiff); JIT stability (PyTree) + JIT compilation tracker; deterministic merge; batch execution; kernel purity — сканирование на запрещённые I/O-операции в compile/execute.

### scientist/ — AI Orchestration (50 файлов)

AI-driven experiment orchestration: от design of experiments до governance и backtesting.

**Search & Optimization (14 файлов):**
- `SearchController` — two-stage filtering (cheap → expensive), stopping criteria
- **Strategies** (9 файлов): Bayesian optimization (BoTorch integration, Sobol cold-start); multi-objective optimization (Pareto front); random/grid search (deterministic seeds, exhaustion); batch generation; strategy adapter; parameter space codec (normalize/denormalize, Sobol sampling); resource arbiter (memory limits, process management)
- Adversarial/stress testing — negated objectives, worst-case search

**Governance (6 файлов):** norm execution — safe expression evaluation через AST policy; multi-pass validation pipeline; legal pass (NormPack compliance); equity pass (distributional equity); confidence pass (statistical thresholds).

**Design of Experiments (2 файла):** sensitivity plans (Morris screening, Sobol indices, guardrails для больших экспериментов); adversarial sampling (grid extreme corners, random tail).

**Agent Protocols & Decision System:** роли агентов (PI, Drafter, Formalizer, Critic); DecisionPacket v2/v3 с distributional и econometric секциями; DecisionCard; reflexion loop с failure cards и recovery; multi-agent workflow с critique.

**Backtesting & Causal Evaluation:** backtesting orchestrator с historical validation и trust scoring; causal evaluation node (observational data → causal effect); distributional analysis node; uncertainty propagation node.

**Infrastructure:** compiler; checkpoint/resume; idempotency; engine executor + default workflow; polyglot compute runner; flow node / LLM client instrumentation.

### integration/ — End-to-End (5 файлов)

Cross-layer сценарии через всю систему. Маркер: `@pytest.mark.integration`.

- **Workflow smoke** — полный pipeline: Trinity bundle → compilation → simulation → DecisionPacket
- **Calibration UDF** — калибровка с user-defined functions
- **Human gate audit** — human approval gate: GATE_REQUESTED/GATE_DECIDED события, audit trail, escalation workflow
- **LLM integration** — интеграция с языковыми моделями

### ir/ — IR Layer (8 файлов)

Промежуточное представление: загрузка, фрагменты, персистенция.

- Policy loaders — загрузка политик из различных форматов
- Trinity loaders — TrinityBundle loading
- Registry fragments — persistence, component-based fragments (Phase 19)
- **HTE + Backtest** — HTEResult (CATE, subgroup effects, feature importances), PolicyRecommendation (targeting rules, budget), BacktestReport (scenarios, metrics, trust grading)
- **UncertaintyEnvelope** — creation, validation (CI bounds), CAS round-trip с idempotency
- Query contracts

### lex/simulator/ — Legal Norm Simulator (3 файла)

Симуляция изменений в правовых нормах:

- **NormImpactAnalyzer** — сравнение NormPack версий, подсчёт added/removed/modified, report persistence в artifact store
- **Mutator** — создание мутаций с intent metadata (scenario, reason, requestor, ticket ref); deterministic pack IDs для одинаковых операций
- **Diff** — структурное сравнение NormPack, классификация: ADDED, REMOVED, MODIFIED, UNCHANGED

### performance/ (2 файла)

Benchmark-baseline regression checks с warmup runs:
- Каждая метрика сравнивается с зафиксированным baseline (`overhead_baseline.json`)
- Для каждой метрики задан отдельный регрессионный бюджет и абсолютный slack
- SLA-подход с фиксированными процентами к synthetic baseline больше не используется

### runtime/ (3 файла)

- Replay verification — воспроизведение simulation run с полным packet
- Manifest paths — relative path handling, портируемость артефактов между директориями

### demos/ (1 файл)

Запуск Laffer curve demo из `tools/demos/` через `runpy`.

## Тестовая инфраструктура

### conftest.py — глобальная конфигурация

```python
# JAX → CPU для консистентности в CI/CD
os.environ["JAX_PLATFORMS"] = "cpu"
os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"

# Loguru → только ошибки (с fallback на stdlib logging)
logger.remove()
logger.add(lambda msg: print(msg), level="ERROR")
```

Также добавляет `policy-engine/src` в `sys.path`.

### Специализированные conftest

| Файл | Фикстуры |
|------|----------|
| `core/phase0/conftest.py` | OTel in-memory exporter, `FileSystemCAS`, `ProducerInfo`, singleton reset |
| `scientist/conftest.py` | OTel setup, `MetricsRegistry` reset |
| `fabric/connectors/conftest.py` | Connector protocol fixtures |
| `foundry/methods/conftest.py` | Shared units (UAH, kWh), slots (income, tax, effective_rate) |
| `scientist/search/strategies/conftest.py` | Search space fixtures, evaluation helpers |

### Маркеры

- `@pytest.mark.integration` — медленные end-to-end тесты; в CI запускаются отдельно

## Запуск тестов

```bash
# Все тесты
pytest

# Без интеграционных (быстрый цикл)
pytest -m "not integration"

# По модулю
pytest tests/fabric/ -v
pytest tests/foundry/methods/ -v
pytest tests/scientist/search/strategies/ -v

# С покрытием
pytest --cov=polisyos --cov-report=html

# Конкретный тест с развёрнутым traceback
pytest tests/foundry/test_calibrator_mvp.py -v --tb=long
```

## Связи с исходным кодом

| Тесты | Исходный код |
|-------|-------------|
| `tests/core/phase0/` | `src/polisyos/core/` — artifacts, observability, contracts |
| `tests/contract/` | `src/polisyos/ir/` + `src/polisyos/core/contracts/` |
| `tests/fabric/` | `src/polisyos/fabric/` — connectors, catalog, claims, world |
| `tests/foundry/` | `src/polisyos/foundry/` — methods, calibration, agent_sim |
| `tests/scientist/` | `src/polisyos/scientist/` — search, governance, doe |
| `tests/ir/` | `src/polisyos/ir/` — kernel, world, linker |
| `tests/lex/` | `src/polisyos/lex/` — simulator, corpus |
| `tests/runtime/` | `src/polisyos/runtime/` |
| `tests/integration/` | Cross-layer: все модули |
| `tests/performance/` | Cross-layer: foundry + core |

## Архитектурные инварианты

Следующие инварианты активно проверяются тестами:

| Инвариант | Где проверяется |
|-----------|----------------|
| Граф зависимостей: `core → runtime → ir → fabric → foundry → scientist` | `test_arch_import_gate` |
| Публичные фасады определяют `__all__`, нет star-imports | `test_public_api_facades` |
| IR-контракты — источник истины, экспорт в JSON Schema | `contract/` |
| `FabricResult` всегда содержит `evidence_ref` | `fabric/` |
| Калибровки предоставляют оценки неопределённости | `foundry/`, `ir/test_uncertainty` |
| Overhead: simulation <2%, CAS I/O <5%, calibration <3% | `performance/` |
| Kernel модули не содержат I/O-операций | `foundry/test_no_io_kernel` |
| Merge и batch операции детерминистичны | `foundry/test_merge_determinism`, `test_runtime_batch` |
| Search loops converge или escalate | `scientist/search/` |

## Технологии

| Категория | Библиотеки |
|-----------|------------|
| Test runner | pytest, pytest-cov |
| Simulation | JAX, Equinox, Optax |
| Observability | OpenTelemetry SDK (in-memory exporter) |
| Data | pandas, PyArrow, NumPy |
| Databases | DuckDB, Kuzu (integration tests) |
| Validation | Pydantic v2 |
| Optimization | BoTorch (optional, Bayesian strategies) |
