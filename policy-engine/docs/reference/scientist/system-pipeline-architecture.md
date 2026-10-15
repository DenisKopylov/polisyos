# PolicyOS Scientist — Pipeline Architecture

Owner: `@scientist-owners`
Source of truth: `src/polisyos/scientist/**`, `src/polisyos/foundry/**`, `src/polisyos/fabric/connectors/**`, `src/polisyos/ir/analytics/**`, and `tests/unit/scientist/**`
Source pin: `codex/docs-refresh-e02-20261014` at `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; diagram content remains the dated 2026-03-21 snapshot.
Evidence level: historical diagram was not revalidated; current path/status handoff to `current-workflows.md` was inspected at this source pin; no tests were executed for this docs update.

> Date: 2026-03-21
> Status: dated architecture snapshot as of 2026-03-21; do not use it as the current path map or as evidence of end-to-end readiness

See the [Scientist index](index.md) for the current map of repository paths.
Observed workflows, evidence handshakes, and missing capability
links are documented in [Current Scientist Workflows and Evidence Handoffs](current-workflows.md).
The full-cycle diagram below describes an architectural model; it is not
evidence that the system works end to end. Node counts and paths in
this snapshot refer to the date shown above and have not been remeasured at the current
source pin.

---

## Contents

<!-- markdownlint-disable MD051 -->
<!-- The attr_list heading IDs below are verified by rendered MkDocs link QA. -->

1. [System overview](#system-overview)
2. [Three workflows and automatic selection](#2-три-workflow-и-автоматическии-выбор)
3. [Knowledge Layer — three knowledge graphs](#3-knowledge-layer-три-графа-знании)
4. [scientist_default — standard workflow](#4-scientist_default-стандартныи-workflow)
5. [scientist_causal_full — full causal analysis](#5-scientist_causal_full-полныи-каузальныи-анализ)
6. [scientist_policy_verified — verified policy](#6-scientist_policy_verified-верифицированная-политика)
7. [Foundry and Data Plane](#foundry-data-plane)
8. [IR Analytics — intermediate representations](#8-ir-analytics-промежуточные-представления)
9. [Checkpoint and recovery](#checkpoint-recovery)
10. [Node-by-node reference](#node-details)
<!-- markdownlint-enable MD051 -->

---

## 1. System overview { #system-overview }

PolicyOS Scientist is a DAG-based workflow engine for policy decision analysis.
The system accepts a policy question or a TrinityBundle and runs the full cycle:

```text
Policy Question / TrinityBundle
    → Knowledge Retrieval (Legal + Academic + Datasets)
    → Causal Identification (Pearl-Bareinboim)
    → Simulation (Foundry)
    → Governance & Legal Check
    → Decision Packet
```

### Key components

| Component                | Path                                                           | Purpose                                                             |
| ------------------------ | -------------------------------------------------------------- | ------------------------------------------------------------------- |
| **Scientist Workflows**  | `scientist/workflows/`                                         | Define and run workflow DAGs                                        |
| **Node Builtins**        | `scientist/nodes/builtins/`                                    | 35 built-in pipeline nodes                                          |
| **Engine**               | `scientist/engine/`                                            | Executor, checkpoint, registry, state                               |
| **Knowledge Layers**     | `academic/knowledge/`, `datasets/knowledge/`, `lex/knowledge/` | Three knowledge graphs                                              |
| **Cross-Graph Compiler** | `scientist/cross_graph/`                                       | Combines evidence from the three graphs                             |
| **Foundry**              | `foundry/`                                                     | Causal engine, data plane, and methods                              |
| **IR Analytics**         | `ir/analytics/`                                                | Intermediate representations (estimands, evidence bundles, reports) |
| **Fabric**               | `fabric/connectors/`                                           | Bridge to external data (UNPD, WVS, and others)                     |

### Central state model: ExperimentState

```python
class ExperimentState(BaseModel):
    run_id: str
    inputs: dict[str, ArtifactRef]          # trinity_bundle_ref, data_snapshot_ref, ...
    artifacts_index: dict[str, ArtifactRef]  # simulation_result_ref, causal_report_ref, ...
    reports_index: dict[str, ArtifactRef]    # governance_report_ref, legal_report_ref, ...
    params: dict[str, JsonValue]             # all runtime parameters
    budgets: dict[str, Decimal]
    execution_profile: str                   # "fast" | "research" | "governed" | "production" | "policy_verified_async"
    # + policy_verified fields: policy_request_ref, legal_candidate_pack_ref, ...
