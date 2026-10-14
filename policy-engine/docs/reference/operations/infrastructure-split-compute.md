# PolicyOS — Infrastructure Guide: Split LLM/Compute Architecture

> A practical guide to deploying PolicyOS with the LLM phase and compute phase
> on separate servers to optimize cost and throughput.
>
> Note date: 2026-04-04 | Status: historical target-design snapshot; deployment not verified

Owner: `@platform-owners`
Source of truth: this 2026-04-04 target-design note describes proposed topology; live host, quota, capacity, object-store, and billing state must come from the currently authorized provider sources and was not checked here.
Repository source reviewed: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` on 2026-10-14; document/source inspection only. No host, container, data copy, quota, cost, provider, network, or deployment command was run.

> **Historical planning snapshot.** Machine types, memory/disk sizes, GPU
> availability, quotas, file/data sizes, throughput estimates, prices, free
> credits, and monthly/run-cost calculations below are the assumptions recorded
> in the 2026-04-04 note. They were not refreshed against provider pricing,
> project quota, or a deployed environment. Treat the architecture and commands
> as proposals requiring source and environment revalidation, not as a live
> deployment runbook.

---

## Contents

0. [Historical gap assessment (2026-04-04)](#0-historical-gap-assessment-2026-04-04)
1. [Motivation and economics](#1-motivation-and-economics)
2. [Compute profile by pipeline stage](#2-compute-profile-by-pipeline-stage)
3. [Target architecture](#3-target-architecture)
4. [Hardware recommendations](#4-hardware-recommendations)
5. [CAS as the coordination layer](#5-cas-as-the-coordination-layer)
6. [Knowledge graphs: build and distribution](#6-knowledge-graphs-build-and-distribution)
7. [Orchestration protocol](#7-orchestration-protocol)
8. [Environment configuration](#8-environment-configuration)
9. [GPU instance lifecycle](#9-gpu-instance-lifecycle)
10. [Fault tolerance and checkpointing](#10-fault-tolerance-and-checkpointing)
11. [Monitoring and observability](#11-monitoring-and-observability)
12. [Scaling](#12-scaling)
13. [Cost model](#13-cost-model)
14. [Deployment checklist](#14-deployment-checklist)

<a id="0-историческая-оценка-разрывов-2026-04-04"></a>

## 0. Historical gap assessment (2026-04-04)

The tables below preserve findings from the original 2026-04-04 note. Their statements
about the “current code” and P0/P1 gaps were not rechecked against the source snapshot
identified above; treat them as historical hypotheses, not as a current implementation audit.

### Summary

**Architecturally, the split LLM/compute design is described as a target state**; the note said
it was not plug-and-play when written. Before using it, first verify these findings against
the selected source pin and deployment state.

### P0 — blockers according to the note

| Reported gap in the 2026-04-04 note                                                                         | Why the note treated it as a blocker                                                              | Proposed follow-up in that note                                                                                                                  |
| ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `runtime.http` and `scientist.workflows` sometimes instantiate `FileSystemCAS(...)` directly                | The note said `POLISYOS_CAS_BACKEND=cached_gcs` was not picked up end to end from the environment | Route runtime/Scientist wiring through `build_artifact_store(ArtifactStoreConfig.from_env())`, retaining `FileSystemCAS` as the default fallback |
| The note found no explicit "LLM-only → compute-only → LLM-only" phase boundary in `scientist_policy_design` | A GPU-only segment could not be run reliably without rerunning LLM nodes                          | Add a compute-only workflow/profile or executor-level node partitioning with explicit split markers                                              |
| The note described the checkpoint head and run lock as local files in `run_dir`                             | According to the note, resuming on another machine using only GCS CAS was not guaranteed          | Store the checkpoint head/lease in a shared durable store, or add a resume API with an explicit `checkpoint_ref` and external run lease          |
| The note said `POST /api/v1/control/runs` created a new `run_id` without `resume_run_id`                    | The recovery flow in section 10 did not match the API on the note date                            | Add a separate resume endpoint/job kind or extend the `WorkflowRunRequest` contract                                                              |
| The note said code did not read `skip_llm_nodes`, `candidates_ref`, or `POLISYOS_*_DB_PATH`                 | On the note date, configuration examples appeared to be no-ops or errors                          | Either implement this environment/API contract or mark it as target state rather than presenting it as a current runbook                         |

### P1 — follow-up items according to the note

| Reported gap in the 2026-04-04 note                                                                  | Risk stated in the note                                                                          | Proposed follow-up                                                                                                                |
| ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| The note said `RunHierarchicalPolicySearchNode` includes an inner compile/readiness/simulation loop  | The DAG in the note did not match the diagram’s boundary between the "LLM phase" and "GPU phase" | Rebuild the split plan around the actual node call graph and move search evaluation to the GPU side                               |
| The compute budget and node list in section 2 partly differed from the `scientist_policy_design` DAG | Sizing and cost estimates could be optimistic or misattributed                                   | Regenerate the tables from `workflows/policy_design.py` and the inner evaluator path                                              |
| The checklist used downloaded `JSON` service-account keys                                            | Keeping a long-lived service-account key on disk is poor practice and increases blast radius     | Use an attached service account on GCE and Workload Identity Federation on Hetzner; keep `JSON` keys only as a temporary fallback |
| No explicit fallback was described for insufficient Spot GPU capacity                                | MIG/Spot may fail to start the requested group size, leaving the run waiting                     | Add retries with backoff, multi-zone fallback, and a controlled fallback to on-demand capacity                                    |

### Recommended rollout sequence

1. **Phase A — storage/control-plane wiring**: shared CAS from the environment, a correct worker backend,
   a shared checkpoint/resume contract, and verified environment variables.
2. **Phase B — split execution semantics**: a compute-only workflow or node partitioning,
   moving candidate search evaluation to a GPU worker, and a recovery path through an explicit resume API.
3. **Phase C — infra hardening**: WIF/attached service accounts, private connectivity,
   Spot fallback policy, production observability, and budget guardrails.

### External best-practice references

- [Spot VMs and managed instance groups](https://docs.cloud.google.com/compute/docs/instances/spot)
- [Cloud Storage / Compute data-transfer pricing](https://cloud.google.com/vpc/network-pricing)
- [Colocate storage and compute in the same zone/region](https://docs.cloud.google.com/architecture/migrate-across-regions/prepare-data-and-batch-workloads)
- [Avoid long-lived service account keys](https://docs.cloud.google.com/iam/docs/best-practices-for-managing-service-account-keys)
- [Use attached service accounts or Workload Identity Federation](https://docs.cloud.google.com/iam/docs/best-practices-service-accounts)

<a id="1-мотивация-и-экономика"></a>

## 1. Motivation and economics

### Problem

The PolicyOS scientist_policy_design pipeline includes two fundamentally different types of
workload:

| Type              | Characteristic                  | Duration            | Resource cost        |
| ----------------- | ------------------------------- | ------------------- | -------------------- |
| **LLM phase**     | Network-bound, CPU idle 95%+    | 5–30 min per cycle  | ~$0.001 (LLM tokens) |
| **Compute phase** | GPU-bound, JAX scan + gradients | 10–50 min per cycle | ~$0.15–0.25 (GPU/hr) |

With a monolithic deployment, the GPU instance sits idle during LLM calls, while LLM calls
block the pipeline while waiting for compute. Splitting the phases addresses both problems.

### Economics of one policy-design cycle

```text
Monolithic (GPU running the whole time):
  Wall time: ~60–90 min
  GPU cost:  ~$0.28/hr × 1.5 hr = $0.42
  LLM cost:  ~$0.001
  Total:     ~$0.42

