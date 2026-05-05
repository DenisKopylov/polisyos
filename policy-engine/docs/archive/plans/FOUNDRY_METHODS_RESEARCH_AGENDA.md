> **Archived:** This document reflects plans as of 2026-04-18.
> See [current docs](../../explanation/index.md) for up-to-date information.

# PolicyOS Foundry Methods — Research Agenda (Non-Causal Families)

> **Version**: 1.1
> **Date**: 2026-04-19
> **Status**: research-first; no implementation until each track's prerequisite result is in hand
> **Companion documents**:
> - `CAUSAL_ENGINE_RESEARCH_AGENDA.md` — sibling agenda for the causal identification stack
> - `FOUNDRY_REMEDIATION_PLAN.md` — engineering-scope sequencing (T0–T4)
> - `RESEARCH_TRACK_HANDOFF_TEMPLATE.md` — governance surface reused by this document
>
> This document is the research companion to the engineering plans for every
> non-causal foundry method family. It covers the Bayesian, ML, forecasting,
> econometrics, survey, distributional, policy/welfare, optimization, mechanism,
> simulation, microsimulation, network, spatial, validation, and sensitivity
> families. The causal family is the subject of a sibling agenda and is
> referenced from this document only where a cross-family dependency exists.
>
> It contains every task that cannot be scheduled as an engineering ticket
> because it requires a new theorem, an impossibility proof, a new estimator
> family with soundness guarantees, or a formalization of an open mathematical
> problem before it can be implemented.
>
> **How to read this document**: the operational spine is
> [Part 0 — End-to-End Phased Execution Plan](#part-0-phased-execution).
> It slices every research task in the agenda into eleven sequential phases
> of 12–16 **in-phase-parallel** problems each. Phases are strictly
> sequential (Phase N integration deliverables gate Phase N+1); research
> inside a phase is maximally parallel by construction. The per-track
> sections in Parts I–IV are the **detailed problem catalog** — each track
> begins with an open problem, specifies what constitutes a sufficient
> result, defines the deliverable form, states which implementation targets
> depend on it, and identifies what can be run in parallel. The phase plan
> is the *when* and *what-together*; the tracks are the *what-exactly*.
>
> **Interpretation rule**: references to foundry contracts (`PosteriorResult`,
> `PredictionResult`, `OptimizationResult`, `SpatialResult`, `NetworkResult`,
> `EconometricResult`, `MicrosimResult`, `UncertaintyEnvelope`, etc.) denote
> integration targets, not completion status, unless an explicit dated note
> says otherwise.
>
> **Dated implementation note (2026-04-21)**: the archival `Status` line above
> is preserved for historical context. Foundry Phase 0 closure is now
> machine-checked in `tools/quality/validation/foundry_phase0_manifest.json`,
> `tools/quality/validation/validate_foundry_phase0_closure.py`, and
> `tools/quality/validation/run_foundry_phase0_validation.sh`, with
> `docs/reference/foundry/phase0-acceptance.md` as the reference acceptance
> surface. Any intentionally narrowed scope must be called out explicitly in
> those artifacts; green tests alone do not count as closure.
>
> **How research integrates with the system**: research artifacts enter as
> `FrontierSketch` objects with `max_readiness = PROOF_ONLY` (equivalently
> `DecisionReadiness = RESEARCH_ARTIFACT`). They are invisible to Layer D
> (governance, promotion) until their `required_for_promotion` checklist is
> satisfied and they graduate to full `FrontierArtifact`. They are never
> self-certifying. See `RESEARCH_TRACK_HANDOFF_TEMPLATE.md` for the six-judge
> promotion stack and the DecisionReadiness ladder.

---

## Contents

0. [Dated Implementation Status Update (2026-04-21)](#dated-implementation-status-update-2026-04-21)
1. [Overview: Why These Tasks Require Research First](#1-overview)

### Part 0 — End-to-End Phased Execution Plan (primary structure)

- [Part 0 — End-to-End Phased Execution Plan](#part-0-phased-execution)
- [Phase 0 — Foundations: Typed UQ Contracts + Runtime Substrate](#phase-0)
- [Phase 1 — Government Data Lane + Dependence Primitive](#phase-1)
- [Phase 2 — Identification Frontier: Network, Spatial, Econometrics, Distributional](#phase-2)
- [Phase 3 — Decision Layer: Welfare, Optimization, Mechanism](#phase-3)
- [Phase 4 — Dynamics, Forecasting, Agent-Based Simulation](#phase-4)
- [Phase 5 — Validation, Calibration Deepening, Explanation, Advisor Completion](#phase-5)
- [Phase 6 — Streaming, Online, Runtime Reliability, Calibration Subsystem](#phase-6)
- [Phase 7 — Privacy, Federation, Verified Numerics, Benchmark Infra, LLM Lifecycle](#phase-7)
- [Phase 8 — New-Family SOTA: Text, Earth-Observation, RL / Adaptive Experimentation](#phase-8)
- [Phase 9 — Structural Macro, Evidence Synthesis, Matching Markets](#phase-9)
- [Phase 10 — Specialised Families: Point Processes, FDA/TDA, Anomaly, EVT, VFI](#phase-10)
- [Phase 11 — Cross-Family Extensions, Tail Closeout, Meta-Evaluation, Replication](#phase-11)
- [Phase Summary and Operational Properties](#phase-summary)

### Part I — Per-Family Research Tracks (detailed problem catalog, consumed by the phase plan)

2. [Research Track 1 — Bayesian Inference and Scalable Posterior Computation](#2-research-track-1)
3. [Research Track 2 — Machine Learning, Representation Learning, and Foundation Models for Policy](#3-research-track-2)
4. [Research Track 3 — Forecasting under Uncertainty, Hierarchies, and Nonstationarity](#4-research-track-3)
5. [Research Track 4 — Econometrics under Regularization, Cross-Unit Dependence, and Misspecification](#5-research-track-4)
6. [Research Track 5 — Survey Design, Imputation, and Small-Area Estimation](#6-research-track-5)
7. [Research Track 6 — Distributional Analysis, Mobility, and Counterfactual Inequality](#7-research-track-6)
8. [Research Track 7 — Policy Evaluation, Welfare Aggregation, and MCDA](#8-research-track-7)
9. [Research Track 8 — Optimization under Uncertainty, Bilevel, and Inverse Optimization](#9-research-track-8)
10. [Research Track 9 — Mechanism Design, Incentive Compatibility, and Auction Theory](#10-research-track-9)
11. [Research Track 10 — Simulation-Based Inference, Agent-Based Models, and Mean-Field Scaling](#11-research-track-10)
12. [Research Track 11 — Microsimulation: Identifiability, Calibration, and Behavioral Feedback](#12-research-track-11)
13. [Research Track 12 — Network Analysis: Peer Effects, Formation, and Temporal Graphs](#13-research-track-12)
14. [Research Track 13 — Spatial Analysis: MAUP, Interference, and Space-Time Identification](#14-research-track-13)
15. [Research Track 14 — Validation, Sensitivity, and Calibration of Estimators](#15-research-track-14)

### Part II — Cross-Cutting Foundry Infrastructure Tracks

16. [Research Track 15 — Method Selection, Advisor Calibration, and Decision-Theoretic Dispatch](#16-research-track-15)
17. [Research Track 16 — Backend Determinism, Cross-Platform Reconciliation, and Replay Tolerance Budgets](#17-research-track-16)
18. [Research Track 17 — Cost, Energy, and Budget-Robust Estimation Infrastructure](#18-research-track-17)
19. [Research Track 18 — Uncertainty Composition and Multi-Stage Envelope Algebra](#19-research-track-18)
20. [Research Track 19 — Calibration Subsystem: Identifiability, Sloppy Modes, and Target Alignment](#20-research-track-19)
21. [Research Track 20 — Streaming, Online, and Memory-Bounded Estimation](#21-research-track-20)
22. [Research Track 21 — Verified Numerics, Probabilistic Programming, and Proof-Carrying Estimates](#22-research-track-21)
23. [Research Track 22 — Differential Privacy, Synthetic Data, and Federated Estimation](#23-research-track-22)
24. [Research Track 23 — Canonical Benchmark Infrastructure and Synthetic Worlds](#24-research-track-23)
25. [Research Track 24 — LLM-Assisted Research Lifecycle with Verification](#25-research-track-24)

### Part III — New Method Families for Broad-Front SOTA

26. [Research Track 25 — Text, NLP, and Regulatory-Language Analytics](#26-research-track-25)
27. [Research Track 26 — Earth-Observation, Remote Sensing, and Multimodal Geospatial](#27-research-track-26)
28. [Research Track 27 — Reinforcement Learning, Off-Policy Evaluation, and Adaptive Policy Experimentation](#28-research-track-27)
29. [Research Track 28 — Structural Macro: DSGE/HANK, Nowcasting, and Structural Model Averaging](#29-research-track-28)
30. [Research Track 29 — Evidence Synthesis, Meta-Analysis, and Living Reviews](#30-research-track-29)
31. [Research Track 30 — Matching Markets, Assignment, and Public-Sector Combinatorial Auctions](#31-research-track-30)
32. [Research Track 31 — Point Processes, Event-History, and Hazard Models](#32-research-track-31)
33. [Research Track 32 — Functional Data, Topological Data Analysis, and Geometric Representations](#33-research-track-32)
34. [Research Track 33 — Anomaly, Fraud, and Administrative-Integrity Detection](#34-research-track-33)
35. [Research Track 34 — Extreme-Value Theory, Tail Risk, and Policy Stress Testing](#35-research-track-34)
36. [Research Track 35 — Agent-Sim, Value-Function Iteration, and Dynamic Decision Uncertainty](#36-research-track-35)

### Part IV — Extensions to Tracks 1–14

37. [Part IV — Cross-Family Extensions to Tracks 1–14](#37-part-iv-extensions)

### Governance, Maps, and Appendices

38. [Dependency and Parallelization Map](#16-dependency-and-parallelization-map)
39. [Anti-Swamp Governance for Non-Causal Research Tracks](#17-anti-swamp-governance)
40. [Research Economics and Kill Rules](#18-research-economics-and-kill-rules)
41. [Appendix A: Open Problem Catalog](#19-appendix-a)
42. [Appendix B: Missing Contract Inventory](#20-appendix-b)
43. [Appendix C: Cross-Cutting Subsystem Inventory](#21-appendix-c)
44. [Appendix D: New Method Family Stub Inventory](#22-appendix-d)

---

## Dated Implementation Status Update (2026-04-21)

Foundry Phase 0 is no longer tracked only as research intent. Current closure
is machine-checked through the dedicated acceptance stack below:

- Acceptance doc: `docs/reference/foundry/phase0-acceptance.md`
- Manifest: `tools/quality/validation/foundry_phase0_manifest.json`
- Validator: `tools/quality/validation/validate_foundry_phase0_closure.py`
- Reproducible wrapper: `tools/quality/validation/run_foundry_phase0_validation.sh`

This dated note supersedes any accidental reading of the archival Phase-0
section as still purely aspirational. Remaining partial or narrowed claims must
be represented in the machine-checked artifacts above rather than inferred from
the historical plan prose.

## 1. Overview

### 1.1. Scope

The foundry exposes sixteen method families under `polisyos.foundry.methods.catalog/*`.
Of these, `causal/` is addressed by the sibling `CAUSAL_ENGINE_RESEARCH_AGENDA.md`.
The remaining fifteen families — bayesian, distributional, econometrics,
forecasting, mechanism, microsim, ml, network, optimization, policy, sensitivity,
simulation, spatial, survey, validation — collectively form the non-causal
compute surface of PolicyOS. This document organizes their unresolved scientific
gaps into research tracks grouped in four parts:

- **Part I** (Tracks 1–14) — per-family tracks for the fifteen non-causal
  families. Methods are clustered by shared statistical foundation, policy
  problem class, or structural challenge.
- **Part II** (Tracks 15–24, added in v1.1) — cross-cutting foundry
  infrastructure tracks. These cover subsystems that every family shares but
  none owns: method selection/advisor, backend determinism, cost/energy
  models, uncertainty composition, calibration subsystem, streaming,
  verified numerics, differential privacy + federated computation,
  benchmark infrastructure, and LLM-assisted research lifecycle. Gaps here
  silently degrade every family regardless of per-method quality.
- **Part III** (Tracks 25–35, added in v1.1) — new method families the
  foundry does not yet ship but that a SOTA policy engine must host:
  text/regulatory NLP, earth-observation and multimodal geospatial,
  reinforcement-learning and off-policy evaluation, structural macro
  (DSGE/HANK), evidence synthesis / meta-analysis, matching markets and
  combinatorial public-sector auctions, point processes / event history,
  functional data and topological data analysis, anomaly and fraud
  detection, extreme-value theory and stress testing, and agent-sim value-
  function iteration.
- **Part IV** (added in v1.1) — cross-family extensions of Tracks 1–14.
  These capture sub-problems that were not covered in the original fourteen
  tracks (Bayesian model selection, deep survival, probabilistic
  forecasting, local projections, adaptive survey design, wealth-top-coding,
  real-options welfare, combinatorial facility location, continuous-time
  SDE solvers, network motifs, meta-evaluation, etc.).

Clustering is deliberate: research results in one sub-family often unlock
integration across several foundry packages, and results in a cross-cutting
track (Part II) are force multipliers across every family in Parts I and III.

### 1.2. What "research-first" means here

A task is research-first if at least one of the following holds:

1. **No known theorem or estimator covers it in the policy-relevant regime**:
   the mathematical result needed either does not yet exist, or it exists only
   for small / clean / stationary settings and degrades silently when applied
   to policy data (administrative records, panels with spillovers, ordinal
   dimensions, strategically generated networks).

2. **The result exists but formalization is open**: the identifiability or
   soundness result is known in the literature but translating it into a
   typed contract, a computable certificate, or a machine-checkable
   precondition requires non-trivial work.

3. **The approach is inherently assumption-heavy and the right assumptions are
   unknown**: implementation would require making choices that determine
   statistical validity, and those choices require research to justify.

4. **The deliverable is inherently a counterexample, a calibration benchmark,
   or an impossibility result**: such items cannot be shipped as a pull
   request without first doing the mathematics or the simulation study.

### 1.3. What counts as a sufficient research result

For each track this document specifies what constitutes a result that unlocks
the corresponding implementation. The bar is:

- a **theorem with conditions** (sufficient conditions that are machine-checkable,
  or a clear statement that says under which inputs the result holds), or
- a **calibrated benchmark** (a simulation study with known Type I / Type II
  error characterization, or a coverage-rate experiment on semi-synthetic data,
  that tells the system when a method is trustworthy), or
- an **impossibility result with a counterexample class** (which tells the
  system when to block and why), or
- a **reduction to a known solvable problem** (which tells the system what to
  compute and with what tool).

A sketch, a conjecture, or a heuristic that "usually works" does not unlock
implementation.

### 1.4. How research integrates with the system

Research tracks run in parallel with T3/T4 engineering scope from the Foundry
Remediation Plan. They are not blockers for Phase-5 frontier work. The
dependency is the other direction: Phase-5 engineering (typed contract ports,
judge stack, `DecisionReadiness` ladder) makes research more productive by
providing:

- a canonical form for output artifacts (`PosteriorResult`,
  `PredictionIntervalResult`, `OptimizationResult`, `NetworkResult`,
  `SpatialResult`, `EconometricResult`, `MicrosimResult`, `UncertaintyEnvelope`);
- a data-readiness oracle that every research result can consume to define
  its own preconditions;
- a six-judge promotion stack (structural, statistical, robustness, governance,
  reproducibility, compute) that can give machine-readable verdicts on research
  artifacts when they mature.

Research conducted before these are available produces correct mathematics, but
the integration work on graduation is higher.

The **Phased Execution Plan** ([Part 0](#part-0-phased-execution)) is the
operational overlay on top of this integration model. Every task in Parts
I–IV lives inside exactly one of eleven phases; each phase bundles 12–16
parallel research problems that, when their research deliverables are in
hand, are integrated together at the phase gate. Phase N+1 integration
work is not allowed to start until Phase N's integration deliverables have
landed in code. Research sketches from later phases may proceed earlier
under `FrontierSketch` / `PROOF_ONLY` status (§17.4 contamination rules)
but may not alter production until their home phase opens.

### 1.5. Priority among tracks

Not all tracks are equal. Based on the foundry's current shape, policy
deployment needs, and the Phase-5/Phase-6 split in the Foundry Remediation Plan:

| Priority | Tracks | Reason |
|----------|--------|--------|
| Highest | Track 1 (Bayesian UQ + posterior), Track 3 (Forecasting uncertainty), Track 14 (Validation & calibration diagnostics) | Three missing contract families — `PosteriorDiagnosticsBundle`, `ForecastingUncertaintyBundle`, `ValidationReport` — block honest UQ across the entire stack. No other track's estimates can be trusted without them. |
| Highest | Track 5 (Survey & small-area), Track 11 (Microsimulation calibration) | Government-facing pipelines start here; every downstream analysis inherits survey bias and calibration bias. Fixing these is the single largest lift to end-to-end credibility. |
| High | Track 4 (Econometrics under dependence), Track 6 (Distributional counterfactuals), Track 12 (Network peer effects) | Each opens a class of queries currently answered with silently invalid estimators. They also unlock Causal Track 9 (topology) and Causal Track 11 (recoverability) integration. |
| High | Track 7 (Welfare & MCDA under uncertainty), Track 8 (Optimization under uncertainty) | Decision-layer correctness. A policy recommendation that ignores GE feedback, weight sensitivity, or distributional ambiguity is not a recommendation, it is a guess with formatting. |
| Medium | Track 2 (ML + representation learning), Track 10 (SBI + ABM), Track 13 (Spatial MAUP) | High moat depth, but either assumption-heavy (T10) or dependent on causal or representation theory (T2, T13). |
| Medium | Track 9 (Mechanism design), Track 14 (Sensitivity part) | High policy value when enabled but lower breadth across existing usage. |

#### 1.5.1. Priority among cross-cutting Part II tracks

| Priority | Tracks | Reason |
|----------|--------|--------|
| Highest | Track 15 (Advisor calibration), Track 16 (Backend determinism), Track 18 (Uncertainty composition) | These three run under every production call. Without them, the rest of the agenda produces correct artifacts that the engine still cannot select, reproduce, or chain. |
| Highest | Track 19 (Calibration subsystem), Track 23 (Benchmark infrastructure) | Calibration is the bottleneck for every identification argument; benchmarks are the only hold-out signal admissible into the six-judge promotion stack. |
| High | Track 17 (Cost/energy/budget), Track 22 (DP + federated + synthetic) | Compute-budget discipline and privacy are non-optional in government deployment; both are under-specified in the current contract set. |
| High | Track 20 (Streaming/online), Track 21 (Verified numerics / PPL), Track 24 (LLM lifecycle) | Each is high-moat infrastructure that amplifies every family but can be deferred until the upstream contracts are in place. |

#### 1.5.2. Priority among Part III new-family tracks

| Priority | Tracks | Reason |
|----------|--------|--------|
| Highest | Track 27 (RL/OPE + adaptive experiments), Track 29 (Evidence synthesis) | Adaptive experimentation and evidence synthesis are the two capabilities a decision-support engine cannot skip without ceding to external tools. |
| Highest | Track 25 (Text/regulatory NLP) | Regulatory text is the single largest unstructured input to policy workflows and today has only a frontier-stub wrapper with no grounding. |
| High | Track 28 (Structural macro), Track 30 (Matching markets), Track 34 (Extreme-value / stress testing) | Each closes a major policy-instrument gap (fiscal macro, assignment policy, tail risk) with well-developed external theory. |
| High | Track 26 (Earth-observation), Track 33 (Anomaly/fraud detection) | High policy value for field-ready outcome measurement and administrative integrity; each depends on cross-cutting Part II scaffolding. |
| Medium | Track 31 (Point processes), Track 32 (FDA/TDA), Track 35 (Agent-sim VFI) | High moat depth but narrower immediate footprint. |

---

# Part 0 — End-to-End Phased Execution Plan {#part-0-phased-execution}

This part is the **operational spine** of the agenda. Every research task in
Parts I–IV is scheduled into one of eleven end-to-end phases. Inside each
phase, 12–16 research problems run **maximally in parallel**; between phases
the order is **strictly sequential** because each phase's integration
deliverables are the input preconditions for the next.

The logic of the plan is exactly the one sketched in §16.3 ("Dependency
chains that affect production integration"): follow the production-integration
lanes — *honest uncertainty → government data → identification → decision
layer → dynamics → validation → streaming → privacy/verification → new
families → macro/specialised → meta-evaluation* — and convert each lane's
dependencies into a phase boundary.

**How to read a phase.** Each phase declares:

1. **Thesis** — one-sentence statement of what the phase achieves end-to-end.
2. **Why this phase runs here** — the dependency that forces its position.
3. **Parallel research problems** — 12–16 tasks that can be staffed
   simultaneously (each problem is a link back to its full specification in
   Parts I–IV).
4. **Integration deliverables** — the contracts, fields, and certificates
   that land in code when the phase closes.
5. **Phase gate** — the machine-checkable condition that must hold before
   the next phase is allowed to begin integration.
6. **What the phase enables downstream** — the later phases that unblock.

**Counting rule.** Each problem is listed in exactly one phase, so a problem
number (P3.07 = seventh parallel task in Phase 3) is a unique handle. The
problem's full specification (*what the problem is / why it cannot be
implemented without research / sufficient result / deliverable form*) lives
in its home track section in Part I, II, III, or IV. The phase row is the
operational pointer.

**Total accounting.** 11 phases × ≈13 parallel tasks ≈ 162 research items,
matching the sum of Part I (74) + Part II (42) + Part III (46) plus Part IV
extension bundles.

---

## Phase 0 — Foundations: Typed UQ Contracts + Runtime Substrate {#phase-0}

**Thesis.** Nothing in later phases can be honest until (a) every posterior
declares its own truthfulness tier, (b) forecast uncertainty exists as a
typed contract, (c) the advisor can route by tier, (d) backend tolerance
budgets and bit-level replay are machine-checkable, (e) an envelope algebra
exists for composed uncertainty, and (f) at least one validated-numerics
kernel and one synthetic benchmark world are online. Phase 0 closes all of
these in parallel.

**Why this phase runs here.** Every subsequent phase writes into one of
these typed surfaces; if they do not exist, downstream research produces
artifacts with no landing zone in the engine.

**Parallel research problems (12 concurrent):**

- `P0.01` **Track 1.1** — truthfulness tiering for approximate posteriors → [§2.1](#2-research-track-1)
- `P0.02` **Track 1.2** — deterministic HMC/NUTS backend envelope → [§2.2](#2-research-track-1)
- `P0.03` **Track 3.1** — forecast-uncertainty contract + calibrated interval estimators → [§4.1](#4-research-track-3)
- `P0.04` **Track 14.1** — formal statistical testing for metric comparisons → [§15.1](#15-research-track-14)
- `P0.05` **Track 14.2** — calibration diagnostics for probabilistic predictions → [§15.2](#15-research-track-14)
- `P0.06` **Track 15.1** — calibrated regret bounds for advisor rankings → [§16.1](#16-research-track-15)
- `P0.07` **Track 15.2** — truthfulness-tier consistency across advisor/method outputs → [§16.2](#16-research-track-15)
- `P0.08` **Track 16.1** — tolerance-budget derivation across backend combinations → [§17.1](#17-research-track-16)
- `P0.09` **Track 16.4** — cross-backend numerical equivalence as a certificate → [§17.4](#17-research-track-16)
- `P0.10` **Track 18.1** — envelope algebra for composed methods → [§19.1](#19-research-track-18)
- `P0.11` **Track 21.1** — validated numerics for critical policy computations → [§22.1](#22-research-track-21)
- `P0.12` **Track 23.1** — ground-truth synthetic worlds (seed benchmark infra) → [§24.1](#24-research-track-23)

**Integration deliverables (code-side landing zone):**

- `PosteriorResult.truthfulness_tier` field live; approximate methods self-tier.
- `ForecastingUncertaintyBundle` contract shipped with
  `prediction_interval`, `fan_chart`, `posterior_predictive_ref`,
  `coverage_diagnostic`, `horizon_policy`.
- `UncertaintyEnvelope.composition_provenance` recorded on every chained method.
- `MethodAdvisorResult.calibrated_regret_certificate` populated per route.
- `RuntimeFingerprint.observed_tolerance_budget` machine-checkable.
- `CrossBackendEquivalenceCertificate` emitted when backends reconcile.
- `ValidatedBoundCertificate` reachable from critical-path estimators.
- `SyntheticWorldDGP` spec + first calibrated world registered in benchmark harness.

**Phase gate.** A Phase-1 track may not begin integration work until:
(1) typed UQ object exists for its family; (2) `RuntimeFingerprint` reports
a non-null tolerance budget; (3) at least one synthetic world is usable for
benchmark proxies; (4) the advisor returns a truthfulness tier that matches
the method's self-declared tier.

**Enables downstream.** Every subsequent phase: without typed UQ the
downstream artifacts have no destination; without the envelope algebra they
cannot compose; without determinism budgets they cannot replay.

---

## Phase 1 — Government Data Lane + Dependence Primitive {#phase-1}

**Thesis.** Every policy pipeline ingests survey, administrative, and
microsim inputs. If these silently inherit bias (design-weighted
missingness, MNAR mechanisms, ignored cross-unit dependence), every
downstream identification and decision is fraudulent. Phase 1 produces a
single `SurveyQualityCertificate`, a single `MicrosimCalibrationReport`,
and one shared dependence-diagnostic primitive that serves econometrics,
SAE, and spatial in one pass.

**Why this phase runs here.** Consumes Phase-0's typed UQ contract. Its
outputs gate Phases 2 (identification), 3 (decision layer), and 4 (dynamic
microsim). Until the certificate lands, downstream refusal-modes have no
trigger.

**Parallel research problems (13 concurrent):**

- `P1.01` **Track 4.2** — dynamic panel asymptotics under cross-sectional dependence → [§5.2](#5-research-track-4)
- `P1.02` **Track 4.3** — semiparametric efficiency bounds for complex-survey estimators → [§5.3](#5-research-track-4)
- `P1.03` **Track 5.1** — double-robust estimation under design + informative missingness → [§6.1](#6-research-track-5)
- `P1.04` **Track 5.2** — small-area estimation under cross-area dependence → [§6.2](#6-research-track-5)
- `P1.05` **Track 5.3** — calibration under measurement error in auxiliary variables → [§6.3](#6-research-track-5)
- `P1.06` **Track 5.4** — MNAR taxonomy for administrative missingness → [§6.4](#6-research-track-5)
- `P1.07` **Track 5.5** — raking / IPF positivity diagnostics → [§6.5](#6-research-track-5)
- `P1.08` **Track 11.1** — behavioral-elasticity identifiability from cross-sectional microdata → [§12.1](#12-research-track-11)
- `P1.09` **Track 11.2** — nonlinear calibration and generalized moment matching → [§12.2](#12-research-track-11)
- `P1.10` **Track 11.4** — MNAR sensitivity for income imputation → [§12.4](#12-research-track-11)
- `P1.11` **Track 13.2** — spatial confounding and proximal spatial identification → [§14.2](#14-research-track-13)
- `P1.12` **IV.T5.6** — adaptive / responsive survey design → [Part IV — Survey extensions](#37-part-iv-extensions)
- `P1.13` **IV.T11.6** — static aging with demographic consistency → [Part IV — Microsim extensions](#37-part-iv-extensions)

**Integration deliverables.**

- `SurveyQualityCertificate` contract shipped; every government-origin
  dataset is annotated with a pass/fail verdict and a sensitivity envelope.
- `MicrosimCalibrationReport` contract shipped; microsim preflight refuses
  to run when calibration fails identifiability.
- Shared `DependenceStructure` diagnostic primitive consumed by
  econometric, SAE, and spatial estimators (Track 4.2 × Track 5.2 × Track
  13.2 compound — see §16.3 "DEPENDENCE PRIMITIVE LANE").
- `MobilityReport` preliminary shell registered for Phase 2 consumers.
- `EconometricResult.dependence_ref`, `SpatialResult.dependence_ref`,
  `SAEResult.dependence_ref` fields populated from the shared primitive.

**Phase gate.** No identification work in Phase 2 may proceed until the
`SurveyQualityCertificate` emits a non-null verdict on at least three
flagship government datasets; the dependence primitive has three calibrated
regimes covering panel, areal, and network-adjacent data.

**Enables downstream.** Phase 2 identification consumes survey certificate
+ dependence primitive; Phase 3 welfare weights inherit microsim
calibration validity; Phase 4 dynamic microsim consumes adaptive-design
estimator.

---

## Phase 2 — Identification Frontier: Network, Spatial, Econometrics, Distributional {#phase-2}

**Thesis.** With clean survey inputs and a shared dependence primitive,
open the identification problems that were previously unanswerable:
high-dimensional IV, sharp distributional bounds, Manski reflection,
strategic formation, ERGM/SBM stratification, network partial observability,
MAUP aggregation invariance, spatial interference. Each produces an
identification certificate that can be machine-checked against a Phase-0
synthetic world.

**Why this phase runs here.** Phase 1 delivered the data-quality substrate;
Phase 0 delivered typed UQ and synthetic worlds. This is the first phase
in which **causal/structural identification certificates** can be minted
with honest coverage.

**Parallel research problems (14 concurrent):**

- `P2.01` **Track 4.1** — post-selection inference for high-dimensional IV → [§5.1](#5-research-track-4)
- `P2.02` **Track 4.4** — threshold and kink models with state-dependent thresholds → [§5.4](#5-research-track-4)
- `P2.03` **Track 4.5** — heterogeneous and nonstationary GARCH for policy risk → [§5.5](#5-research-track-4)
- `P2.04` **Track 6.1** — sharp bounds on counterfactual distributions under partial identification → [§7.1](#7-research-track-6)
- `P2.05` **Track 6.2** — mobility estimation under panel attrition → [§7.2](#7-research-track-6)
- `P2.06` **Track 6.3** — multidimensional poverty with ordinal dimensions → [§7.3](#7-research-track-6)
- `P2.07` **Track 12.1** — Manski reflection-problem identification → [§13.1](#13-research-track-12)
- `P2.08` **Track 12.2** — strategic network formation → [§13.2](#13-research-track-12)
- `P2.09` **Track 12.3** — ERGM and SBM causal stratification → [§13.3](#13-research-track-12)
- `P2.10` **Track 12.4** — network identification under partial observability → [§13.4](#13-research-track-12)
- `P2.11` **Track 12.6** — network embedding fidelity for causal inference → [§13.6](#13-research-track-12)
- `P2.12` **Track 13.1** — aggregation-invariant spatial effects (MAUP) → [§14.1](#14-research-track-13)
- `P2.13` **Track 13.3** — spatial / areal interference identification → [§14.3](#14-research-track-13)
- `P2.14` **Track 13.6** — small-area spatial smoothing under causal constraints → [§14.6](#14-research-track-13)

**Integration deliverables.**

- `EconometricResult.post_selection_ci`, `threshold_state_field`,
  `nonstationary_volatility` fields.
- `DistributionalBoundsBundle` with partial-identification lower/upper envelopes.
- `NetworkResult.peer_effect_decomposition`,
  `NetworkResult.formation_diagnostic`,
  `NetworkResult.embedding_fidelity_certificate`.
- `SpatialResult.maup_invariance_certificate` and
  `InterferenceCertificate` (spatial instance, shared schema with causal Track 9).
- `MobilityReport` fully populated (consumed by Phase 3 welfare).

**Phase gate.** Every certificate in this phase's deliverable list must
verify on a Phase-0 synthetic world and pass the six-judge stack verdict;
no family method may ship into `PROOF_ONLY → ENGINEER_READY` transition
without a passing certificate.

**Enables downstream.** Phase 3 welfare + optimisation consume identified
effects with partial-identification envelopes rather than point estimates;
Phase 4 temporal causality inherits network/spatial identification.

---

## Phase 3 — Decision Layer: Welfare, Optimization, Mechanism {#phase-3}

**Thesis.** Identification produces credible effects; the decision layer
converts them into recommendations **with refusal modes**. After Phase 3
every recommendation flowing through the engine carries (a) a
`WelfareBundle`, (b) an `OptimizationResult.ambiguity_certificate`, and
(c) an `IncentiveCompatibilityCertificate` wherever mechanism design
applies. No bare scalar leaves the engine.

**Why this phase runs here.** Consumes Phase 2 identification certificates
and Phase 1 fiscal microsim calibration. Must precede Phase 4 because
dynamic forecasting + fiscal feedback depend on a static welfare contract
that knows how to compose ambiguity.

**Parallel research problems (14 concurrent):**

- `P3.01` **Track 6.4** — decomposition of inequality under endogenous group composition → [§7.4](#7-research-track-6)
- `P3.02` **Track 7.1** — welfare aggregation under general-equilibrium uncertainty → [§8.1](#8-research-track-7)
- `P3.03` **Track 7.2** — state-dependent social welfare weights → [§8.2](#8-research-track-7)
- `P3.04` **Track 7.4** — MCDA consensus under preference disagreement → [§8.4](#8-research-track-7)
- `P3.05` **Track 7.5** — joint behavioral-fiscal incidence with identifiable channels → [§8.5](#8-research-track-7)
- `P3.06` **Track 8.1** — stochastic programming under distributional ambiguity → [§9.1](#9-research-track-8)
- `P3.07` **Track 8.2** — bilevel optimization with nonconvex follower → [§9.2](#9-research-track-8)
- `P3.08` **Track 8.3** — robust-set adequacy and deadweight-conservatism tradeoff → [§9.3](#9-research-track-8)
- `P3.09` **Track 8.5** — inverse optimization for behavioral calibration → [§9.5](#9-research-track-8)
- `P3.10` **Track 9.1** — IC/IR verification as a machine-checkable certificate → [§10.1](#10-research-track-9)
- `P3.11` **Track 9.2** — Bayesian mechanism design under private types → [§10.2](#10-research-track-9)
- `P3.12` **Track 9.3** — auction and revenue-equivalence under reserve-price uncertainty → [§10.3](#10-research-track-9)
- `P3.13` **Track 9.5** — welfare-loss bounds versus first-best → [§10.5](#10-research-track-9)
- `P3.14` **Track 11.5** — fiscal-feedback-consistent behavioral response → [§12.5](#12-research-track-11)

**Integration deliverables.**

- `WelfareBundle` contract shipped with GE-uncertainty envelope and
  state-dependent weight schedule.
- `OptimizationResult.ambiguity_certificate` populated per stochastic plan.
- `IncentiveCompatibilityCertificate` + `MechanismWelfareLossBound`
  produced by every mechanism family.
- `MicrosimResult.fiscal_feedback_ref` links behavioural response to
  optimisation under DRO.
- Refusal-mode hook: any query returning a `WelfareBundle` with null
  ambiguity certificate or null IC certificate is blocked from the analyst
  workflow (contamination rule §17.4).

**Phase gate.** The decision layer must demonstrate on a synthetic policy
world that **every** recommendation flow terminates with all three
certificates; the advisor refuses when any is null.

**Enables downstream.** Phase 4 dynamic forecasts feed into `WelfareBundle`
with regime status; Phase 8 RL/adaptive experimentation reuses IC
certificate + DRO primitive; Phase 9 macro stress tests compose
`WorstCaseFiscalScenarioCertificate` on top of the DRO primitive.

---

## Phase 4 — Dynamics, Forecasting, Agent-Based Simulation {#phase-4}

**Thesis.** Static estimates do not survive policies with time structure
(multi-year budgets, regime shifts, endogenous feedback). Phase 4
introduces regime-aware forecasting with calibrated intervals, identified
heterogeneous-agent ABMs, coupled discrete-event/agent dynamics, and
temporal/space-time causal inference.

**Why this phase runs here.** Consumes Phase-0 UQ contract + Phase-2
identification + Phase-3 fiscal-feedback primitive. Must precede Phase 5
drift detection because drift semantics depend on the regime-switching
baseline.

**Parallel research problems (14 concurrent):**

- `P4.01` **Track 1.5** — simulation-based inference for intractable policy models → [§2.5](#2-research-track-1)
- `P4.02` **Track 3.2** — hierarchical and grouped forecast reconciliation → [§4.2](#4-research-track-3)
- `P4.03` **Track 3.3** — nonstationarity, regime-switching, and structural-break forecasting → [§4.3](#4-research-track-3)
- `P4.04` **Track 3.4** — neural and hybrid forecasters with trust-region UQ → [§4.4](#4-research-track-3)
- `P4.05` **Track 3.5** — forecast-as-treatment semantics in continuous-time policy → [§4.5](#4-research-track-3)
- `P4.06` **Track 6.5** — long-horizon mobility under latent heterogeneity → [§7.5](#7-research-track-6)
- `P4.07` **Track 7.3** — equilibrium existence and multiplicity under aggregate shocks → [§8.3](#8-research-track-7)
- `P4.08` **Track 10.1** — identifiability of heterogeneous-agent ABMs from aggregate moments → [§11.1](#11-research-track-10)
- `P4.09` **Track 10.2** — bifurcation and attractor analysis for dynamics models → [§11.2](#11-research-track-10)
- `P4.10` **Track 10.3** — simulation-based inference for expensive simulators → [§11.3](#11-research-track-10)
- `P4.11` **Track 10.4** — coupling discrete-event and agent-based dynamics → [§11.4](#11-research-track-10)
- `P4.12` **Track 11.3** — dynamic microsim validation against longitudinal data → [§12.3](#12-research-track-11)
- `P4.13` **Track 12.5** — temporal and dynamic graph causality → [§13.5](#13-research-track-12)
- `P4.14` **Track 13.5** — space-time dynamical causal inference → [§14.5](#14-research-track-13)

**Integration deliverables.**

- `RegimeShiftForecastBundle` contract shipped; forecasts beyond horizon 12
  refuse unless regime status is `CALIBRATED`.
- `ForecastingUncertaintyBundle.horizon_policy` populated with per-horizon
  coverage verdicts.
- `ABMResult.identifiability_certificate`, `ABMResult.bifurcation_report`.
- `DynamicMicrosimValidationReport` integrated with `MicrosimCalibrationReport`.
- `TemporalGraphCausalCertificate`, `SpaceTimeCausalCertificate` — shared
  schema with causal-agenda Track 3.4 (DSCM).
- Equilibrium-multiplicity annotation feeds Phase-3 `WelfareBundle`.

**Phase gate.** Every multi-period policy query runs through the
regime-aware pipeline; the engine refuses long-horizon forecasts when
regime status is `UNKNOWN` or `DRIFTING`. Dynamic microsim refuses when
validation report is red.

**Enables downstream.** Phase 5 drift detection, Phase 8 RL/OPE and
adaptive RCTs, Phase 9 nowcasting + DSGE regime-break detection, Phase 10
VFI uncertainty propagation.

---

## Phase 5 — Validation, Calibration Deepening, Explanation, Advisor Completion {#phase-5}

**Thesis.** Phases 0–4 produced artifacts; Phase 5 closes the diagnostic
loop on every one of them. Prior robustness, multimodality, conditional
coverage for deep models, distribution-shift, explanation infidelity,
fairness, sensitivity-of-sensitivity, drift, cross-method consensus,
cost-value dispatch — all land here. By end of Phase 5, the six-judge
stack runs on every artifact as a normal preflight.

**Why this phase runs here.** Consumes outputs from Phases 0–4 and feeds
Phases 6–11 with the full `ValidationReport` + `SensitivityAnalysisBundle`
machinery.

**Parallel research problems (12 concurrent):**

- `P5.01` **Track 1.3** — prior robustness and prior-predictive checks as gates → [§2.3](#2-research-track-1)
- `P5.02` **Track 1.4** — multimodality and posterior geometry detection → [§2.4](#2-research-track-1)
- `P5.03` **Track 2.1** — uncertainty quantification for deep tabular and graph models → [§3.1](#3-research-track-2)
- `P5.04` **Track 2.2** — distribution-shift detection and covariate shift diagnostics → [§3.2](#3-research-track-2)
- `P5.05` **Track 2.3** — model explanation with bounded infidelity → [§3.3](#3-research-track-2)
- `P5.06` **Track 14.3** — fairness auditing with causal semantics → [§15.3](#15-research-track-14)
- `P5.07` **Track 14.4** — sensitivity with dependent and correlated inputs → [§15.4](#15-research-track-14)
- `P5.08` **Track 14.5** — quantile and distributional sensitivity indices → [§15.5](#15-research-track-14)
- `P5.09` **Track 14.6** — sensitivity of the sensitivity — uncertainty on indices → [§15.6](#15-research-track-14)
- `P5.10` **Track 14.7** — drift and performance-degradation detection → [§15.7](#15-research-track-14)
- `P5.11` **Track 15.3** — cross-method consistency diagnostics under disagreement → [§16.3](#16-research-track-15)
- `P5.12` **Track 15.4** — cost-value-optimal method selection → [§16.4](#16-research-track-15)

**Integration deliverables.**

- `PosteriorResult.prior_sensitivity` + `PosteriorResult.multimodality_status` fields.
- `PredictionIntervalResult.conditional_coverage_diagnostic`.
- `ShiftDiagnosticReport` contract ingested by any `PredictionResult` consumer.
- `ExplanationBundle` contract with bounded-infidelity envelope and cross-method disagreement.
- `ValidationReport` + `SensitivityAnalysisBundle` fully populated.
- `MethodAdvisorResult.cross_method_consensus` gates every recommendation.
- Six-judge stack (structural, statistical, robustness, governance,
  reproducibility, compute) live on every artifact.

**Phase gate.** No artifact enters the analyst workflow without a
`ValidationReport` verdict and advisor cross-method consensus above
threshold. Drift detection downgrades readiness automatically.

**Enables downstream.** Phase 6 streaming inherits drift diagnostics;
Phases 7–9 every shipped artifact runs through the six-judge stack.

---

## Phase 6 — Streaming, Online, Runtime Reliability, Calibration Subsystem {#phase-6}

**Thesis.** Phases 0–5 produced a static pipeline; Phase 6 extends it to
streaming/online settings and closes runtime reliability gaps — circuit-
breaker recovery semantics, deterministic execution under non-associative
reductions, cost-uncertainty-aware plan selection, adaptive importance
sampling, coherent risk composition, identifiability-constrained
calibration, measurement-error-aware calibration, bounded-memory
estimators, rolling-CV streaming validation.

**Why this phase runs here.** Consumes Phase-0 determinism substrate +
Phase-5 drift diagnostics. Must precede Phase 7 privacy/federation work
because federated estimation and DP accountants are streaming-native.

**Parallel research problems (15 concurrent):**

- `P6.01` **Track 15.5** — human-in-the-loop advisor with structured overrides → [§16.5](#16-research-track-15)
- `P6.02` **Track 16.2** — deterministic recovery semantics under circuit-breaker trips → [§17.2](#17-research-track-16)
- `P6.03` **Track 16.3** — deterministic distributed execution under non-associative reductions → [§17.3](#17-research-track-16)
- `P6.04` **Track 17.1** — uncertainty-aware cost estimation → [§18.1](#18-research-track-17)
- `P6.05` **Track 17.3** — precision-budget tradeoffs with error bounds → [§18.3](#18-research-track-17)
- `P6.06` **Track 17.4** — robust optimization of plan selection under cost uncertainty → [§18.4](#18-research-track-17)
- `P6.07` **Track 18.2** — delta vs Monte Carlo selection under policy loss → [§19.2](#19-research-track-18)
- `P6.08` **Track 18.3** — importance sampling and adaptive allocation for UQ → [§19.3](#19-research-track-18)
- `P6.09` **Track 18.4** — coherent risk measures for composed envelopes → [§19.4](#19-research-track-18)
- `P6.10` **Track 19.1** — identifiability-constrained calibration → [§20.1](#20-research-track-19)
- `P6.11` **Track 19.2** — multi-start local-minima characterization → [§20.2](#20-research-track-19)
- `P6.12` **Track 19.3** — target-alignment under missing data and index mismatch → [§20.3](#20-research-track-19)
- `P6.13` **Track 19.4** — measurement-error-aware calibration → [§20.4](#20-research-track-19)
- `P6.14` **Track 20.1** — sequential Bayesian updating with coverage → [§21.1](#21-research-track-20)
- `P6.15` **Track 20.2** — bounded-memory estimators for administrative-scale data → [§21.2](#21-research-track-20)
- `P6.16` **Track 20.3** — online calibration monitoring and early-warning → [§21.3](#21-research-track-20)
- `P6.17` **Track 20.4** — streaming validation and rolling CV → [§21.4](#21-research-track-20)

**Integration deliverables.**

- `CalibrationResult.identifiability_status` +
  `CalibrationResult.measurement_model_ref`.
- `StreamingStateCertificate` bounds memory + rolling coverage.
- `CoherentRiskReport` (CVaR / ES envelope) on composed pipelines.
- `CostEstimate.distribution_ref` + `PrecisionModeBound` fields.
- Circuit-breaker audit log with deterministic recovery plan per trip.
- Human-in-the-loop advisor override protocol (rate-limited, audited).

**Phase gate.** No streaming pipeline ships without a
`StreamingStateCertificate`; every circuit-breaker trip emits a recovery
plan that reproduces bit-identical output on replay; advisor's cost-aware
plan selection runs under cost uncertainty without collapsing tier.

**Enables downstream.** Phase 7 privacy/federation estimators are natively
streaming; Phase 8 adaptive experimentation inherits rolling CV; Phase 9
nowcasting uses bounded-memory estimators.

---

## Phase 7 — Privacy, Federation, Verified Numerics, Benchmark Infra, LLM Lifecycle {#phase-7}

**Thesis.** Cross-jurisdictional policy work is impossible without
measurable leakage bounds; sovereign-grade audit is impossible without
proof-carrying estimates; trustworthy LLM-assisted research is impossible
without machine-verifiable theorem drafts and hallucination detection.
Phase 7 closes all three lanes jointly.

**Why this phase runs here.** Consumes Phase-0 validated numerics seed +
Phase-6 streaming/calibration substrate. Must precede Phase 8 new-family
SOTA because new families (NLP, EO, RL) rely on hidden holdouts,
adversarial case registries, DP budgets, and verified compilation.

**Parallel research problems (14 concurrent):**

- `P7.01` **Track 21.2** — PPL front-end with verified compilation → [§22.2](#22-research-track-21)
- `P7.02` **Track 21.3** — proof-carrying estimate certificates → [§22.3](#22-research-track-21)
- `P7.03` **Track 21.4** — bit-exact reproducibility across hardware → [§22.4](#22-research-track-21)
- `P7.04` **Track 22.1** — DP budget allocation across a pipeline → [§23.1](#23-research-track-22)
- `P7.05` **Track 22.2** — utility-preserving synthetic microdata → [§23.2](#23-research-track-22)
- `P7.06` **Track 22.3** — privacy-preserving record linkage → [§23.3](#23-research-track-22)
- `P7.07` **Track 22.4** — federated estimation with correctness → [§23.4](#23-research-track-22)
- `P7.08` **Track 23.2** — hidden-holdout infrastructure for the six-judge stack → [§24.2](#24-research-track-23)
- `P7.09` **Track 23.3** — per-regime leaderboards and stratified benchmarks → [§24.3](#24-research-track-23)
- `P7.10` **Track 23.4** — adversarial and pathological case library → [§24.4](#24-research-track-23)
- `P7.11` **Track 24.1** — LLM-assisted theorem drafting with machine verification → [§25.1](#25-research-track-24)
- `P7.12` **Track 24.2** — LLM-scaffolded estimator synthesis with unit-level verification → [§25.2](#25-research-track-24)
- `P7.13` **Track 24.3** — LLM-assisted literature synthesis with provenance → [§25.3](#25-research-track-24)
- `P7.14` **Track 24.4** — LLM hallucination detection for policy-text reasoning → [§25.4](#25-research-track-24)

**Integration deliverables.**

- `PrivacyBudgetCertificate`, `SyntheticDatasetCertificate`,
  `FederatedEstimatorCorrectnessCertificate`.
- `VerifiedLoweringCertificate` (PPL) +
  `MethodResult.verification_certificate` field.
- `SealedHoldoutProtocol` + `RegimeLeaderboardEntry` +
  `PathologicalCaseRegistry` live in benchmark harness.
- `TheoremVerificationCertificate`, `LiteratureSynthesisReport`,
  `HallucinationDetectionCertificate`.
- Six-judge stack reads hidden holdout and adversarial registry as normal
  inputs; graduation requires a holdout verdict (§17.4 rule 4).

**Phase gate.** Every cross-jurisdictional query returns a
`PrivacyBudgetCertificate`; every critical computation returns a
verification certificate; no new-family stub ships until a Phase-7 proxy
verdict is in hand.

**Enables downstream.** Phase 8 new-family stubs can graduate; Phase 9
macro/evidence federation across sites; Phase 11 meta-evaluation has a
holdout + adversarial registry to audit against.

---

## Phase 8 — New-Family SOTA: Text, Earth-Observation, RL / Adaptive Experimentation {#phase-8}

**Thesis.** Contracts (Phase 0) + substrate (Phase 6) + verifiers +
benchmark harness (Phase 7) are live. Phase 8 opens the three new
families the foundry does not yet ship: regulatory NLP with citation
correctness, remote-sensing + multimodal geospatial with bias-correction
certificates, reinforcement-learning + adaptive experimentation with valid
post-experiment inference.

**Why this phase runs here.** Each new family requires typed UQ (Phase 0),
fairness-aware advisor (Phase 5), DP + holdout infrastructure (Phase 7).
Without all three, the new families would ship as un-auditable black
boxes.

**Parallel research problems (14 concurrent):**

- `P8.01` **Track 25.1** — regulatory information extraction with citation correctness → [§26.1](#26-research-track-25)
- `P8.02` **Track 25.2** — identified topic models for policy corpora → [§26.2](#26-research-track-25)
- `P8.03` **Track 25.3** — text-as-treatment and text-as-outcome with unbiased measurement → [§26.3](#26-research-track-25)
- `P8.04` **Track 25.4** — retrieval-augmented policy reasoning with calibrated citations → [§26.4](#26-research-track-25)
- `P8.05` **Track 25.5** — statutory and legal reasoning with proof certificates → [§26.5](#26-research-track-25)
- `P8.06` **Track 26.1** — remote-sensing proxies with bias-correction certificates → [§27.1](#27-research-track-26)
- `P8.07` **Track 26.2** — multimodal fusion (imagery + admin + text) → [§27.2](#27-research-track-26)
- `P8.08` **Track 26.3** — geographic privacy and aggregation-level protection → [§27.3](#27-research-track-26)
- `P8.09` **Track 26.4** — change-detection with causal semantics → [§27.4](#27-research-track-26)
- `P8.10` **Track 27.1** — off-policy evaluation under partial identification → [§28.1](#28-research-track-27)
- `P8.11` **Track 27.2** — contextual bandits with fairness and equity constraints → [§28.2](#28-research-track-27)
- `P8.12` **Track 27.3** — adaptive RCTs with valid post-experiment inference → [§28.3](#28-research-track-27)
- `P8.13` **Track 27.4** — safe RL with constraint-violation bounds → [§28.4](#28-research-track-27)
- `P8.14` **Track 27.5** — dynamic treatment regimes with partial observability → [§28.5](#28-research-track-27)

**Integration deliverables.**

- New catalog paths graduate from stub: `catalog/nlp/`,
  `catalog/earth_observation/`, `catalog/reinforcement/`
  (`ope/`, `bandits/`, `adaptive_trials/`).
- `TextExtractionBundle`, `RAGResponseCertificate`,
  `StatutoryReasoningCertificate`.
- `RemoteSensingProxyBundle`, `MultimodalIndicatorBundle`,
  `GeoPrivacyCertificate`.
- `OPEBoundsBundle`, `FairnessConstrainedBanditCertificate`,
  `AdaptiveTrialResult`, `SafeRLViolationBoundCertificate`.

**Phase gate.** No new-family catalog path graduates from `PROOF_ONLY`
until the track has at least one benchmark proxy verdict against a Phase-7
hidden holdout and one adversarial registry case.

**Enables downstream.** Phase 9 consumes OPE + bandit + macro-nowcasting
in a unified decision-time bundle; Phase 11 meta-evaluation audits the
new families.

---

## Phase 9 — Structural Macro, Evidence Synthesis, Matching Markets {#phase-9}

**Thesis.** Sovereign-level policy work requires structural macro (HANK,
DSGE, real-time nowcasting), external-evidence synthesis with
transportability, and matching-market mechanisms. Each depends on prior-
phase substrate (calibration, IC certificates, temporal causality,
federation) to be live.

**Why this phase runs here.** Consumes Phase-3 IC + DRO, Phase-4 regime-
aware forecasting, Phase-6 calibration subsystem, Phase-7 federation +
LLM lifecycle. Opens the decision-time compound (Tracks 25 × 27 × 29) and
the fiscal-stress compound (Tracks 28 × 34 — with 34 to follow in Phase 10/11).

**Parallel research problems (14 concurrent):**

- `P9.01` **Track 17.2** — energy and carbon accounting as first-class cost → [§18.2](#18-research-track-17)
- `P9.02` **Track 22.5** — confidential computing integration and TEE attestation → [§23.5](#23-research-track-22)
- `P9.03` **Track 28.1** — HANK estimation with identification → [§29.1](#29-research-track-28)
- `P9.04` **Track 28.2** — DSGE with robust priors and structural-break detection → [§29.2](#29-research-track-28)
- `P9.05` **Track 28.3** — real-time nowcasting with mixed-frequency and ragged-edge data → [§29.3](#29-research-track-28)
- `P9.06` **Track 28.4** — structural model averaging with identification weights → [§29.4](#29-research-track-28)
- `P9.07` **Track 29.1** — Bayesian network meta-analysis with transportability → [§30.1](#30-research-track-29)
- `P9.08` **Track 29.2** — publication-bias correction with calibrated power → [§30.2](#30-research-track-29)
- `P9.09` **Track 29.3** — living-review infrastructure with automated evidence updating → [§30.3](#30-research-track-29)
- `P9.10` **Track 29.4** — meta-transportability across multiple sites → [§30.4](#30-research-track-29)
- `P9.11` **Track 30.1** — deferred-acceptance with strategy-proofness certificates → [§31.1](#31-research-track-30)
- `P9.12` **Track 30.2** — two-sided matching with preferences elicited from policy data → [§31.2](#31-research-track-30)
- `P9.13` **Track 30.3** — combinatorial auctions for public-sector allocation → [§31.3](#31-research-track-30)
- `P9.14` **Track 30.4** — platform regulation as mechanism design → [§31.4](#31-research-track-30)

**Integration deliverables.**

- `CarbonCertificate`, `TEEAttestationCertificate`.
- `HANKIdentificationCertificate`, `DSGEBreakReport`, `NowcastingBundle`,
  `StructuralModelAveragingWeights`.
- `NetworkMetaAnalysisBundle`, `PublicationBiasReadinessPolicy`,
  `LivingReviewUpdateRecord`, `MetaTransportabilityCertificate`.
- `AssignmentMechanismCertificate`, `CombinatorialAuctionWelfareLossBound`,
  `PlatformMechanismBundle`.
- `catalog/macro/`, `catalog/evidence_synthesis/`, `catalog/matching/`
  graduate from stub.

**Phase gate.** Sovereign stress-test pipeline composes macro +
`WelfareBundle` + DRO + IC; living-review updates flow into the decision
layer automatically; every assignment mechanism ships with a strategy-
proofness verdict.

**Enables downstream.** Phase 10 specialised families (point processes,
FDA/TDA, EVT tail, VFI) can plug into the decision-time compound; Phase 11
meta-evaluation audits the macro stack.

---

## Phase 10 — Specialised Families: Point Processes, FDA/TDA, Anomaly, EVT, VFI {#phase-10}

**Thesis.** Closes the remaining specialised family families that each
unlock a narrow but deep policy capability: Hawkes/competing-risks event
models, functional + topological data, administrative-integrity anomaly
detection, extreme-value tail risk, value-function iteration with
uncertainty propagation.

**Why this phase runs here.** Each family depends on multiple prior
phases: anomaly needs fairness + drift (Phase 5); VFI needs identified
dynamic games (Phase 4) + DRO (Phase 3); EVT needs scenario-coverage
framework (Phase 6 coherent risk) + GE welfare (Phase 3).

**Parallel research problems (15 concurrent):**

- `P10.01` **Track 8.4** — multi-level (three-plus) hierarchical optimization → [§9.4](#9-research-track-8)
- `P10.02` **Track 10.5** — mean-field convergence rates and finite-N correction → [§11.5](#11-research-track-10)
- `P10.03` **Track 9.4** — coupled mechanisms and correlated equilibrium → [§10.4](#10-research-track-9)
- `P10.04` **Track 31.1** — Hawkes and self-exciting processes for policy events → [§32.1](#32-research-track-31)
- `P10.05` **Track 31.2** — competing risks and recurrent events → [§32.2](#32-research-track-31)
- `P10.06` **Track 31.3** — marked point processes for spatial-temporal events → [§32.3](#32-research-track-31)
- `P10.07` **Track 31.4** — deep survival with calibrated intervals → [§32.4](#32-research-track-31)
- `P10.08` **Track 32.1** — functional data for longitudinal policy outcomes → [§33.1](#33-research-track-32)
- `P10.09` **Track 32.2** — persistent homology for policy data shape → [§33.2](#33-research-track-32)
- `P10.10` **Track 32.3** — manifold learning with causal faithfulness → [§33.3](#33-research-track-32)
- `P10.11` **Track 32.4** — geometric deep learning for administrative graphs → [§33.4](#33-research-track-32)
- `P10.12` **Track 33.1** — benefit-abuse detection with causal fairness → [§34.1](#34-research-track-33)
- `P10.13` **Track 33.2** — audit-sampling with detection bounds → [§34.2](#34-research-track-33)
- `P10.14` **Track 33.3** — drift-coupled anomaly detection → [§34.3](#34-research-track-33)
- `P10.15` **Track 34.1** — multivariate extreme-value theory for policy tails → [§35.1](#35-research-track-34)
- `P10.16` **Track 35.1** — VFI error bounds under policy-function iteration → [§36.1](#36-research-track-35)

**Integration deliverables.**

- `PointProcessResult`, `CompetingRisksResult`, `FunctionalResult`,
  `PersistenceDiagramResult`, `ManifoldFaithfulnessDiagnostic`.
- `FraudFairnessFrontierCertificate`, `AdaptiveAuditProtocol`,
  `DetectorUpdateRule`.
- `TailRiskBundle` (multivariate EVT variant).
- `ValueFunctionResult` + VFI uncertainty pipeline shell.
- `catalog/point_processes/`, `catalog/functional/`, `catalog/tda/`,
  `catalog/anomaly/`, `catalog/extreme_value/`,
  `foundry/agent_sim/` (VFI contract) graduate.

**Phase gate.** Each specialised family has at least one benchmark proxy
verdict against Phase-7 hidden holdouts; anomaly detection's fairness
frontier is non-empty; EVT tail bundle composes with Phase-3 `WelfareBundle`.

**Enables downstream.** Phase 11 meta-evaluation has specialised families
to audit; sovereign stress testing (Phase 9 + Phase 10 EVT) is
operational.

---

## Phase 11 — Cross-Family Extensions, Tail Closeout, Meta-Evaluation, Replication {#phase-11}

**Thesis.** Final phase. Closes remaining Part IV extensions (Bayesian
model selection, probabilistic forecasting, real options, fairness-aware
facility location, dynamic mechanisms, validated SDE, motif detection),
finishes EVT / VFI / anomaly / spatial tails, and audits the audit layer
itself (meta-evaluation of the six-judge stack, cross-toolchain
replication).

**Why this phase runs here.** Meta-evaluation (IV.T14.8) requires every
judge in the six-judge stack to be live; cross-toolchain replication
(IV.T14.9) requires bit-exact reproducibility (Phase 7) + validated
numerics (Phase 7) + determinism budget (Phase 0). Part IV extensions
that piggy-back on their home family can only land after the home track
has graduated.

**Parallel research problems (15 concurrent):**

- `P11.01` **Track 13.4** — geostatistical extremes under spatial dependence → [§14.4](#14-research-track-13)
- `P11.02` **Track 33.4** — whistleblower-safe reporting infrastructure → [§34.4](#34-research-track-33)
- `P11.03` **Track 34.2** — copula tail dependence for policy-relevant scenarios → [§35.2](#35-research-track-34)
- `P11.04` **Track 34.3** — scenario generation with coverage → [§35.3](#35-research-track-34)
- `P11.05` **Track 34.4** — worst-case fiscal scenarios under GE feedback → [§35.4](#35-research-track-34)
- `P11.06` **Track 35.2** — dynamic games with identification → [§36.2](#36-research-track-35)
- `P11.07` **Track 35.3** — uncertainty propagation through VFI chains → [§36.3](#36-research-track-35)
- `P11.08` **Track 35.4** — discrete-continuous choice estimation → [§36.4](#36-research-track-35)
- `P11.09` **IV.T1 bundle** — Bayesian model selection (T1.6) + Bayesian optimisation (T1.7) → [Part IV](#37-part-iv-extensions)
- `P11.10` **IV.T2 / IV.T3 bundle** — ordinal regression (T2.8) + probabilistic forecasting (T3.6) + forecast combination (T3.7) → [Part IV](#37-part-iv-extensions)
- `P11.11` **IV.T4 / IV.T6 bundle** — local-projection vs VAR (T4.6) + MHT corrections (T4.7) + top-coded wealth (T6.6) + group deflators (T6.7) → [Part IV](#37-part-iv-extensions)
- `P11.12` **IV.T7 / IV.T8 / IV.T9 bundle** — real options (T7.6) + multi-period welfare (T7.7) + integer programming for policy allocation (T8.6) + fairness-aware facility location (T8.7) + dynamic mechanism design (T9.6) → [Part IV](#37-part-iv-extensions)
- `P11.13` **IV.T10 / IV.T12 bundle** — validated SDE/ODE solvers (T10.6) + network motif detection (T12.7) → [Part IV](#37-part-iv-extensions)
- `P11.14` **IV.T14.8** — meta-evaluation (cross-family benchmarking of the six-judge stack itself) → [Part IV](#37-part-iv-extensions)
- `P11.15` **IV.T14.9** — replication across peer toolchains (R/Stata/Python) with tolerance library → [Part IV](#37-part-iv-extensions)

**Integration deliverables.**

- `ScenarioCoverageCertificate`, `WorstCaseFiscalScenarioCertificate`.
- `PosteriorResult.selection_diagnostic` (WAIC/LOO/stacking).
- `ForecastingUncertaintyBundle.quantile_curves` (distributional forecasts).
- `EconometricResult.mht_correction_applied`.
- `DistributionalBundle.group_deflator`.
- `OptimizationResult.fairness_frontier` (facility location).
- `DynamicMechanismBundle` (time-varying mechanisms with BIC).
- `ValidatedSDEResult` (shared schema with `ValidatedBoundCertificate`).
- `NetworkMotifCensus` estimator + CI.
- **Meta-evaluation protocol**: six-judge stack is benchmarked against
  hidden ground truth and assigned its own readiness tier.
- **Replication registry**: every shipped estimator has a cross-toolchain
  replication entry with a documented tolerance (coupled to Tracks 16, 21).

**Phase gate (final).** No estimator remains in the catalog without:
(i) a cross-toolchain replication entry, (ii) a six-judge verdict that
itself passes meta-evaluation, (iii) a scenario-coverage certificate
(where tail-relevant). The engine is complete.

**Enables downstream.** End of the agenda. From here the operational
loop is maintenance + kill-rule enforcement (§18.3) rather than new phase
initiation.

---

## Phase Summary and Operational Properties {#phase-summary}

**Serial-phase invariant.** Phase N → Phase N+1 is a hard ordering: all
Phase-N integration deliverables must land (contracts shipped, certificates
reachable, phase gate green) before Phase N+1 staff may begin **integration**
work. Research (theorem drafts, benchmark proxies) in later phases may
start earlier as `FrontierSketch` with `max_readiness = PROOF_ONLY` under
the contamination rule (§17.4), but may not alter production until its
home phase opens.

**In-phase parallelism.** All 12–16 problems inside a phase are
independent by construction: they either (a) touch disjoint contracts,
(b) share a primitive that one of them owns (e.g., the dependence
primitive in Phase 1), or (c) feed a single phase-level bundle from
different angles. A phase can therefore be staffed at its full task width
without contention.

**Phase-size calibration.** Each phase sits inside the 12–16 parallel-task
band — large enough to justify a dedicated cross-family research sprint,
small enough that a single integration review at the phase gate can cover
every deliverable.

**Problem coverage.**

| Phase | Parallel tasks | Lane affinity (§16.3) |
|-------|---------------:|-----------------------|
| Phase 0 — Foundations | 12 | HONEST UNCERTAINTY + CROSS-CUTTING INFRASTRUCTURE + AUDIT |
| Phase 1 — Government data + dependence primitive | 13 | GOVERNMENT DATA + DEPENDENCE PRIMITIVE |
| Phase 2 — Identification frontier | 14 | TOPOLOGY + Distributional extension |
| Phase 3 — Decision layer | 14 | DECISION LAYER |
| Phase 4 — Dynamics + forecasting + ABM | 14 | DYNAMICS |
| Phase 5 — Validation + calibration + advisor completion | 12 | HONEST UNCERTAINTY closure + AUDIT |
| Phase 6 — Streaming + reliability + calibration subsystem | 17 | CROSS-CUTTING INFRASTRUCTURE |
| Phase 7 — Privacy, verified numerics, benchmark, LLM | 14 | PRIVACY + FEDERATION + AUDIT |
| Phase 8 — New-family SOTA (text, EO, RL) | 14 | DECISION-TIME |
| Phase 9 — Structural macro, evidence, matching | 14 | DECISION-TIME + PRIVACY |
| Phase 10 — Specialised families (point / FDA / anomaly / EVT / VFI) | 16 | Complementary lanes |
| Phase 11 — Extensions + meta-eval + replication | 15 | AUDIT closeout |
| **Total** | **169** | — |

**Relation to priority scores (§18.2).** Highest-priority tracks (T1, T3,
T5, T11, T14, T15, T16, T18, T19, T23, T25, T27, T29) are front-loaded:
every one of them has at least one problem in Phase 0 or Phase 1.

**Relation to the dependency-chain lanes (§16.3).** Each lane is
*realised* by an ordered sequence of phases rather than a single phase.
Example: the `HONEST UNCERTAINTY LANE` (T1 tier + T3.1 + T14.2) opens in
Phase 0 and closes in Phase 5 when prior-robustness + multimodality +
conditional coverage + sensitivity-of-sensitivity all land. The
`AUDIT + REPRODUCIBILITY LANE` opens in Phase 0 (validated numerics,
synthetic worlds) and closes in Phase 11 (meta-evaluation + replication).

**Failure mode.** A Phase N track whose research deliverable is not in
hand by phase close blocks integration into Phase N+1 only for the
contracts it owns; siblings in Phase N whose deliverables *did* land
integrate normally, and the blocked track drops to `FrontierSketch`
status under §17.1 with a phase-over-budget flag.

---

# Parts I–IV — Detailed Problem Catalog (consumed by the Phase Plan) {#parts-catalog}

**Role of this section.** Everything below is the **reference catalog** of
research problems. It is organized by method family (Part I), cross-cutting
integration (Part II), dependency analysis (Part III), and extension tracks
(Part IV). Each numbered open problem here is referenced by one — and only
one — phase in [Part 0](#part-0-phased-execution) via its `P{phase}.{nn}`
scheduler ID. Read these tracks when you need:

- **Depth.** Full problem statement, sufficient-result criterion, and
  integration contract for a single research item.
- **Context.** Why a track exists within a method family, and how its
  problems relate to siblings in the same family.
- **Dependency reasoning.** The lane analysis in §16.3 that produced the
  phase ordering in Part 0.

**Do not read these parts linearly to execute work.** The execution spine
is Part 0. Use Parts I–IV as the drill-down when a phase lists a problem
by ID and you need the full specification.

---

## 2. Research Track 1 — Bayesian Inference and Scalable Posterior Computation {#2-research-track-1}

**Status in catalog**: `catalog/bayesian/` ships 19 production estimators
(GP regression, sparse GP, EP, SVGD, normalizing flows, BART, SBI via NPE/NLE/NRE,
Bayesian ARIMA/VAR, Bayesian linear/logistic/ridge, Gaussian mixtures, Dirichlet
process mixtures, loopy BP on factor graphs). The `UncertaintyEnvelope` contract
is in place. The problems below remain research-first.

> **Why this track matters**: the `PosteriorResult` contract carries credible
> intervals, but no field in the existing contracts records *truthfulness* —
> whether the posterior is exact, asymptotically exact, or an approximation
> whose coverage is unknown. Downstream consumers (policy welfare under
> parameter uncertainty, forecast intervals, robust optimization) treat every
> posterior as equivalent. This is the single largest silent-degradation risk
> in the non-causal stack.

### 2.1. Open problem: truthfulness tiering for approximate posteriors

**What the problem is**: EP, SVGD, variational, and normalizing-flow posteriors
produce distributions that look identical to HMC output at the contract level
(mean vector, credible interval, diagnostic blob). But their coverage
guarantees are fundamentally different: EP is typically overconfident in the
tails, mean-field VI underestimates correlation, normalizing flows depend on
architecture choice. Downstream consumers cannot tell the difference.

**Why it cannot be implemented without research**: the question is not "label
each method with a static tier" — that produces cosmetic metadata. The real
question is: under what conditions on the target posterior (smoothness,
dimensionality, tail behavior) does a given approximation preserve credible-
interval coverage to within a stated tolerance, and what diagnostic signals
are sufficient to detect violation of those conditions at runtime?

**Sufficient result**: (a) a truthfulness tier ladder (EXACT, ASYMPTOTIC,
APPROXIMATE_CALIBRATED, APPROXIMATE_UNCALIBRATED) with formal conditions for
membership per tier; (b) for each approximate method in the catalog, a
runtime diagnostic that can downgrade the tier when the posterior violates the
method's assumptions; (c) a coverage-calibration benchmark across at least three
policy-relevant posterior families (bimodal, heavy-tailed, high-dimensional
correlated).

**Deliverable form**: truthfulness ladder specification + per-method diagnostic
family + coverage benchmark + extension of `PosteriorResult` to carry a
`truthfulness_tier` field that is set by the method itself, not by static
metadata.

---

### 2.2. Open problem: production HMC/NUTS backend with determinism guarantees

**What the problem is**: the catalog currently lacks a production HMC/NUTS
backend. The Foundry Remediation Plan lists this as a T3 frontier item. The
research question is not "integrate PyMC" — that is engineering scope. The
research question is: under what conditions is an HMC/NUTS run reproducible
enough to meet `DeterminismTier.LIBRARY_DETERMINISTIC`, given that modern
samplers use parallel-chain adaptation, JIT-compiled gradients, and
floating-point nondeterminism on GPUs?

**Why it cannot be implemented without research**: PolicyOS's reproducibility
contract requires that a sampler run given the same inputs and seed produces
byte-identical output for replay and audit. Mainline HMC implementations do
not meet this bar without nontrivial work. Without a sampler whose determinism
is characterized, no Bayesian policy result can be independently verified.

**Sufficient result**: (a) a sampler specification that achieves reproducible
output under a defined hardware/software envelope (CPU-only, bit-for-bit
across same-architecture runs); (b) a degradation mode that detects when
hardware deviates from the envelope and drops to `STATISTICAL` determinism with
explicit warning; (c) diagnostics (R-hat, ESS, energy-bayes-fraction) enforced
as gates, not advisory fields.

**Deliverable form**: sampler contract + determinism envelope specification +
gate-enforced diagnostic thresholds + integration spec for `PosteriorResult`.

---

### 2.3. Open problem: prior robustness and prior-predictive checks as gates

**What the problem is**: all catalog Bayesian methods currently embed prior
choices in method defaults (Gaussian, HalfNormal, uninformative). Policy
inference is often prior-sensitive: small changes in tail-mass assumptions
shift posterior credible intervals by factors of two or more. No current
contract records prior sensitivity or enforces a prior-predictive check.

**Why it cannot be implemented without research**: prior robustness in the
policy setting is not a general statistical problem — it is a question about
which prior families produce predictive distributions that are compatible with
observed policy data. Automating this without producing false precision
requires a formal concept of "admissible prior class" per model family and
a calibration procedure that can reject priors whose predictive mass is
incompatible with observed histories.

**Sufficient result**: (a) formal definitions of admissible prior classes for
each major model family in the catalog (linear/logistic regression, BART, GP,
VAR); (b) a prior-predictive test statistic with calibrated Type I error under
model correctness; (c) a sensitivity measure that quantifies the half-width of
the posterior credible interval as a function of prior hyperparameter shift,
with a pass/fail threshold per readiness tier.

**Deliverable form**: admissible prior library + prior-predictive test +
sensitivity measure + integration spec for `PosteriorResult.prior_sensitivity`.

---

### 2.4. Open problem: multimodality and posterior geometry detection

**What the problem is**: all catalog methods except mixture models assume
unimodal posteriors implicitly (summary: mean + SD + quantiles). Multimodal
posteriors — common in hierarchical identification with weak data — reduce to
a single mean that can lie in a zero-density region. A policy recommendation
based on such a posterior is worse than one from an admitted ambiguity.

**Why it cannot be implemented without research**: multimodality detection
from samples is an active area. Existing tools (Dip test, Silverman test, KDE
density inspection) have low power in high dimensions. For the policy engine
to downgrade a posterior's readiness when multimodality is present, it needs
a test with characterized power for the dimensions used in practice (5–50
parameters), and a protocol for what to report when multimodality is detected
(bounds on each mode? mode-conditional policy? refusal?).

**Sufficient result**: (a) a multimodality test with power characterization for
5–50 dimensional posteriors sampled with HMC/NUTS or comparable; (b) a
specification of the downgrade behavior (readiness, reported summary) when
multimodality is detected; (c) a mode-conditional reporting format that can
carry multiple sub-posteriors under a single `PosteriorResult`.

**Deliverable form**: test procedure + power benchmark + reporting format +
integration spec for `PosteriorResult.multimodality_status`.

---

### 2.5. Open problem: simulation-based inference for intractable policy models

**What the problem is**: the three SBI methods in the catalog (NPE, NLE, NRE)
are production for well-behaved simulators. For policy simulators (tax-benefit
models, labor-market ABMs, fiscal-macro hybrids) the simulator is expensive,
high-dimensional, and frequently violates the "fixed parameter, stochastic
output" assumption (parameters themselves drift with calendar time, policy
regimes, administrative definitions). The research question is: under what
conditions is NPE/NLE/NRE statistically valid for such simulators, and what is
the minimum simulation budget required for calibrated posteriors?

**Why it cannot be implemented without research**: SBI's convergence rates are
known for IID simulators with smooth likelihoods. Policy simulators violate
both. Without a theory of SBI under regime-shifted simulators, the posterior
returned is a fit to an incorrect likelihood and the policy recommendation is
unsound.

**Sufficient result**: (a) identifiability conditions for SBI under simulators
with a declared regime-shift structure; (b) a simulation-budget lower bound
per target coverage; (c) a diagnostic for simulator misspecification that can
flag when the emulator cannot reach a neighborhood of the observed summary
statistics.

**Deliverable form**: identifiability conditions + budget lower bound +
misspecification diagnostic + integration spec for SBI method metadata and
`PosteriorResult.simulator_diagnostic_ref`.

---

## 3. Research Track 2 — Machine Learning, Representation Learning, and Foundation Models for Policy {#3-research-track-2}

**Status in catalog**: `catalog/ml/` ships 15 production estimators across
regression, clustering, decomposition, survival, and uncertainty calibration,
plus 4 frontier stubs (FT-Transformer, TabNet, GCN, masked autoencoder). Typed
contracts `PredictionResult`, `PredictionIntervalResult`, `ClusteringResult`,
`EmbeddingResult`, `SurvivalResult` are in place. The problems below remain
research-first.

### 3.1. Open problem: uncertainty quantification for deep tabular and graph models

**What the problem is**: conformal prediction is in the catalog but only for
classical regressors. Deep tabular models (FT-Transformer, TabNet) and graph
neural networks (GCN) are at Phase-6 frontier without any UQ wrapper. Direct
application of split conformal to these models often produces vacuous
intervals at policy-relevant confidence levels because the underlying score
distribution is heavy-tailed and nonstationary across the target covariate
space.

**Why it cannot be implemented without research**: the problem is not
algorithmic (the conformal wrapper itself is known) but statistical: which
conformal scheme (split, full, Mondrian, locally adaptive, weighted) preserves
marginal and conditional coverage for these model classes, at what sample size,
and under which distribution-shift regimes? No production system should wrap a
deep model with split conformal without verifying that conditional coverage
does not collapse in policy-relevant subgroups.

**Sufficient result**: (a) a coverage benchmark for at least three deep
tabular/graph models across three policy-relevant distribution regimes
(balanced, imbalanced, shifted); (b) a recommended conformal scheme per model
family with conditional-coverage guarantees; (c) a diagnostic that can flag
when the recommended scheme is violating its conditional-coverage assumptions.

**Deliverable form**: coverage benchmark + per-model-family scheme
specification + runtime diagnostic + integration spec for
`PredictionIntervalResult.conditional_coverage_diagnostic`.

---

### 3.2. Open problem: distribution-shift detection and covariate shift diagnostics

**What the problem is**: the foundry currently has no estimator for
detecting covariate or concept shift between training and deployment
distributions. Every regression/classification recommendation is returned as
if the deployment distribution is fixed. For administrative data that evolves
monthly (new benefit rules, new eligibility cohorts, new registry definitions)
this assumption is systematically wrong.

**Why it cannot be implemented without research**: shift detectors in the
literature (KS, MMD, density ratio, classifier two-sample test) each have
failure modes. For high-dimensional administrative data, the interaction
between type of shift (marginal, conditional, concept) and the detector's
operating characteristics is poorly understood. A naive detector with an
uncharacterized false-positive rate produces a wave of misleading alerts
that will be ignored within weeks.

**Sufficient result**: (a) a calibrated shift-detection ensemble with declared
operating characteristics (power per shift type, FP per no-shift regime) for
at least three policy-relevant data modalities (tabular administrative,
longitudinal panel, sparse survey); (b) a formal mapping from detector verdict
to downstream readiness downgrade; (c) a diagnostic that separates marginal
from concept shift and reports each with its own severity.

**Deliverable form**: ensemble detector + operating characteristic library +
shift-to-readiness mapping + new contract `ShiftDiagnosticReport` as an input
slot for any `PredictionResult` consumer.

---

### 3.3. Open problem: model explanation with bounded infidelity

**What the problem is**: no SHAP, LIME, or accumulated-local-effects
estimator currently ships. When policy analysts ask "which features drive
this prediction", the system has no answer. Adding a standard SHAP wrapper is
engineering scope, but *claiming* that the explanation is faithful to the
model's decision boundary — the claim analysts actually act on — is research
scope.

**Why it cannot be implemented without research**: explanation methods have
known infidelity modes (TreeSHAP disagrees with KernelSHAP on high-correlation
features; LIME is unstable under kernel bandwidth changes). A production
system must report infidelity as a bounded quantity, not as an opaque score.
Without formal infidelity bounds, explanations are decorative.

**Sufficient result**: (a) a formal infidelity measure per explanation method
with computable upper bounds under declared model-class assumptions; (b) a
test suite that quantifies disagreement across at least three explanation
methods on the same model, with disagreement reported as uncertainty; (c) a
redundancy-aware explanation format that does not hide correlated-feature
ambiguity behind a single attribution vector.

**Deliverable form**: infidelity measure + cross-method disagreement benchmark
+ `ExplanationBundle` contract + integration spec.

---

### 3.4. Open problem: multi-task learning and transfer across policy jurisdictions

**What the problem is**: policy problems are multi-jurisdictional: the same
structural model (e.g., EITC take-up) applies in dozens of states with partial
data sharing. Multi-task learning can in principle share strength across
jurisdictions. No catalog method supports this. Naïve pooling ignores
jurisdiction-specific shifts; full separation ignores structural similarity.

**Why it cannot be implemented without research**: multi-task learning has
active-research-level issues for policy data: (a) when is a shared
representation causally valid (as opposed to a predictive shortcut that
inherits jurisdiction-specific confounding)? (b) what falsification tests
distinguish genuinely shared structure from spurious transfer? Without this,
a multi-task ML method produces numbers that look like they generalize but
generalize only because both training and validation data share the same
biases.

**Sufficient result**: (a) formal conditions for shared-representation
validity under jurisdiction heterogeneity; (b) a falsification test that
distinguishes genuine transfer from shared bias; (c) a readiness policy that
downgrades transfer predictions whose falsification test is inconclusive.

**Deliverable form**: validity conditions + falsification test + `TransferDiagnostic`
attachment for `PredictionResult` + integration spec.

---

### 3.5. Open problem: foundation-model policy analysis with grounded calibration

**What the problem is**: the policy family's `foundation_model_policy_analysis`
frontier method uses sentence-transformer embeddings for policy-text similarity.
No current calibration links embedding similarity to realized policy outcomes.
The moat (if any) is unclear: embedding similarity is a linguistic property,
not a causal or predictive one.

**Why it cannot be implemented without research**: for a language-model-based
policy tool to be shipped above `PROOF_ONLY`, the system needs a formal link
between embedding-space distance and outcome-space distance. The research
question is: under what conditions does embedding similarity correlate with
outcome similarity (revenue impact, behavioral response, litigation risk),
and what is the regression-to-the-mean correction?

**Sufficient result**: (a) a calibration study linking embedding similarity
to outcome similarity on a holdout corpus of past policies with measured
outcomes; (b) a regression-to-the-mean correction; (c) a refusal policy for
queries outside the calibration envelope.

**Deliverable form**: calibration study + correction factor + envelope-refusal
spec + readiness cap enforcement for the foundation-model method.

---

## 4. Research Track 3 — Forecasting under Uncertainty, Hierarchies, and Nonstationarity {#4-research-track-3}

**Status in catalog**: `catalog/forecasting/` ships 7 production estimators
(ExpSmoothing, SeasonalNaive, MovingAverage, ARIMA, STL, DynamicRegression,
VAR). **The family has no typed uncertainty contract.** All methods currently
emit scalar point forecasts into a generic JSON result slot.

> **Why this track matters**: every forecast consumed by policy welfare,
> budget-impact analysis, or fiscal projection flows through this family. The
> absence of a `ForecastingUncertaintyBundle` contract is the single largest
> structural gap in the non-causal catalog — it forces every downstream to
> either fabricate intervals or silently assume point forecasts are correct.

### 4.1. Open problem: forecast-uncertainty contract and calibrated interval estimators

**What the problem is**: the catalog has no `ForecastingUncertaintyBundle`
contract that carries prediction intervals, fan charts, posterior predictive
distributions, and horizon-dependent coverage guarantees. A contract alone is
engineering scope; what is research-first is the question of which interval
construction method (parametric, bootstrap, conformal, Bayesian) preserves
marginal and horizon-conditional coverage for the seven catalog methods, and
under which regime.

**Why it cannot be implemented without research**: forecast intervals are
systematically under-covered at long horizons due to parameter uncertainty
and model misspecification. A contract that carries uncovered intervals is
worse than no contract. The research question is: per method in the catalog,
which interval construction yields calibrated coverage at horizons 1, 4, 12,
and 24 ahead under declared sample-size assumptions?

**Sufficient result**: (a) a coverage benchmark across the 7 catalog methods
at 4 horizons, 3 policy data regimes, with conformal/bootstrap/parametric
variants tested; (b) a per-method recommended interval construction; (c) a
runtime diagnostic that flags uncalibrated regimes.

**Deliverable form**: coverage benchmark + per-method recommendation +
runtime diagnostic + new `ForecastingUncertaintyBundle` contract
(prediction_interval, fan_chart, posterior_predictive_ref, coverage_diagnostic,
horizon_policy).

---

### 4.2. Open problem: hierarchical and grouped forecast reconciliation

**What the problem is**: policy forecasts are inherently hierarchical — total
revenue = Σ state revenue = ΣΣ program revenue. Catalog methods operate
per-series without reconciliation. Independent forecasts of the hierarchy
levels violate aggregation constraints. Classical reconciliation (bottom-up,
top-down, MinT, OLS-optimal) is known but has not been integrated with typed
uncertainty, and the research question is how reconciliation interacts with
the per-series intervals of Track 3.1.

**Why it cannot be implemented without research**: optimal reconciliation
under heterogeneous-uncertainty per-series intervals is not a solved problem.
Naïve MinT assumes Gaussian errors with full-rank covariance; policy data
series violate both. The research question is: under what structural conditions
does reconciliation tighten the uncertainty envelope without breaking
per-series coverage?

**Sufficient result**: (a) a reconciliation algorithm with coverage-preserving
guarantees under heterogeneous per-series uncertainty; (b) a fallback when the
algorithm's preconditions fail (reports per-series intervals + aggregation
gap); (c) an integration with `ForecastingUncertaintyBundle` carrying a
`reconciliation_certificate` field.

**Deliverable form**: algorithm + fallback mode + integration spec.

---

### 4.3. Open problem: nonstationarity, regime-switching, and structural-break forecasting

**What the problem is**: policy time series contain regime shifts (tax
reforms, benefit changes, crises). Catalog ARIMA/VAR methods assume
stationarity post-differencing, which does not hold across structural
breaks. Markov-switching and change-point forecasters are absent.

**Why it cannot be implemented without research**: regime-switching
identifiability with small regime counts is non-trivial; labels are latent,
break dates are unknown, and posterior over regime counts is often flat. The
research question is: under which conditions (sample size per regime, minimum
regime duration, prior on break count) can a regime-switching forecaster be
identified with calibrated coverage?

**Sufficient result**: identifiability conditions + calibration benchmark +
a `RegimeShiftForecastBundle` extension of `ForecastingUncertaintyBundle` that
carries the estimated regime assignment with its uncertainty.

**Deliverable form**: conditions + benchmark + bundle extension.

**Relationship to causal agenda**: this problem is the forecasting dual of
Causal Track 15 (nonstationarity as an identification tool). Regime shifts
used here as a modelling problem become, in causal Track 15, identification
levers. A successful result in one track should constrain the other.

---

### 4.4. Open problem: neural and hybrid forecasters with trust-region UQ

**What the problem is**: the catalog currently has no neural forecaster
(DeepAR, N-BEATS, Temporal Fusion Transformer, PatchTST). These are Phase-6
candidates. The research question is not "integrate them" but "when should
the system trust them". Neural forecasters on small policy series
(≤ 120 monthly points, common in administrative data) overfit aggressively.

**Sufficient result**: (a) a trust-region policy for neural forecasters as a
function of series length, seasonality, and noise level; (b) a backoff protocol
that switches to catalog baselines when trust region is exceeded; (c) an
ensemble-with-abstention design that refuses to return a neural prediction
when the classical baseline disagrees beyond a threshold.

**Deliverable form**: trust-region specification + backoff protocol + ensemble
design + integration spec for `ForecastingUncertaintyBundle.source_method`.

---

### 4.5. Open problem: forecast-as-treatment semantics in continuous-time policy

**What the problem is**: some policy actions are themselves forecasts
(announcements, guidance, targets). Their causal effect operates through
expectations. The engine currently has no notion of "treat a forecast as a
causal intervention". The research question is: under what conditions is a
published forecast causally identified as an intervention on expectations,
and how does this integrate with the causal proof kernel?

**Why it cannot be implemented without research**: this is at the intersection
of rational-expectations macro, announcement-effect econometrics, and causal
identification. There is no unified treatment of forecasts as interventions.
Without formalization, forecast-treatment effects are either spuriously
claimed (announcement dummies in reduced form) or ignored.

**Sufficient result**: formal semantics for a forecast-as-intervention query
type, with identification conditions and a certificate format compatible with
the causal `ProofBundle`.

**Deliverable form**: semantics + identification conditions + certificate +
integration spec with causal proof kernel (parallel to Causal Track 12 on
intervention hierarchy).

---

## 5. Research Track 4 — Econometrics under Regularization, Cross-Unit Dependence, and Misspecification {#5-research-track-4}

**Status in catalog**: `catalog/econometrics/` ships 15 files covering
panel estimators (FE/RE/BE/FD), time-series (ARIMA/VAR/GARCH), IV (2SLS/LIML/
GMM), count data, discrete choice, factor models, high-dimensional, selection
(Heckman), semiparametric, and event study. Typed contracts `PanelData`,
`TimeSeriesData`, `EconometricResult`, `EconometricDiagnosticResult` are in
place. The problems below remain research-first.

### 5.1. Open problem: post-selection inference for high-dimensional IV

**What the problem is**: the family ships double-selection LASSO IV, but
inference after LASSO selection is not uniformly valid. Standard 2SLS
confidence intervals after instrument selection under-cover whenever the
first-stage R² is moderate.

**Why it cannot be implemented without research**: post-selection inference
for IV is an active research area. Debiased/double-machine-learning approaches
resolve part of the problem but have their own assumptions (orthogonality,
sample-splitting, first-stage rate conditions). For policy data where these
conditions are borderline, no existing theorem guarantees uniform coverage.

**Sufficient result**: uniform coverage conditions for post-LASSO IV in the
policy regime, with a specified test procedure, sample-size requirement, and
runtime diagnostic that flags when the conditions are violated.

**Deliverable form**: conditions + diagnostic + integration spec for
`EconometricResult.coverage_guarantee_tier`.

---

### 5.2. Open problem: dynamic panel asymptotics under cross-sectional dependence

**What the problem is**: Arellano-Bond and system-GMM estimators assume
cross-sectional independence. Policy panels (states, firms, counties) violate
this: spatial or network spillovers produce dependence across units that
biases standard errors toward zero by factors of 2–10.

**Why it cannot be implemented without research**: robust-variance corrections
for dynamic panels under cross-unit dependence are only partially characterized.
The appropriate correction depends on the dependence structure (spatial,
network, block), which the engine must determine from data before selecting a
variance estimator.

**Sufficient result**: (a) a dependence-diagnosis procedure that detects and
classifies cross-unit dependence; (b) per-class variance correction with
consistency proofs; (c) a degraded-readiness mode when diagnosis is
inconclusive.

**Deliverable form**: diagnostic + variance-correction library + degraded-mode
spec + integration spec for `EconometricResult.cross_sectional_dependence_diagnostic`.

**Cross-family link**: the dependence diagnostic should be shareable with the
network family (Track 12) and the spatial family (Track 13) — they need the
same primitive.

---

### 5.3. Open problem: semiparametric efficiency bounds for complex-survey estimators

**What the problem is**: the catalog has semiparametric estimators and
separate complex-survey estimators (in `catalog/survey/`). There is no unified
theory of efficient estimation when both nonparametric nuisances (propensity,
outcome regression) and complex-survey weights are present. Standard
efficiency bounds assume either IID or fixed-design sampling.

**Why it cannot be implemented without research**: double-robust estimators
under complex-survey sampling require a combined efficiency theory. Without
it, the engine either discards design information (loses variance) or
discards orthogonality (loses bias guarantees).

**Sufficient result**: semiparametric efficiency bounds for at least three
core estimators (ATE, ATT, conditional mean) under stratified / clustered /
weighted sampling, together with a double-robust estimator achieving the bound
and a diagnostic for the weight regime under which it is valid.

**Deliverable form**: efficiency bound theorems + estimator family + regime
diagnostic + integration spec shared between `catalog/econometrics/` and
`catalog/survey/`.

---

### 5.4. Open problem: threshold and kink models with state-dependent thresholds

**What the problem is**: policy-relevant thresholds (tax brackets, eligibility
cutoffs, benefit phase-outs) often move over time with policy updates. Catalog
threshold models assume a fixed or exogenous threshold. When the threshold
is itself a policy choice, a naive estimator treats endogenous variation as
exogenous.

**Sufficient result**: identification conditions for threshold models with
endogenous thresholds, a consistent estimator, and a fallback when the
exogeneity condition fails.

**Deliverable form**: identification theorem + estimator + fallback spec +
integration spec.

---

### 5.5. Open problem: heterogeneous and nonstationary GARCH for policy risk

**What the problem is**: the catalog GARCH is univariate and homogeneous.
Macro-financial policy applications (sovereign-debt risk, FX volatility under
regulatory intervention) require group-stratified or structural-break GARCH.
Research need: M-estimation theory for group-conditional heteroskedasticity,
consistent estimators under finite-regime structural breaks, and a coverage
benchmark for the resulting volatility intervals.

**Sufficient result**: theorem + benchmark + integration spec.

**Deliverable form**: as above.

---

## 6. Research Track 5 — Survey Design, Imputation, and Small-Area Estimation {#6-research-track-5}

**Status in catalog**: `catalog/survey/` ships design, estimation
(Horvitz-Thompson, Fay-Herriot, GREG calibration), imputation (MICE,
nonresponse adjustment), and weighting (raking, propensity) estimators. No
formal `SurveyReport` or `SurveyQualityCertificate` contract yet.

> **Why this track matters**: every PolicyOS pipeline that consumes
> administrative or census data enters through this family. Weight
> inconsistency, small-area instability, and missingness misclassification here
> propagate into every downstream inference.

### 6.1. Open problem: double-robust estimation under design and informative missingness

**What the problem is**: survey weights correct for sampling design;
imputation models correct for missingness. Each requires a model assumption,
and if either is misspecified, the estimate is biased. In administrative data
both are typically misspecified. Double-robustness in this combined sense
(design-adjustment + imputation) has only partial results in the literature.

**Sufficient result**: semiparametric efficiency bounds under union of
"design correct OR imputation correct", an achieving estimator, and a
diagnostic for the regime under which it is valid.

**Deliverable form**: theorem + estimator + diagnostic + integration spec
plus a new `SurveyQualityCertificate` contract carrying the design and
imputation assumption vectors with pass/fail per component.

---

### 6.2. Open problem: small-area estimation under cross-area dependence

**What the problem is**: Fay-Herriot assumes independence across areas.
Spatial and administrative-network dependence is the norm in policy data.
Ignoring dependence biases shrinkage in directions that destroy small-area
coverage.

**Sufficient result**: a dependence-aware SAE estimator with identifiable
variance components, a fallback to independent SAE when the dependence
structure is not identified, and a coverage benchmark.

**Deliverable form**: estimator + identifiability conditions + fallback +
benchmark + integration spec.

**Cross-family link**: shares primitives with Track 13 (spatial) and Track 4
(econometrics under dependence). The same dependence diagnostic should be a
single research result serving three tracks.

---

### 6.3. Open problem: calibration under measurement error in auxiliary variables

**What the problem is**: GREG calibration assumes the auxiliary totals are
known exactly. In policy data, auxiliary totals themselves come from another
survey or administrative source with its own error. Plugging in uncertain
totals propagates error in ways that are not captured by the standard
linearization variance.

**Sufficient result**: a modified calibration equation that downweights
uncertain auxiliary variables proportional to their measurement-error
variance, with consistency and efficiency results.

**Deliverable form**: modified estimator + integration spec for
`CalibrationWeights` contract + new `AuxiliaryTotalUncertainty` input slot.

---

### 6.4. Open problem: missing-not-at-random (MNAR) taxonomy for administrative missingness

**What the problem is**: standard MAR/MCAR/MNAR taxonomy does not map cleanly
onto administrative missingness mechanisms (didn't apply, office closed,
system change, record retention expired). Each has different identification
implications.

**Sufficient result**: a taxonomy of administrative missingness with graphical
representations and recoverability conditions per class (this dovetails with
Causal Track 11 on recoverability).

**Deliverable form**: taxonomy + graphical models + recoverability conditions
+ integration spec for `SurveyQualityCertificate.missingness_class` shared
with `DataReadinessReport.missingness_assessment`.

---

### 6.5. Open problem: raking and iterative-proportional-fitting positivity diagnostics

**What the problem is**: raking is the workhorse of tax-benefit microsimulation
weighting. Its fixed point can fail (non-convergence) or produce extreme
weights (near-violation of positivity). The catalog implementation has no
formal stopping rule or positivity check.

**Sufficient result**: a convergence diagnostic with calibrated thresholds,
a near-violation diagnostic, and a formal relationship between near-violation
severity and the resulting variance inflation.

**Deliverable form**: diagnostic + threshold calibration + variance bound +
integration spec.

---

## 7. Research Track 6 — Distributional Analysis, Mobility, and Counterfactual Inequality {#7-research-track-6}

**Status in catalog**: `catalog/distributional/` ships Gini, Lorenz, Atkinson,
generalized entropy, Theil, Palma, FGT poverty, Alkire-Foster multidimensional
poverty, transition matrices, intergenerational elasticity, Esteban-Ray /
Duclos-Esteban-Ray polarization. The family emits scalar JSON; there is no
typed `DistributionalBundle` contract. The problems below remain research-first.

### 7.1. Open problem: sharp bounds on counterfactual distributions under partial identification

**What the problem is**: inequality indices of current distributions are
descriptive. Policy requires counterfactual indices: "what would Gini be
under this reform?". Pointwise point estimates require causal identification
of the full distribution; under partial ID, bounds on indices are needed.

**Why it cannot be implemented without research**: this is the dual of Causal
Track 5 (distributional OT under partial ID). Sharpness for inequality-index
functionals requires specialized dual certificates (the functional is not
linear in the joint distribution). Without sharpness, the system reports
intervals whose width is an artifact of inner approximation, not of the
data.

**Sufficient result**: sharpness theorems for at least four inequality
functionals (Gini, Theil, Atkinson, poverty headcount) under standard partial-
ID assumption classes (monotone treatment response, stochastic dominance).

**Deliverable form**: theorem family + dual-certificate format + integration
spec for a new `DistributionalBoundsBundle` contract sharing the causal
`BoundsBundle.sharpness_status` taxonomy.

---

### 7.2. Open problem: mobility estimation under panel attrition

**What the problem is**: intergenerational and lifetime mobility estimators
assume complete panels. Attrition is nearly universal, is correlated with
low mobility, and is ignored in the current code.

**Sufficient result**: identification conditions for mobility matrices under
attrition, a consistent estimator under at least one attrition mechanism class,
and a bounds-based fallback under weaker assumptions.

**Deliverable form**: identification theorem + estimator + bounds fallback +
integration spec for a `MobilityReport` contract carrying both point and bound
estimates.

---

### 7.3. Open problem: multidimensional poverty with ordinal dimensions

**What the problem is**: Alkire-Foster treats ordinal dimensions (health
status, education level) as cardinal. This is a known methodological issue.
Reform-sensitive poverty indices change sign under alternate ordinal
encodings.

**Sufficient result**: a poverty-index family robust to ordinal re-coding,
with sensitivity bounds, plus a cutoff-choice sensitivity diagnostic.

**Deliverable form**: robust index family + sensitivity bounds + diagnostic +
integration spec.

---

### 7.4. Open problem: decomposition of inequality under endogenous group composition

**What the problem is**: Theil-T / GE decompositions hold within/between
group shares constant. When policy endogenously changes composition
(migration, marriage, firm entry), the decomposition mixes causal and
compositional effects.

**Sufficient result**: causal decomposition conditions, an estimator that
separates structural from compositional change, and a blocking rule when
separation is not identified.

**Deliverable form**: conditions + estimator + blocking rule + integration
spec.

**Cross-family link**: this sits at the boundary between this family and the
causal engine's composition track. A solution here should be expressible as a
causal fragment with a sharp inequality functional.

---

### 7.5. Open problem: long-horizon mobility under latent heterogeneity

**What the problem is**: 5-year and longer mobility transitions mix mean
reversion with latent heterogeneity in earnings ability. The current
transition-matrix estimator cannot separate them.

**Sufficient result**: a latent-heterogeneity mobility model with
identification conditions under multi-period panels and consistency results
for the separation of reversion and heterogeneity.

**Deliverable form**: model + identification + estimator + integration spec.

---

## 8. Research Track 7 — Policy Evaluation, Welfare Aggregation, and MCDA {#8-research-track-7}

**Status in catalog**: `catalog/policy/` ships budget-impact, scorecard,
ex-ante simulation, sufficient-statistics welfare (frontier), cost-benefit,
general welfare, fiscal multiplier, Krusell-Smith lite, mean-field
equilibrium, TOPSIS/AHP/ELECTRE MCDA, and foundation-model policy analysis
(frontier). The problems below remain research-first.

### 8.1. Open problem: welfare aggregation under general-equilibrium uncertainty

**What the problem is**: sufficient-statistics welfare assumes partial-
equilibrium elasticities. General-equilibrium feedbacks (price adjustments,
fiscal revenue effects, crowding in / out) are large and are usually
estimated separately. No current contract propagates GE uncertainty into the
welfare bottom line.

**Sufficient result**: a uncertainty-propagation framework for welfare
aggregation that combines partial-equilibrium elasticity uncertainty with
GE-multiplier uncertainty under a declared model class, producing a robust
welfare interval rather than a point.

**Deliverable form**: propagation framework + `WelfareBundle` contract with
`ge_uncertainty_ref` field + integration spec.

---

### 8.2. Open problem: state-dependent social welfare weights

**What the problem is**: the current methods assume fixed social welfare
weights. Optimal-tax theory (Saez, Diamond) implies that at the optimum the
implicit social weights are pinned down by observed policy. If weights are
not updated to the current state, welfare recommendations drift off the
Pareto frontier.

**Sufficient result**: an iterative procedure to recover implicit social
weights from observed policy, with identifiability conditions under multiple
policy regimes, and an update rule for the welfare calculation.

**Deliverable form**: procedure + identifiability + update rule + integration
spec for `WelfareBundle.social_weight_ref`.

---

### 8.3. Open problem: equilibrium existence and multiplicity under aggregate shocks

**What the problem is**: Krusell-Smith-lite assumes a unique equilibrium.
Heterogeneous-agent macro models exhibit multiplicity under sufficient
inequality or fiscal interaction. The current implementation returns one
equilibrium without detecting or reporting multiplicity.

**Sufficient result**: existence and uniqueness conditions over a declared
parameter class, a multiplicity-detection algorithm, and a reporting format
that carries multiple equilibria with basins of attraction.

**Deliverable form**: conditions + detection algorithm + reporting format +
integration spec.

**Cross-family link**: companion to causal Track 5.4 (MFG) and Track 1.3
(cyclic composition).

---

### 8.4. Open problem: MCDA consensus under preference disagreement

**What the problem is**: TOPSIS / AHP / ELECTRE produce different rankings
under plausible weight vectors. When stakeholders disagree on weights, rank
instability is common. No current method characterizes rank flip probability
or aggregates across stakeholders.

**Sufficient result**: a formal stability measure for MCDA rankings under a
declared weight-disagreement region, an aggregation rule with a characterized
impossibility frontier (analogue of Arrow's theorem), and a refusal policy
when rank flip exceeds a declared threshold.

**Deliverable form**: stability measure + aggregation rule + refusal policy +
integration spec.

---

### 8.5. Open problem: joint behavioral-fiscal incidence with identifiable channels

**What the problem is**: mechanical effects, behavioral-response effects, and
fiscal-feedback effects are currently estimated separately. The joint
incidence under a policy portfolio (multiple simultaneous instruments) is not
identifiable without a structural model that the catalog does not provide.

**Sufficient result**: reduced-form identifiability conditions for channel
decomposition under at least one realistic policy-portfolio class, together
with a blocking rule when the conditions fail.

**Deliverable form**: conditions + blocking rule + integration spec for
`WelfareBundle.channel_decomposition_ref`.

---

## 9. Research Track 8 — Optimization under Uncertainty, Bilevel, and Inverse Optimization {#9-research-track-8}

**Status in catalog**: `catalog/optimization/` ships LP, MILP, convex (QP,
SOCP), multiobjective (NSGA-II), sequential (TwoStageStochastic, DynamicProgramming),
combinatorial (Knapsack, VehicleRouting), game-theoretic (NashEquilibrium),
bilevel, and chance-constrained, plus IO (Leontief) models. Typed contracts
`OptimizationProblem`, `OptimizationResult`, `IOModelResult` exist. The
problems below remain research-first.

### 9.1. Open problem: stochastic programming under distributional ambiguity

**What the problem is**: ChanceConstrained assumes a parametric noise
distribution. Policy fiscal shocks are heavy-tailed and regime-dependent. The
research question is: which moment-constrained distributionally robust
optimization (DRO) formulations are tractable and produce solutions whose
worst-case guarantees hold under declared moment bounds?

**Sufficient result**: tractable DRO formulations for at least three policy-
relevant constraint classes (budget, capacity, equity), with moment-bound
estimators and a diagnostic for bound validity.

**Deliverable form**: formulation library + moment estimator + diagnostic +
integration spec for `OptimizationResult.ambiguity_certificate`.

---

### 9.2. Open problem: bilevel optimization with nonconvex follower

**What the problem is**: the bilevel estimator uses an alternating projection
heuristic that has no global convergence guarantee when the follower's
problem is nonconvex (typical for principal-agent settings). In policy
applications (tax policy against strategic firms), nonconvexity is the default.

**Sufficient result**: either (a) a tighter class of nonconvex follower
problems for which the current heuristic is provably correct, or (b) a
drop-in replacement using value-function methods with global-optimality
certificates, or (c) an impossibility-style counterexample class that justifies
a fallback to bounds on the leader's objective.

**Deliverable form**: one of the three + integration spec.

---

### 9.3. Open problem: robust-set adequacy and deadweight-conservatism tradeoff

**What the problem is**: RobustOptimization minimizes worst-case cost over an
uncertainty set. An over-large set yields solutions with excess cost; an
under-large set yields false confidence. The current implementation has no
diagnostic for set adequacy.

**Sufficient result**: a formal relationship between set size, coverage
guarantee, and expected cost inflation, plus an empirical calibration for at
least two set families (box, ellipsoid).

**Deliverable form**: theorem + calibration + set-size selector + integration
spec.

---

### 9.4. Open problem: multi-level (three-plus) hierarchical optimization

**What the problem is**: policy hierarchies are typically three levels
(federal → state → local). Current bilevel methods cannot represent this.
The research question is tractability of tri-level and higher-level games
under reasonable policy structure.

**Sufficient result**: tractability conditions for tri-level problems under at
least one structural restriction (e.g., separable follower objectives), with
a solver and a blocking rule.

**Deliverable form**: conditions + solver + blocking rule + integration spec.

---

### 9.5. Open problem: inverse optimization for behavioral calibration

**What the problem is**: observed policies and allocations carry information
about the latent objective and constraints of decision-makers. No catalog
method recovers those. Inverse optimization is the natural tool, with direct
integration to microsim calibration (Track 11).

**Sufficient result**: identification conditions for inverse optimization of
latent objectives under declared feasibility structure, with a consistent
estimator and a fallback when the conditions fail.

**Deliverable form**: identification + estimator + fallback + integration
spec shared with microsim Track 11.

---

## 10. Research Track 9 — Mechanism Design, Incentive Compatibility, and Auction Theory {#10-research-track-9}

**Status in catalog**: `catalog/mechanism/` ships 5 runtime mechanisms
(TaxSubsidy, IncomeTax, LaborMarket, Queue, AdaptiveAgent) that emit patches
to state. No typed contract records incentive compatibility (IC), individual
rationality (IR), or allocation efficiency.

### 10.1. Open problem: IC/IR verification as a machine-checkable certificate

**What the problem is**: a mechanism is implementable only if reporting truth
is a best response for every type (IC) and participation is weakly preferred
to the outside option (IR). Catalog mechanisms currently verify neither.

**Sufficient result**: a constructive verification procedure that, given a
typed mechanism, returns either an `IncentiveCompatibilityCertificate` (with
the envelope identity or payment rule) or a `NegativeCertificate` with a
profitable deviation.

**Deliverable form**: verification algorithm + certificate format + integration
spec.

---

### 10.2. Open problem: Bayesian mechanism design under private types

**What the problem is**: the catalog assumes deterministic agent behavior.
Real policy is played against agents with private information. Bayesian
mechanism design (BIC) has a rich theory (Myerson) but no direct
implementation in the catalog.

**Sufficient result**: an implementable Bayesian mechanism family for at
least two policy problems (income-tax design, license allocation), with BIC
certificates and a bound on welfare loss versus first-best.

**Deliverable form**: mechanism family + BIC certificate + welfare bound +
integration spec.

---

### 10.3. Open problem: auction and revenue-equivalence under reserve-price uncertainty

**What the problem is**: public-sector auctions (procurement, spectrum,
emissions permits) are a core policy instrument. No catalog estimator covers
auctions. Revenue equivalence (Myerson) assumes known reserve; in practice
reserve is an estimate with its own uncertainty.

**Sufficient result**: revenue-equivalence-like bounds under reserve
uncertainty, a recommended auction format per uncertainty regime, and an
integration with the optimization track's DRO formulations.

**Deliverable form**: bounds + format recommendation + integration spec.

---

### 10.4. Open problem: coupled mechanisms and correlated equilibrium

**What the problem is**: multiple simultaneous mechanisms (income tax + labor
market + queueing) couple into a joint fixed-point problem. The current
catalog composes mechanisms sequentially, not jointly.

**Sufficient result**: existence and computability conditions for correlated
equilibrium under a declared mechanism-composition class, with a solver and
a fallback.

**Deliverable form**: conditions + solver + fallback + integration spec.

**Cross-family link**: parallels causal Track 5 (strategic composition), but
with mechanism-design semantics rather than reduced-form strategic response.

---

### 10.5. Open problem: welfare-loss bounds versus first-best

**What the problem is**: a shipped mechanism should come with an a-priori
bound on its welfare loss against the unattainable first-best benchmark.
This is currently absent; analysts see mechanism output but not its
suboptimality.

**Sufficient result**: welfare-loss bounds for at least three mechanism
families in the catalog with a runtime computation of the bound under the
observed parameter range.

**Deliverable form**: bound family + runtime computation + integration spec
for mechanism contracts.

---

## 11. Research Track 10 — Simulation-Based Inference, Agent-Based Models, and Mean-Field Scaling {#11-research-track-10}

**Status in catalog**: `catalog/simulation/` ships compartmental (SIR, SEIR),
system dynamics (StockFlow), agent-based (AgentPopulation), discrete-event
(Queue), and UQ (MonteCarlo, Bootstrap, PermutationTest). The problems below
remain research-first.

### 11.1. Open problem: identifiability of heterogeneous-agent ABMs from aggregate moments

**What the problem is**: ABMs are typically calibrated to match aggregate
moments. Many micro-level heterogeneity patterns produce indistinguishable
aggregates. Without identifiability conditions, different ABM calibrations
produce wildly different policy counterfactuals.

**Sufficient result**: identifiability conditions for heterogeneous-agent
ABMs from at least two aggregate-moment classes (mean-variance, quantile),
with a diagnostic that detects near-nonidentifiability.

**Deliverable form**: conditions + diagnostic + integration spec for
`SimulationResult.identifiability_diagnostic`.

---

### 11.2. Open problem: bifurcation and attractor analysis for dynamics models

**What the problem is**: system-dynamics and ABM models can have multiple
attractors, limit cycles, and structural-stability transitions. The current
catalog returns a single trajectory and ignores the bifurcation structure of
the parameter space.

**Sufficient result**: a bifurcation-detection procedure with Lyapunov-based
stability certificates for a declared model class, together with a reporting
format that carries multiple attractors.

**Deliverable form**: procedure + stability certificate + reporting format +
integration spec.

---

### 11.3. Open problem: simulation-based inference for expensive simulators

**What the problem is**: Track 1.5 addresses SBI at the Bayesian level. This
sub-problem concerns the simulation side: budget-minimizing designs for
expensive simulators, and coupling simulation outputs to the causal proof
kernel so that simulated counterfactuals carry their own identification
certificates rather than being treated as ground truth.

**Sufficient result**: a budget-minimizing design algorithm with sample-
efficiency bounds, and an integration that treats simulator outputs as
certified-identified under declared simulator validity assumptions.

**Deliverable form**: design algorithm + efficiency bounds + integration spec
linking `SimulationResult` to causal `ProofBundle`.

---

### 11.4. Open problem: coupling discrete-event and agent-based dynamics

**What the problem is**: QueueDiscreteEvent and AgentPopulation are separate
modules. Policy problems (job search under benefit-eligibility queues,
healthcare triage) require joint discrete-event + agent-heterogeneous dynamics.

**Sufficient result**: a semantic framework for coupled discrete-event / ABM
simulation with soundness conditions and a minimal estimator family.

**Deliverable form**: framework + estimator + integration spec.

---

### 11.5. Open problem: mean-field convergence rates and finite-N correction

**What the problem is**: MFG-based policy welfare assumes the infinite-N
limit. Finite-N policy populations (10³–10⁶ agents) have measurable MFG
bias. Current catalog methods do not quantify or correct for this bias.

**Sufficient result**: MFG convergence-rate theorems for at least two policy
model classes with a finite-N correction and a benchmark.

**Deliverable form**: theorems + correction + benchmark + integration spec
tied to causal Track 5.4 (MFG equilibrium) and policy Track 7.3.

---

## 12. Research Track 11 — Microsimulation: Identifiability, Calibration, and Behavioral Feedback {#12-research-track-11}

**Status in catalog**: `catalog/microsim/` ships reweighting calibration,
static microsim, tax-benefit calculator, behavioral-response estimator,
imputation model, dynamic microsim. Typed contracts
`SurveyMicroData`, `MicrosimResult`, `TaxBenefitResult`, `ReweightingResult`,
`BehavioralResponseResult`, `ImputationResult`, `DynamicMicrosimResult` are in
place. The problems below remain research-first.

### 12.1. Open problem: identifiability of behavioral elasticities from cross-sectional microdata

**What the problem is**: BehavioralResponseEstimator takes elasticity as an
input. Recovering elasticity from microdata alone mixes labor-supply response,
taste heterogeneity, and measurement error. Without identifiability analysis,
the calibration is a black box.

**Sufficient result**: identifiability conditions for heterogeneous
elasticities under declared microdata availability (cross-section, repeated
cross-section, panel), with a consistent estimator and a blocking mode when
the conditions fail.

**Deliverable form**: conditions + estimator + blocking mode + integration
spec.

---

### 12.2. Open problem: nonlinear calibration and generalized moment matching

**What the problem is**: current reweighting is linear. Policy targets are
often nonlinear in weights (match Gini, match quantile). GMM-style
calibration is needed but is not in the catalog.

**Sufficient result**: a GMM calibration estimator with consistency and
efficiency results under nonlinear targets, and a diagnostic for
target-incompatibility.

**Deliverable form**: estimator + diagnostic + integration spec for
`ReweightingResult.target_compatibility`.

---

### 12.3. Open problem: dynamic microsim validation against longitudinal data

**What the problem is**: DynamicMicrosimEstimator projects life-cycle incomes
without formal validation against observed panels. Projection bias accumulates
over horizons of 10–40 years.

**Sufficient result**: a validation protocol with characterized statistical
tests for projected moments vs. observed panel moments, and a horizon-
dependent confidence envelope.

**Deliverable form**: protocol + tests + envelope + integration spec for
`DynamicMicrosimResult.validation_diagnostic`.

---

### 12.4. Open problem: MNAR sensitivity for income imputation

**What the problem is**: ImputationModelEstimator assumes MAR. Income
nonresponse is often MNAR (shame about low income, high income avoidance of
disclosure). Current results silently inherit the MAR assumption.

**Sufficient result**: MNAR sensitivity bounds under at least two MNAR
mechanism classes, with a reporting format that carries the assumption vector
and the bound.

**Deliverable form**: bounds + reporting format + integration spec shared
with survey Track 5.4 (MNAR taxonomy).

---

### 12.5. Open problem: fiscal-feedback-consistent behavioral response

**What the problem is**: TaxBenefitCalculator applies fixed elasticities
linearized around baseline. Large reforms violate the linearization
assumption; fiscal feedback (reduced labor supply → lower revenue → policy
response) is not modeled.

**Sufficient result**: a fixed-point solver for fiscal-feedback-consistent
behavioral response with existence conditions and convergence guarantees, and
a diagnostic when convergence fails.

**Deliverable form**: solver + conditions + diagnostic + integration spec.

**Cross-family link**: parallels causal Track 5.2 (performative convergence).

---

## 13. Research Track 12 — Network Analysis: Peer Effects, Formation, and Temporal Graphs {#13-research-track-12}

**Status in catalog**: `catalog/network/` ships community detection,
input-output linkage, network diffusion, contagion, and multiplex network
analysis. Typed contracts `NetworkData`, `MultiplexNetworkData`, `NetworkResult`
exist. The problems below remain research-first.

> **Relationship to causal agenda**: this track is the foundry-methods partner
> of Causal Track 9 (hypergraph / topological interference). Causal Track 9
> develops identification theory for group-level interference; this track
> covers the upstream network-formation, peer-effect, and temporal-graph
> estimation that the identification theory needs as input.

### 13.1. Open problem: Manski reflection-problem identification

**What the problem is**: network-diffusion and contagion models conflate
contextual, endogenous, and correlated effects. The reflection problem says
these are not separately identified from a single network without additional
structure.

**Sufficient result**: identification conditions for separating the three
channels under at least two structural restrictions (partial network
observability, instrument availability, multi-wave data), with a consistent
estimator and a blocking mode when the conditions fail.

**Deliverable form**: conditions + estimator + blocking mode + integration
spec for `NetworkResult.peer_effect_decomposition`.

---

### 13.2. Open problem: strategic network formation

**What the problem is**: catalog methods assume the network is exogenously
fixed. Policy interventions often change the network (firm entry, coalition
formation, matching markets). Strategic network formation is an active
research area with no standard estimator.

**Sufficient result**: estimator for a strategic-formation model under
declared utility structure, with identifiability conditions and a fallback
when the conditions fail.

**Deliverable form**: estimator + conditions + fallback + integration spec.

**Cross-family link**: couples to causal Track 5 (strategic causality).

---

### 13.3. Open problem: ERGM and SBM causal stratification

**What the problem is**: no ERGM or SBM estimator is currently shipped.
SBM-based stratification could serve as a unit of causal aggregation; ERGM
could serve as a null model for diffusion tests. Degeneracy of ERGM MLE and
identifiability of SBM communities are well-known open problems in the policy
regime.

**Sufficient result**: a practical ERGM variant (e.g., curved exponential
families) with degeneracy diagnostics plus an identifiable SBM estimator with
causal-stratification semantics.

**Deliverable form**: ERGM variant + diagnostics + SBM estimator + integration
spec.

---

### 13.4. Open problem: network identification under partial observability

**What the problem is**: observed networks are almost always incomplete (node
sampling, link censoring, strategic non-disclosure). Catalog methods assume
complete observation. Link-missingness under various mechanisms has known
identifiability consequences that are not represented.

**Sufficient result**: identification conditions for network statistics under
MAR and MNAR link missingness, with bounds when identification fails.

**Deliverable form**: conditions + bounds + integration spec for
`NetworkResult.missingness_assessment`.

---

### 13.5. Open problem: temporal and dynamic graph causality

**What the problem is**: no dynamic graph methods in the catalog. Policy
networks evolve; static analysis misses feedback between network structure
and outcomes.

**Sufficient result**: a dynamic-graph model class with identifiability of
feedback between structure and outcomes, with an estimator and a fallback
under no-feedback restriction.

**Deliverable form**: model class + estimator + fallback + integration spec
tied to causal Track 3.4 (DSCM for continuous-time).

---

### 13.6. Open problem: network embedding fidelity for causal inference

**What the problem is**: node2vec / DeepWalk / GCN embeddings are increasingly
used as features in causal pipelines. Whether a given embedding is causally
faithful (preserves the conditional-independence structure needed for the
downstream ID argument) is unstudied.

**Sufficient result**: faithfulness conditions for network embeddings under
declared embedding families, with a diagnostic that flags violations.

**Deliverable form**: conditions + diagnostic + integration spec coupled to
causal Track 8 (latent representation).

---

## 14. Research Track 13 — Spatial Analysis: MAUP, Interference, and Space-Time Identification {#14-research-track-13}

**Status in catalog**: `catalog/spatial/` ships Moran's I, GWR, Spatial Durbin,
gravity, accessibility (gravity-based and 2SFCA), GP kriging, IDW, SLX and
SARAR panel models, spatial microsimulation, zone-balance design, and MAUP
sensitivity profile. Typed contracts `SpatialData`, `GravityFlowData`,
`AccessibilityData`, `SpatialResult` exist. The problems below remain
research-first.

### 14.1. Open problem: aggregation-invariant spatial effects (MAUP)

**What the problem is**: MAUPSensitivityProfile quantifies sensitivity but
does not produce aggregation-invariant estimators. Spatial-spillover
estimates change with zoning.

**Sufficient result**: conditions under which a spatial causal effect is
aggregation-invariant, with an estimator for that invariant effect and a
blocking mode when invariance fails.

**Deliverable form**: conditions + estimator + blocking mode + integration
spec for `SpatialResult.maup_invariance_certificate`.

**Cross-family link**: parallels causal Track 6 (causal abstraction) —
MAUP-invariance is the spatial instance of faithful micro-to-macro transport.

---

### 14.2. Open problem: spatial confounding and proximal spatial identification

**What the problem is**: Spatial Durbin and SARAR assume observed covariates
capture spatial heterogeneity. Latent spatial confounders (unmeasured local
history, regional institutions) bias all spatial coefficients.

**Sufficient result**: proximal-identification conditions for spatial models
using spatial lags as proxies, with an estimator and a fallback to bounds when
conditions fail.

**Deliverable form**: conditions + estimator + fallback + integration spec
coupled to causal Track 10 (proximal).

---

### 14.3. Open problem: spatial / areal interference identification

**What the problem is**: spatial spillovers interact with the MAUP in ways
that currently yield inconsistent estimates. The research question is a
spatial analogue of Causal Track 9: identification of spillover topology from
areal data.

**Sufficient result**: identification conditions for spatial interference at
a declared scale, with Hodge-style multi-scale decompositions and a benchmark.

**Deliverable form**: conditions + decomposition + benchmark + integration
spec shared with causal Track 9.

---

### 14.4. Open problem: geostatistical extremes under spatial dependence

**What the problem is**: kriging is for the central tendency. Policy decisions
often hinge on tail outcomes (flood, outbreak, fiscal shock). Extreme-value
geostatistics exists but is not in the catalog.

**Sufficient result**: a conditional-extreme-value estimator for spatially
dependent data with asymptotic coverage and an envelope reporting format.

**Deliverable form**: estimator + coverage + envelope + integration spec.

---

### 14.5. Open problem: space-time dynamical causal inference

**What the problem is**: current spatial panel methods use discrete lags.
Continuous space-time dynamics — stochastic PDEs, kernels evolving over time
— are not supported. Policy interventions with space-time spillovers have no
estimation path.

**Sufficient result**: a space-time DSCM framework with identification
conditions for at least one policy-relevant class (e.g., diffusion-reaction),
and an estimator.

**Deliverable form**: framework + estimator + integration spec tied to causal
Track 3.4 (DSCM).

---

### 14.6. Open problem: small-area spatial smoothing under causal constraints

**What the problem is**: small-area spatial smoothing trades bias and variance,
but in the policy setting, smoothing across areas can absorb genuine causal
variation. The catalog has no theory for smoothing that respects a known
causal boundary (e.g., a policy frontier).

**Sufficient result**: a constrained smoother that respects declared causal
boundaries, with a diagnostic for boundary-leakage.

**Deliverable form**: smoother + diagnostic + integration spec shared with
survey Track 5.2 (cross-area dependence SAE).

---

## 15. Research Track 14 — Validation, Sensitivity, and Calibration of Estimators {#15-research-track-14}

**Status in catalog**: `catalog/validation/` ships cross-validation,
walk-forward, bootstrap, and a metrics calculator. `catalog/sensitivity/`
ships Morris, Sobol, derivative-based, specification-curve, and robustness.
**Neither family has a typed bundle.** Results are JSON dicts. The problems
below remain research-first.

> **Why this track matters**: this is the foundry's reflex layer — every
> estimate from every other family should pass through validation and
> sensitivity before being admitted into a decision. The absence of typed
> contracts here means every family has had to invent its own ad-hoc
> reporting, with no cross-family comparability.

### 15.1. Open problem: formal statistical testing for metric comparisons

**What the problem is**: the metrics calculator returns AUC, RMSE, etc., as
point estimates. Downstream consumers compare them without confidence
intervals or hypothesis tests. Multiple comparison corrections are absent.

**Sufficient result**: a test library for pairwise and family-wise metric
comparisons with calibrated Type I / II error, plus a reporting format that
carries significance alongside every metric.

**Deliverable form**: test library + `ValidationReport` contract + integration
spec.

---

### 15.2. Open problem: calibration diagnostics for probabilistic predictions

**What the problem is**: no calibration curve, ECE, MCE, or Brier-decomposition
estimator ships. Probabilistic outputs from the Bayesian and ML families are
reported without calibration checks.

**Sufficient result**: a calibration-diagnostic library with power
characterization, plus integration with `ValidationReport`.

**Deliverable form**: library + power characterization + integration spec.

---

### 15.3. Open problem: fairness auditing with causal semantics

**What the problem is**: the catalog has no group-wise metric breakdown, no
parity-gap test, no causal-fairness scoring. Every prediction-based decision
in production operates without a fairness diagnostic.

**Sufficient result**: a fairness-audit estimator family with at least two
causal-fairness definitions, significance tests for parity gaps, and a refusal
policy when gaps exceed a declared threshold.

**Deliverable form**: estimator family + tests + refusal policy + integration
spec for `ValidationReport.fairness_audit`.

---

### 15.4. Open problem: sensitivity with dependent and correlated inputs

**What the problem is**: all catalog sensitivity methods (Morris, Sobol,
DerivativeBased) assume input independence. Policy inputs are correlated
(income and education, labor-supply elasticity and education). Dependent-input
sensitivity (Kucherenko, Mara) is not in the catalog.

**Sufficient result**: a dependent-input sensitivity estimator family with
identifiability of marginal vs. structural contributions under declared
copula structures.

**Deliverable form**: estimator family + integration spec for a new
`SensitivityAnalysisBundle` contract.

---

### 15.5. Open problem: quantile and distributional sensitivity indices

**What the problem is**: Sobol indices decompose variance. Policy outcomes are
often evaluated at quantiles (median outcome, 95th-percentile risk).
Moment-independent and quantile sensitivity indices are not in the catalog.

**Sufficient result**: an estimator family for moment-independent / quantile
sensitivity with sample-size requirements and convergence rates.

**Deliverable form**: estimator family + sample-size theorems + integration
spec.

---

### 15.6. Open problem: sensitivity of the sensitivity — uncertainty on indices themselves

**What the problem is**: Sobol and Morris indices are themselves estimates
with sampling uncertainty. The catalog reports point estimates without
intervals, which leads to over-interpretation of index ranking.

**Sufficient result**: confidence-interval estimators for sensitivity indices
with calibrated coverage.

**Deliverable form**: CI estimators + coverage benchmark + integration spec.

---

### 15.7. Open problem: drift and performance-degradation detection

**What the problem is**: walk-forward validation runs offline. No runtime
drift detector exists. A model that passed validation last quarter can be
silently degrading in production.

**Sufficient result**: a drift-and-degradation detector with calibrated FP
rate under a declared stationarity regime, plus a degradation-to-readiness
mapping.

**Deliverable form**: detector + calibration + mapping + integration spec
coupled to ML Track 2.2 (shift detection).

---

# Part II — Cross-Cutting Foundry Infrastructure Tracks

Tracks 1–14 treated method families in isolation. Part II covers the foundry's
cross-cutting subsystems — selection, backends, cost/budget, uncertainty
composition, calibration, streaming, verified numerics, privacy protocols,
benchmark infrastructure, and LLM lifecycle. Gaps here silently degrade every
family in Part I and Part III regardless of per-method quality. A correct
estimator plugged into an un-calibrated advisor, a non-deterministic backend,
an ad-hoc uncertainty chainer, or an un-audited cost model inherits all of
that infrastructure's flaws and ships them as its own output.

## 16. Research Track 15 — Method Selection, Advisor Calibration, and Decision-Theoretic Dispatch {#16-research-track-15}

**Status in catalog**: `polisyos.foundry.methods.selection.py` exposes
`advise_methods()`, `MethodAdvisorQuery`, `MethodAdvisorResult`; selection
logic ranks candidates by a hardcoded `_TRUTHFULNESS_DEPTH` ordering plus a
truthfulness bonus. `discovery.py` performs family/scope filtering;
`catalog_snapshot.py` exposes capability-matrix rows for static inventory.
There is no dedicated contract for advisor verdict quality.

> **Why this track matters**: every production call that does not name an
> estimator flows through the advisor. If the advisor's ranking is not
> calibrated — i.e., if "top-ranked method for this query" does not mean
> "method most likely to meet its own advertised tier on this data" — then
> every downstream correctness guarantee is conditional on a heuristic.

### 16.1. Open problem: calibrated regret bounds for advisor rankings

**What the problem is**: `advise_methods()` returns a ranked list of candidates
with confidence scores derived from static metadata (truthfulness tier,
assumption overlap, runtime). Nothing in the system checks whether, over a
realistic query stream, the top-ranked method actually outperforms the
second-ranked or whether the ranking is empirically near-random within tiers.

**Why it cannot be implemented without research**: regret bounds for a
multi-armed recommender under policy-relevant loss (end-to-end downstream
coverage, not selection accuracy) are not derivable by engineering work.
Defining the loss requires a theory of what the advisor is *supposed* to
optimize given that downstream consumers vary in tolerance and time budget.

**Sufficient result**: (a) a decision-theoretic formulation of advisor loss
as a query-conditional regret against the best-tier method in hindsight;
(b) calibrated regret bounds under declared query-stream assumptions;
(c) a runtime diagnostic that detects when observed regret exceeds the bound,
triggering a retraining cycle.

**Deliverable form**: regret formalization + bound theorem + diagnostic +
integration spec for `MethodAdvisorResult.calibrated_regret_certificate`.

---

### 16.2. Open problem: truthfulness-tier consistency across advisor and method outputs

**What the problem is**: the advisor ranks by `_TRUTHFULNESS_DEPTH` (an
integer depth for tiers like EXACT > ASYMPTOTIC > APPROXIMATE_CALIBRATED);
individual methods report their tier via static metadata. There is no check
that a method's runtime tier (Track 1.1) matches its advertised tier. A method
downgraded at runtime but not downgraded in its catalog row is invisible to
the advisor.

**Sufficient result**: a consistency protocol under which the advisor
consumes the runtime-determined tier (from `PosteriorResult.truthfulness_tier`,
`PredictionIntervalResult.conditional_coverage_diagnostic`, etc.) rather than
static catalog metadata. Requires a formal proof that reconciling static and
runtime tiers preserves advisor monotonicity (adding data should never
downgrade a method's rank).

**Deliverable form**: protocol + monotonicity theorem + integration spec.

**Cross-family link**: requires Track 1.1, Track 2.1, Track 3.1, Track 14.2
to produce runtime tiers.

---

### 16.3. Open problem: cross-method consistency diagnostics under disagreement

**What the problem is**: when two valid methods for the same query disagree
beyond their stated uncertainty, at least one is misspecified. The advisor
today does not run cross-method consistency checks — it returns a single
recommendation without checking whether alternative methods would produce
compatible answers.

**Sufficient result**: (a) a formal disagreement measure on paired method
outputs for the same query (with contracts for `PosteriorResult`,
`PredictionResult`, `EconometricResult`, etc.); (b) a refusal threshold above
which the advisor must report "methods disagree, no recommendation"; (c) a
classification of which method family is likely misspecified based on
disagreement structure.

**Deliverable form**: disagreement measure + refusal threshold + classifier +
integration spec for `MethodAdvisorResult.cross_method_consensus`.

---

### 16.4. Open problem: cost-value-optimal method selection

**What the problem is**: `advise_methods()` currently does not integrate the
`cost_model.py` CostEstimate. A more accurate method that would exceed the
budget is indistinguishable to the advisor from one that fits the budget with
margin. Cost-optimal selection is a constrained multi-objective problem with
open complexity characterization.

**Sufficient result**: a cost-aware advisor variant with provable Pareto
efficiency over accuracy × compute × budget, with declared operating
assumptions on CostEstimate accuracy (Track 17).

**Deliverable form**: Pareto advisor + integration spec shared with Track 17
`OptimizationResult`-style budget certificate.

---

### 16.5. Open problem: human-in-the-loop advisor with structured overrides

**What the problem is**: analysts sometimes override the advisor (they know
their domain better). The current system has no formal record of override
rationale, and no mechanism to learn from override patterns. An advisor that
never learns from overrides drifts from expert practice silently.

**Sufficient result**: a structured-override protocol with audit trail,
per-domain override statistics, and a meta-calibration that updates the
advisor when override patterns reveal systematic disagreement.

**Deliverable form**: override protocol + meta-calibration + integration spec
for `MethodAdvisorResult.override_audit_ref`.

---

## 17. Research Track 16 — Backend Determinism, Cross-Platform Reconciliation, and Replay Tolerance Budgets {#17-research-track-16}

**Status in catalog**: `polisyos.foundry.methods.backends/` ships jax_runner,
numpy_runner, ray_runner, ray_chain_executor, async_chain_executor,
bayesian_runner, solver_runner, adapters.py, dispatch.py, circuit_breaker.py,
runtime_fingerprint.py, checkpointing.py. `runtime_fingerprint.py` carries
`DeterminismTier` and `replay_semantics_for_tier()`.

> **Why this track matters**: the replay contract ("same inputs + same seed =
> byte-identical output") is the audit foundation of the entire engine. The
> current implementation declares tiers but does not compute the tolerance
> budget that each backend combination actually meets. Every
> `BIT_EXACT` claim in the codebase is a static assertion with no holdout
> verification.

### 17.1. Open problem: tolerance-budget derivation across backend combinations

**What the problem is**: a JAX-only method, a JAX+Ray method, a JAX+NumPy
fallback method, and a solver-plus-JAX pipeline each have different achievable
determinism characteristics across x86, ARM, CPU, and GPU. The current tier
assignment is the pipeline author's declaration, not a measured property.

**Why it cannot be implemented without research**: tolerance budgets under
JIT recompilation, parallel-chain accumulation, and solver-interior rounding
interact non-linearly; a composed pipeline's tolerance is not the sum of its
parts. Without a theorem for composition, tier metadata is aspirational.

**Sufficient result**: (a) a composition law for `DeterminismTier` across
backend pipelines; (b) per-backend measured tolerance bounds across an
architecture envelope (x86-CPU, ARM-CPU, CUDA, MPS); (c) runtime fingerprint
diagnostics that downgrade the tier when measured output deviates from the
expected tolerance.

**Deliverable form**: composition law + measured envelope library + runtime
fingerprint diagnostic + integration spec for
`RuntimeFingerprint.observed_tolerance_budget`.

---

### 17.2. Open problem: deterministic recovery semantics under circuit-breaker trips

**What the problem is**: `circuit_breaker.py` implements failure recovery by
falling back to an alternate backend. The fallback path is not
bit-reproducible to the primary path, so a circuit-breaker trip today silently
changes the numerical answer without surfacing the change.

**Sufficient result**: a formal spec for fallback semantics that either
(a) preserves a declared tolerance bound across primary/fallback, or
(b) halts and reports "no deterministic path available" — never producing a
silently-altered output.

**Deliverable form**: fallback protocol + halt-vs-proceed criterion +
integration spec.

---

### 17.3. Open problem: deterministic distributed execution under non-associative reductions

**What the problem is**: `ray_chain_executor.py` aggregates partial results
in non-deterministic order when workers return asynchronously. Summation and
reduction of floating-point partials are not associative; a rerun can produce
different last-bit results.

**Sufficient result**: either (a) a deterministic-order protocol for Ray
aggregation that preserves replay, with a measured latency cost, or (b) a
dual-reduction certificate that bounds the cross-run deviation under a
worst-case reduction tree.

**Deliverable form**: protocol + cost measurement OR deviation bound +
integration spec.

---

### 17.4. Open problem: cross-backend numerical equivalence as a certificate

**What the problem is**: when the advisor routes a method to JAX for GPU
throughput and a subsequent audit re-runs it on NumPy-CPU for determinism,
the two runs should produce results within a declared cross-backend tolerance.
No contract captures this. Analysts currently assume equivalence.

**Sufficient result**: a pairwise cross-backend tolerance library for each
method, with a certificate attached to results indicating "rerun on backend
X would change each field by at most ε".

**Deliverable form**: library + certificate format + integration spec for
`MethodResult.cross_backend_equivalence_ref`.

---

## 18. Research Track 17 — Cost, Energy, and Budget-Robust Estimation Infrastructure {#18-research-track-17}

**Status in catalog**: `polisyos.foundry.cost_model.py` exposes `CostEstimate`
with compile/run/memory fields and `budget_violations`; `plan_optimizer.py`
chooses execution plans; `profiler.py` records post-hoc timings. No contract
carries energy or carbon; CostEstimate has no uncertainty.

### 18.1. Open problem: uncertainty-aware cost estimation

**What the problem is**: CostEstimate is a point prediction. Actual runtime
varies with data shape, numerical conditioning, and backend contention by
factors of 2–10×. A planner that treats the estimate as certain will either
reject tractable plans (conservative bias) or accept intractable ones (optimistic
bias).

**Sufficient result**: a distributional-cost estimator with calibrated
percentiles per method, a budget-feasibility certificate that bounds the
probability of runtime overrun, and a plan-optimizer integration that trades
off expected cost against overrun probability.

**Deliverable form**: distributional cost model + feasibility certificate +
integration spec for `CostEstimate.distribution_ref`.

---

### 18.2. Open problem: energy and carbon accounting as a first-class cost

**What the problem is**: deep methods (Bayesian NUTS, GP inference, neural
forecasting) consume substantial compute. No contract records energy, carbon,
or monetary cost per call. Government deployments need these as audit fields
regardless of internal concerns.

**Sufficient result**: an energy-accounting scheme per backend calibrated
against hardware power draw, a carbon-intensity estimate per method run, and
a budget formulation that can constrain by energy rather than wall-clock.

**Deliverable form**: accounting scheme + carbon estimate + integration spec
for `CostEstimate.energy_footprint` and a new `CarbonCertificate`.

---

### 18.3. Open problem: precision-budget tradeoffs with error bounds

**What the problem is**: reduced-precision arithmetic (FP16, BF16, mixed
precision) can cut compute by 2–4× at the cost of numerical error that
propagates unpredictably. No method in the catalog exposes a precision
parameter with coverage guarantees.

**Sufficient result**: per-method precision-to-error maps with provable
forward-error bounds for declared precision modes, plus a runtime diagnostic
that halts when reduced-precision output cannot meet the method's advertised
coverage.

**Deliverable form**: precision-error map + diagnostic + integration spec for
`MethodResult.precision_mode_and_bound`.

---

### 18.4. Open problem: robust optimization of plan selection under cost uncertainty

**What the problem is**: `plan_optimizer.py` selects a plan to minimize
expected cost. Under heavy-tailed cost distributions (Track 17.1), expected
cost is not the right objective — a plan with low mean and catastrophic tail
costs is worse than one with higher mean and bounded tail.

**Sufficient result**: a distributionally robust plan-selection formulation
(connecting to Track 8.1 DRO) with tractable uncertainty sets over cost
distributions, plus an auditable certificate of the chosen plan's worst-case
cost.

**Deliverable form**: DRO plan selector + certificate + integration spec
shared with Track 8.

---

## 19. Research Track 18 — Uncertainty Composition and Multi-Stage Envelope Algebra {#19-research-track-18}

**Status in catalog**: `polisyos.foundry.uncertainty/` ships `analytical.py`,
`covariance.py`, `delta.py`, `monte_carlo.py`, `quasi_mc.py`, `sensitivity.py`,
`aggregator.py`, `dispatcher.py`, plus `UncertaintyEnvelope` contract.
`polisyos.foundry.calibration.uncertainty_adapter.envelopes_from_calibration()`
converts calibration output to envelopes.

> **Why this track matters**: almost every production query is a chain of
> methods (survey → imputation → estimator → welfare → optimization). Today's
> uncertainty handling is per-stage: each method reports its own envelope,
> and downstream consumers make ad-hoc choices about how to propagate. Without
> a formal envelope algebra, the reported uncertainty at the end of a chain
> is either an over-conservative "worst of each stage" or an invalid
> "confidence-interval of the mean" that ignores bias propagation.

### 19.1. Open problem: envelope algebra for composed methods

**What the problem is**: no algebraic law specifies how to compose
uncertainty envelopes from stage A (e.g., imputed data from Track 5) into
stage B (e.g., causal estimator from Causal Agenda Track 4) into stage C
(e.g., optimization under uncertainty from Track 8). Current code adds
variances or takes maximums; both are wrong in general.

**Sufficient result**: (a) a formal envelope algebra (join, push-forward,
pull-back) that is sound across the UncertaintyEnvelope flavours
(analytical, MC, delta, quasi-MC); (b) convergence rates for MC composition
under bias-variance tradeoffs; (c) a flag on composed envelopes indicating
which flavour they arose from.

**Deliverable form**: algebra + rates + integration spec for
`UncertaintyEnvelope.composition_provenance`.

---

### 19.2. Open problem: delta vs Monte Carlo selection under policy loss

**What the problem is**: `dispatcher.py` chooses between delta-method and MC
propagation based on static heuristics. Delta is biased at boundaries (e.g.,
near-zero-probability events, saturated constraints); MC is variance-heavy
in high dimensions. Neither choice is audited against downstream loss.

**Sufficient result**: a decision rule with provable regret against the oracle
choice under a declared policy-loss family, with runtime diagnostics that
detect when the chosen method's error exceeds the rule's bound.

**Deliverable form**: rule + diagnostic + integration spec.

---

### 19.3. Open problem: importance sampling and adaptive allocation for UQ

**What the problem is**: `monte_carlo.py` uses uniform sampling; `quasi_mc.py`
uses low-discrepancy sequences. Neither adapts to the cost structure of the
underlying method or the importance region of the target quantity. For
expensive methods, this is a 10–100× cost gap that active research on
adaptive importance sampling has closed in other domains.

**Sufficient result**: an adaptive importance-sampling protocol with
provable variance reduction per budget, plus a falloff to uniform when the
importance structure cannot be estimated.

**Deliverable form**: protocol + falloff + integration spec for
`MonteCarloConfig.importance_schedule`.

---

### 19.4. Open problem: coherent risk measures for composed envelopes

**What the problem is**: composed envelopes feed into decision quantities
(welfare, budget feasibility, policy ranking). Current reporting uses mean +
credible interval. For tail-sensitive decisions (fiscal risk, extreme-weather
policy), coherent risk measures (CVaR, expected shortfall) are required but
absent.

**Sufficient result**: CVaR and expected-shortfall estimators for composed
envelopes with asymptotic coverage, plus a unified reporting format.

**Deliverable form**: estimators + format + integration spec shared with
Tracks 7, 8, 34.

---

## 20. Research Track 19 — Calibration Subsystem: Identifiability, Sloppy Modes, and Target Alignment {#20-research-track-19}

**Status in catalog**: `polisyos.foundry.calibration/` ships `calibrator.py`,
`identifiability.py` (Hessian-based), `multi_start.py`, `measurement.py`,
`preflight.py`, `bijectors.py`, `loss.py`, `uncertainty_adapter.py`, `hessian.py`,
`pure_executor.py`, `auxiliary.py`, `report.py`.

> **Why this track matters**: calibration is where policy parameters meet
> data. A calibration failure mode — flat loss surface, target misalignment,
> multimodal loss — silently returns a "calibrated" model that is under-
> determined by data. Every downstream counterfactual inherits this silent
> under-determination.

### 20.1. Open problem: identifiability-constrained calibration

**What the problem is**: `identifiability.py` diagnoses the Hessian at the
optimum; calibration nonetheless returns the point estimate even when the
Hessian is rank-deficient (sloppy directions). The returned value is the
optimizer's final point, not a statistically meaningful parameter.

**Sufficient result**: a calibration protocol that detects sloppy directions,
reports them as unidentified (with a directional uncertainty envelope
spanning the null-space of the Hessian), and either blocks or downgrades the
calibration when identifiability is below a declared threshold.

**Deliverable form**: protocol + null-space reporting format + integration
spec for `CalibrationResult.identifiability_status`.

**Cross-family link**: consumes diagnostics from causal agenda Track 2
(identifiability).

---

### 20.2. Open problem: multi-start local-minima characterization

**What the problem is**: `multi_start.py` runs N restarts; final result is
the best local optimum. No contract records (a) the spread of local optima,
(b) whether multiple are statistically indistinguishable, or (c) whether the
"best" is genuine or a lucky restart.

**Sufficient result**: a characterization protocol that returns the
multimodality of the loss surface, a reporting format that carries multiple
candidate optima when they are within a statistical-equivalence region, and
a policy for downstream consumers to either pick, average, or refuse.

**Deliverable form**: protocol + format + integration spec.

---

### 20.3. Open problem: target-alignment under missing data and index mismatch

**What the problem is**: `preflight.py` aligns target series by index;
real-world targets have gaps, holidays, revisions, and index jitter. The
current alignment drops rows silently. A calibration against a subset that
drops non-randomly is biased in ways that are not captured by the calibration
variance.

**Sufficient result**: a missing-aware alignment protocol with a bias
diagnostic that flags when the kept subset is non-representative, and a
fallback to bounds-based calibration when representativeness fails.

**Deliverable form**: alignment protocol + diagnostic + fallback +
integration spec.

---

### 20.4. Open problem: measurement-error-aware calibration

**What the problem is**: `measurement.py` handles additive noise; policy
targets have structured measurement error (revision lag, reporting thresholds,
top-coding). A calibration that treats measurement error as iid Gaussian
mis-weights revisions and top-codes.

**Sufficient result**: a measurement-model library for administrative data
(reporting thresholds, revision, coding drift), a calibration estimator
under each model class, and a diagnostic that selects the model class from
data.

**Deliverable form**: library + estimator + diagnostic + integration spec
for `CalibrationResult.measurement_model_ref`.

---

## 21. Research Track 20 — Streaming, Online, and Memory-Bounded Estimation {#21-research-track-20}

**Status in catalog**: the catalog's estimators are batch. `executor.py` and
`chain_executor.py` support chained batch runs; nothing supports streaming
updates, bounded memory, or online calibration.

> **Why this track matters**: administrative data arrives monthly; policy
> dashboards and monitoring need online estimates that do not re-run from
> scratch. A batch-only catalog forces the dashboard layer to rebuild
> infrastructure the foundry should own.

### 21.1. Open problem: sequential Bayesian updating with coverage

**What the problem is**: sequential Monte Carlo and assumed-density filtering
exist in the literature but are not in the catalog. Applying them to policy
priors/posteriors requires identification conditions under streaming regime
shifts (Track 3.3).

**Sufficient result**: a sequential-updating framework for at least three
catalog Bayesian methods (linear regression, GP, BART) with coverage
guarantees under declared stationarity and regime-shift classes.

**Deliverable form**: framework + coverage results + integration spec for
`PosteriorResult.streaming_state`.

---

### 21.2. Open problem: bounded-memory estimators for administrative-scale data

**What the problem is**: a single administrative panel (100M rows × 50
columns × 10 years) cannot fit in memory on standard analyst hardware. Out-of-
core estimators are an active research area; none ship today.

**Sufficient result**: bounded-memory estimators for at least three classes
(regression, quantile, panel FE) with error bounds as a function of pass
count and memory budget.

**Deliverable form**: estimator family + bounds + integration spec for
`MethodResult.memory_budget_and_bound`.

---

### 21.3. Open problem: online calibration monitoring and early-warning

**What the problem is**: a calibrated model today is calibrated against
yesterday's data. Drift in calibration itself (not just in prediction) is
only detected at the next batch recalibration. Between calibrations the
model is silently degrading.

**Sufficient result**: online calibration-drift detectors with calibrated FP
rate under declared stationarity, plus a degraded-readiness signal to the
advisor (couples to Track 15).

**Deliverable form**: detector + readiness signal + integration spec
coupled to Tracks 14.7, 15.2.

---

### 21.4. Open problem: streaming validation and rolling CV

**What the problem is**: `catalog/validation/` ships walk-forward CV but not
truly streaming validation with a rolling window and memory-bounded summary
statistics. For long-running dashboards, batch CV is both stale and
expensive.

**Sufficient result**: a streaming CV protocol with summary statistics that
accurately approximate batch CV to within declared tolerance, and a trigger
rule that escalates to batch CV when the approximation violates tolerance.

**Deliverable form**: protocol + trigger rule + integration spec.

---

## 22. Research Track 21 — Verified Numerics, Probabilistic Programming, and Proof-Carrying Estimates {#22-research-track-21}

**Status in catalog**: no interval arithmetic, validated ODE, Taylor-model,
or proof-carrying estimator ships. Bayesian backend uses standard float
precision without rigorous forward-error bounds. No universal PPL (NumPyro,
Pyro, Stan) integration.

### 22.1. Open problem: validated numerics for critical policy computations

**What the problem is**: policy quantities on boundaries (eligibility
thresholds, marginal tax rates, break-even calculations) can flip sign due
to floating-point error. Standard doubles are usually sufficient but have
no guarantee at boundaries. Validated numerics (interval arithmetic, Taylor
models, Chebyshev arithmetic) provide rigorous enclosures.

**Sufficient result**: a validated-numerics kernel for at least three
boundary-sensitive operations (marginal-tax computation, root-finding in
bilevel optimization, integral evaluation for welfare) with integration into
the method dispatch path, plus a cost-vs-guarantee tradeoff study.

**Deliverable form**: kernel + tradeoff study + integration spec for
`MethodResult.validated_bound`.

---

### 22.2. Open problem: PPL front-end with verified compilation

**What the problem is**: Bayesian model authoring currently uses method-
specific APIs. A universal PPL front-end (Pyro/NumPyro-style) would let
analysts write models once and run them across backends, but only if the
compilation preserves semantics.

**Sufficient result**: PPL front-end + verified-compilation theorem for a
declared model subset (e.g., conjugate exponential families, state-space
models), plus a canonical lowering to JAX/NumPy/Bayesian-backend.

**Deliverable form**: front-end + theorem + lowering + integration spec.

---

### 22.3. Open problem: proof-carrying estimate certificates

**What the problem is**: research on proof-carrying code has shown that
computations can ship with runtime certificates (small, verifiable
witnesses) that allow independent verification without re-running the
computation. Policy audit would benefit from this, but no method ships with
such certificates today.

**Sufficient result**: certificate formats and verification procedures for
at least two estimator classes (linear/quadratic programming, convex GLM),
plus a policy on when certificates are required (couples to Track 16.4
cross-backend equivalence).

**Deliverable form**: certificate format + verifier + policy + integration
spec for `MethodResult.verification_certificate`.

---

### 22.4. Open problem: bit-exact reproducibility across hardware

**What the problem is**: the `BIT_EXACT` tier in `DeterminismTier` requires
bit-level output equality across reruns. Today this is only achievable
single-architecture. Cross-architecture bit-exactness is an open problem with
partial solutions (reproducible BLAS, Kahan summation, ordered reductions).

**Sufficient result**: a cross-architecture bit-exact protocol for a declared
method subset, with a performance-vs-exactness tradeoff and a fallback to
declared-tolerance mode when bit-exactness is infeasible.

**Deliverable form**: protocol + tradeoff + fallback + integration spec
coupled to Track 16.1.

---

## 23. Research Track 22 — Differential Privacy, Synthetic Data, and Federated Estimation {#23-research-track-22}

**Status in catalog**: no DP estimator, no synthetic-data generator, no
federated-learning primitive. Government-scale data handling is currently
outside the foundry's scope.

> **Why this track matters**: government data has strict privacy constraints.
> An estimator that cannot operate under DP is non-deployable for many
> administrative datasets. This track covers the three interlocking
> capabilities — DP, synthetic data, federated computation — and is a
> prerequisite for cross-jurisdictional policy work.

### 23.1. Open problem: DP budget allocation across a pipeline

**What the problem is**: DP composition theorems (basic, advanced, RDP,
zCDP) give bounds per step; a pipeline of N methods consumes budget N-fold
under basic composition, much less under RDP. No foundry component tracks
per-call budget consumption, so total budget is either overestimated (wasted)
or unaccounted (unsafe).

**Sufficient result**: a budget-accounting system with per-method DP cost
attached to the method contract, a pipeline-level composition theorem that
is machine-checkable, and a halt protocol when budget is exhausted.

**Deliverable form**: accounting system + composition + halt + integration
spec for a new `PrivacyBudgetCertificate`.

---

### 23.2. Open problem: utility-preserving synthetic microdata

**What the problem is**: synthetic data generators (CTGAN, TVAE, diffusion
tabular models, PrivBayes) are used for data sharing. They have declared
utility vs privacy tradeoffs that are not empirically verified for policy
microdata (skewed income distributions, rare events, structural zeros).

**Sufficient result**: a calibration-benchmark suite measuring utility (task
performance, distribution matching, causal invariance) and privacy (DP level,
membership-inference resistance) across generators on policy data, plus a
recommended generator per use case.

**Deliverable form**: benchmark + recommendation + integration spec for
`SyntheticDatasetCertificate`.

---

### 23.3. Open problem: privacy-preserving record linkage

**What the problem is**: linking administrative records across agencies
requires probabilistic record linkage with privacy protection. Current
methods (Bloom filters, secure hashing) have known attack surfaces for
policy-grade adversaries.

**Sufficient result**: a record-linkage protocol with declared privacy
guarantees, a measured leakage bound, and a certificate of linkage quality
(precision/recall under privacy cost).

**Deliverable form**: protocol + leakage bound + certificate + integration
spec shared with Track 5 (survey).

---

### 23.4. Open problem: federated estimation with correctness

**What the problem is**: no federated primitives in the catalog. Cross-
jurisdictional learning (policy comparison, benchmark statistics) cannot
proceed under current data-sharing constraints. Federated averaging has
known bias under heterogeneous data; policy data is always heterogeneous.

**Sufficient result**: federated estimators for at least three families
(GLM, GBT, Bayesian averaging) with correctness proofs under declared
heterogeneity, privacy budgets per round, and a falloff to centralized
estimation when heterogeneity exceeds bounds.

**Deliverable form**: estimator family + proofs + falloff + integration spec.

---

### 23.5. Open problem: confidential-computing integration and attestation

**What the problem is**: some workflows require TEE (trusted execution
environment) guarantees — remote attestation of the code that computed a
statistic. The foundry has no TEE attestation story, making sensitive-data
policy work outsourced to custom infra.

**Sufficient result**: a TEE-hosted executor for a declared method subset
with attestation certificates, plus a policy on when TEE is required by
data sensitivity.

**Deliverable form**: executor + certificate + policy + integration spec.

---

## 24. Research Track 23 — Canonical Benchmark Infrastructure and Synthetic Worlds {#24-research-track-23}

**Status in catalog**: each family has ad-hoc tests under `tests/unit/foundry/`.
No canonical benchmark corpus, no hidden holdout for the six-judge promotion
stack, no synthetic-world generator with known ground truth that could
evaluate any method in the catalog.

> **Why this track matters**: every research-first track in this document
> relies on a "benchmark proxy" (anti-swamp governance rule). Without a
> shared benchmark infrastructure, each track builds its own benchmark, the
> benchmarks are not cross-comparable, and graduation judgments become
> track-local. A canonical benchmark infrastructure is the only way the
> six-judge promotion stack can reach cross-family comparability.

### 24.1. Open problem: ground-truth synthetic worlds

**What the problem is**: no synthetic-world generator produces data with a
known ground truth that can evaluate methods from the Bayesian, ML,
forecasting, econometrics, survey, distributional, and causal families on
the same underlying DGP. Each family uses its own toy DGPs today.

**Sufficient result**: a synthetic-world generator family that covers at
least three DGP classes (cross-sectional, panel, spatio-temporal) with
configurable heterogeneity, missingness, and measurement error, plus ground-
truth targets for all major estimands across families.

**Deliverable form**: generator + DGP class library + target API +
integration spec.

---

### 24.2. Open problem: hidden-holdout infrastructure for the six-judge stack

**What the problem is**: the six-judge promotion stack (structural,
statistical, robustness, governance, reproducibility, compute) requires
hidden holdout data that the method author cannot access. The current
infrastructure does not provide holdout datasets with author-proofed
isolation.

**Sufficient result**: a holdout-infrastructure protocol with cryptographic
sealing, per-author isolation, and an audit trail of holdout evaluations.

**Deliverable form**: protocol + sealing + audit + integration spec.

---

### 24.3. Open problem: per-regime leaderboards and stratified benchmarks

**What the problem is**: method performance is regime-dependent (high-dim vs
low-dim, stationary vs drift, IID vs clustered). A single leaderboard number
averages away regime-conditional quality. Policy users need per-regime
quality.

**Sufficient result**: a leaderboard schema with per-regime stratification,
per-regime confidence intervals, and a "regime detector" that maps a query
to the applicable regime.

**Deliverable form**: schema + regime detector + integration spec shared
with Track 15 (advisor).

---

### 24.4. Open problem: adversarial and pathological case library

**What the problem is**: a SOTA engine must not degrade silently on known
adversarial cases (near-violations of estimator assumptions, pathological
data shapes). Adversarial benchmarks exist in ML but not in policy statistics.

**Sufficient result**: a pathological-case library indexed by
assumption-class with expected behavior per case ("method X must halt",
"method Y must downgrade tier", "method Z has no defined behavior — report
reason").

**Deliverable form**: library + expected-behavior index + integration spec
shared with Tracks 1–14 anti-swamp benchmark proxies.

---

## 25. Research Track 24 — LLM-Assisted Research Lifecycle with Verification {#25-research-track-24}

**Status in catalog**: `catalog/policy/` has a frontier `foundation_model_policy_analysis`
method. There is no LLM-assisted workflow for estimator authoring, proof
checking, literature synthesis, or research-artifact validation.

> **Why this track matters**: research productivity for the remaining 14
> tracks' theorems, proofs, and benchmark construction can be amplified by
> LLM assistants, but only if their contribution is verified. An
> unverified LLM output is indistinguishable from a well-formatted error.

### 25.1. Open problem: LLM-assisted theorem drafting with machine verification

**What the problem is**: LLMs can produce plausible proof drafts but
hallucinate critical steps. Policy research needs theorem drafts that are
machine-checkable before being admitted as evidence.

**Sufficient result**: a workflow that pairs an LLM proof drafter with a
proof assistant (Lean/Coq/Isabelle) on a declared theorem subset (identification
lemmas, coverage results), with a machine-verifiable pass/fail signal per
theorem.

**Deliverable form**: workflow + verification signal + integration spec for
a new `TheoremVerificationCertificate`.

---

### 25.2. Open problem: LLM-scaffolded estimator synthesis with unit-level verification

**What the problem is**: many estimators have a standard structure (moment
condition, IV, GMM, M-estimation); an LLM can scaffold the code but cannot
guarantee correctness. Without verification, LLM-scaffolded estimators are a
code-quality risk.

**Sufficient result**: a scaffolding workflow that produces estimator
candidates paired with unit-test generators, property-based tests, and a
signed audit of what was and was not verified.

**Deliverable form**: workflow + audit + integration spec.

---

### 25.3. Open problem: LLM-assisted literature synthesis with provenance

**What the problem is**: research tracks need continuous monitoring of
external literature (new theorems, new methods, new counterexamples). LLM
synthesis is fast but produces unverifiable claims.

**Sufficient result**: a literature-synthesis workflow with per-claim
provenance (paper, page, span) that can be spot-checked, plus a hallucination
detector that flags claims with no source span.

**Deliverable form**: workflow + provenance format + detector + integration
spec for `LiteratureSynthesisReport`.

---

### 25.4. Open problem: LLM hallucination detection for policy-text reasoning

**What the problem is**: the frontier foundation_model_policy_analysis method
is capped at PROOF_ONLY (Track 2.5). Before it can be lifted, the system
needs a hallucination detector for policy-text claims with bounded false-negative rate.

**Sufficient result**: a hallucination-detector family with measured TP/FP
on a policy-text corpus, plus a refusal-threshold policy that halts
generation when hallucination risk exceeds the threshold.

**Deliverable form**: detector + threshold + integration spec coupled to
Track 2.5.

---

# Part III — New Method Families for Broad-Front SOTA

Tracks 25–35 cover method families the catalog does not yet ship but that a
SOTA policy engine must host. Each family is presented as a research-first
track because integration is gated on contract definition, identification
conditions, or benchmark calibration that engineering cannot produce alone.

## 26. Research Track 25 — Text, NLP, and Regulatory-Language Analytics {#26-research-track-25}

**Status in catalog**: no text/NLP family under `catalog/`. A single frontier
method `foundation_model_policy_analysis` exists under `catalog/policy/`,
capped at PROOF_ONLY pending Track 2.5 calibration.

> **Why this family matters**: regulatory text — statutes, regulations,
> guidance, case law — is the single largest unstructured input to the
> policy workflow. Today, analysts read it manually. A SOTA engine must
> provide typed extraction, identification-aware analysis, and calibrated
> retrieval over this corpus.

### 26.1. Open problem: regulatory information extraction with citation correctness

**What the problem is**: extracting entities, relations, and obligations from
regulatory text is well-studied, but correctness is usually evaluated by
micro-F1. Policy use requires *citation correctness* — every extracted claim
must trace to the exact paragraph or clause. Incorrect citation is a legal
liability, not a quality metric.

**Sufficient result**: an extraction estimator family with per-claim citation
certification, a test that fails any claim whose citation does not contain
the supporting span, and a refusal policy when confidence is below threshold.

**Deliverable form**: estimator family + citation test + refusal + integration
spec for a new `TextExtractionBundle` with `citation_certificate`.

---

### 26.2. Open problem: identified topic models for policy corpora

**What the problem is**: LDA and NMF topic models are used in policy-text
analytics. The identified topics are not invariant to hyperparameters
(number of topics, vocabulary size). The same corpus can yield contradictory
summaries depending on fit. No identification theorem anchors downstream claims.

**Sufficient result**: topic-model identification conditions under declared
priors and vocabulary constraints, with a stability test that flags
non-identified fits.

**Deliverable form**: conditions + test + integration spec.

---

### 26.3. Open problem: text-as-treatment and text-as-outcome with unbiased measurement

**What the problem is**: policy research sometimes uses text as a treatment
variable (e.g., regulatory language variation) or an outcome (e.g., court
opinion sentiment). Both require unbiased text measurement. Downstream causal
estimates inherit any measurement bias.

**Sufficient result**: identification conditions for causal inference with
text as treatment or outcome (connecting to Egami-Roberts-Fong 2018 and
follow-ups), a bias-correction estimator, and a fallback when conditions fail.

**Deliverable form**: conditions + estimator + fallback + integration spec
coupled to the causal agenda's Track 10 (proximal).

---

### 26.4. Open problem: retrieval-augmented policy reasoning with calibrated citations

**What the problem is**: RAG pipelines return generated answers with
citations. Calibration of whether the cited source actually supports the
answer is an open problem. For policy use, hallucinated citation is a
specific harm: the analyst cites a regulation that does not contain the
claimed rule.

**Sufficient result**: a citation-support calibration benchmark with
measured TP/FP over a policy corpus, a refusal threshold, and an
integration with Track 25.4 hallucination detection.

**Deliverable form**: benchmark + threshold + integration spec for
`RAGResponseCertificate`.

---

### 26.5. Open problem: statutory and legal reasoning with proof certificates

**What the problem is**: legal reasoning (does rule R apply under facts F?)
is computable for restricted logics (Datalog-style regulations, decision
tables). Modern LLM approaches lack proof certificates; classical expert
systems lack scale. The policy-relevant subset is somewhere in between.

**Sufficient result**: a statutory-reasoning estimator for at least one
regulated domain (e.g., tax eligibility) that produces a proof certificate
verifiable against the source statute, plus an abstention policy for queries
outside the formalized fragment.

**Deliverable form**: estimator + certificate + abstention + integration
spec for a new `StatutoryReasoningCertificate`.

---

## 27. Research Track 26 — Earth-Observation, Remote Sensing, and Multimodal Geospatial {#27-research-track-26}

**Status in catalog**: no EO/remote-sensing family. `catalog/spatial/`
handles classical spatial statistics but has no satellite/drone imagery
methods, no nightlights-as-proxy, no SAR/optical fusion.

### 27.1. Open problem: remote-sensing proxies with bias-correction certificates

**What the problem is**: nightlights as proxy for economic activity, land-
use as proxy for agricultural output, crop indices as proxy for food
security — all are used in policy, all have known biases (cloud cover,
sensor drift, saturation). Current policy pipelines either ignore the bias
or correct informally.

**Sufficient result**: a proxy-bias-correction estimator family with ground-
truth validation where available, an uncertainty envelope that reflects both
sensor noise and proxy-to-ground gap, and a refusal when ground truth is too
sparse to calibrate.

**Deliverable form**: estimator + envelope + refusal + integration spec for
`RemoteSensingProxyBundle`.

---

### 27.2. Open problem: multimodal fusion (imagery + admin + text)

**What the problem is**: policy indicators often combine satellite
imagery, administrative records, and text (news, social). No theory of fusion
with unbiased aggregation exists in the catalog. Naïve stacking produces
over-confident composite indicators.

**Sufficient result**: a fusion framework with per-modality reliability
weights, an identification theorem for when fused indicators are well-
defined, and a falloff to single-modality reporting when fusion is invalid.

**Deliverable form**: framework + theorem + falloff + integration spec for
`MultimodalIndicatorBundle`.

---

### 27.3. Open problem: geographic privacy and aggregation-level protection

**What the problem is**: raw geolocated imagery is privacy-sensitive at
individual-field / household scale. Standard responses (aggregation,
gridding) interact with MAUP (Track 13.1) and can destroy policy signal.

**Sufficient result**: a geographic-privacy protocol with provable
identifiability bounds at declared aggregation scale, plus a utility-loss
measure that analysts can use to choose aggregation.

**Deliverable form**: protocol + bound + measure + integration spec coupled
to Tracks 13.1 (MAUP) and 22 (DP).

---

### 27.4. Open problem: change-detection with causal semantics

**What the problem is**: EO change-detection algorithms flag pixel-level
change but do not distinguish causal from coincidental change. Policy
consumers need "change attributable to intervention" not "change observed".

**Sufficient result**: a change-detection estimator with causal attribution
under declared assumptions (parallel-trends at pixel level, proximity
exchangeability), with a fallback to descriptive change when attribution
fails.

**Deliverable form**: estimator + fallback + integration spec shared with
causal agenda.

---

## 28. Research Track 27 — Reinforcement Learning, Off-Policy Evaluation, and Adaptive Policy Experimentation {#28-research-track-27}

**Status in catalog**: no RL family. `catalog/mechanism/AdaptiveAgent` has
adaptive agents at the simulation level but no RL estimator for a real-world
policy. No contextual bandits. No off-policy evaluation. No adaptive trial design.

> **Why this family matters**: policy problems with sequential structure
> (treatment sequences, adaptive targeting, dynamic benefit phase-outs) are
> mis-handled by static estimators. OPE is how a government learns from its
> own deployed rules without running new experiments. Both are absent.

### 28.1. Open problem: off-policy evaluation under partial identification

**What the problem is**: standard OPE (IPS, doubly-robust) assumes
overlap and unconfoundedness. Policy data violates both. OPE under partial
identification yields bounds, not points, but the bounds theory is not yet a
production-grade estimator.

**Sufficient result**: OPE bounds estimators for at least two partial-ID
regimes (overlap violation, unmeasured confounding), with sharpness results
(couples to causal agenda Track 5) and runtime diagnostics for each.

**Deliverable form**: estimator family + sharpness + diagnostics + integration
spec coupled to causal agenda.

---

### 28.2. Open problem: contextual bandits with fairness and equity constraints

**What the problem is**: contextual bandits for policy targeting (who gets
outreach, who gets benefit reminders) can produce disparate impact across
protected groups. Standard regret bounds ignore fairness constraints; fairness-
constrained bandits are an active research area without production-grade
algorithms.

**Sufficient result**: a contextual-bandit family with declared fairness
constraints, regret bounds under the constraint, and an auditable certificate
of constraint satisfaction over the deployment horizon.

**Deliverable form**: bandit family + bounds + certificate + integration
spec shared with Track 14.3 (fairness audit).

---

### 28.3. Open problem: adaptive RCTs with valid post-experiment inference

**What the problem is**: adaptive trial designs (response-adaptive randomization,
multi-arm bandits) enable faster learning but invalidate naïve post-trial
confidence intervals. Corrections exist but are fragile to
implementation details.

**Sufficient result**: adaptive-trial protocols with validated post-
experiment inference, simulation-based calibration of Type I error, and a
fallback to fixed-allocation when the validity conditions fail.

**Deliverable form**: protocols + calibration + fallback + integration spec
for `AdaptiveTrialResult`.

---

### 28.4. Open problem: safe RL with constraint-violation bounds

**What the problem is**: RL for policy (e.g., dynamic benefit scheduling)
can explore into constraint-violating regions during training. Safe-RL
algorithms bound violation probability but the bounds are usually
asymptotic and not audited at runtime.

**Sufficient result**: a safe-RL algorithm with non-asymptotic constraint
violation bounds per episode, with runtime audit of the bound, for at least
one policy-relevant environment class.

**Deliverable form**: algorithm + bound + audit + integration spec.

---

### 28.5. Open problem: dynamic treatment regimes with partial observability

**What the problem is**: dynamic treatment regimes (DTR) sequentially
assign treatments; standard estimators (Q-learning, G-computation) assume
full observability. Policy DTR (e.g., benefit stacks over time) has partial
observability from administrative lags and strategic non-reporting.

**Sufficient result**: DTR estimators under partial observability with
identification conditions, a consistent estimator, and a bounds-based
fallback.

**Deliverable form**: estimator + fallback + integration spec coupled to
causal agenda Track 12.

---

## 29. Research Track 28 — Structural Macro (DSGE/HANK), Nowcasting, and Structural Model Averaging {#29-research-track-28}

**Status in catalog**: `catalog/policy/` has a `KrusellSmithLite` frontier
method and `MeanFieldEquilibrium`. No general DSGE, no HANK (heterogeneous-
agent New Keynesian), no nowcasting, no structural model averaging.

### 29.1. Open problem: HANK estimation with identification

**What the problem is**: HANK models link the micro-distribution of
household consumption/saving to aggregate dynamics. Estimation is compute-
intensive; identification from aggregate data alone is weak. Without
calibration from micro-data (distributional moments, panel transitions),
HANK reduces to a representative-agent model with extra parameters.

**Sufficient result**: identification conditions for HANK from joint macro +
micro data, an estimator exploiting both, and a diagnostic for weak
identification.

**Deliverable form**: conditions + estimator + diagnostic + integration
spec coupled to Tracks 6, 11.

---

### 29.2. Open problem: DSGE with robust priors and structural-break detection

**What the problem is**: DSGE estimation is prior-sensitive. Policy regimes
(ZLB, fiscal dominance) create structural breaks. The current frontier
methods do not handle either.

**Sufficient result**: a prior-robustness diagnostic (couples to Track 1.3)
plus a structural-break detector specialized for DSGE state-space, with a
reporting format that carries the estimated break date with uncertainty.

**Deliverable form**: diagnostic + detector + format + integration spec.

---

### 29.3. Open problem: real-time nowcasting with mixed-frequency and ragged-edge data

**What the problem is**: fiscal/monetary nowcasting requires mixed-frequency
data (monthly indicators, quarterly GDP, weekly high-frequency) with ragged
edges (most recent periods missing for some series). Dynamic factor models
and MIDAS handle this in principle; no catalog method does.

**Sufficient result**: a nowcasting estimator family with mixed-frequency
handling, a calibration benchmark on historical ragged-edge data, and
integration with the forecasting uncertainty contract from Track 3.1.

**Deliverable form**: estimator family + benchmark + integration spec.

---

### 29.4. Open problem: structural model averaging with identification weights

**What the problem is**: different structural models (RBC, NK, HANK,
financial-frictions DSGE) disagree on policy conclusions. Naïve model
averaging weighs by posterior probability; under weak identification, this
can give arbitrary weights. A robust averaging scheme is needed.

**Sufficient result**: a model-averaging protocol that downweights weakly-
identified models, with a fallback to model-range reporting when all models
are weakly identified.

**Deliverable form**: protocol + fallback + integration spec coupled to
Track 1.3 and Track 22 (evidence synthesis).

---

## 30. Research Track 29 — Evidence Synthesis, Meta-Analysis, and Living Reviews {#30-research-track-29}

**Status in catalog**: no meta-analysis, no network meta-analysis, no
publication-bias correction, no transportability meta-synthesis, no living-
review infrastructure.

> **Why this family matters**: a policy engine that cannot systematically
> integrate external evidence into its own recommendations is limited to its
> in-house estimates. Evidence synthesis is how a government combines
> academic literature, other agencies' studies, and international
> comparisons with its own data.

### 30.1. Open problem: Bayesian network meta-analysis with transportability

**What the problem is**: network meta-analysis combines evidence across
multiple treatments connected by common comparators. Standard NMA assumes
transitivity (comparisons at different sites are exchangeable). Policy
evidence rarely satisfies transitivity; cross-site heterogeneity dominates.

**Sufficient result**: NMA estimators with transportability conditions
imported from the causal agenda (Track 13 in that document), a
transportability diagnostic, and a fallback to per-site reporting when
transitivity fails.

**Deliverable form**: estimator + diagnostic + fallback + integration spec
shared with causal agenda.

---

### 30.2. Open problem: publication-bias correction with calibrated power

**What the problem is**: classical methods (trim-and-fill, PET-PEESE,
selection models) have known failure modes; recent methods (robust Bayesian
meta-analysis) are better but not characterized at policy-relevant sample
sizes.

**Sufficient result**: a publication-bias correction estimator family with
per-method power characterization and a readiness-tier policy that
downgrades meta-analytic estimates whose correction is uncertain.

**Deliverable form**: estimator family + power characterization + policy +
integration spec.

---

### 30.3. Open problem: living-review infrastructure with automated evidence updating

**What the problem is**: policy-relevant evidence updates continuously.
Static reviews go stale. Living-review infrastructure (automated search +
screening + extraction + meta-analytic update) is an active research area
without a production-grade implementation.

**Sufficient result**: a living-review pipeline with declared update cadence,
a calibration benchmark that measures evidence staleness, and an alert
protocol when new evidence invalidates existing recommendations.

**Deliverable form**: pipeline + benchmark + alert + integration spec
coupled to Track 24.3 (LLM literature synthesis).

---

### 30.4. Open problem: meta-transportability across multiple sites

**What the problem is**: when K > 2 sites exist, transportability from each
pair to a target is a combinatorial problem. Single-pair transportability
(causal agenda Track 13) generalizes to K-site with new identification
conditions.

**Sufficient result**: K-site transportability conditions with a unique
transport estimator plus an impossibility-class counter-example when the
conditions fail.

**Deliverable form**: conditions + estimator + counterexamples +
integration spec shared with causal agenda.

---

## 31. Research Track 30 — Matching Markets, Assignment, and Public-Sector Combinatorial Auctions {#31-research-track-30}

**Status in catalog**: `catalog/mechanism/` ships TaxSubsidy / IncomeTax /
LaborMarket / Queue / AdaptiveAgent as runtime mechanisms. No deferred-
acceptance / Gale-Shapley, no two-sided matching estimator, no school-choice
solver, no combinatorial auction.

### 31.1. Open problem: deferred-acceptance with strategy-proofness certificates

**What the problem is**: deferred acceptance (DA) is theoretically strategy-
proof for one side. Policy deployments (school choice, housing lottery)
need a certificate of strategy-proofness under the specific tie-breaking
and priority rules in use, because variants break the DA theorem.

**Sufficient result**: a DA-variant certifier that verifies strategy-
proofness under the specific priority/tie-breaking rules, with a
counterexample produced when strategy-proofness fails.

**Deliverable form**: certifier + counterexample format + integration spec
for `AssignmentMechanismCertificate`.

---

### 31.2. Open problem: two-sided matching with preferences elicited from policy data

**What the problem is**: observed matches (school-student, physician-
hospital) can be used to estimate preferences. The identification is weak
without structure on the preference class. Current estimators assume linear
utility; policy applications often violate this.

**Sufficient result**: identification conditions for preference estimation
under declared utility-class restrictions, with a consistent estimator and a
fallback.

**Deliverable form**: conditions + estimator + fallback + integration spec.

---

### 31.3. Open problem: combinatorial auctions for public-sector allocation

**What the problem is**: spectrum, emissions permits, timber rights, airport
slots are allocated via combinatorial auctions. Truth-telling under VCG is
theoretically guaranteed; computational infeasibility of exact VCG in large
combinatorial settings forces heuristics that break the guarantee.

**Sufficient result**: a large-scale combinatorial-auction solver with
welfare-loss bounds against VCG and strategy-proofness guarantees under
declared approximation tolerance.

**Deliverable form**: solver + bounds + integration spec.

---

### 31.4. Open problem: platform regulation as mechanism design

**What the problem is**: regulating two-sided platforms (gig-work, short-
term rental, payments) is a mechanism-design problem the catalog cannot
represent. Agents have private types, platforms set rules, regulators set
meta-rules.

**Sufficient result**: a three-layer mechanism model with identifiable
welfare bounds under declared agent-type distributions, a sensitivity
analysis over distributional uncertainty, and a refusal when platform-level
welfare cannot be separated from agent-level.

**Deliverable form**: model + bounds + sensitivity + refusal + integration
spec.

---

## 32. Research Track 31 — Point Processes, Event-History, and Hazard Models {#32-research-track-31}

**Status in catalog**: `catalog/ml/survival.py` ships basic survival
(Kaplan-Meier, Cox). No Hawkes / self-exciting processes, no competing
risks, no recurrent events, no marked point processes.

> **Why this family matters**: administrative events (benefit enrollments,
> arrests, hospitalizations, firm entries/exits) are event data, not
> cross-sectional data. Analyzing them with survival OK for simple durations
> but fails for clustering, self-excitation, and competing risks.

### 32.1. Open problem: Hawkes and self-exciting processes for policy events

**What the problem is**: benefit-uptake clusters after announcements; crime
clusters spatially and temporally. Hawkes processes model this. The
identification of the triggering kernel from limited data is weakly
identified; current methods over-fit.

**Sufficient result**: Hawkes estimator with identification conditions,
shrinkage for weakly-identified kernels, and a fallback to Poisson when
triggering is not identified.

**Deliverable form**: estimator + conditions + fallback + integration spec
for `PointProcessResult`.

---

### 32.2. Open problem: competing risks and recurrent events

**What the problem is**: agents face multiple competing exit paths (employed /
retired / deceased); agents also re-enter (benefit re-claims). Current Cox
ignores this. Fine-Gray, Lunn-McNeil, and recurrent-event estimators exist
but are not in the catalog.

**Sufficient result**: a competing-risks + recurrent-event estimator family
with identification under declared censoring mechanisms, plus a diagnostic
for violation.

**Deliverable form**: estimator family + diagnostic + integration spec.

---

### 32.3. Open problem: marked point processes for spatial-temporal events

**What the problem is**: a crime has location, time, and mark (severity).
A claim has location, time, and mark (amount). Marked point processes handle
this but are not in the catalog.

**Sufficient result**: a marked-point-process estimator with identification
for mark-intensity separation, a conformal-style interval for event-rate
prediction, and integration with spatial Track 13.

**Deliverable form**: estimator + interval + integration spec.

---

### 32.4. Open problem: deep survival with calibrated intervals

**What the problem is**: DeepSurv, DeepHit, Cox-Time are deep-learning
survival estimators used in policy-adjacent domains (healthcare). None
ships, none has coverage guarantees on survival-function intervals.

**Sufficient result**: deep-survival wrappers with conformal survival
intervals (building on Track 2.1 conformal research) and a benchmark.

**Deliverable form**: wrappers + intervals + benchmark + integration spec.

---

## 33. Research Track 32 — Functional Data, Topological Data Analysis, and Geometric Representations {#33-research-track-32}

**Status in catalog**: no FDA, no TDA, no manifold learning with
faithfulness guarantees.

### 33.1. Open problem: functional data for longitudinal policy outcomes

**What the problem is**: longitudinal outcome trajectories (wage trajectories,
benefit-uptake curves) are functions, not vectors. Treating them as vectors
loses smoothness and over-parameterizes. FDA (functional PCA, functional
linear models) is the right tool but is absent.

**Sufficient result**: an FDA estimator family for at least three outcome
types (continuous, counts, binary) with identification and smoothing-
parameter-choice diagnostics.

**Deliverable form**: estimator family + diagnostics + integration spec for
`FunctionalResult`.

---

### 33.2. Open problem: persistent homology for policy data shape

**What the problem is**: TDA detects topological features (holes, voids,
connected components) in high-dim data. For policy (regional cohort
structures, multi-dimensional poverty geometry), these features encode
policy-relevant structure. TDA is unused in the catalog.

**Sufficient result**: a persistence-diagram estimator with stability
theorems (Cohen-Steiner et al.), a policy-relevant feature library, and
integration with clustering for structural-break detection.

**Deliverable form**: estimator + feature library + integration spec.

---

### 33.3. Open problem: manifold learning with causal faithfulness

**What the problem is**: manifold learning (UMAP, t-SNE, diffusion maps) is
used for policy-data visualization. Whether the embedded manifold preserves
the conditional-independence structure needed for downstream causal
inference is unstudied (partially covered by Track 12.6).

**Sufficient result**: faithfulness conditions for manifold learning on
policy data, a diagnostic, and a policy (refuse causal use below a
threshold).

**Deliverable form**: conditions + diagnostic + policy + integration spec
coupled to causal agenda.

---

### 33.4. Open problem: geometric deep learning for administrative graphs

**What the problem is**: administrative graphs (payment networks, supplier-
customer, firm-ownership) have rich geometry. Geometric deep learning is a
principled extension of GCN (Track 12) but is not in the catalog.

**Sufficient result**: geometric-DL estimators with identification under
declared graph-generation model classes, plus an integration with the
causal faithfulness diagnostic from Track 33.3.

**Deliverable form**: estimators + integration spec.

---

## 34. Research Track 33 — Anomaly, Fraud, and Administrative-Integrity Detection {#34-research-track-33}

**Status in catalog**: no anomaly-detection family; no fraud-specific
methods. Any such capability is outsourced.

> **Why this family matters**: administrative systems (benefit programs,
> tax collection, procurement) leak to fraud and error. Integrity detection
> with fairness constraints is a government responsibility that must not be
> implemented without the causal-fairness framework from Track 14.3.

### 34.1. Open problem: benefit-abuse detection with causal fairness

**What the problem is**: fraud-detection ML systems deployed in benefit
programs have produced fairness scandals. A production-grade detector must
bound disparate-impact across protected groups while maintaining
detection power.

**Sufficient result**: a detection estimator family with pareto-frontier
characterization of detection power × fairness gap, with a declared minimum
fairness threshold and a refusal when the frontier cannot meet both.

**Deliverable form**: estimator + frontier + threshold + integration spec
coupled to Track 14.3.

---

### 34.2. Open problem: audit-sampling with detection bounds

**What the problem is**: administrative audit uses random sampling to
estimate misstatement rates. Adaptive sampling (importance sampling on
risk indicators) is more efficient but biases the estimate. Current methods
are either unbiased-inefficient or efficient-biased.

**Sufficient result**: an adaptive audit-sampling protocol with bias
correction and asymptotic variance bounds, plus a robustness diagnostic for
the adaptive-sampling model.

**Deliverable form**: protocol + correction + diagnostic + integration
spec.

---

### 34.3. Open problem: drift-coupled anomaly detection

**What the problem is**: a static anomaly detector drifts out of calibration
as the baseline changes. Coupling the detector to Track 14.7 drift detection
requires a principled update rule that preserves detection-power bounds.

**Sufficient result**: a detector-update rule with preserved power bounds
under declared drift classes.

**Deliverable form**: rule + bounds + integration spec.

---

### 34.4. Open problem: whistleblower-safe reporting infrastructure

**What the problem is**: anomaly detectors used in administrative integrity
must protect whistleblowers and protected-class members from retaliation. The
reporting-infrastructure design is a privacy + fairness compound problem
(Tracks 14.3, 22, 23).

**Sufficient result**: a reporting protocol with provable whistleblower
protection and audit trails, plus a governance policy for when human review
is required.

**Deliverable form**: protocol + policy + integration spec.

---

## 35. Research Track 34 — Extreme-Value Theory, Tail Risk, and Policy Stress Testing {#35-research-track-34}

**Status in catalog**: classical inequality measures in `catalog/distributional/`;
GARCH in `catalog/econometrics/`. No multivariate EVT, no copula tail-
dependence, no scenario-generation for stress testing.

### 35.1. Open problem: multivariate extreme-value theory for policy tails

**What the problem is**: joint tail risks (simultaneous fiscal + labor-
market + health shocks) require multivariate EVT. Univariate EVT is known
but not in catalog; multivariate is under-specified in the literature for
policy-relevant dimension (d ≥ 5).

**Sufficient result**: multivariate-EVT estimators for declared tail-
dependence classes (extreme-value copulas, Pickands dependence function), a
benchmark, and a fallback to univariate when joint estimation fails.

**Deliverable form**: estimators + benchmark + fallback + integration spec
for `TailRiskBundle`.

---

### 35.2. Open problem: copula tail dependence for policy-relevant scenarios

**What the problem is**: tail-dependence coefficients are poorly estimated
with small samples; they determine whether simultaneous shocks are plausible.
Standard estimators have large bias at the tails.

**Sufficient result**: a tail-dependence estimator family with bias
correction under declared copula families and a sample-size guideline.

**Deliverable form**: estimators + guideline + integration spec.

---

### 35.3. Open problem: scenario generation with coverage

**What the problem is**: stress tests use scenarios (adverse, severely
adverse, reverse). Scenario construction today is expert judgment; there is
no coverage statement about "does this set of scenarios cover the 99th
percentile of joint shocks?".

**Sufficient result**: a scenario-generation protocol with coverage
guarantees on a declared joint-shock distribution, plus a refusal when
coverage is infeasible under the specified budget.

**Deliverable form**: protocol + guarantee + refusal + integration spec.

---

### 35.4. Open problem: worst-case fiscal scenarios under GE feedback

**What the problem is**: worst-case fiscal scenarios require combining
Track 7.1 (GE welfare uncertainty) with Track 8.1 (DRO) and tail dependence
from Track 34.1. No unified framework exists.

**Sufficient result**: an integration spec + a solver that combines DRO,
EVT, and GE uncertainty into a single worst-case fiscal scenario with a
machine-checkable certificate.

**Deliverable form**: solver + certificate + integration spec (cross-track
compound).

---

## 36. Research Track 35 — Agent-Sim, Value-Function Iteration, and Dynamic Decision Uncertainty {#36-research-track-35}

**Status in catalog**: `polisyos.foundry.agent_sim/` ships VFI (`vfi.py`),
mechanisms, temporal, metrics — but the module is not in the research agenda.
Value-function iteration, discrete-continuous choice, dynamic games exist
in code without typed contracts or research tracks.

> **Why this track matters**: agent-sim is the bridge between static
> mechanism design (Track 9) and dynamic policy (Tracks 11, 28). Its VFI
> implementation has no UQ contract and no identification story.

### 36.1. Open problem: VFI error bounds under policy-function iteration

**What the problem is**: policy-function iteration solves Bellman equations
approximately; error bounds (McGrattan, Judd) are known but are not
exposed as certificates. Agents acting on an unreliable value function
produce biased dynamic policy recommendations.

**Sufficient result**: runtime error bounds for VFI under declared
discretization and convergence parameters, with a fallback when the bound
exceeds tolerance.

**Deliverable form**: bounds + fallback + integration spec for
`ValueFunctionResult`.

---

### 36.2. Open problem: dynamic games with identification

**What the problem is**: agent-sim mechanisms compose; when they do, the
resulting object is a dynamic game whose equilibrium may be non-unique
(couples to Track 7.3). Current code picks an equilibrium implicitly.

**Sufficient result**: existence / multiplicity conditions for dynamic
games with the mechanisms in use, plus a reporting format that carries
multiple equilibria.

**Deliverable form**: conditions + format + integration spec.

---

### 36.3. Open problem: uncertainty propagation through VFI chains

**What the problem is**: parameter uncertainty propagates through VFI
non-linearly. Current VFI output has no uncertainty envelope.

**Sufficient result**: an uncertainty-propagation framework for VFI coupled
to the envelope algebra (Track 18.1), with a simulation benchmark.

**Deliverable form**: framework + benchmark + integration spec shared with
Track 18.

---

### 36.4. Open problem: discrete-continuous choice estimation

**What the problem is**: policy choices are often discrete (enroll/not) +
continuous (how much to work). Rust-style nested fixed-point methods handle
this but are not in the catalog.

**Sufficient result**: a discrete-continuous choice estimator with
identification conditions, a consistent estimator, and a fallback under
ordered alternatives.

**Deliverable form**: estimator + integration spec coupled to Track 11.

---

# Part IV — Cross-Family Extensions to Tracks 1–14 {#37-part-iv-extensions}

Gaps in the original fourteen tracks that were not covered as sub-problems
but belong in a SOTA agenda. Each extension follows the sub-problem format
and integrates with its home track's integration target.

### IV.T1 — Bayesian extensions

- **T1.6 Bayesian model selection with calibrated WAIC/LOO/stacking**:
  model-selection methods have known pathologies (WAIC underperforms under
  influential observations, stacking is point estimate of stacking weight).
  *Sufficient result*: calibrated model-selection benchmark + integration
  spec for `PosteriorResult.selection_diagnostic`.
- **T1.7 Bayesian optimization as active learning for expensive simulators**:
  couples to Track 1.5 and Track 10.3. *Sufficient result*: BO algorithm
  with regret bounds and integration with SBI budget.

### IV.T2 — ML extensions

- **T2.6 Deep survival with calibrated intervals**: see Track 31.4.
- **T2.7 Competing risks and recurrent events in the ML family**: see Track
  31.2.
- **T2.8 Ordinal regression with proper scoring rules**: catalog has no
  proper ordinal-regression methods; policy ordinal outcomes (satisfaction,
  health status) are common. *Sufficient result*: ordinal-regression family
  with calibrated cumulative-probability forecasts.

### IV.T3 — Forecasting extensions

- **T3.6 Probabilistic forecasting (beyond UQ wrapping)**: quantile
  regression forecasts, distributional regression (GAMLSS). *Sufficient
  result*: estimator family + `ForecastingUncertaintyBundle.quantile_curves`.
- **T3.7 Forecast combination and expert aggregation**: catalog has no
  formal combination (Bates-Granger, Bayesian model averaging for
  forecasts). *Sufficient result*: combination estimator + no-arbitrage
  bounds + integration spec.
- **T3.8 Nowcasting / real-time dating**: see Track 28.3.

### IV.T4 — Econometrics extensions

- **T4.6 Local projections vs VAR under misspecification**: LP and VAR
  impulse responses disagree under non-invertible MA shocks. *Sufficient
  result*: a misspecification diagnostic + readiness policy selecting LP vs
  VAR.
- **T4.7 Multiple-hypothesis-testing corrections in policy econometrics**:
  policy studies routinely test 10–100 hypotheses with no correction.
  *Sufficient result*: FDR / FWER procedure library + integration spec for
  `EconometricResult.mht_correction_applied`.
- **T4.8 DSGE and structural VAR**: see Track 28.

### IV.T5 — Survey extensions

- **T5.6 Adaptive / responsive survey design**: adaptive surveys adjust
  sampling in response to partial data; bias implications are under-
  characterized. *Sufficient result*: adaptive-design estimator + integration
  spec.
- **T5.7 Privacy-preserving survey tools (DP surveys)**: see Track 22.2.

### IV.T6 — Distributional extensions

- **T6.6 Wealth distributions with top-coding and survey-administrative
  fusion**: wealth surveys top-code; administrative data covers tail.
  Fusion requires measurement-error reconciliation. *Sufficient result*:
  fusion estimator + top-code correction + integration spec.
- **T6.7 Chain-weighted / hedonic distributional indices for inflation
  heterogeneity**: different groups face different inflation. *Sufficient
  result*: group-specific deflator estimator + integration spec for
  `DistributionalBundle.group_deflator`.

### IV.T7 — Policy / welfare extensions

- **T7.6 Real options and optionality valuation for policy flexibility**:
  irreversibility and waiting value are absent. *Sufficient result*:
  real-options estimator for at least one policy class (infrastructure
  investment) + integration spec.
- **T7.7 Sequential / multi-period welfare aggregation**: multi-period
  welfare requires time-discounting assumptions; time-inconsistent
  preferences break standard aggregation. *Sufficient result*: multi-period
  estimator with hyperbolic-discounting sensitivity + integration spec.

### IV.T8 — Optimization extensions

- **T8.6 Integer programming for combinatorial policy allocation**: catalog
  has MILP but not specialized branch-and-cut for policy structure
  (facility location, scheduling with fairness). *Sufficient result*:
  specialized solver + integration spec.
- **T8.7 Quadratic assignment / facility location with fairness**: coupled
  fairness-constrained optimization. *Sufficient result*: fairness-aware
  solver + certificate + integration spec coupled to Track 14.3.

### IV.T9 — Mechanism extensions

- **T9.6 Dynamic mechanism design**: mechanisms evolve over time (policy
  reforms); dynamic BIC is under-developed. *Sufficient result*: dynamic
  mechanism family with BIC + integration spec coupled to Track 35.
- **T9.7 Matching markets (see Track 30)**.

### IV.T10 — Simulation extensions

- **T10.6 Validated SDE and ODE solvers**: catalog simulation methods use
  ad-hoc integrators. Validated numerics (Track 21.1) for SDE/ODE gives
  coverage over trajectories. *Sufficient result*: validated SDE/ODE
  solver + integration spec.

### IV.T11 — Microsim extensions

- **T11.6 Static aging with demographic consistency**: aging a sample
  forward requires demographic transitions with consistency across
  states. *Sufficient result*: demographic-consistency estimator +
  integration spec.

### IV.T12 — Network extensions

- **T12.7 Network motif and higher-order structure detection**: motifs
  (triangles, cliques, k-stars) are policy-relevant structural signatures.
  Current catalog has no motif estimator. *Sufficient result*: motif-
  counting estimator with CI and integration spec.

### IV.T13 — Spatial extensions

- **T13.7 Spatial point processes (see Track 31.3)**.

### IV.T14 — Validation and sensitivity extensions

- **T14.8 Meta-evaluation (cross-family benchmarking)**: validation of the
  validation layer itself. *Sufficient result*: a meta-evaluation protocol
  that benchmarks the six-judge stack against hidden ground truth, plus a
  readiness-tier for the judges themselves.
- **T14.9 Replication across toolchains**: PolicyOS vs R/Stata/Python
  alternates for the same estimator. A policy result that cannot be
  replicated in at least one peer toolchain is a red flag. *Sufficient
  result*: a replication protocol + tolerance library + integration spec
  coupled to Tracks 16, 21.

---

## 38. Dependency and Parallelization Map {#16-dependency-and-parallelization-map}

> **Relation to Part 0.** This section is the **dependency evidence** behind
> the [Phased Execution Plan](#part-0-phased-execution). The lane analysis
> in §16.3 is the direct ancestor of the phase ordering — each lane in
> §16.3 is realised by an ordered pair or triple of phases (see the phase
> summary table in [§Phase Summary](#phase-summary)). If you want the
> *operational schedule*, read Part 0; if you want the *reasoning about
> why the schedule looks the way it does*, read this section.

### 16.1. What can be started immediately

All tracks can be started as theoretical investigations. The key rule is that
they must live as `FrontierSketch` objects with `max_readiness = PROOF_ONLY`
(equivalently `DecisionReadiness = RESEARCH_ARTIFACT`) and cannot influence
production until they graduate.

The most independent tracks (minimal dependencies on other research):

- **Track 1** (Bayesian): independent; integration target is `PosteriorResult`.
- **Track 2** (ML): independent; integration targets are
  `PredictionResult` and `PredictionIntervalResult`.
- **Track 3** (Forecasting): independent; needs a new
  `ForecastingUncertaintyBundle` contract as integration target.
- **Track 8** (Optimization): independent; integration target is
  `OptimizationResult`.
- **Track 9** (Mechanism): independent; integration target is new
  `IncentiveCompatibilityCertificate`.
- **Track 14** (Validation & sensitivity): independent; integration targets
  are new `ValidationReport` and `SensitivityAnalysisBundle` contracts.

### 16.2. Tracks with strong cross-family dependencies

| Track | Depends on |
|-------|-----------|
| Track 4 (econometrics under dependence) | Shares dependence diagnostic primitive with Track 12 (network) and Track 13 (spatial). A single primitive should serve all three. |
| Track 5 (survey SAE) | Same dependence primitive as Track 4 + Track 13. |
| Track 5.4 (MNAR taxonomy) | Mirrors Causal Track 11 (recoverability). |
| Track 6 (distributional bounds) | Dual of Causal Track 5 (distributional OT). |
| Track 7 (welfare) | Track 8 (optimization) provides DRO primitive; Track 11 (microsim) provides fiscal-feedback primitive. |
| Track 7.3 (equilibrium) | Causal Track 5.4 (MFG) + Track 11.5 (finite-N correction). |
| Track 9.4 (coupled mechanisms) | Causal Track 5 (strategic). |
| Track 11 (microsim) | Track 5 (survey) is upstream for all microsim calibration; Track 8.5 (inverse optimization) shares identification primitive. |
| Track 12 (network) | Causal Track 9 (topology) is downstream consumer; Causal Track 8 (latent) shares the embedding-faithfulness question. |
| Track 13 (spatial) | Causal Track 6 (abstraction) for MAUP; Causal Track 10 (proximal) for spatial confounding; Causal Track 3.4 (DSCM) for space-time. |
| Track 14 (validation) | Consumes output from every other track; its contracts should be designed to be generic across families. |

### 16.3. Dependency chains that affect production integration

```text
HONEST UNCERTAINTY LANE:
Track 1 (truthfulness tier) + Track 3.1 (forecast intervals) + Track 14.2 (calibration)
    -> uniform UQ contract across Bayesian, Forecasting, ML
    -> every downstream consumer gets typed UQ or typed refusal

GOVERNMENT DATA LANE:
Track 5.1 (double-robust design+missing) + Track 5.4 (MNAR taxonomy)
    -> SurveyQualityCertificate
    -> Track 11.1 (microsim identifiability) consumes it
    -> Track 12.4 (network partial obs) + Track 13.6 (spatial SAE) consume it

DECISION LAYER LANE:
Track 7 (welfare uncertainty) + Track 8 (DRO) + Track 9 (IC certificates)
    -> WelfareBundle + OptimizationResult.ambiguity_certificate + IC certificate
    -> every policy recommendation carries assumption vectors and refusal
       mode, never a bare scalar

TOPOLOGY LANE:
Track 12 (network) + Track 13 (spatial) -> Causal Track 9 (hypergraph)
    -> interference certificate for group-level spillovers

DYNAMICS LANE:
Track 3.3 (regime switching) + Track 11.5 (fiscal feedback) + Causal Track 3.4 (DSCM)
    -> dynamic causal + dynamic forecasting + dynamic microsim
    -> system transitions from "static snapshot" to "time-aware policy engine"

DEPENDENCE PRIMITIVE LANE:
Track 4.2 (cross-sectional dependence) + Track 5.2 (SAE cross-area) + Track 13.2 (spatial confounding)
    -> single dependence-diagnostic primitive
    -> serves three tracks and two families

CROSS-CUTTING INFRASTRUCTURE LANE (v1.1):
Track 15 (advisor calibration) + Track 16 (backend determinism) + Track 18 (envelope algebra)
    -> every query can pick a method, replay it, and compose its uncertainty
    -> gates every family in Parts I and III

PRIVACY + FEDERATION LANE (v1.1):
Track 22 (DP + synthetic + federated) + Track 23 (TEE attestation)
    + Track 5 (survey) + Track 27 (EO geographic privacy)
    -> cross-jurisdictional policy work with measurable leakage bounds

DECISION-TIME LANE (v1.1):
Track 27 (RL / OPE) + Track 28 (structural macro) + Track 29 (evidence synthesis)
    + Track 7 (welfare) + Track 8 (DRO)
    -> sequential decision, structural macro, and external evidence all
       flow into the same WelfareBundle + OptimizationResult

AUDIT + REPRODUCIBILITY LANE (v1.1):
Track 16 (backend determinism) + Track 21 (verified numerics)
    + Track 24 (LLM lifecycle) + Track 23 (benchmark infrastructure)
    + Track 14.8 (meta-evaluation) + Track 14.9 (replication)
    -> every shipped artifact has a replay certificate, a holdout verdict,
       and a cross-toolchain replication check
```

### 16.4. Part II and III tracks — cross-dependency table

| Track | Depends on / enables |
|-------|----------------------|
| Track 15 (advisor) | Consumes runtime tier from Tracks 1.1, 2.1, 3.1, 14.2; consumed by every query. |
| Track 16 (determinism) | Enables Tracks 21 (verified numerics), 24 (benchmark). |
| Track 17 (cost/energy) | Consumes Track 18 (cost uncertainty = envelope); feeds Track 8.1 (DRO). |
| Track 18 (envelope) | Consumes Tracks 1, 2, 3, 5, 14; feeds Tracks 7, 8, 17, 35. |
| Track 19 (calibration) | Consumes causal Track 2 (identifiability); feeds Tracks 1, 11, 28. |
| Track 20 (streaming) | Enables Tracks 14.7, 15, 33.3. |
| Track 21 (verified numerics) | Enables Tracks 16.4, 22.1, 31.1, 35.4. |
| Track 22 (DP + federated) | Enables Tracks 5.7, 27.3, 33.4. |
| Track 23 (benchmarks) | Consumed by every anti-swamp benchmark proxy rule. |
| Track 24 (LLM) | Enables Tracks 25, 26.4, 29.3. |
| Track 25 (NLP) | Depends on Tracks 22, 24. |
| Track 26 (EO) | Depends on Tracks 13.1, 22. |
| Track 27 (RL/OPE) | Depends on causal Track 5; feeds Track 14.3. |
| Track 28 (macro) | Depends on Tracks 1.3, 3.1, 29. |
| Track 29 (evidence) | Depends on causal Track 13 (transportability), Track 24.3. |
| Track 30 (matching) | Depends on Track 9. |
| Track 31 (point processes) | Feeds Tracks 13.7, 32.3. |
| Track 32 (FDA/TDA) | Depends on Track 12.6, 33.3. |
| Track 33 (anomaly) | Depends on Tracks 14.3, 14.7, 22. |
| Track 34 (EVT) | Depends on Tracks 7.1, 8.1. |
| Track 35 (agent-sim VFI) | Depends on Tracks 9, 11, 18. |

---

## 39. Anti-Swamp Governance for Non-Causal Research Tracks {#17-anti-swamp-governance}

Research tracks are more vulnerable to becoming research swamps than
engineering tasks. The following rules apply specifically to the non-causal
research tracks in this document. They mirror the causal agenda's rules and
extend them with considerations specific to the method families here.

### 17.1. Benchmark proxy requirement

A research track that has not produced a benchmark proxy after 2 phases loses
its research budget and is downgraded to a "recorded open problem" state.

A **benchmark proxy** for a non-causal track is one of:

- a synthetic dataset on which the claimed result (if true) would produce a
  measurable signal — e.g., a coverage-failure benchmark for Track 1.1, a
  MAUP-sensitivity benchmark for Track 13.1;
- a counterexample that would be ruled out if the claimed theorem holds —
  e.g., an unidentifiable ABM moment pattern for Track 11.1;
- a sentinel case that can falsify a wrong implementation — e.g., a
  deliberately non-stationary forecast that a naïve interval estimator will
  under-cover on, for Track 3.1.

### 17.2. Contract-first rule

Unlike the causal agenda, this document contains families whose foundational
typed contracts are missing (`ForecastingUncertaintyBundle`,
`ValidationReport`, `SensitivityAnalysisBundle`, `DistributionalBundle`,
`WelfareBundle`, `SurveyQualityCertificate`, `MobilityReport`,
`IncentiveCompatibilityCertificate`, `ExplanationBundle`,
`ShiftDiagnosticReport`, `TransferDiagnostic`). A research track that depends
on one of these missing contracts must declare its contract shape as part of
`required_for_promotion`. A track that produces a theorem without a receiving
contract cannot graduate, because downstream consumers have nowhere to read
the result.

Appendix B lists the missing contracts, their target families, and the tracks
that depend on each.

### 17.3. FrontierSketch integration rule

All research artifacts must be integrated as `FrontierSketch` with:

- `max_readiness = PROOF_ONLY`
- `ttl_phases` set to a concrete number (default: 3 phases)
- `required_for_promotion` populated before work begins, not after, including
  any missing contract that the track depends on.

A research artifact that cannot state its `required_for_promotion` checklist
before starting is not ready to start.

### 17.4. Parallelism without contamination

Research tracks may be run in parallel with engineering tracks. The
contamination rules:

1. A research sketch may not influence a production recommendation, directly
   or indirectly.
2. A research sketch may not be cited as evidence for raising a readiness cap.
3. A research artifact in `PROOF_ONLY` may be exported for research consumers
   with explicit "not for decision support" labelling, but may not enter the
   policy analyst workflow.
4. A research track that has produced a benchmark proxy may request a hidden
   holdout evaluation through the judge stack. The holdout verdict is the
   primary signal for graduation, not the researcher's assessment.

### 17.4a. Cross-cutting-track propagation rule (v1.1)

A Part II cross-cutting track (Tracks 15–24) that produces a result which
alters a shared primitive (advisor ranking, determinism tier composition,
envelope algebra, calibration protocol, benchmark harness) must publish an
integration-impact statement listing every Part I / Part III track whose
integration spec depends on the primitive. The shared primitive is not
allowed to graduate until every dependent track has acknowledged the impact
and either revised its integration spec or declared that the change is
neutral.

### 17.4b. New-family gating rule (v1.1)

A Part III new-family track (Tracks 25–35) may not introduce a catalog stub
under the proposed paths in Appendix D until:

1. a benchmark proxy exists (17.1);
2. a receiving contract is drafted as part of `required_for_promotion`;
3. a cross-family dependency list is registered — every Part I or Part II
   track that must be consulted before the new family can invoke its primitives;
4. a `FamilyReadinessLadder` entry exists, defaulting to `PROOF_ONLY` with a
   single elevation condition specified.

New families that skip any of these steps will have their stub PRs rejected
automatically. The intent is to prevent the catalog from accreting half-
complete families that look operational but have no theory backing them.

### 17.5. Hypothesis discipline

Each research track entry in this document is a hypothesis about what can be
proved or calibrated. As research progresses, the hypothesis may be:

- **confirmed**: the theorem is proved or the benchmark is calibrated;
  integration can proceed;
- **narrowed**: the result holds in a smaller scope than initially claimed;
  scope must be updated in this document and the integration spec adjusted;
- **refuted**: an impossibility result or counterexample is found; the
  counterexample goes to the `CounterexampleRegistry` and the track is closed
  or redirected;
- **deferred**: no progress in 2 phases; track enters "recorded open problem"
  state.

All four outcomes are treated as research contributions. Refutation is not
failure — it clarifies the system's honest claims.

---

## 40. Research Economics and Kill Rules {#18-research-economics-and-kill-rules}

### 18.1. Research budget allocation

- Engineering tasks in T0–T3 of `FOUNDRY_REMEDIATION_PLAN.md` have priority
  and get first claim on engineering budget.
- Research tracks run on a separate, capped research budget.
- The research budget fraction is determined by the economics score
  (moat_depth × policy_relevance × integration_premium) of each track.
- Research tracks in "recorded open problem" state receive maintenance-only
  budget (sufficient to preserve the benchmark proxy and counterexample
  library, nothing more).

### 18.2. Research track economic scores

| Track | Moat depth | Policy relevance | Research difficulty | Priority |
|-------|-----------|------------------|---------------------|---------|
| Track 1 (Bayesian + posterior) | high | very high | medium | highest |
| Track 3 (Forecasting UQ) | high | very high | medium | highest |
| Track 5 (Survey + SAE) | high | very high | medium | highest |
| Track 11 (Microsim calibration) | high | very high | medium-high | highest |
| Track 14 (Validation & sensitivity) | medium-high | very high | medium | highest |
| Track 4 (Econometrics under dependence) | high | high | medium-high | high |
| Track 6 (Distributional bounds) | high | very high | medium-high | high |
| Track 7 (Welfare under GE uncertainty) | very high | very high | high | high |
| Track 8 (Optimization under uncertainty) | high | high | medium-high | high |
| Track 12 (Network peer effects) | very high | high | high | high |
| Track 13 (Spatial MAUP + interference) | very high | high | high | high |
| Track 2 (ML + representation) | medium-high | medium-high | medium | medium |
| Track 10 (SBI + ABM) | high | medium-high | high | medium |
| Track 9 (Mechanism design) | very high | high | very high | medium-long horizon |
| Track 15 (Advisor calibration) | very high | very high | medium | highest |
| Track 16 (Backend determinism) | very high | very high | medium-high | highest |
| Track 18 (Envelope algebra) | very high | very high | medium | highest |
| Track 19 (Calibration subsystem) | high | very high | medium-high | highest |
| Track 23 (Benchmark infrastructure) | medium-high | very high | medium | highest |
| Track 17 (Cost / energy) | high | high | medium | high |
| Track 22 (DP + synthetic + federated) | very high | very high | high | high |
| Track 20 (Streaming / online) | medium-high | high | medium | high |
| Track 21 (Verified numerics + PPL) | very high | medium-high | high | high |
| Track 24 (LLM lifecycle) | medium-high | medium-high | high | medium |
| Track 25 (NLP / regulatory) | very high | very high | medium-high | highest |
| Track 27 (RL / OPE) | very high | very high | high | highest |
| Track 29 (Evidence synthesis) | high | very high | medium | highest |
| Track 28 (DSGE / HANK) | very high | high | very high | high |
| Track 30 (Matching markets) | very high | high | high | high |
| Track 34 (EVT / stress testing) | high | very high | medium-high | high |
| Track 26 (Earth-observation) | high | high | medium-high | high |
| Track 33 (Anomaly / fraud) | medium-high | high | medium-high | high |
| Track 31 (Point processes) | medium-high | medium-high | medium-high | medium |
| Track 32 (FDA / TDA) | high | medium | high | medium |
| Track 35 (Agent-sim VFI) | medium-high | medium-high | medium-high | medium |

### 18.2bis. Compound effects added in v1.1

- **Tracks 15 × 16 × 18 (advisor × determinism × envelope)**: the three
  infrastructure tracks jointly provide "pick a method, replay it, compose
  its uncertainty". Without all three, every per-family result in Parts I
  and III is ungovernable. The compound premium is higher than the sum of
  the three individual moats, because no family can ship SOTA without all
  three present.
- **Tracks 22 × 23 × 24 (privacy × benchmark × LLM lifecycle)**: the
  audit-reproducibility lane. Shipping research artifacts to production
  requires each of these; together they allow the six-judge stack to run.
- **Tracks 25 × 27 × 29 (NLP × RL/OPE × evidence synthesis)**: the
  decision-learning compound. Extract regulatory text, learn from deployed
  rules via OPE, synthesize external evidence — the combination is what a
  SOTA decision-support engine needs, and no single track substitutes.
- **Tracks 17 × 18 × 21 (cost × envelope × verified numerics)**: the
  truthful-compute compound. Cost-aware plans that are also deterministic
  and forward-error-bounded close the loop between performance and
  correctness.
- **Tracks 28 × 34 (structural macro × EVT)**: fiscal-stress compound.
  Structural macro gives mechanism; EVT gives tails; the compound is the
  only defensible basis for sovereign-level stress testing.

### 18.3. Kill rules for research tracks

Consistent with the engineering plan's kill rules:

1. A research track with no benchmark proxy after 2 phases is downgraded to
   "recorded open problem".
2. A research track where the core hypothesis is refuted is closed; the
   counterexample is registered.
3. A research track that has not graduated a `FrontierSketch` to a full
   `FrontierArtifact` after the `ttl_phases` limit is automatically archived.
4. Kill decisions require documented rationale and human review.
5. A killed research track may be reopened if the theoretical landscape
   changes (new external results) or if new benchmark opportunities appear.

### 18.4. Integration premium for research results

A research result that unlocks a production implementation is worth more than
its isolated moat contribution, because it also amplifies the value of the
already-scoped engineering families. Compound effects to factor in:

- **Track 1 (truthfulness) × Track 3 (forecast UQ) × Track 14 (calibration)**:
  unifies UQ across Bayesian, ML, forecasting; every downstream consumer
  inherits calibrated intervals at once.
- **Track 5 (survey + SAE) × Track 11 (microsim calibration)**: together
  resolve the credibility of any tax-benefit microsim pipeline end-to-end.
- **Track 12 (network) × Track 13 (spatial) × Causal Track 9 (hypergraph)**:
  interference-aware policy across network, spatial, and hypergraph topologies
  — a compound that is absent from every competing policy library.
- **Track 4 × Track 5 × Track 13 (dependence primitive)**: a single
  cross-unit-dependence diagnostic serves three tracks and two families; the
  integration premium on a shared primitive is higher than its per-track value.
- **Track 7 (welfare) × Track 8 (DRO) × Track 9 (IC)**: upgrades the decision
  layer from point recommendation to certified recommendation with refusal
  mode.

These compound effects should factor into research budget allocation decisions.

---

## 41. Appendix A: Open Problem Catalog {#19-appendix-a}

A compact reference of all open problems in this document.

| Track | Problem | Unlocks |
|-------|---------|---------|
| T1.1 | Truthfulness tiering for approximate posteriors | `PosteriorResult.truthfulness_tier` |
| T1.2 | Production HMC/NUTS with determinism guarantees | `PosteriorResult` determinism gate |
| T1.3 | Prior robustness and prior-predictive check gates | `PosteriorResult.prior_sensitivity` |
| T1.4 | Multimodality and posterior geometry detection | `PosteriorResult.multimodality_status` |
| T1.5 | SBI for intractable / regime-shifted simulators | SBI method metadata + `PosteriorResult.simulator_diagnostic_ref` |
| T2.1 | UQ for deep tabular and graph models | `PredictionIntervalResult.conditional_coverage_diagnostic` |
| T2.2 | Distribution-shift detection | new `ShiftDiagnosticReport` contract |
| T2.3 | Model explanation with bounded infidelity | new `ExplanationBundle` contract |
| T2.4 | Multi-task learning across jurisdictions | `PredictionResult.transfer_diagnostic` |
| T2.5 | Foundation-model policy analysis calibration | readiness cap enforcement for FM methods |
| T3.1 | Forecast-uncertainty contract + calibrated intervals | new `ForecastingUncertaintyBundle` |
| T3.2 | Hierarchical forecast reconciliation | `ForecastingUncertaintyBundle.reconciliation_certificate` |
| T3.3 | Regime-switching forecasting | `RegimeShiftForecastBundle` extension |
| T3.4 | Neural forecasters with trust-region UQ | `ForecastingUncertaintyBundle.source_method` |
| T3.5 | Forecast-as-treatment semantics | integration with causal `ProofBundle` |
| T4.1 | Post-selection inference for high-dim IV | `EconometricResult.coverage_guarantee_tier` |
| T4.2 | Dynamic panel under cross-sectional dependence | `EconometricResult.cross_sectional_dependence_diagnostic` |
| T4.3 | Semiparametric efficiency under complex survey | shared survey / econometrics efficiency contract |
| T4.4 | Threshold models with endogenous thresholds | threshold-identification certificate |
| T4.5 | Heterogeneous / regime-switching GARCH | volatility-interval coverage contract |
| T5.1 | Double-robust under design + MNAR | new `SurveyQualityCertificate` |
| T5.2 | SAE under cross-area dependence | SAE variance-component contract |
| T5.3 | Calibration under auxiliary measurement error | `CalibrationWeights.auxiliary_uncertainty` |
| T5.4 | MNAR taxonomy for administrative missingness | `SurveyQualityCertificate.missingness_class` |
| T5.5 | Raking convergence + positivity diagnostics | weighting convergence contract |
| T6.1 | Sharp bounds on counterfactual distributional functionals | new `DistributionalBoundsBundle` |
| T6.2 | Mobility under panel attrition | new `MobilityReport` contract |
| T6.3 | Multidimensional poverty with ordinal dimensions | ordinal-robust poverty index family |
| T6.4 | Inequality decomposition under endogenous composition | causal-decomposition certificate |
| T6.5 | Long-horizon mobility under latent heterogeneity | latent-heterogeneity mobility contract |
| T7.1 | Welfare under GE uncertainty | new `WelfareBundle.ge_uncertainty_ref` |
| T7.2 | State-dependent social welfare weights | `WelfareBundle.social_weight_ref` |
| T7.3 | Equilibrium existence / multiplicity under shocks | multi-equilibrium reporting contract |
| T7.4 | MCDA consensus under preference disagreement | MCDA stability + refusal certificate |
| T7.5 | Joint behavioral-fiscal incidence channel decomposition | `WelfareBundle.channel_decomposition_ref` |
| T8.1 | Stochastic programming under distributional ambiguity | `OptimizationResult.ambiguity_certificate` |
| T8.2 | Bilevel with nonconvex follower | bilevel global-optimality certificate |
| T8.3 | Robust set adequacy + deadweight tradeoff | robust-set calibration contract |
| T8.4 | Multi-level (3+) hierarchical optimization | multi-level solver contract |
| T8.5 | Inverse optimization for behavioral calibration | inverse-optimization identification contract |
| T9.1 | IC/IR machine-checkable certificate | new `IncentiveCompatibilityCertificate` |
| T9.2 | Bayesian mechanism design under private types | BIC-certified mechanism family |
| T9.3 | Auctions under reserve-price uncertainty | auction format recommendation contract |
| T9.4 | Coupled mechanisms / correlated equilibrium | mechanism-composition certificate |
| T9.5 | Welfare-loss bounds vs first-best | mechanism welfare-loss bound field |
| T10.1 | Heterogeneous-agent ABM identifiability | `SimulationResult.identifiability_diagnostic` |
| T10.2 | Bifurcation and attractor analysis | multi-attractor reporting format |
| T10.3 | Budget-minimizing SBI for expensive simulators | SBI + causal `ProofBundle` integration |
| T10.4 | Coupled discrete-event + ABM semantics | coupled-dynamics contract |
| T10.5 | Mean-field finite-N correction | MFG-scaling certificate |
| T11.1 | Elasticity identifiability from microdata | microsim-identifiability certificate |
| T11.2 | Nonlinear GMM calibration | `ReweightingResult.target_compatibility` |
| T11.3 | Dynamic microsim validation against panels | `DynamicMicrosimResult.validation_diagnostic` |
| T11.4 | MNAR sensitivity for income imputation | imputation MNAR-bound contract |
| T11.5 | Fiscal-feedback-consistent behavioral response | fixed-point convergence contract |
| T12.1 | Manski reflection-problem identification | `NetworkResult.peer_effect_decomposition` |
| T12.2 | Strategic network formation | network-formation identification contract |
| T12.3 | ERGM / SBM causal stratification | ERGM/SBM contract |
| T12.4 | Network identification under partial observability | `NetworkResult.missingness_assessment` |
| T12.5 | Temporal / dynamic graph causality | dynamic-graph causal contract |
| T12.6 | Network embedding fidelity | embedding-faithfulness diagnostic |
| T13.1 | Aggregation-invariant spatial effects (MAUP) | `SpatialResult.maup_invariance_certificate` |
| T13.2 | Spatial confounding + proximal identification | spatial proximal certificate |
| T13.3 | Spatial / areal interference identification | spatial interference certificate |
| T13.4 | Geostatistical extremes under spatial dependence | extreme-value spatial envelope |
| T13.5 | Space-time dynamical causal inference | space-time DSCM contract |
| T13.6 | Small-area spatial smoothing under causal constraints | causal-smoothing contract |
| T14.1 | Formal statistical testing for metric comparisons | new `ValidationReport` |
| T14.2 | Calibration diagnostics for probabilistic predictions | `ValidationReport.calibration_diagnostic` |
| T14.3 | Fairness auditing with causal semantics | `ValidationReport.fairness_audit` |
| T14.4 | Sensitivity with dependent / correlated inputs | new `SensitivityAnalysisBundle` |
| T14.5 | Quantile and distributional sensitivity | `SensitivityAnalysisBundle.quantile_indices` |
| T14.6 | Uncertainty on sensitivity indices themselves | sensitivity CI contract |
| T14.7 | Drift and performance-degradation detection | runtime drift certificate |
| T15.1 | Calibrated regret bounds for advisor | `MethodAdvisorResult.calibrated_regret_certificate` |
| T15.2 | Truthfulness-tier consistency across advisor and runtime | advisor/runtime tier reconciliation |
| T15.3 | Cross-method disagreement diagnostic | `MethodAdvisorResult.cross_method_consensus` |
| T15.4 | Cost-value-optimal method selection | Pareto advisor / shared with T17 |
| T15.5 | Human-in-the-loop advisor override | `MethodAdvisorResult.override_audit_ref` |
| T16.1 | Tolerance-budget composition law across backends | `RuntimeFingerprint.observed_tolerance_budget` |
| T16.2 | Deterministic recovery semantics under circuit-breaker | fallback protocol |
| T16.3 | Deterministic distributed execution | reduction-order protocol |
| T16.4 | Cross-backend numerical equivalence | `MethodResult.cross_backend_equivalence_ref` |
| T17.1 | Uncertainty-aware cost estimation | `CostEstimate.distribution_ref` |
| T17.2 | Energy / carbon accounting as first-class cost | `CostEstimate.energy_footprint` + `CarbonCertificate` |
| T17.3 | Precision-budget / error-bound tradeoff | `MethodResult.precision_mode_and_bound` |
| T17.4 | DRO plan selection under cost uncertainty | DRO plan certificate |
| T18.1 | Envelope algebra for composed methods | `UncertaintyEnvelope.composition_provenance` |
| T18.2 | Delta vs MC selection under policy loss | delta/MC dispatcher certificate |
| T18.3 | Adaptive importance sampling for UQ | `MonteCarloConfig.importance_schedule` |
| T18.4 | Coherent risk measures (CVaR / ES) for composed envelopes | unified risk reporting |
| T19.1 | Identifiability-constrained calibration | `CalibrationResult.identifiability_status` |
| T19.2 | Multi-start local-minima characterization | multi-optimum reporting |
| T19.3 | Target alignment under missing data / index mismatch | alignment diagnostic |
| T19.4 | Measurement-error-aware calibration | `CalibrationResult.measurement_model_ref` |
| T20.1 | Sequential Bayesian updating with coverage | `PosteriorResult.streaming_state` |
| T20.2 | Bounded-memory estimators | `MethodResult.memory_budget_and_bound` |
| T20.3 | Online calibration-drift detector | online drift signal |
| T20.4 | Streaming / rolling CV | streaming CV protocol |
| T21.1 | Validated numerics for boundary-sensitive computations | `MethodResult.validated_bound` |
| T21.2 | PPL front-end with verified compilation | PPL verified-lowering theorem |
| T21.3 | Proof-carrying estimate certificates | `MethodResult.verification_certificate` |
| T21.4 | Bit-exact cross-architecture reproducibility | cross-arch bit-exact protocol |
| T22.1 | DP budget allocation across a pipeline | new `PrivacyBudgetCertificate` |
| T22.2 | Utility-preserving synthetic microdata | `SyntheticDatasetCertificate` |
| T22.3 | Privacy-preserving record linkage | record-linkage leakage certificate |
| T22.4 | Federated estimation with correctness | federated estimator family |
| T22.5 | Confidential-computing (TEE) attestation | TEE attestation certificate |
| T23.1 | Ground-truth synthetic worlds | shared DGP library |
| T23.2 | Hidden-holdout infrastructure | sealed-holdout protocol |
| T23.3 | Per-regime leaderboards | leaderboard schema |
| T23.4 | Adversarial / pathological case library | pathological-case registry |
| T24.1 | LLM-assisted theorem drafting + verification | `TheoremVerificationCertificate` |
| T24.2 | LLM-scaffolded estimator synthesis with tests | scaffolded-estimator audit |
| T24.3 | LLM literature synthesis with provenance | `LiteratureSynthesisReport` |
| T24.4 | LLM hallucination detection for policy text | hallucination-detection certificate |
| T25.1 | Regulatory IE with citation correctness | `TextExtractionBundle.citation_certificate` |
| T25.2 | Identified topic models | topic-identification test |
| T25.3 | Text-as-treatment / text-as-outcome | text-causal identification |
| T25.4 | Retrieval-augmented reasoning with calibrated citations | `RAGResponseCertificate` |
| T25.5 | Statutory reasoning with proof certificates | `StatutoryReasoningCertificate` |
| T26.1 | Remote-sensing proxy with bias-correction | `RemoteSensingProxyBundle` |
| T26.2 | Multimodal fusion (imagery + admin + text) | `MultimodalIndicatorBundle` |
| T26.3 | Geographic privacy under MAUP | geo-privacy protocol |
| T26.4 | Change-detection with causal semantics | attribution-augmented change detector |
| T27.1 | OPE under partial identification | OPE bounds estimator |
| T27.2 | Contextual bandits with fairness / equity constraints | fairness-constrained bandit + cert |
| T27.3 | Adaptive RCT with valid post-experiment inference | `AdaptiveTrialResult` |
| T27.4 | Safe RL with constraint-violation bounds | safe-RL constraint certificate |
| T27.5 | Dynamic treatment regimes under partial observability | DTR fallback estimator |
| T28.1 | HANK estimation with identification | HANK estimator contract |
| T28.2 | DSGE with robust priors + structural-break detection | DSGE-break reporting format |
| T28.3 | Real-time nowcasting / mixed-frequency | nowcasting estimator contract |
| T28.4 | Structural model averaging with identification weights | identification-weighted averaging |
| T29.1 | Bayesian NMA with transportability | NMA + transportability contract |
| T29.2 | Publication-bias correction with calibrated power | publication-bias readiness policy |
| T29.3 | Living-review infrastructure | automated evidence-update pipeline |
| T29.4 | Meta-transportability across K sites | K-site transport estimator |
| T30.1 | DA with strategy-proofness certificates | `AssignmentMechanismCertificate` |
| T30.2 | Two-sided matching preference elicitation | preference-identification contract |
| T30.3 | Combinatorial auctions at public scale | combinatorial auction welfare-loss bound |
| T30.4 | Platform regulation as mechanism design | three-layer mechanism contract |
| T31.1 | Hawkes / self-exciting processes | `PointProcessResult` |
| T31.2 | Competing risks + recurrent events | competing-risks estimator |
| T31.3 | Marked point processes for spatio-temporal events | marked point-process contract |
| T31.4 | Deep survival with calibrated intervals | deep-survival wrapper |
| T32.1 | Functional data for longitudinal policy outcomes | `FunctionalResult` |
| T32.2 | Persistent homology for policy data shape | TDA persistence contract |
| T32.3 | Manifold learning with causal faithfulness | manifold-faithfulness diagnostic |
| T32.4 | Geometric DL for administrative graphs | geometric-DL estimator |
| T33.1 | Benefit-abuse detection with causal fairness | Pareto fraud-fairness frontier |
| T33.2 | Adaptive audit-sampling with detection bounds | adaptive-audit protocol |
| T33.3 | Drift-coupled anomaly detection | detector-update rule |
| T33.4 | Whistleblower-safe reporting infra | reporting governance protocol |
| T34.1 | Multivariate EVT for policy tails | `TailRiskBundle` |
| T34.2 | Copula tail dependence with bias correction | tail-dependence estimator |
| T34.3 | Scenario generation with coverage | scenario-coverage certificate |
| T34.4 | Worst-case fiscal scenarios under GE feedback | compound DRO + EVT + GE solver |
| T35.1 | VFI error bounds under PFI | `ValueFunctionResult` |
| T35.2 | Dynamic games with identification | dynamic-game equilibrium format |
| T35.3 | Uncertainty propagation through VFI | envelope-VFI integration |
| T35.4 | Discrete-continuous choice estimation | DC-choice estimator contract |
| IV.T1.6 | Calibrated Bayesian model selection (WAIC/LOO/stacking) | `PosteriorResult.selection_diagnostic` |
| IV.T1.7 | Bayesian optimization as active learning | BO regret bound |
| IV.T2.8 | Ordinal regression with proper scoring rules | ordinal calibrated-forecast contract |
| IV.T3.6 | Probabilistic forecasting (quantile + distributional) | `ForecastingUncertaintyBundle.quantile_curves` |
| IV.T3.7 | Forecast combination / expert aggregation | combination no-arbitrage bound |
| IV.T4.6 | Local projections vs VAR under misspecification | LP/VAR dispatcher |
| IV.T4.7 | Multiple-hypothesis-testing corrections | `EconometricResult.mht_correction_applied` |
| IV.T5.6 | Adaptive / responsive survey design | adaptive-survey estimator |
| IV.T6.6 | Wealth distribution with top-code and admin fusion | wealth-fusion estimator |
| IV.T6.7 | Group-specific inflation / chain-weighted deflators | `DistributionalBundle.group_deflator` |
| IV.T7.6 | Real options for policy flexibility | real-options estimator |
| IV.T7.7 | Sequential / multi-period welfare | hyperbolic-sensitivity welfare |
| IV.T8.6 | Integer programming for policy structure | policy-specialized branch-and-cut |
| IV.T8.7 | Quadratic assignment / facility location with fairness | fairness-aware location solver |
| IV.T9.6 | Dynamic mechanism design | dynamic BIC mechanism family |
| IV.T10.6 | Validated SDE / ODE solvers | validated trajectory bound |
| IV.T11.6 | Static aging with demographic consistency | aging estimator contract |
| IV.T12.7 | Network motif / higher-order structure detection | motif-count CI contract |
| IV.T14.8 | Meta-evaluation for the six-judge stack | judge-readiness certificate |
| IV.T14.9 | Replication across toolchains | cross-toolchain tolerance library |

---

## 42. Appendix B: Missing Contract Inventory {#20-appendix-b}

Contracts that do not exist today and that one or more research tracks depend
on for graduation. These are the single largest structural gap for promoting
research sketches to production artifacts.

| Contract | Family / scope | Tracks that depend on it |
|---|---|---|
| `ForecastingUncertaintyBundle` | forecasting | T3.1, T3.2, T3.3, T3.4, T3.5 |
| `RegimeShiftForecastBundle` | forecasting | T3.3 |
| `ValidationReport` | validation | T14.1, T14.2, T14.3, T14.7 |
| `SensitivityAnalysisBundle` | sensitivity | T14.4, T14.5, T14.6 |
| `DistributionalBoundsBundle` | distributional | T6.1 |
| `MobilityReport` | distributional | T6.2, T6.5 |
| `WelfareBundle` | policy | T7.1, T7.2, T7.3, T7.5 |
| `SurveyQualityCertificate` | survey | T5.1, T5.4, T11 (consumer) |
| `ShiftDiagnosticReport` | ml | T2.2, T14.7 |
| `ExplanationBundle` | ml | T2.3 |
| `TransferDiagnostic` | ml | T2.4 |
| `IncentiveCompatibilityCertificate` | mechanism | T9.1, T9.2, T9.5 |
| `MechanismWelfareLossBound` | mechanism | T9.5 |
| `AbstractionCertificate` (spatial instance) | spatial | T13.1 |
| `InterferenceCertificate` (spatial instance) | spatial | T13.3 (shares the causal Track 9 contract) |
| `OptimizationResult.ambiguity_certificate` (field) | optimization | T8.1 |
| `PosteriorResult.truthfulness_tier` (field) | bayesian | T1.1, T1.3, T1.4 |
| `NetworkResult.peer_effect_decomposition` (field) | network | T12.1, T12.2, T12.4 |
| `MethodAdvisorResult.calibrated_regret_certificate` (field) | selection | T15.1, T15.4 |
| `MethodAdvisorResult.cross_method_consensus` (field) | selection | T15.3 |
| `RuntimeFingerprint.observed_tolerance_budget` (field) | backends | T16.1, T16.4 |
| `CrossBackendEquivalenceCertificate` | backends | T16.4, T21.4 |
| `CostEstimate.distribution_ref` (field) | cost model | T17.1, T17.4 |
| `CarbonCertificate` | cost model | T17.2 |
| `PrecisionModeBound` (field) | cost model | T17.3 |
| `UncertaintyEnvelope.composition_provenance` (field) | uncertainty | T18.1 |
| `CoherentRiskReport` (CVaR/ES envelope) | uncertainty | T18.4 |
| `CalibrationResult.identifiability_status` (field) | calibration | T19.1 |
| `CalibrationResult.measurement_model_ref` (field) | calibration | T19.4 |
| `StreamingStateCertificate` | streaming | T20.1, T20.2, T20.3 |
| `ValidatedBoundCertificate` | verified numerics | T21.1, IV.T10.6 |
| `VerifiedLoweringCertificate` (PPL) | verified numerics / PPL | T21.2 |
| `MethodResult.verification_certificate` (field) | verified numerics | T21.3 |
| `PrivacyBudgetCertificate` | privacy / DP | T22.1, T22.3, T22.5 |
| `SyntheticDatasetCertificate` | privacy / synthetic | T22.2 |
| `FederatedEstimatorCorrectnessCertificate` | federated | T22.4 |
| `TEEAttestationCertificate` | confidential computing | T22.5 |
| `SyntheticWorldDGP` spec | benchmarks | T23.1 |
| `SealedHoldoutProtocol` | benchmarks | T23.2 |
| `RegimeLeaderboardEntry` | benchmarks | T23.3 |
| `PathologicalCaseRegistry` | benchmarks | T23.4 |
| `TheoremVerificationCertificate` | LLM lifecycle | T24.1 |
| `LiteratureSynthesisReport` | LLM lifecycle | T24.3 |
| `HallucinationDetectionCertificate` | LLM lifecycle | T24.4, T2.5 |
| `TextExtractionBundle` | NLP | T25.1 |
| `RAGResponseCertificate` | NLP | T25.4 |
| `StatutoryReasoningCertificate` | NLP | T25.5 |
| `RemoteSensingProxyBundle` | earth-observation | T26.1 |
| `MultimodalIndicatorBundle` | earth-observation | T26.2 |
| `GeoPrivacyCertificate` | earth-observation / privacy | T26.3 |
| `OPEBoundsBundle` | RL | T27.1 |
| `FairnessConstrainedBanditCertificate` | RL | T27.2 |
| `AdaptiveTrialResult` | RL | T27.3 |
| `SafeRLViolationBoundCertificate` | RL | T27.4 |
| `HANKIdentificationCertificate` | macro | T28.1 |
| `DSGEBreakReport` | macro | T28.2 |
| `NowcastingBundle` | macro / forecasting | T28.3 |
| `StructuralModelAveragingWeights` | macro | T28.4 |
| `NetworkMetaAnalysisBundle` | evidence synthesis | T29.1 |
| `PublicationBiasReadinessPolicy` | evidence synthesis | T29.2 |
| `LivingReviewUpdateRecord` | evidence synthesis | T29.3 |
| `MetaTransportabilityCertificate` | evidence synthesis | T29.4 |
| `AssignmentMechanismCertificate` | matching markets | T30.1 |
| `CombinatorialAuctionWelfareLossBound` | matching markets | T30.3 |
| `PlatformMechanismBundle` | matching markets | T30.4 |
| `PointProcessResult` | point processes | T31.1–T31.3 |
| `CompetingRisksResult` | point processes / survival | T31.2 |
| `FunctionalResult` | FDA | T32.1 |
| `PersistenceDiagramResult` | TDA | T32.2 |
| `ManifoldFaithfulnessDiagnostic` | geometric | T32.3 |
| `FraudFairnessFrontierCertificate` | anomaly / fairness | T33.1 |
| `AdaptiveAuditProtocol` | anomaly | T33.2 |
| `DetectorUpdateRule` | anomaly | T33.3 |
| `TailRiskBundle` | extreme-value | T34.1, T34.2 |
| `ScenarioCoverageCertificate` | extreme-value / stress | T34.3 |
| `WorstCaseFiscalScenarioCertificate` | extreme-value / GE | T34.4 |
| `ValueFunctionResult` | agent-sim | T35.1, T35.3, T35.4 |

Each missing contract must be specified **before** the corresponding research
track can graduate. The first engineering-scope task for any highest-priority
track (T1, T3, T5, T11, T14, T15, T16, T18, T19, T23, T25, T27, T29) is
therefore to draft its receiving contract as part of the `required_for_promotion`
checklist, even though the contract itself does not require research to
define.

---

## 43. Appendix C: Cross-Cutting Subsystem Inventory {#21-appendix-c}

Subsystems in `polisyos.foundry/` that are cross-cutting concerns rather than
method families. Each maps to at least one Part II track.

| Subsystem | Key modules | Part II track |
|-----------|-------------|---------------|
| Method selection / advisor | `methods/selection.py`, `methods/discovery.py`, `methods/catalog_snapshot.py` | Track 15 |
| Backend dispatch & runtime fingerprint | `methods/backends/` (jax/numpy/ray/solver/bayesian runners, `dispatch.py`, `circuit_breaker.py`, `runtime_fingerprint.py`, `checkpointing.py`) | Track 16 |
| Cost model & plan optimization | `foundry/cost_model.py`, `methods/plan_optimizer.py`, `methods/profiler.py` | Track 17 |
| Uncertainty module | `foundry/uncertainty/` (analytical, covariance, delta, MC, qMC, sensitivity, aggregator, dispatcher), `calibration/uncertainty_adapter.py` | Track 18 |
| Calibration subsystem | `foundry/calibration/` (calibrator, identifiability, multi_start, measurement, preflight, bijectors, loss, report, auxiliary, hessian) | Track 19 |
| Execution lifecycle | `methods/executor.py`, `methods/chain_executor.py`, `methods/async_chain_executor.py`, `methods/lifecycle.py` | Track 20 (streaming) |
| Observability | `methods/observability.py`, `methods/output_monitor.py` | Tracks 15, 20 |
| Semantic validation | `methods/semantic_validator.py`, `methods/slot_schema.py`, `methods/compat_matrix.py` | Tracks 15, 16 |
| Compilation & specialization | `methods/compiler.py`, `methods/specialization.py`, `methods/mypy_plugin.py` | Track 21 (PPL lowering) |
| Artifacts & provenance | `methods/artifacts.py`, `methods/_artifacts_chain.py`, `methods/_artifacts_evidence.py`, `methods/_artifacts_fingerprint.py` | Tracks 16, 21, 23 |
| Registry & hot-reload | `methods/registry.py`, `methods/hot_reload.py`, `methods/resolution.py` | Tracks 15, 23 |
| Agent-sim | `foundry/agent_sim/` (`vfi.py`, `mechanisms.py`, `temporal.py`, `agent_metrics.py`) | Track 35 |

---

## 44. Appendix D: New Method Family Stub Inventory {#22-appendix-d}

Families that do not exist in `catalog/` today and that Part III establishes
research-first before any stub is introduced. Each line specifies the catalog
path once the stub is authored, the Part III track that gates it, and the
causal-agenda cross-reference if any.

| Proposed catalog path | Part III track | Cross-reference |
|-----------------------|----------------|-----------------|
| `catalog/nlp/` | Track 25 | Causal agenda Track 10 (proximal, text-as-proxy) |
| `catalog/earth_observation/` or `catalog/remote_sensing/` | Track 26 | — |
| `catalog/reinforcement/` (with `ope/`, `bandits/`, `adaptive_trials/`) | Track 27 | Causal Track 5 (strategic), Track 12 (intervention hierarchy) |
| `catalog/macro/` (with `dsge/`, `hank/`, `nowcasting/`) | Track 28 | Causal Track 3.4 (DSCM) |
| `catalog/evidence_synthesis/` (with `meta_analysis/`, `living_review/`) | Track 29 | Causal Track 13 (transportability) |
| `catalog/matching/` (with `assignment/`, `two_sided/`, `auctions/`) | Track 30 | Track 9 (mechanism) |
| `catalog/point_processes/` (with `hawkes/`, `competing_risks/`, `marked/`) | Track 31 | Track 13.7 (spatial point) |
| `catalog/functional/` and `catalog/tda/` | Track 32 | Track 12.6 (embedding fidelity) |
| `catalog/anomaly/` | Track 33 | Track 14.3 (fairness), Track 14.7 (drift) |
| `catalog/extreme_value/` or extension to `catalog/distributional/` | Track 34 | Track 7.1 (GE welfare) |
| `foundry/agent_sim/` (already exists; needs contract) | Track 35 | Track 11 (microsim), Track 9 (mechanism) |

No new family may ship a stub method until its Part III track has produced at
least one benchmark proxy and a contract specification as described in the
anti-swamp rule (section 17.2). The foundry will hold each family at
`PROOF_ONLY` readiness until the proxy graduates.