```

Each node reads from and writes to `ExperimentState`. All artifacts are immutable and content-addressed (CAS).

---

<a id="2-три-workflow-и-автоматическии-выбор"></a>

## 2. Three workflows and automatic selection

### Workflow IDs

| ID                          | File                           | Nodes | Purpose                                            |
| --------------------------- | ------------------------------ | ----- | -------------------------------------------------- |
| `scientist_default`         | `workflows/default.py`         | 21    | Standard analysis: compile → simulate → governance |
| `scientist_causal_full`     | `workflows/causal_full.py`     | 25    | + literature priors, transport, causal ensemble    |
| `scientist_policy_verified` | `workflows/policy_verified.py` | 25    | + legal source verification, policy drafting       |

### Automatic selection logic (`selection.py`)

```text
1. Explicit `workflow_id == "scientist_policy_verified"` → `POLICY_VERIFIED`
2. _should_use_policy_verified(state):

   - `policy_answer_mode == "verified_async"` → yes
   - `execution_profile == "policy_verified_async"` → yes
   - No `trinity_bundle`, but `policy_question` or `research_intent` is present → yes
3. execution_profile in {"research", "governed", "production"} → CAUSAL_FULL
4. Explicit `workflow_id == "scientist_causal_full"` → `CAUSAL_FULL`
5. _should_auto_escalate_to_causal_full(state):

   - `transport_required` → yes
   - `source_context ≠ target_context` → yes
   - `external_evidence` or `cross_graph_evidence` → yes
   - `knowledge_bundle_ref` is present → yes
6. Otherwise → `DEFAULT`
```

---

<a id="3-knowledge-layer-три-графа-знании"></a>

## 3. Knowledge Layer — three knowledge graphs

### 3.1 Academic SKG (Scholar Knowledge Graph)

**Storage:** DuckDB (`ac_skg_*` tables)

| Table                          | Contents                                     |
| ------------------------------ | -------------------------------------------- |
| `ac_skg_articles`              | OpenAlex articles and their metadata         |
| `ac_skg_variables`             | Canonical variables with approval status     |
| `ac_skg_edges`                 | Causal edges (`src` → `dst`) with confidence |
| `ac_skg_edge_evidence`         | Evidence per edge per article                |
| `ac_skg_parameters`            | Parameter estimates from the literature      |
| `ac_skg_simulation_parameters` | Refined estimates for calibration            |
| `ac_skg_transport_scores`      | Precomputed transportability penalties       |

**Query interface (`SKGQuery`):**

- `query_prior(variable)` → aggregated distribution (weighted mean/std)
- `query_claims(cause, effect)` → causal links with trust scoring
- `query_parameters(param, target_context)` → candidates with context distance

**Confidence aggregation:** evidence-weighted noisy-OR with a 20-year half-life decay.

### 3.2 Datasets Catalog

**Storage:** DuckDB (`ds_*` tables) plus an HNSW vector index

| Table                    | Contents                                     |
| ------------------------ | -------------------------------------------- |
| `ds_dataset_catalog`     | DCAT-aligned dataset metadata                |
| `ds_distributions`       | Loadable resources with connectors           |
| `ds_variable_alignments` | `raw_var` → `canonical_var` mappings         |
| `ds_metric_bindings`     | Deterministic `metric` → `dataset` bindings  |
| `ds_observations`        | Time-series values (country, year, variable) |

**Search:** hybrid (vector HNSW plus full text), boosted by freshness, metrics, and country hints.

**Registry:** computes P\*(Z) for transport using temporal penalties, interpolation, and proxy penalties.

### 3.3 Lex (Legal) Knowledge Graph

**Storage:** DuckDB (`lex_*` tables) plus an HNSW vector index

| Table                 | Contents                                                |
| --------------------- | ------------------------------------------------------- |
| `lex_facts`           | Legal facts with confidence tiers                       |
| `lex_fact_grounded`   | Facts with source citations                             |
| `lex_normative_facts` | Canonical obligations and prohibitions                  |
| `lex_provisions`      | Hierarchical document structure (Article → Part → Item) |

**Filters:** `trust_tier` (`search_candidate` → `grounded_fact` → `normative_fact`), jurisdiction, domain, and `as_of`.

**Constraints bridge:** maps legal facts to DAG changes (HARD blocks transport; SOFT adds a penalty).

### How the three graphs are combined

```text
CrossGraphEvidenceCompiler.compile(TrinityBundle)
  → extract_evidence_needs()          # metrics, parameters, constraints, mechanisms, and edges
  → _assess_legal_need()              # status: ALLOWED | CONSTRAINED | PROHIBITED
  → _assess_dataset_need()            # status: DIRECT | PROXY_ONLY | MISSING
  → _assess_academic_need()           # status: SUPPORTED | MIXED | INSUFFICIENT
  → _compose_transportability_view()  # status: IDENTIFIED | PARTIALLY | BOUNDED | UNSUPPORTED
  → CrossGraphEvidenceProfile         # four-dimensional confidence for each evidence need
