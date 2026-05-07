# PolicyOS — Infrastructure Guide: Split LLM/Compute Architecture

> Практическое руководство по развёртыванию PolicyOS с разделением LLM-фазы
> и вычислительной фазы на разные серверы для оптимизации стоимости и throughput.
>
> Дата: 2026-04-04 | Статус: живой документ

---

## Содержание

0. [Реалистичность текущей версии и must-fix](#0-реалистичность-текущей-версии-и-must-fix)
1. [Мотивация и экономика](#1-мотивация-и-экономика)
2. [Compute Profile по стадиям pipeline](#2-compute-profile-по-стадиям-pipeline)
3. [Целевая архитектура](#3-целевая-архитектура)
4. [Рекомендации по железу](#4-рекомендации-по-железу)
5. [CAS как связующий слой](#5-cas-как-связующий-слой)
6. [Knowledge Graphs: сборка и раздача](#6-knowledge-graphs-сборка-и-раздача)
7. [Протокол оркестрации](#7-протокол-оркестрации)
8. [Конфигурация окружений](#8-конфигурация-окружений)
9. [Lifecycle GPU-инстанса](#9-lifecycle-gpu-инстанса)
10. [Fault Tolerance и Checkpoint](#10-fault-tolerance-и-checkpoint)
11. [Мониторинг и observability](#11-мониторинг-и-observability)
12. [Масштабирование](#12-масштабирование)
13. [Стоимостная модель](#13-стоимостная-модель)
14. [Checklist развёртывания](#14-checklist-развёртывания)

---

## 0. Реалистичность текущей версии и must-fix

### Короткий вывод

**Архитектурно split LLM/Compute реалистичен**, но в текущем коде это пока не
plug-and-play. Документ ниже описывает целевую схему, а перед production rollout
нужно закрыть несколько P0/P1 разрывов между гайдом и реализацией.

### P0 — без этого split будет нестабильным или не заработает

| Gap                                                                                             | Почему это блокер                                                          | Что сделать                                                                                                                                   |
| ----------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `runtime.http` и `scientist.workflows` местами создают `FileSystemCAS(...)` напрямую            | `POLISYOS_CAS_BACKEND=cached_gcs` из env не подхватывается end-to-end      | Перевести runtime/scientist wiring на `build_artifact_store(ArtifactStoreConfig.from_env())`, а `FileSystemCAS` оставить как default fallback |
| Нет явного phase boundary "LLM-only → compute-only → LLM-only" внутри `scientist_policy_design` | Нельзя надёжно запустить только GPU-сегмент без повторного прогона LLM-нод | Добавить compute-only workflow/profile или executor-level node partitioning + явные split markers                                             |
| Checkpoint head и run lock сейчас локальные файлы в `run_dir`                                   | Resume на другой машине из одного только GCS CAS не гарантирован           | Либо хранить checkpoint head/lease в shared durable store, либо добавить resume API с явным `checkpoint_ref` и внешним run lease              |
| `POST /api/v1/control/runs` сейчас создаёт новый `run_id` и не принимает `resume_run_id`        | Recovery flow из секции 10 пока не соответствует текущему API              | Добавить отдельный resume endpoint/job kind или расширить `WorkflowRunRequest` контракт                                                       |
| `skip_llm_nodes`, `candidates_ref`, `POLISYOS_*_DB_PATH` из примеров не читаются текущим кодом  | Примеры конфигурации выглядят рабочими, но реально будут no-op или ошибкой | Либо реализовать этот env/API контракт, либо пометить его как target-state и не выдавать как текущий runbook                                  |

### P1 — желательно закрыть до реальной эксплуатации

| Gap                                                                                            | Риск                                                                                         | Что сделать                                                                                                                       |
| ---------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `RunHierarchicalPolicySearchNode` уже включает inner compile/readiness/sim loop                | Граница "LLM phase" vs "GPU phase" по DAG сейчас проходит не там, где нарисовано в диаграмме | Пересобрать split-план вокруг фактического node call graph и вынести search eval на GPU сторону                                   |
| Compute budget и список nodes в секции 2 частично не совпадают с `scientist_policy_design` DAG | Sizing/стоимость будут оптимистичны или неверно атрибутированы                               | Перегенерировать таблицы по `workflows/policy_design.py` + inner evaluator path                                                   |
| Secrets через скачанный JSON key в checklist                                                   | Long-lived service account key на диске — плохая практика и лишний blast radius              | Для GCE использовать attached service account, для Hetzner — Workload Identity Federation; JSON key только как временный fallback |
| Нет явного fallback при нехватке Spot GPU capacity                                             | MIG/Spot может не поднять нужный размер группы, run будет ждать                              | Добавить policy: retry с backoff, multi-zone fallback, и controlled fallback на on-demand                                         |

### Рекомендованный rollout-порядок

1. **Phase A — storage/control-plane wiring**: shared CAS из env, корректный worker backend,
   shared checkpoint/resume contract, фиксация реальных env vars.
2. **Phase B — split execution semantics**: compute-only workflow или node partitioning,
   перенос candidate search eval на GPU worker, recovery path через explicit resume API.
3. **Phase C — infra hardening**: WIF/attached service accounts, private connectivity,
   Spot fallback policy, production observability и budget guardrails.

### External best-practice references

- [Spot VMs and managed instance groups](https://docs.cloud.google.com/compute/docs/instances/spot)
- [Cloud Storage / Compute data-transfer pricing](https://cloud.google.com/vpc/network-pricing)
- [Colocate storage and compute in the same zone/region](https://docs.cloud.google.com/architecture/migrate-across-regions/prepare-data-and-batch-workloads)
- [Avoid long-lived service account keys](https://docs.cloud.google.com/iam/docs/best-practices-for-managing-service-account-keys)
- [Use attached service accounts or Workload Identity Federation](https://docs.cloud.google.com/iam/docs/best-practices-service-accounts)

---

## 1. Мотивация и экономика

### Проблема

PolicyOS pipeline `scientist_policy_design` включает два принципиально разных типа
нагрузки:

| Тип              | Характеристика               | Длительность      | Стоимость ресурса    |
| ---------------- | ---------------------------- | ----------------- | -------------------- |
| **LLM-фаза**     | Network-bound, CPU idle 95%+ | 5-30 мин за цикл  | ~$0.001 (LLM tokens) |
| **Compute-фаза** | GPU-bound, JAX scan+grad     | 10-50 мин за цикл | ~$0.15-0.25 (GPU/hr) |

При монолитном развёртывании GPU-инстанс простаивает во время LLM-вызовов, а LLM-вызовы
блокируют pipeline, ожидая compute. Разделение устраняет обе проблемы.

### Экономика одного цикла policy design

```text
Монолитный (GPU всё время):
  Wall-time: ~60-90 мин
  GPU cost:  ~$0.28/hr × 1.5 hr = $0.42
  LLM cost:  ~$0.001
  Total:     ~$0.42

Split (GPU только на compute):
  LLM wall-time: 15-30 мин (дешёвый сервер)
  GPU wall-time: 25-50 мин (spot)
  GPU cost:  ~$0.28/hr × 0.7 hr = $0.20
  LLM cost:  ~$0.001
  Дешёвый сервер: ~$0.004/hr × 0.5 hr = $0.002
  Total:     ~$0.20

Экономия: ~48% на GPU при одном цикле.
```

При итеративном loop (3-5 циклов) экономия растёт: LLM-фазы между вычислениями
не потребляют GPU вообще.

### Сценарий с $300 free credits (GCP)

| Режим                              | Стоимость/run | Runs на $300 |
| ---------------------------------- | ------------- | ------------ |
| Монолитный GPU (on-demand)         | $0.42         | ~714         |
| Монолитный GPU (spot)              | $0.20         | ~1,500       |
| **Split (spot GPU + дешёвый LLM)** | **$0.15**     | **~2,000**   |

---

## 2. Compute Profile по стадиям pipeline

### Классификация всех workflow nodes

Данные получены из анализа исходного кода `src/polisyos/scientist/nodes/builtins/`.
Каждый node классифицирован по реальным вызовам: какие ports он использует, вызывает ли
LLM, обращается ли к Foundry compile/execute.

#### LLM-Heavy Nodes (вызывают LLM API)

| Node                              | Что делает                              | Вызовы                         | Типичное время |
| --------------------------------- | --------------------------------------- | ------------------------------ | -------------- |
| `PlanPolicyRequestNode`           | Формулирует policy problem              | LexPlanningService (LLM)       | 10-30 сек      |
| `BuildSourcePackNode`             | Собирает source evidence pack           | LLM extraction                 | 30-120 сек     |
| `SourceVerifyNode`                | Верифицирует legal sources              | LLM verification loop          | 60-300 сек     |
| `SourceGapReviewNode`             | Ищет пробелы в evidence                 | LLM gap analysis (до 2 циклов) | 60-180 сек     |
| `DraftPolicyOptionsNode`          | Генерирует policy варианты              | LexDraftingService (LLM)       | 30-120 сек     |
| `RunPolicyTranslationNode`        | Переводит policy в target формат        | PolicyTranslatorWorker (LLM)   | 15-60 сек      |
| `RunHierarchicalPolicySearchNode` | Hierarchical search Level 3 (narrative) | LLM narrative generation       | 30-120 сек     |

**Суммарно**: 200-800 LLM вызовов за полный цикл, ~1-2M tokens, $0.0007-0.0014.

#### Compute-Heavy Nodes (JAX/Foundry)

| Node                              | Что делает                      | Вызовы                            | CPU time   | GPU time  |
| --------------------------------- | ------------------------------- | --------------------------------- | ---------- | --------- |
| `CompileFoundryNode`              | Trinity → ExecPlan              | `ctx.foundry.compile()`           | 0.5-10 сек | —         |
| `RunSimulationNode`               | Execute plan → SimulationResult | `ctx.foundry.execute()`           | 2-60 сек   | 0.1-2 сек |
| `RunCausalEvaluationNode`         | Causal query execution          | DoWhy/EconML (CPU)                | 5-30 сек   | —         |
| `RunCausalEnsembleNode`           | ×10 SCM members                 | DoWhy/EconML (CPU)                | 30-300 сек | —         |
| `RunTransportabilityNode`         | TR algorithm                    | Causal methods (CPU)              | 5-30 сек   | —         |
| `PropagateUncertaintyNode`        | Uncertainty propagation         | JAX (GPU-accelerated)             | 5-30 сек   | 0.5-3 сек |
| `RunDistributionalAnalysisNode`   | Distribution analysis           | NumPy/JAX                         | 2-10 сек   | 0.5-2 сек |
| `RunHierarchicalPolicySearchNode` | Funnel Levels 0-5 (eval)        | Foundry compile+sim per candidate | 5-180 сек  | 1-30 сек  |

**Суммарно**: 60-640 сек CPU, 2-37 сек GPU. При policy search с funnel — ×50-200 evaluations.

#### Causal Discovery (CPU-only, не ускоряется GPU)

| Node                                   | Что делает                      | Время             |
| -------------------------------------- | ------------------------------- | ----------------- |
| `BuildLiteraturePriorNode`             | Query Academic SKG              | 5-15 сек (DuckDB) |
| `ReconcileCausalGraphNode`             | Merge data + literature + hints | 10-60 сек (CPU)   |
| `CounterfactualIdentificationGateNode` | ID algorithm check              | 1-5 сек (CPU)     |

#### Data & Pure Logic (минимальная нагрузка)

| Node                            | Что делает                  | Время               |
| ------------------------------- | --------------------------- | ------------------- |
| `BuildDataSnapshotNode`         | Load pre-built snapshot ref | <1 сек (CAS lookup) |
| `BindFoundryInputsNode`         | Parameter binding           | <1 сек              |
| `DataPlaneGateNode`             | Validation                  | <0.1 сек            |
| `CompileCrossGraphEvidenceNode` | DuckDB queries              | 2-10 сек            |
| `RunGovernanceNode`             | 20 governance passes        | 1-5 сек             |
| `LegalCheckNode`                | Lex evaluate                | 1-3 сек             |
| `RunNormativeArbitrationNode`   | Tradeoff analysis           | <1 сек              |
| `BuildDecisionPacketNode`       | Assembly                    | <1 сек              |
| `FormalizVerifiedPolicyNode`    | PolicyOptionSet → Trinity   | <1 сек              |

### Итоговый compute budget (один цикл policy_design)

```text
LLM nodes:      4-15 мин wall-time, ~0% CPU, ~0% GPU
Causal nodes:    1-6 мин wall-time, ~100% CPU (8 cores), 0% GPU
Foundry nodes:   0.5-3 мин wall-time, ~50% CPU, ~100% GPU
Search funnel:   5-20 мин wall-time, ~80% CPU, ~80% GPU (batched evals)
DuckDB queries:  0.5-2 мин wall-time, ~30% CPU, 0% GPU
Governance:      0.2-1 мин wall-time, ~10% CPU, 0% GPU
─────────────────────────────────────────────────────────
Total:           ~12-47 мин wall-time
GPU active:      ~6-23 мин (50-60% утилизация при монолите)
```

---

## 3. Целевая архитектура

### Принцип разделения

Два класса серверов с общим CAS (Content-Addressable Storage) через GCS bucket:

```text
┌─────────────────────────────────────────────────────────┐
│                    GCS Bucket (shared CAS)               │
│                                                          │
│  polisyos-cas/                                          │
│  ├── sha256/<ab>/<cd>/<hex>.blob                        │
│  ├── sha256/<ab>/<cd>/<hex>.manifest.json               │
│  └── knowledge/                                         │
│      ├── academic.duckdb    (~1.2 GB, read-only)        │
│      ├── datasets.duckdb    (~1.2 GB, read-only)        │
│      └── world.duckdb       (~100 MB-1 GB)              │
└────────────┬───────────────────────────┬────────────────┘
             │                           │
     ┌───────▼───────┐          ┌───────▼────────┐
     │  LLM Server   │          │  GPU Worker    │
     │  (постоянный) │          │  (по запросу)  │
     │               │          │                │
     │  CPX21/e2-std │          │  g2-standard-8 │
     │  4 vCPU       │          │  8 vCPU + L4   │
     │  8 GB RAM     │          │  32 GB RAM     │
     │               │          │                │
     │  Роли:        │          │  Роли:         │
     │  • Orchestrator│          │  • Foundry     │
     │  • LLM nodes  │          │  • Calibration │
     │  • Runtime API │          │  • Search eval │
     │  • Dashboard  │          │  • Causal      │
     │  • CAS L1 cache│          │  • CAS L1 cache│
     └───────────────┘          └────────────────┘
```

### Поток данных (один цикл)

```text
LLM Server                              GPU Worker
──────────                              ──────────

1. User → POST /api/v1/control/runs
   (trinity_bundle_ref, data_source)

2. LLM Phase:
   PlanPolicyRequest (LLM)
   BuildSourcePack (LLM)
   SourceVerify (LLM loop)
   SourceGapReview (LLM)
   DraftPolicyOptions (LLM)
   → PolicyCandidateSet artifact → CAS (GCS)
                                    │
3. Trigger GPU worker               │
   gcloud compute instances start   │
                                    ▼
                              4. GPU Worker starts
                                 Pull artifacts from CAS (GCS)
                                 Compile Trinity (Foundry)
                                 Calibration (JAX scan+grad)
                                 Search Funnel (Levels 0-5)
                                 Causal Ensemble (×10 SCM)
                                 Full-fidelity Simulation
                                 Governance Passes
                                 → EvaluationResultSet → CAS (GCS)
                                 Self-shutdown
                                    │
5. Pull results from CAS (GCS)     │
   ← ──────────────────────────────┘

6. LLM Analysis:
   Interpret results (LLM)
   ConstraintCritic → mutations (LLM)
   Generate refined candidates (LLM)

7. Converged?
   YES → BuildDecisionPacket → done
   NO  → goto step 3 (next cycle)
```

### Что остаётся неизменным

- **Foundry/LLM node business logic желательно не переписывать**, но orchestration,
  CAS wiring и checkpoint/resume semantics сейчас всё-таки требуют кода. Тезис
  "вообще без модификаций PolicyOS" для текущей ветки слишком оптимистичен.

- CAS protocol идентичен для обоих серверов (один GCS bucket).
- Knowledge graphs — read-only `.duckdb` файлы, скопированные на оба сервера.

---

## 4. Рекомендации по железу

### LLM Server (постоянный, ~$4-8/мес)

**Задачи**: Runtime API, LLM orchestration, Dashboard, CAS caching.

**Нагрузка**: Минимальная CPU, основные ожидания — network I/O (LLM API calls).

**Рекомендация**: Hetzner CPX21 или GCP e2-standard-2

| Параметр | CPX21 (Hetzner) | e2-standard-2 (GCP)                        |
| -------- | --------------- | ------------------------------------------ |
| vCPU     | 3               | 2                                          |
| RAM      | 4 GB            | 8 GB                                       |
| Disk     | 80 GB SSD       | 50 GB pd-balanced                          |
| Цена     | €4.15/мес       | ~$48/мес (on-demand) или $0 с free credits |
| Network  | 20 TB           | Standard Tier                              |

**Почему хватает 4-8 GB RAM:**

- Runtime API (FastAPI + Uvicorn): ~300 MB
- DuckDB knowledge graphs (read-only, memory-mapped): ~500 MB working set
- CAS L1 cache: configurable, ~200 MB hot set
- Python + imports: ~400 MB
- **Total peak: ~1.5-2 GB**

LLM nodes не загружают данные в RAM — они отправляют prompt через HTTP, ожидают response,
парсят JSON. Memory footprint — минимальный.

**Disk**: Knowledge graphs (~3 GB) + CAS L1 cache (~5-10 GB) + OS = 20-30 GB. 80 GB SSD
с запасом.

### GPU Worker (по запросу, $0.20-0.28/hr spot)

**Задачи**: Foundry compile/execute, calibration, policy search evaluation, causal methods.

**Нагрузка**: JAX scan+grad (GPU), DoWhy/EconML (CPU), DuckDB queries (CPU).

**Рекомендация**: GCP g2-standard-8 (Spot/Preemptible)

| Параметр       | g2-standard-8                        |
| -------------- | ------------------------------------ |
| vCPU           | 8 (AMD EPYC)                         |
| RAM            | 32 GB                                |
| GPU            | NVIDIA L4 (24 GB VRAM, Ada Lovelace) |
| Disk           | 200 GB pd-balanced                   |
| Цена Spot      | ~$0.25-0.34/hr                       |
| Цена On-demand | ~$0.84/hr                            |
| Region         | us-central1-a (минимальная цена)     |

**Почему 32 GB RAM:**

- Python + JAX + XLA compilation cache: ~4-6 GB
- DuckDB knowledge graphs (memory-mapped): ~1-3 GB
- Foundry GlobalState (5K agents): ~0.2 MB (ничтожно)
- Calibration scan buffers (JAX): 2-4 GB peak
- Causal ensemble (10 SCM, DoWhy objects): ~1-2 GB
- CAS L1 cache: ~500 MB
- **Total peak: ~12-16 GB** (32 GB с запасом для спайков)

**Почему L4 а не T4:**

- L4 (Ada, 2023) vs T4 (Turing, 2018): ~60% быстрее в FP32 compute
- VRAM: 24 GB vs 16 GB — запас для роста числа агентов
- На Spot разница в цене минимальна (~$0.03/hr)

**Почему 8 vCPU:**

- Causal ensemble (10 SCM): параллелизуется хорошо на 8 ядрах
- 16 vCPU даёт +30-40% скорости каузального pipeline, но +55% цены
- Diminishing returns: DoWhy не масштабируется линейно

### Альтернативные конфигурации GPU Worker

| Вариант            | Specs                | Spot $/hr | Для кого                         |
| ------------------ | -------------------- | --------- | -------------------------------- |
| **g2-standard-4**  | 4 vCPU, 16 GB, L4    | ~$0.20    | Минимальный бюджет, <5K agents   |
| **g2-standard-8**  | 8 vCPU, 32 GB, L4    | ~$0.28    | **Рекомендация**                 |
| **g2-standard-16** | 16 vCPU, 64 GB, L4   | ~$0.45    | Большие causal graphs (20+ vars) |
| **a2-highgpu-1g**  | 12 vCPU, 85 GB, A100 | ~$1.10    | >20K agents, research-grade      |

### Sizing для типовых задач

| Задача                         | Agents  | Vars  | GPU Worker     | Est. compute time |
| ------------------------------ | ------- | ----- | -------------- | ----------------- |
| Региональная МСБ-политика      | 1K-5K   | 5-10  | g2-standard-8  | 25-50 мин         |
| Национальная налоговая реформа | 10K-20K | 10-15 | g2-standard-8  | 40-90 мин         |
| Межрегиональный transport      | 5K-10K  | 15-20 | g2-standard-16 | 60-120 мин        |
| Research (ABM bilevel)         | 20K+    | 10+   | a2-highgpu-1g  | 2-4 часа          |

---

## 5. CAS как связующий слой

### Почему CAS

CAS (Content-Addressable Storage) — единственный shared state между серверами. Все
artifacts (Trinity bundles, exec plans, simulation results, checkpoints, knowledge bundles)
хранятся по SHA256 hash. Это обеспечивает:

- **Immutability**: запись не может быть перезаписана (same hash = same content)
- **Idempotency**: повторная запись безопасна
- **Distribution**: любая машина, видящая bucket, видит все артефакты
- **Lineage**: каждый артефакт знает свои inputs через `ArtifactManifest.inputs`

### Конфигурация CAS для split-режима

Целевое состояние: обе машины используют `cached_gcs` backend — локальный L1 cache +
GCS source of truth.

**Важно:** backend factory уже есть в `src/polisyos/core/artifacts/backends/config.py`,
но runtime API и Scientist workflow builder в текущем коде частично обходят его и
создают `FileSystemCAS` напрямую. До реального split rollout это надо исправить.

**Env vars (общие для обоих серверов):**

```bash
# CAS backend
export POLISYOS_CAS_BACKEND=cached_gcs
export POLISYOS_CAS_BUCKET=polisyos-cas-prod        # GCS bucket name
export POLISYOS_CAS_PREFIX=polisyos-cas              # Prefix in bucket

# L1 cache (локальный, разный path на каждом сервере)
export POLISYOS_CAS_LOCAL_CACHE_DIR=/data/cas_cache  # GPU worker
# или
export POLISYOS_CAS_LOCAL_CACHE_DIR=~/.polisyos/cas/_cache  # LLM server
```

### Layout в GCS

```text
gs://polisyos-cas-prod/
  polisyos-cas/
    sha256/
      ab/cd/abcdef...789.blob              # Artifact content
      ab/cd/abcdef...789.manifest.json     # Artifact metadata
      ab/cd/abcdef...789.sig               # Ed25519 signature (optional)
```

### Поведение CachingArtifactStore

Реализован в `src/polisyos/core/artifacts/backends/caching_store.py`:

```text
Write path:
  1. put_bytes(blob) → compute sha256
  2. Write to local FileSystemCAS
  3. Write to remote GCSArtifactStore (сейчас последовательно после local write)
  4. Return ArtifactRef

Read path:
  1. Check local FileSystemCAS
  2. Cache hit → return immediately
  3. Cache miss → fetch from GCS → save to local → return

Verify path:
  1. Check local cache
  2. If present → verify locally
  3. If absent → verify remotely
```

### Размеры типичных артефактов

| Artifact Kind               | Размер       | Примечание                   |
| --------------------------- | ------------ | ---------------------------- |
| `ir.trinity_bundle`         | 5-50 KB      | JSON, compact                |
| `foundry.exec_plan`         | 10-100 KB    | Compiled plan                |
| `foundry.program_graph`     | 20-200 KB    | DAG nodes/edges              |
| `foundry.simulation_result` | 50 KB-5 MB   | Зависит от n_agents, n_steps |
| `foundry.state_delta`       | 100 KB-10 MB | Per-step patches             |
| `scientist.checkpoint`      | 50-500 KB    | Serialized ExperimentState   |
| `fabric.data_snapshot`      | 1-100 MB     | Data references + metadata   |
| `governance.report`         | 10-50 KB     | Pass results                 |
| `scholar.knowledge_bundle`  | 100 KB-5 MB  | Literature evidence          |

**Total per run**: ~10-50 MB артефактов.

**Network cost caveat:** GCS/Compute трафик без доплаты — только когда compute и bucket
находятся в одном регионе Google Cloud и доступ идёт как VM→Google service внутри
GCP. Если LLM Server остаётся на Hetzner, то чтение артефактов из GCS в Hetzner —
это уже Internet egress + дополнительная latency. Best practice для минимальной
стоимости и задержки — держать data storage и compute в одном регионе/зоне, а если
нужен Hetzner UI/API, минимизировать частоту CAS pulls на Hetzner стороне.

### ArtifactRef — ключ обмена между серверами

```python
ArtifactRef(
    artifact_id="sha256:a1b2c3d4e5f6...",  # Content hash
    kind="foundry.simulation_result",       # Semantic type
    media_type="application/json"           # Content type
)
```

LLM Server генерирует артефакт → пишет в CAS → передаёт `artifact_id` строку →
GPU Worker читает из CAS по `artifact_id`. Никакого другого shared state нет.

---

## 6. Knowledge Graphs: сборка и раздача

### Три knowledge graph

| Graph                | DuckDB файл       | Примерный размер | Build pipeline                           |
| -------------------- | ----------------- | ---------------- | ---------------------------------------- |
| **Academic SKG**     | `academic.duckdb` | ~1.2 GB          | `academic/batch/` (16 stages, LLM-heavy) |
| **Datasets Catalog** | `datasets.duckdb` | ~1.2 GB          | `datasets/batch/` (14 stages)            |
| **World Store**      | `world.duckdb`    | ~100 MB-1 GB     | `fabric/world/materialize/`              |

### Read-only at runtime

Все runtime DuckDB connections открываются с `read_only=True`:

```python
# src/polisyos/data_forge/domains/academic/knowledge/store.py
self._con = duckdb.connect(str(db_path), read_only=True)

# src/polisyos/data_forge/domains/catalog/knowledge/store.py
self._con = duckdb.connect(str(db_path), read_only=True)
```

Это означает:

- Knowledge graphs **не модифицируются** во время run
- Безопасный concurrent access (нет write locks)
- Файлы можно скопировать на любое количество серверов

### Стратегия: build once, distribute

```text
1. Build Phase (выполняется редко, на LLM Server или отдельной машине):
   ┌────────────────────────────────┐
   │  python -m polisyos.data_forge.domains.academic.batch.pipeline  │
   │  python -m polisyos.data_forge.domains.catalog.batch.pipeline  │
   │  → academic.duckdb, datasets.duckdb          │
   └──────────────────┬─────────────────────────────┘
                      │
2. Upload to GCS:     ▼
   gsutil cp academic.duckdb gs://polisyos-cas-prod/knowledge/
   gsutil cp datasets.duckdb gs://polisyos-cas-prod/knowledge/

3. Download on workers (при старте или по cron):
   gsutil cp gs://polisyos-cas-prod/knowledge/*.duckdb /data/knowledge/
```

### Конфигурация paths

**Target-state env contract:** имена ниже удобны для split deployment, но в текущем
коде они не читаются централизованно. Сейчас `ScholarKnowledgeGraph`, `SKGQuery`,
`DatasetCatalogStore` и связанные компоненты в основном получают `db_path/index_dir`
через конструкторы. Если хотим именно env-driven deployment, этот контракт нужно
дореализовать в ports/adapters.

```bash
# Knowledge graph locations (обе машины)
export POLISYOS_ACADEMIC_DB_PATH=/data/knowledge/academic.duckdb
export POLISYOS_DATASETS_DB_PATH=/data/knowledge/datasets.duckdb
export POLISYOS_WORLD_DB_PATH=/data/knowledge/world.duckdb

# HNSW index directories (для semantic search)
export POLISYOS_ACADEMIC_INDEX_DIR=/data/knowledge/academic_indices/
export POLISYOS_DATASETS_INDEX_DIR=/data/knowledge/datasets_indices/
```

### RAM impact при runtime queries

DuckDB использует memory-mapped I/O. Реальное потребление зависит от queries:

| Query type                         | Estimated RAM    | Частота               |
| ---------------------------------- | ---------------- | --------------------- |
| Variable canonicalization          | 50-100 MB        | Per evidence need     |
| Edge support lookup                | 100-300 MB       | Per causal edge       |
| Parameter candidates               | 50-200 MB        | Per Trinity parameter |
| Transport scoring                  | 100-300 MB       | Per context pair      |
| Cross-graph compilation (суммарно) | 500 MB-2 GB peak | Once per run          |

На LLM Server (8 GB) cross-graph compilation пройдёт без проблем.
На GPU Worker (32 GB) — с большим запасом.

### Обновление knowledge graphs

Knowledge graphs обновляются **отдельно** от compute pipeline:

```text
Frequency:
  Academic SKG — еженедельно/ежемесячно (новые публикации)
  Datasets Catalog — еженедельно (новые датасеты)
  World Store — per-ingestion (факты из Fabric connectors)

Process:
  1. Запустить batch pipeline на LLM Server (или отдельной build машине)
  2. Загрузить в GCS
  3. На следующем старте GPU Worker скачает новую версию
  4. Версионирование через timestamp в filename:
     academic_2026w14.duckdb, academic_2026w15.duckdb
```

---

## 7. Протокол оркестрации

### Вариант A: REST API оркестрация (рекомендуемый)

LLM Server запускает полный Runtime API (`uvicorn`). GPU Worker запускается как
headless compute backend, вызываемый через gcloud API.

```python
# orchestrator.py на LLM Server (pseudo-code)

async def run_policy_design_split(trinity_ref: str, data_source_ref: str):
    """Iterative LLM/Compute split loop."""

    cas = build_artifact_store(ArtifactStoreConfig.from_env())

    for cycle in range(max_cycles):
        # ═══════ LLM PHASE (local) ═══════
        # Выполняем LLM-heavy nodes напрямую через Scientist API
        candidates = await run_llm_phase(
            cas=cas,
            trinity_ref=trinity_ref,
            data_source_ref=data_source_ref,
            previous_results_ref=previous_eval_ref,  # None on first cycle
        )
        # → candidates artifact persisted to CAS (→ GCS)
        candidates_ref = candidates.artifact_id

        # ═══════ GPU PHASE (remote) ═══════
        # 1. Start GPU worker
        start_gpu_instance()

        # 2. Trigger compute via SSH / REST / gcloud ssh
        eval_ref = await trigger_compute_phase(
            gpu_host=GPU_INSTANCE_IP,
            trinity_ref=trinity_ref,
            data_source_ref=data_source_ref,
            candidates_ref=candidates_ref,
        )
        # GPU worker writes results to CAS (→ GCS), then self-stops

        # 3. Read results from CAS
        eval_result = cas.get_json(eval_ref)

        # ═══════ CONVERGENCE CHECK (local) ═══════
        if is_converged(eval_result, candidates):
            break

        previous_eval_ref = eval_ref

    # ═══════ FINALIZE (local) ═══════
    decision_packet = build_decision_packet(cas, eval_ref, candidates_ref)
    return decision_packet
```

### Вариант B: Checkpoint-based split

Использует встроенный checkpoint/resume, но **не как текущий zero-code путь**, а как
основу для доработки intentional pause/resume:

```text
1. LLM Server: Запустить scientist_policy_design workflow
   → Checkpoint policy: "strict"
   → Workflow выполняет LLM nodes
   → Доходит до split marker перед compute-сегментом → checkpoint → PAUSE

2. GPU Worker: Resume from checkpoint
   → Load checkpoint from CAS
   → Выполнить compute-heavy nodes
   → Checkpoint на split marker после compute-сегмента → PAUSE

3. LLM Server: Resume from checkpoint
   → Load results
   → LLM analysis → refined candidates
   → Если converged → finalize
   → Если нет → checkpoint → goto 2
```

**Плюс:** можно переиспользовать checkpoint artifacts и node-cache.

**Минусы текущей реализации:**

- executor не умеет намеренно останавливаться на границе split marker;
- resume опирается на node-cache, а не на `completed_nodes` как hard-skip barrier;
- `checkpoint_head.json` и run lock лежат локально в `run_dir`, а не в shared CAS;
- workflow fingerprint проверяет форму DAG, но не environment hash, поэтому
  одинаковые Python/deps версии всё равно надо обеспечить операционно.

### Вариант C: Control Plane API (максимально нативный)

Runtime API уже поддерживает запуск **полного** workflow run с pre-built artifact refs.
Как target-state это хороший путь для split-оркестрации, но пример ниже требует
API/engine доработок, чтобы GPU worker исполнял только compute-сегмент.

```bash
# На GPU Worker — запустить headless Runtime API
uvicorn 'polisyos.runtime.http.app:create_runtime_api_app' \
  --factory --host 0.0.0.0 --port 8000

# С LLM Server — POST запрос на GPU Worker
curl -X POST http://${GPU_WORKER_IP}:8000/api/v1/control/runs \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "workflow",
    "data_source": {
      "data_snapshot_ref": "sha256:abc123..."
    },
    "trinity_bundle_ref": "sha256:def456...",
    "knowledge_bundle_ref": "sha256:789abc...",
    "norm_pack_ref": "sha256:012def...",
    "calibration_report_ref": "sha256:345ghi...",
    "checkpoint_policy": "strict",
    "execution_profile": "research",
    "params": {
      "workflow_id": "scientist_policy_design",
      "split_phase": "compute_only",
      "policy_candidate_schema": { "...": "..." }
    }
  }'
```

Response:

```json
{
  "status": "accepted",
  "run_id": "R_...",
  "job_id": "...",
  "effective_execution_profile": "research"
}
```

Polling:

```bash
# SSE streaming (real-time)
curl -N http://${GPU_WORKER_IP}:8000/api/v1/runs/${RUN_ID}/live

# или polling
curl http://${GPU_WORKER_IP}:8000/api/v1/control/jobs/${JOB_ID}
# → {"state": "running"} ... {"state": "completed"}
```

Retrieve results:

```bash
curl http://${GPU_WORKER_IP}:8000/api/v1/runs/${RUN_ID}
# → {"root_artifacts": ["sha256:result1...", "sha256:result2..."]}
```

**WorkflowRunRequest** поддерживает следующие pre-built artifact refs:

| Field                           | Назначение                                                                          |
| ------------------------------- | ----------------------------------------------------------------------------------- |
| `data_source.data_snapshot_ref` | Pre-built data snapshot                                                             |
| `trinity_bundle_ref`            | Pre-compiled Trinity bundle                                                         |
| `knowledge_bundle_ref`          | Pre-built knowledge evidence                                                        |
| `norm_pack_ref`                 | Pre-assembled legal norm pack                                                       |
| `calibration_report_ref`        | Previous calibration results                                                        |
| `params` (dict)                 | Arbitrary workflow parameters, но только те, которые реально читают Scientist nodes |

### Рекомендация

**Практически сейчас:** начинать с **Варианта A** — явный orchestrator на LLM Server +
отдельный compute-only entrypoint/workflow на GPU Worker после P0 fixes.

**Target-state:** **Вариант C** — самый нативный, когда Control Plane получит
официальный partial-workflow/resume контракт. Тогда GPU Worker поднимает стандартный
Runtime API, LLM Server отправляет POST с artifact refs, а SSE streaming остаётся
единым мониторингом.

**Вариант B** не рекомендую как основной production путь, пока checkpoint head/run lock
не вынесены в shared durable слой и нет explicit pause markers.

---

## 8. Конфигурация окружений

### LLM Server — env файл

```bash
# ═══════ Core ═══════
export POLISYOS_ENV=production
export POLISYOS_EXECUTION_PROFILE=research

# ═══════ CAS ═══════
export POLISYOS_CAS_BACKEND=cached_gcs
export POLISYOS_CAS_BUCKET=polisyos-cas-prod
export POLISYOS_CAS_PREFIX=polisyos-cas
export POLISYOS_CAS_LOCAL_CACHE_DIR=/home/polisyos/.cas_cache

# ═══════ Knowledge Graphs ═══════
export POLISYOS_ACADEMIC_DB_PATH=/data/knowledge/academic.duckdb
export POLISYOS_DATASETS_DB_PATH=/data/knowledge/datasets.duckdb
export POLISYOS_WORLD_DB_PATH=/data/knowledge/world.duckdb

# ═══════ LLM ═══════
export POLISYOS_LLM_GATEWAY_BASE_URL=https://your-llm-provider.com/v1
export POLISYOS_LLM_GATEWAY_PROVIDER=openai_compatible

# ═══════ Runtime API ═══════
export POLISYOS_CONTROL_WORKER_BACKEND=embedded
export POLISYOS_CONTROL_STATE_STORE_BACKEND=sqlite
export POLISYOS_CONTROL_SQLITE_PATH=/data/control/state.db
export POLISYOS_CONTROL_MAX_WORKERS=2
export POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE=true

# ═══════ Auth (dev/research — упрощённый) ═══════
export POLISYOS_AUTHN_ENABLED=false
export POLISYOS_AUTHZ_MODE=off

# ═══════ Observability ═══════
export POLISYOS_OTEL_ENABLED=true
export POLISYOS_OTEL_CONSOLE_EXPORT=true
```

### GPU Worker — env файл

```bash
# ═══════ Core ═══════
export POLISYOS_ENV=production
export POLISYOS_EXECUTION_PROFILE=research

# ═══════ CAS (тот же bucket, другой local cache) ═══════
export POLISYOS_CAS_BACKEND=cached_gcs
export POLISYOS_CAS_BUCKET=polisyos-cas-prod
export POLISYOS_CAS_PREFIX=polisyos-cas
export POLISYOS_CAS_LOCAL_CACHE_DIR=/data/cas_cache

# ═══════ Knowledge Graphs ═══════
export POLISYOS_ACADEMIC_DB_PATH=/data/knowledge/academic.duckdb
export POLISYOS_DATASETS_DB_PATH=/data/knowledge/datasets.duckdb
export POLISYOS_WORLD_DB_PATH=/data/knowledge/world.duckdb

# ═══════ JAX GPU ═══════
export JAX_PLATFORM_NAME=gpu
export XLA_PYTHON_CLIENT_PREALLOCATE=false
export XLA_PYTHON_CLIENT_MEM_FRACTION=0.7

# ═══════ Runtime API (headless) ═══════
export POLISYOS_CONTROL_WORKER_BACKEND=embedded
export POLISYOS_CONTROL_STATE_STORE_BACKEND=sqlite
export POLISYOS_CONTROL_SQLITE_PATH=/tmp/control.db
export POLISYOS_CONTROL_MAX_WORKERS=1
export POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE=true

# ═══════ Auth ═══════
export POLISYOS_AUTHN_ENABLED=false
export POLISYOS_AUTHZ_MODE=off

# ═══════ Observability ═══════
export POLISYOS_OTEL_ENABLED=true
export POLISYOS_OTEL_CONSOLE_EXPORT=true
```

### JAX GPU verification

```bash
# Убедиться, что JAX видит GPU
python -c "
import jax
print('Devices:', jax.devices())
print('Default backend:', jax.default_backend())
x = jax.numpy.ones(1000)
print('Test computation:', float(jax.numpy.sum(x)))
"
# Expected output:
# Devices: [GpuDevice(id=0, device_kind='NVIDIA L4')]
# Default backend: gpu
# Test computation: 1000.0
```

---

## 9. Lifecycle GPU-инстанса

### Startup script (GPU Worker)

**Best practice:** на GCE не копировать JSON service account key в образ.
Прикрепить к VM/MIG отдельный least-privilege service account и дать ему доступ
к нужному bucket. `gsutil`/Google SDK возьмут short-lived credentials через metadata
server автоматически.

```bash
#!/bin/bash
# /opt/polisyos/start-worker.sh
set -euo pipefail

# 1. Activate environment
source /opt/polisyos/env.sh

# 2. Sync knowledge graphs from GCS (if updated)
gsutil -m rsync -r gs://polisyos-cas-prod/knowledge/ /data/knowledge/

# 3. Verify JAX GPU
python -c "import jax; assert jax.default_backend() == 'gpu', 'No GPU!'"

# 4. Start Runtime API (headless, single worker)
uvicorn 'polisyos.runtime.http.app:create_runtime_api_app' \
  --factory \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --timeout-keep-alive 300 \
  &

UVICORN_PID=$!

# 5. Wait for health check
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "Runtime API ready"
    break
  fi
  sleep 2
done

# 6. Signal ready (write to GCS metadata or stdout)
echo "GPU Worker ready at $(hostname -I | awk '{print $1}'):8000"

# 7. Wait for process
wait $UVICORN_PID
```

### Auto-shutdown script

```bash
#!/bin/bash
# /opt/polisyos/auto-shutdown.sh
# Запускается через cron каждые 5 минут
# Если нет активных runs — shutdown

ACTIVE_RUNS=$(curl -sf http://localhost:8000/api/v1/runs?status=running | \
  python3 -c "import sys,json; print(len(json.load(sys.stdin).get('runs',[])))" 2>/dev/null || echo "0")

IDLE_FILE="/tmp/polisyos_idle_since"

if [ "$ACTIVE_RUNS" = "0" ]; then
  if [ ! -f "$IDLE_FILE" ]; then
    date +%s > "$IDLE_FILE"
    echo "No active runs. Starting idle timer."
  else
    IDLE_SINCE=$(cat "$IDLE_FILE")
    NOW=$(date +%s)
    IDLE_SECONDS=$((NOW - IDLE_SINCE))
    if [ "$IDLE_SECONDS" -gt 600 ]; then  # 10 min idle → shutdown
      echo "Idle for ${IDLE_SECONDS}s. Shutting down."
      rm -f "$IDLE_FILE"
      sudo shutdown -h now
    fi
  fi
else
  rm -f "$IDLE_FILE"
fi
```

**Preemption best practice:** для Spot VM добавить shutdown script, который за 30-секундный
best-effort grace period успевает зафиксировать финальный heartbeat/job status и не
полагается только на cron idle shutdown. Если используется MIG, помнить, что при
дефиците capacity группа может не пересоздать Spot GPU VM сразу.

### Управление с LLM Server

```bash
# Запуск GPU Worker
gcloud compute instances start gpu-worker --zone=us-central1-a

# Получить IP
GPU_IP=$(gcloud compute instances describe gpu-worker \
  --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

# Дождаться готовности
until curl -sf http://${GPU_IP}:8000/api/v1/health; do sleep 5; done

# Запустить compute run
curl -X POST http://${GPU_IP}:8000/api/v1/control/runs \
  -H "Content-Type: application/json" \
  -d @compute_request.json

# Мониторинг через SSE
curl -N http://${GPU_IP}:8000/api/v1/runs/${RUN_ID}/live

# Остановка (или auto-shutdown через 10 мин idle)
gcloud compute instances stop gpu-worker --zone=us-central1-a
```

### Время lifecycle GPU инстанса

```text
gcloud start         → ~30-60 сек (spot instance provisioning)
OS boot + CUDA init  → ~30-60 сек
KG sync from GCS     → ~30-60 сек (3 GB, первый раз; затем rsync <5 сек)
Uvicorn startup      → ~10-15 сек (JAX XLA init + imports)
Health check ready   → ~5 сек
────────────────────────────────────
Total cold start:      ~2-3 мин
Total warm start:      ~1-1.5 мин (KG cached, no download)
```

---

## 10. Fault Tolerance и Checkpoint

### Checkpoint при spot preemption

GCP Spot instances могут быть прерваны с 30-секундным уведомлением.
PolicyOS Scientist записывает checkpoint после **каждого** успешного node:

```python
# src/polisyos/scientist/engine/checkpoint.py
class CASCheckpointHook:
    def on_node_complete(self, alias, state, cache_refs):
        artifact = CheckpointArtifact(
            metadata=CheckpointMetadata(
                run_id=self.run_id,
                sequence_number=self._seq,
                completed_node_alias=alias,
                completed_nodes=list(self._completed),
                workflow_fingerprint=self._fingerprint,
                writer_hostname=socket.gethostname(),
            ),
            state=state.model_dump(),
        )
        ref = self.store.put_json(artifact.model_dump(), ...)
```

**Worst case при preemption**: потеря одного node execution (последний, до checkpoint).
При re-start workflow resume с последнего checkpoint.

### Recovery flow

```text
1. Spot preemption → GPU Worker killed
2. LLM Server detects: SSE stream closes / poll returns error
3. LLM Server restarts GPU Worker:
   gcloud compute instances start gpu-worker

4. GPU Worker boots, syncs KG, starts Runtime API

5. LLM Server resumes run:
   Target-state: отдельный resume endpoint или `workflow_run` job с явным resume contract
   {
     "run_id": "R_...",
     "checkpoint_ref": "sha256:...",
     "workflow_id": "scientist_policy_design"
   }

6. Scientist loads checkpoint from CAS:
   → Validates workflow fingerprint
   → Restores ExperimentState
   → Skips completed nodes (from cache)
   → Continues from next node
```

### Checkpoint metadata

```json
{
  "schema_version": "1.0",
  "run_id": "R_abc123",
  "sequence_number": 7,
  "completed_node_alias": "run_simulation",
  "completed_nodes": [
    "start",
    "build_data_snapshot",
    "build_execution_plan",
    "link_trinity",
    "compile_foundry",
    "bind_foundry_inputs",
    "run_simulation"
  ],
  "workflow_id": "scientist_policy_design",
  "workflow_fingerprint": "sha256:...",
  "writer_hostname": "gpu-worker-abc",
  "created_at": "2026-04-04T14:30:00Z"
}
```

### Что checkpoint НЕ спасает

- **JAX XLA compilation cache** — при restart JIT-перекомпилирует (30-60 сек)
- **DuckDB connection state** — переоткрывается при resume
- **In-flight HTTP requests** — LLM вызовы не resumable (retry from scratch)

---

## 11. Мониторинг и observability

### SSE streaming с LLM Server

LLM Server как orchestrator мониторит GPU Worker через SSE:

```python
import httpx

async def monitor_run(gpu_host: str, run_id: str):
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "GET",
            f"http://{gpu_host}:8000/api/v1/runs/{run_id}/live",
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    event = json.loads(line[5:])
                    print(f"Node: {event.get('current_node')}, "
                          f"Status: {event.get('status')}")
                    if event.get("terminal"):
                        return event
```

### OpenTelemetry spans

Оба сервера экспортируют spans. Для unified view — настроить общий OTLP collector:

```bash
# На обоих серверах
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
export OTEL_SERVICE_NAME=polisyos-llm-server  # или polisyos-gpu-worker
export POLISYOS_OTEL_ENABLED=true
```

### Ключевые метрики

| Метрика                        | Источник   | Что показывает              |
| ------------------------------ | ---------- | --------------------------- |
| `node_duration_seconds`        | Both       | Время каждого workflow node |
| `artifact_io_bytes`            | Both       | CAS read/write volume       |
| `artifact_io_duration_seconds` | Both       | CAS latency (L1 vs GCS)     |
| `gpu_utilization`              | GPU Worker | nvidia-smi GPU %            |
| `jax_compilation_seconds`      | GPU Worker | XLA JIT overhead            |
| `llm_request_duration`         | LLM Server | LLM API latency             |
| `llm_tokens_total`             | LLM Server | Token consumption           |
| `run_total_duration`           | Both       | Full run wall-time          |

### Health checks

```bash
# LLM Server health
curl http://llm-server:8000/api/v1/health
# → {"status": "healthy", "version": "...", "uptime_seconds": ...}

# GPU Worker health (когда запущен)
curl http://gpu-worker:8000/api/v1/health
# → {"status": "healthy", ...}

# GPU Worker GPU health
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv
```

---

## 12. Масштабирование

### Вертикальное (single user, bigger tasks)

| Сценарий                      | Действие                                                |
| ----------------------------- | ------------------------------------------------------- |
| Больше agents (>10K)          | Upgrade GPU Worker: g2-standard-16 (больше RAM для JAX) |
| Больше causal variables (>20) | Upgrade GPU Worker: больше vCPU (discovery quadratic)   |
| Faster iteration              | Upgrade GPU Worker: a2-highgpu-1g (A100 GPU)            |
| Больше knowledge              | Upgrade LLM Server: больше RAM для DuckDB               |

### Горизонтальное (multiple concurrent users/tasks)

```text
Topology A: Shared LLM Server + GPU Pool

  LLM Server (always-on)
    ├── User A request → GPU Worker 1 (spot)
    ├── User B request → GPU Worker 2 (spot)
    └── User C request → GPU Worker 1 (reuse after A completes)

  CAS: GCS bucket (shared, concurrent-safe)
  KG: Each GPU Worker downloads on start (immutable)
```

**Spot/MIG caveat:** MIG с Spot VMs пытается поддерживать target size, но если в зоне
нет доступной GPU capacity, scale-up/autoscale может временно не сработать. Для
production очереди стоит добавить retry с jitter, multi-zone fallback и явный
fallback на on-demand pool для priority jobs.

```text
Topology B: Per-user LLM + Shared GPU Pool

  LLM Server A (user A) ──┐
  LLM Server B (user B) ──┤→ GPU Worker Pool (managed instance group)
  LLM Server C (user C) ──┘
                              ↕
                           GCS CAS (shared)
```

### Managed Instance Group (GCP)

Для автоматического scaling GPU workers:

```bash
# Создать instance template
gcloud compute instance-templates create gpu-worker-tpl \
  --machine-type=g2-standard-8 \
  --accelerator=type=nvidia-l4,count=1 \
  --boot-disk-size=200GB \
  --metadata-from-file=startup-script=start-worker.sh \
  --preemptible

# Создать managed instance group (min 0, max 4)
gcloud compute instance-groups managed create gpu-pool \
  --template=gpu-worker-tpl \
  --size=0 \
  --zone=us-central1-a

# Scale up перед compute phase
gcloud compute instance-groups managed resize gpu-pool --size=1

# Scale down после completion
gcloud compute instance-groups managed resize gpu-pool --size=0
```

---

## 13. Стоимостная модель

### Стоимость одного полного policy design цикла

**Предположения:**

- Региональная МСБ-политика, 3K agents, 8 variables
- 3 итерации LLM/compute loop
- Knowledge graphs уже собраны

```text
Per iteration:
  LLM phase:     ~400 calls × 2K tokens = 800K tokens × $0.0007/1M = $0.0006
  GPU phase:     ~35 мин × $0.28/hr = $0.16
  LLM Server:    ~20 мин × $0.006/hr = $0.002
  GCS egress:    ~50 MB × $0 (same region) = $0

3 iterations:
  LLM total:     $0.002
  GPU total:     $0.48
  LLM Server:    $0.006
  ─────────────────────
  Grand total:   ~$0.49

Rounded:         ~$0.50 per policy design
```

**Cost caveat:** строка `GCS egress = $0` верна только для GPU Worker ↔ GCS в одном
GCP регионе. Если LLM Server работает в Hetzner и регулярно читает артефакты из
GCS, Internet egress уже не нулевой, а latency выше. Для чистой unit economics
лучше держать LLM/orchestrator рядом с bucket в GCP или вынести на Hetzner только
тонкий UI/API слой без частых CAS fetches.

### Месячная стоимость (active research)

| Компонент                     | Использование         | Стоимость/мес   |
| ----------------------------- | --------------------- | --------------- |
| LLM Server (CPX21, 24/7)      | Always on             | €4.15 (~$4.50)  |
| GPU Worker (spot, ~40 hr/мес) | 80 runs × 30 мин      | ~$11.20         |
| LLM API (~32M tokens/мес)     | 80 runs × 400K tokens | ~$0.02          |
| GCS storage (~10 GB)          | CAS + KGs             | ~$0.20          |
| GCS operations (~100K)        | CAS reads/writes      | ~$0.50          |
| **Total**                     |                       | **~$16.50/мес** |

### Budget allocation для $300 GCP credits

```text
GCS storage + operations:     ~$5     (12 мес)
GPU spot compute:             ~$280   (1000 GPU-hours = ~1700 runs)
Reserved for on-demand:       ~$15    (emergency, ~18 GPU-hours)
────────────────────────────────────
$300 total

При 80 runs/мес = ~21 месяц GPU compute.
LLM Server на Hetzner (вне GCP credits): €4.15/мес.
```

---

## 14. Checklist развёртывания

### Phase 1: GCS Setup

```text
[ ] Создать GCS bucket: polisyos-cas-prod (region: us-central1)
[ ] Настроить lifecycle policy: delete incomplete uploads >7 days
[ ] Создать отдельные single-purpose service accounts:
    [ ] polisyos-gpu-worker@project.iam.gserviceaccount.com
    [ ] polisyos-llm-orchestrator@project.iam.gserviceaccount.com
[ ] Выдать минимально нужные bucket-level роли, без project-wide Editor
[ ] Для GCE worker использовать attached service account без JSON key
[ ] Для Hetzner LLM Server настроить Workload Identity Federation; JSON key — только временный fallback
```

### Phase 2: LLM Server (Hetzner CPX21)

```text
[ ] Создать сервер CPX21 (Falkenstein, €4.15/мес)
[ ] Установить Python 3.14, pip, git
[ ] git clone + pip install -e ".[all]"
[ ] Настроить env vars (секция 8)
[ ] Настроить доступ к GCS через Workload Identity Federation
[ ] Если WIF пока нет — временно использовать JSON key с жёсткими file permissions и планом ротации/удаления
[ ] Собрать knowledge graphs (или скачать готовые)
[ ] gsutil cp KGs → GCS
[ ] Запустить Runtime API: uvicorn ... --factory --host 0.0.0.0
[ ] Проверить: curl http://localhost:8000/api/v1/health
[ ] Настроить systemd service для auto-restart
```

### Phase 3: GPU Worker Template (GCP)

```text
[ ] Создать boot disk image:
    [ ] Base: Ubuntu 22.04 LTS
    [ ] Установить NVIDIA driver + CUDA 12.x
    [ ] Установить Python 3.14
    [ ] pip install jaxlib[cuda12] jax
    [ ] git clone + pip install -e ".[all]"
    [ ] Скопировать env файл + startup script
    [ ] Не класть GCS JSON key в образ; использовать attached service account
    [ ] Snapshot → custom image
[ ] Создать instance template:
    [ ] Machine type: g2-standard-8
    [ ] Boot disk: custom image, 200 GB pd-balanced
    [ ] Provisioning: Spot
    [ ] Attached service account: polisyos-gpu-worker@...
    [ ] Startup script: /opt/polisyos/start-worker.sh
    [ ] Network: allow TCP 8000 (firewall rule)
[ ] Тест: запустить instance, проверить JAX GPU, проверить Runtime API
[ ] Настроить auto-shutdown script (cron)
[ ] Добавить shutdown script для preemption notice и graceful status flush
```

### Phase 4: Integration Test

```text
[ ] С LLM Server:
    [ ] gcloud compute instances start gpu-worker
    [ ] Дождаться health check
    [ ] POST /api/v1/control/runs (тестовый Trinity)
    [ ] Мониторинг через SSE
    [ ] Проверить results в CAS
    [ ] gcloud compute instances stop gpu-worker
[ ] Проверить checkpoint/resume:
    [ ] Запустить run
    [ ] Остановить GPU Worker mid-run
    [ ] Перезапустить GPU Worker
    [ ] Target-state resume contract: продолжить run с явного checkpoint_ref или shared checkpoint head
[ ] Проверить CAS consistency:
    [ ] LLM Server записывает artifact
    [ ] GPU Worker читает тот же artifact (по sha256 ref)
[ ] Проверить, что runtime/scientist действительно используют `cached_gcs`, а не локальный `FileSystemCAS`
```

### Phase 5: Production Hardening

```text
[ ] TLS: nginx reverse proxy на GPU Worker (или GCP load balancer)
[ ] Firewall: ограничить TCP 8000 на GPU Worker только LLM Server / internal VPC
[ ] По возможности убрать public IP у GPU Worker и ходить по internal IP/VPN/IAP tunnel
[ ] Secrets: перенести API keys в GCP Secret Manager
[ ] Не хранить service account JSON keys в Secret Manager как основной путь; предпочтительнее attached SA / WIF
[ ] Monitoring: настроить alerting на GPU idle >15 мин
[ ] Alerting: Spot capacity failures, repeated preemptions, CAS remote-write failures, checkpoint resume failures
[ ] Cost alerts: GCP budget alert на $50, $100, $200
[ ] Backup: GCS bucket versioning для CAS
```

---

## Связанные документы

| Документ              | Путь                                                  |
| --------------------- | ----------------------------------------------------- |
| Runtime Deployment    | `docs/how-to/deploy-runtime.md`                       |
| Architecture Overview | `docs/explanation/architecture.md`                    |
| Control Plane How-to  | `docs/how-to/use-control-plane.md`                    |
| Security Model        | `docs/explanation/security-model.md`                  |
| SLO & Error Budget    | `docs/reference/operations/slo-error-budget.md`       |
| Observability         | `docs/reference/operations/observability-topology.md` |