Split (GPU used only for compute):
  LLM wall time: 15–30 min (low-cost server)
  GPU wall time: 25–50 min (Spot)
  GPU cost:  ~$0.28/hr × 0.7 hr = $0.20
  LLM cost:  ~$0.001
  Low-cost server: ~$0.004/hr × 0.5 hr = $0.002
  Total:     ~$0.20

Savings: ~48% on GPU cost for one cycle.
```

With an iterative loop (3–5 cycles), savings increase: LLM phases between compute runs
use no GPU capacity.

### Scenario with $300 in free GCP credits

| Mode                                | Cost/run  | Runs for $300 |
| ----------------------------------- | --------- | ------------- |
| Monolithic GPU (on-demand)          | $0.42     | ~714          |
| Monolithic GPU (Spot)               | $0.20     | ~1,500        |
| **Split (Spot GPU + low-cost LLM)** | **$0.15** | **~2,000**    |

<a id="2-compute-profile-по-стадиям-pipeline"></a>

## 2. Compute profile by pipeline stage

### Classification of all workflow nodes

The data came from an analysis of `src/polisyos/scientist/nodes/builtins/`.
Each node was classified by its actual calls: which ports it uses, whether it calls an
LLM, and whether it calls Foundry compile/execute.

#### LLM-heavy nodes (call the LLM API)

| Node                              | Purpose                                  | Calls                             | Typical time |
| --------------------------------- | ---------------------------------------- | --------------------------------- | ------------ |
| `PlanPolicyRequestNode`           | Frames the policy problem                | `LexPlanningService` (LLM)        | 10–30 sec    |
| `BuildSourcePackNode`             | Builds a source evidence pack            | LLM extraction                    | 30–120 sec   |
| `SourceVerifyNode`                | Verifies legal sources                   | LLM verification loop             | 60–300 sec   |
| `SourceGapReviewNode`             | Finds evidence gaps                      | LLM gap analysis (up to 2 cycles) | 60–180 sec   |
| `DraftPolicyOptionsNode`          | Generates policy options                 | `LexDraftingService` (LLM)        | 30–120 sec   |
| `RunPolicyTranslationNode`        | Translates policy into the target format | `PolicyTranslatorWorker` (LLM)    | 15–60 sec    |
| `RunHierarchicalPolicySearchNode` | Hierarchical search Level 3 (narrative)  | LLM narrative generation          | 30–120 sec   |

**Total**: 200–800 LLM calls per full cycle, ~1–2M tokens, $0.0007–0.0014.

#### Compute-Heavy Nodes (JAX/Foundry)

| Node                              | Purpose                         | Calls                                      | CPU time   | GPU time  |
| --------------------------------- | ------------------------------- | ------------------------------------------ | ---------- | --------- |
| `CompileFoundryNode`              | Trinity → ExecPlan              | `ctx.foundry.compile()`                    | 0.5–10 sec | —         |
| `RunSimulationNode`               | Execute plan → SimulationResult | `ctx.foundry.execute()`                    | 2–60 sec   | 0.1–2 sec |
| `RunCausalEvaluationNode`         | Causal query execution          | DoWhy/EconML (CPU)                         | 5–30 sec   | —         |
| `RunCausalEnsembleNode`           | ×10 SCM members                 | DoWhy/EconML (CPU)                         | 30–300 sec | —         |
| `RunTransportabilityNode`         | TR algorithm                    | Causal methods (CPU)                       | 5–30 sec   | —         |
| `PropagateUncertaintyNode`        | Uncertainty propagation         | JAX (GPU-accelerated)                      | 5–30 sec   | 0.5–3 sec |
| `RunDistributionalAnalysisNode`   | Distribution analysis           | NumPy/JAX                                  | 2–10 sec   | 0.5–2 sec |
| `RunHierarchicalPolicySearchNode` | Funnel Levels 0–5 (evaluation)  | Foundry compile + simulation per candidate | 5–180 sec  | 1–30 sec  |

**Total**: 60–640 sec CPU, 2–37 sec GPU. With a funnel-based policy search: ×50–200 evaluations.

#### Causal discovery (CPU-only; not GPU-accelerated)

| Node                                   | Purpose                         | Time              |
| -------------------------------------- | ------------------------------- | ----------------- |
| `BuildLiteraturePriorNode`             | Query Academic SKG              | 5–15 sec (DuckDB) |
| `ReconcileCausalGraphNode`             | Merge data + literature + hints | 10–60 sec (CPU)   |
| `CounterfactualIdentificationGateNode` | ID algorithm check              | 1–5 sec (CPU)     |

#### Data and pure logic (minimal load)

| Node                            | Purpose                    | Time                |
| ------------------------------- | -------------------------- | ------------------- |
| `BuildDataSnapshotNode`         | Load prebuilt snapshot ref | <1 sec (CAS lookup) |
| `BindFoundryInputsNode`         | Parameter binding          | <1 sec              |
| `DataPlaneGateNode`             | Validation                 | <0.1 sec            |
| `CompileCrossGraphEvidenceNode` | DuckDB queries             | 2–10 sec            |
| `RunGovernanceNode`             | 20 governance passes       | 1–5 sec             |
| `LegalCheckNode`                | Lex evaluation             | 1–3 sec             |
| `RunNormativeArbitrationNode`   | Trade-off analysis         | <1 sec              |
| `BuildDecisionPacketNode`       | Assembly                   | <1 sec              |
| `FormalizVerifiedPolicyNode`    | PolicyOptionSet → Trinity  | <1 sec              |

### Estimated compute budget (one policy_design cycle)

```text
LLM nodes:      4–15 min wall time, ~0% CPU, ~0% GPU
Causal nodes:   1–6 min wall time, ~100% CPU (8 cores), 0% GPU
Foundry nodes:  0.5–3 min wall time, ~50% CPU, ~100% GPU
Search funnel:  5–20 min wall time, ~80% CPU, ~80% GPU (batched evaluations)
DuckDB queries: 0.5–2 min wall time, ~30% CPU, 0% GPU
Governance:     0.2–1 min wall time, ~10% CPU, 0% GPU
─────────────────────────────────────────────────────────
Total:          ~12–47 min wall time
GPU active:     ~6–23 min (50–60% utilization in the monolithic setup)
```

<a id="3-целевая-архитектура"></a>

## 3. Target architecture

### Separation principle

Two classes of servers share a CAS (Content-Addressable Storage) through a GCS bucket:

```text
┌─────────────────────────────────────────────────────────┐
│                 GCS Bucket (shared CAS)                 │
│                                                         │
│  polisyos-cas/                                          │
│  ├── sha256/<ab>/<cd>/<hex>.blob                        │
│  ├── sha256/<ab>/<cd>/<hex>.manifest.json               │
│  └── knowledge/                                         │
│      ├── academic.duckdb    (~1.2 GB, read-only)        │
│      ├── datasets.duckdb    (~1.2 GB, read-only)        │
│      └── world.duckdb       (~100 MB-1 GB)              │
└────────────────┴─────────────────────────────┴──────────┘
                 │                             │
      ┌──────────▼──────────┐       ┌──────────▼──────────┐
      │   LLM Server        │       │   GPU Worker        │
      │   (always on)       │       │   (on demand)       │
      │                     │       │                     │
      │   CPX21/e2-std      │       │   g2-standard-8     │
      │   4 vCPU            │       │   8 vCPU + L4       │
      │   8 GB RAM          │       │   32 GB RAM         │
      │                     │       │                     │
      │   Roles:            │       │   Roles:            │
      │ • Orchestrator      │       │ • Foundry           │
      │ • LLM nodes         │       │ • Calibration       │
      │ • Runtime API       │       │ • Search eval       │
      │ • Dashboard         │       │ • Causal            │
      │ • CAS L1 cache      │       │ • CAS L1 cache      │
      └─────────────────────┘       └─────────────────────┘