```

---

<a id="4-scientist_default-стандартныи-workflow"></a>

## 4. scientist_default — standard workflow

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

### Stages

1. **Data preparation** (in parallel):
   - `build_data_snapshot` — Fabric DataSnapshot
   - `build_execution_plan` → `build_method_catalog_snapshot` → `run_preflight` → `ready_to_run`
   - `link_trinity` — validates the TrinityBundle
   - `bind_foundry_inputs` → `run_data_plane_gate` — PII/quality gates

2. **Compilation:**
   - `compile_foundry` — TrinityBundle → Foundry exec plan
   - `compile_cross_graph_evidence` — gathers evidence from the three graphs
   - `resolve_parameters` — obtains causal parameters from the SKG

3. **Simulation and analysis** (in parallel after `run_simulation`):
   - `legal_check` — checks legality
   - `run_causal_evaluation` — causal analysis (ATE, HTE)
   - `run_distributional_analysis` — distribution across groups
   - `propagate_uncertainty` — propagates uncertainty

4. **Governance and decision:**
   - `run_normative_arbitration` — normative trade-offs
   - `run_governance` — governance gates (verdict: APPROVED | NEEDS_REVISION | BLOCKED)
   - `run_evaluator` — evaluates run quality
   - `build_decision_packet` — builds the final decision packet

---

<a id="5-scientist_causal_full-полныи-каузальныи-анализ"></a>

## 5. scientist_causal_full — full causal analysis

### Differences from `default` (+4 nodes)

```text
Additional nodes:
  build_literature_prior → reconcile_causal_graph  (before compile_cross_graph_evidence)
  run_causal_queries → run_causal_ensemble         (after run_causal_evaluation)
  run_abm_consistency                               (after run_causal_ensemble)
  run_transportability                              (after run_abm_consistency)
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

### Additional stages

| Node                     | What it does                                                                                          |
| ------------------------ | ----------------------------------------------------------------------------------------------------- |
| `build_literature_prior` | Builds `LiteratureCausalPrior` from the SKG: a causal graph with literature evidence                  |
| `reconcile_causal_graph` | Merges the data graph, literature prior, and LLM hints into a reconciled graph                        |
| `run_causal_queries`     | Runs a structural causal query (interventional/counterfactual) through GCM                            |
| `run_causal_ensemble`    | Runs a shared query across an ensemble of ≤10 SCMs and forms a consensus with an uncertainty envelope |
| `run_abm_consistency`    | Compares SCM macro effects with ABM micro aggregates (phase-transition detection)                     |
| `run_transportability`   | Three-graph closure: causal + datasets + legal → transport result                                     |

---

<a id="6-scientist_policy_verified-верифицированная-политика"></a>

## 6. scientist_policy_verified — verified policy

### Purpose

This workflow is intended for cases where no TrinityBundle is ready and only a policy question is available.
The documented workflow has the following stages:

1. Finds legal grounds in the Lex graph.
2. Verifies the sources it finds.
3. Drafts policy options.
4. Formalizes them as a TrinityBundle for Foundry.
5. Runs the full analysis (simulation + causal analysis + governance).

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

