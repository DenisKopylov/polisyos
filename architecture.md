# PolisyOS — AI-Driven Policy Operating System

**PolisyOS** (Policy Engine) — операционная система для проектирования, валидации, калибровки и исполнения публично-политических интервенций как воспроизводимых вычислительных экспериментов. Система принимает запрос на естественном языке, формулирует политику через иерархию AI-агентов, компилирует её в дифференцируемую JAX-симуляцию, проводит governance-проверки и выдаёт пакет решений с полным provenance-следом.

**Architecture:** v2.6.0 · **Python:** >=3.11 · **License:** proprietary · **Актуально:** 3 марта 2026

---

## Содержание

- [Обзор архитектуры](#обзор-архитектуры)
- [Граф зависимостей](#граф-зависимостей)
- [Модули](#модули)
  - [Common — инфраструктурный фундамент](#common--инфраструктурный-фундамент)
  - [Core — фундаментальная инфраструктура](#core--фундаментальная-инфраструктура)
  - [IR — промежуточное представление](#ir--промежуточное-представление)
  - [Fabric — Unified Data Fabric](#fabric--unified-data-fabric)
  - [Foundry — JAX Execution Engine](#foundry--jax-execution-engine)
  - [Runtime — HTTP API, Control Plane и жизненный цикл](#runtime--http-api-control-plane-и-жизненный-цикл)
  - [Lex — юридический анализ и нормативные знания](#lex--юридический-анализ-и-нормативные-знания)
  - [Scholar — обогащение знаний](#scholar--обогащение-знаний)
  - [Academic — академический knowledge graph](#academic--академический-knowledge-graph)
  - [Datasets — каталог статистических данных](#datasets--каталог-статистических-данных)
  - [Scientist — AI-оркестрация](#scientist--ai-оркестрация)
  - [Batch Common — общая batch-инфраструктура](#batch-common--общая-batch-инфраструктура)
  - [Packs — компонентные пакеты](#packs--компонентные-пакеты)
- [Сквозные подсистемы](#сквозные-подсистемы)
- [Ключевые концепции](#ключевые-концепции)
- [Архитектурные инварианты (Laws)](#архитектурные-инварианты-laws)
- [Технологический стек](#технологический-стек)
- [Security и Multi-Tenancy](#security-и-multi-tenancy)
- [Quickstart](#quickstart)
- [Тестирование](#тестирование)
- [Инструменты разработчика](#инструменты-разработчика)
- [Observability и Ops](#observability-и-ops)
- [Frontend](#frontend)
- [Schemas и ABI](#schemas-и-abi)
- [Данные](#данные)
- [Документация](#документация)

---

## Обзор архитектуры

Система реализует компиляторную трубу от запроса на естественном языке до воспроизводимого пакета решений:

```
NL intent (пользовательский запрос)
  → Scientist (AI-агенты: PI → Drafter → Formalizer → Critic + governance)
    → IR (Trinity контракты: ProblemFrame / PolicySpec / ModelSpec + kernel registries)
      → Fabric (connectors, docs, claims, world model, retrieval, data plane, evidence, provenance)
        → Academic (OpenAlex → SKG → literature priors, causal evidence, transportability-aware параметры)
        → Datasets (statistics → catalog → P*(Z) transportability, proxy resolution)
        → Foundry (compile → calibrate → simulate → uncertainty; чистый JAX, patch-based)
          → Runtime (HTTP API v1 + Control Plane, replay, audit trail, artifact refs)
            → Decision Artifacts (DecisionPacket / DecisionCard / GovernanceReport)
```

Сквозные подсистемы:
- **Lex**: юридические документы → corpus → NormPack → legality evaluation → what-if simulator → offline knowledge graph (batch pipeline + vector search)
- **Scholar**: внешние источники → docs → claims → trust → KnowledgeBundle (обогащение Fabric/IR) + freshness management
- **Academic**: OpenAlex → batch pipeline → DuckDB SKG → ScholarKnowledgeGraph + ParameterSelector (transportability-aware literature priors и causal evidence)
- **Datasets**: статистические источники → batch pipeline → DuckDB каталог → DatasetCatalogGraph + DatasetRegistry (hybrid search, P*(Z) transportability, proxy resolution)
- **Batch Common**: общая инфраструктура batch-пайплайнов (snapshot layout, manifests, QC helpers, thermal pacing)
- **Packs**: встроенные доменные компоненты (IR-фрагменты, Foundry-методы, Lex-оценщики, Scholar-экстракторы)
- **Security**: Zero Trust, multi-tenant isolation, OPA policies, TEE attestation, SBOM, SLSA

---

## Граф зависимостей

Зависимости строго однонаправлены (Law A). `A → B` означает «A зависит от B»:

```
                                ┌──────────┐
                                │ common   │  ← нет зависимостей вверх
                                └────┬─────┘
                                     │
                       ┌─────────────┼──────────────┐
                       │             │              │
                  ┌────▼────┐  ┌─────▼──────┐  ┌───▼───┐
                  │  core   │  │batch_common│  │  ir   │  (чистые контракты)
                  └────┬────┘  └─────┬──────┘  └───┬───┘
                       │             │             │
            ┌──────────┼─────────────┼─────────────┤
            │          │             │             │
       ┌────▼────┐ ┌───▼─────┐      │       ┌─────▼───┐
       │ fabric  │ │ foundry │      │       │ runtime │
       └────┬────┘ └───┬─────┘      │       └────┬────┘
            │          │             │            │
  ┌─────────┼──────────┤─────────────┤            │
  │         │          │             │            │
┌─▼──┐ ┌───▼───┐ ┌────▼────┐ ┌─────▼────┐       │
│lex │ │scholar│ │academic │ │ datasets │       │
└─┬──┘ └───┬───┘ └────┬────┘ └─────┬────┘       │
  │         │          │            │            │
  └─────────┴──────────┴────────────┼────────────┘
                                    │
                             ┌──────▼──────┐
                             │  scientist  │  (оркестрация верхнего уровня)
                             └──────┬──────┘
                                    │
                             ┌──────▼──────┐
                             │    packs    │  (листовой модуль, только реализации)
                             └─────────────┘
```

| Модуль | Зависит от | Документация |
|--------|-----------|--------------|
| `polisyos.common` | — | [README](policy-engine/src/polisyos/common/README.md) |
| `polisyos.batch_common` | common | — |
| `polisyos.core` | common | [README](policy-engine/src/polisyos/core/README.md) |
| `polisyos.ir` | — (core только TYPE_CHECKING) | [README](policy-engine/src/polisyos/ir/README.md) |
| `polisyos.fabric` | ir, core, common | [README](policy-engine/src/polisyos/fabric/README.md) |
| `polisyos.foundry` | ir, core, common | [README](policy-engine/src/polisyos/foundry/README.md) |
| `polisyos.runtime` | core, common | [README](policy-engine/src/polisyos/runtime/README.md) |
| `polisyos.lex` | fabric, ir, core, common | [README](policy-engine/src/polisyos/lex/README.md) |
| `polisyos.scholar` | fabric, ir, core, common | [README](policy-engine/src/polisyos/scholar/README.md) |
| `polisyos.academic` | batch_common, ir, core, common | [README](policy-engine/src/polisyos/academic/README.md) |
| `polisyos.datasets` | batch_common, fabric, ir, core, common | [README](policy-engine/src/polisyos/datasets/README.md) |
| `polisyos.scientist` | ir, fabric, foundry, runtime, lex, academic, datasets, core, common | [README](policy-engine/src/polisyos/scientist/README.md) |
| `polisyos.packs` | core, ir, foundry, lex, fabric, common | [README](policy-engine/src/polisyos/packs/README.md) |

---

## Модули

### Common — инфраструктурный фундамент

> `src/polisyos/common/` · [README](policy-engine/src/polisyos/common/README.md) · Нулевые зависимости на polisyos

Самый нижний слой: кросс-модульные утилиты без доменной логики. Импортируется всеми остальными модулями.

| Модуль | Назначение |
|--------|-----------|
| **config.py** | Side-effect при импорте: устанавливает безопасные env defaults (JAX CPU, потоки, DuckDB, Torch). Критично: импортировать до `import jax` |
| **logger.py** | `get_logger(name)` с привязкой `trace_id`/`span_id` из OpenTelemetry. Graceful fallback на stdlib logging |
| **jax_env.py** | Защита от Metal backend на macOS (переключение на CPU) |
| **async_tools.py** | `run_coro_sync()` для безопасного вызова корутин из синхронного кода |
| **serialization.py** | `to_python_data()`, `stable_json_dumps()`, `strip_none()` для нормализации Enum/dataclass/Pydantic/numpy в python-friendly вид |
| **timestamps.py** | Единые UTC-утилиты: `utc_now`, parse/format ISO, epoch conversion |
| **[migrations/](policy-engine/src/polisyos/common/migrations/README.md)** | Детерминированная система миграций артефактов с обнаружением циклов. Текущая миграция: `dataset_manifest` 0.9→1.0 |

---

### Core — фундаментальная инфраструктура

> `src/polisyos/core/` · [README](policy-engine/src/polisyos/core/README.md) · Зависимости: common

Общий инфраструктурный слой для всех подсистем. Организован в четыре архитектурных плоскости:

1. **ABI plane** — типизированные контракты между модулями
2. **Data/provenance plane** — CAS-хранилище, трассировка, аудит
3. **Plugin plane** — компонентная модель, discovery, registry
4. **Runtime-quality plane** — безопасность, observability, resilience

```
core/
├── artifacts/      # CAS + манифесты + подписи + environment fingerprint + dependency graph
├── audit/          # Портативные аудит-пакеты и офлайн-верификация (PROV + SLSA)
├── backends/       # Унифицированный dispatcher backend-реализаций
├── cache/          # Потокобезопасные LRU/TTL кэши
├── canon/          # Канонический JSON + хеширование (float→Decimal, sorted keys)
├── compiler/       # Отчёты компиляции/линковки в CAS
├── components/     # Component Model v1 (metadata/discovery/registry/bootstrap)
├── contracts/      # Typed ABI между модулями (14 доменов)
├── discovery/      # Базовые примитивы discovery (entry points + file modules)
├── errors/         # Унифицированная PolicyOSError + категории
├── evaluation/     # Взвешенный scoring + threshold mapping
├── governance/     # Validation profiles + legal/safety passes
├── llm/            # Трассируемый LLM client + оценка стоимости + retry facade
├── observability/  # Tracing, metrics, context propagation, structured logs
├── pipeline/       # Линейные и DAG pipeline-примитивы
├── registry/       # Сборка/загрузка registry bundles из IR-фрагментов
├── resilience/     # Общая retry-политика с backoff/jitter
├── run/            # RunContext + RunManifest lifecycle
├── security/       # Zero Trust: tenant isolation, authn/authz, audit chain, TEE, SBOM, SLSA
└── trace/          # TraceRecord и sink'и (JSONL/composite)
```

#### Ключевые подсистемы Core

| Подсистема | Назначение |
|------------|-----------|
| **[artifacts/](policy-engine/src/polisyos/core/artifacts/README.md)** | Content-Addressable Storage (SHA-256), Ed25519 подписи, EnvironmentManifest, dependency graph traversal |
| **[audit/](policy-engine/src/polisyos/core/audit/README.md)** | Портативные `.polisyos-audit.tar.gz` пакеты с W3C PROV-JSON, standalone 5-шаговая офлайн-верификация, SLSA attestation |
| **[components/](policy-engine/src/polisyos/core/components/README.md)** | Component Model v1: `namespace.name@semver`, discovery через entry points (8 групп), thread-safe registry, compliance |
| **[contracts/](policy-engine/src/polisyos/core/contracts/README.md)** | 14 доменов typed ABI: Fabric, Foundry, Trinity, Lex, Scientist, Scholar, Runtime, Control, Provenance, Causal, HTE, Backtest, Uncertainty, Distributional |
| **[governance/](policy-engine/src/polisyos/core/governance/README.md)** | Validation profiles (`FAST`/`MVP`/`STRICT`), validator passes (safety/legal), AST policy whitelisting, pluggable legal backends (stub, expr_ast) |
| **[llm/](policy-engine/src/polisyos/core/llm/README.md)** | `TracedLLMClient` — OTel spans + token usage + cost tracking + retry facade. Нормализация ответов из разных LLM-провайдеров |
| **[observability/](policy-engine/src/polisyos/core/observability/README.md)** | OTel tracing (`@traced`), Prometheus MetricsRegistry, DeterminismTier (5 уровней), LLM cost estimation, graceful degradation |
| **[registry/](policy-engine/src/polisyos/core/registry/README.md)** | `GenericRegistry` + `BaseRegistry` с secondary indices. Bundle building/loading из CAS. Compose bundles из IR fragment-компонентов с precedence policy |
| **[security/](policy-engine/src/polisyos/core/security/README.md)** | Zero Trust: tenant routing, DB isolation (PostgreSQL RLS / DuckDB), SPIFFE identity, OPA authz, delegation tokens, audit chain, TEE attestation, SBOM (CycloneDX), SLSA |

---

### IR — промежуточное представление

> `src/polisyos/ir/` · [README](policy-engine/src/polisyos/ir/README.md) · Независимый контрактный слой

Каноническое декларативное представление политик. IR определяет **только модели и валидацию** (Pydantic, `frozen=True`, `extra="forbid"`) — без логики исполнения. IR не зависит от `polisyos.core` (только `TYPE_CHECKING`).

```
Scholar / Scientist / Lex
          │ формируют и читают контракты
          ▼
    polisyos.ir (schemas + validation + linking)
          │
          ├─► Foundry (compile/execute Trinity)
          ├─► Fabric  (world/facts/citations contracts)
          └─► Core    (registry/contract wiring)
```

#### Trinity-контракты (центральная абстракция)

| Артефакт | Вопрос | Содержание |
|----------|--------|-----------|
| **ProblemFrame** | **Why** — зачем | Домен (11 типов: fiscal, social, environmental...), KPI, objectives, success criteria, constraints, stakeholders |
| **PolicySpec** | **What** — что делать | Интервенции, mechanism bindings, tunable parameters, selector expressions (AST, max depth=10, max nodes=50) |
| **ModelSpec** | **How** — как моделировать | Data snapshot ref, agent config, assumptions, fidelity level (surrogate → full_discrete) |

`TrinityBundle` объединяет все три в единый артефакт с `schema_version` (текущая: `1.0`).

#### Подсистемы IR

| Подсистема | Назначение |
|------------|-----------|
| **[trinity/](policy-engine/src/polisyos/ir/trinity/README.md)** | Канонический формат `TrinityBundle`, strict loaders для dict/str/bytes (json/yaml/auto), version enforcement |
| **[governance/](policy-engine/src/polisyos/ir/governance/README.md)** | Контракты ProblemFrame/PolicySpec, selector AST, schedules, gate protocol (`GateRequest`/`GateDecision`/`GateEvent`) |
| **[kernel/](policy-engine/src/polisyos/ir/kernel/README.md)** (13 файлов) | Фундаментальные реестры: mechanisms, slots, units, constraints, metrics, merge rules, trust, selector fields. Типы: `KernelModel`, `DecimalValue`, `MoneyValue`, `RateValue`. Запрет float через `reject_float()` |
| **[world/](policy-engine/src/polisyos/ir/world/README.md)** (10 файлов) | Семантическая модель: Claim, WorldEvent (W3C PROV), ConflictSet, DocFragment, QualityReport, TrustAssessment. Deterministic content-addressed IDs (`<prefix>.sha256_<hex64>`) |
| **[linker/](policy-engine/src/polisyos/ir/linker/README.md)** | Валидация TrinityBundle vs kernel-реестров → `LinkedTrinityBundle` + `LinkReport`. Покрытие: механизмы, параметры, slots, selectors, constraints, merge rules, schedule overlap |
| **[analytics/](policy-engine/src/polisyos/ir/analytics/README.md)** | Контракты отчётов: `UncertaintyEnvelope`, `CausalEffectReport`, `HTEResult`, `DistributionalReport`, `BacktestReport`, `CalibrationConfig`, `NormApplicability`, `DataViewRequest` + CAS I/O (`persist_*`/`load_*`) |
| **[artifacts/](policy-engine/src/polisyos/ir/artifacts/README.md)** | Унифицированный CAS I/O: `ArtifactID` (sha256:<64hex>), `ArtifactStore` protocol, `put_json_artifact`/`get_json_artifact` |
| **[migrations/](policy-engine/src/polisyos/ir/migrations/README.md)** | Runtime миграции canonical payload. Текущая: `policy_ir 1.0→1.0` (identity). Cycle protection, major-version guard |
| **registry_fragments.py** | Композиция `RegistryBundle` из фрагментов с политиками: `error_on_conflict` / `prefer_higher_priority` |

---

### Fabric — Unified Data Fabric

> `src/polisyos/fabric/` · [README](policy-engine/src/polisyos/fabric/README.md) · Зависимости: ir, core, common

Полный жизненный цикл данных: от внешних источников через ingestion и обработку до queryable World Model. Включает подсистемы retrieval (разрешение data needs по метрикам) и data plane (оркестрация режимов ingestion).

```
External APIs / Documents
        |
        v
connectors + docs + claims  (extraction, normalization, conflict resolution)
        |
        v
Fact Log (segments + manifests, append-only)
        |
        v
World materialization (DuckDB, optional Kuzu)
        |
        v
world_query / bridge API (type-safe SQL, column guards)
```

#### Подсистемы Fabric

| Подсистема | Назначение |
|------------|-----------|
| **[connectors/](policy-engine/src/polisyos/fabric/connectors/README.md)** | Protocol-based коннекторы (`SourceConnector`). CAS-кэш, resilience (circuit breaker, retry, rate limiter, fallback), federation (cross-source query), quality validation, DAG transform pipeline. 10 entry points: WorldBank, Eurostat, UKONS, SDMX, CKAN Catalog/Resource, Socrata, OpenDataSoft, SPARQL, REST JSON |
| **[docs/](policy-engine/src/polisyos/fabric/docs/README.md)** | Pipeline обработки документов: `ingest → normalize → structure → chunk`. Поддержка `text/plain`, `text/html`; PDF backend опционален |
| **[claims/](policy-engine/src/polisyos/fabric/claims/README.md)** | Extraction (pluggable backends) → Normalization → Conflict Detection → Resolution → Fact Log. Trust/quality scoring для claims и документов |
| **[world/](policy-engine/src/polisyos/fabric/world/README.md)** | Store: emit/validate/persist фактов в CAS. Materialize: инкрементальная загрузка в DuckDB (13+ таблиц), проекции, optional Kuzu граф. Merge-стратегии: `ERROR_ON_CONFLICT`/`PREFER_NON_NULL_LAST_TX`/`LAST_TX`/`FIRST_TX` |
| **[catalog/](policy-engine/src/polisyos/fabric/catalog/README.md)** | Metric-level контракты с hash-locked bindings, fuzzy/exact search, disambiguation, PII-классификация. Fast-lane resolver + source bindings для deterministic resolve |
| **[data_plane/](policy-engine/src/polisyos/fabric/data_plane/README.md)** | Оркестрация режимов ingestion: `batch_incremental` (cursor-based), `record` (HTTP fixture capture), `replay` (детерминированное воспроизведение), `streaming_windowed`. CursorStore, watermark policies, regression comparison |
| **[retrieval/](policy-engine/src/polisyos/fabric/retrieval/README.md)** | Гибридное разрешение data needs: FastLane (curated bindings) → ExploreLane fallback (live discovery) → preview gate → execution → promotion candidates. Используется control/NL flows |
| **provenance/** | W3C PROV-O lineage: ProvenanceCoreGraph с BFS-поиском предков, экспорт в JSON-LD |
| **pii/** | PII-сканирование (Presidio + regex fallback) для ingestion pipeline |

#### Ключевые API Fabric

- `run_connectors_ingestion(...)` — полный цикл: fetch → transform → cache → CAS → provenance → evidence
- `execute_world_query(...)` / `query_world_table(...)` — типобезопасные SQL-запросы к materialized World Model
- `fabric_get_data(...)` — синхронный мост (`_connector_bridge.py`) для верхних слоёв
- `RetrievalService.resolve(...)` — разрешение metric-based data needs (FastLane → ExploreLane)
- `run_orchestrated_ingestion(...)` — data plane: fetch + optional snapshot assembly

#### Feature flags Fabric

| Флаг | Назначение |
|------|-----------|
| `POLISYOS_RETRIEVAL_FASTLANE_ENABLED` | Deterministic resolve через source bindings |
| `POLISYOS_RETRIEVAL_EXPLORE_ENABLED` | Live discovery для unresolved metrics |
| `POLISYOS_RETRIEVAL_PROMOTION_ENABLED` | Queueing promotion candidates |
| `POLISYOS_RETRIEVAL_PROMOTION_PERSIST` | Persist promoted bindings |

---

### Foundry — JAX Execution Engine

> `src/polisyos/foundry/` · [README](policy-engine/src/polisyos/foundry/README.md) · Зависимости: ir, core, common

Высокопроизводительный execution engine для дифференцируемого исполнения политик. **Чистый JAX/Equinox** — никаких БД, LLM или сетевых вызовов (Law B).

```
ir.trinity_bundle + registry_bundle
          |
          v
  foundry.compile → ProgramGraph + ExecPlan + SlotLayout + TreasuryPlan
          |
          v
  foundry.data_plane → input bindings + bound StateSnapshot
          |
          v
  foundry.execute → StateDelta + Metrics + StateSnapshot + SimulationResult
```

#### Ключевой execution pipeline

1. **compile/** — Trinity IR → `ProgramGraph` DAG → `ExecPlan` (topological order) + compile-time conflict check + cost gating
2. **data_plane/** — связь `DataSnapshot` с `SlotRegistry`, материализация bound `StateSnapshot`
3. **execute/** — разрешение входных данных, `execute_program_graph`, `StateDelta` → новый `StateSnapshot` + `SimulationResult`
4. **executor** (ядро) — topological traversal → selector evaluation → mechanisms → patch collection → CRDT merge → constraint check

#### Встроенные механизмы

- **IncomeTax / TaxSubsidy** — фискальные инструменты с sector-targeting
- **LaborMarketMechanism** — вероятностное распределение занятости
- **QueueMechanism** — три fidelity (fluid/relaxed/hard-discrete)
- **AdaptiveAgentMechanism** — нейросетевые агенты (Equinox MLP)

#### Крупные подсистемы Foundry

| Подсистема | Назначение |
|------------|-----------|
| **[methods/](policy-engine/src/polisyos/foundry/methods/README.md)** | Декларативный фреймворк методов: protocol, registry, DAG-composition, JAX/NumPy/Solver backends. Каталог (`methods/catalog/`): [causal/](policy-engine/src/polisyos/foundry/methods/catalog/causal/README.md) — SCM, DiD, RDD, CATE, DML, Meta-Learners, PolicyTree, Structural Time Series, DAGMA discovery, symbolic identification (y0/R), CI backend selection (auto\|numpy\|jax), full transport bridge; [econometrics/](policy-engine/src/polisyos/foundry/methods/catalog/econometrics/) — Panel FE/RE, IV, ARIMA/VAR; [optimization/](policy-engine/src/polisyos/foundry/methods/catalog/optimization/) — OR-Tools/PuLP. Legacy пути `methods/{causal,econometrics,optimization}` сохранены как facade. Регистрация через `_registry_boot.py`. Golden-record regression testing |
| **[agent_sim/](policy-engine/src/polisyos/foundry/agent_sim/README.md)** | Гетерогенная агентная симуляция: RL (PPO/CMA-ES/VFI/MPC), actor-critic (Equinox), графовые механизмы (social influence, diffusion, lending), демография (рождение/смерть/миграция/наследство), temporal dynamics, distribution-aware rewards. `PureExecutor → DistributionAwareExecutor → GraphAwareExecutor → PopulationAwareExecutor` |
| **[calibration/](policy-engine/src/polisyos/foundry/calibration/README.md)** | Градиентная калибровка на реальных данных: Adam/optax, bijector constraints, multi-target GradNorm, early stopping, Laplace-approximation uncertainty (Hessian) → `CalibrationReport` + `UncertaintyEnvelopes` |
| **[plugins/](policy-engine/src/polisyos/foundry/plugins/README.md)** | Plugin-архитектура для доменных симуляций. `PolisySimulator` high-level API, composite multi-domain execution. Reference: EconomicsPlugin |
| **[uncertainty/](policy-engine/src/polisyos/foundry/uncertainty/README.md)** | Propagation неопределённости: Delta Method (JAX Jacobian) → Monte Carlo fallback → агрегация. Auto-select: delta если differentiable, иначе MC sampling. Результат: `UncertaintyEnvelope` per metric |
| **analysis/** | Distributional impact: Gini, Palma, quintile breakdowns, winners/losers |

#### Fidelity Levels

| Уровень | Градиенты | Описание |
|---------|----------|----------|
| `SURROGATE_FLUID` | Полные | Непрерывные потоки (уравнения) |
| `RELAXED_DISCRETE` | Приближенные | Сглаженные события (Softmax/Sigmoid) |
| `HARD_DISCRETE` | Нет | Честная дискретная симуляция |

#### Инварианты Foundry

- **Patch-first:** механизмы эмитят патчи, а не мутируют состояние напрямую
- **Merge-rule driven:** финальная запись в слот определяется `SUM/OVERRIDE/PRIORITY/ERROR` правилами
- **Artifact-first:** все этапы фиксируются в CAS ссылками
- **Determinism by design:** seed-driven execution + `TreasuryPlan` + environment fingerprint

---

### Runtime — HTTP API, Control Plane и жизненный цикл

> `src/polisyos/runtime/` · [README](policy-engine/src/polisyos/runtime/README.md) · [HTTP](policy-engine/src/polisyos/runtime/http/README.md) · [Services](policy-engine/src/polisyos/runtime/http/services/README.md) · Зависимости: core, common

Runtime HTTP API v1 для интроспекции прогонов и артефактов + полноценный Control Plane для запуска экспериментов, управления данными и Lex pipeline.

#### Runtime HTTP API v1 (FastAPI)

```
HTTP request → app.py (FastAPI) → telemetry middleware → [security chain] → routes → services → CAS + runs dir
```

| Группа | Endpoints | Методы |
|--------|-----------|--------|
| **Health** | `/health`, `/ready`, `/api/v1/health` | GET |
| **Runs** | `/api/v1/runs`, `/runs/{id}`, `/runs/{id}/timeline`, `/runs/{id}/nodes`, `/runs/{id}/lineage`, `/runs/{id}/agents`, `/runs/{id}/workflow` | GET |
| **Debug** | `/api/v1/debug/runs/{id}/nodes/{alias}`, `/debug/runs/{id}/governance`, `/debug/runs/{id}/errors` | GET |
| **Artifacts** | `/api/v1/artifacts/{id}`, `/artifacts/{id}/content`, `/artifacts/{id}/lineage`, `/artifacts/{id}/schema` | GET |
| **Control — Runs** | `/api/v1/control/run/launch`, `/control/run/launch-nl` | POST |
| **Control — Data** | `/api/v1/control/data/ingest`, `/data/resolve`, `/data/discover`, `/data/preview`, `/data/catalog/search`, `/data/index/stats`, `/data/promotion/candidates`, `/data/promotion/approve`, `/data/promotion/reject` | POST/GET |
| **Control — Connectors** | `/api/v1/control/connectors`, `/connectors/profiles`, `/connectors/cache/status` | GET |
| **Control — Lex** | `/api/v1/control/lex/trigger`, `/lex/status`, `/lex/stats`, `/lex/search` | POST/GET |
| **Control — Models** | `/api/v1/control/models/profiles` | GET |

OpenAPI-спецификация: `schemas/runtime_api_v1.openapi.json`.

#### Services

| Сервис | Назначение |
|--------|-----------|
| **run_index** | Кэшированный индекс прогонов из `core_runs_root` (TTL 2s) |
| **timeline** | Парсинг `trace.jsonl` → упорядоченные события, статистика кэша |
| **debug** | Node debug, governance debug, agent pipeline, workflow graph, redaction sensitive полей |
| **lineage** | Dependency graph traversal через CAS |
| **artifact_inspector** | Manifest/content/schema/lineage для CAS артефактов, preview limit 64KiB |
| **control** | Оркестрация: запуск workflow/NL, ingestion, retrieval, connectors/profiles/cache, Lex batch trigger/status/stats/search |
| **task_runner** | In-process `ThreadPoolExecutor` для background операций |

#### Security chain (optional)

При включении: JWT authentication → Cell router (tenant→cell routing) → OPA authorization (enforce / shadow mode) → per-route resource context + tenant checks.

Redaction: `token`, `password`, `authorization` и другие sensitive поля автоматически маскируются в debug-ответах.

#### Replay API

- `build_replay_plan()` — обнаружение стратегии (`foundry`/`scientist`/`none`)
- `completeness_check()` — классификация: `complete`/`recoverable`/`incomplete`
- `verify_replay()` — режимы: `bit_exact` (artifact ID equality), `ci_bounded` (metric drift tolerance), `skip`

#### Feature flags Runtime

| Флаг | Назначение |
|------|-----------|
| `POLISYOS_LLM_MULTIMODEL_ENABLED` | Multi-model LLM profiles в NL launch |
| `POLISYOS_REQUIRED_PREFLIGHT_ENABLED` | Обязательный preflight перед simulation |
| `POLISYOS_AUTO_MATERIALIZATION_ENABLED` | Auto-materialize world после ingestion |
| `POLISYOS_UNIFIED_DAG_ENABLED` | Unified DAG workflow |

---

### Lex — юридический анализ и нормативные знания

> `src/polisyos/lex/` · [README](policy-engine/src/polisyos/lex/README.md) · Зависимости: fabric, ir, core, common

Два контура работы с нормативными документами:

**Контур 1 — Online compliance:**

```
raw bytes → corpus.ingest → corpus.structure → corpus.versioning
                                                       │
                        normpack.assemble_norm_pack  ◄──┘
                                │
                   legal_evaluation.evaluate_legality
                         │               │
                  LegalReportRef    ChangeProposalRef

                    simulator (отдельный путь)
        old NormPack → mutator → diff → engine → NormImpactReport
```

**Контур 2 — Offline knowledge graph (ЄДРНПА):**

```
XML corpus → batch pipeline (parse → structure → SPO extraction → graph → embed)
                    │
                    v
         DuckDB (lex_knowledge_graph.duckdb) + HNSW/NPZ indices
                    │
                    v
         LegalKnowledgeGraph (vector / text / hybrid search)
```

#### Подсистемы Lex

| Подсистема | Назначение |
|------------|-----------|
| **[corpus/](policy-engine/src/polisyos/lex/corpus/README.md)** | Загрузка документов через `fabric.docs`, парсинг юридической структуры (UA/RU/EN юрисдикции: статьи → части → пункты → подпункты), `ProvisionIndex`, `VersionIndex`. Поддержка merge-политик обновления метаданных |
| **[normpack/](policy-engine/src/polisyos/lex/normpack/README.md)** | Сборка NormPack: select sources → select provisions → extract claims → resolve conflicts → claims_to_norm_rules. Два пути: Provider (статический NormPack) или Pipeline (полная сборка). Pluggable providers через entry points `polisyos.norm_pack_providers` |
| **[legal_evaluation/](policy-engine/src/polisyos/lex/legal_evaluation/README.md)** | Rule-by-rule проверка `PolicySpec + SimulationResult` против `NormPack`. Pluggable evaluator backends, unit conversion (`percent↔ratio`, `km↔m`), авто-генерация `ChangeProposal` (JSON Patch) для FAIL findings |
| **[simulator/](policy-engine/src/polisyos/lex/simulator/README.md)** | What-if анализ: `NormPackMutator` (fluent API: add/remove/replace/modify norms), `diff_norm_packs()` (field-level deltas), `NormImpactAnalyzer` (governance passes на обоих пакетах → compliance deltas, affected KPIs) |
| **[batch/](policy-engine/src/polisyos/lex/batch/README.md)** | Offline pipeline для построения legal knowledge graph из XML корпуса (ЄДРНПА). Стадии: `parse → structure → spo → graph → embed`. Sharding, resume, quality gates. OpenAI Batch API для embeddings |
| **[knowledge/](policy-engine/src/polisyos/lex/knowledge/README.md)** | Read-only доступ к legal knowledge graph. `LegalKnowledgeStore` (DuckDB read_only + HNSW indices). `LegalKnowledgeGraph` — high-level API: vector/text/hybrid search по entities, facts, provisions. Graph traversal (`find_related_entities`) |

Точки расширения: entry points `polisyos.norm_pack_providers`, `polisyos.lex_evaluators`, `polisyos.lex_extractors`.

---

### Scholar — обогащение знаний

> `src/polisyos/scholar/` · [README](policy-engine/src/polisyos/scholar/README.md) · Зависимости: fabric, ir, core, common

Преобразование сырых источников (URL, файлы, байты) в структурированные `KnowledgeBundle` через 8-стадийный pipeline:

| # | Стадия | Что делает |
|---|--------|-----------|
| 1 | **validate** | Проверка `ResearchIntent` (`domain` + `seed_sources` обязательны) |
| 2 | **discover** | Каноникализация URL (lower host/scheme, sort query), абсолютные пути, hash-identity для bytes, дедуп, лимит `max_docs` |
| 3 | **acquire** | HTTP fetch / file read / bytes, лимиты `max_bytes_per_doc` и `max_bytes_total` |
| 4 | **docs** | `ingest → normalize → structure → chunk` через Fabric (инкрементально — CAS-кэш пропускает готовые стадии) |
| 5 | **claims** | Bootstrap extractors через `core.components` + извлечение/нормализация claims с claim budget |
| 6 | **reconcile** | Conflict resolution, trust/quality calculation, winner selection |
| 7 | **filtering** | Отсев docs ниже `min_doc_trust_tier`, claims по `claim_targets` и цитируемым выбранным docs |
| 8 | **bundle** | Детерминированный `bundle_id` (SHA от intent + doc_version_ids + claim_ids + policy_ids), CAS persist, `KNOWLEDGE_BUNDLE_BUILD` world event |

#### Подсистемы Scholar

| Подсистема | Назначение |
|------------|-----------|
| **[discover/](policy-engine/src/polisyos/scholar/discover/README.md)** | Нормализация источников: canonical URL (lower-case scheme/host, sorted query), абсолютные пути для local files, hash-identity для bytes. Dedup по `source_identity_key`. HTTP fetch (urllib) и local file read с контролем лимитов |
| **[orchestrator/](policy-engine/src/polisyos/scholar/orchestrator/README.md)** | `enrich_topic()` — полный pipeline: validation → discover → acquire → docs → claims → reconcile → filter → bundle/persist. `compute_bundle_id()` — deterministic ID. `persist_bundle_and_event()` → CAS + world event |

#### Freshness подсистема

- `FreshnessPolicy.check()` — `fresh`/`stale`/`expired` с cooldown и `needs_refresh`
- Sidecar state (`FreshnessStateStore`) с file-lock для анти-штормовой защиты при конкурентном refresh
- Domain defaults: `fiscal`, `labor`, `health`, `infrastructure`, `education` + fallback

---

### Academic — академический knowledge graph

> `src/polisyos/academic/` · [README](policy-engine/src/polisyos/academic/README.md) · Зависимости: batch_common, ir, core, common

Офлайн-контур построения academic knowledge graph (AKG/SKG) на базе OpenAlex и read-only API для извлечения литературы, causal evidence и параметрических priors.

**Контур 1 — Ingestion/pipeline:**

```
relevant_topics_*.csv
  → openalex.topic_catalog + selector (diversity policy, impact/recency/method scoring)
    → batch: topic_select → harvest → parse → resolve_extract → merge_dedup
      → graph_load (DuckDB: ac_works, ac_parameter_estimates, ac_causal_claims, ac_skg_*)
        → graph_index → embed (HNSW + NPZ) → qc → publish
```

**Контур 2 — Query/runtime:**

```
DuckDB + HNSW → ScholarKnowledgeGraph (hybrid text+vector search, priors, causal evidence)
             → ParameterSelector (transportability-aware выбор параметров)
             → VariableCanonizer (deterministic canonical namespace + cache)
```

#### Подсистемы Academic

| Подсистема | Назначение |
|------------|-----------|
| **[batch/](policy-engine/src/polisyos/academic/batch/README.md)** | Стадийный pipeline: `topic_select → harvest → parse → resolve_extract → merge_dedup → graph_load → graph_index → embed → qc → publish`. `resolve_extract` объединяет concurrent fulltext fetch, one-call LLM extraction и deterministic publish gates. OpenAI Batch API для embeddings |
| **[knowledge/](policy-engine/src/polisyos/academic/knowledge/README.md)** | Read-only API: `ScholarKnowledgeGraph` (hybrid text+vector search), `SKGQuery` (edge priors, parameter candidates), `ParameterSelector` (transportability scoring через `ContextProfile`), `VariableCanonizer` (deterministic canonical namespace + cache в DuckDB). SKG versioning и retraction handling |
| **[openalex/](policy-engine/src/polisyos/academic/openalex/README.md)** | Интеграция с OpenAlex API: topic catalog из CSV, async HTTP client с rate limiting и retry, selection algorithm с diversity policy (max 5 per journal, max 2 per first author), TIER1/TIER2 priority filter |
| **trust.py** | Нормализация trust-score по дизайну исследования, цитируемости, свежести и sample size |

#### Ключевые API Academic

- `ScholarKnowledgeGraph.find_relevant_works(...)` — fusion text + vector search
- `ScholarKnowledgeGraph.get_parameter_prior(variable, domain, country)` — trust-weighted mean/std
- `ParameterSelector.select_for_context(...)` — transportability-aware выбор параметра
- `SKGQuery.query_edge_priors(...)` / `query_parameters(...)` — SKG graph API

#### DuckDB слой

Runtime tables: `ac_works`, `ac_parameter_estimates`, `ac_causal_claims`, `ac_causal_claims_raw`, `ac_boundary_conditions`, `ac_topics`, `ac_topic_selections`, `ac_article_extractions`.
SKG tables: `ac_skg_articles`, `ac_skg_variables`, `ac_skg_parameters`, `ac_skg_edges`, `ac_skg_versions`.

CLI: `python -m polisyos.academic.batch.cli run --snapshot-root <path>`.

---

### Datasets — каталог статистических данных

> `src/polisyos/datasets/` · [README](policy-engine/src/polisyos/datasets/README.md) · Зависимости: batch_common, fabric, ir, core, common

Слой построения и чтения каталога статистических датасетов. Два контура:

**Контур 1 — Batch:**

```
source_registry.yaml (waves A/B/C/D: SDMX, WorldBank, WVS, CKAN, UKONS, WHO, UNPD, ...)
  → batch: harvest → normalize (DatasetRecord, DCAT-like) → merge_dedup
    → graph_load (DuckDB: ds_datasets, ds_distributions)
      → graph_index → core_sources_ingest (optional: registry/alignments/observations)
        → embed (SentenceTransformer + HNSW) → qc → publish
```

**Контур 2 — Runtime:**

```
DuckDB + HNSW → DatasetCatalogGraph (hybrid vector+text search, metric/variable lookup)
             → DatasetRegistry (transportability: P*(Z), proxy resolution, confidence composition)
```

#### Подсистемы Datasets

| Подсистема | Назначение |
|------------|-----------|
| **[batch/](policy-engine/src/polisyos/datasets/batch/README.md)** | Staged pipeline: 9 стадий. Source registry с wave selection (A/B/C/D). `core_sources_ingest` опциональна (заполняет registry-таблицы для transportability). Resume и thermal pacing |
| **[knowledge/](policy-engine/src/polisyos/datasets/knowledge/README.md)** | Read-only API: `DatasetCatalogGraph` (hybrid vector+text search, metric/variable lookup), `DatasetRegistry` (transportability: `compute_p_star_z`, proxy resolution, confidence composition). Fallback на text-only при отсутствии embeddings |

#### Ключевые API Datasets

- `DatasetCatalogGraph.search_datasets(query, ...)` — weighted merge vector + text
- `DatasetCatalogGraph.find_by_polisyos_metric(...)` — deterministic resolve
- `DatasetRegistry.find_datasets_for_variable(...)` — ранжирование по proxy/coverage/confidence
- `DatasetRegistry.compute_p_star_z(...)` — point/empirical оценка с penalty breakdown
- `proxy_resolver.resolve_proxy(...)` / `validate_proxy(...)` — proxy chain с 4-condition check

#### Роль в системе

- `fabric.retrieval` — каталог как дополнительный lane для `DataNeed` resolve
- `scientist.agent` — tool для dataset discovery
- `scientist.nodes.builtins.causal.resolve_transport` — `P*(Z)` и proxy fallback
- `ir.analytics` — типы transportability и confidence-композиции

CLI: `python -m polisyos.datasets.batch.cli run --snapshot-root <path>`.

---

### Scientist — AI-оркестрация

> `src/polisyos/scientist/` · [README](policy-engine/src/polisyos/scientist/README.md) · Зависимости: ir, fabric, foundry, runtime, lex, academic, datasets, core, common

Оркестрационный «мозг» системы. Координирует полный цикл эксперимента через DAG workflow.

#### Default Workflow DAG (`scientist_default`)

```
start (noop)
├─ build_data_snapshot
│  └─ bind_foundry_inputs
│     └─ run_data_plane_gate
├─ build_execution_plan
│  └─ build_method_catalog_snapshot
│     └─ run_preflight
│        └─ ready_to_run
├─ link_trinity

compile_foundry (depends: link_trinity + run_data_plane_gate + ready_to_run)
└─ resolve_parameters (depends: compile_foundry + bind_foundry_inputs + run_data_plane_gate)
   └─ run_simulation
      ├─ run_distributional_analysis
      └─ propagate_uncertainty

run_causal_evaluation (depends: build_data_snapshot)
run_governance (depends: propagate_uncertainty + run_distributional_analysis + run_causal_evaluation)
run_evaluator (depends: run_governance)
build_decision_packet (depends: run_governance + run_causal_evaluation + run_evaluator)
```

#### Causal Full Workflow DAG (`scientist_causal_full`)

Расширенный workflow для полного causal-контура. Требует явного вызова `run_causal_full_workflow(...)`.

```
start (noop)
├─ build_data_snapshot
│  └─ bind_foundry_inputs
│     └─ run_data_plane_gate
├─ build_literature_prior
│  └─ reconcile_causal_graph
├─ build_execution_plan
│  └─ build_method_catalog_snapshot
│     └─ run_preflight
│        └─ ready_to_run
├─ link_trinity

compile_foundry (depends: link_trinity + run_data_plane_gate + ready_to_run)
└─ resolve_parameters (depends: compile_foundry + bind_foundry_inputs
                              + run_data_plane_gate + reconcile_causal_graph)
   └─ run_simulation
      ├─ run_distributional_analysis
      └─ propagate_uncertainty

run_causal_evaluation (depends: build_data_snapshot)
└─ run_causal_queries
   └─ run_causal_ensemble
      └─ run_abm_consistency
         └─ run_transportability (depends: run_abm_consistency + reconcile_causal_graph)

run_governance (depends: propagate_uncertainty + run_distributional_analysis
                       + run_causal_evaluation + run_causal_ensemble
                       + run_abm_consistency + reconcile_causal_graph + run_transportability)
run_evaluator (depends: run_governance)
build_decision_packet (depends: run_governance + run_causal_evaluation + run_evaluator)
```

Ключевые отличия от `scientist_default`:
- Добавлена causal-ветка: `build_literature_prior → reconcile_causal_graph`
- Расширенная evaluation цепочка: `run_causal_queries → run_causal_ensemble → run_abm_consistency → run_transportability`
- `resolve_parameters` дополнительно зависит от `reconcile_causal_graph`
- `run_governance` собирает результаты из всех causal-нод

Точки входа: `polisyos.scientist.run_experiment(state)`, `polisyos.scientist.workflows.builder.run_default_workflow(...)`, `polisyos.scientist.workflows.builder.run_causal_full_workflow(...)`.

#### Крупные подсистемы Scientist

| Подсистема | Назначение |
|------------|-----------|
| **[engine/](policy-engine/src/polisyos/scientist/engine/README.md)** | DAG executor: `WorkflowSpec` validation, topological execution, strict `ExperimentState` (`extra="forbid"`), idempotency cache (по `run_id + node_id + state_reads + bind params`), checkpoint/resume, run lock |
| **[workflows/](policy-engine/src/polisyos/scientist/workflows/README.md)** | Сборка и выполнение workflow: `default_workflow_spec()`, `build_execution_context()`, builtin + plugin node registry, `run_default_workflow()`. Engines: `WorkflowExecutor` (primary), `SimpleLoopEngine` (dev/search), `LangGraph` adapter (legacy) |
| **[agent/](policy-engine/src/polisyos/scientist/agent/README.md)** | Иерархия AI-агентов: PI → Drafter → Formalizer → Critic. Multi-pass drafter mode. Self-healing: `FailureCard` → `ReflexionOrchestrator`. RAG, knowledge base, norm loader, feasibility probes, code verifier. **Опциональный контур** — default workflow не запускает автоматически |
| **[llm/](policy-engine/src/polisyos/scientist/llm/README.md)** | Gateway-first LLM layer: `GatewayLLMClient` (OpenAI-compatible), `TracedLLMClient` bridge, `ModelProfileRegistry` с builtin profiles (OpenAI/Anthropic/Gemini/Groq/Gonka). Конфиг через `POLISYOS_LLM_GATEWAY_*` env vars |
| **[governance/](policy-engine/src/polisyos/scientist/governance/README.md)** | `ValidationPipeline` с ordered passes + short-circuit по blocker. Passes: Budget, Schema, Privacy, PII, QualityGate, Confidence, Equity, Safety, Legal. Профили: fast/mvp/strict. Human gate через `HumanGateProtocol` (typed `GateRequest`/`GateDecision` в CAS) |
| **[kernel/](policy-engine/src/polisyos/scientist/kernel/README.md)** | Phase FSM: INTAKE → FRAME → PREFLIGHT_GOV → PLAN → EXECUTE → POSTFLIGHT_GOV → DECIDE → PUBLISH → ARCHIVE (+ SEARCH/REFLEXION). 4 типа бюджетов: Compute, Evidence, Legitimacy, Complexity |
| **[nodes/](policy-engine/src/polisyos/scientist/nodes/README.md)** | Built-in workflow nodes по категориям: data (BuildDataSnapshot, BindFoundryInputs, EnrichKnowledge), compile (LinkTrinity, CompileFoundry), simulate (RunSimulation, RunDistributionalAnalysis, RunCausalEvaluation, PropagateUncertainty), governance (DataPlaneGate, RunPreflight, LegalCheck, RunGovernance), decide (BuildDecisionPacket), planning (BuildExecutionPlan, BuildMethodCatalogSnapshot, ReadyToRun) |
| **[search/](policy-engine/src/polisyos/scientist/search/README.md)** | `SearchController` с cheap/expensive two-stage evaluation. Strategies: Random, Grid, adapter, optional Bayesian (botorch/gpytorch), Multi-Objective, Multi-Fidelity. Stopping: MaxIterations, MaxWallTime, ImprovementPlateau, TargetAchieved. Adversarial stress-test. **Опциональный контур** |
| **[doe/](policy-engine/src/polisyos/scientist/doe/README.md)** | Design of Experiments: ScenarioSweep, AblationPlan, SensitivityPlan (SALib: MORRIS/SOBOL/FAST), AdversarialPlan. Stress-test reports |
| **[backtesting/](policy-engine/src/polisyos/scientist/backtesting/README.md)** | Историческая валидация: OutcomeMasker, PredictionEvaluator (RMSE/MAE/MAPE/Coverage), TrustScorer (coverage/mape/bias → grade A-F). CLI: `polisyos scientist backtest` |
| **[adapters/](policy-engine/src/polisyos/scientist/adapters/README.md)** | Порты интеграции: `DefaultFoundryPort` (compile/execute + optional TEE gate + SBOM derived artifacts), `DefaultFabricPort` (DataViewRequest → DataSnapshot, tabular payload, quality report). Workflow автоматически подключает адаптеры |
| **[compute/](policy-engine/src/polisyos/scientist/compute/README.md)** | Execution jobs: `JobSpec`/`JobKey`/`JobResult`, `run_job()` с двумя backend-ами: `LocalBackend` (legacy program graph) и `MethodBackend` (Foundry method dispatcher). Используется causal-нодами |
| **[orchestrator/](policy-engine/src/polisyos/scientist/orchestrator/README.md)** | Presentation layer: `DecisionCard.from_packet()` — краткая управленческая карточка. Verdict/confidence агрегация, issues summary, markdown-рендер. Не участвует в обязательном DAG |
| **[search/strategies/](policy-engine/src/polisyos/scientist/search/strategies/README.md)** | Выделенная поддиректория стратегий: Random, Grid, Bayesian (botorch/gpytorch), Multi-Objective, Multi-Fidelity. `StrategyAdapter`, resource arbiter, objective bridge |

#### Воспроизводимость

- **Idempotency cache:** ключи из `state_reads + bind params + run_id`; успешные `NodeOutcome` кэшируются в CAS
- **Checkpointing:** `scientist.checkpoint` после каждой успешной ноды; `resume_from_checkpoint`
- **Run lock:** `.polisyos/runs/<run_id>/run.lock` предотвращает конкурентный запуск
- **Replay backend:** стратегии `foundry`/`scientist`, completeness report, environment diffs verification

#### Основные артефакты default workflow

- `scientist.decision_packet` (schema `3.1`)
- `scientist.governance_report`
- `scientist.workflow_report`
- `scientist.experiment_state`
- `scientist.checkpoint`
- Производные `foundry.*` артефакты (exec plan, simulation result, metrics, envelopes)

---

### Batch Common — общая batch-инфраструктура

> `src/polisyos/batch_common/` · Зависимости: common

Общий инфраструктурный слой для offline batch-пайплайнов (`academic.batch` и `datasets.batch`). Не содержит доменной логики.

| Модуль | Назначение |
|--------|-----------|
| **paths.py** | Snapshot filesystem layout: `<root>/<domain>/<stage>/` conventions |
| **manifest.py** | Stage manifests: SHA256-based checksums, stage metadata, resume support |
| **hashing.py** | Stable content hashing для deterministic dedup и cache keys |
| **thermal.py** | Thermal pacing: rate control для batch stages (API rate limits, CPU throttling) |
| **qc.py** | QC helpers: row counts, nullability checks, dedup stats, completeness gates |
| **phase0_quality_validation.py** | Phase-0 quality gate: cross-stage consistency, extraction quality, coverage reports |

---

### Packs — компонентные пакеты

> `src/polisyos/packs/` · [README](policy-engine/src/polisyos/packs/README.md)

Встроенные доменные пакеты — reference implementation для быстрого старта.

**[roads/](policy-engine/src/polisyos/packs/roads/README.md)** — полнофункциональный пакет (6 компонентов):

| Компонент | Тип | Назначение |
|-----------|-----|-----------|
| `roads.ir.registry_fragment@1.0.0` | IR_FRAGMENT | Единица `roads.kmh` (priority=100) |
| `roads.method.speed_cap@1.0.0` | FOUNDRY_METHOD | Ограничение скорости агентов (NumPy, O(N)) |
| `roads.scholar.speed_limit@1.0.0` | SCHOLAR_EXTRACTOR | Regex-извлечение speed limit (en/uk) |
| `lex.eval.simple_v1@1.0.0` | LEX_EVALUATOR | Обёртка evaluate_legality_impl |
| `lex.norm_extractor.regex_v1@1.0.0` | LEX_EXTRACTOR | Legacy regex-экстрактор |
| `roads.normpack.static_provider@1.0.0` | NORM_PACK_PROVIDER | Статический NormPack для UA |

**[econ/](policy-engine/src/polisyos/packs/econ/README.md)** — минималистичный demo-пакет. 1 компонент (`econ.ir.registry_fragment@1.0.0`) с приоритетом 90, намеренно конфликтует с `roads.kmh` для тестирования conflict resolution.

Discovery через Entry Points (production) или dev scan (`__polisyos_components__`).

---

## Сквозные подсистемы

### Observability

- **Трассировка:** OpenTelemetry spans через `PolicyOSTracer` + `@traced` / `@traced_method` декораторы
- **Метрики:** Prometheus-совместимый `MetricsRegistry` (CAS, Fabric, Foundry, Scientist, LLM, Security)
- **Логи:** структурированные JSON-логи (Loguru) с trace/span correlation
- **Determinism:** 5 уровней гарантий: `STRICT_CPU` → `LIBRARY_DETERMINISTIC` → `BEST_EFFORT_GPU` → `STATISTICAL` → `NONDETERMINISTIC`
- **LLM Pricing:** оценка стоимости вызовов для budget-aware workflow
- **Env:** `POLISYOS_OTEL_ENABLED`, `POLISYOS_METRICS_PORT=9464`, `POLISYOS_DETERMINISM_TIER`

### Provenance & Audit

- **W3C PROV-O:** полный граф lineage от входных данных до финальных решений
- **Audit packages:** портативные `.polisyos-audit.tar.gz` с 5-шаговой офлайн-верификацией (Package Integrity, CAS Integrity, Signature Verification, Provenance Validation, SLSA Verification)
- **Ed25519 подписи:** detached sidecar подписи для артефактов, bulk sign/verify
- **Fact Log:** append-only immutable журнал фактов с deterministic SHA-256 IDs
- **SLSA:** модели, attestation builder, Fulcio/Rekor клиенты

### Component Model

- **ComponentId:** `namespace.name@semver` — стандартный формат для всех расширений
- **Discovery:** автоматическое обнаружение через Python entry points (8 групп: `polisyos.fabric_connectors`, `polisyos.ir_fragments`, `polisyos.foundry_methods`, `polisyos.scholar_extractors`, `polisyos.lex_extractors`, `polisyos.lex_evaluators`, `polisyos.norm_pack_providers`, `polisyos.scientist_nodes`)
- **Registry:** thread-safe с conflict resolution policies (`error_on_conflict`/`prefer_higher_priority`)
- **Compliance:** валидация метаданных и ABI-совместимости

### LLM Integration

- **Gateway-first:** OpenAI-compatible gateway client (`POLISYOS_LLM_GATEWAY_BASE_URL`)
- **Traced:** все вызовы обёрнуты в `TracedLLMClient` (OTel spans, token usage, cost tracking)
- **Model profiles:** registry builtin profiles (OpenAI GPT-4o/GPT-4-turbo, Anthropic Claude, Gemini, Groq, Gonka)
- **Cost estimation:** fallback pricing для budget-aware governance
- **NL mode:** MockPIAgent/MockDrafterAgent при `llm_model=None` (для dev/test)

---

## Ключевые концепции

### Trinity IR

Три независимых артефакта, разделяющих *why / what / how*:
- **ProblemFrame** — зачем: домен, KPI, constraints, stakeholders
- **PolicySpec** — что делать: интервенции, mechanisms, parameters, selector expressions
- **ModelSpec** — как моделировать: fidelity, agent config, assumptions, data snapshot

### Kernel Registries

Типобезопасные реестры для всех сущностей модели: mechanisms (типы интервенций), slots (переменные состояния с merge rules), units (единицы измерения), constraints, metrics, merge rules (с алгебраическими свойствами: коммутативность, ассоциативность, идемпотентность), selector fields, trust policies.

### Patch-Based Execution

Все изменения состояния через именованные патчи в слоты (`agents.income`, `government.balance`). CRDT-inspired merge engine с правилами SUM/OVERRIDE/PRIORITY/ERROR. Нет прямой мутации — patch-first updates.

### Content-Addressable Storage (CAS)

ID = SHA256(содержимое). Неизменяемость, дедупликация, provenance tracking. Layout: `.polisyos/artifacts/sha256/{ab}/{cd}/{hash}.blob` + `.manifest.json`.

### World Model

Append-only Fact Log → инкрементальная материализация в DuckDB (13+ реляционных таблиц: `world_facts`, `world_nodes`, `world_edges`, `claims`, `doc_sources`, `conflict_sets`, `trust_assessments` и др.) → optional Kuzu граф. Типобезопасный query API с column guards/masking.

### Legal Knowledge Graph

Offline pipeline (ЄДРНПА XML → parse → structure → SPO extraction → DuckDB graph) → HNSW vector indices → hybrid search (vector + text score fusion). Read-only `LegalKnowledgeGraph` API с поддержкой entity/fact/provision search и graph traversal.

### Scholar Knowledge Graph (SKG)

Offline pipeline (OpenAlex → topic selection → harvest → parse → extraction → DuckDB SKG) → HNSW vector indices → hybrid search (vector + text score fusion). Read-only `ScholarKnowledgeGraph` API: literature search, parameter priors (trust-weighted mean/std), causal evidence. Transportability-aware `ParameterSelector` для выбора параметров под target context через `ContextProfile`.

### Dataset Catalog

Offline pipeline (statistical sources → normalize → DuckDB catalog) → HNSW vector indices → hybrid search. `DatasetCatalogGraph` для discovery датасетов по метрикам и переменным. `DatasetRegistry` для transportability: `P*(Z)` estimation (point/empirical), proxy resolution с 4-condition validation, confidence composition.

### Evidence / Provenance / Trust / Quality

Каждый data product несёт EvidenceBundle с provenance графом, quality indicators (missingness, staleness, coverage) и uncertainty bounds. Governance gates блокируют некачественные данные.

### Data Retrieval

Двухуровневое разрешение data needs: FastLane (deterministic resolve через curated source bindings) → ExploreLane fallback (live discovery по коннекторам) → preview gate (quality check) → execution → promotion candidates для обогащения bindings.

---

## Архитектурные инварианты (Laws)

| Закон | Принцип | Enforcement |
|-------|---------|-------------|
| **A — Import Gate** | Зависимости строго «вниз» по стеку; циклы запрещены | `tools/lint/lint_imports.py` + `import_policy.toml` |
| **B — Foundry is Pure JAX** | Никаких БД/сетей/файлов в execution core | `tools/lint/lint_foundry.py` |
| **C — Contracts as Source of Truth** | IR + typed контракты определяют canonical data; JSON Schemas генерируются из них | `tools/diagnostics/gen_schema.py --check` |
| **D — Reproducibility** | Каждый run аудируем; артефакты content-addressed; determinism tracked | Runtime manifests, CAS, TreasuryPlan |
| **E — Evidence & Provenance** | Data products несут evidence/provenance; Fact Log immutable | W3C PROV-O |
| **K — Quality Gates** | Некачественные или policy-violating данные блокируются до execution | Governance passes |

---

## Технологический стек

### Core Runtime

| Технология | Назначение |
|------------|-----------|
| **Python >=3.11** | Основной язык |
| **JAX / JAXlib** | Дифференцируемые вычисления, JIT, vmap, grad, lax.scan |
| **Equinox** | OOP-обёртка для JAX-модулей (Module, eqx.tree_at) |
| **Jaxtyping / Chex** | Статическая проверка размерностей, frozen dataclasses |
| **Pydantic v2** | Валидация моделей (`frozen=True`, `extra="forbid"`) |
| **DuckDB** | Аналитические SQL-запросы, columnar storage, World Model, Legal Knowledge Graph |
| **Kùzu** (optional) | Графовые Cypher-запросы, entity-event network |

### ML & Optimization

| Технология | Назначение |
|------------|-----------|
| **Optax** | Оптимизаторы (Adam, SGD) для калибровки и RL |
| **Diffrax** | ODE-интеграция для динамических систем |
| **LangGraph / LangChain** | Оркестрация AI-агентов |
| **OpenAI API** | LLM gateway (SPO extraction, embeddings, NL pipeline) |
| **econml** (optional) | Каузальный inference (CATE, DML, meta-learners) |
| **statsmodels / linearmodels** (optional) | Эконометрика (panel, IV, time series) |
| **SALib** (optional) | Sensitivity analysis (MORRIS, SOBOL, FAST) |
| **pymoo** | Multi-objective optimization |

### Data & Storage

| Технология | Назначение |
|------------|-----------|
| **PyArrow / Parquet** | Fact Log сегменты, ETL staging |
| **pandas** | DataFrame операции, quality computation |
| **aiohttp** | Async HTTP для коннекторов |
| **hnswlib** | Approximate nearest neighbor search для Legal/Scholar Knowledge Graph и Dataset Catalog |
| **SentenceTransformers** (optional) | Dense vector embeddings для academic и dataset каталогов |

### Observability & Security

| Технология | Назначение |
|------------|-----------|
| **OpenTelemetry** | Distributed tracing, metrics export |
| **Prometheus** | Метрики и алертинг (27 alerts, 15 recording rules) |
| **Grafana** | 6 дашбордов (Executive, Scientist, Foundry HPC, SLO, Security, Knowledge Freshness) |
| **Loguru** | Структурированное логирование |
| **FastAPI / Uvicorn** (optional) | Runtime HTTP API v1 + Control Plane |
| **OPA (Rego)** | 7 policy-модулей авторизации |
| **Cryptography** | Ed25519 подписи, HMAC delegation tokens |

### Frontend

| Технология | Назначение |
|------------|-----------|
| **React 18** | UI framework для runtime-dashboard |
| **TypeScript** | Типизация frontend |
| **Vite** | Build tool и dev server |
| **TailwindCSS** | Utility-first CSS |
| **React Query** | Server state management, cache/invalidation |
| **openapi-fetch** | Typed HTTP client из OpenAPI spec |
| **Zod** | Runtime validation ответов API |
| **openapi-typescript** | Генерация TypeScript типов из OpenAPI |

### Optional Dependency Groups

```
kuzu          — графовые запросы (Kuzu)
analytics     — scipy, statsmodels, linearmodels
sensitivity   — SALib
causal             — dowhy, econml
causal-discovery   — tigramite, causal-learn
causal-discovery-scale — dagma (DAG learning через differentiable acyclic constraints)
causal-symbolic    — y0 (symbolic identification, do-calculus)
solvers            — ortools, pulp
multi-tenant  — psycopg, asyncpg, fastapi, uvicorn, httpx, PyJWT
methods-full  — analytics + causal + solvers
security      — httpx, boto3, sigstore, presidio, spacy
rag           — faiss-cpu
rag-local          — sentence-transformers, onnxruntime
academic-skg       — PyPDF (PDF parsing для academic pipeline)
sandbox            — RestrictedPython
search_bo     — torch, gpytorch, botorch (Bayesian optimization)
search_mo     — torch, gpytorch, botorch (Multi-objective search)
```

---

## Security и Multi-Tenancy

> [Подробнее](policy-engine/src/polisyos/core/security/README.md) · [OPA policies](policy-engine/ops/opa/README.md)

Архитектура Zero Trust для multi-tenant deployments:

| Подсистема | Что делает |
|------------|-----------|
| **Tenant routing** | `CellRegistry` → `resolve_routing` → tenant-aware execution |
| **DB isolation** | PostgreSQL RLS (`SET LOCAL app.current_tenant`) / DuckDB legacy |
| **Identity** | SPIFFE service identity + OIDC/JWT user claims normalization |
| **Authorization** | Async OPA client с TTL cache и fail-closed семантикой |
| **Delegation** | Подписанные hop-to-hop delegation tokens (`DelegationTokenManager`) |
| **Audit chain** | Append-only chained audit log + hot/cold реплика + tamper verification |
| **TEE** | Attestation policy/verifier + gatekeeper middleware (SEV-SNP) |
| **SBOM** | CycloneDX генерация/слияние/проверка + vulnerability gate (CVSS threshold) |
| **SLSA** | Attestation builder, Fulcio/Rekor клиенты |

OPA policies (7 модулей): tenant boundary, RBAC + MFA, data classification (PII-tier), delegation guard, composite decision, vulnerability gate, deploy decision.

Kubernetes baseline: Helm charts (`polisyos-cell`, `spire`, `keycloak`), deny-by-default NetworkPolicy, Linkerd mTLS, confidential compute node pool (Kata/SEV-SNP).

SQL миграции: `tenant_id` columns → backfill → RLS enable → least-privilege `polisyos_app` role.

Ключевые env-переключатели: `POLISYOS_MULTI_TENANT_ENABLED`, `POLISYOS_AUTHZ_MODE` (off/shadow/enforce), `POLISYOS_TEE_ENABLED`, `POLISYOS_SBOM_ENABLED`.

---

## Quickstart

Prereqs: Python `>=3.11`, `uv`.

```bash
cd policy-engine
uv sync --frozen

# Проверка установки
PYTHONPATH=src uv run python tools/diagnostics/check_setup.py

# Запуск тестов
uv run pytest

# Быстрый цикл без integration
uv run pytest -m "not integration"

# Observability стек
cd ops && docker compose -f docker-compose.observability.yml up -d
# Prometheus: http://localhost:9090  |  Grafana: http://localhost:3000 (admin/admin)

# Runtime API v1 + Control Plane
PYTHONPATH=src uv run --extra multi-tenant --extra test python -c "
from polisyos.runtime.http.app import create_runtime_api_app
import uvicorn
uvicorn.run(create_runtime_api_app(), host='127.0.0.1', port=8000)
"

# Runtime Dashboard (React)
cd frontend/runtime-dashboard
npm install
npm run generate:api   # генерация типов из OpenAPI
npm run dev            # http://127.0.0.1:5173

# Reference UI (static)
cd frontend/runtime-reference-shell && python -m http.server 4173
# http://127.0.0.1:4173

# Dashboard (Streamlit)
uv run streamlit run dashboard.py
```

macOS: импортировать `jax_bootstrap.py` **перед** `import jax` для защиты от Metal backend.

---

## Тестирование

> [README](policy-engine/tests/README.md)

Организованы по архитектурным слоям:

| Директория | `test_*.py` | Что тестирует |
|------------|:-----------:|--------------|
| [tests/](policy-engine/tests/README.md) (корень) | 6 | Архитектурные гейты, фасады API, component/packs discovery |
| [tests/contract/](policy-engine/tests/contract/README.md) | 18 | Trinity/IR контракты, ABI diff, миграции, SLO, gate models |
| [tests/core/](policy-engine/tests/core/README.md) | 52 | CAS, signing, canonical JSON, observability, security, components, registry, LLM, contracts |
| [tests/ir/](policy-engine/tests/ir/README.md) | 10 | Loaders, trinity, registry fragments, uncertainty, hte/backtest, architectural invariant (`ir → core` ban) |
| [tests/fabric/](policy-engine/tests/fabric/README.md) | 46 | Connectors, catalog, provenance, trust, world/materialization, claims/scholar |
| [tests/foundry/](policy-engine/tests/foundry/README.md) | 65 | Methods framework, calibration, agent simulation, determinism/numerics |
| [tests/scientist/](policy-engine/tests/scientist/README.md) | 58 | Engine/workflow, governance passes, search/DOE, decision artifacts |
| [tests/runtime/](policy-engine/tests/runtime/README.md) | 15 | Runtime HTTP API, replay, timeline/debug/artifact inspection, control plane, tenant isolation, OpenAPI hardening |
| [tests/lex/](policy-engine/tests/lex/README.md) | 9 | Batch pipeline (structurers, SPO normalization, quality, sharding), simulator (diff, mutator, impact) |
| tests/academic/ | 22 | Batch pipeline (parser, graph builder, topic catalog/selector, trust, extractors, QC, SKG), knowledge (SKGQuery, ParameterSelector) |
| tests/datasets/ | 12 | Batch pipeline (normalizer, dedup, graph builder, source registry, core_sources_ingest, QC), knowledge (store, registry, proxy resolver, variable alignment) |
| tests/common/ | 1 | Быстрая JSON-сериализация |
| [tests/integration/](policy-engine/tests/integration/README.md) | 1 | Human-gate audit cycle (cross-layer) |
| tests/performance/ | 1 | Observability overhead SLA |

```bash
# Весь тестовый контур
uv run pytest

# Быстрый цикл
uv run pytest -m "not integration"

# По слоям
uv run pytest tests/contract -q
uv run pytest tests/core -q
uv run pytest tests/ir -q
uv run pytest tests/fabric -q
uv run pytest tests/foundry -q
uv run pytest tests/scientist -q
uv run pytest tests/runtime -q
uv run pytest tests/lex -q

# Integration
POLISYOS_RUN_INTEGRATION=1 uv run pytest tests/scientist/integration -q

# Performance regression
uv run pytest tests/performance/test_overhead.py -q
```

---

## Инструменты разработчика

> [Полный каталог](policy-engine/tools/README.md)

### Архитектурные гейты (CI/pre-commit)

| Инструмент | Назначение | Документация |
|-----------|-----------|--------------|
| `tools/lint/lint_imports.py` | Import gate: Law A (однонаправленные зависимости), циклы | [README](policy-engine/tools/lint/README.md) |
| `tools/lint/lint_foundry.py` | Law B (Foundry без I/O) | [README](policy-engine/tools/lint/README.md) |
| `tools/lint/lint_connectors.py` | Изоляция connectors от scientist/foundry | [README](policy-engine/tools/lint/README.md) |
| `tools/lint/lint_connector_hardening.py` | P7 hardening для production connectors | [README](policy-engine/tools/lint/README.md) |
| `tools/lint/check_scholar_imports.py` | Запрет `scholar → fabric.io.db` | [README](policy-engine/tools/lint/README.md) |
| `tools/diagnostics/check_state_reads.py` | AST-проверка `state_reads` у scientist nodes | [README](policy-engine/tools/diagnostics/README.md) |
| `tools/diagnostics/check_scientist_node_version_bump.py` | SemVer bump для измененных nodes | [README](policy-engine/tools/diagnostics/README.md) |
| `tools/lint/collect_arch_metrics.py` | Freeze-артефакты (summary.json, import_gate.txt, ruff_stats.txt) | [README](policy-engine/tools/lint/README.md) |
| `tools/lint/compare_baseline.py` | Baseline comparison, exception policy, deep-import drift | [README](policy-engine/tools/lint/README.md) |

### ABI и контракты

| Инструмент | Назначение | Документация |
|-----------|-----------|--------------|
| `tools/diagnostics/gen_schema.py` | Генерация/проверка JSON Schema из IR-моделей (50 ABI models: IR=48, Fabric=2) | [README](policy-engine/tools/diagnostics/README.md) |
| `tools/diagnostics/abi_diff.py` | Семантический diff baseline/current (13 типов изменений), PASS/WARN/FAIL | [README](policy-engine/tools/diagnostics/README.md) |
| `tools/connectors/check_contracts.py` | Валидация connector contracts snapshot (3 contracts) | [README](policy-engine/tools/connectors/README.md) |

### Runtime и OpenAPI

| Инструмент | Назначение | Документация |
|-----------|-----------|--------------|
| `tools/runtime/export_runtime_openapi.py` | Экспорт OpenAPI Runtime API v1 | [README](policy-engine/tools/runtime/README.md) |
| `tools/runtime/generate_runtime_client.py` | Генерация TypeScript/JS клиента из OpenAPI | [README](policy-engine/tools/runtime/README.md) |
| `tools/runtime/check_runtime_api_contract.py` | Проверка OpenAPI и client drift | [README](policy-engine/tools/runtime/README.md) |
| `tools/connectors/scaffold.py` | Scaffold нового коннектора (REST/CSV/SQL/SDMX) | [README](policy-engine/tools/connectors/README.md) |

### Демо и бенчмарки

| Инструмент | Назначение | Документация |
|-----------|-----------|--------------|
| `tools/demos/run_laffer_demo.py` | JAX/Optax demo кривой Лаффера | [README](policy-engine/tools/demos/README.md) |
| `tools/demos/run_mechanism_design.py` | E2E differentiable mechanism design (IR → compile → execute → grad) | [README](policy-engine/tools/demos/README.md) |
| `tools/benchmarks/bench_simulation.py` | JAX benchmark simulation loop | [README](policy-engine/tools/benchmarks/README.md) |

### Миграции

| Инструмент | Назначение | Документация |
|-----------|-----------|--------------|
| `tools/migrations/migrate_duckdb_to_pg.py` | DuckDB → PostgreSQL для tenant-scoped таблиц | [README](policy-engine/tools/migrations/README.md) |
| `tools/migrations/migrate.py` | Миграция `policy_ir`/`dataset_manifest` между версиями | [README](policy-engine/tools/migrations/README.md) |

### Минимальный gate перед PR

```bash
cd policy-engine
PYTHONPATH=src:. uv run python tools/lint/lint_imports.py --policy import_policy.toml --exceptions import_exceptions.toml
PYTHONPATH=src:. uv run python tools/lint/lint_foundry.py --repo-root .
PYTHONPATH=src:. uv run python tools/diagnostics/check_state_reads.py
PYTHONPATH=src:. uv run python tools/diagnostics/check_scientist_node_version_bump.py --base-ref origin/main
PYTHONPATH=src:. uv run python tools/lint/check_scholar_imports.py
PYTHONPATH=src:. uv run python tools/connectors/check_contracts.py --check
PYTHONPATH=src:. uv run python tools/diagnostics/gen_schema.py --check
PYTHONPATH=src:. uv run python tools/runtime/check_runtime_api_contract.py
```

---

## Observability и Ops

> [ops/README.md](policy-engine/ops/README.md)

### Инфраструктура

| Модуль | Назначение | Документация |
|--------|-----------|--------------|
| **[Prometheus](policy-engine/ops/prometheus/README.md)** | 2 scrape jobs, 27 alerts (operational + SLO + audit chain), 15 recording rules | [README](policy-engine/ops/prometheus/README.md) |
| **[Grafana](policy-engine/ops/grafana/README.md)** | 6 дашбордов: Executive KPI, Scientist Agents, Foundry HPC, SLO Overview, Security Phase4, Knowledge Freshness | [README](policy-engine/ops/grafana/README.md) |
| **[OPA](policy-engine/ops/opa/README.md)** | 7 Rego policy-модулей + 7 unit-тестов. Runtime path: `polisyos/authz/decision` | [README](policy-engine/ops/opa/README.md) |
| **[Helm](policy-engine/ops/helm/README.md)** | `polisyos-cell` (namespace isolation, NetworkPolicy, RBAC, Linkerd), `spire` (PSAT attestation), `keycloak` (OIDC/FIDO2) | [README](policy-engine/ops/helm/README.md) |
| **[Terraform](policy-engine/ops/terraform/README.md)** | AKS node pool для confidential compute (`KataCcIsolation`, `sev-snp`, Standard_DC16as_v5) | [README](policy-engine/ops/terraform/README.md) |
| **[Migrations](policy-engine/ops/migrations/README.md)** | SQL-миграции для PostgreSQL RLS: `tenant_id` → backfill → RLS policies → least-privilege `polisyos_app` role | [README](policy-engine/ops/migrations/README.md) |

### Рекомендуемый порядок развёртывания

```
spire → Linkerd → keycloak → polisyos-cell
```

### Локальный запуск

```bash
cd policy-engine/ops
docker compose -f docker-compose.observability.yml up -d
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3000 (admin/admin)
```

---

## Frontend

> [frontend/README.md](policy-engine/frontend/README.md)

API-first интерфейсы для Runtime API v1 + Control Plane:

| Директория | Назначение | Документация |
|-----------|-----------|--------------|
| **[runtime-dashboard/](policy-engine/frontend/runtime-dashboard/README.md)** | React 18 + TypeScript + Vite + TailwindCSS. Полнофункциональное SPA для observability и control-plane | [README](policy-engine/frontend/runtime-dashboard/README.md), [src/](policy-engine/frontend/runtime-dashboard/src/README.md) |
| **[runtime-api-client/](policy-engine/frontend/runtime-api-client/README.md)** | Typed TypeScript клиент (`.ts`) + ESM runtime клиент (`.js`), автогенерируются из OpenAPI | [README](policy-engine/frontend/runtime-api-client/README.md) |
| **[runtime-reference-shell/](policy-engine/frontend/runtime-reference-shell/README.md)** | Статический reference UI (`index.html` + `app.js` + `styles.css`), без build toolchain | [README](policy-engine/frontend/runtime-reference-shell/README.md) |

### Runtime Dashboard — страницы

| Route | Назначение |
|-------|-----------|
| `/` | Runtime overview: статусы, тренды, failed runs, быстрая навигация |
| `/runs` | Run explorer с фильтрами и cursor pagination |
| `/runs/:runId` | Детальная карточка прогона (табы: timeline, nodes, lineage, agents/models, workflow, governance, debug, decision) |
| `/artifacts/:artifactId` | Artifact inspector (content/schema/lineage + специализированные viewers для decision/trinity/simulation) |
| `/launch` | Запуск прогона: `workflow` и `natural-language` режимы |
| `/sources` | Каталог source profiles + ingest selected source |
| `/data` | Data Intelligence (resolve/discover/preview/promotion) + connectors/cache + ingest |
| `/lex` | Запуск/мониторинг Lex pipeline, graph stats, semantic search |
| `/health` | Техническая health panel для API |

### API hooks

Все взаимодействия с backend через React Query hooks из `src/api/hooks/`:
- **Runtime read:** `useRuns`, `useRunDetails`, `useRunTimeline`, `useRunNodes`, `useRunLineage`, `useRunAgents`, `useRunWorkflow`, `useNodeDebug`, `useGovernanceDebug`, `useArtifactManifest`, `useArtifactContent` и др.
- **Control data:** `useResolveDataNeeds`, `useDiscoverDataSources`, `usePreviewFetchPlan`, `useDataCatalogSearch`, `useDataPromotionCandidates`, `useApprovePromotionCandidate`, `useIngestData` и др.
- **Control runs:** `useLaunchRun`, `useLaunchNlRun`, `useLlmProfiles`
- **Lex:** `useLexTrigger`, `useLexPipelineStatus`, `useLexGraphStats`, `useLexSearch`

### Контрактный поток

```
src/polisyos/runtime/http/* (FastAPI)
  → tools/runtime/export_runtime_openapi.py
  → schemas/runtime_api_v1.openapi.json
    → tools/runtime/generate_runtime_client.py
    → frontend/runtime-api-client/runtimeApiClient.{ts,js}

    → frontend/runtime-dashboard/scripts/generate-api-client.sh
    → frontend/runtime-dashboard/src/api/types.ts
```

Инварианты: UI строго API-only, frontend не обращается к CAS/БД/файловой системе напрямую.

---

## Schemas и ABI

> [schemas/README.md](policy-engine/schemas/README.md)

Директория `schemas/` реализует Architectural Law C: контракты как источник правды.

| Артефакт | Содержание | Документация |
|----------|-----------|--------------|
| **[snapshots/ir/](policy-engine/schemas/snapshots/ir/README.md)** | 48 JSON Schema для IR-моделей (P0=18, P1=23, P2=9), все `strict` compat mode | [README](policy-engine/schemas/snapshots/ir/README.md) |
| **[snapshots/fabric/](policy-engine/schemas/snapshots/fabric/README.md)** | 2 JSON Schema для Fabric enum ABI (`edge_kind`, `node_kind`) | [README](policy-engine/schemas/snapshots/fabric/README.md) |
| **[snapshots/connectors/](policy-engine/schemas/snapshots/connectors/README.md)** | 3 connector contracts (`eurostat`, `ukons`, `worldbank`), version evolution tracking | [README](policy-engine/schemas/snapshots/connectors/README.md) |
| **runtime_api_v1.openapi.json** | OpenAPI 3.1.0 спецификация Runtime API v1 + Control Plane | — |
| **abi_models.py** | Реестр 50 ABI-моделей (`ABIModelEntry`: IR=48, Fabric=2; P0=18, P1=23, P2=9) — single source of truth | — |

ABI compatibility: 13 типов изменений, P0 breaking → major bump, semantic diff + freshness check в CI.
Runtime API: 37 операций (27 GET + 10 POST), OpenAPI 3.1.0.

```bash
# Проверка ABI
PYTHONPATH=src:. uv run python tools/diagnostics/gen_schema.py --check
PYTHONPATH=src:. uv run python tools/diagnostics/abi_diff.py --baseline schemas/snapshots --current /tmp/current --format markdown

# Проверка connectors
PYTHONPATH=src:. uv run python tools/connectors/check_contracts.py --check
```

---

## Данные

```
data/
├── raw/         # Сырые данные (agents.csv, interactions.csv, macro.csv)
├── staging/     # ETL-промежуточные (.parquet)
├── curated/     # С манифестами, data contracts, entity resolution, UDF schema
└── norms/       # Нормативные пакеты (sample_norms.yaml)
```

---

## Документация

### Иерархия README

Трёхуровневая система (~100 README файлов):
- **Уровень 0:** корневой README (этот документ) — полная архитектурная карта
- **Уровень 1:** модуль (`fabric/README.md`, `scientist/README.md`) — архитектура, зависимости, принципы
- **Уровень 2:** подсистемы (`fabric/connectors/README.md`, `scientist/engine/README.md`) — API, контракты, внутренняя структура

### Ключевые документы

| Документ | Содержание |
|----------|-----------|
| [architecture.md](policy-engine/architecture.md) | Полная карта файловой структуры проекта |
| [schemas/README.md](policy-engine/schemas/README.md) | ABI Schema Gate (34 модели, backward compatibility rules) |
| [ops/README.md](policy-engine/ops/README.md) | Platform operations (Helm, OPA, Prometheus, Grafana, Terraform, SQL migrations) |
| [tools/README.md](policy-engine/tools/README.md) | Полный каталог инженерных CLI-инструментов |
| [frontend/README.md](policy-engine/frontend/README.md) | Frontend foundation для Runtime API v1 |
| [tests/README.md](policy-engine/tests/README.md) | Обзор тестового контура |

### Документация модулей

| Слой | README |
|------|--------|
| Common | [common/](policy-engine/src/polisyos/common/README.md), [migrations/](policy-engine/src/polisyos/common/migrations/README.md) |
| Core | [core/](policy-engine/src/polisyos/core/README.md), [artifacts/](policy-engine/src/polisyos/core/artifacts/README.md), [audit/](policy-engine/src/polisyos/core/audit/README.md), [components/](policy-engine/src/polisyos/core/components/README.md), [contracts/](policy-engine/src/polisyos/core/contracts/README.md), [governance/](policy-engine/src/polisyos/core/governance/README.md), [llm/](policy-engine/src/polisyos/core/llm/README.md), [observability/](policy-engine/src/polisyos/core/observability/README.md), [registry/](policy-engine/src/polisyos/core/registry/README.md), [security/](policy-engine/src/polisyos/core/security/README.md), [cache/](policy-engine/src/polisyos/core/cache/README.md) |
| IR | [ir/](policy-engine/src/polisyos/ir/README.md), [trinity/](policy-engine/src/polisyos/ir/trinity/README.md), [governance/](policy-engine/src/polisyos/ir/governance/README.md), [kernel/](policy-engine/src/polisyos/ir/kernel/README.md), [world/](policy-engine/src/polisyos/ir/world/README.md), [linker/](policy-engine/src/polisyos/ir/linker/README.md), [analytics/](policy-engine/src/polisyos/ir/analytics/README.md), [artifacts/](policy-engine/src/polisyos/ir/artifacts/README.md), [migrations/](policy-engine/src/polisyos/ir/migrations/README.md) |
| Fabric | [fabric/](policy-engine/src/polisyos/fabric/README.md), [connectors/](policy-engine/src/polisyos/fabric/connectors/README.md), [claims/](policy-engine/src/polisyos/fabric/claims/README.md), [docs/](policy-engine/src/polisyos/fabric/docs/README.md), [world/](policy-engine/src/polisyos/fabric/world/README.md), [catalog/](policy-engine/src/polisyos/fabric/catalog/README.md), [data_plane/](policy-engine/src/polisyos/fabric/data_plane/README.md), [retrieval/](policy-engine/src/polisyos/fabric/retrieval/README.md) |
| Foundry | [foundry/](policy-engine/src/polisyos/foundry/README.md), [agent_sim/](policy-engine/src/polisyos/foundry/agent_sim/README.md), [calibration/](policy-engine/src/polisyos/foundry/calibration/README.md), [methods/](policy-engine/src/polisyos/foundry/methods/README.md), [methods/catalog/](policy-engine/src/polisyos/foundry/methods/catalog/README.md), [methods/catalog/causal/](policy-engine/src/polisyos/foundry/methods/catalog/causal/README.md), [plugins/](policy-engine/src/polisyos/foundry/plugins/README.md), [uncertainty/](policy-engine/src/polisyos/foundry/uncertainty/README.md) |
| Runtime | [runtime/](policy-engine/src/polisyos/runtime/README.md), [http/](policy-engine/src/polisyos/runtime/http/README.md), [routes/](policy-engine/src/polisyos/runtime/http/routes/README.md), [services/](policy-engine/src/polisyos/runtime/http/services/README.md) |
| Lex | [lex/](policy-engine/src/polisyos/lex/README.md), [corpus/](policy-engine/src/polisyos/lex/corpus/README.md), [normpack/](policy-engine/src/polisyos/lex/normpack/README.md), [legal_evaluation/](policy-engine/src/polisyos/lex/legal_evaluation/README.md), [simulator/](policy-engine/src/polisyos/lex/simulator/README.md), [batch/](policy-engine/src/polisyos/lex/batch/README.md), [knowledge/](policy-engine/src/polisyos/lex/knowledge/README.md) |
| Scholar | [scholar/](policy-engine/src/polisyos/scholar/README.md), [discover/](policy-engine/src/polisyos/scholar/discover/README.md), [orchestrator/](policy-engine/src/polisyos/scholar/orchestrator/README.md) |
| Academic | [academic/](policy-engine/src/polisyos/academic/README.md), [batch/](policy-engine/src/polisyos/academic/batch/README.md), [knowledge/](policy-engine/src/polisyos/academic/knowledge/README.md), [openalex/](policy-engine/src/polisyos/academic/openalex/README.md) |
| Datasets | [datasets/](policy-engine/src/polisyos/datasets/README.md), [batch/](policy-engine/src/polisyos/datasets/batch/README.md), [knowledge/](policy-engine/src/polisyos/datasets/knowledge/README.md) |
| Scientist | [scientist/](policy-engine/src/polisyos/scientist/README.md), [engine/](policy-engine/src/polisyos/scientist/engine/README.md), [workflows/](policy-engine/src/polisyos/scientist/workflows/README.md), [agent/](policy-engine/src/polisyos/scientist/agent/README.md), [llm/](policy-engine/src/polisyos/scientist/llm/README.md), [governance/](policy-engine/src/polisyos/scientist/governance/README.md), [kernel/](policy-engine/src/polisyos/scientist/kernel/README.md), [nodes/](policy-engine/src/polisyos/scientist/nodes/README.md), [search/](policy-engine/src/polisyos/scientist/search/README.md), [search/strategies/](policy-engine/src/polisyos/scientist/search/strategies/README.md), [doe/](policy-engine/src/polisyos/scientist/doe/README.md), [backtesting/](policy-engine/src/polisyos/scientist/backtesting/README.md), [adapters/](policy-engine/src/polisyos/scientist/adapters/README.md), [compute/](policy-engine/src/polisyos/scientist/compute/README.md), [orchestrator/](policy-engine/src/polisyos/scientist/orchestrator/README.md) |
| Packs | [packs/](policy-engine/src/polisyos/packs/README.md), [roads/](policy-engine/src/polisyos/packs/roads/README.md), [econ/](policy-engine/src/polisyos/packs/econ/README.md) |
| Tests | [tests/](policy-engine/tests/README.md), [contract/](policy-engine/tests/contract/README.md), [core/](policy-engine/tests/core/README.md), [ir/](policy-engine/tests/ir/README.md), [fabric/](policy-engine/tests/fabric/README.md), [foundry/](policy-engine/tests/foundry/README.md), [scientist/](policy-engine/tests/scientist/README.md), [runtime/](policy-engine/tests/runtime/README.md), [lex/](policy-engine/tests/lex/README.md), [integration/](policy-engine/tests/integration/README.md) |
| Ops | [ops/](policy-engine/ops/README.md), [helm/](policy-engine/ops/helm/README.md), [helm/polisyos-cell/](policy-engine/ops/helm/polisyos-cell/README.md), [helm/spire/](policy-engine/ops/helm/spire/README.md), [helm/keycloak/](policy-engine/ops/helm/keycloak/README.md), [terraform/](policy-engine/ops/terraform/README.md), [migrations/](policy-engine/ops/migrations/README.md), [opa/](policy-engine/ops/opa/README.md), [prometheus/](policy-engine/ops/prometheus/README.md), [grafana/](policy-engine/ops/grafana/README.md) |
| Tools | [tools/](policy-engine/tools/README.md), [lint/](policy-engine/tools/lint/README.md), [diagnostics/](policy-engine/tools/diagnostics/README.md), [connectors/](policy-engine/tools/connectors/README.md), [runtime/](policy-engine/tools/runtime/README.md), [demos/](policy-engine/tools/demos/README.md), [benchmarks/](policy-engine/tools/benchmarks/README.md), [migrations/](policy-engine/tools/migrations/README.md) |
| Schemas | [schemas/](policy-engine/schemas/README.md), [snapshots/](policy-engine/schemas/snapshots/README.md), [ir/](policy-engine/schemas/snapshots/ir/README.md), [fabric/](policy-engine/schemas/snapshots/fabric/README.md), [connectors/](policy-engine/schemas/snapshots/connectors/README.md) |

---

## Архитектура PolisyOS

```
policy-engine/  # Project root (Policy Engine / PolisyOS).
├── src/  # Python sources and build metadata.
│   └── polisyos/  # Main Python package.
│       ├── __init__.py
│       ├── common/  # Shared utilities: config, logging, JAX env, migrations, serialization.
│       │   ├── __init__.py
│       │   ├── async_tools.py  # Sync/async bridging utilities.
│       │   ├── config.py  # Central pydantic-settings configuration.
│       │   ├── jax_env.py  # JAX environment defaults, macOS backend safety.
│       │   ├── logger.py  # Structured logging (Loguru) + OpenTelemetry correlation.
│       │   ├── serialization.py  # Shared serialization helpers (JSON, msgpack).
│       │   ├── timestamps.py  # UTC timestamp utilities and formatting.
│       │   └── migrations/  # Deterministic schema migrations.
│       │       ├── __init__.py
│       │       ├── base.py  # Migration framework primitives.
│       │       └── manifest.py  # Dataset manifest migrations.
│       ├── core/  # Infrastructure: CAS, contracts, tracing, registry, observability, security.
│       │   ├── __init__.py
│       │   ├── artifacts/  # Artifact system: CAS store, IDs, manifests, environment capture.
│       │   │   ├── __init__.py
│       │   │   ├── _env_capture.py  # Environment snapshot capture logic.
│       │   │   ├── _env_comparison.py  # Environment diff comparison.
│       │   │   ├── _env_models.py  # Environment data models.
│       │   │   ├── _env_utils.py  # Environment utility helpers.
│       │   │   ├── environment.py  # Environment manifests for reproducibility.
│       │   │   ├── environment_parts.py  # Decomposed environment manifest helpers.
│       │   │   ├── graph.py  # Artifact dependency graph tracking.
│       │   │   ├── ids.py  # SHA-256 content-addressed identifiers.
│       │   │   ├── manifest.py  # Artifact manifest models.
│       │   │   ├── registry.py  # Registry bundle artifacts.
│       │   │   ├── signing.py  # Cryptographic artifact signing.
│       │   │   └── store.py  # Filesystem-backed CAS store.
│       │   ├── audit/  # Audit trail assembly, export, verification.
│       │   │   ├── __init__.py
│       │   │   ├── _assembler_archive.py  # Archive creation for audit bundles.
│       │   │   ├── _assembler_core.py  # Core assembler logic.
│       │   │   ├── _assembler_errors.py  # Assembler error types.
│       │   │   ├── _assembler_provenance.py  # Provenance attachment for bundles.
│       │   │   ├── _assembler_slsa.py  # SLSA attestation integration.
│       │   │   ├── assembler.py  # Audit bundle assembly facade.
│       │   │   ├── instructions_template.md  # Template for audit instructions.
│       │   │   ├── models.py  # Audit data models.
│       │   │   ├── prov_json.py  # PROV-JSON export for audit.
│       │   │   ├── report.py  # Human-readable audit reports.
│       │   │   ├── safe_tar.py  # Safe tar archive creation.
│       │   │   ├── standalone_verifier_template.py  # Standalone verifier script.
│       │   │   └── verifier.py  # Audit bundle verification.
│       │   ├── backends/  # Pluggable computation backend dispatch.
│       │   │   ├── __init__.py
│       │   │   └── dispatcher.py  # Backend selection and dispatch logic.
│       │   ├── cache/  # In-process caching primitives.
│       │   │   ├── __init__.py
│       │   │   ├── lru.py  # LRU cache implementation.
│       │   │   ├── protocol.py  # Cache protocol definition.
│       │   │   └── ttl.py  # TTL-based cache with expiration.
│       │   ├── canon/  # Canonical JSON serialization.
│       │   │   ├── __init__.py
│       │   │   ├── canon_json.py  # Deterministic JSON for hashing.
│       │   │   └── hashing.py  # Content-hash computation utilities.
│       │   ├── compiler/  # Compilation reporting.
│       │   │   ├── __init__.py
│       │   │   └── report.py  # Compile report models.
│       │   ├── components/  # Component system for extensible modules.
│       │   │   ├── __init__.py
│       │   │   ├── _cli_audit.py  # CLI subcommand: audit operations.
│       │   │   ├── _cli_components.py  # CLI subcommand: component listing/info.
│       │   │   ├── _cli_crypto.py  # CLI subcommand: crypto/signing operations.
│       │   │   ├── _cli_lex.py  # CLI subcommand: lex operations.
│       │   │   ├── _cli_replay.py  # CLI subcommand: replay operations.
│       │   │   ├── _cli_scholar.py  # CLI subcommand: scholar operations.
│       │   │   ├── _cli_scientist.py  # CLI subcommand: scientist operations.
│       │   │   ├── bootstrap.py  # Component system bootstrap/initialization.
│       │   │   ├── capabilities.py  # Component capability declarations.
│       │   │   ├── cli.py  # Component CLI (polisyos command).
│       │   │   ├── cli_parts.py  # Shared CLI helpers and formatting.
│       │   │   ├── compliance.py  # Component compliance checks.
│       │   │   ├── discovery.py  # Entry-point component discovery.
│       │   │   ├── ids.py  # Component identity and semver.
│       │   │   ├── metadata.py  # Component metadata models.
│       │   │   ├── protocols.py  # Component protocol definitions.
│       │   │   └── registry.py  # Component registry.
│       │   ├── contracts/  # Typed inter-module contracts.
│       │   │   ├── __init__.py
│       │   │   ├── backtest.py  # Backtesting contracts.
│       │   │   ├── causal.py  # Causal inference contracts.
│       │   │   ├── compiler.py  # Compiler typed references.
│       │   │   ├── control.py  # Control Plane request/response DTOs.
│       │   │   ├── cursor.py  # Cursor-based pagination contracts.
│       │   │   ├── distributional.py  # Distributional analysis contracts.
│       │   │   ├── execution_plan.py  # Execution-plan contracts for unified LLM policy cycle.
│       │   │   ├── fabric.py  # Fabric evidence/bounds contracts.
│       │   │   ├── foundry.py  # Foundry ProgramGraph/ExecPlan contracts.
│       │   │   ├── hte.py  # Heterogeneous treatment effects contracts.
│       │   │   ├── lex.py  # Lex layer contracts.
│       │   │   ├── provenance.py  # Provenance tracking contracts.
│       │   │   ├── runtime.py  # Runtime lifecycle contracts.
│       │   │   ├── scholar.py  # Scholar layer contracts.
│       │   │   ├── scientist.py  # Scientist critique/failure/timeline contracts.
│       │   │   ├── trinity.py  # Trinity ProblemFrame/PolicySpec/ModelSpec.
│       │   │   └── uncertainty.py  # Uncertainty envelope contracts.
│       │   ├── discovery/  # Service and component discovery.
│       │   │   ├── __init__.py
│       │   │   ├── base.py  # Discovery protocol and base scanner.
│       │   │   └── orchestrator.py  # Discovery orchestration across sources.
│       │   ├── errors/  # Shared error hierarchy.
│       │   │   ├── __init__.py
│       │   │   └── base.py  # Base exception classes.
│       │   ├── evaluation/  # Scoring and evaluation framework.
│       │   │   ├── __init__.py
│       │   │   └── scoring.py  # Pluggable scoring functions.
│       │   ├── governance/  # Core governance logic (shared by scientist).
│       │   │   ├── __init__.py
│       │   │   ├── profiles.py  # Validation profiles (fast/mvp/strict).
│       │   │   ├── legal/  # Legal compliance.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── ast_policy.py  # AST allowlist policy.
│       │   │   │   └── backends/  # Legal rule backends.
│       │   │   │       ├── __init__.py
│       │   │   │       ├── base.py  # Backend base.
│       │   │   │       ├── expr_ast.py  # Safe AST interpreter.
│       │   │   │       └── stub.py  # Stub backend.
│       │   │   └── passes/  # Validation passes.
│       │   │       ├── __init__.py
│       │   │       ├── base.py  # Pass base class.
│       │   │       ├── legal_pass.py  # Legal compliance check.
│       │   │       └── safety_pass.py  # Safety validation check.
│       │   ├── llm/  # LLM client abstraction.
│       │   │   ├── __init__.py
│       │   │   ├── cost.py  # Token cost accounting.
│       │   │   ├── protocols.py  # LLM client protocol definitions.
│       │   │   ├── response.py  # Standardized LLM response models.
│       │   │   ├── retry.py  # LLM retry/backoff logic.
│       │   │   └── traced_client.py  # TracedLLMClient with OTel spans.
│       │   ├── observability/  # OpenTelemetry tracing, metrics, logs.
│       │   │   ├── __init__.py
│       │   │   ├── _metrics_helpers.py  # Internal metrics helper functions.
│       │   │   ├── _metrics_registry_base.py  # Base metrics registry implementation.
│       │   │   ├── config.py  # OTel configuration and resource attributes.
│       │   │   ├── decorators.py  # @traced / @traced_method decorators.
│       │   │   ├── determinism.py  # Determinism tracking.
│       │   │   ├── logs.py  # Structured logging with trace correlation.
│       │   │   ├── metrics.py  # Prometheus-compatible metrics registry.
│       │   │   ├── metrics_parts.py  # Decomposed metric registration helpers.
│       │   │   ├── pricing.py  # Cost/pricing observability.
│       │   │   ├── propagation.py  # Trace context propagation.
│       │   │   └── tracer.py  # PolicyOSTracer singleton.
│       │   ├── pipeline/  # Generic pipeline execution framework.
│       │   │   ├── __init__.py
│       │   │   ├── base.py  # Pipeline step protocol.
│       │   │   ├── dag.py  # DAG-based pipeline executor.
│       │   │   └── linear.py  # Linear pipeline executor.
│       │   ├── registry/  # Registry bundle builder/loader.
│       │   │   ├── __init__.py
│       │   │   ├── base.py  # Registry base protocol.
│       │   │   ├── builder.py  # Build registry bundles.
│       │   │   ├── builder_from_fragments.py  # Build from IR fragments.
│       │   │   ├── generic.py  # Generic typed registry.
│       │   │   └── loader.py  # Load registry bundles.
│       │   ├── resilience/  # Resilience patterns for core services.
│       │   │   ├── __init__.py
│       │   │   └── retry.py  # Retry with exponential backoff.
│       │   ├── run/  # Run context and manifest.
│       │   │   ├── __init__.py
│       │   │   ├── context.py  # RunContext for single execution.
│       │   │   └── manifest.py  # Run manifest serialization.
│       │   ├── security/  # Multi-tenant security, RBAC, TEE, SLSA.
│       │   │   ├── __init__.py
│       │   │   ├── access_scope.py  # Row/column access scope definitions.
│       │   │   ├── audit_models.py  # Security audit event models.
│       │   │   ├── audit_sink.py  # Tamper-evident audit log sink.
│       │   │   ├── audit_verifier.py  # Audit chain integrity verifier.
│       │   │   ├── authz.py  # Authorization engine (OPA integration).
│       │   │   ├── cell.py  # Cell-level isolation primitives.
│       │   │   ├── db_backend.py  # Database backend with RLS support.
│       │   │   ├── delegation.py  # Capability delegation protocol.
│       │   │   ├── exceptions.py  # Security exception types.
│       │   │   ├── identity.py  # SPIFFE/SPIRE identity management.
│       │   │   ├── registry.py  # Security component registry.
│       │   │   ├── router.py  # Multi-tenant request router.
│       │   │   ├── sbom.py  # Software bill of materials generation.
│       │   │   ├── settings.py  # Security configuration settings.
│       │   │   ├── tee.py  # Trusted Execution Environment support.
│       │   │   ├── tee_middleware.py  # TEE attestation middleware.
│       │   │   ├── tenant_context.py  # Tenant context propagation.
│       │   │   └── slsa/  # SLSA supply-chain security.
│       │   │       ├── __init__.py
│       │   │       ├── attestation.py  # SLSA attestation generation.
│       │   │       ├── config.py  # SLSA configuration.
│       │   │       ├── fulcio.py  # Fulcio certificate integration.
│       │   │       ├── models.py  # SLSA provenance models.
│       │   │       └── rekor.py  # Rekor transparency log integration.
│       │   └── trace/  # Structured tracing records.
│       │       ├── __init__.py
│       │       ├── record.py  # TraceRecord model.
│       │       └── sink.py  # Trace sinks (JSONL).
│       ├── fabric/  # Unified Data Fabric: ingestion, catalog, evidence, quality, trust, connectors.
│       │   ├── __init__.py
│       │   ├── _connector_bridge.py  # Scientist→Fabric isolation (Law A).
│       │   ├── config.py  # Fabric configuration.
│       │   ├── connectors_ingestion.py  # Connector-based ingestion pipeline.
│       │   ├── evidence.py  # Evidence bundle models.
│       │   ├── fact_writer.py  # Immutable fact writer.
│       │   ├── fitness_report.py  # Data fitness reports.
│       │   ├── ingestion.py  # ETL pipeline (raw→staging→stores).
│       │   ├── manifest.py  # Dataset manifest models.
│       │   ├── quality.py  # Quality indicators and thresholds.
│       │   ├── registry.py  # UDF/function registry.
│       │   ├── segment_manifest.py  # Segment manifest models.
│       │   ├── tabular.py  # Tabular data utilities.
│       │   ├── trust.py  # Trust policies and uncertainty.
│       │   ├── trust_adapter.py  # Trust→uncertainty bridge adapter.
│       │   ├── world_query.py  # World model query interface.
│       │   ├── catalog/  # Metric-level data contracts.
│       │   │   ├── __init__.py
│       │   │   ├── binding.py  # Hash-locked metric bindings.
│       │   │   ├── contract.py  # DataContract models.
│       │   │   ├── registry.py  # DataContractRegistry.
│       │   │   ├── resolver_fast_lane.py  # Deterministic FastLane resolver for metric→fetch plan.
│       │   │   ├── search.py  # Metric search/disambiguation.
│       │   │   ├── source_bindings.py  # Curated metric→source bindings for FastLane resolution.
│       │   │   └── validate.py  # Contract collection validation.
│       │   ├── claims/  # Claims management and verification.
│       │   │   ├── __init__.py
│       │   │   ├── canonicalize.py  # Claim canonicalization.
│       │   │   ├── citations.py  # Citation tracking.
│       │   │   ├── errors.py  # Claims error types.
│       │   │   ├── extraction.py  # Claim extraction.
│       │   │   ├── extractor_registry.py  # Extractor plugin registry.
│       │   │   ├── normalize.py  # Claim normalization.
│       │   │   ├── persist.py  # Claim persistence.
│       │   │   ├── types.py  # Claim type definitions.
│       │   │   ├── world_events.py  # World event generation from claims.
│       │   │   ├── backends/  # Claim extraction backends.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── explicit_lines_v1.py  # Explicit lines extractor.
│       │   │   │   ├── lex_norm_regex_v1.py  # Lex norm regex extractor.
│       │   │   │   └── regex_numeric_v1.py  # Regex numeric extractor.
│       │   │   └── conflicts/  # Conflict detection and resolution.
│       │   │       ├── __init__.py
│       │   │       ├── detect.py  # Conflict detection.
│       │   │       ├── key.py  # Conflict key generation.
│       │   │       ├── policies.py  # Resolution policies.
│       │   │       ├── resolve.py  # Conflict resolution.
│       │   │       ├── score_claims.py  # Claim scoring.
│       │   │       ├── score_docs.py  # Document scoring.
│       │   │       ├── types.py  # Conflict type definitions.
│       │   │       └── uncertainty_adapter.py  # Uncertainty integration.
│       │   ├── connectors/  # External data source connectors.
│       │   │   ├── __init__.py
│       │   │   ├── _registry_errors.py  # Registry error types.
│       │   │   ├── _registry_lifecycle.py  # Registry lifecycle management.
│       │   │   ├── _registry_models.py  # Registry internal models.
│       │   │   ├── base.py  # BaseConnector protocol.
│       │   │   ├── capabilities.py  # Protocol compliance checking.
│       │   │   ├── components.py  # Connector component definitions.
│       │   │   ├── components_bridge.py  # Connector↔component system bridge.
│       │   │   ├── discovery.py  # Connector discovery.
│       │   │   ├── pool.py  # Connection pooling.
│       │   │   ├── registry.py  # Connector registry facade.
│       │   │   ├── registry_core.py  # Core registry implementation.
│       │   │   ├── registry_core_parts.py  # Decomposed registry helpers.
│       │   │   ├── validation.py  # Input validation.
│       │   │   ├── bindings/  # Metric→source binding profiles.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── builtin_profiles.py  # Built-in binding profile definitions.
│       │   │   │   ├── models.py  # Binding data models.
│       │   │   │   ├── registry.py  # Binding profile registry.
│       │   │   │   └── resolver.py  # Binding resolution logic.
│       │   │   ├── cache/  # CAS-based caching.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── _store_core.py  # Core cache store logic.
│       │   │   │   ├── _store_index.py  # Cache index management.
│       │   │   │   ├── _store_models.py  # Cache entry models.
│       │   │   │   ├── _store_serialization.py  # Cache serialization.
│       │   │   │   ├── invalidation.py  # Cache invalidation.
│       │   │   │   ├── policy.py  # TTL policies.
│       │   │   │   ├── prefetch.py  # Prefetching.
│       │   │   │   ├── proxy.py  # Caching proxy layer.
│       │   │   │   ├── schema_aware.py  # Schema-aware cache keying.
│       │   │   │   └── store.py  # CAS cache store facade.
│       │   │   ├── contracts/  # Schema evolution and data contracts.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── _inference_config.py  # Schema inference configuration.
│       │   │   │   ├── _inference_engine.py  # Schema inference engine.
│       │   │   │   ├── _inference_result.py  # Inference result models.
│       │   │   │   ├── _inference_validation.py  # Inference validation.
│       │   │   │   ├── _schema_core.py  # Core schema operations.
│       │   │   │   ├── _schema_errors.py  # Schema error types.
│       │   │   │   ├── _schema_field.py  # Schema field definitions.
│       │   │   │   ├── _schema_types.py  # Schema type system.
│       │   │   │   ├── contract.py  # Connector data contracts.
│       │   │   │   ├── contract_registry.py  # Contract registry.
│       │   │   │   ├── evolution.py  # Contract evolution.
│       │   │   │   ├── inference.py  # Schema inference facade.
│       │   │   │   ├── registry.py  # Schema registry.
│       │   │   │   ├── schema.py  # Schema management.
│       │   │   │   └── validation_middleware.py  # Contract validation middleware.
│       │   │   ├── federation/  # Cross-connector federation.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── composer.py  # Federation composition.
│       │   │   │   ├── evidence_aggregation.py  # Evidence aggregation.
│       │   │   │   ├── planner.py  # Federation query planning.
│       │   │   │   ├── ranker.py  # Source ranking.
│       │   │   │   ├── resolver.py  # Conflict resolution.
│       │   │   │   └── types.py  # Federation types.
│       │   │   ├── profiles/  # Source connection profiles.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── builtin_profiles.py  # Built-in source profile definitions.
│       │   │   │   ├── models.py  # Profile data models.
│       │   │   │   ├── registry.py  # Source profile registry.
│       │   │   │   └── resolver.py  # Profile resolution logic.
│       │   │   ├── quality/  # Data quality assessment.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── completeness.py  # Completeness validation.
│       │   │   │   ├── consistency.py  # Consistency checks.
│       │   │   │   ├── freshness.py  # Freshness assessment.
│       │   │   │   ├── report.py  # Quality reports.
│       │   │   │   └── validator.py  # Quality validation.
│       │   │   ├── reference/  # Reference connector implementations.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── rest_json.py  # REST/JSON connector.
│       │   │   │   ├── sdmx.py  # SDMX connector.
│       │   │   │   └── static_csv.py  # Static CSV connector.
│       │   │   ├── resilience/  # Resilience patterns.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── circuit_breaker.py  # Circuit breaker.
│       │   │   │   ├── fallback.py  # Fallback handling.
│       │   │   │   ├── rate_limiter.py  # Rate limiting.
│       │   │   │   └── retry.py  # Retry logic.
│       │   │   ├── sources/  # Production data source connectors.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── ckan_catalog.py  # CKAN catalog discovery connector.
│       │   │   │   ├── ckan_resource.py  # CKAN resource download connector.
│       │   │   │   ├── eurostat.py  # Eurostat statistics connector.
│       │   │   │   ├── http_base.py  # Shared HTTP connector base class.
│       │   │   │   ├── http_common.py  # Common HTTP utilities.
│       │   │   │   ├── opendatasoft.py  # OpenDataSoft portal connector.
│       │   │   │   ├── rest_json.py  # Generic REST/JSON source connector.
│       │   │   │   ├── sdmx_source.py  # SDMX statistical data connector.
│       │   │   │   ├── socrata.py  # Socrata open data connector.
│       │   │   │   ├── sparql.py  # SPARQL endpoint connector.
│       │   │   │   ├── ukons.py  # UK ONS statistics connector.
│       │   │   │   ├── world_bank.py  # World Bank data connector.
│       │   │   │   └── _contracts/  # Source-specific data contracts.
│       │   │   │       ├── __init__.py
│       │   │   │       ├── eurostat_contracts.py  # Eurostat schema contracts.
│       │   │   │       ├── sdmx_contracts.py  # SDMX schema contracts.
│       │   │   │       ├── ukons_contracts.py  # UK ONS schema contracts.
│       │   │   │       └── world_bank_contracts.py  # World Bank schema contracts.
│       │   │   ├── testing/  # Connector test infrastructure.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── contracts.py  # Test contracts.
│       │   │   │   ├── fixtures.py  # Test fixtures.
│       │   │   │   ├── harness.py  # ConnectorTestHarness.
│       │   │   │   └── simulator.py  # APISimulator.
│       │   │   ├── transform/  # Data transformation pipeline.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── _common.py  # Shared transform utilities.
│       │   │   │   ├── aggregator.py  # Data aggregation.
│       │   │   │   ├── filter.py  # Data filtering.
│       │   │   │   ├── harmonizer.py  # Data harmonization.
│       │   │   │   ├── imputer.py  # Missing data imputation.
│       │   │   │   ├── normalizer.py  # Data normalization.
│       │   │   │   ├── pipeline.py  # Pipeline orchestration.
│       │   │   │   └── validator.py  # Transformation validation.
│       │   │   └── types/  # Type system.
│       │   │       ├── __init__.py
│       │   │       ├── _coercion_engine.py  # Coercion dispatch engine.
│       │   │       ├── _coercion_errors.py  # Coercion error types.
│       │   │       ├── _coercion_policies.py  # Coercion policy definitions.
│       │   │       ├── _coercion_rules.py  # Individual coercion rules.
│       │   │       ├── _units_base.py  # Unit base types.
│       │   │       ├── _units_core.py  # Core unit conversion logic.
│       │   │       ├── _units_errors.py  # Unit conversion errors.
│       │   │       ├── _units_prefixes.py  # SI/metric prefix handling.
│       │   │       ├── _units_registry.py  # Unit registry implementation.
│       │   │       ├── coercion.py  # Type coercion facade.
│       │   │       ├── connector_types.py  # Connector types.
│       │   │       ├── dimensions.py  # Dimensional data types.
│       │   │       ├── temporal.py  # Temporal types.
│       │   │       └── units.py  # Unit conversion facade.
│       │   ├── data_plane/  # Incremental data ingestion and replay.
│       │   │   ├── __init__.py
│       │   │   ├── cursor_store.py  # Cursor-based pagination state store.
│       │   │   ├── modes.py  # Ingestion mode definitions (full/incremental/streaming).
│       │   │   ├── orchestrator.py  # Incremental ingestion orchestrator.
│       │   │   ├── regression.py  # Data regression detection.
│       │   │   ├── replay_store.py  # Record/replay store for ingestion.
│       │   │   └── watermark.py  # High-watermark tracking for incremental loads.
│       │   ├── docs/  # Document processing pipeline.
│       │   │   ├── __init__.py
│       │   │   ├── chunking.py  # Document chunking.
│       │   │   ├── errors.py  # Document errors.
│       │   │   ├── ingestion.py  # Document ingestion.
│       │   │   ├── normalize.py  # Text normalization.
│       │   │   ├── structure.py  # Structure extraction.
│       │   │   ├── types.py  # Document types.
│       │   │   └── backends/  # Format backends.
│       │   │       ├── __init__.py
│       │   │       ├── pdf.py  # PDF processing.
│       │   │       ├── text_html.py  # HTML processing.
│       │   │       └── text_plain.py  # Plain text processing.
│       │   ├── io/  # Storage backends.
│       │   │   ├── __init__.py
│       │   │   └── db.py  # DuckDB backend.
│       │   ├── pii/  # PII detection and redaction.
│       │   │   ├── __init__.py
│       │   │   ├── detector.py  # PII detection engine (Presidio).
│       │   │   ├── models.py  # PII annotation models.
│       │   │   └── stage.py  # PII processing pipeline stage.
│       │   ├── provenance/  # W3C PROV-O provenance.
│       │   │   ├── __init__.py
│       │   │   ├── core.py  # PROV-O graph models.
│       │   │   └── export_provo.py  # PROV-O export.
│       │   ├── retrieval/  # Hybrid data retrieval service.
│       │   │   ├── __init__.py
│       │   │   ├── executor.py  # FetchPlan preview/execute with quality gate.
│       │   │   ├── explore_lane.py  # Bounded on-demand metadata discovery (ExploreLane).
│       │   │   └── service.py  # Hybrid retrieval service (FastLane + ExploreLane + PromotionLane).
│       │   ├── security/  # Fabric-level data security.
│       │   │   ├── __init__.py
│       │   │   └── column_mask.py  # Column-level data masking.
│       │   ├── storage/  # Pluggable storage backends.
│       │   │   ├── __init__.py
│       │   │   ├── duckdb_adapter.py  # DuckDB storage adapter.
│       │   │   ├── memory_adapter.py  # In-memory storage adapter.
│       │   │   └── port.py  # Storage port (abstract interface).
│       │   └── world/  # World model and state management.
│       │       ├── __init__.py
│       │       ├── events.py  # World event bus.
│       │       ├── materialize/  # World materialization.
│       │       │   ├── __init__.py
│       │       │   ├── duckdb.py  # DuckDB materializer.
│       │       │   ├── errors.py  # Materialization errors.
│       │       │   ├── kuzu.py  # Kùzu materializer.
│       │       │   ├── projections.py  # Projection definitions.
│       │       │   ├── rules.py  # Materialization rules.
│       │       │   ├── sql.py  # SQL generation.
│       │       │   └── staging.py  # Staging pipeline.
│       │       └── store/  # World persistence.
│       │           ├── __init__.py
│       │           ├── emit.py  # Event emission.
│       │           ├── errors.py  # Store errors.
│       │           ├── ids.py  # World entity IDs.
│       │           ├── persist.py  # Persistence layer.
│       │           ├── provenance.py  # Store provenance.
│       │           ├── segments.py  # Segment management.
│       │           └── validate.py  # Store validation.
│       ├── foundry/  # JAX execution core: compilation, simulation, calibration, uncertainty.
│       │   ├── __init__.py
│       │   ├── _executor_graph.py  # Executor graph representation.
│       │   ├── _executor_models.py  # Executor internal models.
│       │   ├── _executor_ops.py  # Executor operation primitives.
│       │   ├── _executor_patching.py  # State patching logic.
│       │   ├── _executor_snapshots.py  # Execution snapshot management.
│       │   ├── agent_metrics.py  # Agent-level metrics collection.
│       │   ├── agents.py  # Agent type definitions.
│       │   ├── conflict_checker.py  # Static slot-write conflict detection.
│       │   ├── constraints_engine.py  # Constraint evaluation engine.
│       │   ├── cost_model.py  # Heuristic cost model.
│       │   ├── executor.py  # JAX step/scan/batch executor facade.
│       │   ├── layout.py  # State layout management.
│       │   ├── loss.py  # Loss function utilities.
│       │   ├── merge_engine.py  # CRDT-inspired merge semantics.
│       │   ├── patch_vm.py  # Patch-based virtual machine.
│       │   ├── profiles.py  # Execution profiles.
│       │   ├── queue.py  # Execution queue.
│       │   ├── registry.py  # Foundry component registry.
│       │   ├── specs.py  # Specification models.
│       │   ├── trace.py  # Foundry tracing.
│       │   ├── types.py  # Core Foundry types.
│       │   ├── utils.py  # Foundry utility helpers.
│       │   ├── agent_sim/  # Agent-based simulation subsystem.
│       │   │   ├── __init__.py
│       │   │   ├── actor_critic.py  # Actor-critic RL.
│       │   │   ├── analysis.py  # Simulation analysis.
│       │   │   ├── artifact.py  # Simulation artifacts.
│       │   │   ├── credit_assignment.py  # Credit assignment.
│       │   │   ├── dashboard.py  # Simulation dashboard.
│       │   │   ├── demographics.py  # Demographic modeling.
│       │   │   ├── distribution_executor.py  # Distribution execution.
│       │   │   ├── distribution_mechanisms.py  # Distribution mechanisms.
│       │   │   ├── distributions.py  # Distribution definitions.
│       │   │   ├── evolution.py  # Evolutionary dynamics.
│       │   │   ├── executor.py  # Simulation executor.
│       │   │   ├── experiment.py  # Experiment management.
│       │   │   ├── government_policy.py  # Government policy rules.
│       │   │   ├── graph_executor.py  # Graph-based execution.
│       │   │   ├── graph_mechanisms.py  # Graph mechanisms.
│       │   │   ├── graph_observations.py  # Graph observations.
│       │   │   ├── graphs.py  # Graph structures.
│       │   │   ├── jit_training.py  # JIT-compiled training.
│       │   │   ├── mechanism.py  # Single mechanism abstraction.
│       │   │   ├── mechanisms.py  # Mechanism collection.
│       │   │   ├── metrics.py  # Simulation metrics.
│       │   │   ├── modes.py  # Simulation modes.
│       │   │   ├── mpc.py  # Model predictive control.
│       │   │   ├── policy.py  # Policy definitions.
│       │   │   ├── population.py  # Population modeling.
│       │   │   ├── population_executor.py  # Population executor.
│       │   │   ├── population_mechanisms.py  # Population mechanisms.
│       │   │   ├── prng.py  # PRNG management.
│       │   │   ├── rewards.py  # Reward functions.
│       │   │   ├── rl.py  # Reinforcement learning.
│       │   │   ├── state.py  # Simulation state.
│       │   │   ├── temporal.py  # Temporal dynamics.
│       │   │   ├── temporal_executor.py  # Temporal executor.
│       │   │   ├── temporal_mechanisms.py  # Temporal mechanisms.
│       │   │   ├── training.py  # Training loops.
│       │   │   ├── vfi.py  # Value function iteration.
│       │   │   └── visualization.py  # Simulation visualization.
│       │   ├── analysis/  # Post-simulation analysis.
│       │   │   ├── __init__.py
│       │   │   └── distributional.py  # Distributional impact analysis.
│       │   ├── calibration/  # Gradient-based parameter calibration.
│       │   │   ├── __init__.py
│       │   │   ├── bijectors.py  # Parameter constraint bijectors.
│       │   │   ├── calibrator.py  # Calibrator class.
│       │   │   ├── loss.py  # Calibration loss functions.
│       │   │   ├── preflight.py  # Pre-calibration validation.
│       │   │   ├── pure_executor.py  # JAX pure executor.
│       │   │   ├── report.py  # Calibration reports.
│       │   │   └── uncertainty_adapter.py  # Uncertainty propagation adapter.
│       │   ├── compile/  # Foundry compilation.
│       │   │   ├── __init__.py
│       │   │   ├── _graph.py  # Internal graph representation.
│       │   │   ├── api.py  # Compilation public API.
│       │   │   └── trinity_compiler.py  # Trinity→Foundry compiler.
│       │   ├── contracts/  # Foundry-level contracts.
│       │   │   ├── __init__.py
│       │   │   ├── fidelity.py  # Simulation fidelity contracts.
│       │   │   ├── mechanism.py  # Mechanism contracts.
│       │   │   └── state.py  # State contracts.
│       │   ├── data_plane/  # Foundry↔Fabric data bindings.
│       │   │   ├── __init__.py
│       │   │   └── bindings.py  # Input/output data binding definitions.
│       │   ├── domain/  # Economic domain schemas.
│       │   │   ├── __init__.py
│       │   │   └── schema.py  # Domain schema definitions.
│       │   ├── execute/  # Execution orchestration.
│       │   │   ├── __init__.py
│       │   │   └── api.py  # Execution public API.
│       │   ├── mechanisms/  # Reusable economic mechanisms.
│       │   │   ├── __init__.py
│       │   │   ├── fiscal.py  # Fiscal policy mechanisms.
│       │   │   ├── labor.py  # Labor market mechanisms.
│       │   │   └── treasury.py  # RNG/seed treasury.
│       │   ├── methods/  # Method implementations and catalog.
│       │   │   ├── __init__.py
│       │   │   ├── _artifacts_chain.py  # Chain artifact tracking.
│       │   │   ├── _artifacts_evidence.py  # Evidence artifact handling.
│       │   │   ├── _artifacts_fingerprint.py  # Artifact fingerprint computation.
│       │   │   ├── _artifacts_method.py  # Method artifact management.
│       │   │   ├── _artifacts_records.py  # Artifact record types.
│       │   │   ├── artifacts.py  # Method artifact facade.
│       │   │   ├── artifacts_parts.py  # Decomposed artifact helpers.
│       │   │   ├── base.py  # Base method protocol.
│       │   │   ├── catalog_snapshot.py  # Method catalog snapshot builder from MethodRegistry.
│       │   │   ├── compiler.py  # Method compiler.
│       │   │   ├── components_bridge.py  # Component system bridge.
│       │   │   ├── composer.py  # Method composition.
│       │   │   ├── discovery.py  # Method discovery.
│       │   │   ├── exceptions.py  # Method exceptions.
│       │   │   ├── linker.py  # Method linker.
│       │   │   ├── registry.py  # Method registry.
│       │   │   ├── resolution.py  # Method resolution.
│       │   │   ├── specialization.py  # Method specialization.
│       │   │   ├── backends/  # Execution backends.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── adapters.py  # Backend adapters.
│       │   │   │   ├── chain_executor.py  # Chain execution.
│       │   │   │   ├── dispatch.py  # Backend dispatch.
│       │   │   │   ├── jax_runner.py  # JAX runner.
│       │   │   │   ├── numpy_runner.py  # NumPy runner.
│       │   │   │   ├── protocol.py  # Backend protocol.
│       │   │   │   └── solver_runner.py  # Solver runner (OR-Tools/PuLP).
│       │   │   ├── catalog/  # Built-in method catalog.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── causal/  # Causal inference methods.
│       │   │   │   │   ├── __init__.py
│       │   │   │   │   ├── _common.py  # Shared causal utilities.
│       │   │   │   │   ├── _econml_adapter.py  # EconML integration.
│       │   │   │   │   ├── _graph_projection.py  # PAG→DAG graph projection.
│       │   │   │   │   ├── _registry_boot.py  # Auto-registration.
│       │   │   │   │   ├── cate.py  # CATE estimation.
│       │   │   │   │   ├── ci_backends.py  # CI backend selection and dispatch.
│       │   │   │   │   ├── constraint_discovery.py  # Constraint-based causal discovery (PC/FCI).
│       │   │   │   │   ├── dagma_discovery.py  # DAGMA continuous causal discovery.
│       │   │   │   │   ├── did.py  # Difference-in-differences.
│       │   │   │   │   ├── dml.py  # Double machine learning.
│       │   │   │   │   ├── dowhy_identify_estimate.py  # DoWhy identification and estimation.
│       │   │   │   │   ├── dowhy_refute.py  # DoWhy refutation tests.
│       │   │   │   │   ├── full_transport_bridge.py  # Full transportability bridge (symbolic + data).
│       │   │   │   │   ├── gcm_fit.py  # DoWhy GCM model fitting.
│       │   │   │   │   ├── gcm_query.py  # DoWhy GCM counterfactual/attribution queries.
│       │   │   │   │   ├── graph_reconciliation.py  # Multi-source causal graph reconciliation.
│       │   │   │   │   ├── literature_prior.py  # Literature-based parameter prior construction.
│       │   │   │   │   ├── meta_learners.py  # Meta-learner methods.
│       │   │   │   │   ├── parameter_transfer.py  # Cross-context parameter transfer.
│       │   │   │   │   ├── pcmci_discovery.py  # PCMCI temporal causal discovery.
│       │   │   │   │   ├── policy_learning.py  # Policy learning.
│       │   │   │   │   ├── protocols.py  # Causal method protocols.
│       │   │   │   │   ├── rdd.py  # Regression discontinuity.
│       │   │   │   │   ├── scm.py  # Legacy shim for synthetic_control.py.
│       │   │   │   │   ├── sensitivity_metrics.py  # Sensitivity analysis metrics (E-value, Rosenbaum).
│       │   │   │   │   ├── structural_time_series.py  # Structural time series.
│       │   │   │   │   ├── symbolic_identify.py  # Symbolic causal identification (y0).
│       │   │   │   │   ├── synthetic_control.py  # Synthetic Control method (Abadie).
│       │   │   │   │   └── transport_check.py  # S-node transportability elimination checks.
│       │   │   │   ├── econometrics/  # Econometric methods.
│       │   │   │   │   ├── __init__.py
│       │   │   │   │   ├── _registry_boot.py  # Auto-registration.
│       │   │   │   │   ├── iv.py  # Instrumental variables.
│       │   │   │   │   ├── panel.py  # Panel data models.
│       │   │   │   │   ├── protocols.py  # Econometric protocols.
│       │   │   │   │   └── timeseries.py  # Time series models.
│       │   │   │   └── optimization/  # Optimization methods.
│       │   │   │       ├── __init__.py
│       │   │   │       ├── _registry_boot.py  # Auto-registration.
│       │   │   │       ├── io_model.py  # Input-output model.
│       │   │   │       ├── lp.py  # Linear programming.
│       │   │   │       ├── milp.py  # Mixed-integer linear programming.
│       │   │   │       └── protocols.py  # Optimization protocols.
│       │   │   ├── causal/  # Causal method standalone wrappers.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── _common.py  # Shared causal utilities.
│       │   │   │   ├── _econml_adapter.py  # EconML integration.
│       │   │   │   ├── _registry_boot.py  # Auto-registration.
│       │   │   │   ├── cate.py  # CATE estimation wrapper.
│       │   │   │   ├── ci_backends.py  # CI backend selection wrapper.
│       │   │   │   ├── constraint_discovery.py  # Constraint-based discovery wrapper.
│       │   │   │   ├── dagma_discovery.py  # DAGMA discovery wrapper.
│       │   │   │   ├── did.py  # DiD wrapper.
│       │   │   │   ├── dml.py  # DML wrapper.
│       │   │   │   ├── dowhy_identify_estimate.py  # DoWhy identify+estimate wrapper.
│       │   │   │   ├── dowhy_refute.py  # DoWhy refutation wrapper.
│       │   │   │   ├── gcm_fit.py  # GCM fitting wrapper.
│       │   │   │   ├── gcm_query.py  # GCM query wrapper.
│       │   │   │   ├── graph_reconciliation.py  # Graph reconciliation wrapper.
│       │   │   │   ├── literature_prior.py  # Literature prior wrapper.
│       │   │   │   ├── meta_learners.py  # Meta-learner wrapper.
│       │   │   │   ├── policy_learning.py  # Policy learning wrapper.
│       │   │   │   ├── protocols.py  # Causal protocols.
│       │   │   │   ├── rdd.py  # RDD wrapper.
│       │   │   │   ├── scm.py  # Legacy shim wrapper.
│       │   │   │   ├── sensitivity_metrics.py  # Sensitivity metrics wrapper.
│       │   │   │   ├── structural_time_series.py  # STS wrapper.
│       │   │   │   ├── symbolic_identify.py  # Symbolic identification wrapper.
│       │   │   │   └── synthetic_control.py  # Synthetic Control wrapper.
│       │   │   ├── econometrics/  # Econometric method standalone wrappers.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── _registry_boot.py  # Auto-registration.
│       │   │   │   ├── iv.py  # IV wrapper.
│       │   │   │   ├── panel.py  # Panel data wrapper.
│       │   │   │   ├── protocols.py  # Econometric protocols.
│       │   │   │   └── timeseries.py  # Time series wrapper.
│       │   │   ├── optimization/  # Optimization method standalone wrappers.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── _registry_boot.py  # Auto-registration.
│       │   │   │   ├── io_model.py  # IO model wrapper.
│       │   │   │   ├── lp.py  # LP wrapper.
│       │   │   │   ├── milp.py  # MILP wrapper.
│       │   │   │   └── protocols.py  # Optimization protocols.
│       │   │   ├── testing/  # Method testing infrastructure.
│       │   │   │   ├── __init__.py
│       │   │   │   ├── fixtures.py  # Test fixtures.
│       │   │   │   ├── golden.py  # Golden-file testing.
│       │   │   │   ├── jax_suite.py  # JAX backend test suite.
│       │   │   │   ├── numpy_suite.py  # NumPy backend test suite.
│       │   │   │   ├── solver_suite.py  # Solver backend test suite.
│       │   │   │   └── suite.py  # General test suite.
│       │   │   └── types/  # Method type system.
│       │   │       ├── __init__.py
│       │   │       ├── checker.py  # Type checker.
│       │   │       └── units.py  # Unit types.
│       │   ├── plugins/  # Plugin system.
│       │   │   ├── __init__.py
│       │   │   ├── api.py  # Plugin public API.
│       │   │   ├── cli.py  # Plugin CLI (polisy command).
│       │   │   ├── composite.py  # Composite plugins.
│       │   │   ├── core.py  # Plugin core.
│       │   │   ├── discovery.py  # Plugin discovery.
│       │   │   └── economics/  # Economics plugin.
│       │   │       ├── __init__.py
│       │   │       ├── mechanisms.py  # Economic mechanisms.
│       │   │       ├── objectives.py  # Economic objectives.
│       │   │       ├── plugin.py  # Plugin definition.
│       │   │       ├── rewards.py  # Economic rewards.
│       │   │       └── state.py  # Economic state.
│       │   ├── runtime/  # Runtime utilities.
│       │   │   ├── __init__.py
│       │   │   ├── fingerprint.py  # Environment fingerprinting.
│       │   │   └── nan_guard.py  # NaN/Inf detection.
│       │   └── uncertainty/  # Uncertainty propagation framework.
│       │       ├── __init__.py
│       │       ├── aggregator.py  # Uncertainty aggregation.
│       │       ├── analytical.py  # Analytical propagation.
│       │       ├── config.py  # Uncertainty configuration.
│       │       ├── covariance.py  # Covariance tracking.
│       │       ├── delta.py  # Delta method propagation.
│       │       ├── dispatcher.py  # Method dispatch.
│       │       ├── monte_carlo.py  # Monte Carlo propagation.
│       │       └── protocol.py  # Uncertainty protocol.
│       ├── ir/  # Canonical IR: TrinityBundle, kernel registries, loaders, validation.
│       │   ├── __init__.py
│       │   ├── canon.py  # Canonical representations.
│       │   ├── citations.py  # Citation tracking models.
│       │   ├── connectors.py  # Connector IR integration.
│       │   ├── fact_log.py  # Fact log IR models.
│       │   ├── loaders.py  # Universal policy loader.
│       │   ├── migration_report.py  # Migration report models.
│       │   ├── model_spec.py  # ModelSpec (data snapshots, assumptions).
│       │   ├── norm_pack.py  # NormPack/NormRule contracts.
│       │   ├── portfolio.py  # Policy portfolio models.
│       │   ├── predicate.py  # Predicate expressions.
│       │   ├── queries.py  # IR query models.
│       │   ├── refs.py  # IR reference types.
│       │   ├── registry_fragments.py  # IR registry fragments.
│       │   ├── types.py  # IR type definitions.
│       │   ├── units.py  # Unit system models.
│       │   ├── analytics/  # Analytical IR models.
│       │   │   ├── __init__.py
│       │   │   ├── abm_bridge.py  # ABM↔causal alignment status and reports.
│       │   │   ├── alignment_certification.py  # Alignment certification policy and bounded search.
│       │   │   ├── applicability.py  # Policy applicability checks.
│       │   │   ├── backtest.py  # Backtesting IR models.
│       │   │   ├── calibration.py  # Calibration IR models.
│       │   │   ├── causal.py  # Causal effect IR models.
│       │   │   ├── causal_discovery.py  # Causal discovery report IR models.
│       │   │   ├── causal_ensemble.py  # Causal model ensemble IR models.
│       │   │   ├── causal_graph.py  # Causal graph IR models (DAG/CPDAG/PAG).
│       │   │   ├── causal_graph_kuzu.py  # Kùzu-backed causal graph persistence.
│       │   │   ├── causal_queries.py  # Causal query and result IR models.
│       │   │   ├── context.py  # Context-adaptive parameter inference profiles.
│       │   │   ├── data_views.py  # Data view definitions.
│       │   │   ├── distributional.py  # Distributional analysis IR.
│       │   │   ├── hte.py  # HTE result IR models.
│       │   │   ├── literature.py  # Literature-based causal prior IR models.
│       │   │   ├── parameters.py  # Parameter applicability IR models.
│       │   │   ├── partial_identification.py  # Partial identification with Manski bounds.
│       │   │   ├── sensitivity.py  # Sensitivity analysis result IR (E-value).
│       │   │   ├── structural_causal_model.py  # Structural causal model spec IR.
│       │   │   ├── transportability.py  # Transportability result IR models.
│       │   │   └── uncertainty.py  # Uncertainty envelope IR.
│       │   ├── artifacts/  # IR artifact contracts and I/O.
│       │   │   ├── __init__.py
│       │   │   ├── contracts.py  # Artifact contract definitions.
│       │   │   └── io.py  # Artifact serialization/deserialization.
│       │   ├── governance/  # Governance-related IR models.
│       │   │   ├── __init__.py
│       │   │   ├── gate.py  # Gate context/decision IR models.
│       │   │   ├── policy_spec.py  # PolicySpec (interventions).
│       │   │   ├── problem_frame.py  # ProblemFrame (goals/KPIs).
│       │   │   ├── schedule.py  # Schedule models.
│       │   │   ├── selector_expr.py  # Selector expressions.
│       │   │   └── validation.py  # IR validation.
│       │   ├── kernel/  # Kernel registries: mechanisms, slots, units, rules.
│       │   │   ├── __init__.py
│       │   │   ├── base.py  # Kernel base types.
│       │   │   ├── constraints.py  # Kernel constraints.
│       │   │   ├── mechanisms.py  # Mechanism registry.
│       │   │   ├── merge_rules.py  # Merge rule registry.
│       │   │   ├── metrics.py  # Kernel metrics.
│       │   │   ├── numbers.py  # Numeric type registry.
│       │   │   ├── selector_fields.py  # Selector field registry.
│       │   │   ├── slots.py  # Slot registry.
│       │   │   ├── time_semantics.py  # Time semantics registry.
│       │   │   ├── trust.py  # Trust level registry.
│       │   │   ├── units.py  # Unit registry.
│       │   │   └── values.py  # Value type registry.
│       │   ├── linker/  # IR linking and dependency resolution.
│       │   │   ├── __init__.py
│       │   │   ├── _trinity_linker.py  # Trinity linker implementation.
│       │   │   ├── _trinity_mechanisms.py  # Trinity mechanism resolution.
│       │   │   ├── _trinity_models.py  # Trinity linker models.
│       │   │   ├── _trinity_params.py  # Trinity parameter resolution.
│       │   │   ├── link_trinity.py  # Trinity linking facade.
│       │   │   ├── reports.py  # Linker reports.
│       │   │   └── types.py  # Linker types.
│       │   ├── migrations/  # IR format migrations.
│       │   │   ├── __init__.py
│       │   │   ├── base.py  # Migration base.
│       │   │   ├── policy_ir.py  # Policy IR migrations.
│       │   │   └── trinity_migration.py  # Trinity migration.
│       │   ├── trinity/  # Trinity artifact processing.
│       │   │   ├── __init__.py
│       │   │   └── loaders.py  # Trinity loaders.
│       │   └── world/  # World model IR.
│       │       ├── __init__.py
│       │       ├── abi.py  # World ABI definitions.
│       │       ├── claim.py  # Claim models.
│       │       ├── conflict.py  # Conflict models.
│       │       ├── doc.py  # Document models.
│       │       ├── event.py  # Event models.
│       │       ├── ids.py  # World entity IDs.
│       │       ├── predicates.py  # World predicates.
│       │       ├── quality.py  # Quality models.
│       │       └── trust.py  # Trust models.
│       ├── lex/  # Legal corpus and norm evaluation.
│       │   ├── __init__.py
│       │   ├── api.py  # Lex public API.
│       │   ├── artifacts.py  # Lex artifact management.
│       │   ├── common.py  # Shared lex utilities.
│       │   ├── errors.py  # Lex error types.
│       │   ├── factlog.py  # Lex fact log integration.
│       │   ├── types.py  # Lex type definitions.
│       │   ├── batch/  # Lex batch pipeline for legal document processing.
│       │   │   ├── __init__.py
│       │   │   ├── __main__.py  # Module entry point.
│       │   │   ├── canonicalizers.py  # Canonicalizers for SPO extraction.
│       │   │   ├── cli.py  # CLI entry point for Lex batch pipeline.
│       │   │   ├── config.py  # Configuration for Lex batch pipeline.
│       │   │   ├── deterministic_spo.py  # Deterministic SPO extractor used before LLM routing.
│       │   │   ├── domain_classifier.py  # Deterministic domain classifier for legal documents.
│       │   │   ├── embedder.py  # Generate embeddings and build HNSW indexes.
│       │   │   ├── graph_builder.py  # Stream SPO results into DuckDB knowledge graph.
│       │   │   ├── llm_gate.py  # Two-stage LLM gate for Lex SPO extraction.
│       │   │   ├── openai_batch_embeddings.py  # OpenAI Batch API workflow for embeddings.
│       │   │   ├── pipeline.py  # Orchestrate all stages of the batch pipeline.
│       │   │   ├── progress.py  # Checkpoint/resume tracker for batch pipeline.
│       │   │   ├── provisions_io.py  # Disk helpers for Stage 2 provisions with shard prefix.
│       │   │   ├── publish.py  # Publish manifest writer for Lex artifacts.
│       │   │   ├── qc.py  # QC stage for Lex pipeline outputs.
│       │   │   ├── quality_report.py  # Quality report and quality gates.
│       │   │   ├── reference_extractor.py  # Deterministic cross-reference extractor for provisions.
│       │   │   ├── rule_classifier.py  # Rule-based pre-classifier for Ukrainian provisions.
│       │   │   ├── spo_cache.py  # SQLite-backed cache for LLM SPO extraction responses.
│       │   │   ├── spo_extractor.py  # Async LLM-based 2-pass SPO extraction.
│       │   │   ├── spo_prompts.py  # Prompt templates for Ukrainian legal provision extraction.
│       │   │   ├── structurer.py  # Lightweight provision extraction using UA regex.
│       │   │   ├── template_extractor.py  # Template-based SPO extraction for structured documents.
│       │   │   └── xml_parser.py  # Stream-parse ЄДРНПА XML dumps into NPADocument objects.
│       │   ├── corpus/  # Legal document corpus.
│       │   │   ├── __init__.py
│       │   │   ├── index.py  # Corpus indexing.
│       │   │   ├── ingest.py  # Corpus ingestion.
│       │   │   ├── structure.py  # Document structure.
│       │   │   └── versioning.py  # Corpus versioning.
│       │   ├── knowledge/  # Legal knowledge graph.
│       │   │   ├── __init__.py
│       │   │   ├── search.py  # Hybrid search API for legal knowledge graph.
│       │   │   ├── store.py  # Read-only DuckDB knowledge graph + HNSW vector indexes.
│       │   │   └── types.py  # Domain types for knowledge graph (SPO entities, facts).
│       │   ├── legal_evaluation/  # Legal rule evaluation.
│       │   │   ├── __init__.py
│       │   │   ├── change_proposals.py  # Legal change proposals.
│       │   │   ├── context_builder.py  # Evaluation context.
│       │   │   ├── evaluate.py  # Rule evaluation.
│       │   │   ├── evaluator_registry.py  # Evaluator plugin registry.
│       │   │   ├── transport_constraints.py  # Transport constraint evaluation for legal norms.
│       │   │   └── backends/  # Evaluation backends.
│       │   │       ├── __init__.py
│       │   │       └── simple_v1.py  # Simple evaluator.
│       │   ├── normpack/  # Norm pack assembly.
│       │   │   ├── __init__.py
│       │   │   ├── applicability.py  # Norm applicability.
│       │   │   ├── assemble_pack.py  # Pack assembly.
│       │   │   ├── extract_norm_claims.py  # Norm claim extraction.
│       │   │   ├── policies.py  # Norm policies.
│       │   │   ├── provider_registry.py  # Provider registry.
│       │   │   └── select_sources.py  # Source selection.
│       │   └── simulator/  # Lex regulatory change simulator.
│       │       ├── __init__.py
│       │       ├── cli.py  # Simulator CLI.
│       │       ├── diff.py  # Norm diff computation.
│       │       ├── engine.py  # Simulation engine.
│       │       ├── mutator.py  # Norm mutation.
│       │       └── report.py  # Simulation reports.
│       ├── academic/  # Academic literature pipeline: OpenAlex harvesting, extraction, knowledge graph.
│       │   ├── __init__.py
│       │   ├── trust.py  # Trust scoring for academic works and parameter estimates.
│       │   ├── batch/  # Staged academic knowledge pipeline.
│       │   │   ├── __init__.py
│       │   │   ├── article_extractor.py  # Compatibility wrapper + extraction helpers reused by resolve_extract.
│       │   │   ├── cli.py  # CLI for staged academic knowledge pipeline.
│       │   │   ├── config.py  # Pipeline configuration.
│       │   │   ├── context_classifier.py  # Context inference for article extraction.
│       │   │   ├── dedup.py  # Merge and deduplicate by OpenAlex work id.
│       │   │   ├── embedder.py  # Build local embeddings + HNSW index.
│       │   │   ├── graph_builder.py  # Load records into DuckDB and build indexes.
│       │   │   ├── harvester.py  # Materialize topic-selected OpenAlex works.
│       │   │   ├── parser.py  # Parse OpenAlex raw payloads into WorkRecord rows.
│       │   │   ├── pipeline.py  # Thin orchestrator for staged academic pipeline.
│       │   │   ├── publish.py  # Publish academic pipeline artifacts.
│       │   │   ├── qc.py  # QC checks for academic pipeline.
│       │   │   ├── resolve_extract.py  # Streaming fulltext-first one-call extraction + deterministic publish gating.
│       │   │   ├── topic_select.py  # Topic-based OpenAlex selection (Pass 1).
│       │   │   └── prompts/  # LLM prompt templates for extraction.
│       │   │       ├── __init__.py
│       │   │       ├── boundary_conditions.py  # Boundary-condition extraction schema.
│       │   │       ├── causal_claims.py  # Causal-claims extraction schema.
│       │   │       ├── mechanisms.py  # Mechanism extraction schema.
│       │   │       └── screening.py  # Relevance screening prompt.
│       │   ├── knowledge/  # Academic knowledge graph store and search.
│       │   │   ├── __init__.py
│       │   │   ├── canonical_seed.py  # Canonical variable seed dictionary.
│       │   │   ├── parameter_selector.py  # Parameter selection from SKG.
│       │   │   ├── search.py  # Hybrid search API for academic knowledge graph.
│       │   │   ├── skg_query.py  # Topic/run-aware SKG query helpers.
│       │   │   ├── skg_store.py  # SKG table DDL and confidence aggregation.
│       │   │   ├── skg_versioning.py  # SKG versioning and retraction handling.
│       │   │   ├── store.py  # Read-only DuckDB + HNSW vector index access.
│       │   │   ├── types.py  # Domain types (works, estimates, claims, priors).
│       │   │   └── variable_canonizer.py  # Hierarchical variable canonization.
│       │   └── openalex/  # OpenAlex API integration.
│       │       ├── __init__.py
│       │       ├── client.py  # Async OpenAlex client for topic-based harvesting.
│       │       ├── priority_filter.py  # Priority filter for policy-relevant works.
│       │       ├── rate_limiter.py  # Async rate limiter with backoff.
│       │       ├── selector.py  # Topic-based OpenAlex selector (150 works/topic).
│       │       └── topic_catalog.py  # Topic catalog loader from CSV slices.
│       ├── batch_common/  # Shared batch pipeline utilities across academic/datasets/lex.
│       │   ├── __init__.py
│       │   ├── hashing.py  # Hashing helpers for reproducible pipeline artifacts.
│       │   ├── manifest.py  # Manifest writers for raw/stage/publish artifacts.
│       │   ├── paths.py  # Filesystem layout helpers for snapshot-based runs.
│       │   ├── phase0_quality_validation.py  # Phase-0 deterministic quality validation.
│       │   ├── qc.py  # Common QC model and fail-fast evaluator.
│       │   └── thermal.py  # Thermal-safe pacing helpers for laptop-friendly runs.
│       ├── batch_snapshot/  # Unified pipeline snapshot finalization.
│       │   ├── __init__.py
│       │   └── cli.py  # CLI to finalize a unified pipeline snapshot manifest.
│       ├── datasets/  # Dataset catalog pipeline: harvesting, normalization, knowledge graph.
│       │   ├── __init__.py
│       │   ├── metrics_map.py  # PolicyOS metrics → dataset indicator mapping.
│       │   ├── batch/  # Staged dataset catalog pipeline.
│       │   │   ├── __init__.py
│       │   │   ├── cli.py  # CLI for staged dataset catalog pipeline.
│       │   │   ├── config.py  # Pipeline configuration.
│       │   │   ├── core_sources_ingest.py  # Ingest core transportability sources (WGI/WDI/WVS).
│       │   │   ├── dedup.py  # Merge and deduplicate by source+agency+dataset_id.
│       │   │   ├── embedder.py  # Build local embeddings + HNSW index for datasets.
│       │   │   ├── graph_builder.py  # Load records into DuckDB and build indexes.
│       │   │   ├── harvester.py  # Source-driven harvest with wave support.
│       │   │   ├── normalizer.py  # Normalize raw payloads to DCAT-like canonical form.
│       │   │   ├── pipeline.py  # Thin orchestrator for staged dataset pipeline.
│       │   │   ├── publish.py  # Publish dataset pipeline artifacts.
│       │   │   ├── qc.py  # QC checks for datasets pipeline.
│       │   │   └── source_registry.py  # Dataset source registry for staged harvest waves.
│       │   └── knowledge/  # Dataset catalog knowledge graph store and search.
│       │       ├── __init__.py
│       │       ├── proxy_resolver.py  # Proxy resolution for transportability.
│       │       ├── registry.py  # Dataset registry API for canonical variable lookup.
│       │       ├── search.py  # Hybrid search API for dataset catalog graph.
│       │       ├── store.py  # Read-only DuckDB catalog + HNSW vector index.
│       │       ├── types.py  # Domain types (search results, distributions).
│       │       └── variable_alignment.py  # Variable alignment: canonical SKG vars → dataset vars.
│       ├── packs/  # Domain-specific policy packs.
│       │   ├── __init__.py
│       │   ├── econ/  # Economic policy pack.
│       │   │   ├── __init__.py
│       │   │   ├── components.py  # Economic components.
│       │   │   └── ir_fragments.py  # Economic IR fragments.
│       │   └── roads/  # Road infrastructure pack.
│       │       ├── __init__.py
│       │       ├── components.py  # Road components.
│       │       ├── foundry_methods.py  # Road simulation methods.
│       │       ├── ir_fragments.py  # Road IR fragments.
│       │       ├── lex_evaluators.py  # Road legal evaluators.
│       │       ├── norms_provider.py  # Road norm provider.
│       │       └── scholar_extractors.py  # Road claim extractors.
│       ├── runtime/  # Run lifecycle, manifests, HTTP API.
│       │   ├── __init__.py
│       │   ├── api.py  # Runtime lifecycle API.
│       │   ├── manifest.py  # Portable run manifests.
│       │   ├── replay.py  # Run replay infrastructure.
│       │   └── http/  # FastAPI HTTP runtime server.
│       │       ├── __init__.py
│       │       ├── app.py  # FastAPI application factory.
│       │       ├── authz_middleware.py  # Authorization middleware.
│       │       ├── cell_router_middleware.py  # Cell-based request routing.
│       │       ├── dependencies.py  # FastAPI dependency injection.
│       │       ├── errors.py  # HTTP error handlers.
│       │       ├── jwt_auth_middleware.py  # JWT authentication middleware.
│       │       ├── openapi_contract.py  # OpenAPI schema contract validation and example generation.
│       │       ├── routes/  # API route modules.
│       │       │   ├── __init__.py
│       │       │   ├── artifacts.py  # /artifacts endpoints.
│       │       │   ├── control.py  # /api/v1/control/ endpoints (Control Plane).
│       │       │   ├── debug.py  # /debug endpoints.
│       │       │   ├── health.py  # /health endpoints.
│       │       │   └── runs.py  # /runs endpoints.
│       │       └── services/  # Business logic services.
│       │           ├── __init__.py
│       │           ├── artifact_inspector.py  # Artifact inspection service.
│       │           ├── control.py  # Control Plane business logic service.
│       │           ├── debug.py  # Debug service.
│       │           ├── lineage.py  # Lineage tracking service.
│       │           ├── run_index.py  # Run index/search service.
│       │           ├── task_runner.py  # Background task runner for control-plane operations.
│       │           ├── timeline.py  # Timeline service.
│       │           └── adapters/  # Service adapters.
│       │               ├── __init__.py
│       │               └── core_run.py  # Core run adapter.
│       ├── scholar/  # Knowledge discovery layer.
│       │   ├── __init__.py
│       │   ├── api.py  # Scholar public API.
│       │   ├── errors.py  # Scholar errors.
│       │   ├── freshness.py  # Source freshness monitoring.
│       │   ├── freshness_store.py  # Freshness metadata persistence.
│       │   ├── policies.py  # Discovery policies.
│       │   ├── types.py  # Scholar type definitions.
│       │   ├── discover/  # Knowledge discovery.
│       │   │   ├── __init__.py
│       │   │   ├── http_fetch.py  # HTTP-based discovery.
│       │   │   ├── local_files.py  # Local file discovery.
│       │   │   └── manual.py  # Manual entry.
│       │   └── orchestrator/  # Discovery orchestration.
│       │       ├── __init__.py
│       │       ├── bundle.py  # Knowledge bundle assembly.
│       │       └── enrich.py  # Knowledge enrichment.
│       └── scientist/  # Orchestration: agents, workflows, governance, search.
│           ├── __init__.py
│           ├── api.py  # Scientist public API.
│           ├── llm_cycle.py  # Unified LLM policy cycle orchestrator with DAG execution.
│           ├── publisher.py  # Result publishing.
│           ├── replay_backend.py  # Replay backend for re-execution.
│           ├── adapters/  # External system bridges.
│           │   ├── __init__.py
│           │   ├── fabric_bridge.py  # Fabric integration bridge.
│           │   └── foundry_bridge.py  # Foundry integration bridge.
│           ├── agent/  # Hierarchical agent system.
│           │   ├── __init__.py
│           │   ├── _drafter_formatting.py  # Drafter output formatting.
│           │   ├── _drafter_llm.py  # Drafter LLM interaction.
│           │   ├── _drafter_orchestrator.py  # Drafter orchestration logic.
│           │   ├── _drafter_parsing.py  # Drafter response parsing.
│           │   ├── _drafter_passes.py  # Drafter multi-pass processing.
│           │   ├── base.py  # Base agent class.
│           │   ├── code_verifier.py  # Generated code safety verifier.
│           │   ├── constitution.py  # Agent constitutional constraints.
│           │   ├── constraint_context.py  # Constraint context propagation.
│           │   ├── critic.py  # Critic agent.
│           │   ├── data_need_extractor.py  # DataNeedExtractor agent (mock + LLM).
│           │   ├── drafter.py  # Drafter agent facade.
│           │   ├── drafter_clients.py  # Drafter LLM client wrappers.
│           │   ├── drafter_factory.py  # Drafter instance factory.
│           │   ├── drafter_models.py  # Drafter data models.
│           │   ├── drafter_multipass.py  # Multi-pass drafter orchestrator.
│           │   ├── drafter_multipass_parts.py  # Decomposed multi-pass helpers.
│           │   ├── failure_card.py  # Failure card generation.
│           │   ├── failure_index.py  # Failure index for pattern tracking.
│           │   ├── feasibility.py  # Feasibility probe logic.
│           │   ├── feasibility_duckdb.py  # DuckDB-based feasibility checks.
│           │   ├── formalizer.py  # Formalizer agent.
│           │   ├── informed_critic.py  # Evidence-informed critic agent.
│           │   ├── knowledge_base.py  # Agent knowledge base.
│           │   ├── knowledge_tools.py  # Knowledge graph tools for scientist agents.
│           │   ├── memory.py  # Agent memory.
│           │   ├── norm_loader.py  # Norm loading for agent context.
│           │   ├── pi.py  # PI agent.
│           │   ├── prompt.py  # Prompt construction.
│           │   ├── prompts.py  # Prompt templates.
│           │   ├── protocols.py  # Agent protocols.
│           │   ├── rag.py  # RAG index for knowledge retrieval.
│           │   └── reflexion.py  # Self-healing reflexion loop.
│           ├── backtesting/  # Policy backtesting framework.
│           │   ├── __init__.py
│           │   ├── cli.py  # Backtesting CLI.
│           │   ├── evaluator.py  # Backtest evaluator.
│           │   ├── masking.py  # Temporal data masking.
│           │   ├── orchestrator.py  # Backtest orchestrator.
│           │   ├── plan.py  # Backtest plan generation.
│           │   └── trust_scorer.py  # Trust-weighted scoring.
│           ├── compute/  # Compute backend abstraction.
│           │   ├── __init__.py
│           │   ├── job_spec.py  # Job specifications.
│           │   └── runner.py  # Job runner.
│           ├── doe/  # Design of Experiments.
│           │   ├── __init__.py
│           │   ├── analysis.py  # DOE analysis.
│           │   ├── designs.py  # Experimental designs.
│           │   ├── sampling.py  # Sampling strategies.
│           │   └── stress_report.py  # Stress test reports.
│           ├── engine/  # Workflow engine.
│           │   ├── __init__.py
│           │   ├── checkpoint.py  # Workflow checkpointing.
│           │   ├── context.py  # Execution context.
│           │   ├── errors.py  # Engine errors.
│           │   ├── executor.py  # Workflow executor.
│           │   ├── idempotency.py  # Idempotent execution.
│           │   ├── iteration_state_machine.py  # Iteration lifecycle state machine transitions.
│           │   ├── protocol.py  # Engine protocol.
│           │   ├── registry.py  # Node registry.
│           │   ├── state.py  # Workflow state.
│           │   ├── telemetry.py  # Engine telemetry.
│           │   ├── workflow_spec.py  # Workflow specification.
│           │   └── builtins/  # Built-in operations.
│           │       ├── __init__.py
│           │       ├── emit_artifact.py  # Artifact emission.
│           │       ├── noop.py  # No-op node.
│           │       └── set_state.py  # State setter.
│           ├── governance/  # Governance pipeline.
│           │   ├── __init__.py
│           │   ├── pass_entrypoints.py  # Pass entrypoint discovery.
│           │   ├── pass_registry.py  # Pass registry for dynamic pass loading.
│           │   ├── pipeline.py  # Pipeline orchestrator.
│           │   ├── postflight.py  # Post-execution validation.
│           │   ├── preflight.py  # Pre-execution validation.
│           │   ├── profiles.py  # Validation profiles (fast/mvp/strict).
│           │   ├── report.py  # Governance reports.
│           │   ├── telemetry.py  # Governance telemetry.
│           │   ├── legal/  # Legal compliance.
│           │   │   ├── __init__.py
│           │   │   ├── ast_policy.py  # AST allowlist policy.
│           │   │   └── backends/  # Legal rule backends.
│           │   │       ├── __init__.py
│           │   │       ├── base.py  # Backend base.
│           │   │       ├── expr_ast.py  # Safe AST interpreter.
│           │   │       └── stub.py  # Stub backend.
│           │   └── passes/  # Validation passes.
│           │       ├── __init__.py
│           │       ├── base.py  # Pass base class.
│           │       ├── budget_pass.py  # Budget checks.
│           │       ├── confidence_pass.py  # Confidence threshold checks.
│           │       ├── equity_pass.py  # Equity/fairness checks.
│           │       ├── human_review_pass.py  # Human review gate pass.
│           │       ├── legal_pass.py  # Legal compliance.
│           │       ├── literature_gate_pass.py  # Literature evidence gate pass.
│           │       ├── pii_check_pass.py  # PII detection governance pass.
│           │       ├── privacy_pass.py  # Privacy checks.
│           │       ├── quality_gate_pass.py  # Quality gates.
│           │       ├── refutation_pass.py  # Causal refutation gate pass.
│           │       ├── safety_pass.py  # Safety checks.
│           │       ├── schema_pass.py  # Schema validation.
│           │       ├── sutva_check_pass.py  # SUTVA assumption check pass.
│           │       └── transportability_required_pass.py  # Transportability requirement check pass.
│           ├── kernel/  # Scientist kernel.
│           │   ├── __init__.py
│           │   ├── budgets.py  # Budget management.
│           │   ├── fsm.py  # Finite state machine.
│           │   ├── gate_protocol.py  # Human gate protocol.
│           │   └── guards.py  # State transition guards.
│           ├── llm/  # LLM integration and model profile management.
│           │   ├── __init__.py
│           │   ├── factory.py  # Factory helpers for traced gateway-backed LLM clients.
│           │   ├── gateway_client.py  # OpenAI-compatible gateway client for runtime LLM calls.
│           │   ├── traced_client.py  # TracedLLMClient with OTel.
│           │   └── profiles/  # Model profile system for runtime selection.
│           │       ├── __init__.py
│           │       ├── builtin_profiles.py  # Built-in model profiles for dashboard selection.
│           │       ├── models.py  # Model profile data models.
│           │       └── registry.py  # ModelProfileRegistry — in-memory profile registry.
│           ├── nodes/  # Workflow node implementations.
│           │   ├── __init__.py
│           │   └── builtins/  # Built-in nodes.
│           │       ├── __init__.py
│           │       ├── errors.py  # Node errors.
│           │       ├── state_keys.py  # State key constants.
│           │       ├── causal/  # Causal pipeline nodes.
│           │       │   ├── __init__.py
│           │       │   ├── build_literature_prior.py  # Literature prior construction node.
│           │       │   ├── reconcile_causal_graph.py  # Causal graph reconciliation node.
│           │       │   ├── resolve_parameters.py  # Parameter resolution node.
│           │       │   ├── resolve_transport.py  # Transportability resolution node.
│           │       │   ├── run_abm_consistency.py  # ABM consistency check node.
│           │       │   ├── run_causal_ensemble.py  # Causal model ensemble node.
│           │       │   └── run_causal_queries.py  # Causal query execution node.
│           │       ├── compile/  # Compilation nodes.
│           │       │   ├── __init__.py
│           │       │   ├── compile_foundry.py  # Foundry compilation.
│           │       │   └── link_trinity.py  # Trinity linking.
│           │       ├── data/  # Data processing nodes.
│           │       │   ├── __init__.py
│           │       │   ├── bind_foundry_inputs.py  # Foundry input data binding.
│           │       │   ├── build_data_snapshot.py  # Data snapshot.
│           │       │   └── enrich_knowledge.py  # Knowledge enrichment.
│           │       ├── decide/  # Decision nodes.
│           │       │   ├── __init__.py
│           │       │   └── build_decision_packet.py  # Decision packet.
│           │       ├── governance/  # Governance nodes.
│           │       │   ├── __init__.py
│           │       │   ├── data_plane_gate.py  # Data plane access gate.
│           │       │   ├── legal_check.py  # Legal check node.
│           │       │   └── run_governance.py  # Governance node.
│           │       ├── planning/  # Planning and preflight nodes.
│           │       │   ├── __init__.py
│           │       │   ├── build_execution_plan.py  # Execution plan construction node.
│           │       │   ├── build_method_catalog_snapshot.py  # Method catalog snapshot node.
│           │       │   ├── ready_to_run.py  # Ready-to-run gate node.
│           │       │   ├── run_evaluator.py  # Evaluator execution node.
│           │       │   └── run_preflight.py  # Preflight validation node.
│           │       └── simulate/  # Simulation nodes.
│           │           ├── __init__.py
│           │           ├── propagate_uncertainty.py  # Uncertainty propagation.
│           │           ├── run_causal_evaluation.py  # Causal evaluation.
│           │           ├── run_distributional_analysis.py  # Distributional analysis.
│           │           └── run_simulation.py  # Simulation execution.
│           ├── orchestrator/  # High-level orchestration.
│           │   ├── __init__.py
│           │   └── decision_card.py  # Decision card generation.
│           ├── search/  # Search/optimization framework.
│           │   ├── __init__.py
│           │   ├── adversarial.py  # Adversarial search.
│           │   ├── controller.py  # SearchController.
│           │   ├── diversity.py  # Diversity-promoting selection.
│           │   ├── objective.py  # Objective functions.
│           │   ├── portfolio.py  # Policy portfolio optimization.
│           │   ├── sensitivity_adapter.py  # Sensitivity analysis adapter.
│           │   ├── stages.py  # Two-stage evaluation.
│           │   ├── stopping.py  # Stopping criteria.
│           │   └── strategies/  # Search strategies.
│           │       ├── __init__.py
│           │       ├── _deps.py  # Optional dependency checks.
│           │       ├── acquisition.py  # Acquisition functions.
│           │       ├── adapter.py  # Strategy adapter.
│           │       ├── base.py  # Base strategy.
│           │       ├── bayesian.py  # Bayesian optimization.
│           │       ├── codec.py  # Space encoding/decoding.
│           │       ├── errors.py  # Strategy errors.
│           │       ├── grid.py  # Grid search.
│           │       ├── multi_fidelity.py  # Multi-fidelity optimization.
│           │       ├── multi_objective.py  # Multi-objective optimization.
│           │       ├── normalization.py  # Objective normalization.
│           │       ├── objective_adapter.py  # Objective adapter.
│           │       ├── random.py  # Random search.
│           │       ├── resource_arbiter.py  # Resource allocation.
│           │       ├── rl_wrapper.py  # RL strategy wrapper.
│           │       ├── runtime.py  # Runtime strategy utilities.
│           │       ├── space.py  # Search space definitions.
│           │       ├── surrogate.py  # Surrogate modeling.
│           │       └── types.py  # Strategy types.
│           └── workflows/  # Workflow engines and predefined builders.
│               ├── __init__.py
│               ├── builder.py  # Workflow builder.
│               ├── causal_full.py  # Full causal pipeline workflow builder.
│               ├── default.py  # Default workflow.
│               ├── engine_base.py  # Engine base class.
│               ├── engine_langgraph.py  # LangGraph engine.
│               └── engine_simple.py  # Simple sequential engine.
├── schemas/  # ABI schema registry and snapshots.
│   ├── __init__.py
│   ├── abi_models.py  # ABI model definitions for schema generation.
│   ├── runtime_api_v1.openapi.json  # Runtime HTTP API OpenAPI spec.
│   └── snapshots/
│       ├── connectors/  # Connector schema snapshots.
│       │   └── contracts.json  # Connector data contracts.
│       ├── fabric/  # Fabric ABI snapshots.
│       │   ├── _manifest.json  # Fabric schema manifest.
│       │   ├── edge_kind.schema.json  # Edge kind enum.
│       │   └── node_kind.schema.json  # Node kind enum.
│       └── ir/  # IR model JSON Schema snapshots.
│           ├── _manifest.json  # IR schema manifest.
│           ├── abm_alignment_report.schema.json  # ABM alignment report.
│           ├── article_extraction_result.schema.json  # Article extraction result.
│           ├── backtest_report.schema.json  # Backtest report schema.
│           ├── calibration_config.schema.json  # Calibration config.
│           ├── causal_discovery_report.schema.json  # Causal discovery report.
│           ├── causal_effect_report.schema.json  # Causal effect report.
│           ├── causal_graph_model.schema.json  # Causal graph model.
│           ├── causal_model_ensemble.schema.json  # Causal model ensemble.
│           ├── causal_query.schema.json  # Causal query.
│           ├── causal_query_result.schema.json  # Causal query result.
│           ├── certification_result.schema.json  # Certification result.
│           ├── claim.schema.json  # Claim schema.
│           ├── conflict_resolution.schema.json  # Conflict resolution.
│           ├── conflict_set.schema.json  # Conflict set.
│           ├── conflict_set_resolution.schema.json  # Conflict set resolution.
│           ├── context_adaptive_parameter_bundle.schema.json  # Context-adaptive parameter bundle.
│           ├── data_view_request.schema.json  # Data view request.
│           ├── distributional_report.schema.json  # Distributional report.
│           ├── doc_fragment.schema.json  # Document fragment.
│           ├── doc_meta.schema.json  # Document metadata.
│           ├── fact.schema.json  # Fact schema.
│           ├── fact_segment_manifest.schema.json  # Fact segment manifest.
│           ├── gate_context.schema.json  # Gate context.
│           ├── gate_decision.schema.json  # Gate decision.
│           ├── gate_event.schema.json  # Gate event.
│           ├── gate_request.schema.json  # Gate request.
│           ├── hte_result.schema.json  # HTE result.
│           ├── literature_causal_prior.schema.json  # Literature causal prior.
│           ├── model_spec.schema.json  # ModelSpec.
│           ├── norm_pack.schema.json  # NormPack.
│           ├── norm_ref.schema.json  # Norm reference.
│           ├── norm_rule.schema.json  # NormRule.
│           ├── outer_search_result.schema.json  # Outer search result.
│           ├── partial_identification_result.schema.json  # Partial identification result.
│           ├── policy_portfolio.schema.json  # Policy portfolio.
│           ├── policy_recommendation.schema.json  # Policy recommendation.
│           ├── policy_spec.schema.json  # PolicySpec.
│           ├── problem_frame.schema.json  # ProblemFrame.
│           ├── prov_activity.schema.json  # Provenance activity.
│           ├── quality_report.schema.json  # Quality report.
│           ├── refutation_result.schema.json  # Refutation result.
│           ├── sensitivity_result.schema.json  # Sensitivity result.
│           ├── structural_causal_model_spec.schema.json  # Structural causal model spec.
│           ├── transportability_result.schema.json  # Transportability result.
│           ├── trinity_bundle.schema.json  # TrinityBundle.
│           ├── trust_assessment.schema.json  # Trust assessment.
│           ├── uncertainty_envelope.schema.json  # Uncertainty envelope.
│           └── world_event.schema.json  # World event.
├── ops/  # Operations: monitoring, observability, alerting, infra.
│   ├── docker-compose.observability.yml  # Observability stack.
│   ├── grafana/  # Grafana dashboards.
│   │   ├── dashboards/
│   │   │   ├── executive-overview.json  # Executive cost/performance.
│   │   │   ├── foundry-hpc.json  # HPC simulation dashboard.
│   │   │   ├── knowledge-freshness.json  # Knowledge freshness monitoring.
│   │   │   ├── scientist-agents.json  # Agent workflow dashboard.
│   │   │   ├── security-phase4.json  # Security metrics dashboard.
│   │   │   └── slo-overview.json  # SLO tracking dashboard.
│   │   └── provisioning/
│   │       └── dashboards.yml  # Dashboard auto-provisioning.
│   ├── prometheus/  # Prometheus configuration.
│   │   ├── alerts.yml  # Alerting rules.
│   │   ├── prometheus.yml  # Scrape configuration.
│   │   ├── recording_rules.yml  # Metric pre-computation.
│   │   ├── slo_alerts.yml  # SLO alerting rules.
│   │   ├── slo_recording_rules.yml  # SLO recording rules.
│   │   └── rules/  # Additional rule files.
│   │       ├── audit_chain_alerts.yml  # Audit chain integrity alerts.
│   │       └── mtls-rules.yaml  # mTLS monitoring rules.
│   ├── opa/  # OPA policy-as-code.
│   │   └── policies/
│   │       ├── data_classification.rego  # Data classification policy.
│   │       ├── data_classification_test.rego  # Data classification tests.
│   │       ├── decision.rego  # Decision authorization policy.
│   │       ├── decision_test.rego  # Decision policy tests.
│   │       ├── delegation_guard.rego  # Delegation guard policy.
│   │       ├── delegation_guard_test.rego  # Delegation guard tests.
│   │       ├── deploy.rego  # Deployment policy.
│   │       ├── deploy_test.rego  # Deployment policy tests.
│   │       ├── role_access.rego  # Role-based access policy.
│   │       ├── role_access_test.rego  # Role access tests.
│   │       ├── tenant_boundary.rego  # Tenant boundary isolation.
│   │       ├── tenant_boundary_test.rego  # Tenant boundary tests.
│   │       ├── vulnerability.rego  # Vulnerability policy.
│   │       └── vulnerability_test.rego  # Vulnerability policy tests.
│   ├── helm/  # Helm charts for Kubernetes deployment.
│   │   ├── polisyos-cell/  # Cell isolation Helm chart.
│   │   │   ├── Chart.yaml  # Chart metadata.
│   │   │   ├── values.yaml  # Default values.
│   │   │   ├── policies/  # OPA policies bundled in chart.
│   │   │   │   ├── data_classification.rego  # Data classification.
│   │   │   │   ├── decision.rego  # Decision authorization.
│   │   │   │   ├── delegation_guard.rego  # Delegation guard.
│   │   │   │   ├── deploy.rego  # Deployment policy.
│   │   │   │   ├── role_access.rego  # Role access.
│   │   │   │   ├── tenant_boundary.rego  # Tenant boundary.
│   │   │   │   └── vulnerability.rego  # Vulnerability checks.
│   │   │   ├── templates/
│   │   │   │   ├── _helpers.tpl  # Template helpers.
│   │   │   │   ├── configmap-opa-policies.yaml  # OPA policy ConfigMap.
│   │   │   │   ├── namespace.yaml  # Namespace creation.
│   │   │   │   ├── networkpolicy.yaml  # Network policies.
│   │   │   │   ├── NOTES.txt  # Post-install notes.
│   │   │   │   ├── podsecuritystandard.yaml  # Pod security standards.
│   │   │   │   ├── rbac.yaml  # RBAC roles and bindings.
│   │   │   │   ├── resourcequota.yaml  # Resource quotas.
│   │   │   │   ├── runtimeclass-confidential.yaml  # Confidential compute runtime.
│   │   │   │   └── server-policy.yaml  # Server admission policy.
│   │   │   └── tests/
│   │   │       └── test-isolation.yaml  # Isolation test manifest.
│   │   ├── keycloak/  # Keycloak identity provider chart.
│   │   │   ├── Chart.yaml  # Chart metadata.
│   │   │   ├── values.yaml  # Default values.
│   │   │   └── templates/
│   │   │       ├── namespace.yaml  # Namespace creation.
│   │   │       ├── service.yaml  # Keycloak service.
│   │   │       └── statefulset.yaml  # Keycloak StatefulSet.
│   │   └── spire/  # SPIRE identity framework chart.
│   │       ├── Chart.yaml  # Chart metadata.
│   │       ├── values.yaml  # Default values.
│   │       └── templates/
│   │           ├── agent-configmap.yaml  # Agent configuration.
│   │           ├── agent-daemonset.yaml  # Agent DaemonSet.
│   │           ├── namespace.yaml  # Namespace creation.
│   │           ├── server-configmap.yaml  # Server configuration.
│   │           ├── server-deployment.yaml  # Server Deployment.
│   │           ├── server-service.yaml  # Server Service.
│   │           └── service-accounts.yaml  # Service accounts.
│   ├── migrations/  # Database migrations.
│   │   ├── 001_tenant_columns.sql  # Add tenant columns.
│   │   ├── 002_tenant_backfill.sql  # Backfill tenant data.
│   │   ├── 003_rls_enable.sql  # Enable row-level security.
│   │   ├── 003_rls_disable_rollback.sql  # RLS rollback script.
│   │   └── 004_roles_grants.sql  # Role and grant setup.
│   ├── terraform/  # Terraform modules.
│   │   └── modules/
│   │       └── confidential_nodepool/
│   │           └── main.tf  # Confidential compute node pool.
│   └── scripts/  # Operational scripts.
│       └── install-linkerd.sh  # Linkerd service mesh installer.
├── tests/  # Test suite.
│   ├── conftest.py  # Root fixtures.
│   ├── test_arch_import_gate.py  # Import boundary enforcement.
│   ├── test_components_bridge.py  # Component bridge tests.
│   ├── test_components_discovery.py  # Component discovery tests.
│   ├── test_components_id_semver.py  # Component ID/semver tests.
│   ├── test_packs_discovery.py  # Pack discovery tests.
│   ├── test_public_api_facades.py  # Public API facade tests.
│   ├── contract/  # Contract and schema tests.
│   │   ├── conftest.py
│   │   ├── test_abi_diff_tool.py  # ABI diff tool tests.
│   │   ├── test_applicability_contract.py  # Applicability contract tests.
│   │   ├── test_citations_contract.py  # Citations contract tests.
│   │   ├── test_foundry_facade_contracts.py  # Foundry facade tests.
│   │   ├── test_foundry_input_bindings_contract.py  # Foundry input binding tests.
│   │   ├── test_gate_models.py  # Gate model tests.
│   │   ├── test_gate_protocol.py  # Gate protocol tests.
│   │   ├── test_golden_record_ids.py  # Golden record ID tests.
│   │   ├── test_ir_migrations.py  # IR migration tests.
│   │   ├── test_kernel_models.py  # Kernel model tests.
│   │   ├── test_run_experiment_slo.py  # Run experiment SLO tests.
│   │   ├── test_scientist_workflow_spec_contract.py  # Workflow spec tests.
│   │   ├── test_security_metrics_helpers.py  # Security metrics helper tests.
│   │   ├── test_slo_metrics.py  # SLO metrics tests.
│   │   ├── test_trinity_contracts.py  # Trinity contract tests.
│   │   ├── test_trinity_linker_contract.py  # Trinity linker tests.
│   │   ├── test_trinity_migration.py  # Trinity migration tests.
│   │   └── test_world_abi_contract.py  # World ABI tests.
│   ├── core/  # Core infrastructure tests.
│   │   ├── test_backend_dispatcher.py  # Backend dispatcher tests.
│   │   ├── test_cache.py  # Cache subsystem tests.
│   │   ├── test_discovery_base.py  # Discovery base tests.
│   │   ├── test_error_base.py  # Error hierarchy tests.
│   │   ├── test_hashing.py  # Hashing tests.
│   │   ├── test_llm_core.py  # LLM core client tests.
│   │   ├── test_pipeline.py  # Pipeline framework tests.
│   │   ├── test_registry_base.py  # Registry base tests.
│   │   ├── test_registry_generic.py  # Generic registry tests.
│   │   ├── test_scoring_framework.py  # Scoring framework tests.
│   │   ├── phase0/  # Phase-0 core tests.
│   │   │   ├── conftest.py
│   │   │   ├── test_artifact_export_import.py  # Artifact export/import.
│   │   │   ├── test_artifact_graph.py  # Artifact graph tracking.
│   │   │   ├── test_artifact_store.py  # CAS store tests.
│   │   │   ├── test_audit_export_verify.py  # Audit export/verify.
│   │   │   ├── test_audit_manifest_compat.py  # Audit manifest compatibility.
│   │   │   ├── test_canon_json.py  # Canonical JSON tests.
│   │   │   ├── test_cli.py  # CLI tests.
│   │   │   ├── test_cli_resume.py  # CLI resume tests.
│   │   │   ├── test_cli_signing.py  # CLI signing tests.
│   │   │   ├── test_decorators.py  # @traced decorator tests.
│   │   │   ├── test_environment_manifest.py  # Environment manifest tests.
│   │   │   ├── test_logs.py  # Log-trace correlation tests.
│   │   │   ├── test_metrics.py  # Metrics registry tests.
│   │   │   ├── test_observability.py  # Observability workflow tests.
│   │   │   ├── test_propagation.py  # Trace propagation tests.
│   │   │   ├── test_provenance_contract_shims.py  # Provenance contract shims.
│   │   │   ├── test_registry_bundle.py  # Registry bundle tests.
│   │   │   ├── test_run_context.py  # Run context tests.
│   │   │   ├── test_signing.py  # Signing tests.
│   │   │   ├── test_store_signing.py  # Store signing tests.
│   │   │   └── test_tracer.py  # Tracer singleton tests.
│   │   ├── components/  # Component system tests.
│   │   │   ├── test_connector_kind_compliance.py  # Connector kind compliance.
│   │   │   ├── test_no_legacy_entrypoint_groups.py  # Legacy entrypoint check.
│   │   │   └── test_unified_bootstrap_idempotency.py  # Bootstrap idempotency.
│   │   ├── contracts/  # Core contract tests.
│   │   │   ├── test_execution_plan_contracts.py  # Execution plan contract tests.
│   │   │   └── test_ir_ref_facades.py  # IR reference facade tests.
│   │   └── security/  # Security subsystem tests.
│   │       ├── test_access_scope.py  # Access scope tests.
│   │       ├── test_audit_chain.py  # Audit chain integrity tests.
│   │       ├── test_auth_middlewares.py  # Auth middleware tests.
│   │       ├── test_authz.py  # Authorization tests.
│   │       ├── test_cell.py  # Cell isolation tests.
│   │       ├── test_db_backend.py  # DB backend tests.
│   │       ├── test_delegation.py  # Delegation tests.
│   │       ├── test_identity.py  # Identity management tests.
│   │       ├── test_registry.py  # Security registry tests.
│   │       ├── test_rls_isolation.py  # Row-level security tests.
│   │       ├── test_router.py  # Router tests.
│   │       ├── test_router_resolve_headers.py  # Router header resolution tests.
│   │       ├── test_sbom.py  # SBOM generation tests.
│   │       ├── test_tee.py  # TEE tests.
│   │       ├── test_tee_middleware.py  # TEE middleware tests.
│   │       └── test_tenant_context.py  # Tenant context tests.
│   ├── demos/  # Demo smoke tests.
│   │   └── run_laffer_demo.py  # Laffer demo.
│   ├── fabric/  # Fabric tests.
│   │   ├── test_claims_pipeline.py  # Claims pipeline tests.
│   │   ├── test_conflict_uncertainty_adapter.py  # Conflict uncertainty adapter.
│   │   ├── test_conflicts.py  # Conflict resolution tests.
│   │   ├── test_data_catalog.py  # Data catalog tests.
│   │   ├── test_docs_pipeline.py  # Docs pipeline tests.
│   │   ├── test_legal_evaluation.py  # Legal evaluation tests.
│   │   ├── test_lex_corpus.py  # Lex corpus tests.
│   │   ├── test_normpack.py  # Normpack tests.
│   │   ├── test_provenance.py  # Provenance tests.
│   │   ├── test_quality_indicators.py  # Quality indicator tests.
│   │   ├── test_scholar_extractor_components.py  # Scholar extractor tests.
│   │   ├── test_scholar_freshness.py  # Scholar freshness tests.
│   │   ├── test_scholar_freshness_store.py  # Scholar freshness store tests.
│   │   ├── test_scholar_mvp.py  # Scholar MVP tests.
│   │   ├── test_storage_port.py  # Storage port adapter tests.
│   │   ├── test_trust.py  # Trust system tests.
│   │   ├── test_trust_adapter.py  # Trust adapter tests.
│   │   ├── test_trust_two_pass.py  # Two-pass trust tests.
│   │   ├── test_world_kuzu.py  # Kùzu world tests.
│   │   ├── test_world_materialization.py  # Materialization tests.
│   │   ├── test_world_query_column_masking.py  # Column masking tests.
│   │   ├── test_world_query_multibackend.py  # Multi-backend query tests.
│   │   ├── test_world_store.py  # World store tests.
│   │   ├── connectors/  # Connector tests.
│   │   │   ├── conftest.py
│   │   │   ├── test_cache_system.py  # Cache system tests.
│   │   │   ├── test_components_bridge.py  # Components bridge tests.
│   │   │   ├── test_contract_system.py  # Contract system tests.
│   │   │   ├── test_federation.py  # Federation tests.
│   │   │   ├── test_harness.py  # Test harness tests.
│   │   │   ├── test_ingestion_fetch_activity_contract.py  # Ingestion fetch tests.
│   │   │   ├── test_integration.py  # Integration tests.
│   │   │   ├── test_protocol_compliance.py  # Protocol compliance.
│   │   │   ├── test_quality_system.py  # Quality system tests.
│   │   │   ├── test_registry.py  # Registry tests.
│   │   │   ├── test_resilience.py  # Resilience tests.
│   │   │   ├── test_schema_aware_cache.py  # Schema-aware cache tests.
│   │   │   ├── test_schema_system.py  # Schema system tests.
│   │   │   ├── test_transform_pipeline.py  # Transform pipeline tests.
│   │   │   ├── test_type_system.py  # Type system tests.
│   │   │   ├── bindings/  # Binding profile tests.
│   │   │   │   └── test_binding_profiles.py  # Binding profile tests.
│   │   │   ├── profiles/  # Source profile tests.
│   │   │   │   └── test_source_profiles.py  # Source profile tests.
│   │   │   ├── reference/  # Reference connector tests.
│   │   │   │   ├── test_rest_json.py  # REST/JSON tests.
│   │   │   │   ├── test_sdmx.py  # SDMX tests.
│   │   │   │   └── test_static_csv.py  # Static CSV tests.
│   │   │   └── sources/  # Production source connector tests.
│   │   │       ├── test_ckan.py  # CKAN connector tests.
│   │   │       ├── test_http_connector_base.py  # HTTP base tests.
│   │   │       ├── test_http_version_policy.py  # HTTP version policy tests.
│   │   │       ├── test_no_duplicate_http_helpers.py  # No duplicate helpers.
│   │   │       ├── test_opendatasoft.py  # OpenDataSoft connector tests.
│   │   │       ├── test_production_connectors.py  # Production connector tests.
│   │   │       ├── test_sdmx_source.py  # SDMX connector tests.
│   │   │       ├── test_socrata.py  # Socrata connector tests.
│   │   │       ├── test_sparql.py  # SPARQL connector tests.
│   │   │       ├── test_wave1_integration.py  # Wave 1 connector integration tests.
│   │   │       ├── test_wave2_integration.py  # Wave 2 connector integration tests.
│   │   │       └── test_wave3_integration.py  # Wave 3 connector integration tests.
│   │   ├── data_plane/  # Fabric data plane tests.
│   │   │   ├── test_cursor_store.py  # Cursor store tests.
│   │   │   ├── test_incremental.py  # Incremental ingestion tests.
│   │   │   ├── test_orchestrator.py  # Orchestrator tests.
│   │   │   ├── test_record_replay.py  # Record/replay tests.
│   │   │   ├── test_streaming_windowed.py  # Streaming windowed tests.
│   │   │   └── test_watermark.py  # Watermark tracking tests.
│   │   └── pii/  # PII tests.
│   │       └── test_presidio_detector.py  # Presidio PII detector tests.
│   ├── foundry/  # Foundry tests.
│   │   ├── test_adaptive_agents.py  # Adaptive agent tests.
│   │   ├── test_agent_artifact.py  # Agent artifact tests.
│   │   ├── test_agent_simulation_step1.py  # Agent sim step 1.
│   │   ├── test_agent_simulation_step2.py  # Agent sim step 2.
│   │   ├── test_agent_simulation_step3.py  # Agent sim step 3.
│   │   ├── test_agent_simulation_step4.py  # Agent sim step 4.
│   │   ├── test_agent_simulation_step5.py  # Agent sim step 5.
│   │   ├── test_agent_simulation_step6.py  # Agent sim step 6.
│   │   ├── test_calibration_uncertainty_adapter.py  # Calibration uncertainty.
│   │   ├── test_calibrator_fidelity.py  # Calibrator fidelity tests.
│   │   ├── test_calibrator_mvp.py  # Calibrator MVP tests.
│   │   ├── test_catalog_snapshot.py  # Method catalog snapshot tests.
│   │   ├── test_compile_determinism.py  # Compile determinism.
│   │   ├── test_compile_facade.py  # Compile facade tests.
│   │   ├── test_conflict_detection.py  # Conflict detection tests.
│   │   ├── test_constraints_executor.py  # Constraints executor tests.
│   │   ├── test_cost_model.py  # Cost model tests.
│   │   ├── test_execute_facade_smoke.py  # Execute facade smoke.
│   │   ├── test_execute_input_bindings.py  # Execute input bindings.
│   │   ├── test_execute_requires_input_bindings_ref.py  # Input bindings ref check.
│   │   ├── test_fiscal.py  # Fiscal tests.
│   │   ├── test_global_state.py  # Global state tests.
│   │   ├── test_gradients.py  # Gradient tests.
│   │   ├── test_health.py  # Health check tests.
│   │   ├── test_jit_compilation_tracker.py  # JIT tracker tests.
│   │   ├── test_jit_stability.py  # JIT stability tests.
│   │   ├── test_merge_determinism.py  # Merge determinism tests.
│   │   ├── test_nan_guard.py  # NaN guard tests.
│   │   ├── test_no_compat_facade_imports.py  # No compat facade imports.
│   │   ├── test_no_foundry_domain_imports.py  # No foundry domain imports.
│   │   ├── test_no_io_kernel.py  # No-IO kernel purity.
│   │   ├── test_patch_executor.py  # Patch executor tests.
│   │   ├── test_program_graph_ops.py  # Program graph ops tests.
│   │   ├── test_runtime_batch.py  # Runtime batch tests.
│   │   ├── test_uncertainty_propagation.py  # Uncertainty propagation.
│   │   ├── test_unified_dag_method_nodes.py  # Unified DAG method node tests.
│   │   ├── agent_sim/  # Agent sim tests.
│   │   │   └── test_monitoring.py  # Monitoring tests.
│   │   ├── analysis/  # Analysis tests.
│   │   │   └── test_distributional.py  # Distributional analysis tests.
│   │   ├── methods/  # Method tests.
│   │   │   ├── conftest.py
│   │   │   ├── test_artifacts.py  # Method artifact tests.
│   │   │   ├── test_base.py  # Base method tests.
│   │   │   ├── test_compiler.py  # Method compiler tests.
│   │   │   ├── test_components_bootstrap_adapter.py  # Bootstrap adapter tests.
│   │   │   ├── test_composer.py  # Method composer tests.
│   │   │   ├── test_discovery.py  # Method discovery tests.
│   │   │   ├── test_linker.py  # Method linker tests.
│   │   │   ├── test_metadata_assumptions.py  # Metadata/assumptions tests.
│   │   │   ├── test_protocol.py  # Method protocol tests.
│   │   │   ├── test_registry.py  # Method registry tests.
│   │   │   ├── test_testing_infra.py  # Testing infra tests.
│   │   │   ├── test_types.py  # Method type tests.
│   │   │   ├── backends/
│   │   │   │   └── test_backends.py  # Backend tests.
│   │   │   └── catalog/
│   │   │       ├── causal/  # Causal method tests.
│   │   │       │   ├── test_did.py  # DID tests.
│   │   │       │   ├── test_hte_methods.py  # HTE method tests.
│   │   │       │   ├── test_protocols.py  # Causal protocol tests.
│   │   │       │   ├── test_rdd.py  # RDD tests.
│   │   │       │   ├── test_registration.py  # Registration tests.
│   │   │       │   ├── test_synthetic_control.py  # Synthetic Control tests.
│   │   │       │   ├── test_synthetic_control_imports.py  # Legacy/canonical import tests.
│   │   │       │   └── test_structural_time_series.py  # STS tests.
│   │   │       ├── econometrics/  # Econometric method tests.
│   │   │       │   ├── test_iv.py  # IV tests.
│   │   │       │   ├── test_panel.py  # Panel data tests.
│   │   │       │   ├── test_protocols.py  # Econometric protocol tests.
│   │   │       │   ├── test_registration.py  # Registration tests.
│   │   │       │   └── test_timeseries.py  # Time series tests.
│   │   │       └── optimization/  # Optimization method tests.
│   │   │           ├── test_methods.py  # Optimization method tests.
│   │   │           ├── test_protocols.py  # Optimization protocol tests.
│   │   │           └── test_registration.py  # Registration tests.
│   │   └── plugins/  # Plugin tests.
│   │       └── test_plugin_system.py  # Plugin system tests.
│   ├── integration/  # Cross-module integration tests.
│   │   └── test_human_gate_audit.py  # Human gate+audit integration.
│   ├── ir/  # IR tests.
│   │   ├── test_canon_hash_parity.py  # Canon hash parity tests.
│   │   ├── test_hte_backtest.py  # HTE+backtest IR tests.
│   │   ├── test_loaders.py  # Loader tests.
│   │   ├── test_no_core_imports.py  # No-core-imports boundary test.
│   │   ├── test_policy_portfolio.py  # Policy portfolio tests.
│   │   ├── test_queries_contracts.py  # Query contract tests.
│   │   ├── test_registry_fragments.py  # Registry fragment tests.
│   │   ├── test_registry_fragments_components.py  # Fragment component tests.
│   │   ├── test_trinity_loaders.py  # Trinity loader tests.
│   │   └── test_uncertainty.py  # Uncertainty IR tests.
│   ├── lex/  # Lex tests.
│   │   ├── batch/  # Lex batch pipeline tests.
│   │   │   ├── test_canonicalizers.py  # Canonicalizer tests.
│   │   │   ├── test_graph_builder_ids.py  # Graph builder ID tests.
│   │   │   ├── test_quality_report.py  # Quality report tests.
│   │   │   ├── test_sharding_config.py  # Sharding configuration tests.
│   │   │   ├── test_spo_extractor_normalization.py  # SPO extractor normalization tests.
│   │   │   └── test_structurer.py  # Structurer tests.
│   │   └── simulator/  # Lex simulator tests.
│   │       ├── test_diff.py  # Norm diff tests.
│   │       ├── test_engine.py  # Simulator engine tests.
│   │       └── test_mutator.py  # Norm mutator tests.
│   ├── lint/  # Lint rule tests.
│   │   └── test_legacy_cutover_lint.py  # Legacy cutover lint tests.
│   ├── performance/  # Performance tests.
│   │   └── test_overhead.py  # Observability overhead SLA.
│   ├── runtime/  # Runtime tests.
│   │   ├── test_replay_input_bindings_completeness.py  # Replay input bindings.
│   │   ├── test_replay_runtime.py  # Replay runtime tests.
│   │   ├── test_runtime_manifest_paths.py  # Manifest path tests.
│   │   └── http/  # HTTP API tests.
│   │       ├── conftest.py
│   │       ├── test_artifact_inspector_api.py  # Artifact inspector API tests.
│   │       ├── test_control_api.py  # Control Plane API tests.
│   │       ├── test_core_only_runs_api.py  # Core-only runs API tests.
│   │       ├── test_debug_api.py  # Debug API tests.
│   │       ├── test_e2e_ingestion.py  # End-to-end data ingestion tests.
│   │       ├── test_insights_api.py  # Insights API tests.
│   │       ├── test_nl_pipeline_materialization.py  # NL pipeline materialization tests.
│   │       ├── test_runs_api.py  # Runs API tests.
│   │       ├── test_runtime_api_authz.py  # Runtime API authorization tests.
│   │       ├── test_runtime_api_contract_hardening.py  # API contract hardening tests.
│   │       ├── test_runtime_api_no_legacy_sources.py  # No legacy sources check.
│   │       └── test_timeline_api.py  # Timeline API tests.
│   └── scientist/  # Scientist tests.
│       ├── conftest.py
│       ├── test_agent_protocols.py  # Agent protocol tests.
│       ├── test_backtesting.py  # Backtesting tests.
│       ├── test_bind_foundry_inputs_node.py  # Foundry input binding node tests.
│       ├── test_causal_evaluation_node.py  # Causal evaluation node.
│       ├── test_checkpoint.py  # Checkpoint tests.
│       ├── test_code_verifier.py  # Code verifier tests.
│       ├── test_code_verifier_security.py  # Code verifier security tests.
│       ├── test_compiler.py  # Compiler tests.
│       ├── test_constitution.py  # Constitution constraint tests.
│       ├── test_critic_factory.py  # Critic factory tests.
│       ├── test_data_plane_gate_node.py  # Data plane gate node tests.
│       ├── test_decision_card.py  # Decision card tests.
│       ├── test_decision_card_uncertainty_render.py  # Uncertainty rendering.
│       ├── test_decision_packet_distributional_econometrics.py  # Distributional+econometrics.
│       ├── test_decision_packet_node_v3.py  # Decision packet v3.
│       ├── test_distributional_analysis_node.py  # Distributional analysis.
│       ├── test_drafter_constitution.py  # Drafter constitution tests.
│       ├── test_engine_default_workflow_e1_7.py  # Default workflow tests.
│       ├── test_engine_default_workflow_p8.py  # Default workflow P8 tests.
│       ├── test_engine_executor_idempotency.py  # Idempotency tests.
│       ├── test_engine_executor_v0.py  # Executor v0 tests.
│       ├── test_engine_registry_v0.py  # Registry v0 tests.
│       ├── test_enrich_knowledge_cache_policy.py  # Knowledge cache policy tests.
│       ├── test_enrich_knowledge_node_freshness.py  # Knowledge freshness tests.
│       ├── test_failure_index.py  # Failure index tests.
│       ├── test_feasibility_probe.py  # Feasibility probe tests.
│       ├── test_idempotency.py  # Idempotency tests.
│       ├── test_informed_critic.py  # Informed critic tests.
│       ├── test_iteration_state_machine.py  # Iteration state machine tests.
│       ├── test_knowledge_base.py  # Knowledge base tests.
│       ├── test_llm_cycle_preflight.py  # LLM cycle preflight tests.
│       ├── test_multipass_drafter.py  # Multi-pass drafter tests.
│       ├── test_node_registry_components_bootstrap.py  # Node registry bootstrap tests.
│       ├── test_norm_loader.py  # Norm loader tests.
│       ├── test_propagate_uncertainty_node.py  # Uncertainty propagation node.
│       ├── test_rag_index.py  # RAG index tests.
│       ├── test_replay_backend.py  # Replay backend tests.
│       ├── compute/
│       │   └── test_runner_polyglot.py  # Polyglot runner tests.
│       ├── doe/
│       │   ├── test_sampling.py  # DOE sampling tests.
│       │   └── test_sensitivity_plan.py  # Sensitivity plan tests.
│       ├── governance/  # Governance tests.
│       │   ├── test_confidence_pass.py  # Confidence pass tests.
│       │   ├── test_equity_pass.py  # Equity pass tests.
│       │   ├── test_legal_pass.py  # Legal pass tests.
│       │   ├── test_norm_execution.py  # Norm execution tests.
│       │   ├── test_pii_check_pass.py  # PII check pass tests.
│       │   ├── test_shared_shims.py  # Shared governance shims tests.
│       │   └── test_validation_pipeline.py  # Validation pipeline tests.
│       ├── integration/  # Scientist integration tests.
│       │   ├── test_checkpoint_resume.py  # Checkpoint+resume tests.
│       │   └── test_workflow_tracing.py  # Workflow tracing tests.
│       └── search/  # Search tests.
│           ├── conftest.py
│           ├── test_adversarial.py  # Adversarial search tests.
│           ├── test_diversity.py  # Diversity selection tests.
│           ├── test_portfolio_search.py  # Portfolio search tests.
│           ├── test_search_loop.py  # Search loop tests.
│           └── strategies/  # Strategy tests.
│               ├── conftest.py
│               ├── test_adapter.py  # Adapter tests.
│               ├── test_bayesian.py  # Bayesian tests.
│               ├── test_controller_batch.py  # Controller batch tests.
│               ├── test_multi_objective.py  # Multi-objective tests.
│               ├── test_random_grid.py  # Random/grid tests.
│               ├── test_resource_arbiter.py  # Resource arbiter tests.
│               └── test_space_codec.py  # Space codec tests.
├── tools/  # Developer tooling.
│   ├── lint/  # Architecture and import linters.
│   │   ├── check_scholar_imports.py  # Scholar import boundary checker.
│   │   ├── collect_arch_metrics.py  # Architecture metrics collector.
│   │   ├── compare_baseline.py  # Baseline metric comparison.
│   │   ├── lint_connector_hardening.py  # Connector hardening linter.
│   │   ├── lint_connectors.py  # Connector Law A/B linter.
│   │   ├── lint_foundry.py  # Foundry purity linter (Law B).
│   │   ├── lint_foundry_data_plane.py  # Foundry data plane linter.
│   │   ├── lint_imports.py  # Architecture import-boundary linter (Law A).
│   │   └── lint_legacy_cutover.py  # Legacy cutover progress linter.
│   ├── diagnostics/  # Diagnostic and schema tools.
│   │   ├── abi_diff.py  # ABI schema diff tool.
│   │   ├── capture_env.py  # Environment reproducibility manifest.
│   │   ├── check_perf_regression.py  # Performance regression checker.
│   │   ├── check_scientist_node_version_bump.py  # Node version bump check.
│   │   ├── check_setup.py  # Setup diagnostics.
│   │   ├── check_state_reads.py  # State read pattern checker.
│   │   ├── check_udf_perf.py  # UDF perf diagnostics.
│   │   ├── gen_schema.py  # JSON Schema snapshot generator.
│   │   ├── generate_ir_schema.py  # IR schema generator.
│   │   ├── scan_fabric.py  # Fabric data contract scanner.
│   │   ├── verify_scm_v3.py  # SCM v3 structural verification.
│   │   ├── verify_scm_v3_fullspec.py  # SCM v3 full-spec verification.
│   │   └── visualize_provenance.py  # Provenance graph visualizer.
│   ├── demos/  # Demo scripts.
│   │   ├── run_export_demo.py  # Export demo.
│   │   ├── run_laffer_demo.py  # Laffer curve demo.
│   │   ├── run_mechanism_design.py  # Differentiable mechanism design demo.
│   │   ├── run_udf_hybrid_demo.py  # UDF hybrid demo.
│   │   └── run_udf_query_demo.py  # UDF query demo.
│   ├── benchmarks/  # Performance benchmarks.
│   │   ├── bench_domain.py  # Domain benchmark.
│   │   └── bench_simulation.py  # Simulation benchmark.
│   ├── connectors/  # Connector tools.
│   │   ├── check_contracts.py  # Connector contract validation.
│   │   └── scaffold.py  # Connector scaffold generator.
│   ├── migrations/  # Migration tools.
│   │   ├── migrate.py  # Migration runner.
│   │   └── migrate_duckdb_to_pg.py  # DuckDB→PostgreSQL migration.
│   └── runtime/  # Runtime tools.
│       ├── archive_legacy_runs.py  # Legacy run archival.
│       ├── check_runtime_api_contract.py  # Runtime API contract validation script.
│       ├── export_runtime_openapi.py  # OpenAPI spec export.
│       ├── generate_runtime_client.py  # TypeScript client generation.
│       └── inventory_legacy_runs.py  # Legacy run inventory.
├── data/  # Data workspace and reference datasets.
│   ├── norms/  # Norm packs (YAML).
│   │   └── sample_norms.yaml  # Sample norm pack.
│   ├── raw/  # Raw input datasets.
│   │   ├── agents.csv  # Agent data.
│   │   ├── interactions.csv  # Interaction data.
│   │   └── macro.csv  # Macroeconomic data.
│   ├── staging/  # ETL intermediate outputs.
│   │   ├── agents.parquet  # Staged agent data.
│   │   ├── interactions.parquet  # Staged interactions.
│   │   └── macro.parquet  # Staged macro data.
│   ├── curated/  # Curated datasets with manifests.
│   │   ├── agents.parquet  # Curated agent data.
│   │   ├── agents_manifest.json  # Agent data manifest.
│   │   ├── data_contracts.json  # Data contract definitions.
│   │   ├── entity_resolution_manifest.json  # Entity resolution manifest.
│   │   ├── interactions.parquet  # Curated interactions.
│   │   ├── interactions_manifest.json  # Interactions manifest.
│   │   ├── macro.parquet  # Curated macro data.
│   │   ├── macro_manifest.json  # Macro data manifest.
│   │   ├── source_bindings.json  # Source binding definitions.
│   │   └── udf_schema.json  # UDF schema definitions.
│   ├── dataset_catalog/  # Dataset catalog reference files.
│   │   ├── metrics_map.yaml  # Metrics → dataset indicator mapping.
│   │   └── seed_variable_alignments.yaml  # Seed variable alignment definitions.
│   ├── phase12_survey.json  # Phase 1–2 survey data.
│   └── databases/  # Embedded databases.
│       ├── demo_udf.duckdb  # Demo UDF DuckDB.
│       ├── demo_udf.kuzu  # Demo UDF Kùzu.
│       ├── integration.duckdb  # Integration test DuckDB.
│       ├── simulation.duckdb  # Simulation DuckDB.
│       ├── simulation.kuzu  # Simulation Kùzu.
│       ├── test_macro.duckdb  # Test macro DuckDB.
│       ├── test_udf.duckdb  # Test UDF DuckDB.
│       └── test_udf.kuzu  # Test UDF Kùzu.
├── frontend/  # Frontend applications.
│   ├── runtime-api-client/  # TypeScript API client.
│   │   ├── runtimeApiClient.ts  # TypeScript API client source.
│   │   └── runtimeApiClient.js  # Compiled JavaScript client.
│   ├── runtime-dashboard/  # React 18 + Vite + TailwindCSS monitoring dashboard.
│   │   ├── vite.config.ts  # Vite build configuration.
│   │   ├── tailwind.config.ts  # Tailwind CSS configuration.
│   │   └── src/
│   │       ├── main.tsx  # Application entry point.
│   │       ├── App.tsx  # Root component with routing.
│   │       ├── api/  # API layer.
│   │       │   ├── client.ts  # API client configuration.
│   │       │   ├── http.ts  # HTTP utilities.
│   │       │   ├── queryClient.ts  # React Query client configuration.
│   │       │   ├── queryKeys.ts  # Query key constants.
│   │       │   ├── types.ts  # Generated TypeScript types from OpenAPI.
│   │       │   ├── validators.ts  # Zod validators for API responses.
│   │       │   └── hooks/  # React Query hooks.
│   │       │       ├── useArtifactContent.ts  # Artifact content fetching.
│   │       │       ├── useArtifactLineage.ts  # Artifact lineage graph.
│   │       │       ├── useArtifactManifest.ts  # Artifact manifest fetching.
│   │       │       ├── useArtifactSchema.ts  # Artifact schema fetching.
│   │       │       ├── useCacheStatus.ts  # Cache status query.
│   │       │       ├── useConnectors.ts  # Connector listing.
│   │       │       ├── useDataCatalogSearch.ts  # Data catalog search.
│   │       │       ├── useDataIndexStats.ts  # Data index statistics.
│   │       │       ├── useDataPromotionCandidates.ts  # Data promotion candidates.
│   │       │       ├── useDiscoverDataSources.ts  # Data source discovery.
│   │       │       ├── useGovernanceDebug.ts  # Governance debug info.
│   │       │       ├── useHealth.ts  # Health check query.
│   │       │       ├── useIngestData.ts  # Data ingestion mutation.
│   │       │       ├── useLaunchNlRun.ts  # Natural language run launch.
│   │       │       ├── useLaunchRun.ts  # Policy run launch mutation.
│   │       │       ├── useLexGraphStats.ts  # Lex knowledge graph statistics.
│   │       │       ├── useLexPipelineStatus.ts  # Lex pipeline status query.
│   │       │       ├── useLexSearch.ts  # Lex knowledge graph search.
│   │       │       ├── useLexTrigger.ts  # Lex pipeline trigger mutation.
│   │       │       ├── useLlmProfiles.ts  # LLM profile listing.
│   │       │       ├── useNodeDebug.ts  # Node debug info.
│   │       │       ├── usePreviewFetchPlan.ts  # Fetch plan preview.
│   │       │       ├── usePromotionDecision.ts  # Promotion decision mutation.
│   │       │       ├── useResolveDataNeeds.ts  # Data needs resolution.
│   │       │       ├── useRunAgents.ts  # Run agent details.
│   │       │       ├── useRunDetails.ts  # Run detail fetching.
│   │       │       ├── useRunErrors.ts  # Run error fetching.
│   │       │       ├── useRunLineage.ts  # Run lineage graph.
│   │       │       ├── useRunNodes.ts  # Run node listing.
│   │       │       ├── useRunTimeline.ts  # Run timeline events.
│   │       │       ├── useRunWorkflow.ts  # Run workflow state.
│   │       │       ├── useRuns.ts  # Run listing query.
│   │       │       └── useSourceProfiles.ts  # Source profile listing.
│   │       ├── components/  # UI components.
│   │       │   ├── agents/
│   │       │   │   └── AgentPipelinePanel.tsx  # Agent pipeline visualization.
│   │       │   ├── data/
│   │       │   │   └── DataIntelligencePanel.tsx  # Data analysis and recommendations.
│   │       │   ├── debug/
│   │       │   │   ├── ErrorsPanel.tsx  # Error display panel.
│   │       │   │   └── NodeDebugPanel.tsx  # Node debug inspection.
│   │       │   ├── decision/
│   │       │   │   └── DecisionCardView.tsx  # Decision card display.
│   │       │   ├── governance/
│   │       │   │   └── GovernanceReport.tsx  # Governance report view.
│   │       │   ├── layout/
│   │       │   │   ├── Header.tsx  # Application header.
│   │       │   │   ├── Shell.tsx  # Application shell layout.
│   │       │   │   └── Sidebar.tsx  # Navigation sidebar.
│   │       │   ├── shared/
│   │       │   │   ├── ApiErrorAlert.tsx  # API error display.
│   │       │   │   ├── EmptyState.tsx  # Empty state placeholder.
│   │       │   │   ├── JsonPreview.tsx  # JSON data preview.
│   │       │   │   ├── LineageGraph.tsx  # Lineage graph visualization.
│   │       │   │   └── StatusBadge.tsx  # Status indicator badge.
│   │       │   ├── simulation/
│   │       │   │   ├── CalibrationReport.tsx  # Calibration report view.
│   │       │   │   ├── DistributionalPanel.tsx  # Distributional analysis panel.
│   │       │   │   ├── MetricsPanel.tsx  # Simulation metrics display.
│   │       │   │   ├── SimulationResultsViewer.tsx  # Simulation results.
│   │       │   │   └── UncertaintyOverlay.tsx  # Uncertainty visualization overlay.
│   │       │   ├── trinity/
│   │       │   │   ├── InterventionDetail.tsx  # Intervention detail view.
│   │       │   │   ├── TrinityCard.tsx  # Trinity artifact card.
│   │       │   │   └── TrinityDiff.tsx  # Trinity diff visualization.
│   │       │   ├── ui/
│   │       │   │   └── card.tsx  # Reusable card component.
│   │       │   └── workflow/
│   │       │       └── WorkflowDagPanel.tsx  # Workflow DAG visualization.
│   │       ├── lib/  # Shared utilities.
│   │       │   ├── constants.ts  # Application constants.
│   │       │   ├── parsing.ts  # Data parsing utilities.
│   │       │   ├── utils.ts  # General utility functions.
│   │       │   └── domain/  # Domain logic.
│   │       │       ├── agents.ts  # Agent-related utilities.
│   │       │       ├── decision.ts  # Decision domain logic.
│   │       │       ├── governance.ts  # Governance domain logic.
│   │       │       ├── simulation.ts  # Simulation domain logic.
│   │       │       ├── trinity.ts  # Trinity domain logic.
│   │       │       └── workflow.ts  # Workflow domain logic.
│   │       └── pages/  # Route pages.
│   │           ├── ArtifactInspector.tsx  # Artifact inspection page.
│   │           ├── Dashboard.tsx  # Main dashboard page.
│   │           ├── DataManagement.tsx  # Data management page.
│   │           ├── LaunchRun.tsx  # Run launch page.
│   │           ├── LexKnowledgeGraph.tsx  # Knowledge graph visualization page.
│   │           ├── RunDetail.tsx  # Run detail page.
│   │           ├── RunsList.tsx  # Runs list page.
│   │           ├── SourcesManagement.tsx  # Source profile management page.
│   │           └── SystemHealth.tsx  # System health page.
│   └── runtime-reference-shell/  # Reference UI shell.
│       ├── index.html  # Shell HTML entry point.
│       ├── app.js  # Shell application logic.
│       └── styles.css  # Shell styles.
├── pyproject.toml  # Project metadata, deps, tool config.
├── import_policy.toml  # Architecture import-boundary rules (Law A).
├── import_exceptions.toml  # Temporary import gate exceptions.
└── (root files)
    ├── architecture.md  # This document.
    ├── arch_cycles_register.csv  # Architecture cycle tracking register.
    ├── import_debt_register.csv  # Import debt tracking register.
    ├── import_exceptions_registry.md  # Import exceptions documentation.
    ├── freeze_policy.md  # API freeze policy documentation.
    ├── jax_bootstrap.py  # JAX environment defaults.
    ├── migrate.py  # Schema migration CLI.
    ├── install.sh  # Bootstrap installer.
    ├── env_example.txt  # Environment variables template.
    ├── uv.lock  # Locked dependency graph.
    ├── Dockerfile.reproducible  # Reproducible container build.
    ├── .pre-commit-config.yaml  # Pre-commit hooks.
    └── .gitignore  # Git ignore rules.
```