```

### Data flow (one cycle)

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

### What remains unchanged

- **Ideally, Foundry/LLM node business logic needs no rewrite**, but orchestration,
  CAS wiring, and checkpoint/resume semantics still require code changes. The claim
  that PolicyOS can run "with no modifications" is too optimistic for the current branch.

- The CAS protocol is identical on both servers (one GCS bucket).
- Knowledge graphs are read-only `.duckdb` files copied to both servers.

<a id="4-рекомендации-по-железу"></a>

## 4. Hardware recommendations

### LLM server (always on, ~$4–8/month)

**Tasks**: Runtime API, LLM orchestration, dashboard, CAS caching.

**Load**: Minimal CPU; most waiting is for network I/O (LLM API calls).

**Recommendation**: Hetzner CPX21 or GCP e2-standard-2

| Parameter | CPX21 (Hetzner) | e2-standard-2 (GCP)                            |
| --------- | --------------- | ---------------------------------------------- |
| vCPU      | 3               | 2                                              |
| RAM       | 4 GB            | 8 GB                                           |
| Disk      | 80 GB SSD       | 50 GB pd-balanced                              |
| Price     | €4.15/month     | ~$48/month (on-demand) or $0 with free credits |
| Network   | 20 TB           | Standard Tier                                  |

**Why 4–8 GB RAM may be enough:**

- Runtime API (FastAPI + Uvicorn): ~300 MB
- DuckDB knowledge graphs (read-only, memory-mapped): ~500 MB working set
- CAS L1 cache: configurable, ~200 MB hot set
- Python + imports: ~400 MB
- **Total peak: ~1.5-2 GB**

LLM nodes do not load datasets into RAM: they send a prompt over HTTP, wait for a response,
and parse JSON. Their memory footprint is small.

**Disk**: Knowledge graphs (~3 GB) + CAS L1 cache (~5-10 GB) + OS = 20-30 GB. 80 GB SSD
with headroom.

### GPU worker (on demand, $0.20–0.28/hr Spot)

**Tasks**: Foundry compile/execute, calibration, policy-search evaluation, and causal methods.

**Load**: JAX scan + gradients (GPU), DoWhy/EconML (CPU), and DuckDB queries (CPU).

**Recommendation**: GCP g2-standard-8 (Spot/Preemptible)

| Parameter       | g2-standard-8                            |
| --------------- | ---------------------------------------- |
| vCPU            | 8 (AMD EPYC)                             |
| RAM             | 32 GB                                    |
| GPU             | NVIDIA L4 (24 GB VRAM, Ada Lovelace)     |
| Disk            | 200 GB pd-balanced                       |
| Spot price      | ~$0.25–0.34/hr                           |
| On-demand price | ~$0.84/hr                                |
| Region          | us-central1-a (lowest price in the note) |

**Why 32 GB RAM:**

- Python + JAX + XLA compilation cache: ~4-6 GB
- DuckDB knowledge graphs (memory-mapped): ~1-3 GB
- Foundry GlobalState (5K agents): ~0.2 MB (negligible)
- Calibration scan buffers (JAX): 2-4 GB peak
- Causal ensemble (10 SCM, DoWhy objects): ~1-2 GB
- CAS L1 cache: ~500 MB
- **Total peak: ~12–16 GB** (32 GB leaves headroom for spikes)

**Why L4 instead of T4:**

- L4 (Ada, 2023) vs. T4 (Turing, 2018): ~60% faster for FP32 compute.
- VRAM: 24 GB vs. 16 GB, leaving headroom for more agents.
- On Spot, the price difference is small (~$0.03/hr).

**Why 8 vCPUs:**

- Causal ensembles (10 SCMs) parallelize well across 8 cores.
- 16 vCPUs may improve causal-pipeline speed by 30–40%, at 55% higher cost.
- Diminishing returns: DoWhy does not scale linearly.

### Alternative GPU-worker configurations

| Option             | Specs                | Spot $/hr | Intended workload               |
| ------------------ | -------------------- | --------- | ------------------------------- |
| **g2-standard-4**  | 4 vCPU, 16 GB, L4    | ~$0.20    | Tight budget, <5K agents        |
| **g2-standard-8**  | 8 vCPU, 32 GB, L4    | ~$0.28    | **Recommendation**              |
| **g2-standard-16** | 16 vCPU, 64 GB, L4   | ~$0.45    | Larger causal graphs (20+ vars) |
| **a2-highgpu-1g**  | 12 vCPU, 85 GB, A100 | ~$1.10    | >20K agents, research-grade     |

### Sizing for typical workloads

| Workload                       | Agents  | Vars  | GPU worker     | Estimated compute time |
| ------------------------------ | ------- | ----- | -------------- | ---------------------- |
| Regional SME policy            | 1K–5K   | 5–10  | g2-standard-8  | 25–50 min              |
| National tax reform            | 10K–20K | 10–15 | g2-standard-8  | 40–90 min              |
| Interregional transportability | 5K–10K  | 15–20 | g2-standard-16 | 60–120 min             |
| Research (ABM bilevel)         | 20K+    | 10+   | a2-highgpu-1g  | 2–4 hours              |

<a id="5-cas-как-связующий-слой"></a>

## 5. CAS as the coordination layer

### Why CAS

CAS (Content-Addressable Storage) is the only shared state between servers. All artifacts
(Trinity bundles, exec plans, simulation results, checkpoints, and knowledge bundles) are stored
by SHA-256 hash. This provides:

- **Immutability**: a write cannot be overwritten (same hash = same content)
- **Idempotency**: repeating a write is safe
- **Distribution**: any machine that can access the bucket can see all artifacts
- **Lineage**: each artifact records its inputs through ArtifactManifest.inputs

### CAS configuration for split mode

Target state: both machines use the `cached_gcs` backend — a local L1 cache plus
GCS source of truth.

**Important:** a backend factory already exists in `src/polisyos/core/artifacts/backends/config.py`,
but the Runtime API and Scientist workflow builder partially bypass it in the current code and
instantiate `FileSystemCAS` directly. This must be fixed before a real split rollout.

**Environment variables (shared by both servers):**

```bash
# CAS backend
export POLISYOS_CAS_BACKEND=cached_gcs
export POLISYOS_CAS_BUCKET=polisyos-cas-prod        # GCS bucket name
export POLISYOS_CAS_PREFIX=polisyos-cas              # Prefix in bucket