### Stage 1: Request planning

**`plan_policy_request`** — creates a PolicyRequestFrame:

- Extracts `policy_question`, jurisdiction (default: `UA`), domain, and `as_of`.
- Generates `request_id` from a SHA-256 hash.
- Sets `policy_answer_mode = "verified_async"`.

### Stage 2: Legal candidate collection

**`compile_cross_graph_evidence`** — gathers an evidence profile from the three graphs.

**`assemble_legal_candidate_pack`** — searches the Lex graph:

- Generates up to `max_candidate_queries` (default: 40) search queries.
- Includes Ukrainian-language query variants.
- Collects `fact_hits` and `provision_hits`.
- Tracks `hit_reasons` and `anchor_coverage`.

### Stage 3: Source expansion

**`expand_legal_source_pack`** — resolves candidates into full source bundles:

- Loads document version chains.
- Resolves the reference neighborhood (`max_reference_hops=2`).
- Collects appendix context (headings and tables).
- Limit: `max_source_docs=120`.

### Stage 4: Source verification

**`run_source_verification`** — verifies citations and claims:

1. **Baseline claims** — derived deterministically from source bundles and candidate facts:
   - Checks that the citation exists in the text and the anchor matches.
   - Confidence = max(0.5, min(fact.confidence, 0.99))

2. **LLM verification** (optional, if an LLM is available):
   - Each source bundle → verifier agent → JSON claims.
   - Computes `disagreement_rate` (baseline vs. LLM).

3. **Merge** — deduplicates by `(claim_type, anchor, claim_text)` and keeps the highest-confidence result.
4. **Gap detection** — source bundles with no verified claims become `SourceCoverageGap` records.
   - Severity is `critical` for `approval_bundle` and `amendment_bundle`.

### Stage 5: Gap review (bounded recovery)

**`run_source_gap_review`** — iteratively attempts to recover coverage:

```text
Cycle 1: gaps → recovery queries → re-assemble → re-expand → re-verify → merge
Cycle 2: if gaps remain → repeat
After cycle 2: STOP → emit a report with `unresolved_critical_gaps`
```

**Limits:**

- `verification_cycles_completed >= 2` → stop recovery.
- `max_gap_review_calls = 80` — gap-review budget.
- If critical gaps remain → `needs_expert_review = True`.

### Stage 6: Drafting policy options

**`draft_policy_options`** — uses verified claims:

- `verified_options` — supported by citations and legal grounds.
- `hypothesis_options` — hypothetical options (when `allow_hypotheses=True`).
- Each option includes: `title`, `summary`, `legal_basis_refs`, and `constraints`.

### Stage 7: Formalization

**`formalize_verified_policy`** — PolicyOptionSet → TrinityBundle:

- Selects the primary option (the first verified option, falling back to a hypothesis).
- Creates a `DraftResult` with interventions.
- Uses `MockFormalizerAgent` to create a TrinityBundle.
- Sets `policy_trinity_generated = True`.

### Stage 8: Standard pipeline (as in `default`)

`compile_foundry` → `resolve_parameters` → `run_simulation` → analysis → governance

### Stage 9: Final report

**`build_verified_policy_report`** — assembles a `VerifiedPolicyReport`:

- executive_summary
- `verified_legal_basis` (all verified claims)
- policy_options (verified + hypothesis)
- constraints_and_timing
- simulation_and_causal_implications
- `verified_findings` (formatted claims with citations)
- hypotheses
- `missing_evidence` (from `unresolved_critical_gaps`)
- citation_appendix
- intervention_legal_basis_map
- needs_expert_review flag

**`build_decision_packet`** — final `DecisionPacket` with a monitoring contract.

### Default `policy_verified` parameters

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

## 7. Foundry and Data Plane { #foundry-data-plane }

### Data Plane Bindings

```text
External Data
  → Fabric Connectors (UNPD, WVS, ...)
  → DataSnapshot (tabular payload + quality report)
  → build_input_bindings() → FoundryInputBindings
  → GlobalState (typed slots: agent-scoped, firm-scoped)
```

**Binding rules:** `source_path` → `target_slot_id`, with transformations (`identity`, `to_bool`, `to_int`, `scale`, `clip`, `round`).

