# PolisyOS — AI-Driven Policy Operating System

**PolisyOS** (Policy Engine) — операционная система для проектирования, валидации, калибровки и исполнения публично-политических интервенций как воспроизводимых вычислительных экспериментов. Система принимает запрос на естественном языке, формулирует политику через иерархию AI-агентов, компилирует её в дифференцируемую JAX-симуляцию, проводит governance-проверки и выдаёт пакет решений с полным provenance-следом.

**Architecture:** v2.6.0 · **Python:** >=3.11 · **License:** proprietary · **Актуально:** 3 марта 2026

Transport / causal note:
- serious external-evidence runs теперь auto-escalate в first-class causal/transport path;
- runtime capability posture для `y0` / `r_causaleffect` / bounds фиксируется отдельным contract-артефактом и попадает в control-plane capability manifest.

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
    → batch: topic_select → harvest → parse → article_extract|extract_llm → merge_dedup
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
| **[batch/](policy-engine/src/polisyos/academic/batch/README.md)** | Стадийный pipeline: 11 стадий от topic selection до publish. Extraction modes: `deterministic` → `llm_enriched` → `article_extract` (приоритет при merge). LLM gate с budget control, audit и circuit breaker. OpenAI Batch API для embeddings |
| **[knowledge/](policy-engine/src/polisyos/academic/knowledge/README.md)** | Read-only API: `ScholarKnowledgeGraph` (hybrid text+vector search), `SKGQuery` (edge priors, parameter candidates), `ParameterSelector` (transportability scoring через `ContextProfile`), `VariableCanonizer` (deterministic canonical namespace + cache в DuckDB). SKG versioning и retraction handling |
| **[openalex/](policy-engine/src/polisyos/academic/openalex/README.md)** | Интеграция с OpenAlex API: topic catalog из CSV, async HTTP client с rate limiting и retry, selection algorithm с diversity policy (max 5 per journal, max 2 per first author), TIER1/TIER2 priority filter |
| **trust.py** | Нормализация trust-score по дизайну исследования, цитируемости, свежести и sample size |

#### Ключевые API Academic

- `ScholarKnowledgeGraph.find_relevant_works(...)` — fusion text + vector search
- `ScholarKnowledgeGraph.get_parameter_prior(variable, domain, country)` — trust-weighted mean/std
- `ParameterSelector.select_for_context(...)` — transportability-aware выбор параметра
- `SKGQuery.query_edge_priors(...)` / `query_parameters(...)` — SKG graph API

#### DuckDB слой

Runtime tables: `ac_works`, `ac_parameter_estimates`, `ac_causal_claims`, `ac_boundary_conditions`, `ac_topics`, `ac_topic_selections`, `ac_article_extractions`.
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
uv sync --frozen --extra dev --extra test --extra runtime-http

# Проверка установки
PYTHONPATH=src uv run python tools/diagnostics/check_setup.py

# Запуск тестов
uv run pytest

# Быстрый цикл без integration
uv run pytest -m "not integration"

# Отдельно HTTP/runtime-контур без skip по optional deps
uv run pytest tests/runtime/http

# Observability стек
cd ops && docker compose -f docker-compose.observability.yml up -d
# Prometheus: http://localhost:9090  |  Grafana: http://localhost:3000 (admin/admin)

# Runtime API v1 + Control Plane
PYTHONPATH=src uv run python -c "
from polisyos.runtime.http.app import create_runtime_api_app
import uvicorn
uvicorn.run(create_runtime_api_app(), host='127.0.0.1', port=8000)
"

# Runtime Dashboard (React)
cd frontend/runtime-dashboard
npm ci
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
