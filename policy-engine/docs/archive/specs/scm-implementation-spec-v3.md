# Спецификация реализации: Структурно-каузальные модели в PolicyOS

**Версия:** 3.0 (реструктуризация v2.3)
**Дата:** 2026-02-28
**Статус:** DRAFT
**Покрытие:** 17 фаз (−1..15, включая 8A/8B) + 8 сквозных слоёв, ориентировочно 15–19 месяцев (2 инженера)
**Изменения v3.0:** реструктуризация: матрица зависимостей перенесена вверх, фаза 0 разбита на подфазы, 8B возвращена в фазу 8, инварианты сгруппированы, устранены дубли формул и Приложения B

---

## Содержание

1. [Обзор и принципы](#1-обзор-и-принципы)
2. [Матрица зависимостей и timeline](#2-матрица-зависимостей-и-timeline)
3. [Фазы реализации](#3-фазы-реализации)
   - 3.1 [Фаза −1 — Architecture Freeze](#фаза--1--architecture-freeze)
   - 3.2 [Фаза 0 — Scientific Knowledge Graph](#фаза-0--scientific-knowledge-graph)
     - 0a: Article Extraction Pipeline
     - 0b: Dataset Metadata Graph + WVS
     - 0c: Legal Bridge + Proxy Resolver
     - 0d: Variable Canonization + Quality Validation
   - 3.3 [Фаза 1 — Терминологическая гигиена](#фаза-1--терминологическая-гигиена-и-adr)
   - 3.4 [Фаза 2 — DoWhy Identify/Estimate](#фаза-2--dowhy-identifyestimate)
   - 3.5 [Фаза 3 — Refutation pipeline](#фаза-3--refutation-pipeline)
   - 3.6 [Фаза 4 — Sensitivity metrics](#фаза-4--sensitivity-metrics)
   - 3.7 [Фаза 5 — CausalGraphModel](#фаза-5--causalgraphmodel-как-ir-артефакт)
   - 3.8 [Фаза 6 — PCMCI/Tigramite discovery](#фаза-6--causal-discovery)
   - 3.9 [Фаза 7 — Constraint/score-based discovery](#фаза-7--constraint-discovery)
   - 3.10 [Фаза 8 — Governance gates (8A + 8B)](#фаза-8--governance-gates)
   - 3.11 [Фаза 9 — Literature+LLM prior](#фаза-9--literaturellm-prior)
   - 3.12 [Фаза 10 — StructuralCausalModelSpec](#фаза-10--structural-causal-model-spec)
   - 3.13 [Фаза 11 — Causal queries](#фаза-11--causal-queries)
   - 3.14 [Фаза 12 — Transportability](#фаза-12--transportability)
   - 3.15 [Фаза 13 — SCM + ABM bridge](#фаза-13--scm-abm-bridge)
   - 3.16 [Фаза 14 — CausalModelEnsemble](#фаза-14--causal-model-ensemble)
   - 3.17 [Фаза 15 — Parameter Registry](#фаза-15--parameter-registry)
4. [Сквозные слои](#4-сквозные-слои)
   - 4.1 Архитектурные паттерны (SL-1..SL-4)
   - 4.2 Тестирование (SL-5..SL-6)
   - 4.3 Операционные (SL-7..SL-8)
5. [Справочные материалы](#5-справочные-материалы)
   - 5.1 [Реестр ADR](#реестр-adr)
   - 5.2 [Справочник формул confidence](#справочник-формул-confidence)
   - 5.3 [Глоссарий](#глоссарий)
   - 5.4 [Карта рисков](#карта-рисков)
   - 5.5 [Стратегия обработки ошибок](#стратегия-обработки-ошибок-внешних-зависимостей)
6. [Приложения](#приложения)
   - A: [Выравнивание с существующей кодовой базой](#приложение-a)
   - B: [Backlog оптимизаций](#приложение-b)

---

## 1. Обзор и принципы

### 1.1 Цель документа

Документ описывает 17 последовательных фаз (−1..15) превращения PolicyOS в платформу со структурно-каузальным интеллектом, опирающимся на три источника знаний: эмпирические данные (tabular/time-series), научная литература (OpenAlex-based SKG), и экспертные prior (LLM-ассистированные, но верифицированные). Ключевые свойства целевой системы:

- Каузальные графы как IR-артефакты с полным provenance (через `InputRef` → `put_json_artifact`)
- Автоматическая идентификация, оценка и рефутация эффектов
- Prior для графа строится из peer-reviewed литературы, а не из LLM-весов
- Формальный перенос результатов между контекстами (Simplified TR с явным scope)
- **Замыкание трёх графов:** SKG (что переносить) + Dataset Metadata Graph (чем вычислить P*(Z)) + Legal Knowledge Graph (можно ли + юридические S-узлы) — превращает transport formula из символического утверждения в вычислимый pipeline
- Контекстно-адаптивный реестр параметров для JAX-симуляций

### 1.2 Архитектурные инварианты

Каждая фаза обязана соблюдать 14 законов, сгруппированных по теме:

#### Чистота кода

| Закон | Требование | Проверка |
|-------|-----------|----------|
| **A (Import Gate)** | PyWhy/Tigramite/causal-learn/kuzu — только в `foundry/methods/catalog/causal/` и `scientist/nodes/builtins/causal/` (kuzu также в `fabric/world/materialize/`). Следуем `STANDARD_BANNED_IMPORT_ROOTS` в `lint_foundry.py` | `lint_foundry.py` allowlist |
| **B (Foundry Pure)** | Каузальные вычисления — method jobs на `ComputeBackend.NUMPY`. `pure_step` принимает только arrays/primitives | `test_foundry_purity.py` |
| **F (Pure Step)** | `FoundryMethod.pure_step()` — `@staticmethod`, без side effects. Следует Protocol из `foundry/methods/base.py` | Type checker + test |

#### Контракты и lineage

| Закон | Требование | Проверка |
|-------|-----------|----------|
| **C (Contract-first)** | Каждый новый IR-тип имеет JSON Schema snapshot в `schemas/snapshots/ir/` | `gen_schema.py --check` |
| **E (Evidence)** | Каждый артефакт хранит `inputs: list[InputRef]`. Граф→Report→Envelope→DecisionPacket — полная lineage | Integration test |
| **H (Stable Digest)** | Все параметры stable-serializable через `CanonInfo` (sort_keys=True, separators=(",",":")) | `_stable_digest()` tests |

#### Качество и воспроизводимость

| Закон | Требование | Проверка |
|-------|-----------|----------|
| **D (Reproducibility)** | Стохастические элементы получают seed из `ExperimentState.params.random_seed`. Tier: `DeterminismTier.STATISTICAL` | Golden record tests |
| **K (Governance)** | Новые проверки — `ValidatorPass`, регистрируются в `ValidationPipeline`. Профили FAST/MVP/STRICT | `test_validation_pipeline.py` |

#### Каузальная корректность

| Закон | Требование | Проверка |
|-------|-----------|----------|
| **L (Literature-first)** | Рёбра с source только `llm_prior` → `unsupported_by_evidence=True`, не проходят STRICT | `test_literature_gate.py` |
| **T (Transport-aware)** | `CausalEffectReport` из external source обязан содержать `transport_result` | `test_transport_required.py` |
| **G (Graph Closure)** | Transport formula вычислима при замыкании трёх графов: SKG + Dataset Graph + Legal Graph. Отсутствие графа → `DataGap` + confidence penalty | `test_graph_closure.py` |
| **S (Three-Layer)** | Конфликты классифицируются: L1 (identifiability), L2 (estimation), L3 (ontology). Смешение слоёв запрещено | `test_layer_separation.py` |
| **V (SUTVA)** | Каждый `CausalEffectReport` и `TransportabilityResult` содержит `sutva_assumed: bool`. Market-wide → WARNING | `test_sutva_check.py` |

### 1.3 Три уровня использования научных статей

```
ArticleExtractionResult
├── empirical_parameters     → ContextAdaptiveParameterRegistry (Фаза 15)
│                              └── JAX-симуляции через Foundry
├── causal_claims            → LiteratureCausalPrior (Фаза 9)
│                              └── Рёбра в prior graph с evidence_refs
├── mechanisms               → ProblemFrame construction
│                              └── Структура причинно-следственных цепочек
├── boundary_conditions      → TransportabilityEngine (Фаза 12)
│                              └── Условия применимости → S-узлы
└── citation_summary         → DecisionPacket / Report generation
                               └── Объяснимость для стейкхолдеров
```

### 1.4 Стратегия зависимостей

> **Консолидация технологического стека (устранение "зоопарка"):**
>
> Для 2 инженеров критично минимизировать количество библиотек. Принципы:
> 1. **Один основной движок для каждой задачи**, не 3-4 параллельных
> 2. **Графовые запросы:** KuzuDB (Cypher) — единый стек с World Graph
> 3. **In-memory граф-алгоритмы:** rustworkx — замена NetworkX
> 4. **SCM inference:** DoWhy (identify/estimate) + EconML (CATE) — один PyWhy стек
> 5. **Discovery:** tigramite (time-series) + causal-learn (cross-sectional) — необходимый минимум
> 6. **Backlog (не в MVP):** NumPyro (Фаза 15 JAX), y0 (Фаза 12b), DAGMA (масштабирование)
>
> **Убрано из обязательного стека:** отдельный dowhy.gcm (заменён hybrid `HybridSCMFit`),
> NetworkX (заменён KuzuDB + rustworkx).

```toml
[project.optional-dependencies]
# --- Core SCM (один PyWhy стек) ---
causal             = ["dowhy>=0.11,<0.13", "econml>=0.15,<1.0"]
causal-discovery   = ["causal-learn>=0.1.3.8", "tigramite>=5.2"]
causal-sensitivity = ["pysensemakr>=0.1"]

# --- Graph operations (единый стек: KuzuDB + rustworkx) ---
# kuzu уже определён в pyproject.toml: kuzu = ["kuzu>=0.1.0"]
academic-skg       = ["rustworkx>=0.14", "httpx>=0.25"]
academic-skg-llm   = ["openai>=1.0"]

# --- Backlog (НЕ в MVP, устанавливается по необходимости) ---
# causal-bayesian  = ["numpyro>=0.15", "jax>=0.4"]     # Фаза 15 JAX backend
# causal-full-tr   = ["y0>=0.2"]                         # Фаза 12b full do-calculus

# --- Meta-group ---
causal-full        = ["polisyos[causal,causal-discovery,causal-sensitivity,academic-skg,academic-skg-llm,kuzu]"]
```

WGI/WDI получаем через `WorldBankConnector`, WVS — новый connector, Legal bridge через `lex/api.py`.

Избегаем параллельных библиотек для одной задачи:

| Задача | MVP библиотека | Backlog upgrade |
|--------|---------------|-----------------|
| Causal identification & estimation | DoWhy + EconML (CATE) | — |
| Discovery (time-series) | Tigramite (PCMCI) | — |
| Discovery (cross-section) | causal-learn (PC, FCI) | DAGMA (>50 vars) |
| SCM fitting | `HybridSCMFit` (DoWhy GCM + SKG prior) | NumPyro (Bayesian) |
| Graph queries | **KuzuDB** (Cypher) | — |
| Graph algorithms | **rustworkx** (in-memory) | — |
| Full do-calculus | Simplified TR (built-in) | y0 bridge (Phase 12b) |

Принцип graceful skip сохраняется: отсутствие любой группы — соответствующие методы не регистрируются в `MethodRegistry`.

### 1.5 Каноническая файловая структура (целевое состояние)

Расширяем существующие модули, не создаём параллельные. Пометка `[СУЩЕСТВУЕТ]` — файл уже есть, `[РАСШИРЯЕТСЯ]` — добавляем в существующий файл, `[НОВЫЙ]` — создаём.

```
policy-engine/src/polisyos/
├── ir/
│   └── analytics/
│       ├── causal.py                          # [СУЩЕСТВУЕТ] CausalEffectReport
│       │                                      #   [РАСШИРЯЕТСЯ] +transport_result, +graph_ref (optional)
│       ├── causal_graph.py                    # [НОВЫЙ] CausalGraphModel (Фаза 5)
│       ├── causal_discovery.py                # [НОВЫЙ] CausalDiscoveryReport (Фаза 6)
│       ├── literature.py                      # [НОВЫЙ] ArticleExtractionResult, EvidenceParameter,
│       │                                      #   CausalClaim, Mechanism, BoundaryCondition,
│       │                                      #   LiteratureCausalPrior (Фазы 0, 9)
│       ├── context.py                         # [НОВЫЙ] ContextProfile, ContextProfileInferenceLevel
│       │                                      #   (canonical location — импортируется Фазами 0 и 12)
│       ├── structural_causal_model.py         # [НОВЫЙ] StructuralCausalModelSpec (Фаза 10)
│       ├── causal_queries.py                  # [НОВЫЙ] CausalQuery, CausalQueryResult (Фаза 11)
│       ├── transportability.py                # [НОВЫЙ] SelectionDiagram, SNode,
│       │                                      #   TransportabilityResult (Фаза 12)
│       ├── causal_ensemble.py                 # [НОВЫЙ] CausalModelEnsemble (Фаза 14)
│       ├── sensitivity.py                     # [НОВЫЙ] SensitivityResult, EValueResult (Фаза 4)
│       └── parameters.py                      # [НОВЫЙ] ParameterBundle, ParameterApplicability (Фаза 15)
│
├── academic/                                  # [СУЩЕСТВУЕТ] → SKG base (Граф 1)
│   ├── knowledge/
│   │   ├── types.py                           # [РАСШИРЯЕТСЯ] +BoundaryCondition, +TransportFormula,
│   │   │                                      #   +ArticleExtractionResult (extends WorkRecord)
│   │   ├── store.py                           # [СУЩЕСТВУЕТ] Vector store
│   │   ├── skg_query.py                       # [НОВЫЙ] Запросы к SKG (causal claims + params)
│   │   ├── variable_canonizer.py              # [НОВЫЙ] Иерархическая канонизация
│   │   └── skg_versioning.py                  # [НОВЫЙ] Версионирование + retraction
│   ├── batch/
│   │   ├── harvester.py                       # [РАСШИРЯЕТСЯ] +5-level extraction, +context_classifier
│   │   ├── graph_builder.py                   # [РАСШИРЯЕТСЯ] +DDL: ac_skg_edges, ac_boundary_conditions
│   │   ├── config.py                          # [РАСШИРЯЕТСЯ] +screening/extraction model config
│   │   ├── context_classifier.py              # [НОВЫЙ] Инференс ContextProfile из метаданных статьи
│   │   └── prompts/                           # [НОВЫЙ] LLM prompts для extraction
│   │       ├── screening.py
│   │       ├── causal_claims.py
│   │       ├── mechanisms.py
│   │       └── boundary_conditions.py
│   └── openalex/
│       ├── client.py                          # [НОВЫЙ] OpenAlex API wrapper (если нет)
│       ├── priority_filter.py                 # [НОВЫЙ] Фильтрация по topic display_name
│       └── rate_limiter.py                    # [НОВЫЙ] По паттерну _SlidingWindowLimiter
│
├── datasets/                                  # [СУЩЕСТВУЕТ] → Dataset Metadata Graph (Граф 2)
│   ├── knowledge/
│   │   ├── types.py                           # [РАСШИРЯЕТСЯ] +DatasetVariable (canonical mapping)
│   │   ├── store.py                           # [СУЩЕСТВУЕТ]
│   │   ├── variable_alignment.py              # [НОВЫЙ] Canonical var → dataset variable
│   │   ├── proxy_resolver.py                  # [НОВЫЙ] Прокси-цепочки
│   │   └── p_star.py                          # [НОВЫЙ] P*(Z) computation
│   └── batch/
│       └── graph_builder.py                   # [РАСШИРЯЕТСЯ] +DDL: ds_variable_alignments
│
├── lex/                                       # [СУЩЕСТВУЕТ] → Legal Graph bridge (Граф 3)
│   ├── api.py                                 # [РАСШИРЯЕТСЯ] +evaluate_transport_constraints()
│   └── legal_evaluation/
│       ├── transport_constraints.py           # [НОВЫЙ] ConstraintSeverity, LegalToDAGMapping
│       └── backends/                          # [СУЩЕСТВУЕТ] simple_v1.py etc.
│
├── fabric/connectors/sources/
│   ├── world_bank.py                          # [СУЩЕСТВУЕТ] WorldBankConnector (WDI/WGI)
│   └── wvs.py                                 # [НОВЫЙ] World Values Survey connector
│
├── foundry/methods/catalog/causal/
│   ├── scm.py                                 # [СУЩЕСТВУЕТ] SyntheticControlMethod
│   ├── _registry_boot.py                      # [РАСШИРЯЕТСЯ] +новые методы
│   ├── dowhy_identify_estimate.py             # [НОВЫЙ] Фаза 2
│   ├── dowhy_refute.py                        # [НОВЫЙ] Фаза 3
│   ├── sensitivity_metrics.py                 # [НОВЫЙ] Фаза 4
│   ├── pcmci_discovery.py                     # [НОВЫЙ] Фаза 6
│   ├── constraint_discovery.py                # [НОВЫЙ] Фаза 7
│   ├── literature_prior.py                    # [НОВЫЙ] Фаза 9
│   ├── graph_reconciliation.py                # [НОВЫЙ] Фаза 9
│   ├── gcm_fit.py                             # [НОВЫЙ] Фаза 10
│   ├── gcm_query.py                           # [НОВЫЙ] Фаза 11
│   ├── transport_check.py                     # [НОВЫЙ] Фаза 12
│   └── parameter_transfer.py                  # [НОВЫЙ] Фаза 15
│
├── scientist/
│   ├── nodes/builtins/
│   │   ├── __init__.py                        # [РАСШИРЯЕТСЯ] +каузальные ноды в builtin_nodes()
│   │   ├── causal/                            # [НОВЫЙ] каталог каузальных нод
│   │   │   ├── build_literature_prior.py      # Фаза 9
│   │   │   ├── run_causal_discovery.py        # Фаза 6
│   │   │   ├── reconcile_causal_graph.py      # Фаза 9
│   │   │   ├── validate_causal_graph.py       # Фаза 8
│   │   │   ├── fit_structural_model.py        # Фаза 10
│   │   │   ├── run_causal_queries.py          # Фаза 11
│   │   │   ├── resolve_transport.py           # Фаза 12 (ResolutionLoop нода)
│   │   │   ├── run_abm_consistency.py         # Фаза 13
│   │   │   ├── resolve_parameters.py          # Фаза 15
│   │   │   ├── materialize_causal_kuzu.py     # [НОВЫЙ] DuckDB→Kuzu (паттерн world/materialize/kuzu.py)
│   │   │   └── ddl/
│   │   │       └── kuzu_causal.cypher         # [НОВЫЙ] Cypher DDL для CausalVar, SNode, CausalEdge
│   │   └── governance/
│   │       ├── run_governance.py              # [СУЩЕСТВУЕТ]
│   │       └── legal_check.py                 # [СУЩЕСТВУЕТ]
│   ├── governance/
│   │   ├── pipeline.py                        # [СУЩЕСТВУЕТ] ValidationPipeline
│   │   └── passes/
│   │       ├── literature_gate_pass.py        # [НОВЫЙ] Закон L (Фаза 8)
│   │       ├── transport_required_pass.py     # [НОВЫЙ] Закон T (Фаза 8)
│   │       └── human_review_pass.py           # [НОВЫЙ] STRICT governance (Фаза 8)
│   └── workflows/
│       ├── engine_langgraph.py                # [СУЩЕСТВУЕТ]
│       └── causal_full.py                     # [НОВЫЙ] scientist_causal_full workflow
│
└── tools/
    ├── lint/lint_foundry.py                   # [РАСШИРЯЕТСЯ] +каузальные dir policies
    └── diagnostics/gen_schema.py              # [СУЩЕСТВУЕТ]
```

### 1.6 Границы оптимальности и фиксированные входы (anti-overclaim)

Все утверждения про "оптимальность" в документе фиксируются **относительно входного набора**, а не "вообще среди всех возможных систем":

- `I` — evidence base (набор источников с данными/метаданными/контекстом)
- `[G]` — класс графов (PAG), содержащий истинный DAG
- `P` — policy сертификации выравнивания (пороги, типы сертификатов, правило композиции confidence)
- `R_eta` — класс допустимых reconciliation maps при данном `P`

Оптимальность разделяется на два уровня:
- **Inner optimality:** для фиксированного comparison complex решаем reconciliation минимум-нормы (Hodge/Laplacian).
- **Outer optimality:** выбираем comparison complex, максимизируя coverage при штрафе за irreducible conflict.

Это защищает от overclaim и не добавляет runtime-стоимости: секция описывает контракт интерпретации результатов, а не новые вычисления.

---

## 2. Матрица зависимостей и timeline

```
Фаза -1 (Architecture Freeze)  → нет зависимостей (ПЕРВАЯ)
Фаза 0  (SKG = academic/ ext)  → Фаза -1
Фаза 1  (Терминология)         → нет зависимостей
Фаза 2  (DoWhy I/E)            → Фаза 1
Фаза 3  (Refutation)           → Фаза 2
Фаза 4  (Sensitivity)          → Фаза 3
Фаза 5  (CausalGraphModel)     → Фаза 2
Фаза 6  (PCMCI discovery)      → Фаза 5
Фаза 7  (PC/FCI/GES)           → Фаза 5, 6 (shared infra)
Фаза 8A (Governance: L+Human)  → Фаза 4, 5 (LiteratureGate требует Фазу 0)
Фаза 8B (Governance: T)        → Фаза 12a (TransportRequiredPass требует стабильный TR)
Фаза 9  (Lit+LLM Prior)        → Фаза 0, 5, 6 или 7
Фаза 10 (SCM mechanisms)       → Фаза 5, 2
Фаза 11 (Causal queries)       → Фаза 10
Фаза 12 (Transportability)     → Фаза 0 (SKG + Dataset Graph + Legal Graph bridge), 5, 10, 11
Фаза 13 (ABM bridge)           → Фаза 10, 11
Фаза 14 (Ensemble)             → Фаза 6/7, 10, 13 (optional)
Фаза 15 (Parameter Registry)   → Фаза 0, 12
```

Фаза 0 теперь включает Dataset Metadata Graph и Legal Graph bridge. Фаза 12 зависит от всех трёх подсистем Фазы 0.

### Оптимальная timeline при 2 инженерах (15–19 месяцев)

Таймлайн **сокращён** на ~1 месяц за счёт переиспользования `academic/`, `datasets/`, `fabric/`, `lex/` вместо создания с нуля. Добавлена Фаза −1 (1-2 недели).

```
Неделя 1-2:
  Оба: Фаза -1 (Architecture Freeze: контракты, CI gate, lint, snapshot tests)

Месяц 1-2:
  Инженер A: Фаза 1 → 2 → 3
  Инженер B: Фаза 0a (расширение academic/: 5-level extraction, DDL, context_classifier)

Месяц 3-4:
  Инженер A: Фаза 4 → 5
  Инженер B: Фаза 0b (расширение datasets/: variable alignment, ds_variable_alignments DDL)
             + WVSConnector в fabric/

Месяц 5-6:
  Инженер A: Фаза 6 → 7
  Инженер B: Фаза 0c (proxy resolver в datasets/, transport_constraints в lex/)
             + Фаза 0 quality validation (50 статей)

Месяц 7-8:
  Инженер A: Фаза 8A (governance: LiteratureGatePass + HumanReviewPass)
  Инженер B: Фаза 9 (literature prior + reconciliation, time-aware _break_cycles)

Месяц 9-11:
  Инженер A: Фаза 10 (HybridSCMFit: GCM + SKG prior) → 11
  Инженер B: Фаза 12a (ContextProfile, S-diagram, Simplified TR v2)

Месяц 12-13:
  Инженер A: Фаза 12b (ResolutionLoop, DataGap, Legal S-nodes) + Подфаза 8B (TransportRequiredPass) → 13
  Инженер B: Фаза 15 (parameter registry + JAX backend bridge) → 14

Месяц 14-16:
  Оба: e2e scientist_causal_full workflow, cross-graph integration tests, regression

Месяц 17 (CUTOVER):
  Один controlled switch: scientist_default → scientist_causal_full
  Full regression pass, rollback plan ready

Месяц 18-19 (buffer):
  Stabilization, edge cases, documentation, Phase 12b backlog triage
```

---

## 3. Фазы реализации

## Фаза −1 — Architecture Freeze

**Длительность:** 1–2 недели | **Риск:** LOW
**Предусловия:** нет

> **Принцип "без переездов":** не создавать изолированные модули, когда эквивалентные уже существуют. Строить поверх `academic/`, `datasets/`, `fabric/connectors/`, `lex/` — расширяя их контрактами, а не дублируя.

### −1.1 Точки сборки (Assembly Points) → контракты

Перед стартом любой фазы фиксируем контракты на существующие модули, которые будут расширяться:

| Модуль | Файлы-контракты | Что фиксируем |
|--------|----------------|---------------|
| **academic/** (→ SKG base) | `academic/knowledge/types.py`, `academic/batch/graph_builder.py` | `WorkRecord`, `CausalClaimResult`, `ParameterEstimateResult`, DDL таблицы `ac_works`, `ac_causal_claims`, `ac_parameter_estimates` |
| **datasets/** (→ Dataset Graph base) | `datasets/knowledge/types.py`, `datasets/batch/graph_builder.py` | `DatasetRecord`, `DatasetSearchResult`, DDL таблицы `ds_datasets`, `ds_distributions` |
| **fabric/connectors/** (→ data sources) | `fabric/connectors/sources/world_bank.py` | `WorldBankConnector` API: `fetch()`, `list_datasets()`, `get_dataset_schema()` |
| **lex/** (→ Legal Graph bridge) | `lex/api.py`, `lex/legal_evaluation/` | `evaluate_legality()` signature, `LegalEvaluationRequest`, `LegalReportRef` |
| **foundry/methods/base.py** (→ Foundry ABI) | `base.py` | `MethodSignature` (frozen, `input_slots: frozenset`, `output_slots: frozenset`), `ComputeBackend.NUMPY` → `supports_jit/vmap/grad=False` |
| **scientist/governance/** (→ Governance) | `pipeline.py`, `profiles.py` | `ValidationPipeline` (pass ordering by cost, short-circuit), profile-driven pass selection |
| **schemas/** (→ ABI registry) | `abi_models.py`, `tools/quality/diagnostics/gen_schema.py` | `IR_ABI_MODELS` registry, `gen_schema.py --check` для snapshot validation |
| **tools/quality/lint/** (→ Import gate) | `lint_foundry.py` | `STANDARD_BANNED_IMPORT_ROOTS`, `NO_JAX_DIRS`, per-directory policy enforcement |

### −1.2 Three-Graph Federation: не новые модули, а расширение существующих

SKG, Dataset Graph и Legal Graph — это **не** отдельные `skg/`, `skg/dataset_graph/`, `skg/legal_graph/` модули. Это расширения существующих `academic/`, `datasets/` и `lex/`:

```
Замыкание трёх графов:

  academic/                        ← расширяется типами SKG
    knowledge/types.py             ← +BoundaryCondition, +TransportFormula
    batch/graph_builder.py         ← +DDL таблицы ac_boundary_conditions, ac_skg_edges
    batch/harvester.py             ← расширяется 5-level extraction
    knowledge/skg_query.py         ← НОВЫЙ: запросы к SKG поверх academic DuckDB
    knowledge/variable_canonizer.py ← НОВЫЙ: иерархическая канонизация

  datasets/                        ← расширяется Dataset Metadata Graph
    knowledge/types.py             ← +DatasetVariable (canonical mapping)
    batch/graph_builder.py         ← +DDL таблица ds_variable_alignments
    knowledge/proxy_resolver.py    ← НОВЫЙ: прокси-цепочки
    knowledge/p_star.py            ← НОВЫЙ: P*(Z) computation

  lex/                             ← расширяется Legal → DAG bridge
    legal_evaluation/transport_constraints.py  ← НОВЫЙ: ConstraintSeverity, LegalToDAGMapping
    api.py                         ← расширяется evaluate_transport_constraints()

  scientist/nodes/builtins/causal/ ← НОВЫЙ каталог каузальных нод
    resolve_transport.py           ← TransportabilityResolutionLoop как нода

  ir/analytics/                    ← расширяется каузальными IR
    transportability.py            ← НОВЫЙ (ContextProfile, SelectionDiagram, TransportabilityResult)
    causal.py                      ← +опциональные поля (backward-compatible)
```

### −1.3 Compatibility Policy

**Правило:** только additive changes до релиза full-system, один planned cutover.

1. **CausalEffectReport**: расширять **только** опциональными полями (`transport_result: TransportabilityResult | None = None`). Обязательные поля не изменяются.
2. **Schema versioning**: `schema_version: "1.0"` → `"1.1"` при добавлении полей. Все ноды делают dual-read: `1.0` и `1.1`.
3. **DuckDB таблицы**: новые таблицы в `academic/` (`ac_skg_edges`, `ac_boundary_conditions`) и `datasets/` (`ds_variable_alignments`) — **ALTER TABLE не используется**. Новые таблицы рядом, foreign keys на существующие.
4. **Workflow**: новый `scientist_causal_full` workflow параллельно с `scientist_default`. Cutover один раз после full regression.
5. **Governance passes**: новые passes (`LiteratureGatePass`, `TransportabilityRequiredPass`) регистрируются в `ValidationPipeline` через entry points, не hardcoded.

### −1.4 Import Gate как CI-контракт

`lint_foundry.py` уже enforces per-directory import policies. С первого дня Фазы 0:

```python
# Добавить в lint_foundry.py:
NO_JAX_DIRS += {"methods/catalog/causal/transport", "methods/catalog/causal/discovery"}
MIXED_BACKEND_ALLOWED += {rustworkx, kuzu}  # rustworkx + KuzuDB вместо networkx
```

CI pipeline: `python tools/quality/lint/lint_foundry.py --strict` на каждый PR.

### −1.5 Migration Budget = 1

Один controlled switch `scientist_default` → `scientist_causal_full`:
- **До cutover:** оба workflow работают параллельно. `scientist_default` — production, `scientist_causal_full` — staging.
- **Cutover trigger:** full regression на staging проходит >98% существующих тестов.
- **Rollback:** cutover reversible за 1 commit (swap workflow ID в конфигурации).
- **Нет постоянной миграции.** Нет feature flags. Нет dual-mode execution. Один switch.

### −1.6 Definition of Done — Фаза −1

- [ ] Контракты зафиксированы как snapshot tests (`gen_schema.py --check` для каждого)
- [ ] `lint_foundry.py` обновлён с новыми directory policies
- [ ] `scientist_causal_full` workflow зарегистрирован (пустой: только существующие ноды)
- [ ] CI pipeline: schema check + lint + import gate на каждый PR
- [ ] ADR-0053 (Architecture Freeze) принят командой

---

## Фаза 0 — Scientific Knowledge Graph: расширение academic/ модуля

**Длительность:** 5–7.5 недель (параллельно с Фазой 1–2), разделена на 4 подфазы: 0a (Extraction Pipeline, 2–3 нед.), 0b (Dataset Graph + WVS, 1.5–2 нед.), 0c (Legal Bridge + Proxy Resolver, 1–1.5 нед.), 0d (Quality Validation, 0.5–1 нед.)
**Предусловия:** Фаза −1
**Риск:** MEDIUM-HIGH (качество LLM-извлечения, rate limits OpenAlex)

### Подфаза 0a: Article Extraction Pipeline (2–3 недели)

> Секции 0.1–0.9, 0.16: OpenAlex harvesting, LLM-извлечение, канонизация переменных, SKG store.

### 0.1 Цель

Построить Scientific Knowledge Graph (SKG) — базу знаний, извлечённую из peer-reviewed литературы через OpenAlex. SKG служит источником для: (a) prior для каузального графа, (b) эмпирических параметров для JAX-симуляций, (c) boundary conditions для transportability, (d) **базового ContextProfile для каждой статьи**. SKG хранится в DuckDB (не SQLite — по аналогии с `graph_builder.py`) как специализированный граф-стор.

### 0.2 Приоритизация статей из OpenAlex

**ИСПРАВЛЕНО:** matching по `topic.display_name`, а не по topic ID.

```python
# academic/openalex/priority_filter.py

TIER_1_KEYWORDS = {
    # Прямое ядро PolicyOS — ищем в display_name
    "economic policy", "fiscal policy", "tax policy", "public policy",
    "policy analysis", "policy evaluation", "governance",
    "corruption", "institutional quality", "state capacity",
    "social policy", "welfare state",
}

TIER_2_KEYWORDS = {
    # Контекстно-зависимые: активируются по domain filter
    "natural resources", "immigration", "legal reform",
    "labor market", "gender equality", "trade policy",
    "education policy", "health policy", "environmental policy",
    "agent-based model", "computational social science",
}

def should_process(
    work: dict,
    domain_filter: list[str] | None = None,
    min_citations: int = 10,
) -> tuple[bool, str]:
    """
    Returns (should_process, reason).
    reason: "tier1" | "tier2_domain_match" | "skip_irrelevant" | "skip_low_citation"
    """
    # ИСПРАВЛЕНО: matching по display_name, не по ID
    topic_names = {
        t.get("display_name", "").lower()
        for t in work.get("topics", [])
    }

    # Tier 1: прямое совпадение ключевых слов
    if any(kw in name for kw in TIER_1_KEYWORDS for name in topic_names):
        if work.get("cited_by_count", 0) >= min_citations:
            return True, "tier1"
        return False, "skip_low_citation"

    # Tier 2: domain-dependent
    if domain_filter:
        domain_lower = [d.lower() for d in domain_filter]
        if any(
            kw in name and any(d in name for d in domain_lower)
            for kw in TIER_2_KEYWORDS
            for name in topic_names
        ):
            if work.get("cited_by_count", 0) >= max(5, min_citations // 2):
                return True, "tier2_domain_match"

    return False, "skip_irrelevant"
```

### 0.3 Rate Limiter (по паттерну из `spo_extractor.py`)

```python
# academic/openalex/rate_limiter.py
# Следует паттерну _SlidingWindowLimiter из lex/batch/spo_extractor.py

class OpenAlexRateLimiter:
    """
    OpenAlex polite pool: 10 req/sec с mailto.
    Паттерн: sliding window + exponential backoff на 429.
    """

    def __init__(self, max_rps: int = 10, max_concurrent: int = 5):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._window: deque[float] = deque()
        self._max_rps = max_rps
        self._backoff_until: float = 0.0

    async def acquire(self) -> None:
        async with self._semaphore:
            now = time.monotonic()
            # Backoff penalty (по аналогии с GonkaClient)
            if now < self._backoff_until:
                await asyncio.sleep(self._backoff_until - now)
            # Sliding window
            while self._window and self._window[0] < now - 1.0:
                self._window.popleft()
            if len(self._window) >= self._max_rps:
                sleep_time = 1.0 - (now - self._window[0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
            self._window.append(time.monotonic())

    def report_429(self) -> None:
        """Exponential backoff: 5s buffer (по аналогии с GonkaClient)."""
        self._backoff_until = time.monotonic() + 5.0
```

### 0.4 IR: ArticleExtractionResult

Центральный тип данных фазы 0. Следует паттернам `CausalEffectReport`: ConfigDict(extra="forbid"), model_validator, persist/load helpers.

```python
# ir/analytics/literature.py

from polisyos.ir.artifacts.contracts import InputRef
from polisyos.ir.artifacts.io import put_json_artifact, get_json_artifact

class ParameterType(str, Enum):
    QUANTITATIVE   = "quantitative"
    QUALITATIVE    = "qualitative"
    ORDINAL        = "ordinal"
    DISTRIBUTIONAL = "distributional"

class EvidenceStrength(str, Enum):
    RCT            = "rct"
    QUASI_NATURAL  = "quasi_natural"
    OBSERVATIONAL  = "observational"
    THEORETICAL    = "theoretical"
    META_ANALYSIS  = "meta_analysis"

class CausalDirection(str, Enum):
    POSITIVE   = "positive"
    NEGATIVE   = "negative"
    AMBIGUOUS  = "ambiguous"
    NON_LINEAR = "non_linear"

class EvidenceParameter(BaseModel):
    """Числовой или качественный параметр, извлечённый из статьи."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str                        # Каноническое имя: "gdp_growth.real"
    display_name: str
    parameter_type: ParameterType

    # Значение
    value: float | None = None
    value_range: tuple[float, float] | None = None
    value_qualitative: str | None = None
    confidence_interval: tuple[float, float] | None = None
    unit: str | None = None

    # Источник и контекст
    evidence_strength: EvidenceStrength
    geographic_scope: str            # "OECD", "Sub-Saharan Africa", "Germany"
    time_period: str | None = None
    aggregation_level: str           # "national" | "regional" | "firm" | "individual"

    # Применимость
    transferability: str             # "high" | "conditional" | "low"
    transfer_conditions: list[str] = []
    heterogeneity_note: str | None = None
    subgroup_estimates: dict[str, float] = {}

    @model_validator(mode="after")
    def _validate_value_present(self) -> "EvidenceParameter":
        """Хотя бы одно из value/value_range/value_qualitative должно быть задано."""
        if self.value is None and self.value_range is None and self.value_qualitative is None:
            raise ValueError("At least one of value, value_range, value_qualitative required")
        if self.confidence_interval is not None:
            lo, hi = self.confidence_interval
            if not (math.isfinite(lo) and math.isfinite(hi) and lo <= hi):
                raise ValueError(f"Invalid confidence_interval: ({lo}, {hi})")
        return self

class CausalClaim(BaseModel):
    """Причинно-следственное утверждение из статьи."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    cause_variable: str              # Каноническое имя переменной
    effect_variable: str
    direction: CausalDirection
    magnitude_qualitative: str | None = None
    effect_size: float | None = None
    evidence_strength: EvidenceStrength
    scope_conditions: list[str] = []
    counterevidence_notes: str | None = None

class Mechanism(BaseModel):
    """Объяснительный механизм — почему причина порождает эффект."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str
    mediating_variables: list[str] = []
    evidence_type: str               # "laboratory" | "natural_experiment" | "survey"
    theoretical_framework: str | None = None

class BoundaryCondition(BaseModel):
    """Условие применимости результатов статьи — основа для S-узлов."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    variable: str                    # Переменная контекста
    condition_type: str              # "threshold" | "categorical" | "ordinal"
    required_value: str | float
    violated_by: list[str] = []
    consequence_if_violated: str

class ArticleExtractionResult(BaseModel):
    """Полный результат обработки одной научной статьи."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    openalex_id: str
    doi: str | None = None
    title: str
    year: int
    cited_by_count: int

    # Пять типов извлечённых объектов
    empirical_parameters: list[EvidenceParameter] = []
    causal_claims: list[CausalClaim] = []
    mechanisms: list[Mechanism] = []
    boundary_conditions: list[BoundaryCondition] = []
    citation_summary: str = ""

    # Методология статьи
    methodology: str | None = None
    sample_size: int | None = None

    # Провенанс извлечения (по аналогии с SPOExtractionResult)
    extraction_model: str
    extraction_timestamp: str
    extraction_confidence: float

    # ContextProfile заполняется СРАЗУ в Фазе 0
    source_context: "ContextProfile | None" = None

    # Стоимость (по аналогии с SPOExtractionResult)
    screening_cost_usd: float = 0.0
    extraction_cost_usd: float = 0.0
    token_count_prompt: int = 0
    token_count_completion: int = 0

    @model_validator(mode="after")
    def _validate_confidence(self) -> "ArticleExtractionResult":
        if not (0.0 <= self.extraction_confidence <= 1.0):
            raise ValueError(f"extraction_confidence must be [0,1], got {self.extraction_confidence}")
        return self


# --- Persistence (паттерн из causal.py) ---

_SCHEMA_NAME = "ir.article_extraction_result"
_SCHEMA_VERSION = "1.0"

def persist_article_extraction_result(
    store,
    result: ArticleExtractionResult,
    inputs: list[InputRef] | None = None,
) -> dict:
    return put_json_artifact(
        store,
        result.model_dump(mode="json"),
        kind=_SCHEMA_NAME,
        schema_name=_SCHEMA_NAME,
        schema_version=_SCHEMA_VERSION,
        inputs=inputs or [],
    )

def load_article_extraction_result(store, ref) -> ArticleExtractionResult:
    payload = get_json_artifact(store, ref.artifact_id if hasattr(ref, "artifact_id") else ref)
    return ArticleExtractionResult.model_validate(payload)
```

### 0.5 Context Classifier в Фазе 0

**Проблема:** `source_context` заполнялся в Фазе 12, но нужен в Фазах 0, 9, 15 — циклическая зависимость.

**Решение:** базовый ContextProfile инферится из метаданных статьи и OpenAlex affiliations сразу при экстракции. Полная версия ContextProfile (с точными WGI/WVS значениями) обогащается в Фазе 12, но базовая версия достаточна для SKG queries и parameter selection.

```python
# academic/batch/context_classifier.py

class ContextProfileInferenceLevel(str, Enum):
    INFERRED_BASIC = "inferred_basic"      # Из метаданных статьи (Фаза 0)
    ENRICHED       = "enriched"            # С WGI/WVS данными (Фаза 12)
    MANUAL         = "manual"              # Задан экспертом

def infer_context_from_article(
    work: dict,                            # OpenAlex work object
    extraction: ArticleExtractionResult,
) -> ContextProfile:
    """
    Инферит базовый ContextProfile из:
    1. OpenAlex authorships → institutions → country_code → income_level
    2. EvidenceParameter.geographic_scope → context_id
    3. BoundaryCondition → structural indicators
    4. work.publication_year → time_period

    Точность: ~70% для income_level, ~50% для institutional_quality.
    Достаточно для SKG ordering, недостаточно для точного transport check.
    """

    # Извлечь страны из affiliations
    countries = set()
    for authorship in work.get("authorships", []):
        for inst in authorship.get("institutions", []):
            cc = inst.get("country_code")
            if cc:
                countries.add(cc)

    # Извлечь geographic_scope из параметров
    scopes = {p.geographic_scope for p in extraction.empirical_parameters}

    # Определить основную страну/регион
    context_id, context_label = _resolve_primary_context(countries, scopes)

    # Income level из World Bank classification (static lookup)
    income_level = _lookup_income_level(context_id)

    # Structural indicators — заглушки, обогащаются в Фазе 12
    return ContextProfile(
        context_id=context_id,
        context_label=context_label,
        income_level=income_level,
        time_period=str(work.get("publication_year", "")),
        inference_level=ContextProfileInferenceLevel.INFERRED_BASIC,
        data_sources=["openalex_affiliations"],
    )

# Static lookup: ISO country code → IncomeLevel
_INCOME_LEVEL_MAP: dict[str, IncomeLevel] = {
    "US": IncomeLevel.HIGH, "DE": IncomeLevel.HIGH, "GB": IncomeLevel.HIGH,
    "FR": IncomeLevel.HIGH, "JP": IncomeLevel.HIGH, "CA": IncomeLevel.HIGH,
    "UA": IncomeLevel.LOWER_MIDDLE, "NG": IncomeLevel.LOWER_MIDDLE,
    "CN": IncomeLevel.UPPER_MIDDLE, "BR": IncomeLevel.UPPER_MIDDLE,
    "IN": IncomeLevel.LOWER_MIDDLE, "ZA": IncomeLevel.UPPER_MIDDLE,
    # ... расширяется из World Bank данных
}
```

### 0.6 Иерархическая канонизация переменных

**Проблемы:**
1. Плоский словарь не различал "gdp_growth" vs "real_gdp_growth"
2. LLM fallback нарушал Закон D (Reproducibility)
3. 11 переменных в seed — ~1% от нужного

#### 0.6.0 Формальная грамматика канонических имён (ADR-0084)

Каноническое имя переменной определяется формальной грамматикой. Все компоненты системы (SKG, Dataset Graph, CausalEdge, EvidenceParameter) обязаны использовать только валидные имена.

```
canonical_name  ::= domain "." subdomain ("." modifier)*
                  | domain                               // root-level alias

domain          ::= IDENTIFIER
subdomain       ::= IDENTIFIER
modifier        ::= transformation | scope | temporal

transformation  ::= "real" | "nominal" | "log" | "growth" | "level" | "rate"
                   | "per_capita" | "ppp" | "index" | "share" | "ratio"
scope           ::= "national" | "regional" | "urban" | "rural" | "firm" | "individual"
temporal        ::= "annual" | "quarterly" | "monthly" | "lagged"

IDENTIFIER      ::= [a-z][a-z0-9_]*      // snake_case, max 40 chars
```

**Примеры валидных имён:**
- `gdp_growth.real` — реальный рост ВВП
- `gdp_growth.real.per_capita` — реальный рост ВВП на душу
- `gdp_growth.nominal.quarterly` — номинальный рост ВВП (квартальный)
- `institutional_quality.rule_of_law` — подкомпонент
- `corruption_level` — корневой алиас (без subdomain)
- `tax_elasticity.income_tax.regional` — составное имя

**Правила disambiguation:**
1. При коллизии (`inflation.cpi` vs `inflation_cpi`) — предпочитать иерархическую форму
2. Максимальная глубина: 4 уровня (`domain.sub.mod1.mod2`)
3. `_root` в seed dict → domain без subdomain (backward-compatible alias)
4. Новые переменные, не прошедшие грамматику → `pending_review` автоматически

**Seed-таблица:** минимум 200 переменных покрывающих все domain'ы PolicyOS. Группы:
- Макроэкономика: 40 переменных (gdp_*, inflation_*, fiscal_*, trade_*, ...)
- Институты: 30 (institutional_quality.*, corruption_level.*, state_capacity.*, ...)
- Социология: 25 (social_trust.*, social_capital.*, inequality_*, ...)
- Рынок труда: 20 (unemployment_rate.*, labor_*, wage_*, ...)
- Образование/здоровье: 20 (human_capital.*, education_*, health_*, ...)
- Демография: 15 (population_*, migration_*, urbanization_*, ...)
- Финансы: 15 (interest_rate.*, credit_*, savings_*, ...)
- Энергетика/экология: 15 (energy_*, emissions_*, ...)
- Политика/право: 20 (rule_of_law.*, regulatory_*, property_rights.*, ...)

Полная seed-таблица создаётся в `academic/knowledge/canonical_seed.py` в Фазе −1, до первого запуска extraction pipeline.

**Решение:**

```python
# academic/batch/variable_canonizer.py

# Иерархическая структура: parent.child
CANONICAL_VARIABLES: dict[str, dict[str, list[str]]] = {
    "gdp_growth": {
        "_root": ["gdp growth", "economic growth", "output growth"],
        "real": ["real gdp growth", "real economic growth", "real output growth"],
        "nominal": ["nominal gdp growth", "nominal gdp"],
        "per_capita": ["gdp per capita growth", "per capita growth"],
    },
    "inflation": {
        "_root": ["inflation", "price level", "price growth"],
        "cpi": ["cpi", "consumer price index", "cpi inflation"],
        "core": ["core inflation", "underlying inflation"],
    },
    "fiscal_multiplier": {
        "_root": ["fiscal multiplier", "government spending multiplier"],
        "expenditure": ["expenditure multiplier", "spending multiplier"],
        "tax": ["tax multiplier", "revenue multiplier"],
    },
    "institutional_quality": {
        "_root": ["institutional quality", "governance quality", "institutional capacity"],
        "rule_of_law": ["rule of law", "legal certainty"],
        "regulatory": ["regulatory quality", "regulatory effectiveness"],
        "voice": ["voice and accountability", "democratic accountability"],
    },
    "corruption_level": {
        "_root": ["corruption", "corruption index", "bribe rate", "corruption perception"],
        "petty": ["petty corruption", "street-level corruption"],
        "grand": ["grand corruption", "state capture"],
    },
    "social_trust": {
        "_root": ["social trust", "interpersonal trust", "generalized trust"],
        "institutional": ["trust in government", "institutional trust", "political trust"],
        "interpersonal": ["interpersonal trust", "social trust level"],
    },
    "unemployment_rate": {
        "_root": ["unemployment", "jobless rate", "unemployment rate"],
        "youth": ["youth unemployment", "youth jobless rate"],
        "long_term": ["long-term unemployment", "structural unemployment"],
    },
    "inequality_gini": {
        "_root": ["inequality", "gini", "income inequality", "gini coefficient"],
        "income": ["income gini", "income inequality"],
        "wealth": ["wealth inequality", "wealth gini"],
    },
    "state_capacity": {
        "_root": ["state capacity", "government effectiveness", "bureaucratic quality"],
        "fiscal": ["fiscal capacity", "tax capacity", "revenue capacity"],
        "coercive": ["coercive capacity", "enforcement capacity"],
    },
    "tax_elasticity": {
        "_root": ["tax elasticity", "tax revenue elasticity"],
        "income_tax": ["income tax elasticity", "pit elasticity"],
        "vat": ["vat elasticity", "consumption tax elasticity"],
    },
    "social_capital": {
        "_root": ["social capital", "civic engagement", "associational life"],
    },
}

class VariableCanonizer:
    """
    Детерминированная канонизация с кэшированием.
    LLM fallback кэшируется в SKG — один и тот же термин
    всегда маппится в одно и то же имя (Закон D).
    """

    def __init__(self, skg_cache: dict[str, str] | None = None):
        self._reverse: dict[str, str] = {}
        self._build_reverse_index()
        self._cache = skg_cache or {}       # raw_name → canonical, persisted in SKG
        self._pending_review: list[tuple[str, str]] = []  # (raw, suggested_canonical)

    def _build_reverse_index(self) -> None:
        for parent, children in CANONICAL_VARIABLES.items():
            for child_key, synonyms in children.items():
                canonical = parent if child_key == "_root" else f"{parent}.{child_key}"
                for syn in synonyms:
                    self._reverse[syn.lower().strip()] = canonical

    def canonize(self, raw_name: str) -> tuple[str, bool]:
        """
        Returns (canonical_name, is_new).
        is_new=True означает что имя не было в словаре и добавлено
        через кэш или LLM fallback. Такие имена попадают в
        pending_review для batch human approval.
        """
        normalized = raw_name.lower().strip()

        # 1. Точное совпадение в словаре
        if normalized in self._reverse:
            return self._reverse[normalized], False

        # 2. Кэш SKG (детерминированный, Закон D)
        if normalized in self._cache:
            return self._cache[normalized], False

        # 3. Fuzzy match (без LLM — детерминированный)
        best = self._fuzzy_match(normalized)
        if best:
            self._cache[normalized] = best
            return best, True

        # 4. Fallback: snake_case от raw_name + помечаем для review
        fallback = raw_name.replace(" ", "_").replace("-", "_").lower()
        self._cache[normalized] = fallback
        self._pending_review.append((raw_name, fallback))
        return fallback, True

    def _fuzzy_match(self, normalized: str, threshold: float = 0.85) -> str | None:
        """Levenshtein ratio matching."""
        from difflib import SequenceMatcher
        best_score = 0.0
        best_canonical = None
        for syn, canonical in self._reverse.items():
            score = SequenceMatcher(None, normalized, syn).ratio()
            if score > best_score and score >= threshold:
                best_score = score
                best_canonical = canonical
        return best_canonical

    def get_pending_review(self) -> list[tuple[str, str]]:
        """Имена для batch human approval."""
        return list(self._pending_review)

    def approve_mapping(self, raw_name: str, canonical: str) -> None:
        """Human approves a mapping — persists to SKG cache."""
        self._cache[raw_name.lower().strip()] = canonical
        self._pending_review = [
            (r, c) for r, c in self._pending_review
            if r.lower().strip() != raw_name.lower().strip()
        ]
```

### 0.7 SKG хранилище (расширение academic/ DuckDB)

Новые таблицы добавляются **рядом** с существующими `ac_works`, `ac_causal_claims`, `ac_parameter_estimates` в том же DuckDB. Существующие таблицы не изменяются (Compatibility Policy). Foreign keys через `openalex_id` → `ac_works.id`.

```python
# academic/knowledge/skg_store.py
# расширение academic/ DuckDB, не отдельная БД

SKG_SCHEMA = """
-- Эти таблицы добавляются К существующим ac_works, ac_causal_claims, ac_parameter_estimates
-- Foreign keys: skg_articles.openalex_id → ac_works.id

CREATE TABLE IF NOT EXISTS skg_articles (
    openalex_id     TEXT PRIMARY KEY,
    doi             TEXT,
    title           TEXT NOT NULL,
    year            INT NOT NULL,
    cited_by_count  INT DEFAULT 0,
    extraction_json TEXT NOT NULL,          -- ArticleExtractionResult as JSON
    context_json    TEXT,                   -- ContextProfile as JSON
    extraction_ts   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    retracted       BOOLEAN DEFAULT FALSE,  -- retraction tracking
    skg_version     INT NOT NULL            -- version when added
);

CREATE TABLE IF NOT EXISTS skg_variables (
    canonical_name  TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    parent_name     TEXT,                   -- hierarchical: gdp_growth for gdp_growth.real
    mention_count   INT DEFAULT 0,
    first_seen_ts   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS skg_edges (
    edge_id         TEXT PRIMARY KEY,       -- hash(src, dst)
    src             TEXT NOT NULL REFERENCES skg_variables(canonical_name),
    dst             TEXT NOT NULL REFERENCES skg_variables(canonical_name),
    direction       TEXT NOT NULL,          -- CausalDirection value
    n_articles      INT DEFAULT 1,
    article_refs    TEXT NOT NULL,           -- JSON array of openalex_ids
    evidence_strength TEXT NOT NULL,         -- best EvidenceStrength
    confidence      REAL NOT NULL,
    scope_conditions TEXT DEFAULT '[]',      -- JSON array
    meta_effect_size REAL,
    updated_ts      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS skg_parameters (
    param_id        TEXT PRIMARY KEY,       -- hash(name, openalex_id)
    canonical_name  TEXT NOT NULL REFERENCES skg_variables(canonical_name),
    openalex_id     TEXT NOT NULL REFERENCES skg_articles(openalex_id),
    parameter_json  TEXT NOT NULL,           -- EvidenceParameter as JSON
    context_json    TEXT                     -- ContextProfile of source article
);

-- канонизация cache
CREATE TABLE IF NOT EXISTS skg_canonization_cache (
    raw_name        TEXT PRIMARY KEY,
    canonical_name  TEXT NOT NULL,
    approved        BOOLEAN DEFAULT FALSE,  -- human-reviewed
    created_ts      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- версионирование
CREATE TABLE IF NOT EXISTS skg_versions (
    version_id      INT PRIMARY KEY,
    created_ts      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    n_articles      INT,
    n_edges         INT,
    n_variables     INT,
    description     TEXT
);

-- Indexes (по аналогии с graph_builder.py)
CREATE INDEX IF NOT EXISTS idx_edges_src ON skg_edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON skg_edges(dst);
CREATE INDEX IF NOT EXISTS idx_edges_confidence ON skg_edges(confidence);
CREATE INDEX IF NOT EXISTS idx_params_name ON skg_parameters(canonical_name);
CREATE INDEX IF NOT EXISTS idx_params_article ON skg_parameters(openalex_id);
CREATE INDEX IF NOT EXISTS idx_articles_year ON skg_articles(year);
CREATE INDEX IF NOT EXISTS idx_articles_retracted ON skg_articles(retracted);
"""
```

### 0.8 Confidence aggregation

**Проблема:** `weighted_mean * log(1+n)/log(10)` — 9 observational перевешивали 1 RCT.

**Решение:** двухкомпонентная формула: (1) evidence quality score, (2) replication bonus.

```python
EVIDENCE_WEIGHTS: dict[EvidenceStrength, float] = {
    EvidenceStrength.RCT: 1.0,
    EvidenceStrength.META_ANALYSIS: 0.95,
    EvidenceStrength.QUASI_NATURAL: 0.7,
    EvidenceStrength.OBSERVATIONAL: 0.4,
    EvidenceStrength.THEORETICAL: 0.15,
}

def aggregate_edge_confidence(
    articles: list[tuple[EvidenceStrength, float]],  # (strength, extraction_confidence)
) -> float:
    """
    Двухкомпонентная формула:

    1. quality_score = max(evidence_weight_i × extraction_confidence_i)
       (одна сильная статья устанавливает floor)

    2. replication_bonus = min(0.3, 0.1 × log2(n_independent_articles))
       (репликация добавляет до +0.3, с насыщением)

    3. confidence = min(1.0, quality_score + replication_bonus)

    Свойства:
    - 1 RCT (extraction_conf=0.9) → 0.9 + 0.0 = 0.9
    - 9 observational (extraction_conf=0.8 each) → 0.32 + 0.3 = 0.62
    - 1 RCT + 3 observational → 0.9 + 0.2 = 1.0 (capped)
    - 1 theoretical → 0.15 + 0.0 = 0.15

    Одна RCT всегда сильнее множества observational. ✓
    """
    if not articles:
        return 0.0

    # Quality score: best single article
    quality_score = max(
        EVIDENCE_WEIGHTS[strength] * ext_conf
        for strength, ext_conf in articles
    )

    # Replication bonus: log saturation
    n = len(articles)
    replication_bonus = min(0.3, 0.1 * math.log2(max(1, n)))

    return min(1.0, quality_score + replication_bonus)
```

### 0.9 SKG Versioning & Retraction Handling

```python
# academic/knowledge/skg_versioning.py

class SKGVersionManager:
    """
    Управляет версиями SKG. Каждое batch-добавление статей
    создаёт новую версию. CausalGraphModel хранит skg_version_id
    для воспроизводимости.

    Retraction handling:
    - OpenAlex предоставляет retraction_date/is_retracted
    - При обнаружении retraction: помечаем статью, пересчитываем
      confidence для затронутых рёбер
    - НЕ удаляем рёбра автоматически — только пересчёт + WARNING
    """

    def create_version(self, conn, description: str = "") -> int:
        """Создаёт новую версию SKG, возвращает version_id."""
        ...

    def check_retractions(self, conn, openalex_client) -> list[str]:
        """
        Проверяет все статьи в SKG на retraction status.
        Возвращает список retracted openalex_ids.
        """
        ...

    def handle_retraction(self, conn, openalex_id: str) -> dict:
        """
        1. Помечает статью retracted=True
        2. Пересчитывает confidence для всех рёбер, ссылающихся на эту статью
        3. Если ребро осталось без поддерживающих статей — удаляет
        4. Возвращает отчёт: {affected_edges: [...], removed_edges: [...]}
        """
        ...
```

### Подфаза 0b: Dataset Metadata Graph + WVS Connector (1.5–2 недели)

> Секции 0.10–0.12: интеграция источников данных (WGI/WDI/WVS), Dataset Metadata Graph, variable alignment.

### 0.10 Data Source Integration через fabric connectors

WGI и WDI получаем через **существующий** `WorldBankConnector` (`fabric/connectors/sources/world_bank.py`), а не через standalone клиенты. Это переиспользует rate-limit (`HTTPResilienceProfile`), retry, caching (`ConnectorCache`), contracts (`ConnectorMetadataSpec`), и quality (`QualityValidator`).

```python
# Использование существующего WorldBankConnector для WGI/WDI:

from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
from polisyos.fabric.connectors.types import FetchRequest, ConnectionHandle

async def fetch_wgi_indicators(
    connector: WorldBankConnector,
    handle: ConnectionHandle,
    country_code: str,
    year: int,
) -> dict[str, float | None]:
    """
    WGI через существующий WorldBankConnector.
    Indicator IDs:
      - RL.EST → institutional_quality (Rule of Law)
      - CC.EST → corruption_level (Control of Corruption, inverted)
      - GE.EST → state_capacity (Government Effectiveness)
      - RQ.EST → regulatory_quality
    """
    indicators = {
        "RL.EST": "institutional_quality",
        "CC.EST": "corruption_level",
        "GE.EST": "state_capacity",
    }
    result: dict[str, float | None] = {}
    for indicator_id, canonical_name in indicators.items():
        fetch_result = await connector.fetch(handle, FetchRequest(
            dataset_id=indicator_id,
            dimensions={"country": country_code},
            date_range=(str(year), str(year)),
        ))
        if fetch_result.data is not None and not fetch_result.data.empty:
            # Нормализация WGI (-2.5..+2.5) → [0,1]
            raw_val = fetch_result.data.iloc[0]["value"]
            result[canonical_name] = (raw_val + 2.5) / 5.0 if raw_val is not None else None
        else:
            result[canonical_name] = None
    return result


# WVS: НОВЫЙ fabric connector (по паттерну WorldBankConnector)
# fabric/connectors/sources/wvs.py

class WVSConnector(HTTPConnectorBase[pd.DataFrame]):
    """
    World Values Survey connector.
    По паттерну WorldBankConnector: namespace, capabilities, metadata, resilience.
    Данные: фиксированные waves (Wave 7: 2017-2022).
    Предоставляет: social_trust, cultural_cluster.

    ВАЖНО: WVS не проводится ежегодно!
    Wave 7 охватывает 2017-2022, но в разных странах в разные годы:
    - Украина: 2020, Германия: 2018, Россия: 2017.
    Запрос по точному году (year=2020 для Германии) вернёт None
    и необоснованно создаст DataGap. Решение: wave-based temporal matching.
    """
    namespace: ClassVar[str] = "wvs"
    short_id: ClassVar[str] = "wvs7"
    connector_id: ClassVar[str] = "wvs.wave7"

    # Wave metadata для temporal matching
    WAVE_RANGES: ClassVar[dict[int, tuple[int, int]]] = {
        5: (2005, 2009),
        6: (2010, 2014),
        7: (2017, 2022),
    }

    def find_closest_in_wave(
        self,
        country_code: str,
        target_year: int,
        max_distance_years: int = 3,
    ) -> tuple[int | None, int | None]:
        """
        Wave-based temporal matching для опросных данных.

        Вместо exact year match, ищем ближайший опрос в той же волне.
        Returns: (actual_survey_year, wave_number) или (None, None)

        Пример: target_year=2020, Germany surveyed in 2018 (Wave 7)
        → returns (2018, 7) т.к. |2020-2018| <= max_distance_years
        """
        ...

    # ... следует паттерну WorldBankConnector
```

### 0.11 Dataset Metadata Graph

Dataset Metadata Graph решает проблему операционализации transport formula: превращает символическое "нужен P*(Z)" в конкретный API-вызов или SQL-запрос. Это федеративный каталог внешних датасетов с маппингом на канонические переменные SKG.

```python
# datasets/knowledge/registry.py

class DatasetEntry(BaseModel):
    """Запись о датасете в каталоге."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str                     # "WB_WGI_2023", "TI_CPI_2023"
    provider: str                       # "world_bank", "transparency_international"
    title: str
    variables: list["DatasetVariable"]
    coverage: "DatasetCoverage"
    access: "DatasetAccess"
    update_frequency: str               # "annual", "wave", "quarterly"
    last_updated: str                   # ISO date

class DatasetVariable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_name: str                       # "rl_est" (WGI original column)
    canonical_name: str                 # "institutional_quality" (SKG canonical)
    mapping_confidence: float           # 0.0-1.0: насколько точно raw ≈ canonical
    mapping_rationale: str              # "WGI Rule of Law → institutional quality (r=0.92)"
    is_proxy: bool = False              # Прямое соответствие или прокси?
    proxy_penalty: float = 0.0          # Штраф при использовании как прокси

class DatasetCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    countries: list[str]                # ISO alpha-2 codes
    time_range: str                     # "2000-2023"
    granularity: str                    # "country-year", "region-quarter", "individual"

class DatasetAccess(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    access_type: str                    # "open", "registration", "licensed"
    api_endpoint: str | None = None
    bulk_download_url: str | None = None
    license: str                        # "CC-BY-4.0", "proprietary"


class DatasetRegistry:
    """
    DuckDB-backed каталог датасетов.
    По паттерну из graph_builder.py: DuckDB schema + batch inserts.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS datasets (
        dataset_id    TEXT PRIMARY KEY,
        provider      TEXT NOT NULL,
        title         TEXT NOT NULL,
        coverage_json TEXT NOT NULL,
        access_json   TEXT NOT NULL,
        update_freq   TEXT NOT NULL,
        last_updated  TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS dataset_variables (
        dataset_id         TEXT NOT NULL REFERENCES datasets(dataset_id),
        raw_name           TEXT NOT NULL,
        canonical_name     TEXT NOT NULL,
        mapping_confidence REAL NOT NULL,
        mapping_rationale  TEXT NOT NULL,
        is_proxy           BOOLEAN DEFAULT FALSE,
        proxy_penalty      REAL DEFAULT 0.0,
        PRIMARY KEY (dataset_id, raw_name)
    );
    CREATE INDEX IF NOT EXISTS idx_dv_canonical ON dataset_variables(canonical_name);
    """

    def find_datasets_for_variable(
        self,
        canonical_var: str,
        country_code: str,
        year_range: tuple[int, int] | None = None,
    ) -> list["DatasetMatch"]:
        """
        Находит датасеты, покрывающие каноническую переменную для контекста.
        Возвращает отсортированный список: прямые совпадения первыми, прокси — далее.
        """
        ...

    def compute_p_star_z(
        self,
        canonical_var: str,
        country_code: str,
        year: int,
        *,
        # поддержка условных распределений для медиаторов
        condition_on: dict[str, float] | None = None,
    ) -> "PStarZResult":
        """
        Вычисляет P*(Z) или P*(Z|X=x) для target контекста.

        CRITICAL (Pearl & Bareinboim, 2011):
        - Если Z — pre-treatment covariate: condition_on=None → P*(z) маргинальная
        - Если Z — медиатор (X→Z→Y): condition_on={"treatment": x} → P*(z|x)
          Маргинальная P*(z) для медиатора инвалидирует каузальный эффект!

        Когда condition_on задан:
          1. Находим датасет с обеими переменными (Z и conditioning vars)
          2. Фильтруем observations по condition_on
          3. Возвращаем эмпирическое распределение / среднее P*(z|x)
        """
        ...


class DatasetMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str
    raw_variable: str
    canonical_variable: str
    is_proxy: bool
    proxy_penalty: float
    coverage_match: str                 # "full", "partial", "none"
    temporal_match: str                 # "exact", "wave_closest", "overlap", "extrapolation"
    # wave-based matching для опросных данных (WVS, EVS)
    actual_survey_year: int | None = None  # Реальный год опроса (если wave_closest)
    temporal_distance_years: int = 0       # |target_year - actual_year|


class PStarZResult(BaseModel):
    """Результат вычисления P*(Z) или P*(Z|X) для одной переменной."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_variable: str
    value: float | None                 # None если данные недоступны
    dataset_id: str | None
    raw_variable: str | None
    is_proxy: bool = False
    proxy_chain: list[str] = []         # ["CPI → institutional_quality"]
    confidence: float                   # 1.0 прямое, <1.0 прокси/экстраполяция
    penalty_breakdown: dict[str, float] = {}  # {"proxy": -0.1, "temporal": -0.05}
    # conditional P*(z|x) support
    is_conditional: bool = False        # True если P*(z|x), False если P*(z)
    condition_on: dict[str, float] = {} # {"tax_rate": 0.25} для медиаторов
    # distribution support (not just point estimate)
    distribution: list[float] | None = None  # Empirical samples if available
    distribution_type: str = "point"    # "point", "empirical", "kde"
```

### 0.12 Variable Alignment Pipeline (Dataset Graph)

Маппинг canonical_var SKG → raw variable в датасете — не string matching, а доменная экспертиза. Pipeline:

```python
# datasets/knowledge/variable_alignment.py

class AlignmentMethod(str, Enum):
    EXACT       = "exact"        # Один-к-одному маппинг в seed таблице
    SEMANTIC    = "semantic"     # Embedding similarity > threshold
    META_ANALYTIC = "meta_analytic"  # Корреляция из мета-анализов в SKG

class VariableAlignment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_var: str
    dataset_var: str
    dataset_id: str
    method: AlignmentMethod
    confidence: float
    evidence: str                       # Обоснование маппинга

# Seed таблица известных маппингов (расширяемая)
SEED_ALIGNMENTS: dict[str, list[tuple[str, str, float]]] = {
    # canonical_var: [(dataset_id, raw_var, confidence), ...]
    "institutional_quality": [
        ("WB_WGI", "rl_est", 0.92),             # Rule of Law estimate
        ("WB_WGI", "ge_est", 0.85),             # Government Effectiveness
        ("TI_CPI", "cpi_score", 0.78),          # Corruption Perceptions (прокси)
    ],
    "social_trust": [
        ("WVS_W7", "A165", 0.95),               # "Most people can be trusted"
        ("EVS_2017", "v31", 0.90),               # European Values Survey analog
    ],
    "gdp_per_capita": [
        ("WB_WDI", "NY.GDP.PCAP.PP.CD", 1.0),  # PPP, current international $
    ],
    "informal_economy_share": [
        ("IMF_SHADOW", "shadow_gdp_pct", 0.88), # IMF shadow economy estimates
        ("WB_WDI", "SL.TLF.TOTL.IN.ZS", 0.65), # Informal employment (прокси)
    ],
}
```

### Подфаза 0c: Legal Bridge + Proxy Resolver (1–1.5 недели)

> Секции 0.13–0.14: прокси-цепочки для недоступных данных, Legal Knowledge Graph bridge.

### 0.13 Proxy Resolver

Когда прямые данные недоступны, Dataset Graph предлагает прокси-цепочки с контекстно-зависимыми штрафами.

```python
# datasets/knowledge/proxy_resolver.py

class ProxyCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    proxy_variable: str
    proxy_dataset_id: str
    proxy_raw_name: str
    base_correlation: float             # Базовая корреляция из литературы
    context_adjustment: float           # Поправка на контекст
    effective_confidence: float         # base * context_adjustment
    source: str                         # "meta_analysis" | "seed_table" | "skg_correlation"

class ProxyChain(BaseModel):
    """Цепочка прокси для одной недоступной переменной."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_variable: str                # Что нужно
    proxies: list[ProxyCandidate]       # Доступные прокси (отсортированы по confidence)
    composite_method: str | None = None # "weighted_mean" | "pca" | None
    composite_confidence: float | None = None
    best_single_confidence: float


def resolve_proxy(
    target_var: str,
    target_context: str,             # ISO country code
    dataset_registry: DatasetRegistry,
    skg_store: "ScientificKnowledgeGraph",
) -> ProxyChain:
    """
    1. Ищет прямые данные → если есть, confidence = dataset.mapping_confidence
    2. Ищет прокси из seed таблицы → base_correlation
    3. Проверяет контекстную надёжность:
       - Есть ли мета-анализы в SKG по корреляции proxy↔target для данного региона?
       - Если да → context_adjustment из мета-анализа
       - Если нет → context_adjustment = 0.8 (conservative default)
    4. Возвращает ранжированный список с explicit penalties
    """
    ...
```

### 0.14 Legal Knowledge Graph Bridge

Legal Graph производит два типа constraints: **hard** (блокируют вычисление) и **soft** (добавляют S-узлы и штрафы к confidence). Маппинг юридических ограничений в элементы каузального графа формализован через `LegalToDAGMapping`.

```python
# lex/legal_evaluation/types.py

class ConstraintSeverity(str, Enum):
    SOFT = "soft"   # Штраф к confidence, можно продолжать
    HARD = "hard"   # Блокирует вычисление, требует альтернативу или отказ

class LegalConstraint(BaseModel):
    """Юридическое ограничение из Legal Knowledge Graph."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    constraint_id: str                  # "UA-TAX-2010-ART58"
    description: str                    # "Запрет ретроактивного применения налоговых изменений"
    jurisdiction: str                   # "UA"
    legal_source: str                   # "Податковий кодекс України, ст.58"
    severity: ConstraintSeverity
    affects_mechanism: bool             # Меняет ли каузальный механизм (структуру DAG)?
    quantitative_impact: str | None     # "transition_period >= 6 months"


class LegalToDAGMappingType(str, Enum):
    EFFECT_MODIFIER    = "effect_modifier"      # Меняет силу существующего ребра
    MECHANISM_NODE     = "mechanism_node"        # Добавляет новый узел в DAG
    INTERVENTION_REDEF = "intervention_redef"    # Переопределяет do() в target контексте


class LegalToDAGMapping(BaseModel):
    """
    Формализованный маппинг юридического ограничения в элемент каузального графа.
    В MVP: requires_expert_review = True всегда.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    legal_constraint: LegalConstraint
    mapping_type: LegalToDAGMappingType
    affected_edges: list[tuple[str, str]]   # [(cause, effect), ...]
    new_node_name: str | None = None        # Для MECHANISM_NODE
    mechanism_description: str              # "Переходный период 6мес → do(tax) != мгновенный шок"
    confidence_penalty: float = 0.0         # Дополнительный штраф к transport confidence
    requires_expert_review: bool = True     # В MVP всегда True
    rationale: str


# lex/legal_evaluation/constraint_bridge.py

class LegalConstraintBridge:
    """
    Мост между Legal Knowledge Graph и TransportabilityEngine.
    Запрашивает Legal KG для целевой юрисдикции + policy domain,
    и преобразует юридические ограничения в S-узлы и hard constraints.
    """

    def get_constraints_for_policy(
        self,
        jurisdiction: str,              # "UA"
        policy_domain: str,             # "tax_policy"
        policy_spec: dict,              # Описание конкретной политики
    ) -> "LegalConstraintSet":
        """
        Возвращает релевантные юридические ограничения,
        разделённые на hard (блокирующие) и soft (S-узлы).
        """
        ...

    def map_constraints_to_dag(
        self,
        constraints: list[LegalConstraint],
        causal_graph: "CausalGraphModel",
    ) -> list[LegalToDAGMapping]:
        """
        Преобразует юридические ограничения в маппинги на каузальный граф.
        В MVP: все маппинги с requires_expert_review=True.
        """
        ...


class LegalConstraintSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    jurisdiction: str
    policy_domain: str
    hard_constraints: list[LegalConstraint]   # Блокируют → TransportResult.feasible=False
    soft_constraints: list[LegalConstraint]   # → S-узлы
    data_license_constraints: list[LegalConstraint]  # Ограничения на использование данных
    legal_dag_mappings: list[LegalToDAGMapping]
```

### 0.16 Двухшаговый скрининг (по паттерну из spo_extractor.py)

```python
# academic/batch/article_extractor.py

class PolicyArticleExtractor:
    """
    По паттерну GonkaClient из lex/batch/spo_extractor.py:
    - Async с semaphore
    - Retry с exponential backoff
    - Стоимость tracking (screening_cost_usd, extraction_cost_usd)
    - Token counting
    """

    def __init__(
        self,
        screening_model: str = "claude-haiku-4-5",
        extraction_model: str = "claude-sonnet-4-6",
        max_concurrent: int = 5,
        canonizer: VariableCanonizer | None = None,
    ):
        self.screening_model = screening_model
        self.extraction_model = extraction_model
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._canonizer = canonizer or VariableCanonizer()

    async def process_batch(
        self,
        works: list[dict],
        domain_filter: list[str] | None = None,
    ) -> tuple[list[ArticleExtractionResult], ExtractorStats]:
        """
        Обрабатывает батч статей из OpenAlex.
        Returns: (results, stats) — по аналогии с SPO pipeline.
        """
        stats = ExtractorStats()
        results = []

        for work in works:
            should, reason = should_process(work, domain_filter)
            stats.total_seen += 1
            if not should:
                stats.skipped += 1
                continue

            result = await self._process_one(work, stats)
            if result:
                results.append(result)

        return results, stats

    async def _process_one(
        self, work: dict, stats: ExtractorStats,
    ) -> ArticleExtractionResult | None:
        async with self._semaphore:
            # Шаг 1: Скрининг по аннотации (дёшево)
            abstract = self._reconstruct_abstract(work)
            if abstract:
                relevant = await self._screen(abstract, stats)
                if not relevant:
                    stats.screening_rejected += 1
                    return None

            # Шаг 2: Получение полного текста
            full_text = await self._fetch_full_text(work)
            if not full_text:
                stats.no_fulltext += 1
                return None

            # Шаг 3: Извлечение (дорого)
            result = await self._extract(work, full_text, stats)
            if result is None:
                return None

            # Шаг 4: Канонизация имён переменных
            result = self._canonize_variables(result)

            # Шаг 5: инференс базового ContextProfile
            result = result.model_copy(update={
                "source_context": infer_context_from_article(work, result),
            })

            stats.extracted += 1
            return result

    def _canonize_variables(self, result: ArticleExtractionResult) -> ArticleExtractionResult:
        """Канонизирует имена переменных во всех claims и parameters."""
        canonized_claims = []
        for claim in result.causal_claims:
            cause, _ = self._canonizer.canonize(claim.cause_variable)
            effect, _ = self._canonizer.canonize(claim.effect_variable)
            canonized_claims.append(claim.model_copy(update={
                "cause_variable": cause,
                "effect_variable": effect,
            }))

        canonized_params = []
        for param in result.empirical_parameters:
            name, _ = self._canonizer.canonize(param.name)
            canonized_params.append(param.model_copy(update={"name": name}))

        return result.model_copy(update={
            "causal_claims": canonized_claims,
            "empirical_parameters": canonized_params,
        })


@dataclass
class ExtractorStats:
    """Статистика по аналогии с PipelineStats из lex/batch/pipeline.py."""
    total_seen: int = 0
    skipped: int = 0
    screening_rejected: int = 0
    no_fulltext: int = 0
    extracted: int = 0
    extraction_errors: int = 0
    total_screening_cost_usd: float = 0.0
    total_extraction_cost_usd: float = 0.0
    total_tokens_prompt: int = 0
    total_tokens_completion: int = 0
    new_canonical_names: int = 0
    elapsed_seconds: float = 0.0
```

### Подфаза 0d: Quality Validation (0.5–1 неделя)

> Секция 0.17: валидация extraction pipeline на 50 статьях, сквозные проверки.

### 0.17 Definition of Done — Фаза 0

Фаза 0 разделена на четыре подфазы с независимыми DoD. Каждая подфаза может быть оценена и принята отдельно.

#### 0.17a DoD — Подфаза 0a: Extraction Pipeline (2–3 недели)

- [ ] `PolicyArticleExtractor` обрабатывает статьи из OpenAlex с двухшаговым скринингом
- [ ] `ArticleExtractionResult` сериализуется и проходит JSON Schema snapshot
- [ ] `ScientificKnowledgeGraph` строится в DuckDB из набора `ArticleExtractionResult`
- [ ] `source_context` заполняется при экстракции (не в Фазе 12)
- [ ] `VariableCanonizer` — детерминированный, с кэшем в DuckDB, fuzzy match
- [ ] `aggregate_edge_confidence` — 1 RCT > 9 observational (golden test)
- [ ] `priority_filter` — matching по display_name (не по topic ID)
- [ ] Тест: 50 статей по экономической политике → >200 causal claims, >100 parameters
- [ ] Канонизация: "gdp growth" и "economic growth" → один узел `gdp_growth`
- [ ] Rate limiting для OpenAlex API: max 10 req/sec, backoff при 429
- [ ] Кэширование: одна статья обрабатывается ровно один раз (CAS hash по DOI/openalex_id)
- [ ] `academic-skg` optional dependency group изолирована — без неё все остальные фазы работают
- [ ] `ExtractorStats` — стоимость tracking (по аналогии с SPO pipeline)
- [ ] `skg_versions` таблица, retraction handling

#### 0.17b DoD — Подфаза 0b: Dataset Graph + WVS (1.5–2 недели)

- [ ] Data sources (WGI, WVS, WDI) — bulk download + DuckDB таблицы
- [ ] `DatasetRegistry` — DuckDB-backed каталог с seed alignments для WGI/WVS/WDI/IMF
- [ ] `DatasetRegistry.find_datasets_for_variable()` — прямые + прокси результаты
- [ ] Тест: WVS wave-based temporal matching корректно выбирает ближайшую волну

#### 0.17c DoD — Подфаза 0c: Legal Bridge + Proxy Resolver (1–1.5 недели)

- [ ] `ProxyResolver` — контекстно-зависимые штрафы, не фиксированные константы
- [ ] `LegalConstraintBridge` — hard/soft constraints, `LegalToDAGMapping` с `requires_expert_review=True`
- [ ] `ConstraintSeverity.HARD` → блокирует транспортировку (не просто снижает confidence)
- [ ] Golden test: Legal constraint "ретроактивность запрещена" → `MECHANISM_NODE` S-узел

#### 0.17d DoD — Подфаза 0d: Quality Validation (0.5–1 неделя)

- [ ] Интеграционный тест: полный pipeline от OpenAlex query до DuckDB с SKG + Dataset Graph + Legal Bridge
- [ ] Smoke test: >80% извлечённых causal claims имеют каноничные имена переменных
- [ ] Golden test: known article → expected `ArticleExtractionResult` (regression guard)

---

## Фаза 1 — Терминологическая гигиена и ADR

**Длительность:** 3–5 дней | **Риск:** LOW
**Предусловия:** нет

Переименование `scm.py` → `synthetic_control.py` (уже существует как `scm.py` в `foundry/methods/catalog/causal/`). Shim для обратной совместимости. ADR-0025, ADR-0026.

### 1.1 Действия

1. **Переименование:** `SyntheticControlMethod` уже зарегистрирован в `_registry_boot.py` как `causal.inference.synthetic_control@1.0.0`. Файл `scm.py` переименовывается в `synthetic_control.py`. В `scm.py` остаётся `__all__ = []; from .synthetic_control import *` (deprecation shim).

2. **ADR-0025:** SCM = Structural Causal Model. Abadie method = Synthetic Control Method.

3. **ADR-0026:** NOTEARS excluded — нестабилен при >20 переменных, continuous optimization не гарантирует DAG.

### 1.2 Definition of Done

- [ ] `synthetic_control.py` — основной файл, `scm.py` — shim
- [ ] `_registry_boot.py` обновлён
- [ ] ADR-0025, ADR-0026 в `docs/adr/`
- [ ] Все существующие тесты проходят

---

## Фаза 2 — DoWhy Identify/Estimate как Foundry method

**Длительность:** 2–3 недели | **Риск:** MEDIUM
**Предусловия:** Фаза 1

### 2.1 Foundry Method: DoWhyIdentifyEstimate

```python
# foundry/methods/catalog/causal/dowhy_identify_estimate.py

@foundry_method(
    namespace="causal.inference",
    version="1.0.0",
    tags={"causal", "dowhy", "identification", "estimation"},
)
class DoWhyIdentifyEstimate:
    """
    DoWhy identify + estimate в одном шаге.
    Backend: NUMPY (DoWhy не совместим с JAX).
    """
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="dowhy_identify_estimate",
        namespace="causal.inference",
        version="1.0.0",
        input_slots=(
            SlotSpec(name="data", slot_type=SlotType.MATRIX, unit=None, shape=("N", "K")),
        ),
        output_slots=(
            SlotSpec(name="report", slot_type=SlotType.SCALAR, unit=None, shape=()),
        ),
        parameters=(
            ParameterSpec(name="treatment", default=None, is_static=True),
            ParameterSpec(name="outcome", default=None, is_static=True),
            ParameterSpec(name="column_names", default=None, is_static=True),  # list[str], K имён
            ParameterSpec(name="graph_gml", default=None, is_static=True),
            ParameterSpec(name="estimand_type", default="nonparametric-ate", is_static=True),
            ParameterSpec(name="method_name", default="backdoor.linear_regression", is_static=True),
        ),
        backend=ComputeBackend.NUMPY,
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="DoWhy causal identification and estimation",
        tags=frozenset({"causal", "dowhy", "ate"}),
        assumptions=("Causal graph correctly specified", "Backdoor criterion satisfied"),
    )
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC

    # Маппинг DoWhy method_name → CausalMethod enum
    _METHOD_MAP: ClassVar[dict[str, "CausalMethod"]] = {
        "backdoor.linear_regression": CausalMethod.DOWHY_BACKDOOR,
        "backdoor.propensity_score_matching": CausalMethod.DOWHY_BACKDOOR,
        "backdoor.propensity_score_weighting": CausalMethod.DOWHY_BACKDOOR,
        "backdoor.econml.dml": CausalMethod.DOWHY_BACKDOOR,
        "iv.instrumental_variable": CausalMethod.DOWHY_IV,
        "frontdoor.two_stage_regression": CausalMethod.DOWHY_FRONTDOOR,
    }

    @staticmethod
    def pure_step(state: dict[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        import dowhy
        import pandas as pd

        # DoWhy требует DataFrame с именами колонок, не голый ndarray.
        # state["data"] — ndarray (N,K) из SlotSpec; column_names — из params.
        raw_data = state["data"]
        column_names = params.get("column_names")
        if column_names is None:
            raise ValueError(
                "column_names parameter required: DoWhy CausalModel expects "
                "a DataFrame with named columns, not a raw matrix"
            )
        df = pd.DataFrame(raw_data, columns=column_names)

        model = dowhy.CausalModel(
            data=df,
            treatment=params["treatment"],
            outcome=params["outcome"],
            graph=params.get("graph_gml"),
        )
        identified = model.identify_effect(proceed_when_unidentifiable=False)

        method_name = params.get("method_name", "backdoor.linear_regression")
        estimate = model.estimate_effect(identified, method_name=method_name)

        # Детерминированный маппинг method_name → CausalMethod
        causal_method = DoWhyIdentifyEstimate._METHOD_MAP.get(
            method_name, CausalMethod.DOWHY_BACKDOOR
        )

        report = CausalEffectReport(
            method=causal_method,
            status=EstimationStatus.SUCCESS,
            identified_estimand=str(identified),
            point_estimate=float(estimate.value),
            standard_error=float(estimate.get_standard_error()) if hasattr(estimate, "get_standard_error") else None,
            confidence_interval=(
                float(estimate.get_confidence_intervals()[0]),
                float(estimate.get_confidence_intervals()[1]),
            ) if hasattr(estimate, "get_confidence_intervals") else None,
            method_params=dict(params),
        )
        return {"report": report}
```

### 2.2 Расширение CausalEffectReport

Добавляются поля для DoWhy-специфичной информации:

```python
# Добавляется в ir/analytics/causal.py

class CausalMethod(str, Enum):
    # Существующие
    SYNTHETIC_CONTROL = "synthetic_control"
    DIFFERENCE_IN_DIFFERENCES = "difference_in_differences"
    # ...
    # Новые (Фаза 2)
    DOWHY_BACKDOOR = "dowhy_backdoor"
    DOWHY_IV = "dowhy_iv"
    DOWHY_FRONTDOOR = "dowhy_frontdoor"

# CausalEffectReport получает опциональные поля:
#   identified_estimand: str | None = None
#   estimand_type: str | None = None    # "nonparametric-ate" etc.
#   graph_ref: str | None = None        # CAS ref на CausalGraphModel
#   transport_result: "TransportabilityResult | None" = None  # Фаза 12
```

### 2.3 GraphCausalData — входной тип для graph-based methods

```python
# foundry/methods/catalog/causal/protocols.py (дополнение)

class GraphCausalData(BaseModel):
    """Данные для graph-based каузального вывода."""
    model_config = ConfigDict(extra="forbid")

    data: np.ndarray                # (N, K) матрица наблюдений
    column_names: list[str]         # K имён переменных
    treatment: str                  # Имя treatment переменной
    outcome: str                    # Имя outcome переменной
    graph_gml: str | None = None    # GML строка графа (для DoWhy)
    graph_ref: str | None = None    # CAS ref на CausalGraphModel
    covariates: list[str] = []      # Имена ковариат

    @model_validator(mode="after")
    def _validate(self) -> "GraphCausalData":
        if self.data.shape[1] != len(self.column_names):
            raise ValueError("data columns != len(column_names)")
        if self.treatment not in self.column_names:
            raise ValueError(f"treatment '{self.treatment}' not in column_names")
        if self.outcome not in self.column_names:
            raise ValueError(f"outcome '{self.outcome}' not in column_names")
        return self
```

### 2.4 Definition of Done — Фаза 2

- [ ] `DoWhyIdentifyEstimate` зарегистрирован в `MethodRegistry` как `causal.inference.dowhy_identify_estimate@1.0.0`
- [ ] `GraphCausalData` — входной тип для graph-based методов, `model_validator` проверяет консистентность
- [ ] `CausalMethod` расширен: `DOWHY_BACKDOOR`, `DOWHY_IV`, `DOWHY_FRONTDOOR`
- [ ] `CausalEffectReport` расширен: `identified_estimand`, `graph_ref`
- [ ] Тест: linear confounding scenario → ATE ±0.1 от ground truth
- [ ] JSON Schema snapshot для расширенного `CausalEffectReport`
- [ ] ADR-0027 в `docs/adr/`

---

## Фаза 3 — Refutation pipeline

**Длительность:** 1.5–2 недели | **Риск:** LOW
**Предусловия:** Фаза 2

### 3.1 Foundry Method: DoWhyRefute

```python
@foundry_method(
    namespace="causal.refutation",
    version="1.0.0",
    tags={"causal", "refutation", "robustness"},
)
class DoWhyRefute:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    @staticmethod
    def pure_step(state: dict[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        """
        Запускает набор refutation тестов:
        - placebo_treatment_refuter
        - random_common_cause
        - data_subset_refuter
        - bootstrap_refuter (если seed задан)

        Каждый тест → RefutationResult.
        """
        ...
```

### 3.2 IR: RefutationResult

```python
class RefutationTestType(str, Enum):
    PLACEBO_TREATMENT = "placebo_treatment"
    RANDOM_COMMON_CAUSE = "random_common_cause"
    DATA_SUBSET = "data_subset"
    BOOTSTRAP = "bootstrap"
    UNOBSERVED_COMMON_CAUSE = "unobserved_common_cause"

class RefutationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    test_type: RefutationTestType
    original_estimate: float
    refuted_estimate: float
    p_value: float | None = None
    passed: bool                    # True если estimate robust
    effect_ratio: float             # refuted/original — должен быть ~1.0 для robust
    details: dict[str, Any] = {}
```

### 3.3 Definition of Done — Фаза 3

- [ ] `DoWhyRefute` — 4 refutation теста, seed из `random_seed`
- [ ] `RefutationResult` — JSON Schema snapshot
- [ ] Тест: synthetic confounded data → `random_common_cause` не отвергает
- [ ] ADR-0028: Refutation mandatory для observational estimates

---

## Фаза 4 — Sensitivity metrics

**Длительность:** 2–2.5 недели | **Риск:** MEDIUM
**Предусловия:** Фаза 3

### 4.1 IR: SensitivityResult

```python
class SensitivityResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"

    # E-value (Ding & VanderWeele 2016)
    e_value: float | None = None
    e_value_ci_lower: float | None = None
    conversion_method: str | None = None  # "ate_to_rr_log" | "ate_to_rr_approx"

    # Robustness Value (Cinelli & Hazlett 2020)
    robustness_value: float | None = None
    partial_r2_treatment: float | None = None

    # Rosenbaum Γ (sensitivity to hidden bias)
    rosenbaum_gamma: float | None = None
    rosenbaum_p_value: float | None = None

    # Interpretation
    interpretation: str = ""        # Human-readable summary
    is_robust: bool = False         # Combined assessment

    @model_validator(mode="after")
    def _validate(self) -> "SensitivityResult":
        if self.e_value is not None and self.e_value < 1.0:
            raise ValueError("E-value must be >= 1.0")
        return self
```

### 4.2 Definition of Done — Фаза 4

- [ ] `SensitivityMetrics` Foundry method — E-value, Robustness Value, Rosenbaum Γ
- [ ] `SensitivityResult` — JSON Schema snapshot
- [ ] E-value `conversion_method` записывается для auditability (ADR-0029)
- [ ] Golden test: known confounded scenario → E-value matches hand calculation
- [ ] Интеграция в DecisionPacket секция 3.2

---

## Фаза 5 — CausalGraphModel как IR-артефакт

**Длительность:** 2 недели | **Риск:** MEDIUM
**Предусловия:** Фаза 2
`CausalEdge.compute_combined_confidence()` исправлена.

### 5.1 IR: CausalGraphModel

```python
# ir/analytics/causal_graph.py

class GraphType(str, Enum):
    DAG   = "dag"
    CPDAG = "cpdag"
    PAG   = "pag"

class EdgeMark(str, Enum):
    TAIL   = "tail"     # ─
    ARROW  = "arrow"    # →
    CIRCLE = "circle"   # ○ (PAG)

class EdgeSource(str, Enum):
    DATA        = "data"
    LITERATURE  = "literature"
    LLM_PRIOR   = "llm_prior"
    EXPERT      = "expert"
    SIMULATION  = "simulation"

class CausalEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    src: str
    dst: str
    mark_src: EdgeMark = EdgeMark.TAIL
    mark_dst: EdgeMark = EdgeMark.ARROW
    lag: int | None = None

    # Источник и доверие
    sources: list[EdgeSource] = []
    data_confidence: float | None = None
    literature_confidence: float | None = None
    llm_confidence: float | None = None
    expert_confidence: float | None = None
    combined_confidence: float | None = None

    # Закон L
    unsupported_by_evidence: bool = False

    # Provenance
    evidence_refs: list[str] = []     # OpenAlex IDs или artifact_ids
    p_value: float | None = None

    # Метаданные (cycle resolution, orientation, etc.)
    metadata: dict[str, Any] = {}

    def compute_combined_confidence(self) -> float:
        """
        Формула 1 - Π(1 - conf_i)^w_i  (weighted Noisy-OR через экспоненту).

        Веса в экспоненте → (1 - conf_i)^w_i:
        - Идеальная статья (conf=1.0, w=0.5): 1-(1-1)^0.5 = 1.0
        - Статья (conf=0.8, w=0.5) + данные (conf=0.7, w=0.4):
          1 - (1-0.8)^0.5 × (1-0.7)^0.4 = 1 - 0.447 × 0.618 = 0.724
        - llm_prior (w=0.05) по-прежнему почти не влияет

        Свойства:
        - Потолок НЕ ограничен весами (идеальный источник → conf=1.0)
        - Каждый новый источник снижает остаточную неопределенность
        - Вес отражает степень доверия к типу источника
        """
        SOURCE_WEIGHTS = {
            EdgeSource.LITERATURE: 0.5,
            EdgeSource.DATA: 0.4,
            EdgeSource.EXPERT: 0.1,
            EdgeSource.LLM_PRIOR: 0.05,
            EdgeSource.SIMULATION: 0.1,
        }

        product_of_failures = 1.0
        for source in self.sources:
            conf_attr = f"{source.value}_confidence"
            conf = getattr(self, conf_attr, None) or 0.0
            w = SOURCE_WEIGHTS.get(source, 0.05)
            # (1 - conf)^w, NOT (1 - conf * w)
            product_of_failures *= (1.0 - conf) ** w

        return 1.0 - product_of_failures

class CausalGraphModel(BaseModel):
    """DAG / CPDAG / PAG как IR-артефакт."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    graph_type: GraphType
    nodes: list[str]
    edges: list[CausalEdge]
    discovery_method: str = ""
    skg_version_id: int | None = None  # для воспроизводимости

    @model_validator(mode="after")
    def _validate_nodes_in_edges(self) -> "CausalGraphModel":
        node_set = set(self.nodes)
        for edge in self.edges:
            if edge.src not in node_set:
                raise ValueError(f"Edge src '{edge.src}' not in nodes")
            if edge.dst not in node_set:
                raise ValueError(f"Edge dst '{edge.dst}' not in nodes")
        return self

    def to_gml(self) -> str:
        """Конвертация в GML для DoWhy."""
        ...

    def to_rustworkx(self) -> tuple["rx.PyDiGraph", dict[str, int]]:
        """Конвертация в rustworkx PyDiGraph для in-memory алгоритмов."""
        import rustworkx as rx
        G = rx.PyDiGraph()
        node_map: dict[str, int] = {}
        for node in self.nodes:
            idx = G.add_node(node)
            node_map[node] = idx
        for e in self.edges:
            G.add_edge(
                node_map[e.src], node_map[e.dst],
                e.model_dump(exclude={"src", "dst"}),
            )
        return G, node_map

    def to_networkx(self):
        """Legacy: NetworkX DiGraph. Предпочитать to_rustworkx() или to_kuzu()."""
        import networkx as nx
        G = nx.DiGraph()
        G.add_nodes_from(self.nodes)
        for e in self.edges:
            G.add_edge(e.src, e.dst, **e.model_dump(exclude={"src", "dst"}))
        return G

    def to_kuzu(self, kuzu_conn) -> None:
        """Материализация в KuzuDB для Cypher-запросов.
        По паттерну fabric/world/materialize/kuzu.py:
        1. Убеждаемся что DDL применён (CausalVar, CausalEdge tables)
        2. INSERT OR REPLACE для узлов и рёбер
        Для bulk materiализации использовать materialize_causal_kuzu.py (CSV COPY).
        """
        for node in self.nodes:
            kuzu_conn.execute(
                "MERGE (v:CausalVar {name: $name})",
                {"name": node},
            )
        for e in self.edges:
            kuzu_conn.execute(
                "MATCH (s:CausalVar {name: $src}), (d:CausalVar {name: $dst}) "
                "MERGE (s)-[r:CausalEdge]->(d) "
                "SET r.mark_src = $mark_src, r.mark_dst = $mark_dst, "
                "r.combined_confidence = $conf, r.lag = $lag",
                {
                    "src": e.src, "dst": e.dst,
                    "mark_src": e.mark_src.value,
                    "mark_dst": e.mark_dst.value,
                    "conf": e.combined_confidence or 0.0,
                    "lag": e.lag or 0,
                },
            )


# Persistence
def persist_causal_graph_model(store, graph: CausalGraphModel, inputs=None) -> dict:
    return put_json_artifact(
        store,
        graph.model_dump(mode="json"),
        kind="ir.causal_graph_model",
        schema_name="ir.causal_graph_model",
        schema_version="1.0",
        inputs=inputs or [],
    )
```

### 5.2 Definition of Done — Фаза 5

- [ ] `CausalGraphModel` — DAG/CPDAG/PAG через EdgeMark
- [ ] `CausalEdge.compute_combined_confidence()` — тест: два источника > один
- [ ] `to_gml()` корректен для DoWhy
- [ ] `to_kuzu()` материализация в KuzuDB (паттерн `world/materialize/kuzu.py`)
- [ ] `to_rustworkx()` для in-memory графовых алгоритмов (primary)
- [ ] `to_networkx()` legacy shim для discovery библиотек (causal-learn/tigramite требуют NetworkX)
- [ ] JSON Schema snapshot
- [ ] ADR-0030

---

## Фаза 6 — Causal discovery: PCMCI/Tigramite

**Длительность:** 2.5–3 недели | **Риск:** MEDIUM-HIGH
**Предусловия:** Фаза 5

### 6.1 Foundry Method: PCMCIDiscovery

```python
@foundry_method(
    namespace="causal.discovery",
    version="1.0.0",
    tags={"causal", "discovery", "time-series", "pcmci"},
)
class PCMCIDiscovery:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    @staticmethod
    def pure_step(state: dict[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        """
        PCMCI+ через Tigramite.
        Параметры: max_lag, significance_level, cond_ind_test (par_corr/gpdc/cmi).
        Block bootstrap для stability.
        Timeout: max 10 минут (Tigramite медленный на >30 переменных).
        """
        ...
```

### 6.2 IR: CausalDiscoveryReport

```python
class CausalDiscoveryReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    method: str                      # "pcmci+" | "pc" | "fci" | "ges"
    graph: CausalGraphModel
    bootstrap_stability: dict[str, float] = {}  # edge_key → stability [0,1]
    n_bootstrap: int = 0
    significance_level: float = 0.05
    computation_time_seconds: float = 0.0
    warnings: list[str] = []
```

### 6.3 Definition of Done — Фаза 6

- [ ] `PCMCIDiscovery` — timeout 10 min, default `par_corr`, `max_lag=5`
- [ ] `CausalDiscoveryReport` — JSON Schema snapshot
- [ ] Block bootstrap stability ≥100 runs для production
- [ ] Тест: VAR(1) synthetic data → восстанавливает ground truth DAG
- [ ] ADR-0031: Block bootstrap для time-series stability
- [ ] (Опционально) JAX-vectorized ParCorr для >30 переменных — см. Приложение B.7

---

## Фаза 7 — Causal discovery: constraint/score-based

**Длительность:** 2–2.5 недели | **Риск:** MEDIUM
**Предусловия:** Фаза 5, Фаза 6 (shared infra)

### 7.1 Foundry Methods

- `PCDiscovery` — PC algorithm через causal-learn
- `FCIDiscovery` — FCI algorithm (PAG output)
- `GESDiscovery` — Greedy Equivalence Search (score-based)

Все следуют тому же паттерну: `pure_step` → `CausalDiscoveryReport`.

### 7.2 PAG → Идентификация: консервативная политика (ADR-0085)

Когда discovery возвращает PAG (класс эквивалентности DAG), идентификация каузального запроса может быть возможна в одних DAG и невозможна в других.

**Политика для MVP: CONSERVATIVE.**

Запрос считается identifiable iff identifiable **во всех** DAG ∈ PAG. Это самый безопасный вариант: ложные `TRANSPORTABLE` исключены.

```python
class PAGIdentificationPolicy(str, Enum):
    CONSERVATIVE = "conservative"   # id iff id во всех DAG ∈ PAG (MVP)
    OPTIMISTIC   = "optimistic"     # id iff id в хотя бы одном DAG
    PROBABILISTIC = "probabilistic" # id_confidence = доля DAG, где id успешен

# CausalGraphModel получает:
#   pag_identification_policy: PAGIdentificationPolicy = PAGIdentificationPolicy.CONSERVATIVE
#   id_confidence_under_pag: float | None = None  # заполняется при policy=PROBABILISTIC
```

**Трёхуровневая стратегия:**

1. **CONSERVATIVE (MVP):** если PAG содержит хотя бы один DAG где backdoor criterion не выполнен → `NON_TRANSPORTABLE`. Реализация: перечисление DAG из PAG через `pag_to_dags()` (causal-learn), проверка backdoor на каждом. Для PAG с >100 DAG — fallback на PROBABILISTIC с random sample.
2. **PROBABILISTIC (Phase 14):** `id_confidence_under_pag = N_id / N_total`, где `N_id` — число DAG с успешной идентификацией, `N_total` — общее или sample. Интегрируется с `CausalModelEnsemble`.
3. **OPTIMISTIC (backlog):** не рекомендуется для production; полезен для exploration/what-if.

**Связь с теоретической работой (Sheaf Foundations):** PAG uncertainty не рассматривается в шифовой теории напрямую. Однако different DAG ∈ PAG порождают разные идентификационные формулы — это L1-level неопределённость (Section 1.5 теории), ортогональная к L2 (estimation) и L3 (alignment). Рекомендуется хранить PAG-level uncertainty как отдельный компонент в `TransportabilityResult`, не смешивая с confidence penalties.

### 7.3 Definition of Done — Фаза 7

- [ ] PC, FCI, GES зарегистрированы в `MethodRegistry`
- [ ] FCI → `CausalGraphModel` с `graph_type=PAG`, EdgeMark.CIRCLE
- [ ] PAG хранится рядом с resolved DAG (не теряем информацию)
- [ ] Тест: FCI с latent confounder → PAG корректен
- [ ] `PAGIdentificationPolicy.CONSERVATIVE` — default для всех PAG-based запросов
- [ ] ADR-0085

---

## Фаза 8 — Governance gates (часть A)

**Длительность:** 1–1.5 недели | **Риск:** LOW
**Предусловия:** Фаза 4, Фаза 5 (LiteratureGate требует Фазу 0)

> Фаза 8 разделена на 8A и 8B:
> - **8A (здесь):** `LiteratureGatePass` (Закон L) + `HumanReviewPass` — зависят только от Фаз 0/5
> - **8B (конец Фазы 12):** `TransportabilityRequiredPass` (Закон T) — внедряется после стабилизации ResolutionLoop

### 8.1 LiteratureGatePass (Закон L)

По паттерну из `confidence_pass.py` и `quality_gate_pass.py`:

```python
# scientist/governance/passes/literature_gate_pass.py

from polisyos.core.governance import ValidatorPass, ComplianceIssue, IssueSeverity

class LiteratureGatePass(ValidatorPass):
    """
    Закон L: рёбра без поддержки литературы в STRICT profile → BLOCKER.
    В MVP → WARNING. В FAST → skip.

    Паттерн: по аналогии с ConfidencePass (estimated_cost_ms=50).
    """

    @property
    def pass_id(self) -> str:
        return "literature_gate"

    @property
    def estimated_cost_ms(self) -> int:
        return 30  # Только проверка флагов на рёбрах

    def validate(self, ctx) -> list[ComplianceIssue]:
        profile_level = ctx.profile.level  # "FAST" | "MVP" | "STRICT"

        if profile_level == "FAST":
            return []

        graph_ref = ctx.state.get("causal_graph_ref")
        if not graph_ref:
            return []

        graph = load_causal_graph_model(ctx.state.get("_store"), graph_ref)

        issues = []
        for edge in graph.edges:
            if edge.unsupported_by_evidence:
                severity = (
                    IssueSeverity.BLOCKER if profile_level == "STRICT"
                    else IssueSeverity.WARNING
                )
                issues.append(ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["causal_graph", "edges", f"{edge.src}→{edge.dst}"],
                    message=(
                        f"Edge {edge.src}→{edge.dst} has sources={[s.value for s in edge.sources]} "
                        f"with no literature or data support"
                    ),
                    severity=severity,
                    code="LITERATURE_GATE_UNSUPPORTED_EDGE",
                    suggestion="Add peer-reviewed evidence or remove edge from graph",
                ))

        return issues
```

### 8.2 TransportabilityRequiredPass (Закон T) → **см. Подфазу 8B ниже**

> Этот pass внедряется после стабилизации `TransportabilityResolutionLoop` (Фаза 12).
> Полное описание — в подфазе 8B (секция 12.7) сразу после Definition of Done 8A.

### 8.3 SUTVA Assumption Check (ADR-0086)

**Проблема:** вся каузальная система предполагает SUTVA (Stable Unit Treatment Value Assumption) — эффект на одну единицу не зависит от treatment других единиц. Для policy interventions это часто нарушается:
- Налоговые реформы: общеэкономические spillover effects
- Трудовой рынок: displacement effects (программа занятости в регионе A перетягивает работников из B)
- Торговая политика: по определению влияет на третьи стороны
- Монетарная политика: general equilibrium effects

**Решение:** явный governance flag + pass.

```python
# ir/analytics/causal.py — расширение CausalEffectReport
#   sutva_assumed: bool = True              # по умолчанию SUTVA предполагается
#   sutva_violation_risk: str | None = None  # "high" | "medium" | "low" | None

# ir/analytics/transportability.py — расширение TransportabilityResult
#   sutva_assumed: bool = True

# scientist/governance/passes/sutva_check_pass.py

class SutvaCheckPass(ValidatorPass):
    """
    Проверяет тип intervention: market-wide policies → WARNING.
    Не блокирует — SUTVA нарушение неверифицируемо автоматически.
    """

    MARKET_WIDE_KEYWORDS = {
        "tax_rate", "monetary_policy", "interest_rate", "trade_policy",
        "exchange_rate", "minimum_wage", "fiscal_policy", "subsidy",
        "tariff", "regulation", "licensing", "antitrust",
    }

    @property
    def pass_id(self) -> str:
        return "sutva_check"

    @property
    def estimated_cost_ms(self) -> int:
        return 20

    def validate(self, ctx) -> list[ComplianceIssue]:
        treatment = ctx.state.get("query_treatment", "")
        if any(kw in treatment.lower() for kw in self.MARKET_WIDE_KEYWORDS):
            return [ComplianceIssue(
                pass_id=self.pass_id,
                path=["causal_query", "treatment"],
                message=(
                    f"Treatment '{treatment}' appears to be a market-wide policy. "
                    f"SUTVA may be violated (spillover/general equilibrium effects). "
                    f"Effect estimates assume no interference between units."
                ),
                severity=IssueSeverity.WARNING,
                code="SUTVA_VIOLATION_RISK",
                suggestion="Consider general equilibrium effects; ABM bridge (Phase 13) may capture some spillovers",
            )]
        return []
```

### 8.4 Human-in-the-loop для STRICT governance

```python
class HumanReviewRequiredPass(ValidatorPass):
    """
    В STRICT profile: если есть unsupported_by_evidence рёбра
    или low-confidence параметры — создаёт review request.
    НЕ блокирует автоматически — создаёт артефакт HumanReviewRequest.
    """

    @property
    def pass_id(self) -> str:
        return "human_review_required"

    @property
    def estimated_cost_ms(self) -> int:
        return 50

    def validate(self, ctx) -> list[ComplianceIssue]:
        if ctx.profile.level != "STRICT":
            return []

        review_items = self._collect_review_items(ctx)
        if not review_items:
            return []

        # Создать артефакт для human review
        review_request = HumanReviewRequest(
            items=review_items,
            created_by="governance.human_review_required",
            deadline_hours=72,
        )
        # Persist (не блокируем — INFO)
        return [ComplianceIssue(
            pass_id=self.pass_id,
            path=["human_review"],
            message=f"Human review requested for {len(review_items)} items",
            severity=IssueSeverity.INFO,
            code="HUMAN_REVIEW_REQUESTED",
        )]
```

### 8.5 Definition of Done — Фаза 8A

- [ ] `LiteratureGatePass` — FAST: skip, MVP: WARNING, STRICT: BLOCKER
- [ ] `HumanReviewRequiredPass` — создаёт review request для STRICT
- [ ] `SutvaCheckPass` — WARNING для market-wide policies (ADR-0086)
- [ ] `sutva_assumed: bool` + `sutva_violation_risk` поля в CausalEffectReport / TransportabilityResult
- [ ] Все passes (8A) зарегистрированы в `ValidationPipeline`
- [ ] ordered by `estimated_cost_ms` (cheapest first)
- [ ] Тест: graph с `unsupported_by_evidence` edge → STRICT блокирует
- [ ] Тест: treatment=`tax_rate` → `SUTVA_VIOLATION_RISK` WARNING
- [ ] `TransportabilityRequiredPass` → реализуется в Фазе 12 (подфаза 8B)

---

### 12.7 Подфаза 8B: TransportabilityRequiredPass (Закон T)

> Перенесён из Фазы 8 для устранения хронологического парадокса.

```python
class TransportabilityRequiredPass(ValidatorPass):
    """
    Закон T: CausalEffectReport из внешнего источника
    без transport_result → WARNING/BLOCKER.

    Реализуется в конце Фазы 12 (не в Фазе 8), т.к.
    зависит от стабильно работающего TransportabilityResolutionLoop.
    """

    @property
    def pass_id(self) -> str:
        return "transportability_required"

    @property
    def estimated_cost_ms(self) -> int:
        return 20

    def validate(self, ctx) -> list[ComplianceIssue]:
        profile_level = ctx.profile.level
        if profile_level == "FAST":
            return []

        reports = ctx.state.get("causal_effect_reports", [])
        issues = []
        for report_ref in reports:
            report = load_causal_effect_report(ctx.state["_store"], report_ref)
            if (
                report.method_params.get("source_type") == "external_literature"
                and not report.method_params.get("transport_result")
            ):
                severity = (
                    IssueSeverity.BLOCKER if profile_level == "STRICT"
                    else IssueSeverity.WARNING
                )
                issues.append(ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["causal_effect_reports", report_ref],
                    message="External CausalEffectReport lacks transportability check",
                    severity=severity,
                    code="TRANSPORT_REQUIRED_MISSING",
                    suggestion="Run transportability check before using this estimate",
                ))
        return issues
```

---

## Фаза 9 — Literature+LLM prior и graph reconciliation

**Длительность:** 3–4 недели
**Предусловия:** Фаза 0, Фаза 5, Фаза 6 или 7
**Риск:** MEDIUM
Только LITERATURE_FIRST стратегия в MVP (остальные — backlog).

### 9.1 Концептуальная схема

```
SKG.query_prior_for_variables(vars) → LiteratureCausalPrior  → Главный источник
LLM(context_description, variables) → LLMStructuralHints     → Интерпретатор

reconcile(LiteratureCausalPrior, LLMStructuralHints, data_graph) → final_graph

Приоритет при конфликте: data > literature > expert > llm_prior
```

### 9.2 IR: LiteratureCausalPrior

```python
# ir/analytics/literature.py (дополнение)

class LiteratureEdgePrior(BaseModel):
    """Ребро prior-графа, обоснованное научной литературой."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    src: str
    dst: str
    direction: CausalDirection
    n_articles: int
    evidence_strength: EvidenceStrength  # Сильнейший тип
    confidence: float                    # Из aggregate_edge_confidence()
    openalex_ids: list[str]
    scope_conditions: list[str] = []

    def to_causal_edge(self) -> CausalEdge:
        return CausalEdge(
            src=self.src,
            dst=self.dst,
            sources=[EdgeSource.LITERATURE],
            literature_confidence=self.confidence,
            evidence_refs=self.openalex_ids,
            unsupported_by_evidence=False,
        )

class LiteratureCausalPrior(BaseModel):
    """Каузальный prior, извлечённый из научной литературы."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    query_variables: list[str]
    query_domain: str | None = None
    edges: list[LiteratureEdgePrior]
    total_articles_queried: int
    min_confidence_threshold: float
    skg_snapshot_ref: str
    skg_version_id: int              # для воспроизводимости
    timestamp: str

    def to_causal_graph_model(self) -> CausalGraphModel:
        nodes = list({e.src for e in self.edges} | {e.dst for e in self.edges})
        edges = [e.to_causal_edge() for e in self.edges]
        return CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=nodes,
            edges=edges,
            discovery_method="literature_prior",
            skg_version_id=self.skg_version_id,
        )
```

### 9.3 Reconciliation: LITERATURE_FIRST (единственная стратегия в MVP)

Убраны DATA_FIRST, CONSENSUS, UNION из MVP. Это over-engineering — одна стратегия покрывает основной use case. Остальные — в backlog после валидации MVP.

```python
# foundry/methods/catalog/causal/graph_reconciliation.py

@foundry_method(
    namespace="causal.prior",
    version="1.0.0",
    tags={"causal", "reconciliation", "prior"},
)
class ReconcileCausalGraph:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.DETERMINISTIC

    @staticmethod
    def pure_step(state: dict[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        """
        LITERATURE_FIRST стратегия (единственная в MVP):

        1. Начать с literature_prior как базой
        2. Для каждого ребра из data_graph:
           - Совпадает с literature → boost via compute_combined_confidence()
           - Противоречит direction → data wins, literature confidence снижен
           - Только в data → добавить с sources=[DATA]
        3. Для каждого ребра из llm_hints:
           - Уже есть в literature или data → добавить LLM_PRIOR как доп. источник
           - Только в LLM → добавить с unsupported_by_evidence=True
        4. Отфильтровать рёбра с combined_confidence < threshold
        5. Проверить ацикличность; разрешить циклы:
           ребро с наименьшим combined_confidence удаляется
        """

        threshold = params.get("min_edge_confidence", 0.25)

        lit_graph = CausalGraphModel.model_validate(state.get("literature_prior_graph"))
        data_graph = (
            CausalGraphModel.model_validate(state["data_graph"])
            if state.get("data_graph") else None
        )
        llm_hints = state.get("llm_hints", [])

        reconciled: dict[tuple[str, str], CausalEdge] = {}

        # Шаг 1: Literature base
        for edge in lit_graph.edges:
            reconciled[(edge.src, edge.dst)] = edge

        # Шаг 2: Data integration
        if data_graph:
            for d_edge in data_graph.edges:
                key = (d_edge.src, d_edge.dst)
                reverse_key = (d_edge.dst, d_edge.src)

                if key in reconciled:
                    # Boost: оба источника согласны
                    existing = reconciled[key]
                    merged = existing.model_copy(update={
                        "sources": list(set(existing.sources + [EdgeSource.DATA])),
                        "data_confidence": d_edge.data_confidence,
                    })
                    reconciled[key] = merged.model_copy(update={
                        "combined_confidence": merged.compute_combined_confidence(),
                    })

                elif reverse_key in reconciled:
                    # Конфликт direction: data wins
                    existing = reconciled.pop(reverse_key)
                    reconciled[key] = d_edge.model_copy(update={
                        "sources": [EdgeSource.DATA],
                        "literature_confidence": existing.literature_confidence * 0.3,
                    })

                else:
                    # Только в data
                    reconciled[key] = d_edge.model_copy(update={
                        "sources": [EdgeSource.DATA],
                    })

        # Шаг 3: LLM hints
        for hint in llm_hints:
            key = (hint["src"], hint["dst"])
            if key in reconciled:
                existing = reconciled[key]
                merged = existing.model_copy(update={
                    "sources": list(set(existing.sources + [EdgeSource.LLM_PRIOR])),
                    "llm_confidence": hint.get("confidence", 0.3),
                })
                reconciled[key] = merged.model_copy(update={
                    "combined_confidence": merged.compute_combined_confidence(),
                })
            else:
                reconciled[key] = CausalEdge(
                    src=hint["src"],
                    dst=hint["dst"],
                    sources=[EdgeSource.LLM_PRIOR],
                    llm_confidence=hint.get("confidence", 0.3),
                    unsupported_by_evidence=True,
                )

        # Шаг 4: Фильтрация
        final_edges = []
        for edge in reconciled.values():
            edge = edge.model_copy(update={
                "combined_confidence": edge.compute_combined_confidence(),
            })
            if edge.combined_confidence >= threshold:
                final_edges.append(edge)

        # Шаг 5: Ацикличность (time-aware — пропускает для PCMCI)
        data_graph_tags = set(state.get("data_graph_method_tags", []))
        final_edges = _break_cycles(final_edges, source_method_tags=data_graph_tags)

        nodes = list({e.src for e in final_edges} | {e.dst for e in final_edges})
        result = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=nodes,
            edges=final_edges,
            discovery_method="reconciled",
        )

        return {"reconciled_graph": result.model_dump(mode="json")}


MAX_LAG_DEPTH = 2          # Жёсткий лимит: максимальная глубина лага
MAX_LAGGED_EDGES = 10      # Жёсткий лимит: максимальное число лагированных рёбер за один вызов
MAX_CYCLES_TO_RESOLVE = 8  # Safety valve: если циклов больше — warning + остановка


def _break_cycles(
    edges: list[CausalEdge],
    *,
    source_method_tags: set[str] | None = None,
    max_lag_depth: int = MAX_LAG_DEPTH,
    max_lagged_edges: int = MAX_LAGGED_EDGES,
    max_cycles: int = MAX_CYCLES_TO_RESOLVE,
) -> list[CausalEdge]:
    """
    Конвертирует циклы в лагированную структуру вместо удаления.

    TIME-AWARE: Если граф пришёл из PCMCI (Фаза 6), временная
    структура уже корректно выведена из данных — _break_cycles ПРОПУСКАЕТСЯ.
    PCMCI создаёт Time-Unrolled DAG (X_{t-1} → Y_t → X_{t+1}), где
    "циклы" уже разрешены через лагирование эмпирически.

    Применение _break_cycles к выхлопу PCMCI приведёт к дублированию лагов.

    Args:
        source_method_tags: теги метода, создавшего граф.
            Если {"time-series"} ∈ tags → skip (доверяем PCMCI).
        max_lag_depth: максимальная глубина лага (default 2).
            Ребро, уже имеющее lag >= max_lag_depth, не лагируется повторно,
            а удаляется (fallback) с warning.
        max_lagged_edges: максимальное число лагированных рёбер, создаваемых
            за один вызов. Предотвращает взрыв размерности графа при
            множественных пересекающихся циклах.
        max_cycles: safety valve — если обнаружено больше циклов, чем этот лимит,
            оставшиеся разрешаются классическим удалением (min confidence edge).

    ПРОБЛЕМА: Жадное удаление ребра с минимальным confidence уничтожало
    знания о динамике системы (structural misspecification). В макроэкономике
    обратные связи — реальность (Institutional Quality ↔ Economic Growth).

    РЕШЕНИЕ: Если SKG находит цикл A↔B, конвертируем в лагированную
    структуру: A_{t-1} → B_t и B_{t-1} → A_t. CausalEdge уже поддерживает
    поле `lag: int | None` — используем его. Это совместимо с PCMCI (Фаза 6),
    который строит Time-Unrolled DAG.

    ЗАЩИТА ОТ ВЗРЫВА РАЗМЕРНОСТИ: Множественные пересекающиеся циклы
    могут сгенерировать огромный лагированный граф, который «повесит» инференс.
    Три жёстких лимита предотвращают это:
    - max_lag_depth=2: ребро не лагируется глубже 2 шагов
    - max_lagged_edges=10: после 10 лагированных рёбер — fallback на удаление
    - max_cycles=8: после 8 циклов — fallback на удаление с warning

    Стратегия:
    1. Находим все циклы
    2. Для каждого цикла: ребро с меньшим confidence → lag=1 (не удаление!)
    3. Создаём лагированные узлы (e.g., "gdp_growth" → "gdp_growth_t-1")
    4. Если цикл содержит >2 узлов — fallback: min confidence edge → lag=1
    5. Если достигнут лимит лагов/рёбер/циклов — fallback: удаление + warning
    """
    # TIME-AWARE: пропускаем для time-series discovery (PCMCI)
    if source_method_tags and "time-series" in source_method_tags:
        return edges  # Лаги уже выведены эмпирически, не дублируем

    import rustworkx as rx

    G = rx.PyDiGraph()
    node_map: dict[str, int] = {}      # name → node index
    node_names: dict[int, str] = {}    # node index → name
    edge_map: dict[tuple[str, str], CausalEdge] = {}

    # Построить граф
    for e in edges:
        for n in (e.src, e.dst):
            if n not in node_map:
                idx = G.add_node(n)
                node_map[n] = idx
                node_names[idx] = n
        G.add_edge(
            node_map[e.src], node_map[e.dst],
            {"confidence": e.combined_confidence or 0.0},
        )
        edge_map[(e.src, e.dst)] = e

    lagged_edges: list[CausalEdge] = []
    cycles_resolved = 0
    warnings: list[str] = []

    while True:
        # rustworkx: digraph_find_cycle возвращает список (src_idx, dst_idx)
        cycle = rx.digraph_find_cycle(G)
        if not cycle:
            break

        cycles_resolved += 1

        # Ребро с минимальным confidence → кандидат на лагирование
        min_edge_pair = min(
            cycle,
            key=lambda e_pair: G.get_edge_data(e_pair[0], e_pair[1]).get("confidence", 0),
        )
        src_name = node_names[min_edge_pair[0]]
        dst_name = node_names[min_edge_pair[1]]
        src, dst = src_name, dst_name
        original_edge = edge_map.pop((src, dst), None)
        # rustworkx: remove_edge by node indices
        edge_idx = G.edge_index_map().get((node_map[src], node_map[dst]))
        if edge_idx is not None:
            G.remove_edge(edge_idx)

        if not original_edge:
            continue

        # Проверяем лимиты — если превышены, fallback на удаление
        current_lag = original_edge.lag or 0
        if (cycles_resolved > max_cycles
                or len(lagged_edges) >= max_lagged_edges
                or current_lag >= max_lag_depth):
            # Fallback: удаляем ребро (не лагируем), логируем warning
            reason = (
                f"lag_depth={current_lag}>={max_lag_depth}" if current_lag >= max_lag_depth
                else f"lagged_edges={len(lagged_edges)}>={max_lagged_edges}" if len(lagged_edges) >= max_lagged_edges
                else f"cycles={cycles_resolved}>{max_cycles}"
            )
            warnings.append(
                f"Cycle {src}↔{dst}: fallback to edge removal ({reason})"
            )
            continue  # Ребро уже удалено из G и edge_map

        # Конвертируем в лагированное ребро: src_{t-1} → dst_t
        lagged_src = f"{src}_t-1"
        lagged_edge = original_edge.model_copy(update={
            "src": lagged_src,
            "dst": dst,
            "lag": current_lag + 1,
            "metadata": {
                **(original_edge.metadata or {}),
                "cycle_resolution": "time_lagged",
                "original_src": src,
                "original_lag": current_lag or None,
            },
        })
        lagged_edges.append(lagged_edge)

    # warnings доступны через metadata результирующего графа
    return list(edge_map.values()) + lagged_edges
```

### 9.4 LLM Prior Calibration Model (ADR-0087)

**Проблема двойного счёта:** LLM обучен на той же литературе, что идёт в SKG. Если статья X→Y в SKG confidence=0.8, и LLM «подтверждает» X→Y с confidence=0.7 — это **не** независимые свидетельства. Суммирование их confidence завышает реальную уверенность.

**Решение: фиксированный LLM prior ceiling.**

```python
# Константы для LLM prior (ADR-0087)
LLM_PRIOR_CEILING = 0.3          # Максимальный confidence для LLM-only рёбер
LLM_OVERLAP_DISCOUNT = 0.5       # Дисконт при пересечении с SKG
```

**Правила:**
1. **LLM-only ребро** (нет в SKG, нет в data): `confidence = min(llm_raw_conf, LLM_PRIOR_CEILING) = max 0.3`. Это честнее, чем фиктивная точность LLM.
2. **LLM + SKG совпадают** (одно ребро): LLM confidence не добавляется к SKG confidence. LLM подтверждение → `replication_bonus += 0.05` (не полный boost). Обоснование: LLM ≈ сжатая копия SKG, не независимый источник.
3. **LLM противоречит SKG:** SKG wins (Закон L). LLM contradiction → `metadata.llm_disagreement = True` для аудита.

**Формальная модель:** LLM prior трактуется как **improper prior** (не калиброванная вероятность, а ординальный score). В `compute_combined_confidence()` вес LLM_PRIOR = 0.05 уже отражает это, но ceiling 0.3 добавляет жёсткую верхнюю границу.

### 9.5 Трёхслойное разделение конфликтов (из шифовой теории) (ADR-0088)

Reconciliation в `ReconcileCausalGraph.pure_step()` смешивает три фундаментально разных типа конфликтов. Шифовая теория формализует их как три ортогональных слоя:

| Слой | Вопрос | В коде (текущий) | В коде (целевой) |
|------|--------|-----------------|-----------------|
| **L1** (Identifiability) | Существует ли формула? | `DoWhy.identify()` | Без изменений |
| **L2** (Estimation) | Каково числовое значение? | `combined_confidence` | + `estimation_conflict_metric` |
| **L3** (Ontology) | Это «та же» переменная? | `VariableCanonizer` | + `alignment_confidence` |

**Hodge-диагностики для reconciliation:**

После reconciliation, перед финальной фильтрацией, вычисляем Hodge-компоненты на **bounded comparison complex**.

**Операциональная формализация (MVP):**
- Вершины (`0`-симплексы): source-specific estimates после L1-проверки.
- Рёбра (`1`-симплексы): есть, если выполнены одновременно:
  1. тип сертификата входит в allowlist policy,
  2. `c(chi_ij) >= tau_min`,
  3. есть валидный anchor `A_ij`.
- Треугольник (`2`-симплекс): добавляется только если есть все три рёбра **и** валидный triple anchor `A_ijk` (общий anchor id или явно подтверждённый anchor bundle).
- `delta^0` на ребре `(i,j)`: `(delta^0 s)_ij = R_ij s_j - L_ij s_i`.
- `delta^1` на треугольнике `(i,j,k)`: `(delta^1 alpha)_ijk = pi_jk^* alpha_jk - pi_ik^* alpha_ik + pi_ij^* alpha_ij`.

**Важно:** decomposition выполняется для **произвольных** `1`-коцепей `alpha ∈ C^1` (не только для cocycle, где `delta^1 alpha = 0`).

```python
# В ReconcileCausalGraph.pure_step() — после шагов 1-4, перед шагом 5

class ReconciliationDiagnostics(BaseModel):
    """Hodge-декомпозиция конфликтов в evidence graph."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    # Exact component: конфликты, снимаемые локальной корректировкой весов
    patchable_conflict_norm: float = 0.0

    # Harmonic component: irreducible disagreement (топологический)
    irreducible_conflict_norm: float = 0.0
    irreducible_edges: list[tuple[str, str]] = []  # рёбра с max вкладом

    # Coexact component: транзитивная несогласованность
    # A→B и B→C согласованы, но A→C нет
    cyclic_inconsistency_norm: float = 0.0
    inconsistent_triangles: list[tuple[str, str, str]] = []

    # Флаг для governance
    needs_expert_review: bool = False  # True если irreducible > threshold

def compute_reconciliation_diagnostics(
    reconciled: dict[tuple[str, str], CausalEdge],
    lit_graph: CausalGraphModel,
    data_graph: CausalGraphModel | None,
) -> ReconciliationDiagnostics:
    """
    Вычисляет Hodge-компоненты конфликтов.

    Hodge decomposition (general 1-cochains):
      alpha = delta^0 beta + alpha_H + (delta^1)^* gamma

    Solve path (bounded, sparse):
    1) Строим sparse D0, W и решаем patchable часть:
         (D0^T W D0) beta = D0^T W alpha
    2) Coexact часть оцениваем через sparse D1 (если треугольники доступны).
    3) Harmonic residual = alpha - delta^0 beta - coexact.

    Gauge-fixing для D0^T W D0 (иначе нулевой mode):
    - default: pinning (1 reference node на connected component)
    - fallback: ridge epsilon=1e-6 + post-projection на ортогональ constant mode

    Hard limits (production safety):
    - MAX_RECON_SOURCES = 128
    - MAX_RECON_EDGES = 4096
    - MAX_TRIANGLES = 20000
    - TRIANGLE_BUDGET_MS = 250

    Если лимит превышен:
    - coexact считается только по top-K=5000 треугольникам (по |edge discrepancy|),
    - при исчерпании бюджета ставим diagnostics_truncated=True,
      outer pipeline продолжается без BLOCKER.
    """
    ...
```

**Связь с `_break_cycles()`:** Coexact component (cyclic inconsistency) ловит именно те ситуации, когда цепочка свидетельств A→B→C→A не самосогласована. Это дополняет graph-level cycle detection: _break_cycles работает на уровне причинных рёбер, а cyclic inconsistency — на уровне evidence-конфликтов.

**Operational integration:**
- `irreducible_conflict_norm > 0.5` → `needs_expert_review = True` → HumanReviewPass создаёт review request
- `cyclic_inconsistency_norm > 0.3` → WARNING: "alignment operators internally inconsistent" → рекомендация проверить L3 (variable canonization)
- Метрики записываются в `CausalGraphModel.metadata.reconciliation_diagnostics`
- `diagnostics_truncated=True` и `truncation_reason` обязательны при срабатывании hard limits

### 9.6 Definition of Done — Фаза 9

- [ ] `BuildLiteraturePrior` Foundry method — запрашивает SKG
- [ ] `LiteratureCausalPrior` — JSON Schema snapshot
- [ ] `ReconcileCausalGraph` — LITERATURE_FIRST стратегия
- [ ] Только одна стратегия в MVP (остальные — backlog)
- [ ] LLM prior ceiling = 0.3 для LLM-only рёбер (ADR-0087)
- [ ] LLM + SKG overlap → replication_bonus += 0.05 (не полный boost)
- [ ] `ReconciliationDiagnostics` — Hodge-метрики (patchable, irreducible, cyclic) (ADR-0088)
- [ ] `delta^0`, `delta^1`, `D1` и правило построения 2-симплексов (`A_ijk`) реализованы явно в коде
- [ ] Декомпозиция работает для arbitrary `alpha ∈ C^1` (не только cocycle)
- [ ] Gauge-fixing: pinning по connected components + fallback `epsilon=1e-6` ridge
- [ ] Hard limits соблюдаются: `MAX_RECON_SOURCES=128`, `MAX_RECON_EDGES=4096`, `MAX_TRIANGLES=20000`, `TRIANGLE_BUDGET_MS=250`
- [ ] При превышении лимитов: `diagnostics_truncated=True`, `truncation_reason` заполнен
- [ ] `irreducible_conflict_norm > 0.5` → `needs_expert_review = True`
- [ ] `cyclic_inconsistency_norm > 0.3` → WARNING
- [ ] Тест: literature + data agree → boosted confidence > каждого по отдельности
- [ ] Тест: data contradicts literature direction → data wins
- [ ] Тест: only LLM hint → `unsupported_by_evidence=True`, confidence ≤ 0.3
- [ ] Тест: цикл → ребро с min confidence конвертировано в лагированную структуру (lag=1)
- [ ] Тест: >8 пересекающихся циклов → fallback на удаление после `max_cycles`, warning в metadata
- [ ] Тест: ребро с lag=2 при `max_lag_depth=2` → удаление (не лагирование глубже)
- [ ] Тест: triangle conflict (A→B=0.8, B→C=0.9, A→C=0.2) → cyclic_inconsistency > 0
- [ ] ADR-0032: LLM как интерпретатор контекста, не источник структуры
- [ ] ADR-0087: LLM Prior Calibration Model
- [ ] ADR-0088: Трёхслойное разделение конфликтов + Hodge-диагностики

---

## Фаза 10 — StructuralCausalModelSpec: механизмы и GCM

**Длительность:** 2.5–3 недели | **Риск:** MEDIUM-HIGH
**Предусловия:** Фаза 5, Фаза 2

### 10.1 IR: StructuralCausalModelSpec

```python
# ir/analytics/structural_causal_model.py

class MechanismFamily(str, Enum):
    LINEAR          = "linear"
    ADDITIVE_NOISE  = "additive_noise"
    POST_NONLINEAR  = "post_nonlinear"
    CLASSIFIER      = "classifier"
    EMPIRICAL       = "empirical"
    PARAMETRIC_PRIOR = "parametric_prior"  # из SKG литературы (Фаза 15 → 10)

class MechanismSource(str, Enum):
    """Откуда получен механизм — определяет приоритет."""
    DATA_FITTED     = "data_fitted"      # GCM auto-assignment на эмпирических данных
    LITERATURE_PRIOR = "literature_prior" # Параметры из SKG мета-анализа
    HYBRID          = "hybrid"           # Данные + литературный prior (байесовский)
    DEFAULT         = "default"          # Fallback: широкий prior, нет данных

class NodeMechanism(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    variable: str
    parents: list[str]
    family: MechanismFamily
    family_params: dict[str, Any] = {}  # JSON-serializable only (Закон H)
    noise_distribution: str = "empirical"
    # hybrid SCM support
    source: MechanismSource = MechanismSource.DATA_FITTED
    literature_prior: dict[str, float] | None = None  # {"mean": 0.5, "std": 0.15} из SKG
    sensitivity_to_latent: float | None = None  # для U-узлов из PAG→DAG projection

class StructuralCausalModelSpec(BaseModel):
    """
    Полная спецификация SCM: граф + механизмы + шум.

    HYBRID DESIGN:
    ==============
    Гибридный SCM с приоритетами источников:
    1. Если есть данные И литературный prior → HYBRID (байесовский:
       литература = prior, данные = likelihood)
    2. Если только данные → DATA_FITTED (классический GCM)
    3. Если только литература → LITERATURE_PRIOR (параметрический)
    4. Если ничего → DEFAULT (широкий prior, высокая неопределённость)

    Это позволяет собрать SCM как единый гибридный конструкт
    ПЕРЕД тем, как начать do() интервенции (Фаза 11).
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    graph: CausalGraphModel
    mechanisms: list[NodeMechanism]
    fitted: bool = False
    fit_method: str | None = None    # "auto" | "manual" | "gcm" | "hybrid"
    fit_metrics: dict[str, float] = {}
    # hybrid tracking
    mechanism_source_summary: dict[str, int] = {}  # {"data_fitted": 5, "literature_prior": 3, ...}
    skg_snapshot_ref: str | None = None  # Для воспроизводимости литературных prior'ов

    @model_validator(mode="after")
    def _validate_mechanisms_cover_graph(self) -> "StructuralCausalModelSpec":
        mech_vars = {m.variable for m in self.mechanisms}
        graph_vars = set(self.graph.nodes)
        missing = graph_vars - mech_vars
        # Root nodes (no parents) не обязаны иметь механизм
        non_roots = {e.dst for e in self.graph.edges}
        missing_non_roots = missing & non_roots
        if missing_non_roots:
            raise ValueError(f"Non-root nodes without mechanisms: {missing_non_roots}")
        return self
```

### 10.2 Foundry Method: GCMFit

```python
@foundry_method(
    namespace="causal.structural",
    version="1.0.0",
    tags={"causal", "gcm", "structural"},
)
class HybridSCMFit:
    """Гибридный фиттер SCM (бывший GCMFit).

    Объединяет данные (DoWhy GCM) и литературу (SKG prior) в один SCM:
    - Узлы с данными → GCM auto-assignment (MechanismSource.DATA_FITTED)
    - Узлы без данных, но с литературой → параметрический prior (LITERATURE_PRIOR)
    - Узлы с обоими → байесовское объединение (HYBRID)
    - U-узлы из PAG projection → DEFAULT с sensitivity_to_latent
    """
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    @staticmethod
    def pure_step(state: dict[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        """
        Hybrid fitting: DoWhy GCM + SKG литературные prior'ы.

        Алгоритм:
        1. PAG→DAG projection (если нужно)
        2. Для каждого узла определяем доступные источники:
           a. Данные есть? → dowhy.gcm auto-assignment
           b. SKG prior есть? → literature_prior из мета-анализа
           c. Оба? → GCM fit с информативным prior (байесовский)
           d. Ни одного? → широкий default prior
        3. Sensitivity check: если dE/dU_xy > threshold → unstable, route to Phase 12b

        PAG→DAG projection (обязательный шаг):
        dowhy.gcm СТРОГО требует DAG. Бидирекциональные рёбра из FCI → U-dummy nodes.
        Неопределённые рёбра → ориентация по SKG prior / алфавиту.
        U-узлы: sensitivity_to_latent; если высокая → маркировка unstable.
        """
        from dowhy import gcm
        ...


def _pag_to_dag_projection(
    graph: "CausalGraphModel",
) -> tuple["CausalGraphModel", list[str]]:
    """
    Проецирует PAG/CPDAG в DAG для dowhy.gcm.

    Returns:
        (dag_graph, latent_vars) — проецированный DAG + список добавленных U-узлов

    Raises:
        ValueError: если проекция невозможна (слишком много неопределённостей)
    """
    new_edges = []
    latent_vars = []
    latent_counter = 0

    for edge in graph.edges:
        if edge.mark_src == EdgeMark.ARROW and edge.mark_dst == EdgeMark.ARROW:
            # Бидирекциональное: X ↔ Y → U_n → X, U_n → Y
            u_name = f"U_{latent_counter}"
            latent_counter += 1
            latent_vars.append(u_name)
            new_edges.append(edge.model_copy(update={
                "src": u_name, "dst": edge.src,
                "mark_src": EdgeMark.TAIL, "mark_dst": EdgeMark.ARROW,
                "metadata": {"latent_proxy": True, "original_bidirected": f"{edge.src}↔{edge.dst}"},
            }))
            new_edges.append(edge.model_copy(update={
                "src": u_name, "dst": edge.dst,
                "mark_src": EdgeMark.TAIL, "mark_dst": EdgeMark.ARROW,
                "metadata": {"latent_proxy": True, "original_bidirected": f"{edge.src}↔{edge.dst}"},
            }))
        elif edge.mark_src == EdgeMark.CIRCLE or edge.mark_dst == EdgeMark.CIRCLE:
            # Неопределённое: ориентируем src → dst (алфавитный порядок как fallback)
            oriented = edge.model_copy(update={
                "mark_src": EdgeMark.TAIL, "mark_dst": EdgeMark.ARROW,
                "metadata": {**(edge.metadata or {}), "orientation_uncertain": True},
            })
            new_edges.append(oriented)
        else:
            new_edges.append(edge)

    new_nodes = list(graph.nodes) + latent_vars
    return graph.model_copy(update={
        "graph_type": GraphType.DAG,
        "nodes": new_nodes,
        "edges": new_edges,
    }), latent_vars
```

### 10.3 Definition of Done — Фаза 10

- [ ] `StructuralCausalModelSpec` — JSON Schema snapshot
- [ ] `GCMFit` — auto-assignment mechanisms, fit metrics
- [ ] `_pag_to_dag_projection()` — корректная проекция PAG→DAG с U-узлами
- [ ] Тест: PAG с бидирекциональным ребром → DAG с U-node → GCMFit не падает
- [ ] `NodeMechanism.family_params` — только JSON-serializable (Закон H)
- [ ] Тест: linear SCM → fitted → predict matches
- [ ] ADR-0033: JSON-serializable mechanism families only

---

## Фаза 11 — Causal queries: интервенции и контрафактуалы

**Длительность:** 2 недели | **Риск:** MEDIUM
**Предусловия:** Фаза 10

### 11.1 IR: CausalQuery и CausalQueryResult

```python
# ir/analytics/causal_queries.py

class QueryType(str, Enum):
    INTERVENTIONAL      = "interventional"       # P(Y|do(X=x))
    COUNTERFACTUAL      = "counterfactual"       # P(Y_x|X=x', Y=y)
    ATTRIBUTION         = "attribution"          # Какая доля Y объясняется X
    SOFT_INTERVENTION   = "soft_intervention"    # P(Y|do(X~g(x)))

class InterventionSpec(BaseModel):
    """Поддержка атомарных и мягких интервенций.

    Legal Graph может диктовать мягкие ограничения (переходный период,
    квоты, лимиты), которые превращают атомарную do(X=x) в
    стохастическую/soft intervention do(X~g(x)).

    Пример: Закон вводит верхний лимит 20% на ставку →
    do(tax_rate) → do(tax_rate ~ Truncated(upper=0.2))
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str = "atomic"                    # "atomic", "truncated", "shifted", "stochastic"
    value: float | None = None              # Для atomic: do(X=value)
    distribution: str | None = None         # Для stochastic: "truncnorm(0.1,0.05,0,0.2)"
    bounds: tuple[float, float] | None = None  # Для truncated: (lower, upper)
    shift: float | None = None              # Для shifted: do(X = X_obs + shift)
    legal_constraint_id: str | None = None  # Ссылка на юридическое ограничение

class CausalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query_type: QueryType
    treatment_variable: str
    treatment_value: float | None = None    # None для soft interventions
    outcome_variable: str
    condition: dict[str, float] = {}  # Для counterfactual: наблюдённое состояние
    n_samples: int = 1000
    # soft intervention support для Legal Graph constraints
    intervention_spec: InterventionSpec | None = None  # Если None → atomic do(X=treatment_value)

class CausalQueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    query: CausalQuery
    result_mean: float
    result_std: float
    result_ci: tuple[float, float]
    result_distribution: list[float] | None = None  # Samples if stored
    computation_time_seconds: float = 0.0

    def to_uncertainty_envelope(self) -> "UncertaintyEnvelope":
        """По аналогии с CausalEffectReport.to_uncertainty_envelope()."""
        from polisyos.ir.analytics.uncertainty import (
            UncertaintyEnvelope, UncertaintySource,
            DistributionFamily, PropagationMethod, IntervalSemantics,
        )
        return UncertaintyEnvelope(
            point_estimate=self.result_mean,
            confidence_interval=self.result_ci,
            confidence_level=0.95,
            distribution_family=DistributionFamily.BOOTSTRAP,
            source=UncertaintySource.CAUSAL,
            propagation_method=PropagationMethod.MONTE_CARLO,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            sample_size=self.query.n_samples,
            is_heuristic_ci=False,
            gate_eligible=True,
        )
```

### 11.2 Definition of Done — Фаза 11

- [ ] `GCMQuery` Foundry method — interventional + counterfactual
- [ ] `CausalQueryResult.to_uncertainty_envelope()` — совместим с существующим UncertaintyEnvelope
- [ ] Тест: do(X=1) vs do(X=0) → ATE совпадает с DoWhy estimate
- [ ] JSON Schema snapshot

---

## Фаза 12 — Transportability: замыкание трёх графов, S-диаграммы, transport formula

**Длительность:** 12–16 недель
**Предусловия:** Фаза 0 (SKG + Dataset Graph + Legal Graph bridge), Фаза 5, Фаза 10, Фаза 11
**Риск:** HIGH

Ключевые аспекты:
- Явное ограничение scope: «Simplified TR» (backdoor-only)
- ContextProfile.inference_level для tracking точности
- Data source integration (WGI/WVS/WDI) для enrichment
- **Замыкание трёх графов:** SKG → Dataset Metadata Graph → Legal KG → итеративный resolver
- **DataGap** как первоклассный объект: explicit reporting о недостающих данных
- **Прокси-цепочки** с контекстно-зависимыми штрафами (не фиксированные константы)
- **Legal → S-nodes:** юридические ограничения как S-узлы в SelectionDiagram
- **Hard/soft constraints:** `ConstraintSeverity.HARD` блокирует транспортировку
- **`TransportabilityResolutionLoop`:** итеративный цикл с обратными связями между графами

### 12.0 Архитектура замыкания трёх графов (Three-Graph Closure)

Transport formula из Bareinboim-Pearl говорит: чтобы перенести эффект из одного контекста в другой, нужен P*(Z) — распределение переменной Z в целевом контексте. Оперативный вопрос — откуда взять P*(Z)? Здесь три графа смыкаются:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TransportabilityResolutionLoop                    │
│                                                                     │
│   ┌──────────┐      ┌───────────────┐      ┌──────────────────┐    │
│   │   SKG    │      │ Dataset Graph │      │  Legal Graph     │    │
│   │          │      │               │      │                  │    │
│   │ Что      │      │ Чем вычислить │      │ Можно ли +       │    │
│   │ переносить│◄────►│ P*(Z)         │◄────►│ юр. S-узлы       │    │
│   │ и при    │      │               │      │                  │    │
│   │ каких    │      │ Конкретные    │      │ hard constraints │    │
│   │ условиях │      │ датасеты, API │      │ soft → S-nodes   │    │
│   └────┬─────┘      └───────┬───────┘      └────────┬─────────┘    │
│        │                    │                        │              │
│        └────────────┬───────┘                        │              │
│                     ▼                                │              │
│        ┌────────────────────────┐                    │              │
│        │  SelectionDiagram     │◄───────────────────┘              │
│        │  S-узлы из:           │   Legal добавляет                 │
│        │  - context delta      │   S-узлы на mechanism             │
│        │  - legal constraints  │                                   │
│        └──────────┬────────────┘                                   │
│                   ▼                                                │
│        ┌────────────────────────┐                                  │
│        │  TR-алгоритм          │                                  │
│        │  → TransportFormula    │                                  │
│        │  → required P*(Z)     │                                  │
│        └──────────┬────────────┘                                  │
│                   ▼                                                │
│        ┌────────────────────────┐                                  │
│        │  Dataset Graph         │                                  │
│        │  вычисляет P*(Z)       │                                  │
│        │  или → DataGap         │                                  │
│        └──────────┬────────────┘                                  │
│                   ▼                                                │
│        ┌────────────────────────┐                                  │
│        │  Convergence check     │                                  │
│        │  S-nodes changed?      │──── yes ──→ next round           │
│        │  New data gaps?        │                                  │
│        └──────────┬────────────┘                                  │
│                   │ no                                              │
│                   ▼                                                │
│        ┌────────────────────────┐                                  │
│        │  TransportedEstimate   │                                  │
│        │  + full lineage        │                                  │
│        │  + DataGaps            │                                  │
│        │  + confidence decomp   │                                  │
│        └────────────────────────┘                                  │
└─────────────────────────────────────────────────────────────────────┘
```

**Почему итеративный цикл, а не pipeline:** Обратные связи между графами неизбежны:
- SKG: "нужен Z = institutional_quality"
- Dataset Graph: "WGI доступен только до 2023" → меняет временной горизонт
- Legal Graph: "переходный период 6 мес" → меняет intervention (не мгновенный шок, а постепенный) → SKG должен искать статьи с phased implementation → Dataset Graph нужны monthly данные, не annual

```python
# scientist/nodes/builtins/causal/resolve_transport.py

class ResolutionState(BaseModel):
    """Состояние одного раунда resolution loop."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    round: int
    s_nodes: list["SNode"]
    legal_s_nodes: list["SNode"]        # S-узлы от Legal Graph
    data_gaps: list["DataGap"]
    hard_constraints: list["LegalConstraint"]
    p_star_values: dict[str, "PStarZResult"]   # canonical_var → computed P*(Z)
    converged: bool                     # S-nodes не менялись с прошлого раунда
    feasible: bool                      # False если есть HARD constraint

class DataGap(BaseModel):
    """Явное описание недостающих данных для transport formula."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    required_variable: str              # "institutional_quality"
    required_context: str               # "UA, 2020-2024"
    available_proxies: list["ProxyCandidate"]
    best_proxy_confidence: float        # Лучший прокси confidence (или 0.0)
    gap_impact: str                     # "transport_confidence drops from 0.7 to 0.4"
    suggested_action: str               # "WGI 2024 update available March 2025"

class TransportabilityResolutionLoop:
    """
    Итеративный resolver для замыкания трёх графов.

    Каждый раунд:
    1. SKG: находит source studies, extraction results, boundary conditions
    2. build_selection_diagram(): контекст-S-узлы из delta
    3. LegalConstraintBridge: юридические hard/soft constraints → дополнительные S-узлы
    4. CheckTransportability: TR-алгоритм → transport formula → required P*(Z)
    5. DatasetRegistry: вычисляет P*(Z) или создаёт DataGap
    6. Convergence check: если S-nodes или data gaps изменились → следующий раунд

    Max 3 раунда (ADR-0048). На практике сходится за 1-2.

    ОПТИМИЗАЦИЯ: LRU-кэш для детерминированных запросов (compute_p_star_z,
    find_datasets_for_variable, distance_to) — ~60% повторных запросов
    при 3 раундах с 10+ S-узлами. См. Приложение B.8.
    """

    MAX_ROUNDS: int = 3

    def __init__(
        self,
        skg_store: "ScientificKnowledgeGraph",
        dataset_registry: "DatasetRegistry",
        legal_bridge: "LegalConstraintBridge",
    ):
        self._skg = skg_store
        self._datasets = dataset_registry
        self._legal = legal_bridge

    def resolve(
        self,
        source_context: "ContextProfile",
        target_context: "ContextProfile",
        causal_graph: "CausalGraphModel",
        query_treatment: str,
        query_outcome: str,
        policy_spec: dict | None = None,
    ) -> "TransportabilityResult":
        """
        Полный цикл замыкания: итеративно разрешает S-узлы,
        вычисляет P*(Z), собирает DataGaps и legal constraints.
        """
        prev_s_node_set: set[str] = set()
        state: ResolutionState | None = None

        for round_num in range(self.MAX_ROUNDS):
            # --- Шаг 1: S-узлы из контекстной дистанции ---
            context_s_nodes = _build_context_s_nodes(source_context, target_context, causal_graph)

            # --- Шаг 2: Legal constraints → дополнительные S-узлы ---
            legal_constraints = LegalConstraintSet(
                jurisdiction=target_context.context_id,
                policy_domain="",
                hard_constraints=[],
                soft_constraints=[],
                data_license_constraints=[],
                legal_dag_mappings=[],
            )
            legal_s_nodes: list[SNode] = []
            hard_constraints: list[LegalConstraint] = []

            if policy_spec:
                legal_constraints = self._legal.get_constraints_for_policy(
                    jurisdiction=target_context.context_id,
                    policy_domain=policy_spec.get("domain", ""),
                    policy_spec=policy_spec,
                )
                hard_constraints = legal_constraints.hard_constraints
                legal_s_nodes = _legal_constraints_to_s_nodes(
                    legal_constraints.legal_dag_mappings,
                    causal_graph,
                )

            # --- Шаг 2b: Hard constraint check ---
            if hard_constraints:
                return self._build_infeasible_result(
                    source_context, target_context,
                    hard_constraints, query_treatment, query_outcome,
                )

            # --- Шаг 3: Merged S-nodes ---
            all_s_nodes = context_s_nodes + legal_s_nodes
            current_s_set = {(s.target_variable, s.context_dimension) for s in all_s_nodes}

            # --- Шаг 4: TR-алгоритм ---
            diagram = SelectionDiagram(
                base_graph=causal_graph,
                s_nodes=all_s_nodes,
                source_context=source_context,
                target_context=target_context,
                context_distance=source_context.distance_to(target_context),
            )
            tr_result_raw = CheckTransportability.pure_step(
                {
                    "selection_diagram": diagram.model_dump(mode="json"),
                    "query_treatment": query_treatment,
                    "query_outcome": query_outcome,
                },
                {},
            )
            tr_result = TransportabilityResult.model_validate(tr_result_raw["transport_result"])

            # --- Шаг 5: Вычисление P*(Z) через Dataset Graph ---
            p_star_values: dict[str, PStarZResult] = {}
            data_gaps: list[DataGap] = []

            if tr_result.transport_formula:
                # Построить lookup: z_var → StratificationVariable (для condition_on)
                strat_lookup: dict[str, StratificationVariable] = {
                    sd.name: sd
                    for sd in tr_result.transport_formula.stratification_details
                }

                for z_var in tr_result.transport_formula.stratification_variables:
                    # CRITICAL (Pearl & Bareinboim 2011):
                    # Медиатор → P*(z|x), ковариата → P*(z) маргинальная
                    strat_detail = strat_lookup.get(z_var)
                    condition_on: dict[str, float] | None = None
                    if strat_detail and strat_detail.requires_conditional:
                        # Медиатор: нужна P*(z|treatment=x).
                        # treatment_value из query_spec или среднее по target данным.
                        condition_on = {
                            strat_detail.condition_on_treatment: (
                                query_treatment_value  # из policy_spec или default
                            ),
                        }

                    p_star = self._datasets.compute_p_star_z(
                        canonical_var=z_var,
                        country_code=target_context.context_id,
                        year=_extract_year(target_context.time_period),
                        condition_on=condition_on,
                    )
                    if p_star.value is not None:
                        p_star_values[z_var] = p_star
                    else:
                        # Попытка прокси
                        proxy_chain = resolve_proxy(
                            z_var, target_context.context_id,
                            self._datasets, self._skg,
                        )
                        if proxy_chain.best_single_confidence > 0.3:
                            # Используем лучший прокси
                            best = proxy_chain.proxies[0]
                            # Прокси для условной P*(z|x): дополнительный штраф,
                            # т.к. прокси-данные могут не содержать treatment variable
                            extra_penalty = 0.1 if condition_on else 0.0
                            p_star_values[z_var] = PStarZResult(
                                canonical_variable=z_var,
                                value=None,  # будет вычислено из прокси
                                dataset_id=best.proxy_dataset_id,
                                raw_variable=best.proxy_raw_name,
                                is_proxy=True,
                                proxy_chain=[f"{best.proxy_variable} → {z_var}"],
                                confidence=best.effective_confidence - extra_penalty,
                                penalty_breakdown={
                                    "proxy": 1.0 - best.effective_confidence,
                                    **({"conditional_proxy": extra_penalty} if condition_on else {}),
                                },
                                is_conditional=condition_on is not None,
                                condition_on=condition_on or {},
                            )
                        else:
                            data_gaps.append(DataGap(
                                required_variable=z_var,
                                required_context=f"{target_context.context_id}, {target_context.time_period}",
                                available_proxies=proxy_chain.proxies,
                                best_proxy_confidence=proxy_chain.best_single_confidence,
                                gap_impact=f"transport_confidence reduced by ~0.2-0.3",
                                suggested_action=_suggest_data_collection(z_var),
                            ))

            # --- Шаг 5b: Proxy-depth guard (anti-oscillation) ---
            # Риск осцилляции: Legal→S-node → Dataset→proxy → proxy имеет
            # другой context delta → новый S-node → бесконечный цикл.
            # Запрет: переменные, введённые как прокси, НЕ могут генерировать
            # новые контекстные S-узлы в следующем раунде.
            proxy_introduced_vars = {
                z_var for z_var, pz in p_star_values.items() if pz.is_proxy
            }
            # Фильтруем S-узлы: если target_variable — прокси из предыдущего шага → skip
            context_s_nodes = [
                s for s in context_s_nodes
                if s.target_variable not in proxy_introduced_vars
            ]
            all_s_nodes = context_s_nodes + legal_s_nodes
            current_s_set = {(s.target_variable, s.context_dimension) for s in all_s_nodes}

            # --- Шаг 6: Convergence check ---
            converged = (current_s_set == prev_s_node_set) or round_num == self.MAX_ROUNDS - 1
            prev_s_node_set = current_s_set

            state = ResolutionState(
                round=round_num,
                s_nodes=context_s_nodes,
                legal_s_nodes=legal_s_nodes,
                data_gaps=data_gaps,
                hard_constraints=hard_constraints,
                p_star_values=p_star_values,
                converged=converged,
                feasible=True,
            )

            if converged:
                break

        # --- Финальный результат с полным lineage ---
        return self._build_final_result(tr_result, state, diagram)

    def _build_infeasible_result(
        self,
        source: "ContextProfile",
        target: "ContextProfile",
        hard_constraints: list["LegalConstraint"],
        treatment: str,
        outcome: str,
    ) -> "TransportabilityResult":
        """Hard legal constraint → транспортировка невозможна."""
        return TransportabilityResult(
            query=f"P*({outcome}|do({treatment}))",
            status=TransportabilityStatus.NON_TRANSPORTABLE,
            base_confidence=0.0,
            context_distance_penalty=0.0,
            data_availability_penalty=0.0,
            final_confidence=0.0,
            algorithm_version="simplified_tr_v2",
            feasible=False,
            hard_legal_constraints=[c.constraint_id for c in hard_constraints],
            warnings=[
                f"HARD legal constraint blocks transportability: {c.description}"
                for c in hard_constraints
            ],
            source_context_id=source.context_id,
            target_context_id=target.context_id,
        )

    def _build_final_result(
        self,
        tr_result: "TransportabilityResult",
        state: "ResolutionState",
        diagram: "SelectionDiagram",
    ) -> "TransportabilityResult":
        """Обогащает TR результат данными из замыкания.

        Мультипликативные штрафы вместо аддитивных.

        ПРОБЛЕМА: `confidence - proxy_penalties - data_gap_penalty`
        При conf=0.4 и двух прокси по 0.2 → confidence=0, что уничтожает
        относительную шкалу и приводит к резкому схлопыванию метрики.

        РЕШЕНИЕ: Conf_final = Conf_base × Π(1 - penalty_i)
        Гарантирует graceful degradation и никогда не даёт жёсткий 0,
        если только один из компонентов не равен 0 абсолютно.
        """
        # мультипликативные штрафы (цепь условных вероятностей)
        confidence = tr_result.final_confidence
        proxy_penalty_total = 0.0
        for pz in state.p_star_values.values():
            if pz.is_proxy:
                penalty = 1.0 - pz.confidence  # 0.0 (идеально) .. 1.0 (нет данных)
                confidence *= (1.0 - penalty)   # graceful degradation
                proxy_penalty_total += penalty

        # Data gaps: каждый gap снижает confidence на 15% мультипликативно
        data_gap_penalty = 0.0
        for _ in state.data_gaps:
            confidence *= 0.85  # (1 - 0.15)
            data_gap_penalty += 0.15

        adjusted_confidence = max(0.0, confidence)

        return tr_result.model_copy(update={
            "final_confidence": adjusted_confidence,
            "data_availability_penalty": tr_result.data_availability_penalty + proxy_penalty_total + data_gap_penalty,
            "data_gaps": [g.model_dump(mode="json") for g in state.data_gaps],
            "p_star_values": {k: v.model_dump(mode="json") for k, v in state.p_star_values.items()},
            "legal_s_nodes": [s.model_dump(mode="json") for s in state.legal_s_nodes],
            "resolution_rounds": state.round + 1,
        })
```

### 12.0b DataGap: первоклассный объект

Когда transport formula требует P*(Z), а Dataset Graph не находит подходящего датасета — система явно сообщает чего не хватает:

```python
# Пример DataGap в итоговом TransportabilityResult:

DataGap(
    required_variable="institutional_quality",
    required_context="UA, 2020-2024",
    available_proxies=[
        ProxyCandidate(
            proxy_variable="corruption_perception",
            proxy_dataset_id="TI_CPI_2023",
            proxy_raw_name="cpi_score",
            base_correlation=0.78,
            context_adjustment=0.85,     # post-communist adjustment
            effective_confidence=0.66,
            source="seed_table",
        ),
    ],
    best_proxy_confidence=0.66,
    gap_impact="transport_confidence drops from 0.72 to 0.54",
    suggested_action="WGI 2024 release expected Q1 2025; use CPI as interim proxy",
)
```

Это качественно меняет диалог с пользователем: не "результат недоступен", а "нам не хватает конкретно этих данных, вот что можно собрать, а пока вот прокси с explicit штрафом".

### 12.1 Теоретическая основа и scope ограничения

Transportability формализована Pearl и Bareinboim (2011–2014).

**Явное ограничение scope (ADR-0034):**

Полный TR-алгоритм рекурсивен и использует все три правила do-calculus + C-компоненты (Tian-Pearl). Это алгоритмически сложно и требует отдельной библиотеки.

**Simplified TR:**
- Покрывает: S-узлы на pre-treatment ковариатах (P\*(z) маргинальная), S-узлы на медиаторах (P\*(z|x) условная), S-узлы не являющиеся предками treatment
- Метод устранения: backdoor adjustment с stratification по S-affected переменным
- Collider detection (selection bias) → БЛОКИРОВКА, не adjustment
- Bidirectional edge check (скрытые конфаундеры) → `needs_advanced_tr`
- **НЕ покрывает:** front-door adjustment, правило 2/3 do-calculus, C-component factorization, полумарковские модели с U-узлами

**Unsupported cases (явно классифицируются, не пропускаются):**
1. S-узел на коллайдере (X→Z←Y) — selection bias при обуславливании
2. Бидирекциональные рёбра (FCI/PAG) между treatment и adjustment variable — скрытый конфаундер ломает backdoor
3. Front-door criterion — требует Rule 2 do-calculus (→ Phase 12b)
4. C-component factorization — полумарковские модели (→ Phase 12b)

**Оценка покрытия (требуется pre-implementation survey, ADR-0089):**

Текущая оценка ~60-70% требует верификации. До начала кодирования Phase 12 необходимо провести **ручной survey** на 30-50 типичных policy вопросах:

```
Survey Protocol (до старта Phase 12):
1. Выбрать 30-50 реальных policy questions из PolicyOS domain
   (налоги, трудовой рынок, институты, торговля, образование)
2. Для каждого вопроса: определить identifiability method вручную
3. Классифицировать:
   - BACKDOOR_SUFFICIENT: стандартный backdoor (Simplified TR покрывает)
   - IV_REQUIRED: инструментальные переменные
   - FRONTDOOR_REQUIRED: front-door criterion
   - GENERAL_CALCULUS: правила 2/3 do-calculus
   - NON_IDENTIFIABLE: не идентифицируемо
4. Если BACKDOOR_SUFFICIENT < 60% → пересмотреть MVP scope:
   рассмотреть IV support (2-3 недели) как часть Phase 12a

Ожидаемый результат survey:
- BACKDOOR_SUFFICIENT: 50-70% (tax reform, subsidy, regulation)
- IV_REQUIRED: 15-25% (education→income, innovation→growth)
- FRONTDOOR_REQUIRED: 5-10% (mediation questions)
- GENERAL_CALCULUS: 5-10% (complex multi-level policies)
```

Если survey показывает IV_REQUIRED > 20% — добавить IV-based transport в Phase 12a (DoWhy уже поддерживает IV через `method_name="iv.instrumental_variable"`). Это +1-2 недели, но закроет ~85% вместо ~65%.

Оставшиеся случаи классифицируются как NON_TRANSPORTABLE с рекомендацией manual review. Снижены false-positive TRANSPORTABLE (коллайдеры и U-nodes теперь ловятся).

### 12.1b Формальные условия валидности прокси-переменных (ADR-0090)

`proxy_resolver.py` использует прокси для P*(Z) когда прямые данные недоступны. Но не все корреляты являются валидными прокси для каузальной идентификации. Формальные условия (Pearl 2012, Miao et al. 2018):

**Прокси W валиден для Z в транспортной формуле iff:**

1. **Relevance**: `W ⊥̸ Z` — прокси коррелирует с целевой переменной (проверяемо по данным)
2. **Exclusion**: `W ⊥ Y | Z, X` — прокси не влияет на outcome кроме как через Z (проверяемо по графу)
3. **Non-collider**: W не является коллайдером на пути X→Z→Y (проверяемо по графу)
4. **Completeness**: E[Z|W] обратима — W несёт достаточную информацию о Z (проверяемо при `Corr(W,Z) > threshold`)

**Checklist для `proxy_resolver.py`:**

```python
class ProxyValidityChecklist(BaseModel):
    """Формальная проверка валидности прокси-переменной."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    proxy_variable: str
    target_variable: str

    # Condition 1: Relevance (from seed table or data)
    relevance_check: bool = False
    correlation: float | None = None        # |corr(W,Z)| from data

    # Condition 2: Exclusion restriction (from causal graph)
    exclusion_check: bool = False
    exclusion_method: str = ""              # "graph_check" | "assumed" | "untestable"

    # Condition 3: Non-collider (from causal graph)
    non_collider_check: bool = False

    # Condition 4: Completeness (from data, correlation threshold)
    completeness_check: bool = False
    completeness_threshold: float = 0.5     # |corr| > 0.5

    @property
    def is_valid(self) -> bool:
        return self.relevance_check and self.non_collider_check
        # exclusion и completeness: WARNING если False, не блокируют

    @property
    def requires_expert_review(self) -> bool:
        return not self.exclusion_check or not self.completeness_check
```

**Интеграция:** `resolve_proxy()` вызывает `validate_proxy()` для каждого кандидата. Если `is_valid=False` → skip proxy. Если `requires_expert_review=True` → proxy используется с дополнительным penalty и `metadata.proxy_validity_warning`.

### 12.1c Частичная идентификация: bounds вместо бинарного ⊥ (ADR-0091)

Когда Simplified TR возвращает `NON_TRANSPORTABLE`, текущая система создаёт `DataGap` и останавливается. Но часто доступны **информативные границы** (Manski bounds), дающие полезный интервал вместо полного отказа.

```python
class PartialIdentificationResult(BaseModel):
    """Результат частичной идентификации (bounds)."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    method: str                       # "manski_bounds" | "iv_bounds" | "monotone_treatment"
    lower_bound: float
    upper_bound: float
    assumptions: list[str]            # Какие assumptions нужны для этих bounds
    is_informative: bool              # width < 0.5 (или другой threshold)
    width: float                      # upper - lower

    @model_validator(mode="after")
    def _validate_bounds(self) -> "PartialIdentificationResult":
        if self.lower_bound > self.upper_bound:
            raise ValueError("lower_bound > upper_bound")
        return self

# Расширение TransportabilityResult:
#   partial_id_bounds: PartialIdentificationResult | None = None
```

**Manski worst-case bounds** (когда backdoor fails):
```
P*(Y=1|do(X=1)) ∈ [P*(Y=1,X=1), P*(Y=1,X=1) + P*(X=0)]
```

**Monotone treatment response** (если можно предполагать монотонность):
```
P*(Y=1|do(X=1)) ∈ [P*(Y=1|X=1), P*(Y=1|X=1) + P*(Y=1|X=0) × delta]
```

**Реализация:** когда `CheckTransportability` возвращает `NON_TRANSPORTABLE`:
1. Проверить: доступны ли маргинальные P(Y,X) в target?
2. Если да → вычислить Manski bounds
3. Если `is_informative` (width < threshold) → включить в `TransportabilityResult`
4. Пользователь получает «эффект между -0.05 и +0.20» вместо «нет данных»

### 12.1d Гармоническое среднее для composition of confidence (ADR-0092)

Из шифовой теории: при цепочке alignments (proxy chain, chained certificates), confidence композируется через **гармоническое среднее**, а не произведение:

```python
def compose_confidence_harmonic(c1: float, c2: float) -> float:
    """
    Harmonic mean composition (из шифовой теории, Section 4.2).

    Свойства:
    - c ≤ min(c1, c2): monotone degradation (цепь = слабейшее звено)
    - Graceful: если оба > 0.9, результат > 0.9
    - c = 0 iff любой фактор = 0
    - Для c1=0.9, c2=0.5: harmonic = 0.64 (close to min, conservative)

    Сравнение с текущим подходом (мультипликативный):
    - Произведение: 0.9 × 0.5 = 0.45 (слишком агрессивно)
    - Harmonic:    2×0.9×0.5/(0.9+0.5) = 0.64 (ближе к min)
    - Min:         0.5 (потеря информации о сильном звене)
    """
    if c1 <= 0 or c2 <= 0:
        return 0.0
    return 2 * c1 * c2 / (c1 + c2)
```

**Применение в `proxy_resolver.py`:** заменить текущие мультипликативные штрафы `confidence *= (1 - penalty)` на `compose_confidence_harmonic()` для proxy chains длиной ≥ 2.

**Применение в `_build_final_result()`:** для proxy penalty chain вместо `Π(1-p_i)`.

**Предупреждение для длинных цепочек:** при chain length > 5 → diagnostic WARNING «long alignment chain» (из шифовой теории: harmonic mean сходится к min для длинных цепочек, но информация теряется).

### 12.1e Динамическая transportability для лаговых эффектов (ADR-0093)

PCMCI (Фаза 6) возвращает лаговые рёбра `X_{t-1} → Y_t`. Теория транспортировки (Bareinboim-Pearl) — статическая. Формальное допущение для переноса лаговых эффектов:

**Assumption (Time-Stationarity for Transport):** Лаговый эффект `β(X_{t-k} → Y_t)` транспортируется из source в target если:
1. Временная структура (лаг k) одинакова в обоих контекстах
2. Механизм `X → Y` стационарен (не зависит от t)
3. Нет time-varying confounders, различающихся между контекстами

```python
# Расширение TransportabilityResult:
#   assumes_time_stationarity: bool = False  # True если есть lagged edges в графе
#   lagged_edges_in_query: list[str] = []    # рёбра с lag > 0 в transport path
#   time_stationarity_warning: str | None = None  # "Lagged effects assume time-stationarity"
```

**В `CheckTransportability.pure_step()`:** если в `SelectionDiagram.base_graph` есть рёбра с `lag > 0` на transport path → выставить `assumes_time_stationarity = True` и добавить WARNING.

### 12.1f Typed certification policy + bounded outer objective

Чтобы L3 не был "неявным", вводится типизированная политика сертификатов выравнивания:

```python
class AlignmentCertificateType(str, Enum):
    EXACT = "exact"
    SCALE_LINK = "scale_link"
    LATENT_LINK_IRT = "latent_link_irt"
    PROXY_BUNDLE = "proxy_bundle"
    TEXT_CONCEPT_MAP = "text_concept_map"

class AlignmentCertificationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed_types: frozenset[AlignmentCertificateType] = frozenset({
        AlignmentCertificateType.EXACT,
        AlignmentCertificateType.SCALE_LINK,
        AlignmentCertificateType.LATENT_LINK_IRT,
        AlignmentCertificateType.PROXY_BUNDLE,
        AlignmentCertificateType.TEXT_CONCEPT_MAP,
    })
    tau_min: float = 0.75               # hard bounded: 0.55 <= tau_min <= 0.95
    composition_rule: str = "harmonic"  # harmonic | multiplicative (MVP: harmonic)
    max_chain_length: int = 5           # >5 => long_chain_warning
```

**Outer objective (coverage vs conflict):**

`score(N) = coverage_queries(N) - lambda_conflict * irreducible_conflict_norm(N)`

Где `N` — текущий certified comparison complex.

**Выбор `lambda_conflict`:**
- `expert`: фиксированное `lambda_conflict=1.0` (MVP default)
- `cv`: из сетки по holdout-prediction error (Phase 14+)
- `bic_like`: штраф за сложность complex (`|E|`, `|T|`) для noisier evidence graphs

**Жёсткие лимиты outer-loop (не роняем latency):**
- `TAU_GRID = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]` (8 точек)
- `LAMBDA_GRID = [0.5, 1.0, 2.0]` (3 точки, только если не expert mode)
- `TYPE_CONFIGS_MAX = 6` (предопределённые конфигурации, без полного `2^K` перебора)
- `MAX_OUTER_SOLVES = 48` (hard cap)
- `MAX_OUTER_WALLTIME_SEC = 3.0` (hard timeout)

При исчерпании бюджета: возвращаем `best_seen_config`, ставим
`outer_search_truncated=True`, логируем `search_budget_exhausted`.

**Полный TR (Phase 12b, backlog):**

**АРХИТЕКТУРНОЕ РЕШЕНИЕ: Мост к существующим решателям вместо реализации с нуля.**

Полный s-ID алгоритм с рекурсивным спуском по C-компонентам — задача уровня
CS-диссертации. Написание с нуля на Python — огромный риск для таймлайна.

**Рекомендуемая стратегия: Bridge Pattern**

1. **Python:** библиотека `y0` (лаборатория Altamira, Robert Osazuwa Ness) —
   реализует полный Shpitser-Pearl ID алгоритм и транспортабельность
2. **R (fallback):** библиотека `causaleffect` (Bareinboim & Tikka) —
   нативная функция `transport()` для transportability

**Архитектура моста:**
```python
# scientist/nodes/builtins/causal/full_transport.py

class FullTransportBridge:
    """
    Мост между PolicyOS SelectionDiagram и y0/causaleffect solver.

    Вместо написания рекурсивной деривации с нуля:
    1. Из Kuzu Causal Graph (Cypher) экспортируем SelectionDiagram → y0.dsl.Variable graph
    2. Вызываем y0.algorithm.identify.identify() для идентификации
    3. Получаем символическую TransportFormula
    4. Скармливаем формулу обратно в DatasetRegistry для P*(Z)

    Для R-based fallback (causaleffect):
    1. Сериализуем граф в igraph-compatible формат
    2. Вызываем R через rpy2: causaleffect::transport()
    3. Парсим символический результат

    Оценка: ~2 недели интеграция (vs ~3-4 месяца с нуля)
    """
    ...
```

**Что реализуется через мост (а не с нуля):**
- Правила 2 и 3 do-calculus
- C-component factorization (Tian-Pearl)
- Рекурсивная деривация transport formula
- Обработка полумарковских моделей (скрытые конфаундеры)

**Что остаётся в PolicyOS:**
- SelectionDiagram ↔ y0 трансляция
- Интеграция символической формулы с DatasetRegistry
- Legal constraint mapping (уникально для PolicyOS)
- Confidence aggregation и reporting

Ориентировочно +2-3 недели (интеграция моста), после стабилизации Simplified TR

### 12.2 IR: ContextProfile

```python
# ir/analytics/transportability.py

class IncomeLevel(str, Enum):
    HIGH         = "high"
    UPPER_MIDDLE = "upper_middle"
    LOWER_MIDDLE = "lower_middle"
    LOW          = "low"

class CulturalCluster(str, Enum):
    """Inglehart-Welzel Cultural Map clusters."""
    PROTESTANT_EUROPE = "protestant_europe"
    CATHOLIC_EUROPE   = "catholic_europe"
    ENGLISH_SPEAKING  = "english_speaking"
    LATIN_AMERICA     = "latin_america"
    POST_COMMUNIST    = "post_communist"
    SOUTH_ASIA        = "south_asia"
    AFRICAN_ISLAMIC   = "african_islamic"
    CONFUCIAN         = "confucian"
    ORTHODOX          = "orthodox"

class ContextProfileInferenceLevel(str, Enum):
    """Tracking точности ContextProfile."""
    INFERRED_BASIC = "inferred_basic"   # Фаза 0: из метаданных статьи
    ENRICHED       = "enriched"         # Фаза 12: с WGI/WVS данными
    MANUAL         = "manual"           # Задан экспертом

class ContextProfile(BaseModel):
    """
    Профиль контекста — используется для source (статья) и target (симуляция).
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    # Идентификация
    context_id: str                  # ISO country code или custom region ID
    context_label: str

    # inference tracking
    inference_level: ContextProfileInferenceLevel = ContextProfileInferenceLevel.INFERRED_BASIC
    data_sources: list[str] = []     # "wgi", "wvs", "wdi", "openalex_affiliations"

    # Экономика
    income_level: IncomeLevel
    gdp_per_capita: float | None = None
    economic_openness: float | None = None
    informal_economy_share: float | None = None

    # Институты (WGI, [0,1] normalized)
    institutional_quality: float | None = None
    corruption_level: float | None = None
    state_capacity: float | None = None

    # Социология (WVS, [0,1] normalized)
    social_trust: float | None = None
    cultural_cluster: CulturalCluster | None = None
    post_conflict: bool = False
    post_communist: bool = False

    # Время
    time_period: str | None = None

    def distance_to(self, other: "ContextProfile") -> float:
        """
        Нормированное расстояние между профилями [0, ~2.0].
        Используется для confidence penalty в транспортировке.
        """
        numeric_dims: list[tuple[str, float]] = [
            ("institutional_quality", 2.0),
            ("social_trust", 1.5),
            ("corruption_level", 1.0),
            ("state_capacity", 1.0),
            ("economic_openness", 0.5),
        ]

        total_dist = 0.0
        total_weight = 0.0

        # Income level — ординальная дистанция
        income_order = {
            IncomeLevel.LOW: 0, IncomeLevel.LOWER_MIDDLE: 1,
            IncomeLevel.UPPER_MIDDLE: 2, IncomeLevel.HIGH: 3,
        }
        if self.income_level is not None and other.income_level is not None:
            income_dist = abs(income_order[self.income_level] - income_order[other.income_level]) / 3.0
            total_dist += 1.5 * income_dist
            total_weight += 1.5

        # Numeric dimensions
        for dim, weight in numeric_dims:
            v_self = getattr(self, dim, None)
            v_other = getattr(other, dim, None)
            if v_self is not None and v_other is not None:
                total_dist += weight * abs(v_self - v_other)
                total_weight += weight

        # Categorical penalties
        if (self.cultural_cluster is not None
                and other.cultural_cluster is not None
                and self.cultural_cluster != other.cultural_cluster):
            total_dist += 1.5
            total_weight += 1.5

        if self.post_communist != other.post_communist:
            total_dist += 2.0
            total_weight += 2.0

        if self.post_conflict != other.post_conflict:
            total_dist += 1.5
            total_weight += 1.5

        return total_dist / total_weight if total_weight > 0 else 0.0

    def enrich_from_datasources(
        self,
        wgi: "WGIClient",
        wvs: "WVSConnector",
        wdi: "WDIClient",
        year: int | None = None,
    ) -> "ContextProfile":
        """Обогащает INFERRED_BASIC профиль до ENRICHED.

        WVS использует wave-based temporal matching.
        WVS не публикуется ежегодно — данные привязаны к волнам.
        Wave 7 (2017-2022): разные страны опрашивались в разные годы.
        """
        year = year or (int(self.time_period.split("-")[0]) if self.time_period else 2020)

        wgi_data = wgi.get_indicators(self.context_id, year)
        # wave-based lookup вместо exact year
        wvs_survey_year, wvs_wave = wvs.find_closest_in_wave(
            self.context_id, year, max_distance_years=3,
        )
        wvs_data = wvs.get_indicators(
            self.context_id,
            survey_year=wvs_survey_year,  # может быть None → graceful fallback
        )
        wdi_data = wdi.get_indicators(self.context_id, year)

        return self.model_copy(update={
            "inference_level": ContextProfileInferenceLevel.ENRICHED,
            "data_sources": list(set(self.data_sources + ["wgi", "wvs", "wdi"])),
            "institutional_quality": wgi_data.get("institutional_quality", self.institutional_quality),
            "corruption_level": wgi_data.get("corruption_level", self.corruption_level),
            "state_capacity": wgi_data.get("state_capacity", self.state_capacity),
            "social_trust": wvs_data.get("social_trust", self.social_trust),
            "cultural_cluster": wvs_data.get("cultural_cluster", self.cultural_cluster),
            "gdp_per_capita": wdi_data.get("gdp_per_capita", self.gdp_per_capita),
            "economic_openness": wdi_data.get("economic_openness", self.economic_openness),
        })
```

### 12.3 Автоматическое построение S-диаграммы

```python
# ir/analytics/transportability.py (продолжение)

CONTEXT_VARIABLE_SENSITIVITY: dict[str, list[str]] = {
    "institutional_quality": [
        "tax_compliance", "corruption_level", "policy_effectiveness",
        "contract_enforcement", "public_service_quality",
    ],
    "social_trust": [
        "collective_action_outcome", "cooperation_rate", "civic_participation",
        "social_capital", "compliance_voluntary",
    ],
    "income_level": [
        "consumption_response", "fiscal_multiplier", "human_capital_investment",
        "credit_access", "savings_rate",
    ],
    "economic_openness": [
        "trade_elasticity", "exchange_rate_pass_through", "capital_flow",
    ],
    "post_communist": [
        "institutional_quality", "state_capacity", "corruption_level",
        "market_competition", "property_rights",
    ],
    "post_conflict": [
        "state_capacity", "institutional_quality", "investment_rate",
        "human_capital", "migration_rate",
    ],
}

THRESHOLD_FOR_S_NODE = 0.2

class SNodeOrigin(str, Enum):
    """Откуда возник S-узел."""
    CONTEXT_DELTA = "context_delta"     # Различие контекстов (социо-экономическое)
    LEGAL         = "legal"             # Юридическое ограничение
    DATA_MISMATCH = "data_mismatch"     # Несовпадение доступных данных

class SNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_variable: str
    context_dimension: str
    source_value: float | str
    target_value: float | str
    delta: float
    severity: str                    # "low" | "medium" | "high"
    origin: SNodeOrigin = SNodeOrigin.CONTEXT_DELTA  # источник S-узла
    legal_constraint_id: str | None = None           # ref на LegalConstraint если origin=LEGAL

class SelectionDiagram(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_graph: CausalGraphModel
    s_nodes: list[SNode]
    source_context: ContextProfile
    target_context: ContextProfile
    context_distance: float


def build_selection_diagram(
    source_context: ContextProfile,
    target_context: ContextProfile,
    causal_graph: CausalGraphModel,
) -> SelectionDiagram:
    """Автоматически строит SelectionDiagram через сравнение контекстов."""

    graph_variables = set(causal_graph.nodes)
    s_nodes = []

    # Числовые измерения
    for dim, affected_variables in CONTEXT_VARIABLE_SENSITIVITY.items():
        src_val = _get_context_numeric(source_context, dim)
        tgt_val = _get_context_numeric(target_context, dim)

        if src_val is None or tgt_val is None:
            continue

        delta = abs(src_val - tgt_val)
        if delta < THRESHOLD_FOR_S_NODE:
            continue

        for var in affected_variables:
            if var in graph_variables:
                severity = "high" if delta > 0.5 else ("medium" if delta > 0.3 else "low")
                s_nodes.append(SNode(
                    target_variable=var,
                    context_dimension=dim,
                    source_value=src_val,
                    target_value=tgt_val,
                    delta=delta,
                    severity=severity,
                ))

    # Boolean измерения (post_communist, post_conflict)
    for bool_dim in ["post_communist", "post_conflict"]:
        src_val = getattr(source_context, bool_dim, False)
        tgt_val = getattr(target_context, bool_dim, False)
        if src_val != tgt_val:
            for var in CONTEXT_VARIABLE_SENSITIVITY.get(bool_dim, []):
                if var in graph_variables:
                    s_nodes.append(SNode(
                        target_variable=var,
                        context_dimension=bool_dim,
                        source_value=str(src_val),
                        target_value=str(tgt_val),
                        delta=1.0,
                        severity="high",
                    ))

    distance = source_context.distance_to(target_context)

    return SelectionDiagram(
        base_graph=causal_graph,
        s_nodes=s_nodes,
        source_context=source_context,
        target_context=target_context,
        context_distance=distance,
    )


def _get_context_numeric(ctx: ContextProfile, dim: str) -> float | None:
    """Извлекает числовое значение из ContextProfile."""
    if dim == "income_level":
        order = {IncomeLevel.LOW: 0.0, IncomeLevel.LOWER_MIDDLE: 0.33,
                 IncomeLevel.UPPER_MIDDLE: 0.67, IncomeLevel.HIGH: 1.0}
        return order.get(ctx.income_level)
    return getattr(ctx, dim, None)
```

### 12.4 Simplified TR-алгоритм

```python
# foundry/methods/catalog/causal/transport_check.py

class TransportabilityStatus(str, Enum):
    DIRECT            = "direct"
    TRANSPORTABLE     = "transportable"
    NON_TRANSPORTABLE = "non_transportable"

class StratificationVariable(BaseModel):
    """Переменная стратификации с ролью — определяет формулу P*(Z) vs P*(Z|X)."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    role: SNodeRole                   # PRE_TREATMENT_COVARIATE → P*(z), MEDIATOR → P*(z|x)
    requires_conditional: bool        # True для медиаторов (Pearl & Bareinboim 2011)
    condition_on_treatment: str | None = None  # treatment variable name если requires_conditional

class TransportFormula(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    formula_str: str
    stratification_variables: list[str]        # имена (backward-compatible)
    stratification_details: list[StratificationVariable] = []  # роли + condition_on
    source_quantities: list[str]
    target_quantities: list[str]
    adjustment_type: str              # "stratification" | "direct"

    def requires_target_data(self) -> bool:
        return len(self.target_quantities) > 0

class TransportabilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    query: str                        # P*(Y|do(X))

    status: TransportabilityStatus
    transport_formula: TransportFormula | None = None
    blocking_s_nodes: list[SNode] = []

    # Confidence
    base_confidence: float
    context_distance_penalty: float
    data_availability_penalty: float
    final_confidence: float

    # scope tracking
    algorithm_version: str = "simplified_tr_v2"  # Явная версия алгоритма
    unsupported_cases: list[str] = []   # Случаи вне scope Simplified TR

    # Three-Graph Closure
    feasible: bool = True               # False при HARD legal constraint
    hard_legal_constraints: list[str] = []  # constraint_ids блокирующих ограничений
    data_gaps: list[dict] = []          # Serialized DataGap objects
    p_star_values: dict[str, dict] = {} # canonical_var → serialized PStarZResult
    legal_s_nodes: list[dict] = []      # S-узлы от Legal Graph
    resolution_rounds: int = 1          # Сколько раундов потребовалось для сходимости
    proxy_penalties: dict[str, float] = {}  # var → penalty за использование прокси

    # Рекомендации
    warnings: list[str] = []
    required_target_data: list[str] = []

    # Lineage
    selection_diagram_ref: str = ""
    source_context_id: str
    target_context_id: str


@foundry_method(
    namespace="causal.transport",
    version="1.0.0",
    tags={"causal", "transportability"},
)
class CheckTransportability:
    """
    Simplified TR Algorithm.

    Покрывает:
    ✓ Нет S-узлов → DIRECT
    ✓ S-узел на переменной Z, не являющейся предком X → устраним
    ✓ S-узел на медиаторе Z → backdoor adjustment через Z
    ✓ S-узел блокирует все пути → NON_TRANSPORTABLE

    НЕ покрывает (→ NON_TRANSPORTABLE + unsupported_cases):
    ✗ Front-door adjustment
    ✗ Правила 2, 3 do-calculus
    ✗ C-component factorization
    ✗ Рекурсивная деривация
    """
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.DETERMINISTIC

    @staticmethod
    def pure_step(state: dict[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:

        selection_diagram = SelectionDiagram.model_validate(state["selection_diagram"])
        query_treatment = state["query_treatment"]
        query_outcome = state["query_outcome"]

        s_nodes = selection_diagram.s_nodes
        graph = selection_diagram.base_graph

        # Шаг 1: Нет S-узлов
        if not s_nodes:
            result = TransportabilityResult(
                query=f"P*({query_outcome}|do({query_treatment}))",
                status=TransportabilityStatus.DIRECT,
                base_confidence=1.0,
                context_distance_penalty=0.0,
                data_availability_penalty=0.0,
                final_confidence=1.0,
                source_context_id=selection_diagram.source_context.context_id,
                target_context_id=selection_diagram.target_context.context_id,
            )
            return {"transport_result": result.model_dump(mode="json")}

        # Шаг 2: Попытка устранить S-узлы (role-aware elimination)
        rx_graph, node_map = graph.to_rustworkx()
        residual_s_nodes = []
        elimination_results: list[EliminationResult] = []
        unsupported_cases = []

        for s_node in s_nodes:
            var = s_node.target_variable
            elim = _try_eliminate_s_node_simplified(
                var, rx_graph, node_map, query_treatment, query_outcome
            )
            if elim.can_eliminate:
                if elim.adj_var:
                    elimination_results.append(elim)
            elif elim.method == "collider_selection_bias":
                # коллайдер → selection bias, НЕЛЬЗЯ обуславливать
                unsupported_cases.append(
                    f"S-node on {var}: collider (selection bias). "
                    f"Conditioning would open spurious path."
                )
                residual_s_nodes.append(s_node)
            elif elim.method == "needs_advanced_tr":
                unsupported_cases.append(
                    f"S-node on {var}: requires do-calculus rule 2/3 or front-door"
                )
                residual_s_nodes.append(s_node)
            else:
                residual_s_nodes.append(s_node)

        # Проверка бидирекциональных рёбер (скрытые конфаундеры)
        for elim in elimination_results:
            if elim.adj_var and _has_bidirectional_edge(
                rx_graph, node_map, query_treatment, elim.adj_var
            ):
                unsupported_cases.append(
                    f"Unobserved confounder between {query_treatment} and "
                    f"{elim.adj_var}: backdoor adjustment invalid. "
                    f"Requires front-door or IV (Phase 12b)."
                )
                # Downgrade to residual
                residual_s_nodes.append(
                    next(s for s in s_nodes if s.target_variable == elim.adj_var)
                )
                elimination_results.remove(elim)

        # Результат
        dist = selection_diagram.context_distance

        if residual_s_nodes:
            result = TransportabilityResult(
                query=f"P*({query_outcome}|do({query_treatment}))",
                status=TransportabilityStatus.NON_TRANSPORTABLE,
                blocking_s_nodes=residual_s_nodes,
                base_confidence=0.0,
                context_distance_penalty=0.0,
                data_availability_penalty=0.0,
                final_confidence=0.0,
                algorithm_version="simplified_tr_v2",
                unsupported_cases=unsupported_cases,
                warnings=[
                    f"Effect not transportable. Blocking S-nodes: "
                    f"{[n.target_variable for n in residual_s_nodes]}",
                    "Note: Simplified TR may classify as NON_TRANSPORTABLE "
                    "cases that full do-calculus could resolve. "
                    "Consider manual review." if unsupported_cases else "",
                ],
                required_target_data=[n.target_variable for n in residual_s_nodes],
                source_context_id=selection_diagram.source_context.context_id,
                target_context_id=selection_diagram.target_context.context_id,
            )
        else:
            # CRITICAL FIX: target_quantities зависят от роли S-узла
            # Медиатор → P*(z|x) (условная), Ковариата → P*(z) (маргинальная)
            adjustment_vars = [e.adj_var for e in elimination_results]
            target_quantities = []
            for elim in elimination_results:
                z = elim.adj_var
                if elim.requires_conditional:
                    # Медиатор: Z зависит от X, нужна P*(z|x)
                    target_quantities.append(
                        f"P*({z}|{query_treatment})"
                    )
                else:
                    # Pre-treatment covariate: P*(z) маргинальная
                    target_quantities.append(f"P*({z})")

            # Построить stratification_details с ролями для ResolutionLoop
            strat_details = []
            for elim in elimination_results:
                strat_details.append(StratificationVariable(
                    name=elim.adj_var,
                    role=elim.role,
                    requires_conditional=elim.requires_conditional,
                    condition_on_treatment=query_treatment if elim.requires_conditional else None,
                ))

            formula = TransportFormula(
                formula_str=_build_formula_str(query_outcome, query_treatment, adjustment_vars),
                stratification_variables=adjustment_vars,
                stratification_details=strat_details,
                source_quantities=[
                    f"P({query_outcome}|do({query_treatment}),{z})"
                    for z in adjustment_vars
                ] or [f"P({query_outcome}|do({query_treatment}))"],
                target_quantities=target_quantities,
                adjustment_type="stratification" if adjustment_vars else "direct",
            )

            conf = _compute_final_confidence(1.0, dist, formula.target_quantities)

            result = TransportabilityResult(
                query=f"P*({query_outcome}|do({query_treatment}))",
                status=TransportabilityStatus.TRANSPORTABLE,
                transport_formula=formula,
                base_confidence=1.0,
                context_distance_penalty=min(dist * 0.3, 0.5),
                data_availability_penalty=len(formula.target_quantities) * 0.05,
                final_confidence=conf,
                algorithm_version="simplified_tr_v2",
                required_target_data=formula.target_quantities,
                source_context_id=selection_diagram.source_context.context_id,
                target_context_id=selection_diagram.target_context.context_id,
            )

        return {"transport_result": result.model_dump(mode="json")}


class SNodeRole(str, Enum):
    """Роль S-узла определяет формулу переноса."""
    PRE_TREATMENT_COVARIATE = "pre_treatment_covariate"  # Z → X, Z → Y
    MEDIATOR                = "mediator"                 # X → Z → Y
    COLLIDER                = "collider"                 # X → Z ← Y (selection bias!)
    INSTRUMENT              = "instrument"               # Z → X (no direct Z → Y)

class EliminationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    can_eliminate: bool
    method: str
    adj_var: str | None = None
    role: SNodeRole | None = None
    # медиатор требует P*(z|x), ковариата — P*(z)
    requires_conditional: bool = False


def _try_eliminate_s_node_simplified(
    s_var: str,
    rx_graph: "rx.PyDiGraph",
    node_map: dict[str, int],
    treatment: str,
    outcome: str,
) -> EliminationResult:
    """
    Simplified TR elimination rules (rustworkx implementation):

    1. S-var не предок treatment и не на всех каузальных путях → безопасно устранить
    2. S-var — pre-treatment covariate (конфаундер) → backdoor adjustment, P*(z)
    3. S-var — медиатор (X→Z→Y) → stratification, но P*(z|x) (условная!)
    4. S-var — коллайдер (X→Z←Y) → CANNOT ELIMINATE (selection bias)
    5. Иначе → needs_advanced_tr

    КРИТИЧНОЕ ОТЛИЧИЕ: Формула переноса для медиатора:
      P*(Y|do(X)) = Σ_z P(Y|do(X),z) × P*(z|x)  [НЕ P*(z)!]
    Pearl & Bareinboim (2011): маргинальная P*(z) инвалидирует
    каузальный эффект при медиации, т.к. Z зависит от X.
    """
    import rustworkx as rx

    if s_var not in node_map or treatment not in node_map or outcome not in node_map:
        return EliminationResult(can_eliminate=False, method="node_not_found", role=None)

    s_idx = node_map[s_var]
    t_idx = node_map[treatment]
    o_idx = node_map[outcome]

    # Правило 0: проверка на коллайдер (selection bias check)
    if _is_collider(rx_graph, node_map, s_var, treatment, outcome):
        return EliminationResult(
            can_eliminate=False,
            method="collider_selection_bias",
            role=SNodeRole.COLLIDER,
        )

    # Правило 1: не предок treatment
    ancestors_of_treatment = rx.ancestors(rx_graph, t_idx)
    if s_idx not in ancestors_of_treatment and s_idx != t_idx:
        if not _is_on_all_causal_paths(rx_graph, node_map, treatment, outcome, s_var):
            return EliminationResult(
                can_eliminate=True, method="not_ancestor", role=None,
            )

    # Правило 2: pre-treatment covariate (конфаундер) → P*(z) маргинальная
    if _is_pre_treatment_covariate(rx_graph, node_map, s_var, treatment, outcome):
        return EliminationResult(
            can_eliminate=True,
            method="backdoor_adjustment",
            adj_var=s_var,
            role=SNodeRole.PRE_TREATMENT_COVARIATE,
            requires_conditional=False,  # P*(z) достаточно
        )

    # Правило 3: медиатор → P*(z|x) УСЛОВНАЯ (CRITICAL FIX)
    if _is_mediator(rx_graph, node_map, treatment, outcome, s_var):
        return EliminationResult(
            can_eliminate=True,
            method="mediator_stratification",
            adj_var=s_var,
            role=SNodeRole.MEDIATOR,
            requires_conditional=True,  # P*(z|x), NOT P*(z)!
        )

    # Правило 4: bidirectional check (FCI/PAG → hidden confounder)
    if _has_bidirectional_edge(rx_graph, node_map, treatment, s_var):
        return EliminationResult(
            can_eliminate=False,
            method="needs_advanced_tr",
            role=None,
        )

    return EliminationResult(
        can_eliminate=False,
        method="needs_advanced_tr",
        role=None,
    )


def _is_collider(
    G: "rx.PyDiGraph", node_map: dict[str, int],
    var: str, treatment: str, outcome: str,
) -> bool:
    """Проверяет, является ли var коллайдером между treatment и outcome.
    Коллайдер: и treatment, и outcome являются родителями var (X → Z ← Y).
    Обуславливание на коллайдер открывает spurious path (selection bias).
    """
    if var not in node_map:
        return False
    var_idx = node_map[var]
    # rustworkx: predecessor_indices возвращает список parent node indices
    predecessors = set(G.predecessor_indices(var_idx))
    return node_map.get(treatment) in predecessors and node_map.get(outcome) in predecessors


def _is_pre_treatment_covariate(
    G: "rx.PyDiGraph", node_map: dict[str, int],
    var: str, treatment: str, outcome: str,
) -> bool:
    """Проверяет: var → treatment И var → outcome (конфаундер / pre-treatment)."""
    import rustworkx as rx
    var_idx, t_idx = node_map[var], node_map[treatment]
    desc_of_var = rx.descendants(G, var_idx)
    desc_of_treatment = rx.descendants(G, t_idx)
    return (
        t_idx in desc_of_var
        and node_map[outcome] in desc_of_var
        and var_idx not in desc_of_treatment
    )


def _has_bidirectional_edge(
    G: "rx.PyDiGraph", node_map: dict[str, int],
    node_a: str, node_b: str,
) -> bool:
    """Проверяет наличие бидирекционального ребра (FCI/PAG).
    Бидирекциональное ребро = скрытый конфаундер U: node_a ← U → node_b.
    """
    a_idx, b_idx = node_map.get(node_a), node_map.get(node_b)
    if a_idx is None or b_idx is None:
        return False
    # Оба направления → бидирекциональное
    has_a_to_b = G.has_edge(a_idx, b_idx)
    has_b_to_a = G.has_edge(b_idx, a_idx)
    if has_a_to_b and has_b_to_a:
        return True
    # Check edge attribute for PAG representation
    if has_a_to_b:
        edge_data = G.get_edge_data(a_idx, b_idx)
        if isinstance(edge_data, dict) and edge_data.get("edge_type") == "bidirected":
            return True
    return False


def _compute_final_confidence(
    base: float, distance: float, target_quantities: list[str],
) -> float:
    """Мультипликативные штрафы вместо аддитивных."""
    # Дистанция: чем дальше контексты, тем больше затухание (max 50%)
    distance_factor = 1.0 - min(distance * 0.3, 0.5)
    # Каждая target quantity добавляет 5% мультипликативного штрафа
    data_factor = 0.95 ** len(target_quantities)
    return max(0.0, base * distance_factor * data_factor)
```

### 12.5 Тесты

```python
def test_direct_transport_no_s_nodes():
    """Одинаковые контексты → DIRECT, confidence=1.0."""
    ctx = ContextProfile(context_id="DE", context_label="Germany",
                         income_level=IncomeLevel.HIGH,
                         institutional_quality=0.8)
    diagram = build_selection_diagram(ctx, ctx, simple_dag)
    assert diagram.s_nodes == []
    result = CheckTransportability.pure_step(
        {"selection_diagram": diagram.model_dump(mode="json"),
         "query_treatment": "tax_rate", "query_outcome": "gdp_growth"}, {}
    )
    r = TransportabilityResult.model_validate(result["transport_result"])
    assert r.status == TransportabilityStatus.DIRECT
    assert r.final_confidence == 1.0

def test_s_nodes_generated_for_institutional_gap():
    """DE (inst=0.8) vs UA (inst=0.35) → S-узлы на institution-sensitive vars."""
    src = ContextProfile(context_id="DE", income_level=IncomeLevel.HIGH,
                         institutional_quality=0.8, context_label="DE")
    tgt = ContextProfile(context_id="UA", income_level=IncomeLevel.LOWER_MIDDLE,
                         institutional_quality=0.35, context_label="UA",
                         post_communist=True)
    diagram = build_selection_diagram(src, tgt, tax_compliance_dag)
    s_var_names = [n.target_variable for n in diagram.s_nodes]
    assert "tax_compliance" in s_var_names

def test_confidence_penalty_increases_with_distance():
    """Большая дистанция контекстов → меньший final_confidence."""
    close_result = _run_transport(src_close, target)
    far_result = _run_transport(src_far, target)
    assert far_result.final_confidence < close_result.final_confidence

def test_post_communist_penalty():
    """Post-communist vs western → большой context_distance."""
    src = ContextProfile(context_id="DE", context_label="DE",
                         income_level=IncomeLevel.HIGH, post_communist=False)
    tgt = ContextProfile(context_id="UA", context_label="UA",
                         income_level=IncomeLevel.LOWER_MIDDLE, post_communist=True)
    assert src.distance_to(tgt) > 0.4

def test_simplified_tr_scope_tracking():
    """unsupported_cases populated when advanced TR needed."""
    # Create case where front-door would work but simplified can't
    result = _run_complex_transport(...)
    assert result.status == TransportabilityStatus.NON_TRANSPORTABLE
    assert len(result.unsupported_cases) > 0
    assert "simplified_tr_v2" == result.algorithm_version

def test_context_profile_enrichment():
    """INFERRED_BASIC → ENRICHED with datasources."""
    basic = ContextProfile(
        context_id="DE", context_label="Germany",
        income_level=IncomeLevel.HIGH,
        inference_level=ContextProfileInferenceLevel.INFERRED_BASIC,
    )
    enriched = basic.enrich_from_datasources(wgi_client, wvs_client, wdi_client, year=2020)
    assert enriched.inference_level == ContextProfileInferenceLevel.ENRICHED
    assert enriched.institutional_quality is not None
    assert "wgi" in enriched.data_sources


# ─── Three-Graph Closure Tests ───

def test_resolution_loop_converges():
    """Resolution loop сходится за ≤3 раунда."""
    loop = TransportabilityResolutionLoop(skg, dataset_registry, legal_bridge)
    result = loop.resolve(src_de, tgt_ua, tax_dag, "tax_rate", "tax_compliance")
    assert result.resolution_rounds <= 3
    assert result.feasible is True

def test_hard_legal_constraint_blocks_transport():
    """Unconstitutional policy → feasible=False, confidence=0."""
    loop = TransportabilityResolutionLoop(skg, dataset_registry, legal_bridge)
    result = loop.resolve(
        src_de, tgt_ua, tax_dag, "tax_rate", "tax_compliance",
        policy_spec={"domain": "tax_policy", "retroactive": True},
    )
    assert result.feasible is False
    assert result.final_confidence == 0.0
    assert len(result.hard_legal_constraints) > 0

def test_legal_constraint_adds_s_node():
    """Transition period requirement → S-node with origin=LEGAL."""
    loop = TransportabilityResolutionLoop(skg, dataset_registry, legal_bridge)
    result = loop.resolve(
        src_pl, tgt_ua, tax_dag, "tax_rate", "tax_compliance",
        policy_spec={"domain": "tax_policy", "transition_period": "6mo"},
    )
    legal_nodes = [s for s in result.legal_s_nodes]
    assert len(legal_nodes) > 0

def test_data_gap_explicit_when_no_dataset():
    """Missing P*(Z) → DataGap с proxy suggestions."""
    loop = TransportabilityResolutionLoop(skg, dataset_registry_missing, legal_bridge)
    result = loop.resolve(src_de, tgt_ua, tax_dag, "tax_rate", "tax_compliance")
    assert len(result.data_gaps) > 0
    gap = DataGap.model_validate(result.data_gaps[0])
    assert gap.required_variable == "institutional_quality"
    assert len(gap.available_proxies) > 0

def test_proxy_penalty_context_dependent():
    """CPI→inst_quality прокси штраф зависит от региона."""
    chain_eu = resolve_proxy("institutional_quality", "DE", dataset_registry, skg)
    chain_ua = resolve_proxy("institutional_quality", "UA", dataset_registry, skg)
    # Post-communist context → larger adjustment
    assert chain_ua.proxies[0].context_adjustment < chain_eu.proxies[0].context_adjustment

def test_full_lineage_across_three_graphs():
    """ATE lineage включает article + dataset + legal ref."""
    loop = TransportabilityResolutionLoop(skg, dataset_registry, legal_bridge)
    result = loop.resolve(
        src_pl, tgt_ua, tax_dag, "tax_rate", "tax_compliance",
        policy_spec={"domain": "tax_policy"},
    )
    # P*(Z) linked to specific dataset
    assert len(result.p_star_values) > 0
    for var, pz in result.p_star_values.items():
        pz_obj = PStarZResult.model_validate(pz)
        assert pz_obj.dataset_id is not None
    # Legal constraints linked to specific НПА
    if result.legal_s_nodes:
        assert any(
            s.get("legal_constraint_id") is not None
            for s in result.legal_s_nodes
        )

def test_dataset_registry_find_variable():
    """DatasetRegistry находит WGI для institutional_quality, UA."""
    matches = dataset_registry.find_datasets_for_variable(
        "institutional_quality", "UA", (2020, 2024),
    )
    assert len(matches) > 0
    assert matches[0].coverage_match in ("full", "partial")
    # Прямые совпадения идут перед прокси
    direct = [m for m in matches if not m.is_proxy]
    proxy = [m for m in matches if m.is_proxy]
    if direct and proxy:
        assert matches.index(direct[0]) < matches.index(proxy[0])
```

### 12.6 Definition of Done — Фаза 12

- [ ] `ContextProfile` с `distance_to()` — тест: post-communist penalty корректен
- [ ] `inference_level` tracking — INFERRED_BASIC vs ENRICHED
- [ ] `enrich_from_datasources()` — WGI/WVS/WDI integration
- [ ] `build_selection_diagram()` автоматически генерирует S-узлы из delta > 0.2
- [ ] `CheckTransportability`: DIRECT / TRANSPORTABLE / NON_TRANSPORTABLE
- [ ] `algorithm_version="simplified_tr_v2"`, `unsupported_cases` populated
- [ ] Явно документировано что покрывается и не покрывается
- [ ] `TransportabilityResult` — JSON Schema snapshot
- [ ] `RunTransportabilityNode` обрабатывает статьи без source_context (graceful skip)
- [ ] `TransportabilityRequiredPass` интегрирован в governance (Подфаза 8B, после стабилизации ResolutionLoop)
- [ ] DecisionPacket `3.3` содержит `transportability_summary`
- [ ] `TransportabilityResolutionLoop` — итеративный resolver, max 3 раунда
- [ ] `DataGap` — explicit reporting: переменная + контекст + доступные прокси + impact
- [ ] `PStarZResult` — вычисленный P*(Z) с полным lineage (dataset_id, raw_var, proxy_chain)
- [ ] `SNode.origin` — различает `CONTEXT_DELTA`, `LEGAL`, `DATA_MISMATCH`
- [ ] Legal constraints: `HARD` → `feasible=False`, `SOFT` → дополнительные S-узлы
- [ ] `LegalToDAGMapping` с `requires_expert_review=True` для всех маппингов в MVP
- [ ] Прокси-штрафы контекстно-зависимые (не фиксированные константы)
- [ ] Pre-implementation survey: 30-50 policy questions → Simplified TR scope validation (ADR-0089)
- [ ] `ProxyValidityChecklist` — формальные условия для каждого прокси (ADR-0090)
- [ ] `PartialIdentificationResult` — Manski bounds fallback для NON_TRANSPORTABLE (ADR-0091)
- [ ] `compose_confidence_harmonic()` для proxy chains (ADR-0092)
- [ ] `AlignmentCertificationPolicy` реализован: typed certificates + `tau_min` (bounded 0.55..0.95) + `max_chain_length=5`
- [ ] Outer objective реализован: `coverage - lambda_conflict * irreducible_conflict_norm`
- [ ] Outer search bounded: `TAU_GRID=8`, `LAMBDA_GRID<=3`, `TYPE_CONFIGS_MAX=6`, `MAX_OUTER_SOLVES=48`, `MAX_OUTER_WALLTIME_SEC=3.0`
- [ ] При budget exhaustion: `outer_search_truncated=True` + `search_budget_exhausted` в events
- [ ] `assumes_time_stationarity` flag для lagged effects в transport path (ADR-0093)
- [ ] Golden test: DE→UA tax reform с legal constraint → resolution_rounds=2, legal_s_nodes populated
- [ ] Golden test: отсутствующий P*(Z) → DataGap с proxy suggestion
- [ ] Golden test: proxy с exclusion violation → `requires_expert_review=True`
- [ ] Golden test: NON_TRANSPORTABLE → Manski bounds с `is_informative` check
- [ ] Lineage через все три графа: ATE → article + dataset + НПА (полная цепочка)


---

## Фаза 13 — SCM + ABM bridge

**Длительность:** 2.5–3 недели | **Риск:** MEDIUM
**Предусловия:** Фаза 10, Фаза 11

### 13.1 Цель

Связать каузальные модели (macro-level) с агентными симуляциями (micro-level). Проверка: ABM emergence patterns согласуются с SCM causal effects.

### 13.2 IR: MacroVariableMapping

```python
# ir/analytics/abm_bridge.py

class AlignmentStatus(str, Enum):
    """Расширенный статус выравнивания SCM↔ABM."""
    CONSISTENT           = "consistent"            # |delta| < tolerance
    INCONSISTENT         = "inconsistent"           # |delta| >= tolerance, линейная зона
    NON_LINEAR_DIVERGENCE = "non_linear_divergence" # фазовый переход в ABM
    INSUFFICIENT_RUNS    = "insufficient_runs"      # Недостаточно ABM прогонов

class MacroMicroMapping(BaseModel):
    """Маппинг макропеременной SCM на ABM-агрегат."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    macro_variable: str              # Каноническое имя в CausalGraphModel
    abm_aggregation: str             # "mean(agent.income)" | "gini(agent.wealth)"
    aggregation_function: str        # "mean" | "median" | "gini" | "sum" | "count"
    agent_property: str              # "income" | "wealth" | "compliance"
    # tolerance зависит от дисперсии ABM-прогонов, не глобальная константа
    tolerance: float | None = None   # None → вычисляется автоматически
    tolerance_method: str = "adaptive"  # "adaptive" (2σ ABM variance) | "fixed"

class ABMAlignmentReport(BaseModel):
    """Расширен фазовыми переходами и адаптивной tolerance."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    mappings: list[MacroMicroMapping]
    alignment_results: dict[str, dict] = {}  # macro_var → {scm_effect, abm_effect, status, tolerance_used}
    overall_consistent: bool = False
    # phase transition detection
    phase_transitions: list[dict] = []  # [{variable, threshold_value, pre_regime, post_regime}]
    warnings: list[str] = []
```

### 13.3 Definition of Done — Фаза 13

- [ ] `MacroMicroMapping` — маппинг SCM ↔ ABM переменных
- [ ] `ABMAlignmentReport` — JSON Schema snapshot
- [ ] Adaptive tolerance (2σ ABM variance, не глобальная 0.2)
- [ ] Phase transition detection: `NON_LINEAR_DIVERGENCE` при резком скачке
- [ ] Широкий tolerance "consistent" — WARNING, не BLOCKER (риск: ABM alignment шумный)
- [ ] `RunABMConsistencyCheckNode` — scientist node

---

## Фаза 14 — CausalModelEnsemble и структурная неопределённость

**Длительность:** 2.5–3 недели | **Риск:** MEDIUM
**Предусловия:** Фаза 6/7, Фаза 10, Фаза 13 (optional)

### 14.1 IR: CausalModelEnsemble

```python
# ir/analytics/causal_ensemble.py

class EnsembleMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_ref: str                   # CAS ref на CausalGraphModel
    discovery_method: str            # "pcmci" | "pc" | "fci" | "ges"
    weight: float                    # Вес в ансамбле [0,1]
    bootstrap_stability: float       # Средняя stability рёбер

class CausalModelEnsemble(BaseModel):
    """Ансамбль каузальных моделей для structural uncertainty."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    members: list[EnsembleMember]
    consensus_graph_ref: str | None = None  # Граф из рёбер в ≥50% members
    edge_inclusion_frequency: dict[str, float] = {}  # "X→Y" → fraction of members

    def to_uncertainty_envelope(self, query_results: dict[str, list[float]]) -> "UncertaintyEnvelope":
        """
        Каждый member даёт оценку эффекта → distribution across members
        = structural uncertainty.
        """
        from polisyos.ir.analytics.uncertainty import (
            UncertaintyEnvelope, UncertaintySource,
            DistributionFamily, PropagationMethod, IntervalSemantics,
        )
        # Агрегация по всем members
        all_estimates = []
        for member_key, estimates in query_results.items():
            all_estimates.extend(estimates)

        if not all_estimates:
            return UncertaintyEnvelope(
                point_estimate=0.0,
                confidence_interval=(-1e12, 1e12),
                confidence_level=0.95,
                distribution_family=DistributionFamily.UNKNOWN,
                source=UncertaintySource.ENSEMBLE,
                propagation_method=PropagationMethod.NONE,
                interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
                is_heuristic_ci=True,
                gate_eligible=False,
            )

        import numpy as np
        arr = np.array(all_estimates)
        return UncertaintyEnvelope(
            point_estimate=float(np.median(arr)),
            confidence_interval=(float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))),
            confidence_level=0.95,
            distribution_family=DistributionFamily.BOOTSTRAP,
            source=UncertaintySource.ENSEMBLE,
            propagation_method=PropagationMethod.MONTE_CARLO,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            sample_size=len(all_estimates),
            is_heuristic_ci=False,
            gate_eligible=True,
        )
```

### 14.2 Definition of Done — Фаза 14

- [ ] `CausalModelEnsemble` — max 10 members (budget cap)
- [ ] `edge_inclusion_frequency` — рёбра в ≥50% members → consensus
- [ ] `to_uncertainty_envelope()` — совместим с существующим UncertaintyEnvelope
- [ ] Тест: 3 discovery methods на одних данных → ensemble captures structural uncertainty

---

## Фаза 15 — Context-Adaptive Parameter Registry + JAX Backend

**Длительность:** 3–4 недели
**Предусловия:** Фаза 0, Фаза 10 (hybrid SCM), Фаза 12
**Риск:** MEDIUM

### 15.1 Проблема и связь с Фазой 10

В v1.0 параметры из научных статей предполагались применимыми ко всем симуляциям. В реальности фискальный мультипликатор из Германии не применим к Украине без коррекции на контекст.

> **Hybrid design (Фаза 10 + 15):**
> - **Фаза 10** собирает `StructuralCausalModelSpec` с `MechanismSource` (DATA/LITERATURE/HYBRID)
> - **Фаза 15** добавляет контекстно-адаптивную выборку параметров и (опционально)
>   JAX/NumPyro backend для узлов с `source=LITERATURE_PRIOR` или `HYBRID`
>
> Фазы дополняют друг друга, а не конкурируют:
> - Фаза 10: **какие** механизмы + **откуда** параметры
> - Фаза 15: **адаптация** параметров к целевому контексту + **JAX simulation engine**

### 15.2 IR: ContextAdaptiveParameterBundle

```python
# ir/analytics/parameters.py

class ParameterApplicability(BaseModel):
    """Оценка применимости параметра к целевому контексту."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    parameter_id: str
    target_context_id: str
    transport_status: TransportabilityStatus
    transport_confidence: float
    context_distance: float
    is_applicable: bool
    adjustment_required: bool
    uncertainty_multiplier: float = 1.0  # Inflate CI при низком confidence
    recommended_value: float | None = None

class ContextAdaptiveParameterBundle(BaseModel):
    """Набор параметров для JAX-симуляции, адаптированных к target context."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    target_context: ContextProfile
    simulation_domain: str

    parameters: dict[str, EvidenceParameter]
    applicability: dict[str, ParameterApplicability]
    unsupported_parameters: list[str] = []

    skg_snapshot_ref: str = ""
    skg_version_id: int | None = None
    selection_timestamp: str = ""
```

### 15.3 Логика выбора параметра

```python
# academic/knowledge/parameter_selector.py

class ParameterSelector:

    def __init__(self, skg_store, transport_engine=None):
        self.skg = skg_store
        self.transport = transport_engine

    def select_for_context(
        self,
        parameter_name: str,
        target_context: ContextProfile,
        causal_graph: CausalGraphModel,
        min_transport_confidence: float = 0.3,
    ) -> tuple[EvidenceParameter | None, ParameterApplicability]:
        """
        Алгоритм:
        1. Найти все параметры с данным именем в SKG
        2. Для каждого вычислить transport_confidence к target_context
        3. Отфильтровать с confidence < min_transport_confidence
        4. Из оставшихся: выбрать с max(transport_confidence × evidence_weight)
        5. Если ни один не прошёл → вернуть None + warning

        uncertainty_multiplier = 1.0 + (1.0 - confidence) × 2.0
        При confidence=0.5 → multiplier=2.0 (CI удваивается).
        При confidence=0.9 → multiplier=1.2 (CI почти не меняется).
        """
        candidates = self.skg.query_parameters(parameter_name)
        if not candidates:
            return None, self._no_evidence(parameter_name, target_context)

        scored = []
        for param, source_context in candidates:
            if param.parameter_type != ParameterType.QUANTITATIVE:
                continue

            if source_context is None:
                conf = 0.3
                status = TransportabilityStatus.NON_TRANSPORTABLE
                dist = 1.0
            else:
                dist = source_context.distance_to(target_context)
                # Если дистанция мала — DIRECT, иначе полная проверка
                if dist < 0.1:
                    conf = 0.95
                    status = TransportabilityStatus.DIRECT
                else:
                    selection_diag = build_selection_diagram(
                        source_context, target_context, causal_graph
                    )
                    if not selection_diag.s_nodes:
                        conf = _compute_final_confidence(1.0, dist, [])
                        status = TransportabilityStatus.DIRECT
                    else:
                        # Simplified assessment based on distance
                        conf = max(0.0, 1.0 - dist * 0.5)
                        status = TransportabilityStatus.TRANSPORTABLE

            evidence_weight = EVIDENCE_WEIGHTS.get(param.evidence_strength, 0.3)
            score = conf * evidence_weight
            scored.append((score, conf, status, dist, param))

        # Фильтрация
        scored = [(s, c, st, d, p) for s, c, st, d, p in scored if c >= min_transport_confidence]

        if not scored:
            return None, self._low_confidence(parameter_name, target_context)

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_conf, best_status, best_dist, best_param = scored[0]

        uncertainty_multiplier = 1.0 + (1.0 - best_conf) * 2.0

        applicability = ParameterApplicability(
            parameter_id=best_param.name,
            target_context_id=target_context.context_id,
            transport_status=best_status,
            transport_confidence=best_conf,
            context_distance=best_dist,
            is_applicable=True,
            adjustment_required=(best_status == TransportabilityStatus.TRANSPORTABLE),
            uncertainty_multiplier=uncertainty_multiplier,
            recommended_value=best_param.value,
        )

        return best_param, applicability
```

### 15.4 Scientist Node: ResolveParametersNode

```python
# scientist/nodes/builtins/causal/resolve_parameters.py

class ResolveParametersNode:
    """
    Перед запуском JAX-симуляции разрешает все параметры из SKG
    с учётом target context.
    """

    @property
    def spec(self) -> NodeSpec:
        return NodeSpec(
            metadata=ComponentMetadata(
                name="resolve_parameters",
                version="1.0.0",
                description="Resolve simulation parameters from SKG for target context",
            ),
            state_reads=["target_context", "required_parameters", "skg_ref",
                         "causal_graph_ref"],
            state_writes=["parameter_bundle_ref"],
            produces=["ir.context_adaptive_parameter_bundle"],
        )

    def execute(self, ctx, state) -> NodeOutcome:
        target_context = ContextProfile.model_validate(state.params["target_context"])
        required_params = state.params.get("required_parameters", [])
        causal_graph = load_causal_graph_model(state["_store"], state["causal_graph_ref"])

        skg_store = load_skg_store(state.params.get("skg_ref"))
        selector = ParameterSelector(skg_store)

        parameters = {}
        applicability = {}
        unsupported = []

        for param_name in required_params:
            param, appl = selector.select_for_context(
                parameter_name=param_name,
                target_context=target_context,
                causal_graph=causal_graph,
            )
            if param is None:
                unsupported.append(param_name)
            else:
                parameters[param_name] = param
                applicability[param_name] = appl

        events = []
        if unsupported:
            events.append(NodeEvent(
                level="WARNING",
                code="PARAMS_WITHOUT_EVIDENCE",
                message=f"Parameters without literature support: {unsupported}",
            ))

        bundle = ContextAdaptiveParameterBundle(
            target_context=target_context,
            simulation_domain=state.params.get("domain", "unknown"),
            parameters=parameters,
            applicability=applicability,
            unsupported_parameters=unsupported,
            skg_snapshot_ref=state.params.get("skg_ref", ""),
            selection_timestamp=datetime.utcnow().isoformat(),
        )

        ref = persist_parameter_bundle(state["_store"], bundle)

        return NodeOutcome(
            status="ok" if not unsupported else "ok",
            state={"parameter_bundle_ref": ref},
            events=events,
        )
```

### 15.5 Definition of Done — Фаза 15

- [ ] `ParameterSelector.select_for_context()` — max(confidence × evidence_weight)
- [ ] Параметры с transport_confidence < 0.3 исключаются; fallback → warning
- [ ] `uncertainty_multiplier` корректно inflate CI: confidence=0.5 → multiplier=2.0
- [ ] `ContextAdaptiveParameterBundle` — JSON Schema snapshot
- [ ] `ResolveParametersNode` интегрирован в default workflow до JAX-шага
- [ ] Тест e2e: SKG → select fiscal_multiplier для UA → выбирает CEE-region статью

---

## 4. Сквозные слои

### 4.1 Архитектурные паттерны

### SL-1: Canonicalization Layer

Имена переменных в `CausalEdge`, `EvidenceParameter`, `ContextProfile` используют одни и те же канонические имена. `VariableCanonizer` — единственная точка нормализации, вызывается при записи в SKG и при создании `CausalEdge` из любого источника.

Иерархические имена (`gdp_growth.real`), детерминированный кэш, batch human review.

### SL-2: Lineage Chain

Полная цепочка provenance для любого результата. Lineage проходит через все три графа — SKG, Dataset Graph, Legal Graph:

```
OpenAlex Article
  → ArticleExtractionResult (CAS ref, InputRef: openalex_work)
    → SKGEdge (aggregated from N articles)
      → LiteratureCausalPrior (InputRef: skg_snapshot)
        → CausalGraphModel (reconciled, InputRef: literature_prior + data_graph)
          → StructuralCausalModelSpec (InputRef: graph)
            → CausalQueryResult (InputRef: scm_spec)
              → TransportabilityResolutionLoop:
                ├── SelectionDiagram (InputRef: source_context + target_context)
                │   ├── S-nodes from context delta
                │   └── S-nodes from Legal Graph (InputRef: legal_constraint_ids)
                ├── TransportFormula → required P*(Z)
                ├── P*(Z) values (InputRef: dataset_ids + raw_variables)
                │   └── ProxyChain if proxy used (InputRef: proxy_evidence)
                └── DataGaps (explicit: what's missing)
              → TransportabilityResult (InputRef: resolution_state)
                → ContextAdaptiveParameterBundle (InputRef: transport_results)
                  → JAX SimulationResult (InputRef: parameter_bundle)
                    → DecisionPacket (InputRef: all above)

Пример lineage для конкретного ATE:
  ATE = 0.73% [confidence: 0.54]
  ├── Source: Kowalski et al. (PL, 2019) [SKG: T13825]
  ├── Transport: Σ_Z P(e|do(t),Z)·P*(Z)
  │   ├── Z₁ = institutional_quality
  │   │   └── Data: WGI 2023, UA [Dataset: WB_WGI_2023, col: rl_est]
  │   └── Z₂ = informal_economy
  │       └── Data: StatUA 2022 [Dataset: STATUA_SE_2022] (proxy, penalty=-0.08)
  ├── Legal: Tax Code UA Art.58 → transition ≥6mo [Legal: L-UA-TAX-2010-ART58]
  └── Confidence decomposition:
      base=0.80, context_penalty=-0.18, proxy_penalty=-0.08, total=0.54
```

Каждый шаг хранит `inputs: list[InputRef]` — требование Закона E. Формат `InputRef` из `ir/artifacts/contracts.py`: `{artifact_id: ArtifactID, role: str}`.

### SL-3: Method Selection Diagnostics

```python
class MethodGapReport(BaseModel):
    """Формализованное описание недостающего метода в Foundry."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    required_properties: list[str]
    closest_existing_method: str
    why_insufficient: str
    suggested_method_type: str
    workaround: str | None = None
```

### SL-4: Three-Graph Closure

Сквозной паттерн, затрагивающий Фазы 0, 12, 15. **Полная архитектура** описана в Фазе 12, секция 12.0.

**Краткая суть:** три графа (SKG → `academic/`, Dataset Graph → `datasets/`, Legal Graph → `lex/`) — федерация поверх существующих модулей. Связи через `VariableCanonizer` (canonical names), `ContextProfile.context_id`, `InputRef` (lineage). `TransportabilityResolutionLoop` — query layer.

### 4.2 Тестирование

### SL-5: Canonical SCM Test Fixtures (ADR-0095)

Каузальный код невозможно тестировать без ground truth. Создаём 7 синтетических SCM-фикстур с аналитически известными ответами — единый набор для всех фаз.

```python
# tests/fixtures/causal_scm_fixtures.py

"""
7 канонических SCM для тестирования всего каузального пайплайна.
Каждая фикстура: (DAG, structural equations, N=5000 synthetic data, analytical ATE).
"""

# 1. FORK (common cause confounding)
# Z → X, Z → Y, no X→Y edge
# Analytical: ATE(X→Y) = 0 (confounded by Z, no true effect)
# Tests: backdoor adjustment, refutation should flag if naive regression used

# 2. CHAIN (mediator)
# X → M → Y
# Analytical: ATE(X→Y) = β_XM × β_MY
# Tests: front-door criterion, mediation analysis, simplified TR

# 3. COLLIDER (selection bias)
# X → Z ← Y (Z is collider)
# Analytical: conditioning on Z creates spurious X-Y association
# Tests: collider detection in governance, SUTVA check

# 4. INSTRUMENTAL_VARIABLE
# I → X → Y, U → X, U → Y (U latent)
# Analytical: ATE = Cov(I,Y)/Cov(I,X) (Wald estimator)
# Tests: IV identification, PAG with bidirectional edge

# 5. BACKDOOR_WITH_TRANSPORT
# Same as FORK but with S-node on Z
# Source: Z ~ N(0.5, 0.1), Target: Z ~ N(0.8, 0.1)
# Analytical: transported ATE requires P*(Z) reweighting
# Tests: Simplified TR, P*(Z) computation, proxy resolver

# 6. FRONT_DOOR (for Phase 12b testing)
# X → M → Y, U → X, U → Y (U latent)
# Analytical: ATE via front-door formula
# Tests: front-door identification (marks unsupported_cases in MVP)

# 7. DIAMOND (multiple paths)
# X → A → Y, X → B → Y
# Analytical: ATE = β_XA × β_AY + β_XB × β_BY
# Tests: multiple mediators, ensemble uncertainty

SCM_FIXTURES: dict[str, SCMFixture] = {
    "fork": SCMFixture(
        graph=CausalGraphModel(graph_type=GraphType.DAG, ...),
        equations={"X": "0.5*Z + ε_X", "Y": "0.7*Z + ε_Y", "Z": "ε_Z"},
        analytical_ate={"X→Y": 0.0},
        n_samples=5000,
        seed=42,
    ),
    # ... (all 7)
}

def generate_synthetic_data(fixture: SCMFixture) -> np.ndarray:
    """Deterministic data generation (Закон D: seed from fixture)."""
    ...
```

**Использование:** каждая фаза, начиная с Phase 2, обязана включать тесты на ≥3 фикстуры из набора.

| Фаза | Фикстуры для тестирования |
|------|--------------------------|
| 2 (DoWhy) | fork, chain, diamond |
| 3 (Refutation) | fork (должен обнаружить confounding), chain |
| 4 (Sensitivity) | fork (E-value > 1), instrumental_variable |
| 6-7 (Discovery) | fork, chain, diamond (восстановление DAG из данных) |
| 9 (Reconciliation) | fork + conflicting literature prior → Hodge diagnostics |
| 12 (Transport) | backdoor_with_transport (основной), front_door (unsupported_cases) |
| 14 (Ensemble) | diamond (structural uncertainty across methods) |

**DoWhy smoke tests (до Phase 2):** запустить все 7 фикстур через `DoWhy.identify() + estimate()` с text output. Верифицировать: fork → ATE ≈ 0, chain → ATE = β₁β₂, IV → Wald ≈ true. Это 2-3 дня работы, предотвращает неделю дебаггинга API breaking changes.

### SL-6: Integration Test Matrix

```
Уровень 1 — Unit Tests (каждая фаза):
  academic/batch/  → extraction quality, canonization, DDL correctness
  datasets/knowledge/  → variable alignment, proxy resolver
  lex/legal_evaluation/  → constraint severity, DAG mapping
  foundry/methods/catalog/causal/  → pure_step purity, determinism

Уровень 2 — Cross-Graph Tests (Фаза 12):
  SKG ↔ Dataset Graph:  transport formula → P*(Z) lookup → concrete value
  SKG ↔ Legal Graph:    boundary condition → legal constraint → S-node
  Dataset Graph ↔ Legal Graph:  data license → access check → allow/deny

Уровень 3 — Workflow Tests (scientist_causal_full):
  Full pipeline: PolicySpec → ... → DecisionPacket with transport lineage
  Regression: all existing scientist_default tests still pass

Уровень 4 — Governance Tests:
  New passes register in ValidationPipeline without breaking existing
  Profile coverage: FAST/MVP/STRICT with new passes

Уровень 5 — Replay Tests:
  Golden scenarios: DE→UA tax reform, PL→UA institutional quality
  Deterministic replay: same inputs → same TransportabilityResult
```

### 4.3 Операционные

### SL-7: Operational SLO

| Операция | SLO | Fallback |
|----------|-----|----------|
| OpenAlex API fetch | ≤10 req/sec, p99 < 2s | Exponential backoff, CAS кэш по DOI |
| WorldBankConnector.fetch() | p99 < 5s | `HTTPResilienceProfile` (уже реализован), local DuckDB cache |
| WVS connector | p99 < 3s (bulk download раз в wave) | Local CSV cache |
| Legal evaluation (lex/) | p99 < 1s (rule-based), < 10s (LLM) | Stub backend для CI |
| TransportabilityResolutionLoop | ≤3 раунда, total < 30s | Hard timeout, partial result с DataGaps |
| Variable alignment (semantic) | p99 < 500ms | Seed table fallback (no LLM) |
| gen_schema.py --check | < 10s для всех моделей | CI gate: fail = block merge |

### SL-8: Data Governance

Лицензии и доступ к данным как runtime gate (не post-hoc проверка):

```python
# datasets/knowledge/types.py — расширение DatasetSearchResult

class DataLicenseGate(str, Enum):
    OPEN       = "open"        # CC-BY, public domain → разрешено без ограничений
    REGISTERED = "registered"  # Требует регистрации API key → проверка credentials
    RESTRICTED = "restricted"  # NDA, proprietary → HARD constraint, нельзя использовать
    UNKNOWN    = "unknown"     # Лицензия неизвестна → WARNING, default RESTRICTED

# Интеграция с Legal Graph bridge:
# lex/legal_evaluation/transport_constraints.py проверяет:
# 1. Лицензия датасета (DataLicenseGate) — может ли система использовать данные
# 2. Правовой режим данных — публичные/конфиденциальные
# 3. Юрисдикционные ограничения — GDPR, data residency
```

---

## 5. Справочные материалы

## Реестр ADR

| ADR | Название | Фаза | Статус |
|-----|---------|------|--------|
| ADR-0025 | SCM = Structural Causal Model; synthetic_control для Abadie | 1 | ACCEPTED |
| ADR-0026 | NOTEARS excluded from default discovery | 1 | ACCEPTED |
| ADR-0027 | DoWhy как primary graph-based causal engine | 2 | ACCEPTED |
| ADR-0028 | Refutation mandatory для observational estimates | 3 | ACCEPTED |
| ADR-0029 | E-value ATE→RR conversion strategy; `conversion_method` записывается | 4 | ACCEPTED |
| ADR-0030 | CausalGraphModel: DAG/CPDAG/PAG через EdgeMark | 5 | ACCEPTED |
| ADR-0031 | Block bootstrap для time-series stability | 6 | ACCEPTED |
| ADR-0032 | LLM как интерпретатор контекста, не источник структуры; основной prior → SKG | 9 | ACCEPTED |
| ADR-0033 | SCM mechanisms: JSON-serializable families only (Закон H) | 10 | PROPOSED |
| ADR-0034 | Simplified TR (backdoor-only); полный do-calculus → Phase 12b backlog | 12 | PROPOSED |
| ADR-0035 | Двухшаговый скрининг: Haiku для screening, Sonnet для extraction | 0 | PROPOSED |
| ADR-0036 | VariableCanonizer — иерархические имена, детерминированный кэш, batch human review | 0 | PROPOSED |
| ADR-0037 | Закон L: рёбра без evidence support → `unsupported_by_evidence`, STRICT → FAIL | 5/8 | PROPOSED |
| ADR-0038 | Закон T: TransportabilityRequired для external CausalEffectReport | 8/12 | PROPOSED |
| ADR-0039 | ContextProfile.distance_to() + inference_level tracking | 12 | PROPOSED |
| ADR-0040 | max(transport_confidence × evidence_weight) как критерий выбора параметра | 15 | PROPOSED |
| ADR-0041 | Confidence aggregation: quality_score + replication_bonus (не weighted_mean) | 0 | PROPOSED |
| ADR-0042 | DuckDB для SKG storage (не SQLite) — по аналогии с graph_builder.py | 0 | PROPOSED |
| ADR-0043 | SKG versioning + retraction handling | 0 | PROPOSED |
| ADR-0044 | LITERATURE_FIRST — единственная reconciliation стратегия в MVP | 9 | PROPOSED |
| ADR-0045 | CausalEdge.compute_combined_confidence() = 1 - Π(1 - conf_i × w_i) | 5 | **SUPERSEDED by ADR-0064** |
| ADR-0046 | Three-Graph Closure: SKG + Dataset Graph + Legal Graph для вычислимой transportability | 0/12 | PROPOSED |
| ADR-0047 | Федерация графов с cross-references (не единый граф) — разные ритмы обновления | 0/12 | PROPOSED |
| ADR-0048 | TransportabilityResolutionLoop: max 3 раунда, convergence по stability S-nodes | 12 | PROPOSED |
| ADR-0049 | ConstraintSeverity: HARD блокирует транспортировку, SOFT → S-узлы | 12 | PROPOSED |
| ADR-0050 | Прокси-штрафы контекстно-зависимые через proxy_reliability(var, context), не фиксированные | 0/12 | PROPOSED |
| ADR-0051 | LegalToDAGMapping: 3 типа (effect_modifier, mechanism_node, intervention_redef); MVP: requires_expert_review=True | 0/12 | PROPOSED |
| ADR-0052 | DataGap как first-class object в TransportabilityResult | 12 | PROPOSED |
| ADR-0053 | Architecture Freeze: контракты на assembly points до Фазы 0 | −1 | PROPOSED |
| ADR-0054 | SKG поверх `academic/`, не отдельный `skg/` модуль | 0 | PROPOSED |
| ADR-0055 | Dataset Graph поверх `datasets/`, не отдельный модуль | 0 | PROPOSED |
| ADR-0056 | WGI/WDI через fabric `WorldBankConnector`, WVS — новый fabric connector | 0 | PROPOSED |
| ADR-0057 | Legal bridge через `lex/api.py`, не отдельный `legal_graph/` | 0/12 | PROPOSED |
| ADR-0058 | Compatibility Policy: only additive changes, schema 1.0→1.1, dual-read | all | PROPOSED |
| ADR-0059 | `scientist_causal_full` workflow параллельно с `scientist_default`, один cutover | all | PROPOSED |
| ADR-0060 | Migration Budget = 1: один controlled switch, нет feature flags | all | PROPOSED |
| ADR-0061 | Import gate как CI-контракт (`lint_foundry.py --strict` на каждый PR) | −1 | PROPOSED |
| ADR-0062 | `knowledge_snapshot_id` + обязательный `InputRef` на каждый graph-переход (lineage sync) | all | PROPOSED |
| ADR-0063 | Медиатор→P\*(z\|x) условная; ковариата→P\*(z) маргинальная (Pearl & Bareinboim 2011) | 12 | PROPOSED |
| ADR-0064 | `compute_combined_confidence()` = `1 - Π(1-conf_i)^w_i` (не `conf_i × w_i`) | 5 | PROPOSED |
| ADR-0065 | Cycle breaking через time-lag conversion (не удаление ребра) | 9 | PROPOSED |
| ADR-0066 | PAG→DAG projection: бидирекциональные→U-dummy nodes для dowhy.gcm | 10 | PROPOSED |
| ADR-0067 | Мультипликативные confidence penalties `Π(1-p_i)` вместо аддитивных | 12 | PROPOSED |
| ADR-0068 | WVS wave-based temporal matching `find_closest_in_wave(max_distance=3)` | 0/12 | PROPOSED |
| ADR-0069 | Collider (selection bias) check в `_try_eliminate_s_node_simplified` | 12 | PROPOSED |
| ADR-0070 | Bidirectional edge (U-node) → backdoor invalid → `needs_advanced_tr` | 12 | PROPOSED |
| ADR-0071 | `InterventionSpec` для soft/stochastic interventions (Legal Graph) | 11 | PROPOSED |
| ADR-0072 | Phase 12b via y0/causaleffect bridge, не from-scratch s-ID | 12b | PROPOSED |
| ADR-0073 | rustworkx вместо NetworkX для графовых вычислений | 0/9/12 | PROPOSED |
| ADR-0074 | NumPyro для байесовских SCM (Фаза 15) | 15 | PROPOSED |
| ADR-0075 | EconML/CATE: гетерогенные эффекты (DML, Causal Forests) | 2/11 | PROPOSED |
| ADR-0076 | KuzuDB для графовых запросов каузального графа (Cypher вместо NetworkX). Единый стек с существующим `fabric/world/materialize/kuzu.py` | 0/9/12 | PROPOSED |
| ADR-0077 | rustworkx для in-memory tight-loop алгоритмов (cycle breaking, resolution loop) | 9/12 | PROPOSED |
| ADR-0078 | Фаза 8 → 8A + 8B. TransportabilityRequiredPass перенесён в конец Фазы 12 (хронологический парадокс) | 8/12 | PROPOSED |
| ADR-0079 | Hybrid SCM: `MechanismSource` (DATA/LITERATURE/HYBRID/DEFAULT). Фаза 10 и 15 — дополняют, не конкурируют | 10/15 | PROPOSED |
| ADR-0080 | Tech consolidation: DoWhy+EconML (inference), tigramite+causal-learn (discovery), KuzuDB+rustworkx (graphs). NumPyro/y0/DAGMA → backlog | all | PROPOSED |
| ADR-0081 | `_break_cycles` time-aware: skip для PCMCI output (tags={"time-series"}) | 9 | PROPOSED |
| ADR-0082 | ABM bridge: adaptive tolerance (2σ variance) + `NON_LINEAR_DIVERGENCE` при фазовых переходах | 13 | PROPOSED |
| ADR-0083 | Resolution Loop proxy-depth guard: прокси-переменные не генерируют новые S-узлы | 12 | PROPOSED |
| ADR-0084 | Формальная грамматика канонических имён переменных (BNF + seed 200 vars) | 0/−1 | PROPOSED |
| ADR-0085 | PAG → Identification: CONSERVATIVE policy (id iff id во всех DAG ∈ PAG) | 7 | PROPOSED |
| ADR-0086 | SUTVA assumption check: `SutvaCheckPass` WARNING для market-wide policies; `sutva_assumed` flag | 8 | PROPOSED |
| ADR-0087 | LLM Prior Calibration: ceiling = 0.3, overlap discount = 0.05, не independent source | 9 | PROPOSED |
| ADR-0088 | Трёхслойное разделение конфликтов (L1/L2/L3) + Hodge-диагностики в reconciliation | 9 | PROPOSED |
| ADR-0089 | Pre-implementation survey: 30-50 policy questions → Simplified TR scope validation | 12 | PROPOSED |
| ADR-0090 | Формальные условия валидности прокси: relevance, exclusion, non-collider, completeness | 12 | PROPOSED |
| ADR-0091 | Partial identification bounds (Manski) как fallback для NON_TRANSPORTABLE | 12 | PROPOSED |
| ADR-0092 | Гармоническое среднее для confidence composition в proxy chains (из шифовой теории) | 12 | PROPOSED |
| ADR-0093 | Динамическая transportability: `assumes_time_stationarity` для lagged effects | 12 | PROPOSED |
| ADR-0094 | Confidence = ординальный quality score [0,1], не калиброванная вероятность | all | PROPOSED |
| ADR-0095 | Canonical SCM Test Fixtures: 7 синтетических SCM с analytical ground truth | all | PROPOSED |

---

## Карта рисков

| Риск | Вероятность | Воздействие | Митигация |
|------|-------------|-------------|-----------|
| DoWhy API breaking change в 0.12+ | Medium | High | Pin `dowhy>=0.11,<0.13`; adapter layer |
| Tigramite медленный на >30 переменных | High | Medium | Default `max_lag=5`, `par_corr`; timeout 10 min |
| E-value конвертация некорректна для continuous outcomes | Medium | High | `conversion_method` записывается; golden tests |
| LLM галлюцинирует рёбра в prior | High | Medium | Закон L блокирует unsupported в STRICT; SKG-first |
| SKG extraction quality < 70% precision | Medium | High | Validation set: 50 статей с ручной разметкой; acceptance > 0.75 |
| Variable name collisions при масштабировании | Medium | High | Иерархические имена, fuzzy match, batch human review |
| OpenAlex rate limits | High | Low | Rate limiter 10 req/s; backoff; CAS кэш |
| Simplified TR ложно классифицирует TRANSPORTABLE случаи | Low | High | Документировано в `unsupported_cases`; manual review warning |
| ContextProfile данные недоступны для target | Medium | High | Graceful degradation: unknown → max penalty; warning в DecisionPacket |
| PAG→DAG resolution теряет валидные структуры | Medium | Medium | Хранить PAG рядом с resolved DAG |
| Bootstrap stability × N алгоритмов = timeout | Medium | Medium | Budget cap: max 10 ensemble members |
| ABM → SCM macro alignment шумный | High | Medium | Широкий tolerance; WARNING, не BLOCKER |
| WGI/WVS/WDI bulk downloads устаревают | Low | Medium | Ежегодное обновление; версионирование в skg_versions |
| Variable alignment (canonical→dataset) ошибочен для нестандартных переменных | Medium | High | Seed таблица + semantic matching; requires_expert_review для новых маппингов |
| Dataset Graph deceptively complex — temporal/granularity mismatch | High | Medium | MVP: country-year granularity only; partial match → explicit penalty |
| Legal→DAG mapping некорректен без эксперта | High | High | MVP: `requires_expert_review=True` для всех; автоматический маппинг только в Phase 12b+ |
| ResolutionLoop не сходится (циклические зависимости между графами) | Low | High | Max 3 раунда hard limit; convergence по S-node stability; warning при max_rounds |
| Proxy composite (PCA/weighted mean) даёт некорректный P*(Z) | Medium | Medium | MVP: single best proxy only (composite в backlog); explicit penalty на каждый прокси-шаг |
| WGI/WVS data не покрывает target country | Medium | Medium | Graceful degradation: DataGap + max penalty; suggest nearest available data |
| Расхождение governance preflight и runtime governance | Medium | High | `run_governance` переводится на `ValidationPipeline` с реестром passes; убрать hardcoded selection |
| Поломка тестов/decision packet при расширении causal IR | Medium | High | Backward-compatible schema 1.0→1.1, dual-read, только optional поля |
| Неявные import errors при optional deps | Medium | Medium | Capability-detection + явный skip регистрации (паттерн `_registry_boot.py`) |
| Рассинхронизация lineage между graph-слоями | Medium | High | `knowledge_snapshot_id` + обязательный `InputRef` на каждый переход |
| Два параллельных workflow ломают CI/CD | Low | Medium | `scientist_causal_full` в staging, `scientist_default` в production; один cutover по trigger |
| Echo-chamber confidence (пересекающиеся источники) | Medium | Medium | `aggregate_edge_confidence` replication bonus; документировать риск; дедупликация datasets по provenance |
| PAG→DAG projection теряет информацию о неопределённости | Medium | Medium | Хранить оригинальный PAG; `orientation_uncertain` flag; sensitivity analysis в Фазе 4 |
| Условная P\*(z\|x) недоступна в target датасете | Medium | High | Fallback: маргинальная P\*(z) + explicit warning + доп. confidence penalty |
| y0 библиотека API нестабильна / breaking changes | Low | Medium | Pin version; adapter layer; fallback на causaleffect (R) |
| Time-lagged cycle conversion создаёт слишком много узлов | Low | Medium | Три жёстких лимита: `max_lag_depth=2`, `max_lagged_edges=10`, `max_cycles=8`; при превышении — fallback на удаление ребра + warning |
| PAG→DAG U-узлы дестабилизируют GCM fit | Medium | High | `sensitivity_to_latent` метрика; при high → маркировка unstable → route to Phase 12b |
| HybridSCMFit: конфликт DATA vs LITERATURE prior | Medium | Medium | Байесовский подход: литература=prior, данные=likelihood; при расхождении → WARNING |
| Resolution Loop осцилляция через proxy→S-node | Low | High | Proxy-depth guard: прокси-переменные не генерируют S-узлы (ADR-0083) |
| ABM фазовый переход маскируется средним | Medium | High | `NON_LINEAR_DIVERGENCE` detection; adaptive tolerance (2σ) |
| SUTVA violation для market-wide policies | High | High | `SutvaCheckPass` WARNING; ABM bridge (Phase 13) для partial capture; документировать assumption |
| LLM double-counting с SKG | High | Medium | LLM prior ceiling = 0.3 (ADR-0087); overlap discount; LLM ≠ independent source |
| Proxy variable violates exclusion restriction | Medium | High | `ProxyValidityChecklist` (ADR-0090); exclusion_check=False → expert review; non-collider check обязательна |
| Simplified TR покрывает < 50% реальных policy questions | Medium | High | Pre-implementation survey (ADR-0089); если backdoor < 60% → добавить IV в Phase 12a |
| PAG содержит >100 DAG → conservative identification отклоняет всё | Medium | Medium | Fallback на PROBABILISTIC (random sample 50 DAG); `id_confidence_under_pag` для ranking |
| Hodge decomposition выдаёт high irreducible conflict при мало источников | Low | Medium | Threshold only при ≥5 sources; иначе diagnostics=informational |
| Lagged effects transport assumes time-stationarity (нарушается в crises) | Medium | Medium | `assumes_time_stationarity` flag; WARNING для crisis periods; cross-validate with PCMCI |
| Manski bounds too wide to be informative | Medium | Low | `is_informative` check (width < 0.5); report bounds only if informative |
| Variable canonicalization grammar не покрывает domain-specific variables | High | Medium | Seed 200 vars; batch human review; extensible grammar; `pending_review` pipeline |

---

## Глоссарий

| Термин | Определение |
|--------|-------------|
| **SCM** | Structural Causal Model — модель причинно-следственных связей между переменными в виде DAG + набора структурных уравнений |
| **SKG** | Scientific Knowledge Graph — граф знаний, извлечённый из peer-reviewed литературы через OpenAlex. Хранится в DuckDB |
| **DAG** | Directed Acyclic Graph — ориентированный ацикличный граф, стандартное представление каузальной структуры |
| **CPDAG** | Completed Partially Directed Acyclic Graph — класс эквивалентности DAG'ов; результат PC/GES алгоритмов |
| **PAG** | Partial Ancestral Graph — обобщение CPDAG, допускающее латентные переменные; результат FCI алгоритма |
| **S-узел** | Selection node в SelectionDiagram — переменная, различающая source и target контексты. Генерируется из context delta, legal constraints или proxy resolver |
| **Transport formula** | Формула Bareinboim-Pearl для переноса каузального эффекта из source в target контекст: требует P*(Z) для каждой переменной Z, на которую влияет S-узел |
| **P*(Z)** | Распределение переменной Z в целевом контексте. Получается из Dataset Graph (напрямую или через прокси) |
| **DataGap** | Явное указание на отсутствие данных P*(Z) для конкретной переменной в target контексте |
| **Three-Graph Closure** | Замыкание трёх графов: SKG (что переносить) + Dataset Graph (чем вычислить P*(Z)) + Legal Graph (можно ли + юридические S-узлы) |
| **Simplified TR** | Упрощённый Transportability Resolution — только backdoor adjustment, без front-door или do-calculus. Scope MVP |
| **GCM** | Generalized Causal Model (dowhy.gcm) — модель с конкретными функциональными механизмами на каждом ребре DAG |
| **Foundry method** | Метод, зарегистрированный в PolicyOS Foundry: `pure_step`, `MethodSignature`, детерминированная или стохастическая тирада |
| **ValidatorPass** | Governance pass в `ValidationPipeline`: проверяет compliance (FAST/MVP/STRICT профили) |
| **Закон L** | Literature Gate: рёбра без evidence support блокируются в STRICT |
| **Закон T** | Transportability Required: external-context отчёты требуют прохождения TR |
| **Закон H** | Mechanism Homogeneity: SCM-механизмы должны быть JSON-serializable |
| **ContextProfile** | Профиль контекста (страна + год): income_level, institutional_quality, WGI/WVS индикаторы |
| **ResolutionLoop** | `TransportabilityResolutionLoop` — итеративный цикл с max 3 раунда, разрешающий зависимости между графами |
| **EdgeMark** | Тип конца ребра: TAIL (→), ARROW (←), CIRCLE (○). Позволяет представить DAG, CPDAG, PAG в единой модели |
| **SUTVA** | Stable Unit Treatment Value Assumption — эффект на единицу не зависит от treatment других единиц. Нарушается для market-wide policies |
| **Manski bounds** | Worst-case bounds для каузального эффекта без assumptions о confounding. Информативны когда width < 0.5 |
| **Hodge decomposition** | Разложение вектора evidence-конфликтов на patchable (exact), irreducible (harmonic), и cyclic inconsistency (coexact) компоненты |
| **Sheaf Laplacian** | Матричная реализация Hodge-декомпозиции: Δ₀ = D₀ᵀWD₀. Обобщение meta-analysis на неполные графы сравнения |
| **L1/L2/L3** | Три слоя каузального знания: L1 (identifiability — формула), L2 (estimation — числа), L3 (ontology — alignment переменных) |
| **Proxy validity** | Формальные условия для прокси-переменной: relevance, exclusion restriction, non-collider, completeness |
| **Partial identification** | Получение информативных bounds (интервалов) для каузального эффекта когда точечная идентификация невозможна |

---

## Справочник формул confidence

### Семантика confidence: ординальный quality score (ADR-0094)

**Архитектурное решение:** все confidence в системе — **ординальные quality scores [0,1]**, не калиброванные вероятности.

**Правила:**
1. **Сравнение**: для ranking (больше = лучше), не абсолютные thresholds
2. **Composition**: гармоническое среднее (ADR-0092), не произведение
3. **Aggregation**: Noisy-OR (ADR-0064) — каждый источник снижает остаточную неопределённость
4. **Interpretation**: HIGH (>0.8), MEDIUM (0.5-0.8), LOW (<0.5)
5. **НЕ probability**: `confidence = 0.7` ≠ «с вероятностью 70%»

### Индекс формул

| # | Формула | Назначение | Определена в |
|---|---------|------------|--------------|
| 1 | `aggregate_edge_confidence()` | Агрегация по статьям для ребра SKG | Фаза 0, секция 0.8 |
| 2 | `compute_combined_confidence()` | Noisy-OR по типам источников для CausalEdge | Фаза 5, секция 5.1 |
| 3 | Мультипликативные штрафы | Proxy/DataGap penalties | Фаза 12, секция 12.4 |
| 4 | Conflict budget λ | Trade-off coverage vs consistency | Фаза 9, секция 9.5 |

---

## Стратегия обработки ошибок внешних зависимостей

| Зависимость | Тип сбоя | Стратегия | Fallback |
|-------------|----------|-----------|----------|
| **OpenAlex API** | Rate limit (429) | Backoff + retry (max 3); 10 req/s limiter | CAS кэш по DOI; продолжение с имеющимися данными |
| **OpenAlex API** | Полная недоступность | Graceful degradation: SKG из кэша | Warning в `ExtractorStats`; skip batch |
| **World Bank API** (WGI/WDI) | Rate limit / timeout | `HTTPResilienceProfile` из fabric connector | Bulk download fallback; DuckDB таблицы |
| **WVS данные** | Wave отсутствует для target year | `find_closest_in_wave(max_distance=3)` | Nearest wave + explicit penalty |
| **DoWhy** | API breaking change | Pin `>=0.11,<0.13`; adapter layer | Переход на y0 (Phase 12b) |
| **Tigramite** | Timeout (>30 vars) | `max_lag=5`, `par_corr`; timeout 10 min | Fallback: PC algorithm (causal-learn) |
| **KuzuDB** | Материализация fails | Retry + rebuild mode | Fallback: rustworkx in-memory граф |
| **LLM extraction** | Галлюцинации / low quality | Двухшаговый скрининг; Закон L в STRICT | Skip article; log в `ExtractorStats` |
| **Legal KG** (lex/) | Constraint mapping некорректен | `requires_expert_review=True` (MVP) | Manual review queue; block auto-mapping |
| **ResolutionLoop** | Не сходится (осцилляция) | Max 3 раунда hard limit | Convergence по S-node stability; warning |

Общие принципы:
1. **Никогда не блокировать pipeline целиком** — отсутствие одного источника данных → DataGap + penalty, не crash
2. **Explicit reporting** — каждый fallback записывается в `TransportabilityResult` / `ExtractorStats`
3. **Версионирование** — `skg_version_id` и `knowledge_snapshot_id` для воспроизводимости при retry

---

## 6. Приложения

## Приложение A: Выравнивание с существующей кодовой базой

### A.1 Существующие типы, которые расширяются

| Тип | Файл | Расширение |
|-----|------|-----------|
| `CausalMethod` | `ir/analytics/causal.py` | +3 DoWhy methods (Фаза 2) |
| `CausalEffectReport` | `ir/analytics/causal.py` | +`identified_estimand`, `graph_ref`, `transport_result` |
| `UncertaintySource` | `ir/analytics/uncertainty.py` | +`ENSEMBLE` (уже существует) |
| `ValidatorPass` | `core/governance/` | +3 new passes (Фаза 8) |
| `_registry_boot.py` | `foundry/methods/catalog/causal/` | +12 new methods |
| `TransportabilityResult` | `ir/analytics/transportability.py` | +`feasible`, `data_gaps`, `p_star_values`, `legal_s_nodes`, `resolution_rounds`, `proxy_penalties` (Graph Closure) |
| `SNode` | `ir/analytics/transportability.py` | +`origin` (CONTEXT_DELTA/LEGAL/DATA_MISMATCH), +`legal_constraint_id` |

### A.2 Паттерны из существующего кода, которым следуем

| Паттерн | Источник | Применение |
|---------|----------|-----------|
| `ConfigDict(extra="forbid", frozen=True)` | Все IR типы | Все новые Pydantic модели |
| `@model_validator(mode="after")` | `CausalEffectReport`, `PanelObservationalData` | `ArticleExtractionResult`, `CausalGraphModel`, `StructuralCausalModelSpec` |
| `persist_X() / load_X()` | `causal.py` | Каждый новый IR тип |
| `put_json_artifact()` с `InputRef` | `ir/artifacts/io.py` | Все artifact persistence |
| `MethodSignature` + `@foundry_method` | `foundry/methods/base.py` | Все Foundry methods |
| `DeterminismTier.STATISTICAL` | `SyntheticControlMethod` | Discovery, bootstrap methods |
| `GonkaClient` async pattern | `lex/batch/spo_extractor.py` | `PolicyArticleExtractor` |
| `_SlidingWindowLimiter` | `lex/batch/spo_extractor.py` | `OpenAlexRateLimiter` |
| DuckDB schema + batch inserts | `lex/batch/graph_builder.py` | `skg/graph/skg_store.py` |
| `EntityDeduplicator` pattern | `lex/batch/graph_builder.py` | `VariableCanonizer` |
| `canonicalize_action()` with OOV flag | `lex/batch/canonicalizers.py` | `VariableCanonizer.canonize()` |
| `ComplianceIssue` + severity levels | `core/governance/` | `LiteratureGatePass`, `TransportabilityRequiredPass` |
| `NodeSpec` + `NodeOutcome` + `NodeEvent` | `scientist/nodes/` | `ResolveParametersNode`, `RunTransportabilityNode` |
| Cost tracking (USD) | `SPOExtractionResult` | `ArticleExtractionResult` |
| `PipelineStats` | `lex/batch/pipeline.py` | `ExtractorStats` |
| DuckDB schema + batch inserts | `lex/batch/graph_builder.py` | `skg/dataset_graph/registry.py` (Dataset Metadata Graph) |
| `ComplianceIssue` severity levels | `core/governance/` | `ConstraintSeverity` (HARD/SOFT) в Legal Graph bridge |
| Lex Knowledge Graph patterns | `lex/knowledge/types.py` | `LegalConstraint`, `LegalToDAGMapping` — bridge между Lex Legal KG и causal DAG |

### A.3 Новые компоненты (Three-Graph Closure поверх существующих модулей)

| Компонент | Файл | Расширяет | Назначение |
|-----------|---------------------------|-----------|-----------|
| `VariableAlignment` | `datasets/knowledge/variable_alignment.py` | `datasets/` | Seed table + semantic matching для canonical→dataset variable |
| `ProxyResolver` | `datasets/knowledge/proxy_resolver.py` | `datasets/` | Контекстно-зависимые прокси-цепочки для недоступных переменных |
| `PStarZComputer` | `datasets/knowledge/p_star.py` | `datasets/` | P*(Z) computation из конкретных датасетов |
| `VariableCanonizer` | `academic/knowledge/variable_canonizer.py` | `academic/` | Иерархическая канонизация переменных |
| `SKGQuery` | `academic/knowledge/skg_query.py` | `academic/` | Запросы к SKG (causal claims + params) |
| `SKGVersioning` | `academic/knowledge/skg_versioning.py` | `academic/` | Версионирование + retraction handling |
| `TransportConstraints` | `lex/legal_evaluation/transport_constraints.py` | `lex/` | ConstraintSeverity, LegalToDAGMapping |
| `TransportabilityResolutionLoop` | `scientist/nodes/builtins/causal/resolve_transport.py` | `scientist/` | Итеративный resolver (max 3 раунда), как scientist node |
| `DataGap` | `ir/analytics/transportability.py` | `ir/` | First-class объект: missing data + impact + suggestion |
| `WVSConnector` | `fabric/connectors/sources/wvs.py` | `fabric/` | World Values Survey (новый connector по паттерну WorldBank) |
| `materialize_causal_kuzu` | `scientist/nodes/builtins/causal/materialize_causal_kuzu.py` | `scientist/` | DuckDB→Kuzu для каузального графа (паттерн `world/materialize/kuzu.py`) |
| `kuzu_causal.cypher` | `scientist/nodes/builtins/causal/ddl/kuzu_causal.cypher` | `scientist/` | Cypher DDL: CausalVar, SNode, CausalEdge, AffectsS |
| `scientist_causal_full` | `scientist/workflows/causal_full.py` | `scientist/` | Полный каузальный workflow (параллельно с default) |

### A.4 Маппинг существующих модулей → три графа

| Существующий модуль | Граф | Что даёт | Что добавляем |
|---------------------|------|---------|---------------|
| `academic/` | SKG (Граф 1) | `WorkRecord`, `CausalClaimResult`, `ParameterEstimateResult`, DuckDB `ac_*` таблицы | +BoundaryCondition, +TransportFormula, +5-level extraction, +ac_skg_edges, +ac_boundary_conditions |
| `datasets/` | Dataset Metadata Graph (Граф 2) | `DatasetRecord`, `DatasetSearchResult`, DuckDB `ds_*` таблицы, DCAT alignment | +DatasetVariable (canonical mapping), +ds_variable_alignments, +ProxyResolver, +PStarZComputer |
| `fabric/connectors/` | Data Sources | `WorldBankConnector` (WDI/WGI), rate-limit, retry, caching, contracts | +WVSConnector (новый), +WGI indicator normalizer |
| `lex/` | Legal Graph (Граф 3) | `evaluate_legality()`, `LegalEvaluationRequest`, norm assembly, rule backends | +`evaluate_transport_constraints()`, +ConstraintSeverity, +LegalToDAGMapping |
| `scientist/governance/` | Governance | `ValidationPipeline`, pass ordering, profile-driven | +LiteratureGatePass, +TransportRequiredPass, +HumanReviewPass |
| `scientist/nodes/builtins/` | Workflow | 18 builtin nodes, lazy imports, phase-aware | +каузальные ноды в `builtins/causal/`, +`scientist_causal_full` workflow, +`materialize_causal_kuzu.py` |
| `fabric/world/materialize/kuzu.py` | World Graph | DuckDB→Kuzu материализация, Cypher DDL, CSV COPY, validate_counts | **ПАТТЕРН** для `materialize_causal_kuzu.py` (тот же flow: DDL→export→COPY→validate) |

---

## Приложение B: Backlog оптимизаций

Элементы, **НЕ** входящие в MVP-фазы, но запланированные для масштабирования и углубления.

> **Примечание:** KuzuDB, rustworkx, EconML/CATE и NumPyro описаны в основных фазах (секция 1.4 "Стратегия зависимостей"). Здесь — только backlog-оптимизации, не покрытые фазами.

### B.1 Causal Discovery: DAGMA (backlog)

**Проблема:** PCMCI, PC, FCI чувствительны к проклятию размерности. При >50 переменных — timeout или пустые графы.

**Решение:** [DAGMA](https://github.com/kevinsbello/dagma) (Bello et al., 2022) — непрерывная оптимизация для causal discovery. На порядки быстрее и стабильнее NOTEARS. Подходит для извлечения графов на 50+ переменных.

**Приоритет:** LOW (backlog, для масштабирования)
**Усилия:** ~1 неделя (Foundry method wrapper)
**Условие:** когда PC/FCI не справляются с размерностью конкретных доменов

### B.2 Phase 12b: y0 библиотека для полного do-calculus

**Решение:** [y0](https://github.com/y0-causal-inference/y0) — полный ID алгоритм + transportability.
**Резервный вариант:** R-библиотека `causaleffect` через rpy2.
**Детали:** см. Фаза 12b (backlog) в основном тексте.

**Приоритет:** MEDIUM (после стабилизации Simplified TR)
**Усилия:** ~2-3 недели (bridge integration)

### B.3 Быстрая сериализация IR-артефактов: orjson

**Проблема:** Повсюду в коде используется `model_dump(mode="json")`. Стандартный `json` модуль Python медленный. При росте графов сериализация/десериализация `ArticleExtractionResult`, `CausalGraphModel`, `StructuralCausalModelSpec` при записи в DuckDB станет заметным бутылочным горлышком (3-10x overhead).

**Решение:** Подключить [orjson](https://github.com/ijl/orjson) как JSON backend для Pydantic V2. Остаёмся на Pydantic (валидация, `ConfigDict(extra="forbid")`, schema generation), но заменяем сериализатор:

```python
import orjson

# Вариант 1: глобальный override для всех моделей
class PolicyBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def model_dump_json_fast(self) -> bytes:
        return orjson.dumps(self.model_dump())

# Вариант 2: Pydantic V2 custom serializer (model_config)
# model_config = ConfigDict(json_encoders={...})  # orjson-backed
```

**Ускорение:** 3-10x на больших JSON-объектах (графы >1000 рёбер, `ArticleExtractionResult` с десятками claims).

**Приоритет:** LOW (оптимизация, не блокирует MVP)
**Усилия:** ~0.5 дня (добавить orjson в deps, один базовый класс)
**Условие:** когда профилирование покажет, что JSON ser/de > 5% wall time

### B.4 Векторизация тестов на независимость: JAX для Фаз 6/7

**Проблема:** Causal discovery (PCMCI в Tigramite, PC/FCI в causal-learn) — O(N³) в худшем случае. Основное время уходит на conditional independence (CI) тесты (`ParCorr`, `GPDC`, `CMI`). В чистом Python на >30 переменных это приводит к timeout 10 min (текущий лимит).

**Решение:** Поскольку в Фазе 15 уже запланирован JAX backend, использовать `jax.vmap` + `jax.jit` для батчевой vectorизации CI-тестов раньше. Это позволит:
- Снизить timeout discovery с 10 min до секунд
- Увеличить лимит переменных с 30 до 100+
- Проверять больше лагов (`max_lag` > 5)

```python
# Пример: ParCorr на JAX (батчевая корреляция)
import jax.numpy as jnp
from jax import vmap, jit

@jit
def partial_corr_batch(X: jnp.ndarray, Y: jnp.ndarray, Z: jnp.ndarray) -> jnp.ndarray:
    """Батчевый partial correlation — все пары (X,Y|Z) одновременно."""
    # Z-residualize X and Y
    Z_pinv = jnp.linalg.pinv(Z)
    X_res = X - Z @ Z_pinv @ X
    Y_res = Y - Z @ Z_pinv @ Y
    # Pearson correlation of residuals
    return jnp.corrcoef(X_res, Y_res)[0, 1]

# vmap по всем парам переменных
batched_parcorr = vmap(partial_corr_batch, in_axes=(1, 1, None))
```

**Приоритет:** MEDIUM (Фазы 6/7, если профилирование покажет bottleneck)
**Усилия:** ~1 неделя (JAX-обёртка для ParCorr, интеграция с Tigramite custom test)
**Условие:** GPU/TPU доступен; без GPU выигрыш меньше (~2-5x vs 50-100x)

### B.5 Кэширование запросов Three-Graph Closure (Фаза 12)

**Проблема:** `TransportabilityResolutionLoop` делает повторные запросы к SKG, Dataset Graph и Legal Graph в цикле (до 3 итераций). Запросы `compute_p_star_z()`, `find_datasets_for_variable()`, `distance_to()` детерминированы внутри одного прогона (датасеты WGI/WVS обновляются раз в год).

**Решение:** In-memory LRU-кэш для детерминированных запросов внутри одного прогона:

```python
from functools import lru_cache

class TransportabilityResolutionLoop:
    # ...

    @lru_cache(maxsize=256)
    def _cached_p_star_z(
        self, canonical_var: str, context_id: str, year: int,
    ) -> "PStarZResult | None":
        """Кэш P*(Z) — результат не меняется в пределах одного прогона."""
        return self._datasets.compute_p_star_z(canonical_var, context_id, year)

    @lru_cache(maxsize=128)
    def _cached_distance(self, src_id: str, tgt_id: str) -> float:
        """Кэш distance_to() — профили контекстов не меняются."""
        return self._src_profile.distance_to(self._tgt_profile)

    @lru_cache(maxsize=512)
    def _cached_find_datasets(self, canonical_var: str) -> tuple:
        """Кэш поиска датасетов — маппинг стабилен в пределах версии."""
        return tuple(self._datasets.find_datasets_for_variable(canonical_var))
```

**Выигрыш:** При 3 раундах resolution loop с 10+ S-узлами — ~60% повторных запросов попадают в кэш. Особенно эффективно для `compute_p_star_z()`, который может включать сетевые вызовы к WGI/WVS.

**Приоритет:** HIGH (Фаза 12, zero-cost improvement)
**Усилия:** ~0.5 дня (декоратор `@lru_cache` + `cache_clear()` между прогонами)