**Quality Gates (DataPlaneGateNode):**

- PII scan → block if PII is detected.
- Quality gate → freshness (≤14 days = fresh), grade (A–F).

### Causal Engine (Pearl-Bareinboim Orchestrator)

Three phases:

**1. Identify** — select an identification algorithm:

```text
Counterfactual → ctf_transportability | id_star
Measurement error → identify_with_proxy
Multi-outcome → multi_outcome_id
Stochastic → sid_algorithm
Selection/transport → tr_algorithm + SelectionDiagram
Standard → id_with_oracle_fallback (backdoor/frontdoor)
```

Result: `IdentificationResult` (`estimand_ast` + `proof_steps`) or `NegativeCertificate`.

**2. Compile** — `EstimandAST` → `ExecutorGraph` (DAG of typed nodes with `method_fqn`, `params`, and `dependencies`).

**3. Estimate** — execute nodes in topological order:

- Nuisance nodes (propensity, outcome models)
- Primary estimators (AIPW, DML, IPW, CATE)
- Diagnostics (positivity, overlap, covariate balance)
- → CausalEffectReport + EvidenceBundle

### Methods (`protocols.py`)

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

## 8. IR Analytics — intermediate representations

### CausalEffectReport

- point_estimate, confidence_interval, inference_method
- placebo_results, refutation_results, diagnostic_tests
- → converted to an `UncertaintyEnvelope`

### EstimandAST

A typed tree for a causal query:

- Leaf: `DistributionRef` — P(Y|X), P\*(Y|do(X))
- Operators: Sum, Product, Ratio, Integral, Nuisance
- Side conditions: positivity, overlap, SUTVA, consistency

### EvidenceBundle

Machine-readable audit trail:

- proof_steps (identification)
- data_provenance
- compilation_steps
- estimation_steps (wall_time, backend, params_hash)
- diagnostic_scores
- quality_report (composite grade)

### NegativeCertificate

When identification fails:

- blocking_type: HEDGE | S_NODE | POSITIVITY | SUPPORT_MISMATCH | MISSING_DISTRIBUTION
- fallback_results: partial identification bounds
- suggested_experiments: RCT, natural experiment, IV, DiD, RDD
- epistemicTier: EXACT_NONPARAMETRIC → PARTIAL → ASSUMPTION_DEPENDENT → DIAGNOSTIC

---

## 9. Checkpoint and recovery { #checkpoint-recovery }

### Checkpoint Policy

```python
CheckpointPolicy = "off" | "strict" | "best_effort"
```

### How it works

1. After each node → `CASCheckpointHook.on_node_complete()`.
2. Saves: `run_id`, `sequence_number`, `completed_nodes`, `workflow_fingerprint`, and `cache_entry_refs`.
3. On recovery: loads `NodeResultCache` from checkpoint references.
4. If `workflow_fingerprint` does not match → `WorkflowMismatchError`.
5. A run lock via `fcntl.flock` prevents concurrent execution of the same `run_id`.

### Node Cache

- Idempotency key = SHA256(workflow_spec + state + bind_params)
- Disabled for: `noop`, `set_state`, `emit_artifact`, and `enrich_knowledge`.
- On a cache hit → skip execution and use the cached outcome.

### Error Policy

All three workflows use `error_policy = "continue"`:

- When a node fails → its upstream nodes are blocked.
- Other DAG branches continue executing.
- The final `WorkflowReport` contains the status of every node.

---

## 10. Node-by-node reference { #node-details }

### Data Nodes

| Node                    | Node ID                                    | Description                                                                                                            |
| ----------------------- | ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| **build_data_snapshot** | `scientist.node_build_data_snapshot@1.0.0` | Calls Fabric `snapshot()` to create a `DataSnapshot`. Skips if one already exists. Extracts the PII scan summary.      |
| **bind_foundry_inputs** | `scientist.node_bind_foundry_inputs@1.0.0` | Builds deterministic Foundry input bindings. Validates the model spec. Returns a binding report.                       |
| **enrich_knowledge**    | `scientist.node_enrich_knowledge@1.1.0`    | Builds a `knowledge_bundle` through Scholar. Manages freshness, cooldown, and drift. Uses distributed refresh locking. |

