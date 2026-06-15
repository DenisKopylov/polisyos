# PolicyOS Scientist — Архитектура пайплайна

Owner: `@scientist-owners`
Source of truth: `src/polisyos/scientist/**`, `src/polisyos/foundry/**`, `src/polisyos/fabric/connectors/**`, `src/polisyos/ir/analytics/**`, and `tests/unit/scientist/**`

> Дата: 2026-03-21
> Статус: живой документ, описывает текущее состояние кодовой базы

---

## Содержание

1. [Обзор системы](#system-overview)
2. [Три workflow и автоматический выбор](#2-три-workflow-и-автоматическии-выбор)
3. [Knowledge Layer — три графа знаний](#3-knowledge-layer-три-графа-знании)
4. [scientist_default — стандартный workflow](#4-scientist_default-стандартныи-workflow)
5. [scientist_causal_full — полный каузальный анализ](#5-scientist_causal_full-полныи-каузальныи-анализ)
6. [scientist_policy_verified — верифицированная политика](#6-scientist_policy_verified-верифицированная-политика)
7. [Foundry и Data Plane](#foundry-data-plane)
8. [IR Analytics — промежуточные представления](#8-ir-analytics-промежуточные-представления)
9. [Checkpoint и восстановление](#checkpoint-recovery)
10. [Детальное описание каждого node](#node-details)

---

## 1. Обзор системы { #system-overview }

PolicyOS Scientist — это DAG-based workflow engine для анализа политических решений.
Система принимает policy question или TrinityBundle и проводит полный цикл:

```text
Policy Question / TrinityBundle
    → Knowledge Retrieval (Legal + Academic + Datasets)
    → Causal Identification (Pearl-Bareinboim)
    → Simulation (Foundry)
    → Governance & Legal Check
    → Decision Packet
```

### Ключевые компоненты

| Компонент                | Путь                                                           | Назначение                                                       |
| ------------------------ | -------------------------------------------------------------- | ---------------------------------------------------------------- |
| **Scientist Workflows**  | `scientist/workflows/`                                         | Определение и запуск workflow DAG                                |
| **Node Builtins**        | `scientist/nodes/builtins/`                                    | 35 встроенных узлов пайплайна                                    |
| **Engine**               | `scientist/engine/`                                            | Executor, checkpoint, registry, state                            |
| **Knowledge Layers**     | `academic/knowledge/`, `datasets/knowledge/`, `lex/knowledge/` | Три графа знаний                                                 |
| **Cross-Graph Compiler** | `scientist/cross_graph/`                                       | Объединение evidence из трёх графов                              |
| **Foundry**              | `foundry/`                                                     | Каузальный движок, data plane, методы                            |
| **IR Analytics**         | `ir/analytics/`                                                | Промежуточные представления (estimand, evidence bundle, reports) |
| **Fabric**               | `fabric/connectors/`                                           | Мост к внешним данным (UNPD, WVS и др.)                          |

### Центральная модель состояния: ExperimentState

```python
class ExperimentState(BaseModel):
    run_id: str
    inputs: dict[str, ArtifactRef]          # trinity_bundle_ref, data_snapshot_ref, ...
    artifacts_index: dict[str, ArtifactRef]  # simulation_result_ref, causal_report_ref, ...
    reports_index: dict[str, ArtifactRef]    # governance_report_ref, legal_report_ref, ...
    params: dict[str, JsonValue]             # все runtime-параметры
    budgets: dict[str, Decimal]
    execution_profile: str                   # "fast" | "research" | "governed" | "production" | "policy_verified_async"
    # + поля для policy_verified: policy_request_ref, legal_candidate_pack_ref, ...
```

Каждый node читает и пишет в `ExperimentState`. Все артефакты — immutable, content-addressed (CAS).

---

<a id="2-три-workflow-и-автоматическии-выбор"></a>

## 2. Три workflow и автоматический выбор

### Workflow IDs

| ID                          | Файл                           | Узлов | Назначение                                          |
| --------------------------- | ------------------------------ | ----- | --------------------------------------------------- |
| `scientist_default`         | `workflows/default.py`         | 21    | Стандартный анализ: compile → simulate → governance |
| `scientist_causal_full`     | `workflows/causal_full.py`     | 25    | + literature priors, transport, causal ensemble     |
| `scientist_policy_verified` | `workflows/policy_verified.py` | 25    | + legal source verification, policy drafting        |

### Логика автоматического выбора (`selection.py`)

```text
1. Явный workflow_id == "scientist_policy_verified" → POLICY_VERIFIED
2. _should_use_policy_verified(state):

   - policy_answer_mode == "verified_async" → да
   - execution_profile == "policy_verified_async" → да
   - Нет trinity_bundle, но есть policy_question/research_intent → да
3. execution_profile in {"research", "governed", "production"} → CAUSAL_FULL
4. Явный workflow_id == "scientist_causal_full" → CAUSAL_FULL
5. _should_auto_escalate_to_causal_full(state):

   - transport_required → да
   - source_context ≠ target_context → да
   - external_evidence/cross_graph_evidence → да
   - knowledge_bundle_ref присутствует → да
6. Иначе → DEFAULT
```

---

<a id="3-knowledge-layer-три-графа-знании"></a>

## 3. Knowledge Layer — три графа знаний

### 3.1 Academic SKG (Scholar Knowledge Graph)

**Хранилище:** DuckDB (`ac_skg_*` таблицы)

| Таблица                        | Содержание                                 |
| ------------------------------ | ------------------------------------------ |
| `ac_skg_articles`              | Статьи из OpenAlex с метаданными           |
| `ac_skg_variables`             | Каноничные переменные с одобрением         |
| `ac_skg_edges`                 | Каузальные рёбра (src → dst) с confidence  |
| `ac_skg_edge_evidence`         | Evidence per edge per article              |
| `ac_skg_parameters`            | Оценки параметров из литературы            |
| `ac_skg_simulation_parameters` | Refined-оценки для калибрации              |
| `ac_skg_transport_scores`      | Пре-вычисленные transportability penalties |

**Интерфейс запросов (SKGQuery):**

- `query_prior(variable)` → агрегированное распределение (weighted mean/std)
- `query_claims(cause, effect)` → каузальные связи с trust scoring
- `query_parameters(param, target_context)` → кандидаты с context distance

**Агрегация confidence:** evidence-weighted noisy-OR с 20-летним half-life decay.

### 3.2 Datasets Catalog

**Хранилище:** DuckDB (`ds_*` таблицы) + HNSW vector index

| Таблица                  | Содержание                                     |
| ------------------------ | ---------------------------------------------- |
| `ds_dataset_catalog`     | DCAT-aligned метаданные датасетов              |
| `ds_distributions`       | Загружаемые ресурсы с коннекторами             |
| `ds_variable_alignments` | raw_var → canonical_var маппинги               |
| `ds_metric_bindings`     | Детерминистичные metric → dataset привязки     |
| `ds_observations`        | Time-series значения (country, year, variable) |

**Поиск:** гибридный (vector HNSW + full-text), с бустами по свежести, метрикам, country hints.

**Registry:** вычисляет P\*(Z) для transport — темпоральные штрафы, интерполяция, proxy penalties.

### 3.3 Lex (Legal) Knowledge Graph

**Хранилище:** DuckDB (`lex_*` таблицы) + HNSW vector index

| Таблица               | Содержание                                                    |
| --------------------- | ------------------------------------------------------------- |
| `lex_facts`           | Юридические факты с confidence tiers                          |
| `lex_fact_grounded`   | Факты с цитатами из источников                                |
| `lex_normative_facts` | Каноничные обязательства/запреты                              |
| `lex_provisions`      | Иерархическая структура документов (Стаття → Частина → Пункт) |

**Фильтры:** trust_tier (search_candidate → grounded_fact → normative_fact), jurisdiction, domain, as_of.

**Constraints bridge:** маппинг legal facts → модификации DAG (HARD блокирует transport, SOFT штрафует).

### Как три графа объединяются

```text
CrossGraphEvidenceCompiler.compile(TrinityBundle)
  → extract_evidence_needs()          # метрики, параметры, constraints, механизмы, рёбра
  → _assess_legal_need()              # статус: ALLOWED | CONSTRAINED | PROHIBITED
  → _assess_dataset_need()            # статус: DIRECT | PROXY_ONLY | MISSING
  → _assess_academic_need()           # статус: SUPPORTED | MIXED | INSUFFICIENT
  → _compose_transportability_view()  # статус: IDENTIFIED | PARTIALLY | BOUNDED | UNSUPPORTED
  → CrossGraphEvidenceProfile         # 4-мерная confidence по каждой evidence need
```

---

<a id="4-scientist_default-стандартныи-workflow"></a>

## 4. scientist_default — стандартный workflow

### DAG (21 node)

```text
start
 ├── build_data_snapshot
 │    └── bind_foundry_inputs
 │         └── run_data_plane_gate ─────────────────────────┐
 ├── build_execution_plan                                    │
 │    └── build_method_catalog_snapshot                      │
 │         └── run_preflight                                 │
 │              └── ready_to_run ───────────────────────────┐│
 └── link_trinity ─────────────────────────────────────────┐││
                                                           │││
                              compile_foundry ◄────────────┘┘┘
                                   │
                    compile_cross_graph_evidence
                                   │
                          resolve_parameters
                                   │
                           run_simulation
                      ┌────────┬───┴────┬──────────┐
                 legal_check   │   run_distrib   propagate_unc
                      │        │        │              │
                      │   run_causal_eval              │
                      │        │        │              │
                      └────────┴───┬────┴──────────────┘
                                   │
                     run_normative_arbitration
                                   │
                          run_governance
                                   │
                          run_evaluator
                                   │
                      build_decision_packet
```

### Этапы

1. **Подготовка данных** (параллельно):

   - `build_data_snapshot` — Fabric DataSnapshot
   - `build_execution_plan` → `build_method_catalog_snapshot` → `run_preflight` → `ready_to_run`
   - `link_trinity` — валидация TrinityBundle
   - `bind_foundry_inputs` → `run_data_plane_gate` — PII/quality gates

2. **Компиляция**:

   - `compile_foundry` — TrinityBundle → Foundry exec plan
   - `compile_cross_graph_evidence` — сбор evidence из 3 графов
   - `resolve_parameters` — каузальные параметры из SKG

3. **Симуляция и анализ** (параллельно после `run_simulation`):

   - `legal_check` — проверка легальности
   - `run_causal_evaluation` — каузальный анализ (ATE, HTE)
   - `run_distributional_analysis` — распределение по группам
   - `propagate_uncertainty` — propagation неопределённости

4. **Governance и решение**:

   - `run_normative_arbitration` — нормативные trade-offs
   - `run_governance` — governance gates (verdict: APPROVED | NEEDS_REVISION | BLOCKED)
   - `run_evaluator` — оценка качества run
   - `build_decision_packet` — финальный пакет решения

---

<a id="5-scientist_causal_full-полныи-каузальныи-анализ"></a>

## 5. scientist_causal_full — полный каузальный анализ

### Отличия от default (+4 node)

```text
Дополнительные узлы:
  build_literature_prior → reconcile_causal_graph  (до compile_cross_graph_evidence)
  run_causal_queries → run_causal_ensemble         (после run_causal_evaluation)
  run_abm_consistency                               (после run_causal_ensemble)
  run_transportability                              (после run_abm_consistency)
```

### DAG (25 nodes)

```text
start
 ├── build_data_snapshot → bind_foundry_inputs → run_data_plane_gate ──┐
 ├── build_execution_plan → build_method_catalog_snapshot              │
 │    └── run_preflight → ready_to_run ────────────────────────────────┤
 ├── link_trinity ─────────────────────────────────────────────────────┤
 └── build_literature_prior                                            │
      └── reconcile_causal_graph ──────────────────────────────────────┤
                                                                       │
                                    compile_foundry ◄──────────────────┘
                                         │
                          compile_cross_graph_evidence  (+ reconcile_causal_graph)
                                         │
                                resolve_parameters  (+ reconcile_causal_graph)
                                         │
                                  run_simulation
                            ┌──────┬─────┴─────┬───────────┐
                       legal_check  │   run_distrib   propagate_unc
                                    │
                           run_causal_eval
                                    │
                           run_causal_queries
                                    │
                          run_causal_ensemble
                                    │
                         run_abm_consistency
                                    │
                        run_transportability  (+ reconcile_causal_graph)
                                    │
                      run_normative_arbitration  (+ run_transportability)
                                    │
             run_governance  (+ reconcile_causal_graph, run_causal_ensemble,
                               run_abm_consistency, run_transportability)
                                    │
                          run_evaluator
                                    │
                      build_decision_packet
```

### Новые этапы

| Node                     | Что делает                                                                   |
| ------------------------ | ---------------------------------------------------------------------------- |
| `build_literature_prior` | Строит LiteratureCausalPrior из SKG: каузальный граф с literature evidence   |
| `reconcile_causal_graph` | Мёрж data graph + literature prior + LLM hints → reconciled graph            |
| `run_causal_queries`     | Структурный каузальный запрос (interventional/counterfactual) через GCM      |
| `run_causal_ensemble`    | Ensemble из ≤10 SCM → shared query → consensus с uncertainty envelope        |
| `run_abm_consistency`    | Сверка SCM macro effects ↔ ABM micro aggregates (phase transition detection) |
| `run_transportability`   | Three-graph closure: causal + datasets + legal → transport result            |

---

<a id="6-scientist_policy_verified-верифицированная-политика"></a>

## 6. scientist_policy_verified — верифицированная политика

### Назначение

Workflow для случаев, когда нет готового TrinityBundle, а есть policy question.
Система самостоятельно:

1. Ищет юридические основания в Lex graph
2. Верифицирует найденные источники
3. Составляет policy options
4. Формализует в TrinityBundle для Foundry
5. Проводит полный анализ (simulation + causal + governance)

### DAG (25 nodes)

```text
start
 ├── build_data_snapshot → bind_foundry_inputs → run_data_plane_gate ────────────────────┐
 ├── build_execution_plan → build_method_catalog_snapshot → run_preflight ────────────────┤
 │                                                                                        │
 └── plan_policy_request                                                                  │
      ├── compile_cross_graph_evidence                                                    │
      │    └── assemble_legal_candidate_pack                                              │
      │         └── expand_legal_source_pack                                              │
      │              └── run_source_verification                                          │
      │                   └── run_source_gap_review ◄─── (bounded: max 2 cycles)          │
      │                        └── draft_policy_options                                   │
      │                             └── formalize_verified_policy ────────────────────────┐│
      │                                                                                  ││
      │                                       compile_foundry ◄──────────────────────────┘┘
      │                                            │
      │                                   resolve_parameters
      │                                            │
      │                                     run_simulation
      │                               ┌──────┬─────┴─────┬───────────┐
      │                          legal_check  │   run_distrib   propagate_unc
      │                                       │
      │                              run_causal_eval
      │                                       │
      │                         run_normative_arbitration
      │                                       │
      │                              run_governance
      │                                       │
      │              build_verified_policy_report
      │              (+ run_source_gap_review, draft_policy_options,
      │                 run_simulation, run_causal_eval, run_distrib, propagate_unc)
      │                                       │
      └────────────────────────── build_decision_packet
```

### Этап 1: Планирование запроса

**`plan_policy_request`** — создаёт PolicyRequestFrame:

- Извлекает policy_question, jurisdiction (default: UA), domain, as_of
- Генерирует request_id через SHA256 hash
- Устанавливает `policy_answer_mode = "verified_async"`

### Этап 2: Сбор юридических кандидатов

**`compile_cross_graph_evidence`** — собирает evidence profile из трёх графов.

**`assemble_legal_candidate_pack`** — поиск в Lex graph:

- Генерирует до `max_candidate_queries` (default 40) поисковых запросов
- Включает украиноязычные варианты запросов
- Собирает fact_hits и provision_hits
- Отслеживает hit_reasons и anchor_coverage

### Этап 3: Развёртывание источников

**`expand_legal_source_pack`** — разрешает кандидатов в полные source bundles:

- Загружает версионные цепочки документов
- Разрешает reference neighbourhood (max_reference_hops=2)
- Собирает appendix context (заголовки, таблицы)
- Лимит: max_source_docs=120

### Этап 4: Верификация источников

**`run_source_verification`** — верификация цитат и claims:

1. **Baseline claims** — детерминистично из source bundles + candidate facts:

   - Проверяет: цитата существует в тексте, anchor совпадает
   - Confidence = max(0.5, min(fact.confidence, 0.99))
2. **LLM verification** (опционально, если доступен LLM):

   - Каждый source bundle → verifier agent → JSON с claims
   - Считает disagreement_rate (baseline vs LLM)
3. **Merge** — дедупликация по (claim_type, anchor, claim_text), сохраняет с наивысшим confidence
4. **Gap detection** — source bundles без verified claims → SourceCoverageGap

   - Severity "critical" для approval_bundle/amendment_bundle

### Этап 5: Обзор пробелов (Bounded Recovery)

**`run_source_gap_review`** — итеративное восстановление coverage:

```text
Цикл 1: gaps → recovery queries → re-assemble → re-expand → re-verify → merge
Цикл 2: если gaps остались → повторить
После цикла 2: СТОП — выпустить report с unresolved_critical_gaps
```

**Ограничения:**

- `verification_cycles_completed >= 2` → прекратить recovery
- `max_gap_review_calls = 80` — бюджет на gap review
- Если critical gaps остаются → `needs_expert_review = True`

### Этап 6: Составление policy options

**`draft_policy_options`** — из verified claims:

- `verified_options` — подкреплённые цитатами и юридическими основаниями
- `hypothesis_options` — гипотетические (если `allow_hypotheses=True`)
- Каждый option включает: title, summary, legal_basis_refs, constraints

### Этап 7: Формализация

**`formalize_verified_policy`** — PolicyOptionSet → TrinityBundle:

- Выбирает primary option (первый verified, fallback на hypothesis)
- Создаёт DraftResult с interventions
- Формализует через MockFormalizerAgent → TrinityBundle
- Устанавливает `policy_trinity_generated = True`

### Этап 8: Стандартный pipeline (как в default)

`compile_foundry` → `resolve_parameters` → `run_simulation` → analysis → governance

### Этап 9: Финальный отчёт

**`build_verified_policy_report`** — собирает VerifiedPolicyReport:

- executive_summary
- verified_legal_basis (все verified claims)
- policy_options (verified + hypothesis)
- constraints_and_timing
- simulation_and_causal_implications
- verified_findings (форматированные claims с citation)
- hypotheses
- missing_evidence (из unresolved_critical_gaps)
- citation_appendix
- intervention_legal_basis_map
- needs_expert_review flag

**`build_decision_packet`** — финальный DecisionPacket с monitoring contract.

### Дефолтные параметры policy_verified

```python
execution_profile = "policy_verified_async"
policy_answer_mode = "verified_async"
allow_hypotheses = True
policy_request_jurisdiction = "UA"
max_candidate_queries = 40
max_source_docs = 120
max_source_anchors = 400
max_reference_hops = 2
max_verifier_calls = 500
max_gap_review_calls = 80
verification_cycles_completed = 0  # max 2
```

---

## 7. Foundry и Data Plane { #foundry-data-plane }

### Data Plane Bindings

```text
External Data
  → Fabric Connectors (UNPD, WVS, ...)
  → DataSnapshot (tabular payload + quality report)
  → build_input_bindings() → FoundryInputBindings
  → GlobalState (typed slots: agent-scoped, firm-scoped)
```

**Binding Rules:** source_path → target_slot_id, с трансформациями (identity, to_bool, to_int, scale, clip, round).

**Quality Gates (DataPlaneGateNode):**

- PII scan → блокировка если обнаружены PII
- Quality gate → свежесть (≤14 дней = fresh), grade (A–F)

### Causal Engine (Pearl-Bareinboim Orchestrator)

Три фазы:

**1. Identify** — выбор алгоритма идентификации:

```text
Counterfactual → ctf_transportability | id_star
Measurement error → identify_with_proxy
Multi-outcome → multi_outcome_id
Stochastic → sid_algorithm
Selection/transport → tr_algorithm + SelectionDiagram
Standard → id_with_oracle_fallback (backdoor/frontdoor)
```

Результат: `IdentificationResult` (estimand_ast + proof_steps) или `NegativeCertificate`.

**2. Compile** — EstimandAST → ExecutorGraph (DAG typed nodes с method_fqn, params, dependencies).

**3. Estimate** — топологическое выполнение:

- Nuisance nodes (propensity, outcome models)
- Primary estimators (AIPW, DML, IPW, CATE)
- Diagnostics (positivity, overlap, covariate balance)
- → CausalEffectReport + EvidenceBundle

### Методы (protocols.py)

| Contract                     | Use Case                                 |
| ---------------------------- | ---------------------------------------- |
| `PanelObservationalData`     | DiD, SCM, structural time series         |
| `HTEObservationalData`       | Forest, BCF, DML (HTE)                   |
| `TimeSeriesCausalData`       | PCMCI/Tigramite discovery                |
| `TabularCausalDiscoveryData` | PC/FCI/GES discovery                     |
| `SCMFitData`                 | Structural model fitting                 |
| `SCMQueryData`               | Interventional/counterfactual simulation |
| `RDDObservationalData`       | Regression discontinuity                 |
| `NetworkCausalData`          | Interference/GNN                         |
| `FairnessObservationalData`  | Fairness-constrained causal              |

---

<a id="8-ir-analytics-промежуточные-представления"></a>

## 8. IR Analytics — промежуточные представления

### CausalEffectReport

- point_estimate, confidence_interval, inference_method
- placebo_results, refutation_results, diagnostic_tests
- → конвертируется в UncertaintyEnvelope

### EstimandAST

Типизированное дерево каузального запроса:

- Leaf: `DistributionRef` — P(Y|X), P\*(Y|do(X))
- Operators: Sum, Product, Ratio, Integral, Nuisance
- Side conditions: positivity, overlap, SUTVA, consistency

### EvidenceBundle

Машинно-читаемый audit trail:

- proof_steps (identification)
- data_provenance
- compilation_steps
- estimation_steps (wall_time, backend, params_hash)
- diagnostic_scores
- quality_report (composite grade)

### NegativeCertificate

Когда identification не удался:

- blocking_type: HEDGE | S_NODE | POSITIVITY | SUPPORT_MISMATCH | MISSING_DISTRIBUTION
- fallback_results: partial identification bounds
- suggested_experiments: RCT, natural experiment, IV, DiD, RDD
- epistemicTier: EXACT_NONPARAMETRIC → PARTIAL → ASSUMPTION_DEPENDENT → DIAGNOSTIC

---

## 9. Checkpoint и восстановление { #checkpoint-recovery }

### Checkpoint Policy

```python
CheckpointPolicy = "off" | "strict" | "best_effort"
```

### Как работает

1. После каждого node → `CASCheckpointHook.on_node_complete()`
2. Сохраняет: run_id, sequence_number, completed_nodes, workflow_fingerprint, cache_entry_refs
3. При восстановлении: загружает NodeResultCache из checkpoint refs
4. Если `workflow_fingerprint` не совпадает → `WorkflowMismatchError`
5. Run lock через `fcntl.flock` предотвращает параллельный запуск одного run_id

### Node Cache

- Idempotency key = SHA256(workflow_spec + state + bind_params)
- Disabled для: noop, set_state, emit_artifact, enrich_knowledge
- При cache hit → skip execution, используется cached outcome

### Error Policy

Все три workflow используют `error_policy = "continue"`:

- При fail node → upstream nodes блокируются
- Остальные ветки DAG продолжают выполнение
- Финальный WorkflowReport содержит статус каждого node

---

## 10. Детальное описание каждого node { #node-details }

### Data Nodes

| Node                    | Node ID                                    | Описание                                                                                                  |
| ----------------------- | ------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| **build_data_snapshot** | `scientist.node_build_data_snapshot@1.0.0` | Вызывает Fabric snapshot() для создания DataSnapshot. Если уже есть — skip. Извлекает PII scan summary.   |
| **bind_foundry_inputs** | `scientist.node_bind_foundry_inputs@1.0.0` | Строит deterministic foundry input bindings. Валидирует model spec. Возвращает binding report.            |
| **enrich_knowledge**    | `scientist.node_enrich_knowledge@1.1.0`    | Строит knowledge_bundle через Scholar. Управляет freshness, cooldown, drift. Distributed refresh locking. |

### Planning Nodes

| Node                              | Node ID                                              | Описание                                                                                             |
| --------------------------------- | ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| **plan_policy_request**           | `scientist.node_plan_policy_request@1.0.0`           | Создаёт PolicyRequestFrame из policy_question + jurisdiction + domain. _(policy_verified only)_      |
| **build_execution_plan**          | `scientist.node_build_execution_plan@1.0.0`          | Создаёт/сохраняет ExecutionPlan (data_needs, constraints, expected_outputs).                         |
| **build_method_catalog_snapshot** | `scientist.node_build_method_catalog_snapshot@1.0.0` | Snapshot каталога FoundryMethod + capability contract.                                               |
| **run_preflight**                 | `scientist.node_run_preflight@1.0.0`                 | Валидация ExecutionPlan vs live method catalog. Устанавливает preflight_ready.                       |
| **ready_to_run**                  | `scientist.node_ready_to_run@1.0.0`                  | Hard gate: блокирует если preflight_ready=False.                                                     |
| **compile_cross_graph_evidence**  | `scientist.node_compile_cross_graph_evidence@1.0.0`  | CrossGraphEvidenceCompiler: объединяет evidence из 3 графов. Оценивает benchmarks.                   |
| **assemble_legal_candidate_pack** | `scientist.node_assemble_legal_candidate_pack@1.0.0` | Поиск юридических кандидатов в Lex graph (до 40 запросов, вкл. украинские). _(policy_verified only)_ |
| **expand_legal_source_pack**      | `scientist.node_expand_legal_source_pack@1.0.0`      | Разрешение кандидатов в source bundles с version chains и references. _(policy_verified only)_       |
| **run_source_verification**       | `scientist.node_run_source_verification@1.0.0`       | Baseline + LLM верификация claims. Gap detection. _(policy_verified only)_                           |
| **run_source_gap_review**         | `scientist.node_run_source_gap_review@1.0.0`         | Итеративное восстановление coverage (max 2 цикла). _(policy_verified only)_                          |
| **draft_policy_options**          | `scientist.node_draft_policy_options@1.0.0`          | Составление verified + hypothesis policy options. _(policy_verified only)_                           |
| **run_evaluator**                 | `scientist.node_run_evaluator@1.0.0`                 | Оценка качества run, решение о следующей итерации.                                                   |

### Compile Nodes

| Node                          | Node ID                                          | Описание                                                                                                                 |
| ----------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| **link_trinity**              | `scientist.node_link_trinity@1.0.0`              | Валидация TrinityBundle: mechanisms, slots, merge rules, constraints, selectors, units.                                  |
| **compile_foundry**           | `scientist.node_compile_foundry@1.0.0`           | Trinity → Foundry exec plan. Производит 7 артефактов (exec_plan, lowered_ir, program_graph, slot_layout, treasury_plan). |
| **formalize_verified_policy** | `scientist.node_formalize_verified_policy@1.0.0` | PolicyOptionSet → TrinityBundle для Foundry. _(policy_verified only)_                                                    |

### Simulate Nodes

| Node                            | Node ID                                            | Описание                                                                                                                                     |
| ------------------------------- | -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **run_simulation**              | `scientist.node_run_simulation@1.0.0`              | Выполнение Foundry exec plan. Производит 8 артефактов (result, metrics, state_delta, snapshot, constraints, environment, attestation, sbom). |
| **run_distributional_analysis** | `scientist.node_run_distributional_analysis@1.0.0` | DistributionalReport: breakdown по geography/income quintiles.                                                                               |
| **propagate_uncertainty**       | `scientist.node_propagate_uncertainty@1.0.0`       | Propagation input uncertainty → output metrics.                                                                                              |
| **run_causal_evaluation**       | `scientist.node_run_causal_evaluation@1.0.0`       | Каузальный анализ (ATE/HTE). Опционально refutation + sensitivity. Производит 7 артефактов.                                                  |

### Causal Nodes (causal_full only)

| Node                       | Node ID                                       | Описание                                                                   |
| -------------------------- | --------------------------------------------- | -------------------------------------------------------------------------- |
| **build_literature_prior** | `scientist.node_build_literature_prior@1.0.0` | LiteratureCausalPrior из SKG: каузальный граф с evidence weights.          |
| **reconcile_causal_graph** | `scientist.node_reconcile_causal_graph@1.0.0` | Merge: data graph + literature prior + LLM hints → reconciled graph.       |
| **run_causal_queries**     | `scientist.node_run_causal_queries@1.0.0`     | Структурный каузальный запрос через GCM. Persists query result + envelope. |
| **run_causal_ensemble**    | `scientist.node_run_causal_ensemble@1.0.0`    | ≤10 SCM members → shared query → consensus weights → uncertainty envelope. |
| **run_abm_consistency**    | `scientist.node_run_abm_consistency@1.0.0`    | SCM macro effects ↔ ABM aggregates. Phase transition detection.            |
| **run_transportability**   | `scientist.node_resolve_transport@1.0.0`      | Three-graph closure (causal + datasets + legal) → TransportabilityResult.  |

### Governance Nodes

| Node                          | Node ID                                          | Описание                                                                                                              |
| ----------------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| **run_data_plane_gate**       | `scientist.node_data_plane_gate@1.0.0`           | PII + Quality gates до expensive Foundry execution.                                                                   |
| **legal_check**               | `scientist.node_legal_check@1.0.0`               | Evaluate legality: NormPack → LegalReport + ChangeProposal (compliance grade).                                        |
| **run_normative_arbitration** | `scientist.node_run_normative_arbitration@1.0.0` | Нормативные trade-offs: stakeholder utilities, outcomes, rights audit.                                                |
| **run_governance**            | `scientist.node_run_governance@1.0.0`            | Governance pipeline: quality → safety → alignment → consistency → tradeoff. Verdict: APPROVED/NEEDS_REVISION/BLOCKED. |

### Decide Nodes

| Node                             | Node ID                                             | Описание                                                                                  |
| -------------------------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| **build_verified_policy_report** | `scientist.node_build_verified_policy_report@1.0.0` | VerifiedPolicyReport с verified findings, citations, gaps. _(policy_verified only)_       |
| **build_decision_packet**        | `scientist.node_build_decision_packet@1.0.0`        | Финальный DecisionPacket: validity envelope, triggers, dependencies, monitoring contract. |

---

## Приложение: Полный путь данных в policy_verified

```text
1. Policy Question ("Яка податкова ставка оптимальна для ФОП?")
   │
2. plan_policy_request
   │  → PolicyRequestFrame {question, jurisdiction="UA", domain, goals, constraints}
   │
3. compile_cross_graph_evidence
   │  → CrossGraphEvidenceProfile {legal_status, dataset_status, academic_status, transport_status}
   │
4. assemble_legal_candidate_pack
   │  → LegalCandidatePack {fact_hits, provision_hits, queries}
   │  Запросы: "податкова ставка ФОП", "єдиний податок група", "tax rate sole proprietor UA"
   │
5. expand_legal_source_pack
   │  → LegalSourcePack {source_bundles с version chains, reference context}
   │  До 120 документів, до 2 hops reference resolution
   │
6. run_source_verification
   │  → SourceVerificationReport {verified_claims, unresolved_gaps}
   │  Baseline: цитати + факти → claims
   │  LLM: verifier agent → validated claims
   │  Merge → deduplicated claims
   │
7. run_source_gap_review  (max 2 cycles)
   │  Цикл 1: gaps → recovery queries → re-assemble → re-verify → merge
   │  Цикл 2: якщо gaps залишились → повторити
   │  Після 2 циклів: СТОП → unresolved_critical_gaps
   │
8. draft_policy_options
   │  → PolicyOptionSet {verified_options, hypothesis_options}
   │
9. formalize_verified_policy
   │  → TrinityBundle (з interventions та constraints)
   │
10. compile_foundry → resolve_parameters → run_simulation
    │  → SimulationResult, Metrics, StateSnapshot
    │
11. legal_check + run_causal_eval + run_distrib + propagate_uncertainty
    │  (параллельно)
    │
12. run_normative_arbitration → run_governance
    │  → GovernanceReport {verdict, issues}
    │
13. build_verified_policy_report
    │  → VerifiedPolicyReport {
    │       executive_summary,
    │       verified_legal_basis,
    │       policy_options,
    │       constraints_and_timing,
    │       simulation_implications,
    │       missing_evidence,
    │       citation_appendix
    │    }
    │
14. build_decision_packet
    → DecisionPacket {validity_envelope, triggers, dependencies, monitoring_contract}
```