# L1 cache (a different local path on each server)
export POLISYOS_CAS_LOCAL_CACHE_DIR=/data/cas_cache  # GPU worker
# or
export POLISYOS_CAS_LOCAL_CACHE_DIR=~/.polisyos/cas/_cache  # LLM server
```

### GCS layout

```text
gs://polisyos-cas-prod/
  polisyos-cas/
    sha256/
      ab/cd/abcdef...789.blob              # Artifact content
      ab/cd/abcdef...789.manifest.json     # Artifact metadata
      ab/cd/abcdef...789.sig               # Ed25519 signature (optional)
```

### CachingArtifactStore behavior

Implemented in `src/polisyos/core/artifacts/backends/caching_store.py`:

```text
Write path:
  1. put_bytes(blob) → compute sha256
  2. Write to local FileSystemCAS
  3. Write to remote `GCSArtifactStore` (currently, this follows the local write sequentially)
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

### Typical artifact sizes

| Artifact kind              | Size         | Notes                           |
| -------------------------- | ------------ | ------------------------------- |
| `ir.trinity_bundle`        | 5-50 KB      | JSON, compact                   |
| `foundry.exec_plan`        | 10-100 KB    | Compiled plan                   |
| `foundry.program_graph`    | 20-200 KB    | DAG nodes/edges                 |
| foundry.simulation_result  | 50 KB–5 MB   | Depends on n_agents and n_steps |
| `foundry.state_delta`      | 100 KB-10 MB | Per-step patches                |
| `scientist.checkpoint`     | 50-500 KB    | Serialized ExperimentState      |
| `fabric.data_snapshot`     | 1-100 MB     | Data references + metadata      |
| `governance.report`        | 10-50 KB     | Pass results                    |
| `scholar.knowledge_bundle` | 100 KB-5 MB  | Literature evidence             |

**Total per run**: ~10–50 MB of artifacts.