### Planning Nodes

| Node                              | Node ID                                              | Description                                                                                                            |
| --------------------------------- | ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **plan_policy_request**           | `scientist.node_plan_policy_request@1.0.0`           | Creates a PolicyRequestFrame from `policy_question`, jurisdiction, and domain. _(policy_verified only)_                |
| **build_execution_plan**          | `scientist.node_build_execution_plan@1.0.0`          | Creates and persists an ExecutionPlan (`data_needs`, `constraints`, `expected_outputs`).                               |
| **build_method_catalog_snapshot** | `scientist.node_build_method_catalog_snapshot@1.0.0` | Snapshots the FoundryMethod catalog and capability contract.                                                           |
| **run_preflight**                 | `scientist.node_run_preflight@1.0.0`                 | Validates the ExecutionPlan against the live method catalog. Sets `preflight_ready`.                                   |
| **ready_to_run**                  | `scientist.node_ready_to_run@1.0.0`                  | Hard gate: blocks execution if `preflight_ready=False`.                                                                |
| **compile_cross_graph_evidence**  | `scientist.node_compile_cross_graph_evidence@1.0.0`  | `CrossGraphEvidenceCompiler`: combines evidence from three graphs and evaluates benchmarks.                            |
| **assemble_legal_candidate_pack** | `scientist.node_assemble_legal_candidate_pack@1.0.0` | Searches the Lex graph for legal candidates (up to 40 queries, including Ukrainian variants). _(policy_verified only)_ |
| **expand_legal_source_pack**      | `scientist.node_expand_legal_source_pack@1.0.0`      | Expands candidates into source bundles with version chains and references. _(policy_verified only)_                    |
| **run_source_verification**       | `scientist.node_run_source_verification@1.0.0`       | Baseline + LLM claim verification; gap detection. _(policy_verified only)_                                             |
| **run_source_gap_review**         | `scientist.node_run_source_gap_review@1.0.0`         | Iteratively attempts to recover coverage (max 2 cycles). _(policy_verified only)_                                      |
| **draft_policy_options**          | `scientist.node_draft_policy_options@1.0.0`          | Drafts verified and hypothesis policy options. _(policy_verified only)_                                                |
| **run_evaluator**                 | `scientist.node_run_evaluator@1.0.0`                 | Evaluates run quality and decides whether another iteration is needed.                                                 |

### Compile Nodes

| Node                          | Node ID                                          | Description                                                                                                                              |
| ----------------------------- | ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **link_trinity**              | `scientist.node_link_trinity@1.0.0`              | Validates the TrinityBundle: mechanisms, slots, merge rules, constraints, selectors, and units.                                          |
| **compile_foundry**           | `scientist.node_compile_foundry@1.0.0`           | Compiles Trinity into a Foundry execution plan. Produces 7 artifacts (exec_plan, lowered_ir, program_graph, slot_layout, treasury_plan). |
| **formalize_verified_policy** | `scientist.node_formalize_verified_policy@1.0.0` | Converts a PolicyOptionSet to a TrinityBundle for Foundry. _(policy_verified only)_                                                      |

### Simulate Nodes

| Node                            | Node ID                                            | Description                                                                                                                                                            |
| ------------------------------- | -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **run_simulation**              | `scientist.node_run_simulation@1.0.0`              | Executes the Foundry plan. Produces 8 artifacts (result, metrics, state_delta, snapshot, constraints, environment, attestation, sbom).                                 |
| **run_distributional_analysis** | `scientist.node_run_distributional_analysis@1.0.0` | `DistributionalReport`: breakdown by geography and income quintile.                                                                                                    |
| **propagate_uncertainty**       | `scientist.node_propagate_uncertainty@1.0.0`       | Propagation input uncertainty → output metrics.                                                                                                                        |
| **run_causal_evaluation**       | `scientist.node_run_causal_evaluation@2.0.0`       | Causal analysis (ATE/HTE). Refutation and sensitivity are optional. Preserves the full declared output contract; conditional outputs carry a verifiable typed refusal. |

### Causal Nodes (causal_full only)

