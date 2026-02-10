# PolisyOS — AI-Driven Policy Operating System

**PolisyOS** (Policy Engine) — операционная система для проектирования, валидации, калибровки и исполнения публично-политических интервенций как воспроизводимых вычислительных экспериментов. Система принимает запрос на естественном языке, формулирует политику через иерархию AI-агентов, компилирует её в дифференцируемую JAX-симуляцию, проводит governance-проверки и выдаёт пакет решений с полным provenance-следом.

**Architecture:** v2.5.0 · **Python:** >=3.11 · **License:** proprietary · **Актуально:** 10 февраля 2026

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
  - [Runtime — Runtime API и жизненный цикл](#runtime--runtime-api-и-жизненный-цикл)
  - [Lex — юридический анализ](#lex--юридический-анализ)
  - [Scholar — обогащение знаний](#scholar--обогащение-знаний)
  - [Scientist — AI-оркестрация](#scientist--ai-оркестрация)
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
      → Fabric (connectors, docs, claims, world model, evidence, provenance, quality, trust)
        → Foundry (compile → calibrate → simulate; чистый JAX, patch-based)
          → Runtime (HTTP API v1, replay, audit trail, artifact refs)
            → Decision Artifacts (DecisionPacket / DecisionCard / GovernanceReport)
```

Сквозные подсистемы:
- **Lex**: юридические документы → corpus → NormPack → legality evaluation → what-if simulator
- **Scholar**: внешние источники → docs → claims → trust → KnowledgeBundle (обогащение Fabric/IR)
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
                          ┌──────────┴──────────┐
                          │                     │
                     ┌────▼────┐          ┌─────▼────┐
                     │  core   │          │    ir    │  (чистые контракты)
                     └────┬────┘          └─────┬────┘
                          │                     │
               ┌──────────┼─────────────────────┤
               │          │                     │
          ┌────▼────┐ ┌───▼─────┐         ┌────▼────┐
          │ fabric  │ │ foundry │         │ runtime │
          └────┬────┘ └───┬─────┘         └────┬────┘
               │          │                    │
          ┌────▼────┐ ┌───▼─────┐              │
          │   lex   │ │ scholar │              │
          └────┬────┘ └───┬─────┘              │
               │          │                    │
               └──────────┼────────────────────┘
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
| `polisyos.core` | common | [README](policy-engine/src/polisyos/core/README.md) |
| `polisyos.ir` | — (core только TYPE_CHECKING) | [README](policy-engine/src/polisyos/ir/README.md) |
| `polisyos.fabric` | ir, core, common | [README](policy-engine/src/polisyos/fabric/README.md) |
| `polisyos.foundry` | ir, core, common | [README](policy-engine/src/polisyos/foundry/README.md) |
| `polisyos.runtime` | core, common | [README](policy-engine/src/polisyos/runtime/README.md) |
| `polisyos.lex` | fabric, ir, core, common | [README](policy-engine/src/polisyos/lex/README.md) |
| `polisyos.scholar` | fabric, ir, core, common | [README](policy-engine/src/polisyos/scholar/README.md) |
| `polisyos.scientist` | ir, fabric, foundry, runtime, lex, core, common | [README](policy-engine/src/polisyos/scientist/README.md) |
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
| **migrations/** | Детерминированная система миграций артефактов с обнаружением циклов. Текущая миграция: `dataset_manifest` 0.9→1.0 |

---

### Core — фундаментальная инфраструктура

> `src/polisyos/core/` · [README](policy-engine/src/polisyos/core/README.md) · Зависимости: common

Общий инфраструктурный слой для всех подсистем: CAS-хранилище, типизированные контракты, компонентная модель, observability, security, аудит.

```
core/
├── artifacts/      # CAS + манифесты + подписи + environment fingerprint + dependency graph
├── audit/          # Портативные аудит-пакеты и офлайн-верификация (PROV + SLSA)
├── backends/       # Унифицированный dispatcher backend-реализаций
├── cache/          # Потокобезопасные LRU/TTL кэши
├── canon/          # Канонический JSON + хеширование (float→Decimal, sorted keys)
├── compiler/       # Отчеты компиляции/линковки в CAS
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
| **[contracts/](policy-engine/src/polisyos/core/contracts/README.md)** | 14 доменов typed ABI: Fabric, Foundry, Trinity, Lex, Scientist, Scholar, Runtime, Provenance, Causal, HTE, Backtest, Uncertainty, Distributional, Compiler |
| **[observability/](policy-engine/src/polisyos/core/observability/README.md)** | OTel tracing (`@traced`), Prometheus MetricsRegistry, DeterminismTier (5 уровней), LLM cost estimation, graceful degradation |
| **[security/](policy-engine/src/polisyos/core/security/README.md)** | Zero Trust: tenant routing, DB isolation (PostgreSQL RLS / DuckDB), SPIFFE identity, OPA authz, delegation tokens, audit chain, TEE attestation, SBOM (CycloneDX), SLSA |

---

### IR — промежуточное представление

> `src/polisyos/ir/` · [README](policy-engine/src/polisyos/ir/README.md) · Независимый контрактный слой

Каноническое декларативное представление политик. IR определяет **только модели и валидацию** (Pydantic, `frozen=True`, `extra="forbid"`) — без логики исполнения. IR не зависит от `polisyos.core`.

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

`TrinityBundle` объединяет все три в единый артефакт с `schema_version`.

#### Подсистемы IR

| Подсистема | Назначение |
|------------|-----------|
| **[kernel/](policy-engine/src/polisyos/ir/kernel/README.md)** (13 файлов) | Фундаментальные реестры: mechanisms, slots, units, constraints, metrics, merge rules, trust, selector fields. Типы: `KernelModel`, `DecimalValue`, `MoneyValue`, `RateValue`. Запрет float через `reject_float()` |
| **[world/](policy-engine/src/polisyos/ir/world/README.md)** (10 файлов) | Семантическая модель: Claim, WorldEvent (W3C PROV), ConflictSet, DocFragment, QualityReport, TrustAssessment. Deterministic content-addressed IDs (`<prefix>.sha256_<hex64>`) |
| **linker/** (3 файла) | Валидация TrinityBundle vs kernel-реестров → `LinkedTrinityBundle` + `LinkReport` с типизированными `LinkIssueCode` |
| **migrations/** (4 файла) | Миграция артефактов между версиями IR-схем. Канонический формат — Trinity `schema_version` семейства `1.x` |
| **analytics/** | Контракты отчётов: `UncertaintyEnvelope`, `CausalEffectReport`, `HTEResult`, `DistributionalReport`, `BacktestReport`, `CalibrationConfig` + CAS I/O (`persist_*`/`load_*`) |
| **registry_fragments.py** | Композиция `RegistryBundle` из фрагментов с политиками: `error_on_conflict` / `prefer_higher_priority` |

---

### Fabric — Unified Data Fabric

> `src/polisyos/fabric/` · [README](policy-engine/src/polisyos/fabric/README.md) · Зависимости: ir, core, common

Полный жизненный цикл данных: от внешних источников через ingestion и обработку до queryable World Model.

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
| **[connectors/](policy-engine/src/polisyos/fabric/connectors/README.md)** | Protocol-based коннекторы (`SourceConnector`). CAS-кэш, resilience (circuit breaker, retry, rate limiter, fallback), federation (cross-source query), quality validation, DAG transform pipeline. Reference implementations: REST JSON, SDMX, CSV. Production: WorldBank, Eurostat, UKONS |
| **[docs/](policy-engine/src/polisyos/fabric/docs/README.md)** | Pipeline обработки документов: `ingest → normalize → structure → chunk`. Поддержка `text/plain`, `text/html`; PDF backend опционален |
| **[claims/](policy-engine/src/polisyos/fabric/claims/README.md)** | Extraction (pluggable backends) → Normalization → Conflict Detection → Resolution → Fact Log. Trust/quality scoring для claims и документов |
| **[world/](policy-engine/src/polisyos/fabric/world/README.md)** | Store: emit/validate/persist фактов в CAS. Materialize: инкрементальная загрузка в DuckDB (13+ таблиц), проекции, optional Kuzu граф. Merge-стратегии: `ERROR_ON_CONFLICT`/`PREFER_NON_NULL_LAST_TX`/`LAST_TX`/`FIRST_TX` |
| **[catalog/](policy-engine/src/polisyos/fabric/catalog/README.md)** | Metric-level контракты с hash-locked bindings, fuzzy/exact search, disambiguation, PII-классификация. Предотвращает hallucination метрик |
| **provenance/** | W3C PROV-O lineage: ProvenanceCoreGraph с BFS-поиском предков, экспорт в JSON-LD |
| **pii/** | PII-сканирование (Presidio + regex fallback) для ingestion pipeline |

#### Ключевые API Fabric

- `run_connectors_ingestion(...)` — полный цикл: fetch → transform → cache → CAS → provenance → evidence
- `execute_world_query(...)` / `query_world_table(...)` — типобезопасные SQL-запросы к materialized World Model
- `fabric_get_data(...)` — синхронный мост (`_connector_bridge.py`) для верхних слоёв

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
| **[methods/](policy-engine/src/polisyos/foundry/methods/README.md)** | Декларативный фреймворк методов: protocol, registry, DAG-composition, JAX/NumPy/Solver backends. Каталог: каузальный inference (SCM, DiD, RDD, CATE, DML, Meta-Learners, PolicyTree, Structural Time Series), эконометрика (Panel FE/RE, IV, ARIMA/VAR), оптимизация (OR-Tools/PuLP). Golden-record regression testing |
| **[agent_sim/](policy-engine/src/polisyos/foundry/agent_sim/README.md)** | Гетерогенная агентная симуляция: RL (PPO/CMA-ES/VFI/MPC), actor-critic (Equinox), графовые механизмы (social influence, diffusion, lending), демография (рождение/смерть/миграция/наследство), temporal dynamics, distribution-aware rewards. `PureExecutor → DistributionAwareExecutor → GraphAwareExecutor → PopulationAwareExecutor` |
| **[calibration/](policy-engine/src/polisyos/foundry/calibration/README.md)** | Градиентная калибровка на реальных данных: Adam/optax, bijector constraints, multi-target GradNorm, early stopping, Laplace-approximation uncertainty (Hessian) → `CalibrationReport` + `UncertaintyEnvelopes` |
| **[plugins/](policy-engine/src/polisyos/foundry/plugins/README.md)** | Plugin-архитектура для доменных симуляций. `PolisySimulator` high-level API, composite multi-domain execution. Reference: EconomicsPlugin |
| **uncertainty/** | Propagation неопределённости: Delta Method (Jacobian), Monte Carlo, Analytical. Автовыбор метода |
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

### Runtime — Runtime API и жизненный цикл

> `src/polisyos/runtime/` · [README](policy-engine/src/polisyos/runtime/README.md) · Зависимости: core, common

Runtime HTTP API v1 для read-only интроспекции прогонов и артефактов + replay-инфраструктура.

#### Runtime HTTP API v1 (FastAPI)

```
HTTP request → app.py (FastAPI) → telemetry middleware → [security chain] → routes → services → CAS + runs dir
```

| Группа | Endpoints |
|--------|-----------|
| **Health** | `GET /health`, `GET /ready`, `GET /api/v1/health` |
| **Runs** | `GET /api/v1/runs`, `/runs/{id}`, `/runs/{id}/timeline`, `/runs/{id}/nodes`, `/runs/{id}/lineage` |
| **Debug** | `GET /api/v1/debug/runs/{id}/nodes/{alias}`, `/debug/runs/{id}/governance`, `/debug/runs/{id}/errors` |
| **Artifacts** | `GET /api/v1/artifacts/{id}`, `/artifacts/{id}/content`, `/artifacts/{id}/lineage`, `/artifacts/{id}/schema` |

Все endpoints — read-only (`GET`). OpenAPI-спецификация: `schemas/runtime_api_v1.openapi.json` (15 endpoints).

#### Security chain (optional)

При включении: JWT authentication → Cell router (tenant→cell routing) → OPA authorization (enforce / shadow mode) → per-route resource context + tenant checks.

#### Replay API

- `build_replay_plan()` — обнаружение стратегии (`foundry`/`scientist`/`none`)
- `completeness_check()` — классификация: `complete`/`recoverable`/`incomplete`
- `verify_replay()` — режимы: `bit_exact` (artifact ID equality), `ci_bounded` (metric drift tolerance), `skip`

---

### Lex — юридический анализ

> `src/polisyos/lex/` · [README](policy-engine/src/polisyos/lex/README.md) · Зависимости: fabric, ir, core, common

Полный цикл работы с нормативными документами:

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

| Подсистема | Назначение |
|------------|-----------|
| **[corpus/](policy-engine/src/polisyos/lex/corpus/README.md)** | Загрузка документов через `fabric.docs`, парсинг юридической структуры (UA/RU/EN юрисдикции: статьи → части → пункты → подпункты), `ProvisionIndex`, `VersionIndex`. Поддержка merge-политик обновления метаданных |
| **[normpack/](policy-engine/src/polisyos/lex/normpack/README.md)** | Сборка NormPack: select sources → select provisions → extract claims → resolve conflicts → claims_to_norm_rules. Два пути: Provider (статический NormPack) или Pipeline (полная сборка). Pluggable providers через entry points `polisyos.norm_pack_providers` |
| **[legal_evaluation/](policy-engine/src/polisyos/lex/legal_evaluation/README.md)** | Rule-by-rule проверка `PolicySpec + SimulationResult` против `NormPack`. Pluggable evaluator backends, unit conversion (`percent↔ratio`, `km↔m`), авто-генерация `ChangeProposal` (JSON Patch) для FAIL findings |
| **[simulator/](policy-engine/src/polisyos/lex/simulator/README.md)** | What-if анализ: `NormPackMutator` (fluent API: add/remove/replace/modify norms), `diff_norm_packs()` (field-level deltas), `NormImpactAnalyzer` (governance passes на обоих пакетах → compliance deltas, affected KPIs) |

Точки расширения: entry points `polisyos.norm_pack_providers`, `polisyos.lex_evaluators`.

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

#### Freshness подсистема

- `FreshnessPolicy.check()` — `fresh`/`stale`/`expired` с cooldown и `needs_refresh`
- Sidecar state (`freshness_state`) с file-lock для анти-штормовой защиты при конкурентном refresh
- Domain defaults: `fiscal`, `labor`, `health`, `infrastructure`, `education` + fallback

---

### Scientist — AI-оркестрация

> `src/polisyos/scientist/` · [README](policy-engine/src/polisyos/scientist/README.md) · Зависимости: ir, fabric, foundry, runtime, lex, core, common

Оркестрационный «мозг» системы. Координирует полный цикл эксперимента через DAG workflow.

#### Default Workflow DAG

```
start (noop)
├─ build_data_snapshot
│  └─ bind_foundry_inputs
│     └─ run_data_plane_gate
├─ link_trinity
│  └─ compile_foundry
│     └─ run_simulation
│        ├─ run_distributional_analysis
│        └─ propagate_uncertainty
│           └─ run_governance
└─ run_causal_evaluation (depends on build_data_snapshot)

build_decision_packet (depends on run_governance + run_causal_evaluation)
```

Точки входа: `polisyos.scientist.run_experiment(state)`, `polisyos.scientist.workflows.builder.run_default_workflow(...)`.

#### Крупные подсистемы Scientist

| Подсистема | Назначение |
|------------|-----------|
| **[engine/](policy-engine/src/polisyos/scientist/engine/README.md)** | DAG executor: `WorkflowSpec` validation, topological execution, strict `ExperimentState` (`extra="forbid"`), idempotency cache (по `run_id + node_id + state_reads + bind params`), checkpoint/resume, run lock |
| **[agent/](policy-engine/src/polisyos/scientist/agent/README.md)** | Иерархия AI-агентов: PI → Drafter → Formalizer → Critic. Multi-pass drafter mode. Self-healing: `FailureCard` → `ReflexionOrchestrator`. RAG, knowledge base, norm loader, feasibility probes, code verifier. **Опциональный контур** — default workflow не запускает автоматически |
| **[governance/](policy-engine/src/polisyos/scientist/governance/README.md)** | `ValidationPipeline` с ordered passes + short-circuit по blocker. Passes: Budget, Schema, Privacy, PII, QualityGate, Confidence, Equity, Safety, Legal. Профили: fast/mvp/strict. Human gate через `HumanGateProtocol` (typed `GateRequest`/`GateDecision` в CAS) |
| **[kernel/](policy-engine/src/polisyos/scientist/kernel/README.md)** | Phase FSM: INTAKE → FRAME → PREFLIGHT_GOV → PLAN → EXECUTE → POSTFLIGHT_GOV → DECIDE → PUBLISH → ARCHIVE (+ SEARCH/REFLEXION). 4 типа бюджетов: Compute, Evidence, Legitimacy, Complexity |
| **[nodes/](policy-engine/src/polisyos/scientist/nodes/README.md)** | Built-in workflow nodes: data (BuildDataSnapshot, BindFoundryInputs, EnrichKnowledge), compile (LinkTrinity, CompileFoundry), simulate (RunSimulation, RunDistributionalAnalysis, RunCausalEvaluation, PropagateUncertainty), governance (DataPlaneGate, LegalCheck, RunGovernance), decide (BuildDecisionPacket) |
| **[search/](policy-engine/src/polisyos/scientist/search/README.md)** | `SearchController` с cheap/expensive two-stage evaluation. Strategies: Random, Grid, adapter, optional Bayesian (botorch/gpytorch), Multi-Objective, Multi-Fidelity. Stopping: MaxIterations, MaxWallTime, ImprovementPlateau, TargetAchieved. Adversarial stress-test. **Опциональный контур** |
| **[doe/](policy-engine/src/polisyos/scientist/doe/README.md)** | Design of Experiments: ScenarioSweep, AblationPlan, SensitivityPlan (SALib: MORRIS/SOBOL/FAST), AdversarialPlan. Stress-test reports |
| **[backtesting/](policy-engine/src/polisyos/scientist/backtesting/README.md)** | Историческая валидация: OutcomeMasker, PredictionEvaluator (RMSE/MAE/MAPE/Coverage), TrustScorer (coverage/mape/bias → grade A-F). CLI: `polisyos scientist backtest` |

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

### Packs — компонентные пакеты

> `src/polisyos/packs/` · [README](policy-engine/src/polisyos/packs/README.md)

Встроенные доменные пакеты — reference implementation для быстрого старта.

**roads/** — полнофункциональный пакет (6 компонентов):

| Компонент | Тип | Назначение |
|-----------|-----|-----------|
| `roads.ir.registry_fragment@1.0.0` | IR_FRAGMENT | Единица `roads.kmh` (priority=100) |
| `roads.method.speed_cap@1.0.0` | FOUNDRY_METHOD | Ограничение скорости агентов (NumPy, O(N)) |
| `roads.scholar.speed_limit@1.0.0` | SCHOLAR_EXTRACTOR | Regex-извлечение speed limit (en/uk) |
| `lex.eval.simple_v1@1.0.0` | LEX_EVALUATOR | Обёртка evaluate_legality_impl |
| `lex.norm_extractor.regex_v1@1.0.0` | LEX_EXTRACTOR | Legacy regex-экстрактор |
| `roads.normpack.static_provider@1.0.0` | NORM_PACK_PROVIDER | Статический NormPack для UA |

**econ/** — минималистичный demo-пакет для тестирования conflict resolution.

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
- **Discovery:** автоматическое обнаружение через Python entry points (8 групп: `polisyos.scholar_extractors`, `polisyos.lex_evaluators`, `polisyos.norm_pack_providers` и др.)
- **Registry:** thread-safe с conflict resolution policies
- **Compliance:** валидация метаданных и ABI-совместимости

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

### Evidence / Provenance / Trust / Quality

Каждый data product несёт EvidenceBundle с provenance графом, quality indicators (missingness, staleness, coverage) и uncertainty bounds. Governance gates блокируют некачественные данные.

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
| **DuckDB** | Аналитические SQL-запросы, columnar storage, World Model |
| **Kùzu** (optional) | Графовые Cypher-запросы, entity-event network |

### ML & Optimization

| Технология | Назначение |
|------------|-----------|
| **Optax** | Оптимизаторы (Adam, SGD) для калибровки и RL |
| **Diffrax** | ODE-интеграция для динамических систем |
| **LangGraph / LangChain** | Оркестрация AI-агентов |
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

### Observability & Security

| Технология | Назначение |
|------------|-----------|
| **OpenTelemetry** | Distributed tracing, metrics export |
| **Prometheus** | Метрики и алертинг (27 alerts, 15 recording rules) |
| **Grafana** | 6 дашбордов (Executive, Scientist, Foundry HPC, SLO, Security, Knowledge Freshness) |
| **Loguru** | Структурированное логирование |
| **FastAPI / Uvicorn** (optional) | Runtime HTTP API v1 |
| **OPA (Rego)** | 7 policy-модулей авторизации |
| **Cryptography** | Ed25519 подписи, HMAC delegation tokens |

### Optional Dependency Groups

```
kuzu          — графовые запросы (Kuzu)
analytics     — scipy, statsmodels, linearmodels
sensitivity   — SALib
causal        — dowhy, econml
solvers       — ortools, pulp
multi-tenant  — psycopg, asyncpg, fastapi, uvicorn, httpx, PyJWT
methods-full  — analytics + causal + solvers
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

# Runtime API v1
PYTHONPATH=src uv run --extra multi-tenant --extra test python -c "
from polisyos.runtime.http.app import create_runtime_api_app
import uvicorn
uvicorn.run(create_runtime_api_app(), host='127.0.0.1', port=8000)
"

# Reference UI
cd frontend/runtime-reference-shell && python -m http.server 4173
# http://127.0.0.1:4173

# Dashboard
uv run streamlit run dashboard.py
```

macOS: импортировать `jax_bootstrap.py` **перед** `import jax` для защиты от Metal backend.

---

## Тестирование

> [README](policy-engine/tests/README.md) · 270 тестовых файлов · 9 conftest.py

Организованы по архитектурным слоям:

| Директория | `test_*.py` | Что тестирует |
|------------|:-----------:|--------------|
| [tests/](policy-engine/tests/README.md) (корень) | 6 | Архитектурные гейты, фасады API, component/packs discovery |
| [tests/contract/](policy-engine/tests/contract/README.md) | 18 | Trinity/IR контракты, ABI diff, миграции, SLO, gate models |
| tests/core/ | 51 | CAS, signing, canonical JSON, observability, security, components |
| [tests/fabric/](policy-engine/tests/fabric/README.md) | 46 | Connectors, catalog, provenance, trust, world/materialization, claims/scholar |
| [tests/foundry/](policy-engine/tests/foundry/README.md) | 65 | Methods framework, calibration, agent simulation, determinism/numerics |
| [tests/scientist/](policy-engine/tests/scientist/README.md) | 58 | Engine/workflow, governance passes, search/DOE, decision artifacts |
| tests/runtime/ | 10 | Runtime HTTP API, replay, timeline/debug/artifact inspection, tenant isolation |
| tests/ir/ | 10 | Loaders, registry fragments, uncertainty, portfolio/query contracts |
| tests/lex/ | 3 | Simulator: norm diff, mutator, engine |
| [tests/integration/](policy-engine/tests/integration/README.md) | 1 | Human-gate audit cycle (cross-layer) |
| tests/performance/ | 1 | Observability overhead SLA |

```bash
# Весь тестовый контур
uv run pytest

# Быстрый цикл
uv run pytest -m "not integration"

# По слоям
uv run pytest tests/contract -q
uv run pytest tests/fabric -q
uv run pytest tests/foundry -q
uv run pytest tests/scientist -q
uv run pytest tests/runtime -q

# Integration
POLISYOS_RUN_INTEGRATION=1 uv run pytest tests/scientist/integration -q

# Performance regression
uv run pytest tests/performance/test_overhead.py -q
```

---

## Инструменты разработчика

> [Полный каталог](policy-engine/tools/README.md)

### Архитектурные гейты (CI/pre-commit)

| Инструмент | Назначение |
|-----------|-----------|
| `tools/lint/lint_imports.py` | Import gate: Law A (однонаправленные зависимости), циклы |
| `tools/lint/lint_foundry.py` | Law B (Foundry без I/O) |
| `tools/lint/lint_connectors.py` | Изоляция connectors от scientist/foundry |
| `tools/lint/lint_connector_hardening.py` | P7 hardening для production connectors |
| `tools/lint/check_scholar_imports.py` | Запрет `scholar → fabric.io.db` |
| `tools/diagnostics/check_state_reads.py` | AST-проверка `state_reads` у scientist nodes |
| `tools/diagnostics/check_scientist_node_version_bump.py` | SemVer bump для измененных nodes |

### ABI и контракты

| Инструмент | Назначение |
|-----------|-----------|
| `tools/diagnostics/gen_schema.py` | Генерация/проверка JSON Schema из IR-моделей (34 ABI models) |
| `tools/diagnostics/abi_diff.py` | Семантический diff baseline/current (13 типов изменений), PASS/WARN/FAIL |
| `tools/connectors/check_contracts.py` | Валидация connector contracts snapshot |

### Runtime и OpenAPI

| Инструмент | Назначение |
|-----------|-----------|
| `tools/runtime/export_runtime_openapi.py` | Экспорт OpenAPI Runtime API v1 |
| `tools/runtime/generate_runtime_client.py` | Генерация TypeScript/JS клиента из OpenAPI |
| `tools/connectors/scaffold.py` | Scaffold нового коннектора (REST/CSV/SQL/SDMX) |

### Демо и бенчмарки

| Инструмент | Назначение |
|-----------|-----------|
| `tools/demos/run_laffer_demo.py` | JAX/Optax demo кривой Лаффера |
| `tools/demos/run_mechanism_design.py` | E2E differentiable mechanism design (IR → compile → execute → grad) |
| `tools/benchmarks/bench_simulation.py` | JAX benchmark simulation loop |

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
```

---

## Observability и Ops

> [ops/README.md](policy-engine/ops/README.md)

### Инфраструктура

| Модуль | Назначение |
|--------|-----------|
| **[Prometheus](policy-engine/ops/prometheus/README.md)** | 2 scrape jobs, 27 alerts (operational + SLO + audit chain), 15 recording rules |
| **[Grafana](policy-engine/ops/grafana/README.md)** | 6 дашбордов: Executive KPI, Scientist Agents, Foundry HPC, SLO Overview, Security Phase4, Knowledge Freshness |
| **[OPA](policy-engine/ops/opa/README.md)** | 7 Rego policy-модулей + 7 unit-тестов. Runtime path: `polisyos/authz/decision` |
| **Helm** | `polisyos-cell` (namespace isolation, NetworkPolicy, RBAC, Linkerd), `spire` (PSAT attestation), `keycloak` (OIDC/FIDO2) |
| **Terraform** | AKS node pool для confidential compute (`KataCcIsolation`, `sev-snp`) |
| **Migrations** | SQL-миграции для PostgreSQL RLS: `tenant_id` → backfill → RLS policies → least-privilege role |

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

API-first интерфейсы для Runtime API v1:

| Директория | Назначение |
|-----------|-----------|
| **[runtime-api-client/](policy-engine/frontend/runtime-api-client/README.md)** | Typed TypeScript клиент (`.ts`) + ESM runtime клиент (`.js`), автогенерируются из OpenAPI. Покрытие: Health, Runs, Debug, Artifacts |
| **[runtime-reference-shell/](policy-engine/frontend/runtime-reference-shell/README.md)** | Статический reference UI (`index.html` + `app.js` + `styles.css`), без build toolchain. Run List → Timeline → Node Debug → Artifact Inspector |

Контрактный поток:

```
src/polisyos/runtime/http/* (FastAPI)
  → tools/runtime/export_runtime_openapi.py
  → schemas/runtime_api_v1.openapi.json
  → tools/runtime/generate_runtime_client.py
  → frontend/runtime-api-client/runtimeApiClient.{ts,js}
  → frontend/runtime-reference-shell/app.js
```

Инварианты: UI строго API-only, read-only (`GET`), `source_kind == "core_run"`.

---

## Schemas и ABI

> [schemas/README.md](policy-engine/schemas/README.md)

Директория `schemas/` реализует Architectural Law C: контракты как источник правды.

| Артефакт | Содержание |
|----------|-----------|
| `snapshots/ir/` | 32 JSON Schema для IR-моделей (P0=18, P1=14), все `strict` compat mode |
| `snapshots/fabric/` | 2 JSON Schema для Fabric enum ABI (`edge_kind`, `node_kind`) |
| `snapshots/connectors/contracts.json` | 3 connector contracts (`eurostat`, `ukons`, `worldbank`), version evolution tracking |
| `runtime_api_v1.openapi.json` | OpenAPI 3.1.0 спецификация Runtime API v1 (15 GET endpoints) |
| `abi_models.py` | Реестр 34 ABI-моделей (`ABIModelEntry`) — single source of truth |

ABI compatibility: 13 типов изменений, P0 breaking → major bump, semantic diff + freshness check в CI.

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

Двухуровневая система (~50 README файлов):
- **Уровень 1:** модуль (`fabric/README.md`, `scientist/README.md`) — архитектура, зависимости, принципы
- **Уровень 2:** крупные подсистемы (`fabric/connectors/README.md`, `scientist/engine/README.md`) — API, контракты, внутренняя структура

### Ключевые документы

| Документ | Содержание |
|----------|-----------|
| [architecture.md](policy-engine/architecture.md) | Полная карта файловой структуры проекта (1080 строк) |
| [schemas/README.md](policy-engine/schemas/README.md) | ABI Schema Gate (34 модели, backward compatibility rules) |
| [ops/README.md](policy-engine/ops/README.md) | Platform operations (Helm, OPA, Prometheus, Grafana, Terraform, SQL migrations) |
| [tools/README.md](policy-engine/tools/README.md) | Полный каталог инженерных CLI-инструментов |
| [frontend/README.md](policy-engine/frontend/README.md) | Frontend foundation для Runtime API v1 |
| [tests/README.md](policy-engine/tests/README.md) | Обзор тестового контура (270 test files, 9 conftest) |

### Документация подсистем

| Слой | README |
|------|--------|
| Common | [common/README.md](policy-engine/src/polisyos/common/README.md) |
| Core | [core/README.md](policy-engine/src/polisyos/core/README.md), [artifacts/](policy-engine/src/polisyos/core/artifacts/README.md), [audit/](policy-engine/src/polisyos/core/audit/README.md), [components/](policy-engine/src/polisyos/core/components/README.md), [contracts/](policy-engine/src/polisyos/core/contracts/README.md), [observability/](policy-engine/src/polisyos/core/observability/README.md), [security/](policy-engine/src/polisyos/core/security/README.md), [cache/](policy-engine/src/polisyos/core/cache/README.md) |
| IR | [ir/README.md](policy-engine/src/polisyos/ir/README.md), [kernel/](policy-engine/src/polisyos/ir/kernel/README.md), [world/](policy-engine/src/polisyos/ir/world/README.md) |
| Fabric | [fabric/README.md](policy-engine/src/polisyos/fabric/README.md), [connectors/](policy-engine/src/polisyos/fabric/connectors/README.md), [claims/](policy-engine/src/polisyos/fabric/claims/README.md), [docs/](policy-engine/src/polisyos/fabric/docs/README.md), [world/](policy-engine/src/polisyos/fabric/world/README.md), [catalog/](policy-engine/src/polisyos/fabric/catalog/README.md) |
| Foundry | [foundry/README.md](policy-engine/src/polisyos/foundry/README.md), [agent_sim/](policy-engine/src/polisyos/foundry/agent_sim/README.md), [calibration/](policy-engine/src/polisyos/foundry/calibration/README.md), [methods/](policy-engine/src/polisyos/foundry/methods/README.md), [plugins/](policy-engine/src/polisyos/foundry/plugins/README.md) |
| Runtime | [runtime/README.md](policy-engine/src/polisyos/runtime/README.md) |
| Lex | [lex/README.md](policy-engine/src/polisyos/lex/README.md), [corpus/](policy-engine/src/polisyos/lex/corpus/README.md), [normpack/](policy-engine/src/polisyos/lex/normpack/README.md), [legal_evaluation/](policy-engine/src/polisyos/lex/legal_evaluation/README.md), [simulator/](policy-engine/src/polisyos/lex/simulator/README.md) |
| Scholar | [scholar/README.md](policy-engine/src/polisyos/scholar/README.md) |
| Scientist | [scientist/README.md](policy-engine/src/polisyos/scientist/README.md), [agent/](policy-engine/src/polisyos/scientist/agent/README.md), [engine/](policy-engine/src/polisyos/scientist/engine/README.md), [governance/](policy-engine/src/polisyos/scientist/governance/README.md), [kernel/](policy-engine/src/polisyos/scientist/kernel/README.md), [nodes/](policy-engine/src/polisyos/scientist/nodes/README.md), [search/](policy-engine/src/polisyos/scientist/search/README.md), [doe/](policy-engine/src/polisyos/scientist/doe/README.md), [backtesting/](policy-engine/src/polisyos/scientist/backtesting/README.md) |
| Packs | [packs/README.md](policy-engine/src/polisyos/packs/README.md), [roads/](policy-engine/src/polisyos/packs/roads/README.md) |