**Network-cost caveat:** GCS/Compute traffic is free only when compute and the bucket
are in the same Google Cloud region and access is VM-to-Google-service traffic inside
GCP. If the LLM server stays on Hetzner, reading artifacts from GCS there incurs
Internet egress and additional latency. To minimize cost and latency, keep storage and compute
in the same region/zone; if Hetzner is needed for the UI/API, minimize the frequency of
CAS pulls from the Hetzner side.

### `ArtifactRef` — the exchange key between servers

```python
ArtifactRef(
    artifact_id="sha256:a1b2c3d4e5f6...",  # Content hash
    kind="foundry.simulation_result",       # Semantic type
    media_type="application/json"           # Content type
)
```

The LLM server generates an artifact → writes it to CAS → passes the `artifact_id` string →
the GPU worker reads it from CAS by `artifact_id`. There is no other shared state.

<a id="6-knowledge-graphs-сборка-и-раздача"></a>

## 6. Knowledge graphs: build and distribution

### Three knowledge graphs

| Graph                | DuckDB file       | Approximate size | Build pipeline                           |
| -------------------- | ----------------- | ---------------- | ---------------------------------------- |
| **Academic SKG**     | `academic.duckdb` | ~1.2 GB          | `academic/batch/` (16 stages, LLM-heavy) |
| **Datasets Catalog** | `datasets.duckdb` | ~1.2 GB          | `datasets/batch/` (14 stages)            |
| **World Store**      | `world.duckdb`    | ~100 MB-1 GB     | `fabric/world/materialize/`              |

### Read-only at runtime

All runtime DuckDB connections are opened with `read_only=True`:

```python
# src/polisyos/data_forge/domains/academic/knowledge/store.py
self._con = duckdb.connect(str(db_path), read_only=True)

# src/polisyos/data_forge/domains/catalog/knowledge/store.py
self._con = duckdb.connect(str(db_path), read_only=True)
```

This means:

- Knowledge graphs are **not modified** during a run.
- Concurrent access is safe (no write locks).
- The files can be copied to any number of servers.

### Strategy: build once, distribute

```text
1. Build phase (run infrequently, on the LLM server or a separate machine):
   ┌────────────────────────────────┐
   │  python -m polisyos.data_forge.domains.academic.batch.pipeline  │
   │  python -m polisyos.data_forge.domains.catalog.batch.pipeline  │
   │  → academic.duckdb, datasets.duckdb          │
   └──────────────────┬─────────────────────────────┘
                      │
2. Upload to GCS:     ▼
   gsutil cp academic.duckdb gs://polisyos-cas-prod/knowledge/
   gsutil cp datasets.duckdb gs://polisyos-cas-prod/knowledge/

3. Download on workers (at startup or via cron):
   gsutil cp gs://polisyos-cas-prod/knowledge/*.duckdb /data/knowledge/
```

### Path configuration

**Target-state environment contract:** the names below are convenient for split deployment, but
they are not read centrally by the current code. `ScholarKnowledgeGraph`, `SKGQuery`,
`DatasetCatalogStore`, and related components mostly receive `db_path/index_dir`
through constructors. To support environment-driven deployment, this contract must be
implemented in the ports/adapters.

```bash
# Knowledge-graph locations (both machines)
export POLISYOS_ACADEMIC_DB_PATH=/data/knowledge/academic.duckdb
export POLISYOS_DATASETS_DB_PATH=/data/knowledge/datasets.duckdb
export POLISYOS_WORLD_DB_PATH=/data/knowledge/world.duckdb

# HNSW index directories (for semantic search)
export POLISYOS_ACADEMIC_INDEX_DIR=/data/knowledge/academic_indices/
export POLISYOS_DATASETS_INDEX_DIR=/data/knowledge/datasets_indices/
```

### RAM impact of runtime queries

DuckDB uses memory-mapped I/O. Actual consumption depends on the queries:

| Query type                         | Estimated RAM    | Frequency             |
| ---------------------------------- | ---------------- | --------------------- |
| Variable canonicalization          | 50-100 MB        | Per evidence need     |
| Edge support lookup                | 100-300 MB       | Per causal edge       |
| Parameter candidates               | 50-200 MB        | Per Trinity parameter |
| Transport scoring                  | 100-300 MB       | Per context pair      |
| Cross-graph compilation (combined) | 500 MB–2 GB peak | Once per run          |

On the LLM server (8 GB), cross-graph compilation should run without issues.
On the GPU worker (32 GB), it should have substantial headroom.

### Updating knowledge graphs

Knowledge graphs are updated **separately** from the compute pipeline:

```text
Frequency:
  Academic SKG — weekly/monthly (new publications)
  Datasets Catalog — weekly (new datasets)
  World Store — per ingestion (facts from Fabric connectors)

Process:
  1. Run the batch pipeline on the LLM server (or a separate build machine)
  2. Upload to GCS
  3. The GPU worker downloads the new version on its next startup
  4. Version by timestamp in the filename:
     academic_2026w14.duckdb, academic_2026w15.duckdb
```

<a id="7-протокол-оркестрации"></a>

## 7. Orchestration protocol

### Option A: REST API orchestration (recommended in the note)

The LLM server starts the full Runtime API (uvicorn). The GPU worker runs as a
headless compute backend invoked through the gcloud API.

```python
# `orchestrator.py` on the LLM server (pseudo-code)

async def run_policy_design_split(trinity_ref: str, data_source_ref: str):
    """Iterative LLM/Compute split loop."""

    cas = build_artifact_store(ArtifactStoreConfig.from_env())

    for cycle in range(max_cycles):
        # ═══════ LLM PHASE (local) ═══════
        # Run LLM-heavy nodes directly through the `Scientist API`
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

### Option B: Checkpoint-based split

Uses built-in checkpoint/resume, but **not as a current zero-code path**; it is a
foundation for adding an intentional pause/resume flow:

```text
1. LLM server: start the `scientist_policy_design` workflow
   → Checkpoint policy: "strict"
   → Workflow executes LLM nodes
   → Reaches a split marker before the compute segment → checkpoint → PAUSE