| Node                       | Node ID                                       | Description                                                                          |
| -------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------ |
| **build_literature_prior** | `scientist.node_build_literature_prior@1.0.0` | Builds a `LiteratureCausalPrior` from the SKG: a causal graph with evidence weights. |
| **reconcile_causal_graph** | `scientist.node_reconcile_causal_graph@1.0.0` | Merge: data graph + literature prior + LLM hints → reconciled graph.                 |
| **run_causal_queries**     | `scientist.node_run_causal_queries@1.0.0`     | Runs a structural causal query through GCM. Persists the query result and envelope.  |
| **run_causal_ensemble**    | `scientist.node_run_causal_ensemble@1.0.0`    | ≤10 SCM members → shared query → consensus weights → uncertainty envelope.           |
| **run_abm_consistency**    | `scientist.node_run_abm_consistency@1.0.0`    | SCM macro effects ↔ ABM aggregates. Phase transition detection.                      |
| **run_transportability**   | `scientist.node_resolve_transport@1.0.0`      | Three-graph closure (causal + datasets + legal) → TransportabilityResult.            |

### Governance Nodes

| Node                          | Node ID                                          | Description                                                                                                           |
| ----------------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| **run_data_plane_gate**       | `scientist.node_data_plane_gate@1.0.0`           | PII and quality gates before expensive Foundry execution.                                                             |
| **legal_check**               | `scientist.node_legal_check@1.0.0`               | Evaluate legality: NormPack → LegalReport + ChangeProposal (compliance grade).                                        |
| **run_normative_arbitration** | `scientist.node_run_normative_arbitration@1.0.0` | Normative trade-offs: stakeholder utilities, outcomes, and rights audit.                                              |
| **run_governance**            | `scientist.node_run_governance@1.0.0`            | Governance pipeline: quality → safety → alignment → consistency → tradeoff. Verdict: APPROVED/NEEDS_REVISION/BLOCKED. |

### Decide Nodes

| Node                             | Node ID                                             | Description                                                                                  |
| -------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| **build_verified_policy_report** | `scientist.node_build_verified_policy_report@1.0.0` | `VerifiedPolicyReport` with verified findings, citations, and gaps. _(policy_verified only)_ |
| **build_decision_packet**        | `scientist.node_build_decision_packet@1.0.0`        | Final `DecisionPacket`: validity envelope, triggers, dependencies, and monitoring contract.  |

---

## Appendix: Data path through `policy_verified`

```text
1. Policy question ("Яка податкова ставка оптимальна для ФОП?" — Ukrainian input literal; English gloss: "Which tax rate is optimal for a sole proprietor?")
   │
2. plan_policy_request
   │  → PolicyRequestFrame {question, jurisdiction="UA", domain, goals, constraints}
   │
3. compile_cross_graph_evidence
   │  → CrossGraphEvidenceProfile {legal_status, dataset_status, academic_status, transport_status}
   │
4. assemble_legal_candidate_pack
   │  → LegalCandidatePack {fact_hits, provision_hits, queries}
   │  Query literals: "податкова ставка ФОП" (tax rate for a sole proprietor), "єдиний податок група" (single-tax group), "tax rate sole proprietor UA"
   │
5. expand_legal_source_pack
   │  → LegalSourcePack {source_bundles with version chains, reference context}
   │  Up to 120 documents, up to 2 hops for reference resolution
   │
6. run_source_verification
   │  → SourceVerificationReport {verified_claims, unresolved_gaps}
   │  Baseline: citations + facts → claims
   │  LLM: verifier agent → validated claims
   │  Merge → deduplicated claims
   │
7. run_source_gap_review  (max 2 cycles)
   │  Cycle 1: gaps → recovery queries → re-assemble → re-verify → merge
   │  Cycle 2: if gaps remain → repeat
   │  After 2 cycles: STOP → unresolved_critical_gaps
   │
8. draft_policy_options
   │  → PolicyOptionSet {verified_options, hypothesis_options}
   │
9. formalize_verified_policy
   │  → TrinityBundle (with interventions and constraints)
   │
10. compile_foundry → resolve_parameters → run_simulation
    │  → SimulationResult, Metrics, StateSnapshot
    │
11. legal_check + run_causal_eval + run_distrib + propagate_uncertainty
     │  (in parallel)
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
