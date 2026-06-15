# PolicyOS Causal Engine — Architecture, Capabilities & Benchmark Results

Owner: `@foundry-owners`
Source of truth: `src/polisyos/foundry/methods/catalog/causal/**`, `benchmarks/_reports/server_pull_focused_v26_20260320/`, and `tests/unit/foundry/methods/catalog/causal/**`

> **Version**: v26 (March 20, 2026)
> **Location**: `policy-engine/src/polisyos/foundry/methods/catalog/causal/`
> **Benchmark data**: `policy-engine/benchmarks/_reports/server_pull_focused_v26_20260320/`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Layer 1 — Symbolic Identification](#3-layer-1-symbolic-identification)
4. [Layer 2 — Estimand Compilation](#4-layer-2-estimand-compilation)
5. [Layer 3 — Estimation Methods](#5-layer-3-estimation-methods)
6. [Graph Algorithms (ADMG Core)](#6-graph-algorithms-admg-core)
7. [IR Types (Intermediate Representation)](#7-ir-types-intermediate-representation)
8. [Registry & Plugin System](#8-registry-plugin-system)
9. [Data Contracts (Protocols)](#9-data-contracts-protocols)
10. [Benchmark Infrastructure](#10-benchmark-infrastructure)
11. [Benchmark Results (v26)](#11-benchmark-results-v26)
12. [Competitive Positioning](#12-competitive-positioning)
13. [Design Principles](#13-design-principles)

---

## 1. Overview

The Causal Engine is the central analytical core of PolicyOS. It implements the **Pearl-Bareinboim causal inference framework** end-to-end: from symbolic identification of causal queries on DAGs/ADMGs, through compilation to statistical estimands, to numerical estimation with full audit trails.

**Key numbers:**

- **91 Python modules** in the causal catalog
- **70+ registered methods** across 9 development phases
- **55/55 symbolic identification tests** passing (100% accuracy)
- **16/16 transportability tests** passing
- **11/11 missing-data (M-graph) tests** passing
- **Sub-millisecond** symbolic identification (mean 0.37ms)

**Pipeline flow:**

```text
Query → Identify → Compile → Estimate → Audit
```

---

## 2. Architecture

### High-Level Pipeline

```text
User Query (treatment, outcome, graph, data)
    │
    ▼
┌─────────────────────────────────────────┐
│         CausalEngine.identify()         │
│  Routes by query type:                  │
│  • Standard → id_algorithm()            │
│  • Counterfactual → id_star/idc_star    │
│  • Transport → tr_algorithm / z_id      │
│  • Multi-domain → mz_id_algorithm       │
│  • Soft intervention → sid_algorithm    │
│  • Cyclic → cyclic_id                   │
│  • M-graph → full_law_identify          │
│  • Measurement error → proxy pipeline   │
│                                         │
│  Uses: do_calculus, admg_ops            │
│  Output: IdentificationResult           │
│          (EstimandAST or Hedge)         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      EstimandCompiler.compile()         │
│  Pattern-matches EstimandAST →          │
│  • EstimandShape (BACKDOOR, FRONTDOOR,  │
│    IV, DML_COMPATIBLE, TRANSPORT_REWEIGHT│
│    BOUNDS_ONLY, CYCLIC, ...)            │
│  • EstimationStrategy (PLUG_IN, AIPW,   │
│    TMLE, DML, DENSITY_RATIO, ...)       │
│  Output: ExecutionPlan[ExecutorNode]     │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      CausalEngine.estimate()            │
│  MethodRegistry.lookup() → method class │
│  method.pure_step(input_slots, params)  │
│  Output: CausalEffectReport             │
│          + EvidenceBundle (audit trail)  │
└─────────────────────────────────────────┘
```

### Module Map

```text
causal/
├── causal_engine.py          ← Main orchestrator (600+ lines)
├── id_engine.py              ← Identification algorithms (1200+ lines)
├── do_calculus.py            ← Pearl's 3 rules
├── estimand_compiler.py      ← AST → ExecutionPlan (400+ lines)
├── admg_ops.py               ← Pure graph algorithms (500+ lines)
├── protocols.py              ← Data contracts (800+ lines)
├── _registry_boot.py         ← 70+ method registrations
│
├── # Symbolic extensions
├── sigma_calculus.py          ← Selection-biased data (Bareinboim 2012)
├── cyclic_id.py               ← Cyclic SCM identification
├── ctf_calculus.py            ← Counterfactual calculus
├── ctf_transport.py           ← CTF transportability
│
├── # Estimation methods
├── treatment_effects.py       ← AIPW, TMLE, IPW, PSM, CBPS, Entropy Balancing
├── meta_learners.py           ← S/T/X/R/DML learners
├── cate.py                    ← Causal Forest (EconML)
├── forest_dr.py               ← Forest doubly-robust
├── causal_bcf.py              ← Bayesian Causal Forest
├── g_computation.py           ← G-computation
├── g_estimation.py            ← G-estimation
├── superlearner.py            ← Super Learner / stacking
├── tmle_core.py               ← TMLE cross-fit engine
├── nuisance_layer.py          ← Nuisance estimation orchestration
├── nuisance_backends.py       ← sklearn/lightgbm/etc. backends
│
├── # Partial identification & bounds
├── bounds_engine.py           ← Orchestrates bound methods
├── eif_bounds.py              ← EIF-based bounds
├── lp_bounds.py               ← Linear programming auto-bounds
├── transport_bounds.py        ← Bounds under transport assumptions
│
├── # Panel & quasi-experimental
├── synthetic_control.py       ← Synthetic control method
├── advanced_designs.py        ← DiD, modern DiD, RDD, etc.
│
├── # Causal discovery
├── constraint_discovery.py    ← PC, FCI, GES
│
├── # Special topics
├── interference.py            ← Network/spatial AIPW, partial interference
├── missing_data.py            ← M-graph recoverability
├── data_fusion.py             ← Multi-source fusion
├── path_specific.py           ← NDE/NIE via cross-fit EIF
├── actual_causality.py        ← Halpern-Pearl (PN/PS/PNS/HP)
├── ncm_engine.py              ← NCM abduction-action-prediction
├── causal_fairness.py         ← Fairness-constrained identification
├── optimal_design.py          ← CausalExperimentDesigner
├── calibration.py             ← Calibration & density-ratio
└── transport_engine.py        ← Multi-backend transport solver
```

---

<a id="3-layer-1-symbolic-identification"></a>

## 3. Layer 1 — Symbolic Identification

The identification layer answers: _"Can this causal query be expressed as a function of observable data?"_

### Core Algorithms

| Algorithm          | Function               | Theory                                                                    |
| ------------------ | ---------------------- | ------------------------------------------------------------------------- |
| **ID**             | `id_algorithm()`       | Shpitser & Pearl (2006) — complete recursive identification               |
| **IDC**            | `idc_algorithm()`      | Conditional interventional distributions                                  |
| **ID\***           | `id_star_algorithm()`  | Counterfactual identification (Pearl Layer-3)                             |
| **IDC\***          | `idc_star_algorithm()` | Conditional counterfactual identification                                 |
| **Z-ID**           | `z_id_algorithm()`     | Experimental + observational fusion (Bareinboim & Pearl 2013)             |
| **mZ-ID**          | `mz_id_algorithm()`    | Multi-study fusion from K datasets (Bareinboim & Pearl 2016)              |
| **TR**             | `tr_algorithm()`       | Transportability via selection diagrams with S-nodes                      |
| **SID**            | `sid_algorithm()`      | Stochastic/soft intervention identification                               |
| **Do-calculus**    | `rewrite_estimand()`   | Pearl's 3 rules (insertion/deletion, action/observation, action deletion) |
| **Sigma-calculus** | `sigma_identify()`     | Selection-biased data handling (Bareinboim & Pearl 2012)                  |
| **Cyclic-ID**      | `cyclic_identify()`    | Cyclic SCMs with feedback loops                                           |
| **CTF-transport**  | `ctf_transport()`      | Counterfactual transportability across domains                            |

### Output

- **IDENTIFIED**: Returns `EstimandAST` (symbolic expression of the causal effect as function of observables)
- **HEDGE_FOUND**: Returns `HedgeCertificate` (constructive proof of non-identifiability)
- **ORACLE_NEEDED**: Query cannot be resolved without additional data

When identification fails, the engine produces a `NegativeCertificate` with:

- Blocking type (hedge, S-node, positivity violation, etc.)
- Fallback chain: partial bounds → parametric rescue → sensitivity sweep → suggested experiments
- Actionable guidance for the analyst

### Proof Audit

Every identification step is recorded as `ProofStep`:

- Rule applied (e.g., `RULE1`, `C_COMPONENT`, `HEDGE`)
- Variables affected
- Graph state before/after
- Applicable theorem reference

---

<a id="4-layer-2-estimand-compilation"></a>

## 4. Layer 2 — Estimand Compilation

The compiler transforms the symbolic `EstimandAST` into a concrete `ExecutionPlan`.

### EstimandAST Node Types

| Node                | Semantics                                                      |                               |
| ------------------- | -------------------------------------------------------------- | ----------------------------- |
| `DistributionRef`   | P(Y \                                                          | do(X), Z) — leaf distribution |
| `SumNode`           | Σ_V (marginalization over discrete variables)                  |                               |
| `ProductNode`       | Π (multiplication of factors)                                  |                               |
| `RatioNode`         | Numerator / Denominator                                        |                               |
| `ExpectationNode`   | E[Y \                                                          | X, do(Z)]                     |
| `IntegralNode`      | ∫ over continuous variables                                    |                               |
| `NuisanceNode`      | Intermediate fitted model (propensity, outcome, density ratio) |                               |
| `RecoveredDistNode` | M-graph recovered distribution                                 |                               |

### Classification Pipeline

```text
EstimandAST → classify_estimand() → EstimandShape → recommend_estimator() → ExecutionPlan
```

**EstimandShape** (pattern detected):

- `BACKDOOR`, `FRONTDOOR`, `IV`, `DML_COMPATIBLE`
- `TRANSPORT_REWEIGHT`, `BOUNDS_ONLY`, `CATE_REQUIRED`
- `STOCHASTIC_INTERVENTION`, `MEASUREMENT_ERROR_PROXY`
- `CYCLIC`, `COUNTERFACTUAL_IDENTIFIED`

**EstimationStrategy** (chosen approach):

- `PLUG_IN`, `AIPW`, `TMLE`, `DML`
- `DENSITY_RATIO_REWEIGHT`, `MEDIATION`, `IV`
- `MANSKI_BOUNDS`, `GPS_DOSE_RESPONSE`, `SHIFT_TMLE`
- `MULTI_OUTCOME_AIPW`, `REGRESSION_CALIBRATION`, `SIMEX`
- `FIXED_POINT_SOLVER` (for cyclic), `TWIN_NETWORK_MC`

---

<a id="5-layer-3-estimation-methods"></a>

## 5. Layer 3 — Estimation Methods

### Treatment Effects (Core)

| Method                    | Module                 | Reference                       |
| ------------------------- | ---------------------- | ------------------------------- |
| AIPW                      | `treatment_effects.py` | Robins, Rotnitzky & Zhao (1994) |
| TMLE                      | `tmle_core.py`         | van der Laan & Rubin (2006)     |
| IPW                       | `treatment_effects.py` | Horvitz & Thompson (1952)       |
| Propensity Score Matching | `treatment_effects.py` | Rosenbaum & Rubin (1983)        |
| Entropy Balancing         | `treatment_effects.py` | Hainmueller (2012)              |
| CBPS                      | `treatment_effects.py` | Imai & Ratkovic (2014)          |
| G-computation             | `g_computation.py`     | Robins (1986)                   |
| DML                       | `meta_learners.py`     | Chernozhukov et al. (2018)      |

### Heterogeneous Treatment Effects (HTE)

| Method                 | Module             | Reference                        |
| ---------------------- | ------------------ | -------------------------------- |
| Causal Forest          | `cate.py`          | Athey & Wager (2019)             |
| Forest Doubly-Robust   | `forest_dr.py`     | Athey, Tibshirani & Wager (2019) |
| Bayesian Causal Forest | `causal_bcf.py`    | Hahn, Murray & Carvalho (2020)   |
| S/T/X/R-Learner        | `meta_learners.py` | Künzel et al. (2019)             |
| Super Learner          | `superlearner.py`  | van der Laan et al. (2007)       |

### Partial Identification & Bounds

| Method           | Module                | Reference                          |
| ---------------- | --------------------- | ---------------------------------- |
| Manski bounds    | `bounds_engine.py`    | Manski (1989)                      |
| Balke-Pearl LP   | `lp_bounds.py`        | Balke & Pearl (1994)               |
| Lee bounds       | `bounds_engine.py`    | Lee (2009)                         |
| Imbens-Manski CI | `bounds_engine.py`    | Imbens & Manski (2004)             |
| Copula bounds    | `bounds_engine.py`    | —                                  |
| Rosenbaum sharp  | `bounds_engine.py`    | Rosenbaum (2002)                   |
| Transport bounds | `transport_bounds.py` | Bareinboim & Pearl (2016)          |
| EIF bounds       | `eif_bounds.py`       | Efficient influence function based |

### Panel & Quasi-Experimental

| Method                     | Module                 | Reference                            |
| -------------------------- | ---------------------- | ------------------------------------ |
| Synthetic Control          | `synthetic_control.py` | Abadie, Diamond & Hainmueller (2010) |
| DiD (standard + staggered) | `advanced_designs.py`  | Callaway & SantAnna (2021)           |
| RDD                        | `advanced_designs.py`  | Imbens & Lemieux (2008)              |

### Causal Discovery

| Method | Module                    | Reference                          |
| ------ | ------------------------- | ---------------------------------- |
| PC     | `constraint_discovery.py` | Spirtes, Glymour & Scheines (2000) |
| FCI    | `constraint_discovery.py` | Spirtes et al. (2000)              |
| GES    | `constraint_discovery.py` | Chickering (2002)                  |

### Special Topics

| Capability                       | Module                                          |
| -------------------------------- | ----------------------------------------------- |
| Network/spatial interference     | `interference.py`                               |
| M-graph recovery (missing data)  | `missing_data.py`                               |
| Multi-source data fusion         | `data_fusion.py`                                |
| Path-specific effects (NDE/NIE)  | `path_specific.py`                              |
| Actual causality (Halpern-Pearl) | `actual_causality.py`                           |
| NCM abduction-action-prediction  | `ncm_engine.py`                                 |
| Causal fairness                  | `causal_fairness.py`                            |
| Optimal experimental design      | `optimal_design.py`                             |
| Transportability solver          | `transport_engine.py`                           |
| Continuous/multi-treatment       | `continuous_treatment.py`, `multi_treatment.py` |
| Counterfactual transport (CTF)   | `ctf_calculus.py`, `ctf_transport.py`           |

---

## 6. Graph Algorithms (ADMG Core)

Module: `admg_ops.py` — pure functions over Acyclic Directed Mixed Graphs.

| Function                     | Description                                |
| ---------------------------- | ------------------------------------------ |
| `ancestors(V, G)`            | BFS closure An(V)                          |
| `descendants(V, G)`          | BFS closure De(V)                          |
| `do_operator(X, G)`          | Mutilated graph G\_{do(X)}                 |
| `c_components(G)`            | C-component decomposition (Union-Find)     |
| `induced_subgraph(V, G)`     | Restriction of G to vertex set V           |
| `m_separation(X, Y, Z, G)`   | M-separation via Bayes Ball (mixed graphs) |
| `topological_order(G)`       | Kahn's algorithm                           |
| `augment_with_s_nodes(G, S)` | Selection diagram construction             |

**Performance features:**

- WeakRef-based caching for adjacency matrices and c-components
- Edge marks: `TAIL`, `ARROW`, `CIRCLE` (PAG uncertainty)
- Supports DAG, CPDAG, PAG, ADMG, MGRAPH graph types

---

## 7. IR Types (Intermediate Representation)

All external data flows through typed IR from `polisyos.ir.analytics`:

### CausalGraphModel (`causal_graph.py`)

- Graph types: DAG, CPDAG, PAG, MGRAPH, ADMG
- Edges with source provenance (`DATA`, `LITERATURE`, `LLM_PRIOR`, `EXPERT`, `SIMULATION`)
- Multi-confidence scoring per edge (data, literature, LLM, expert, combined)
- Export: DOT, rustworkx, NetworkX, Kuzu graph DB
- Validation: acyclicity for DAGs, M-graph naming conventions

### EstimandAST (`estimand.py`)

- Recursive AST with 8 node types (see Layer 2)
- Side conditions: POSITIVITY, OVERLAP, SUTVA, CONSISTENCY, NO_INTERFERENCE, etc.
- Domain awareness: SOURCE, TARGET, EXPERIMENTAL
- LaTeX rendering: `to_latex()` on leaf nodes

### EvidenceBundle (`evidence_bundle.py`)

- Complete audit trail: `ProofStep[]` → `CompilationStep[]` → `EstimationStep[]`
- SHA-256 fingerprints for graph and estimand
- Data provenance tracking
- Diagnostic scores aggregation
- `to_summary()` for human-readable audit

### CausalEffectReport (`causal.py`)

- Point estimate + SE + CI + p-value
- Refutation results (placebo, random common cause, bootstrap)
- Diagnostic tests
- Transport result if applicable
- `to_uncertainty_envelope()` for governance integration

### NegativeCertificate (`negative_certificate.py`)

- Blocking type: HEDGE, S_NODE, POSITIVITY_VIOLATION, SUPPORT_MISMATCH, MISSING_DISTRIBUTION
- Fallback chain: PartialIdentificationResult → ParametricRescueResult → SensitivitySweepResult → SuggestedExperiment
- Epistemic tiers: EXACT_NONPARAMETRIC → PARTIAL_IDENTIFICATION → ASSUMPTION_DEPENDENT → DIAGNOSTIC_GUIDANCE

### PartialIdentificationResult (`partial_identification.py`)

- 14 bound methods (Manski through Rosenbaum sharp)
- BoundsReport with consensus bounds (max lower, min upper across methods)
- SensitivitySweepResult for parameter sensitivity analysis
- Informativeness detection

### Actual Causality (`actual_causality.py`)

- PNResult, PSResult, PNSResult — probabilities of causation
- PNPSBounds — Tian & Pearl sharp bounds
- HPResult — Halpern-Pearl AC1+AC2+AC3 with degree of responsibility/blame

---

<a id="8-registry-plugin-system"></a>

## 8. Registry & Plugin System

`_registry_boot.py` exports `register_causal_methods()` which dynamically registers **70+ method classes** via the Foundry `MethodRegistry`.

### Registration Phases

| Phase   | Methods                                                             | Count |
| ------- | ------------------------------------------------------------------- | ----- |
| Phase 1 | Treatment effects (AIPW, TMLE, IPW, PSM, CBPS, BCF, Forest-DR)      | ~10   |
| Phase 2 | Missing data (RecoverabilityTest, OrderedRecovery, FullLawIdentify) | ~5    |
| Phase 3 | Discovery (PC, FCI, GES, DAGMA, PCMCI)                              | ~5    |
| Phase 4 | Interference & network causal inference                             | ~5    |
| Phase 5 | Measurement error, conditional/dynamic interventions, multi-outcome | ~8    |
| Phase 6 | Continuous & multi-valued treatments (GPS, kernel, shift)           | ~8    |
| Phase 7 | Advanced partial ID (Copula, sensitivity bounds)                    | ~6    |
| Phase 8 | Fairness (CF, PS, TV decomposition)                                 | ~5    |
| Phase 9 | Data fusion, optimal experimental design                            | ~5    |

All registrations use lazy imports (`try/except`) for optional dependencies: `econml`, `dowhy`, `cvxpy`, `shap`, `tigramite`, `lightgbm`.

---

## 9. Data Contracts (Protocols)

Module: `protocols.py` — Pydantic models with strict validation (`extra="forbid"`).

| Contract                     | Fields                                             | Use Case                           |
| ---------------------------- | -------------------------------------------------- | ---------------------------------- |
| `PanelObservationalData`     | n_units, n_periods, treatment, outcome, covariates | DiD, Synthetic Control             |
| `HTEObservationalData`       | n_obs, n_features, treatment, outcome, covariates  | HTE (Causal Forest, meta-learners) |
| `GraphCausalData`            | data + CausalGraphModel (DoWhy v2+)                | Graph-aware estimation             |
| `TimeSeriesCausalData`       | n_timesteps, n_variables                           | PCMCI                              |
| `TabularCausalDiscoveryData` | n_samples, n_variables                             | PC/FCI/GES                         |
| `SCMFitData`                 | data + graph + literature priors                   | SCM fitting                        |
| `SCMQueryData`               | SCM spec + CausalQuery                             | NCM/AAP execution                  |
| `RDDObservationalData`       | running variable, cutoff, bandwidth                | RDD                                |
| `NetworkCausalData`          | adjacency, exposure model                          | Interference                       |
| `ContinuousTreatmentData`    | continuous treatment variable                      | GPS dose-response                  |
| `MultiTreatmentData`         | multi-arm treatment                                | Multinomial IPW                    |
| `FairnessObservationalData`  | sensitive attributes                               | Fairness estimators                |

All contracts include shape validation, missing-data detection, and finite-value checks.

---

## 10. Benchmark Infrastructure

### 6-Circuit Architecture

The benchmark suite is organized into **6 core circuits** plus supplementary suites:

| Circuit             | Target                                   | Pass Bar                              |
| ------------------- | ---------------------------------------- | ------------------------------------- |
| **1. Symbolic**     | ID algorithm correctness (55 gold cases) | 100% accuracy, zero false positives   |
| **2. Estimation**   | ACIC, LBIDD, RealCause, HTE              | Mean rank ≤ top-2; PEHE ≤ 2× baseline |
| **3. Discovery**    | Sachs, Tuebingen, CauseME                | SHD ≤ 11; skeleton precision/recall   |
| **4. Missing Data** | 10 canonical M-graph cases               | 100% recoverability correctness       |
| **5. Transport**    | ID, TR, mZ-ID, CTF formulas              | 100% formula correctness              |
| **6. Policy**       | DiD natural experiments, interference    | Effect calibration, CI coverage       |

### Supporting Suites

- **Adversarial stress** (3 cases): False-positive provocation on small graphs
- **Capability wins** (11 demos): Unique PolicyOS capabilities vs. baselines
- **Reproducibility** (3 suites): Deterministic outputs, no-flaky 3× repeats, audit trail completeness

### Benchmark Harness (`harness.py`)

```text
BenchmarkCase → runner() → checker() → CaseResult (PASS/FAIL/ERROR/TIMEOUT)
    │
    ▼
BenchmarkReport → CircuitScore per circuit
    │
    ▼
Scorecards → Mean rank, max rank, deviation, top-quartile failure
```

### Scoring Methodology (`metrics.py`, `research_metrics.py`)

- **AccuracyMetrics**: TP, TN, FP, FN; any FP = blocker
- **TimingStats**: mean, p50, p95, max (seconds)
- **MemoryStats**: mean, peak RSS (MB)
- **ProofStepStats**: mean/max steps, rule distribution
- **Research metrics**: PEHE, ECETH (calibration error), policy value, overlap diagnostics

### Claim Profiles

| Claim                         | Required Suites                                  |
| ----------------------------- | ------------------------------------------------ |
| **Pearl-Bareinboim frontier** | Symbolic + Missing + Transport + Reproducibility |
| **Full-stack publication**    | All 6 circuits + all capability wins             |

---

## 11. Benchmark Results (v26)

### Run Environment

- **Date**: March 20, 2026
- **Platform**: Python 3.12.3, Linux x86_64
- **Profile**: `flagship_plus_production` (air-m2 tier)
- **Total suites**: 31

### Claim Readiness

| Claim                                      | Status        | Detail                                    |
| ------------------------------------------ | ------------- | ----------------------------------------- |
| **Pearl-Bareinboim frontier completeness** | **READY**     | 18/18 suites passed                       |
| **Publication-grade full-stack SOTA**      | **NOT READY** | 4 critical failures (estimation timeouts) |

### Results by Circuit

#### Circuit 1: Symbolic Identification — **55/55 (100%)**

| Metric          | Value  |
| --------------- | ------ |
| True positives  | 27     |
| True negatives  | 12     |
| False positives | 0      |
| False negatives | 0      |
| Mean latency    | 0.37ms |
| Max latency     | 3.87ms |

Covers: ID, IDC, ID\*, frontdoor, hedge, CTF transport, cyclic SCC, sigma calculus, M-graph recoverability. 35+ proof rule types exercised.

#### Adversarial Stress — **3/3 (100%)**

Bow-arc false positive guards, frontdoor with decoy nodes, false identifiability detection. Mean 1.67 proof steps per case.

#### Circuit 4: Missing Data (M-graph) — **11/11 (100%)**

All MCAR, MAR, MNAR variants correctly classified for recoverability.

#### Circuit 5: Transport — **16/16 (100%)**

S-node identification, instrument nodes, bow-arc non-transportability, CTF chains, L2 reduction. Mean 133ms.

#### Circuit 6a: Policy Natural Experiments — **3/3 (100%)**

| Scenario           | ATE         | 95% CI       |
| ------------------ | ----------- | ------------ |
| Clean rollout DiD  | 1.997       | [1.53, 2.46] |
| Placebo null       | ~0          | As expected  |
| Staggered adoption | 0.495 (ATT) | Weighted     |

#### Discovery — **4/4 (100%)**

Sachs network (3/3) + Tuebingen pair (1/1).

#### Reproducibility — **5/5 (100%)**

All audit trail fields populated, deterministic replay verified, no regressions.

#### Capability Wins — **All 11 passing**

Multi-source mZ-ID, fusion + missingness, symbolic non-ID certificate, CTF transport, compiled audit, cyclic feedback, surrogate experiments, nested surrogate CTF, multiple incomplete sources, DID + interference, non-transportability bounds.

---

#### Circuit 2: Estimation — **BLOCKER**

| Suite                  | Pass Rate     | Issue                                           |
| ---------------------- | ------------- | ----------------------------------------------- |
| `estimation_acic`      | 0/6           | Timeout (mean 426s, limit 300s, peak RAM 598MB) |
| `estimation_lbidd`     | 0/5           | Timeout                                         |
| `estimation_realcause` | 0/6           | Timeout (cascade)                               |
| `hte_interpretable`    | 11/14 (78.6%) | 3 failures on sparse features                   |

**ACIC root cause**: Multi-method ensemble evaluation (15+ variants × cross-validation) exceeds time budget. Where partial results exist, ATE estimates and CI coverage are reasonable.

**HTE sparse failure**: On `sparse_linear_2mod`, PolicyOS methods show 2–3× higher PEHE vs. best comparator:

- PolicyOS BCF PEHE: 0.596 (threshold: 0.346)
- PolicyOS Causal Forest PEHE: 0.376
- Best comparator PEHE: 0.173

---

### Summary Scorecard

| Circuit                           | Pass Rate     | Status             |
| --------------------------------- | ------------- | ------------------ |
| Symbolic identification           | 55/55 (100%)  | **PASS**           |
| Adversarial stress                | 3/3 (100%)    | **PASS**           |
| Missing data (M-graph)            | 11/11 (100%)  | **PASS**           |
| Transport / fusion                | 16/16 (100%)  | **PASS**           |
| Policy natural experiments        | 3/3 (100%)    | **PASS**           |
| Discovery                         | 4/4 (100%)    | **PASS**           |
| Reproducibility / audit           | 5/5 (100%)    | **PASS**           |
| Capability wins                   | 11/11 (100%)  | **PASS**           |
| Estimation (ACIC/LBIDD/RealCause) | 0/17 (0%)     | **FAIL** — timeout |
| HTE interpretable                 | 11/14 (78.6%) | **PARTIAL**        |

---

## 12. Competitive Positioning

### Capabilities vs. Y0, DoWhy, EconML

| Capability                    | PolicyOS | Y0      | DoWhy   | EconML |
| ----------------------------- | -------- | ------- | ------- | ------ |
| Symbolic ID (complete)        | **Full** | Full    | Partial | —      |
| ID\*/IDC\* (counterfactual)   | **Full** | Partial | —       | —      |
| Transportability (TR)         | **Full** | Partial | —       | —      |
| Multi-source fusion (mZ-ID)   | **Full** | —       | —       | —      |
| CTF transport                 | **Full** | —       | —       | —      |
| M-graph recoverability        | **Full** | —       | —       | —      |
| Cyclic identification         | **Full** | —       | —       | —      |
| Estimand → execution plan     | **Full** | —       | Partial | —      |
| HTE (meta-learners, forests)  | Full     | —       | —       | Full   |
| Audit trail / evidence bundle | **Full** | —       | Partial | —      |
| Partial ID / bounds           | **Full** | Partial | —       | —      |
| Interference / network        | Full     | —       | —       | —      |
| Causal fairness               | Full     | —       | —       | —      |
| End-to-end pipeline           | **Full** | —       | —       | —      |

**PolicyOS unique capabilities** (no equivalent in Y0/DoWhy/EconML):

- End-to-end symbolic-to-numeric pipeline with compilation
- Multi-source data fusion (mZ-ID) with transport
- Cyclic SCM identification
- Counterfactual transportability (CTF)
- NegativeCertificate with actionable fallback chains
- Compiled execution plans with audit trail
- M-graph + fusion in a single query

---

## 13. Design Principles

1. **Symbolic-then-numeric**: Always identify symbolically before estimating numerically. If identification fails, produce constructive certificates rather than silent failure.

2. **Frozen internal state**: Algorithm internals use frozen dataclasses, never crossing the JSON/Pydantic boundary. External contracts use Pydantic models with `extra="forbid"`.

3. **Pure functions**: Graph algorithms (`admg_ops`) and identification (`id_engine`) are stateless, side-effect-free functions. Caching via WeakRef where needed.

4. **Lazy imports**: Optional heavy dependencies (`econml`, `dowhy`, `cvxpy`, `shap`, `tigramite`) loaded only when the method is actually invoked.

5. **Layered abstractions**: Identification → Compilation → Estimation → Auditing — each layer has clean contracts and can be tested independently.

6. **Exhaustive routing**: `CausalEngine.identify()` explicitly routes by query type (counterfactual, transport, cyclic, M-graph, soft, proxy, standard) rather than relying on fallback heuristics.

7. **Audit-first**: Every run produces an `EvidenceBundle` with proof steps, compilation decisions, estimation metadata, and SHA-256 fingerprints for reproducibility.

8. **Graceful degradation**: Non-identifiable queries produce `NegativeCertificate` with a tiered fallback chain (bounds → parametric rescue → sensitivity → experiments) rather than errors.

9. **Registry-based extensibility**: 70+ methods registered via `_registry_boot.py` — new methods added without touching the engine core.

10. **Contract-driven data**: All method inputs validated through typed Pydantic protocols with shape checks, missing-data detection, and finite-value guards.