2. GPU Worker: Resume from checkpoint
   → Load checkpoint from CAS
   → Execute compute-heavy nodes
   → Checkpoint at the split marker after the compute segment → PAUSE

3. LLM Server: Resume from checkpoint
   → Load results
   → LLM analysis → refined candidates
   → If converged → finalize
   → If not → checkpoint → go to step 2
```

**Advantage:** checkpoint artifacts and the node cache can be reused.

**Current implementation limitations:**

- The executor cannot intentionally stop at a split-marker boundary.
- Resume relies on the node cache, not on `completed_nodes` as a hard-skip barrier.
- `checkpoint_head.json` and the run lock are local to `run_dir`, not in shared CAS.
- The workflow fingerprint checks the DAG shape, not the environment hash, so
  matching Python and dependency versions still have to be ensured operationally.

### Option C: Control Plane API (most native)

The Runtime API already supports starting a **full** workflow run with prebuilt artifact refs.
As a target state, this is a good path for split orchestration, but the example below requires
API/engine changes so the GPU worker can execute only the compute segment.

```bash
# On the GPU worker — start the headless `Runtime API`
uvicorn 'polisyos.runtime.http.app:create_runtime_api_app' \
  --factory --host 0.0.0.0 --port 8000

# From the LLM server — `POST` a request to the GPU worker
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

# or poll
curl http://${GPU_WORKER_IP}:8000/api/v1/control/jobs/${JOB_ID}
# → {"state": "running"} ... {"state": "completed"}
```

Retrieve results:

```bash
curl http://${GPU_WORKER_IP}:8000/api/v1/runs/${RUN_ID}
# → {"root_artifacts": ["sha256:result1...", "sha256:result2..."]}
```

`WorkflowRunRequest` supports the following prebuilt artifact refs:

| Field                           | Purpose                                                                          |
| ------------------------------- | -------------------------------------------------------------------------------- |
| `data_source.data_snapshot_ref` | Pre-built data snapshot                                                          |
| `trinity_bundle_ref`            | Pre-compiled Trinity bundle                                                      |
| `knowledge_bundle_ref`          | Pre-built knowledge evidence                                                     |
| `norm_pack_ref`                 | Pre-assembled legal norm pack                                                    |
| `calibration_report_ref`        | Previous calibration results                                                     |
| `params` (dict)                 | Arbitrary workflow parameters, limited to those actually read by Scientist nodes |

### Recommendation

**Practical starting point:** begin with **Option A** — an explicit orchestrator on the LLM server +
a separate compute-only entrypoint/workflow on the GPU worker after the P0 fixes.

**Target state:** **Option C** is the most native option once the Control Plane has an
official partial-workflow/resume contract. The GPU worker could then run the standard
Runtime API, the LLM server could POST artifact refs, and SSE streaming could remain
the unified monitoring surface.

**Option B** is not recommended as the primary production path while the checkpoint head/run lock
remain outside a shared durable layer and explicit pause markers are unavailable.

<a id="8-конфигурация-окружений"></a>

## 8. Environment configuration

### LLM server — environment file

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

# ═══════ Auth (simplified for dev/research) ═══════
export POLISYOS_AUTHN_ENABLED=false
export POLISYOS_AUTHZ_MODE=off

# ═══════ Observability ═══════
export POLISYOS_OTEL_ENABLED=true
export POLISYOS_OTEL_CONSOLE_EXPORT=true
```

### GPU worker — environment file

```bash
# ═══════ Core ═══════
export POLISYOS_ENV=production
export POLISYOS_EXECUTION_PROFILE=research

# ═══════ CAS (same bucket, different local cache) ═══════
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
# Verify that JAX detects the GPU
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

<a id="9-lifecycle-gpu-инстанса"></a>

## 9. GPU instance lifecycle

### Startup script (GPU Worker)

**Best practice:** on GCE, do not copy a JSON service-account key into the image.
Attach a dedicated least-privilege service account to the VM/MIG and grant it access
to the required bucket. gsutil/the Google SDK will automatically obtain short-lived credentials
through the metadata server.

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
# Run by cron every 5 minutes
# Shut down if there are no active runs

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

**Preemption best practice:** for Spot VMs, add a shutdown script that uses the 30-second
best-effort grace period to record the final heartbeat/job status; do not rely solely on
cron-based idle shutdown. With a MIG, also note that the group may not recreate a Spot GPU VM
immediately when capacity is unavailable in the zone.

### Manage from the LLM server

```bash
# Start the GPU worker
gcloud compute instances start gpu-worker --zone=us-central1-a

# Get the IP address
GPU_IP=$(gcloud compute instances describe gpu-worker \
  --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

# Wait until ready
until curl -sf http://${GPU_IP}:8000/api/v1/health; do sleep 5; done

# Start a compute run
curl -X POST http://${GPU_IP}:8000/api/v1/control/runs \
  -H "Content-Type: application/json" \
  -d @compute_request.json

# Monitor through SSE
curl -N http://${GPU_IP}:8000/api/v1/runs/${RUN_ID}/live

# Stop (or let auto-shutdown run after 10 minutes idle)
gcloud compute instances stop gpu-worker --zone=us-central1-a
```

### GPU instance lifecycle timing

```text
gcloud start         → ~30–60 sec (Spot instance provisioning)
OS boot + CUDA init  → ~30–60 sec
KG sync from GCS     → ~30–60 sec (3 GB on first run; then rsync <5 sec)
Uvicorn startup      → ~10–15 sec (JAX XLA initialization + imports)
Health check ready   → ~5 sec
────────────────────────────────────
Total cold start:      ~2–3 min
Total warm start:      ~1–1.5 min (KG cached; no download)
```

<a id="10-fault-tolerance-и-checkpoint"></a>

## 10. Fault tolerance and checkpointing

### Checkpointing during Spot preemption

GCP Spot instances may be preempted with 30 seconds’ notice.
PolicyOS Scientist records a checkpoint after **each** successful node:

```python
# src/polisyos/scientist/orchestration/engine/checkpoint.py
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

**Worst case during preemption**: one node execution is lost (the last one, before its checkpoint).
When the workflow restarts, it resumes from the latest checkpoint.

### Recovery flow

```text
1. Spot preemption → GPU Worker killed
2. LLM Server detects: SSE stream closes / poll returns error
3. LLM Server restarts GPU Worker:
   gcloud compute instances start gpu-worker

4. GPU Worker boots, syncs KG, starts Runtime API

5. LLM Server resumes run:
   Target state: a separate resume endpoint or workflow_run job with an explicit resume contract
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

### What checkpointing does not save

- **JAX XLA compilation cache** — JIT recompiles after restart (30–60 sec).
- **DuckDB connection state** — reopened on resume.
- **In-flight HTTP requests** — LLM calls are not resumable (retry from scratch).

<a id="11-мониторинг-и-observability"></a>

## 11. Monitoring and observability

### SSE streaming from the LLM server

The LLM server, acting as the orchestrator, monitors the GPU worker through SSE:

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

Both servers export spans. For a unified view, configure a shared OTLP collector:

```bash
# On both servers
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
export OTEL_SERVICE_NAME=polisyos-llm-server  # or polisyos-gpu-worker
export POLISYOS_OTEL_ENABLED=true
```

### Key metrics

| Metric                         | Source     | What it shows                  |
| ------------------------------ | ---------- | ------------------------------ |
| node_duration_seconds          | Both       | Duration of each workflow node |
| `artifact_io_bytes`            | Both       | CAS read/write volume          |
| `artifact_io_duration_seconds` | Both       | CAS latency (L1 vs GCS)        |
| `gpu_utilization`              | GPU Worker | nvidia-smi GPU %               |
| `jax_compilation_seconds`      | GPU Worker | XLA JIT overhead               |
| `llm_request_duration`         | LLM Server | LLM API latency                |
| `llm_tokens_total`             | LLM Server | Token consumption              |
| `run_total_duration`           | Both       | Full run wall-time             |

### Health checks

```bash
# LLM Server health
curl http://llm-server:8000/api/v1/health
# → {"status": "healthy", "version": "...", "uptime_seconds": ...}

# GPU worker health (when running)
curl http://gpu-worker:8000/api/v1/health
# → {"status": "healthy", ...}

# GPU Worker GPU health
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv
```

<a id="12-масштабирование"></a>

## 12. Scaling

### Vertical scaling (single user, larger workloads)

| Scenario                    | Action                                                    |
| --------------------------- | --------------------------------------------------------- |
| More agents (>10K)          | Upgrade GPU worker to g2-standard-16 (more RAM for JAX)   |
| More causal variables (>20) | Upgrade GPU worker to more vCPUs (discovery is quadratic) |
| Faster iteration            | Upgrade GPU Worker: a2-highgpu-1g (A100 GPU)              |
| More knowledge data         | Upgrade LLM server to more RAM for DuckDB                 |

### Horizontal scaling (multiple concurrent users/tasks)

```text
Topology A: Shared LLM Server + GPU Pool

  LLM Server (always-on)
    ├── User A request → GPU Worker 1 (spot)
    ├── User B request → GPU Worker 2 (spot)
    └── User C request → GPU Worker 1 (reuse after A completes)

  CAS: GCS bucket (shared, concurrent-safe)
  KG: Each GPU Worker downloads on start (immutable)
```

**Spot/MIG caveat:** a MIG with Spot VMs tries to maintain the target size, but scale-up/autoscaling
may temporarily fail if GPU capacity is unavailable in the zone. For a production queue,
add retries with jitter, multi-zone fallback, and an explicit
fallback to an on-demand pool for priority jobs.

```text
Topology B: Per-user LLM + Shared GPU Pool

  LLM Server A (user A) ──┐
  LLM Server B (user B) ──┤→ GPU Worker Pool (managed instance group)
  LLM Server C (user C) ──┘
                              ↕
                           GCS CAS (shared)
```

### Managed Instance Group (GCP)

To scale GPU workers automatically:

```bash
# Create an instance template
gcloud compute instance-templates create gpu-worker-tpl \
  --machine-type=g2-standard-8 \
  --accelerator=type=nvidia-l4,count=1 \
  --boot-disk-size=200GB \
  --metadata-from-file=startup-script=start-worker.sh \
  --preemptible

# Create a managed instance group (min 0, max 4)
gcloud compute instance-groups managed create gpu-pool \
  --template=gpu-worker-tpl \
  --size=0 \
  --zone=us-central1-a

# Scale up before the compute phase
gcloud compute instance-groups managed resize gpu-pool --size=1

# Scale down after completion
gcloud compute instance-groups managed resize gpu-pool --size=0
```

<a id="13-стоимостная-модель"></a>

## 13. Cost model

### Cost of one complete policy-design cycle

**Assumptions:**

- Regional SME policy, 3K agents, 8 variables
- 3 iterations of the LLM/compute loop
- Knowledge graphs have already been built

```text
Per iteration:
  LLM phase:     ~400 calls × 2K tokens = 800K tokens × $0.0007/1M = $0.0006
  GPU phase:     ~35 min × $0.28/hr = $0.16
  LLM server:    ~20 min × $0.006/hr = $0.002
  GCS egress:    ~50 MB × $0 (same region) = $0

3 iterations:
  LLM total:     $0.002
  GPU total:     $0.48
  LLM Server:    $0.006
  ─────────────────────
  Grand total:   ~$0.49

Rounded:         ~$0.50 per policy design
```

**Cost caveat:** the GCS egress = $0 line is valid only for GPU worker ↔ GCS traffic within one
GCP region. If the LLM server runs on Hetzner and regularly reads artifacts from
GCS, Internet egress is not zero and latency is higher. For clean unit economics,
keep the LLM/orchestrator near the bucket in GCP, or use Hetzner only for a thin
UI/API layer without frequent CAS fetches.

### Monthly cost (active research)

| Component                       | Usage                 | Cost/month        |
| ------------------------------- | --------------------- | ----------------- |
| LLM Server (CPX21, 24/7)        | Always on             | €4.15 (~$4.50)    |
| GPU worker (Spot, ~40 hr/month) | 80 runs × 30 min      | ~$11.20           |
| LLM API (~32M tokens/month)     | 80 runs × 400K tokens | ~$0.02            |
| GCS storage (~10 GB)            | CAS + KGs             | ~$0.20            |
| GCS operations (~100K)          | CAS reads/writes      | ~$0.50            |
| **Total**                       |                       | **~$16.50/month** |

### Budget allocation for $300 in GCP credits

```text
GCS storage + operations:     ~$5     (12 months)
GPU spot compute:             ~$280   (1000 GPU-hours = ~1700 runs)
Reserved for on-demand:       ~$15    (emergency, ~18 GPU-hours)
────────────────────────────────────
$300 total

At 80 runs/month, this covers ~21 months of GPU compute.
LLM server on Hetzner (outside GCP credits): €4.15/month.
```

<a id="14-checklist-развёртывания"></a>

## 14. Deployment checklist

### Phase 1: GCS Setup

```text
[ ] Create GCS bucket: polisyos-cas-prod (region: us-central1)
[ ] Set a lifecycle policy: delete incomplete uploads after >7 days
[ ] Create separate single-purpose service accounts:
    [ ] polisyos-gpu-worker@project.iam.gserviceaccount.com
    [ ] polisyos-llm-orchestrator@project.iam.gserviceaccount.com
[ ] Grant only the required bucket-level roles; avoid project-wide Editor
[ ] Use an attached service account without a JSON key for the GCE worker
[ ] Configure Workload Identity Federation for the Hetzner LLM server; use a JSON key only as a temporary fallback
```

### Phase 2: LLM Server (Hetzner CPX21)

```text
[ ] Create a CPX21 server (Falkenstein, €4.15/month)
[ ] Install Python 3.14, pip, and git
[ ] git clone + pip install -e ".[all]"
[ ] Set environment variables (section 8)
[ ] Configure GCS access through Workload Identity Federation
[ ] If WIF is not yet available, temporarily use a JSON key with strict file permissions and a rotation/removal plan
[ ] Build the knowledge graphs or download prebuilt copies
[ ] gsutil cp KGs → GCS
[ ] Start the Runtime API: uvicorn ... --factory --host 0.0.0.0
[ ] Check: curl http://localhost:8000/api/v1/health
[ ] Configure a systemd service for automatic restart
```

### Phase 3: GPU Worker Template (GCP)

```text
[ ] Create a boot-disk image:
    [ ] Base: Ubuntu 22.04 LTS
    [ ] Install the NVIDIA driver and CUDA 12.x
    [ ] Install Python 3.14
    [ ] pip install jaxlib[cuda12] jax
    [ ] git clone + pip install -e ".[all]"
    [ ] Copy the environment file and startup script
    [ ] Do not include a GCS JSON key in the image; use an attached service account
    [ ] Snapshot → custom image
[ ] Create an instance template:
    [ ] Machine type: g2-standard-8
    [ ] Boot disk: custom image, 200 GB pd-balanced
    [ ] Provisioning: Spot
    [ ] Attached service account: polisyos-gpu-worker@...
    [ ] Startup script: /opt/polisyos/start-worker.sh
    [ ] Network: allow TCP 8000 (firewall rule)
[ ] Test: start an instance, check JAX GPU, and check the Runtime API
[ ] Configure an auto-shutdown script (cron)
[ ] Add a shutdown script for preemption notice and graceful status flush
```

### Phase 4: Integration Test

```text
[ ] From the LLM server:
    [ ] gcloud compute instances start gpu-worker
    [ ] Wait for the health check
    [ ] POST /api/v1/control/runs (test Trinity)
    [ ] Monitor through SSE
    [ ] Check results in CAS
    [ ] gcloud compute instances stop gpu-worker
[ ] Check checkpoint/resume:
    [ ] Start a run
    [ ] Stop the GPU worker mid-run
    [ ] Restart the GPU worker
    [ ] Target-state resume contract: continue the run from an explicit checkpoint_ref or shared checkpoint head
[ ] Check CAS consistency:
    [ ] LLM server writes an artifact
    [ ] GPU worker reads the same artifact (by sha256 ref)
[ ] Check that runtime/Scientist actually use cached_gcs rather than local FileSystemCAS
```

### Phase 5: Production Hardening

```text
[ ] TLS: nginx reverse proxy on the GPU worker (or GCP load balancer)
[ ] Firewall: limit TCP 8000 on the GPU worker to the LLM server/internal VPC
[ ] If possible, remove the GPU worker's public IP; use internal IP/VPN/IAP tunnel
[ ] Secrets: move API keys to GCP Secret Manager
[ ] Do not use service-account JSON keys as the primary Secret Manager path; prefer attached service accounts/WIF
[ ] Monitoring: alert on GPU idle time >15 min
[ ] Alerting: Spot capacity failures, repeated preemptions, CAS remote-write failures, checkpoint resume failures
[ ] Cost alerts: GCP budget alerts at $50, $100, and $200
[ ] Backup: enable GCS bucket versioning for CAS
```

---

## Related documents

| Document              | Path                                                  |
| --------------------- | ----------------------------------------------------- |
| Runtime Deployment    | `docs/how-to/deploy-runtime.md`                       |
| Architecture Overview | `docs/explanation/architecture.md`                    |
| Control Plane How-to  | `docs/how-to/use-control-plane.md`                    |
| Security Model        | `docs/explanation/security-model.md`                  |
| SLO & Error Budget    | `docs/reference/operations/slo-error-budget.md`       |
| Observability         | `docs/reference/operations/observability-topology.md` |
