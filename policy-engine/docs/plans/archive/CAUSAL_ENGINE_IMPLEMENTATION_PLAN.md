> **Archived:** This document reflects plans as of 2026-03-27.
> See [current docs](../../explanation/index.md) for up-to-date information.

# PolicyOS Causal Engine — Implementation Plan

> **Version**: 1.0
> **Date**: 2026-03-26
> **Status**: engineering-ready, immediate implementation
> **Derived from**: `CAUSAL_ENGINE_BEYOND_SOTA_BLUEPRINT.md` v2.1
> **Companion document**: `CAUSAL_ENGINE_RESEARCH_AGENDA.md`
>
> This document contains every task that can be started immediately without prior research.
> It covers the full architecture, contracts, and phased build order for all
> engineering-grade deliverables. Where original blueprint tasks require original
> mathematical research before implementation, they are excluded here and tracked in
> `CAUSAL_ENGINE_RESEARCH_AGENDA.md`.
>
> **Scope rule**: if a task has known mathematical foundations, a clear artifact type,
> and a benchmarkable output — it belongs here. If it requires a new theorem,
> an impossibility proof, or a formalization of an open problem — it belongs in the
> research agenda.

---

## Contents

1. [Central Thesis](#1-central-thesis)
2. [Architecture: Four Layers, Not One Engine](#2-architecture-four-layers-not-one-engine)
3. [Layer Contracts](#3-layer-contracts)
4. [Semantic Alignment Contract Layer](#4-semantic-alignment-contract-layer)
5. [Data Readiness Contract](#5-data-readiness-contract)
6. [Mathematical Frontier Taxonomy](#6-mathematical-frontier-taxonomy)
7. [Judge Stack](#7-judge-stack)
8. [Research Economics Layer (VOI x Moat)](#8-research-economics-layer-voi-x-moat)
9. [Causal Readiness Contract](#9-causal-readiness-contract)
10. [Direction I — Compositional Causality](#10-direction-i-compositional-causality)
11. [Direction II — Sharp Identification, Bounds, and Recovery](#11-direction-ii-sharp-identification-bounds-and-recovery)
12. [Direction III — Continuous-Time Causal Dynamics](#12-direction-iii-continuous-time-causal-dynamics)
13. [Direction IV — Distributional Causality via Optimal Transport](#13-direction-iv-distributional-causality-via-optimal-transport)
14. [Direction V — Strategic and Multi-Scale Policy Causality](#14-direction-v-strategic-and-multi-scale-policy-causality)
15. [Direction VI — Discovery, Latents, and Algebraic Structure](#15-direction-vi-discovery-latents-and-algebraic-structure)
16. [Direction VII — Hypergraph Interference and Topology](#16-direction-vii-hypergraph-interference-and-topology)
17. [Shared Infrastructure](#17-shared-infrastructure)
18. [Architectural Invariants and Failure Modes](#18-architectural-invariants-and-failure-modes)
19. [Degraded Mode and Safe Fallback](#19-degraded-mode-and-safe-fallback)
20. [Execution Phases](#20-execution-phases)
21. [Build Order](#21-build-order)
22. [Beyond-SOTA Acceptance Criteria](#22-beyond-sota-acceptance-criteria)
23. [User-Facing Interaction Model](#23-user-facing-interaction-model)
24. [Artifact Export and Integration Contract](#24-artifact-export-and-integration-contract)
25. [Falsification Loop and Post-Deployment Contract](#25-falsification-loop-and-post-deployment-contract)
26. [Computation Architecture Principles](#26-computation-architecture-principles)
27. [Design Inspirations](#27-design-inspirations)

---

## 1. Central Thesis

PolicyOS Causal Engine must not become "one more estimator catalog".
It must become a **proof-carrying causal reasoning platform** where:

1. every causal claim is either identified, bounded, or explicitly refused;
2. every frontier method is governed by typed contracts;
3. every new mathematical direction is promoted only through hidden benchmarks and replay;
4. every policy artifact carries explicit structural, temporal, distributional, strategic, and abstraction uncertainty;
5. every cross-domain composition passes semantic alignment verification before structural gluing;
6. every estimation step is gated by data readiness evidence, not only theorem validity.

The moat does not come from any single method.
It comes from the integration:

```text
query
  -> semantic alignment check          (variable semantics, measurement model, ontology)
  -> proof kernel                      (ID / transport / ctf / recoverability / failure cert)
  -> data readiness gate               (overlap, ESS, missingness, measurement quality)
  -> bounds-or-estimand compiler       (point ID if possible, sharp bounds otherwise)
  -> frontier reasoners                (composition / time / OT / strategy / abstraction / discovery)
  -> refutation + hidden challenge     (adversarial, holdout, replay, calibration)
  -> judge stack verdict               (typed promotion gates with numerical thresholds)
  -> promote only if readiness contract passes
  -> export to downstream consumers    (policy analyst UI, audit trail, API)
```

### 1.1. What "beyond SOTA" means operationally

1. **Graph composition is first-class**: the engine must reason over stitched SCM fragments, not only one flat DAG.
2. **Semantic alignment is mandatory**: no composition without verified variable semantics and measurement comparability.
3. **Non-identification is productive**: "cannot identify" is not an endpoint; the engine must return sharp bounds, counterexamples, or acquisition guidance whenever theory allows.
4. **Data readiness gates estimation**: theorem validity does not imply estimation feasibility; overlap, sample size, and measurement quality are first-class concerns.
5. **Time is native**: the engine must model effect trajectories, not only before/after scalars.
6. **Distributions matter**: the engine must compare counterfactual distributions, not only means.
7. **Strategic adaptation is explicit**: policies change behavior; equilibrium response must be represented.
8. **Micro-to-macro consistency is certified**: aggregation cannot be hand-waved.
9. **Discovery remains uncertainty-honest**: latent factors and disputed edges must be surfaced, not smoothed away.
10. **Topology is a horizon, not a shortcut**: hypergraph and simplicial reasoning are research lanes with hard readiness caps.
11. **Proof beats prose**: no LLM, heuristic, or estimator may overrule the proof kernel.
12. **Governed integration is the moat**: the competitive gap is the whole stack, not an isolated module.

### 1.2. Current baseline and implementation stance

This plan is **not** greenfield.
Current code and benchmark evidence already establish a strong causal baseline:

1. symbolic identification, missing-data recoverability, transportability, natural-experiment and DID-with-interference suites are already green in the current benchmark floor;
2. adversarial symbolic stress, compiled audit, cyclic feedback, multi-source, surrogate, and non-transportability capability demos already exist and pass;
3. reproducibility and audit-trail infrastructure already exist and are benchmarked;
4. substantial artifact substrate already exists in `ir/analytics/*`, and substantial governance substrate already exists in `scientist/search/*`, `scientist/replay/*`, and `scientist/discovery/*`.

Therefore, the implementation posture for this document is:

1. **extend and unify existing substrate first**;
2. **preserve the current benchmark floor while adding contracts and frontier layers**;
3. create a new companion module only when no canonical home exists in `foundry/methods/catalog/causal/`, `ir/analytics/`, or `scientist/*`;
4. do **not** build a parallel causal stack beside the current one.

---

## 2. Architecture: Four Layers, Not One Engine

The causal engine should evolve as four explicitly separated layers.
Without this separation, frontier mathematics will leak into the proof kernel and corrupt reliability.

```text
┌──────────────────────────────────────────────────────────────┐
│ Layer D - Governance and Scientist Shell                    │
│ Search, hidden benchmarks, judge stack, readiness, replay,  │
│ budget routing, adversarial evaluation, promotion policy.   │
├──────────────────────────────────────────────────────────────┤
│ Layer C - Frontier Reasoners                                │
│ Composition, sharp bounds, continuous-time, OT, strategic   │
│ equilibria, abstraction, latent discovery, topology.        │
│ Extends Layer B, never replaces Layer A.                    │
├──────────────────────────────────────────────────────────────┤
│ Layer B - Compilation and Execution Kernel                  │
│ Estimand compilation, estimator routing, uncertainty,       │
│ transport estimation, policy value, simulation execution.   │
│ Data readiness verification before estimation.              │
├──────────────────────────────────────────────────────────────┤
│ Layer A - Symbolic Proof Kernel (stratified)                │
│ A0: DAG/ADMG, ID/IDC, transport (crisp), neg. certs        │
│ A1: recoverability, sigma, limited cyclic, ID*/IDC*         │
│ A2: oracle-backed, partial-coverage, delegated proofs       │
└──────────────────────────────────────────────────────────────┘
```

### 2.1. Layer A internal stratification

Layer A must remain the truth anchor, but not all symbolic results carry equal implementation maturity.
Mixing crisp, battle-tested theorems with partial-coverage experimental proofs under the same trust label creates a dangerous illusion of uniform reliability.

| Stratum | Contents | Trust level | Implementation requirement |
|---------|----------|-------------|---------------------------|
| **A0 - Trusted Core** | DAG/ADMG graph model, ID/IDC algorithms, transportability (where theorem coverage is crisp and complete), negative certificates, hedges | **Full trust** | Complete implementation with exhaustive test coverage |
| **A1 - Extended Symbolic** | Recoverability engine, sigma/selection-extended settings, limited cyclic subfamilies, ID*/IDC* (if fully proven in implementation scope) | **High trust, bounded scope** | Implementation covers declared scope; scope boundaries are machine-readable |
| **A2 - Oracle-backed** | Anything incomplete, delegated to external solvers, or with partial coverage; novel theorem families under validation | **Conditional trust** | Must declare coverage gaps; outputs carry `oracle_backed` flag |

`ProofBundle` must reflect this stratification:

```python
class ProofBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proof_status: Literal["identified", "non_identified", "oracle_needed"]
    proof_stratum: Literal["A0_trusted", "A1_extended", "A2_oracle_backed"]
    theorem_family: str                        # e.g., "id_dag", "idc_admg", "sigma_selection", "cyclic_bow"
    completeness_regime: Literal["complete", "sound_incomplete", "heuristic_backed"]
    implementation_coverage: str               # human-readable scope statement
    estimand_ast_ref: ArtifactRef | None
    negative_certificate_ref: ArtifactRef | None
    proof_trace_ref: ArtifactRef
    assumptions: list[str]
    graph_ref: ArtifactRef
    query_ref: ArtifactRef
```

### 2.2. Dependency graph

```text
Layer D -> consumes certification from Layer C and Layer B
Layer C -> consumes proofs and certificates from Layer A, execution services from Layer B
Layer B -> consumes proofs from Layer A, enforces data readiness before estimation
Layer A -> depends only on graph/query/IR contracts, not on frontier modules
```

### 2.3. Why this separation matters

1. **Layer A must remain small, pure, and stratified**. It is the truth anchor. A0 is the bedrock; A1 and A2 extend it with explicit trust boundaries.
2. **Layer B is an execution layer, not a theorem layer**. It can route estimators but must not invent identifiability. It must verify data readiness before executing any estimation plan.
3. **Layer C is where the moat grows**. New mathematics lands here first under readiness caps.
4. **Layer D is where trust is decided**. Promotion, not novelty, is the final gate.

### 2.4. Grounding in existing code

| Layer | Existing modules | Role in target architecture |
|-------|------------------|-----------------------------|
| A - Proof | `foundry/methods/catalog/causal/id_engine.py`, `do_calculus.py`, `ctf_calculus.py`, `ctf_transport.py`, `sigma_calculus.py`, `cyclic_id.py`, `recoverability_engine.py`, `admg_ops.py`, `query_validator.py` | Current proof kernel anchor |
| B - Execution | `estimand_compiler.py`, `protocols.py`, `treatment_effects.py`, `tmle_core.py`, `dml.py`, `g_computation.py`, `transport_engine.py`, `bounds_engine.py`, `quality_aggregator.py`, `calibration.py` | Current execution and estimation kernel |
| C - Frontier | `graph_reconciliation.py`, `twin_graph.py`, `amn.py`, `interference.py`, `structural_time_series.py`, `policy_learning.py`, `optimal_design.py`, `discovery_pipeline.py`, `dagma_discovery.py`, `pcmci_discovery.py`, `literature_prior.py`, `measurement_error.py`, `ncm_engine.py` | Existing footholds for moat extensions |
| D - Governance | `scientist/search/*`, `scientist/governance/*`, `scientist/backtesting/*`, `scientist/doe/*`, `scientist/replay/*`, `scientist/cross_graph/*`, `scientist/engine/*` | Promotion, routing, hidden benchmarks, replay, governance |

### 2.5. Anti-god-object rule

No frontier feature may directly patch `causal_engine.py` into a catch-all orchestrator.
New families should enter via dedicated contracts and registries.
If a new idea cannot be expressed as a typed contract, it is not ready for integration.

Implementation posture:

1. execution logic should land next to the canonical causal catalog in `foundry/methods/catalog/causal/`;
2. artifact schemas should land in `ir/analytics/`;
3. promotion, judge, replay, and readiness logic should land in `scientist/*`;
4. a brand-new top-level `causal/` package should be created only if no existing package can host the feature cleanly.

---

## 3. Layer Contracts

Layers communicate only through typed contracts.
Frontier mathematics is allowed to be ambitious, but not vague.

### 3.1. Layer A -> Layer B/C

```python
class ProofKernel(Protocol):
    """Pure symbolic reasoning layer."""

    def identify(
        self,
        query: CausalQuery,
        graph: CausalGraphModel,
        context: ProofContext,
    ) -> ProofBundle: ...

    def bound(
        self,
        query: CausalQuery,
        graph: CausalGraphModel,
        context: ProofContext,
    ) -> BoundsBundle: ...
```

### 3.2. Layer B -> Layer C/D

```python
class ExecutionKernel(Protocol):
    """Compiles proofs into executable plans and runs them."""

    def compile(
        self,
        proof: ProofBundle,
        data_readiness: DataReadinessReport,
        context: ExecutionContext,
    ) -> ExecutionPlan: ...

    def execute(
        self,
        plan: ExecutionPlan,
        runtime: RuntimeContext,
    ) -> ExecutionBundle: ...
```

```python
class ExecutionBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimand_ref: ArtifactRef | None
    estimate_ref: ArtifactRef | None
    uncertainty_ref: ArtifactRef
    diagnostics_ref: ArtifactRef
    data_readiness_ref: ArtifactRef          # link to DataReadinessReport used
    audit_refs: list[ArtifactRef]
```

### 3.3. Layer C frontier contract

```python
class FrontierReasoner(Protocol):
    """Each frontier family extends the core with one typed capability."""

    family: FrontierFamily

    def run(
        self,
        proof: ProofBundle,
        execution: ExecutionBundle | None,
        context: FrontierContext,
    ) -> FrontierArtifact: ...
```

```python
class FrontierArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: FrontierFamily
    artifact_type: str
    primary_ref: ArtifactRef
    readiness_cap: CausalReadiness
    uncertainty_envelope_ref: ArtifactRef
    failure_cards: list[ArtifactRef]
    benchmark_requirements: list[str]
```

### 3.4. Layer C lightweight exploration contract

Full `FrontierArtifact` creation is expensive and may discourage early experimentation.
For research-stage exploration within frontier families, a lighter entry point is available:

```python
class FrontierSketch(BaseModel):
    """Lightweight artifact for early frontier experiments before full certification."""
    model_config = ConfigDict(extra="forbid")

    family: FrontierFamily
    sketch_type: str
    hypothesis: str                            # what this experiment is trying to show
    primary_ref: ArtifactRef
    known_limitations: list[str]
    required_for_promotion: list[str]          # what must be done to graduate to FrontierArtifact
    max_readiness: Literal["PROOF_ONLY"]       # sketches are never promotable
    ttl_phases: int                            # auto-expire after N phases if not graduated
```

Rules:
1. Sketches may not be promoted. They are research-only.
2. A sketch that survives and passes its `required_for_promotion` checklist graduates to a full `FrontierArtifact`.
3. A sketch that exceeds `ttl_phases` is archived automatically.
4. **Anti-leak rules**: sketches must not be used in downstream policy simulation by default; must not participate in composite judge verdicts alongside full frontier artifacts; must not raise the perceived maturity of their parent family. A sketch is invisible to Layer D except for archival and TTL enforcement.

### 3.5. Layer D certification contract

```python
class CausalCertificationService(Protocol):
    """Promotion and readiness are decided here, never inside frontier modules."""

    def evaluate(
        self,
        proof: ProofBundle,
        execution: ExecutionBundle | None,
        frontier_artifacts: list[FrontierArtifact],
        data_readiness: DataReadinessReport,
        alignment_report: AlignmentReport | None,
    ) -> CausalJudgeVerdict: ...
```

### 3.6. Cardinal contract rules

1. Frontier modules may **consume** proofs; they may not mutate them.
2. Layer B may compile an identified estimand; it may not silently reinterpret a non-identified query as identified.
3. Layer B must verify `DataReadinessReport` before executing any estimation plan. Estimation on insufficient data is a system bug, not a user error.
4. Every frontier artifact must reference the exact `ProofBundle` and input graph CAS hash it used.
5. Every promoted artifact must be reproducible without frontier modules being "remembered" informally.
6. No composition may proceed without a passing `AlignmentReport` for all interface variables.

---

## 4. Semantic Alignment Contract Layer

### 4.1. Why this layer is mandatory

Compositional causality (Direction I) is the primary moat. But composition is currently too graph-centric.
In real policy work, graphs break not only because of structural misalignment, but because "employment", "informal employment", "registered employment", "labor force participation" and "taxable wage income" are treated as interchangeable when they are not.

Without a formal semantic alignment layer, the compositional engine will regularly perform **formally valid but semantically false stitching**.

### 4.2. The alignment problem decomposed

Composition requires three independent verifications:

| Verification | Question | Can be automated? |
|---|---|---|
| **Structural composability** | Can the graph fragments be glued without contradictions? | Yes, fully |
| **Identification preservation** | Which queries remain identifiable after gluing? | Yes, within theorem coverage |
| **Measurement comparability** | Do the same-named variables in different fragments actually measure the same construct at compatible scales? | Partially; requires metadata + human review for ambiguous cases |

The first two are already addressed by the compositional engine. The third requires a dedicated contract layer.

### 4.3. Alignment contracts

```python
class AlignmentType(str, Enum):
    EXACT = "exact"                    # same construct, same measurement, same scale
    SCALE_LINKED = "scale_linked"      # same construct, different unit/scale, known transform
    PROXY = "proxy"                    # related but distinct constructs with known empirical relationship
    LATENT_BRIDGE = "latent_bridge"    # linked through a shared latent with explicit assumptions
    INCOMPATIBLE = "incompatible"      # cannot be aligned without unverifiable assumptions
```

```python
class VariableAlignmentCertificate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variable_a: str
    fragment_a_id: str
    variable_b: str
    fragment_b_id: str
    alignment_type: AlignmentType
    measurement_model_a_ref: ArtifactRef | None
    measurement_model_b_ref: ArtifactRef | None
    transform_ref: ArtifactRef | None          # for SCALE_LINKED: the transform function
    proxy_evidence_ref: ArtifactRef | None     # for PROXY: empirical evidence of proxy validity
    latent_bridge_ref: ArtifactRef | None      # for LATENT_BRIDGE: the bridging assumptions
    assumptions_introduced: list[str]          # assumptions added by alignment itself, not by structure
    reviewer: Literal["automated", "human_verified", "pending_review"]
```

```python
class AlignmentReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fragment_ids: list[str]
    per_variable_certificates: list[VariableAlignmentCertificate]
    overall_status: Literal["aligned", "partially_aligned", "incompatible"]
    incompatible_pairs: list[tuple[str, str]]
    alignment_assumptions: list[str]           # all assumptions introduced by alignment, collected
    ontology_mismatch_warnings: list[str]
    measurement_comparability_grade: Literal["high", "medium", "low", "insufficient"]
```

### 4.4. Alignment rules

1. No composition may proceed if any interface variable pair has `alignment_type == INCOMPATIBLE` without explicit human override.
2. `PROXY` and `LATENT_BRIDGE` alignments introduce additional assumptions that must appear in the `CompositionCertificate.newly_required_assumptions`.
3. The `AlignmentReport` must be attached to every `CompositionCertificate`. A composition without alignment evidence is incomplete.
4. Alignment assumptions are a distinct category from structural assumptions. They must be reported separately so that sensitivity analysis can target them independently.

### 4.5. Alignment review workflow

The `reviewer` field in `VariableAlignmentCertificate` follows a concrete lifecycle:

```text
automated -> pending_review -> human_verified
                            -> automated_sufficient (if rules allow)
```

**Workflow rules**:
1. `EXACT` and `SCALE_LINKED` alignments with machine-verifiable transforms may remain `automated` and do not require human review.
2. `PROXY` alignments are created as `pending_review`. While pending, composition may proceed at **reduced readiness** (capped at `BOUNDS_READY`) with a mandatory warning. This prevents human review from becoming a production bottleneck.
3. `LATENT_BRIDGE` alignments are created as `pending_review` and **block composition** until `human_verified`. No reduced-readiness fallback.
4. `pending_review` items are tracked in a review queue with SLA targets. Items pending beyond SLA emit escalation alerts.
5. The reviewer must be a domain expert with explicit authority over the relevant semantic namespace. The system tracks reviewer identity and credentials for audit.

### 4.6. Ontology dispute resolution

When two fragments define the same concept differently (e.g., Ministry of Finance and Ministry of Economy disagree on the definition of "small business"), the system must not simply block and wait. Instead:

```python
class OntologyDispute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variable_name: str
    definition_a: str
    fragment_a_id: str
    definition_b: str
    fragment_b_id: str
    resolution_status: Literal["unresolved", "forked", "resolved"]
    fork_refs: list[ArtifactRef]               # analysis results under each definition
    sensitivity_to_definition: float | None    # how much does the final estimate change?
```

**Resolution protocol**:
1. The system **forks the analysis**: it computes the causal estimate under both competing definitions (Version A and Version B).
2. It reports the **sensitivity to definition choice**: if the estimates diverge significantly, this is surfaced as a key fragility driver.
3. If estimates are robust to the definitional difference (within tolerance), the dispute is downgraded to `info` and either definition may be used.
4. If estimates diverge, the dispute remains `unresolved` and both versions are exported. The final readiness is capped at `BOUNDS_READY` until the dispute is resolved by domain authority.

### 4.7. Why this compounds with existing architecture

The alignment layer integrates naturally with:
- `CompositionCertificate`: adds `alignment_report_ref` field
- `GovernanceJudge`: can flag compositions where all alignments are `PROXY` or weaker
- `RecoveryPlan`: can suggest measurement improvements when alignment is the bottleneck
- `DataReadinessContract`: measurement quality feeds directly into alignment feasibility

---

## 5. Data Readiness Contract

### 5.1. The gap between theorem and estimation

The proof kernel guarantees theorem validity. But between a valid estimand and a policy-grade estimate, the most common failure is not mathematical — it is empirical. The engine must not allow a valid theorem to produce an estimate on data that cannot support it.

### 5.2. Data readiness contract

```python
class OverlapGrade(str, Enum):
    STRONG = "strong"              # positivity holds robustly across covariate space
    ADEQUATE = "adequate"          # positivity holds but some regions are sparse
    WEAK = "weak"                  # practical positivity violations in significant regions
    VIOLATED = "violated"          # structural positivity violations

class MissingnessRegime(str, Enum):
    COMPLETE = "complete"
    MCAR = "mcar"                  # missing completely at random
    MAR = "mar"                    # missing at random
    MNAR_MODELED = "mnar_modeled"  # missing not at random, with explicit model
    MNAR_UNMODELED = "mnar_unmodeled"  # MNAR without model - blocks most estimators

class DataReadinessReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimand_ref: ArtifactRef
    dataset_ref: ArtifactRef

    # Sample adequacy
    raw_sample_size: int
    effective_sample_size: float
    ess_ratio: float                           # ESS / raw_n; low ratio = high weight concentration
    ess_sufficient: bool                       # ESS >= threshold for target estimand

    # Overlap / positivity
    overlap_grade: OverlapGrade
    positivity_stress_ref: ArtifactRef | None  # detailed positivity diagnostics
    trimming_fraction: float | None            # fraction of units trimmed for overlap

    # Missingness
    missingness_regime: MissingnessRegime
    missing_fraction_by_variable: dict[str, float]
    missingness_model_ref: ArtifactRef | None

    # Measurement quality
    measurement_reliability: dict[str, float]  # per-variable reliability coefficients where available
    measurement_model_refs: dict[str, ArtifactRef]

    # Domain shift / transport
    domain_shift_detected: bool
    transport_distance_ref: ArtifactRef | None
    support_mismatch_ref: ArtifactRef | None

    # Nuisance feasibility
    nuisance_feasibility: Literal["feasible", "marginal", "infeasible"]
    nuisance_diagnostics_ref: ArtifactRef | None

    # Summary flags
    estimation_feasible: bool                  # can we estimate at all?
    estimation_underpowered: bool              # identified but insufficient data for target precision
    warnings: list[str]
    blockers: list[str]                        # any blocker -> estimation must not proceed
```

### 5.3. Data readiness rules

1. Layer B must produce a `DataReadinessReport` before compiling any estimation plan.
2. If `estimation_feasible == False`, Layer B must not proceed to estimation. It must return the report with blockers to the caller.
3. If `estimation_underpowered == True`, the resulting artifact must carry a mandatory disclosure and its readiness cap must not exceed `BOUNDS_READY`.
4. `overlap_grade == VIOLATED` is a blocker for any estimand that requires positivity.
5. `missingness_regime == MNAR_UNMODELED` is a blocker for all estimators except bounds-only analysis.
6. The `DataReadinessReport` is attached to every `ExecutionBundle` and is visible to the judge stack.

### 5.4. Integration with judge stack

The `DataJudge` (see section 7) consumes the `DataReadinessReport` and enforces numerical thresholds before any estimation artifact can be promoted.

---

## 6. Mathematical Frontier Taxonomy

The dialogue surfaced ten candidate moat directions.
They are not equally mature, equally urgent, or equally compatible with the current code.
They must be typed explicitly.

```python
class FrontierFamily(str, Enum):
    COMPOSITIONAL = "compositional"
    SHARP_BOUNDS = "sharp_bounds"
    CONTINUOUS_TIME = "continuous_time"
    DISTRIBUTIONAL_OT = "distributional_ot"
    STRATEGIC = "strategic"
    ABSTRACTION = "abstraction"
    DISCOVERY_ALGEBRAIC = "discovery_algebraic"
    LATENT_REPRESENTATION = "latent_representation"
    TOPOLOGICAL_INTERFERENCE = "topological_interference"
```

### 6.1. Frontier families and intended role

| Family | Core question | Near-term status | Strategic value |
|--------|---------------|------------------|-----------------|
| Compositional causality | How do we stitch multiple SCMs without lying about identifiability? | Production-first | Deep moat for multi-ministry policy |
| Sharp bounds | What is the strongest valid answer when point ID fails? | Production-first | Massive ROI, unlocks non-ID cases |
| Continuous-time causality | What is the effect trajectory over time, not just a scalar? | Production-second | Direct policy value for budgeting and timing |
| Distributional OT | How does the full counterfactual distribution move? | Production-second | Tail risk and subgroup shift moat |
| Strategic causality | How do agents adapt to policy strategically? | Production-third (reduced scope) | Lucas-critique moat for policy realism |
| Causal abstraction | Is macro reasoning faithful to micro structure? | Production-third (finite-state scope) | Micro-to-macro credibility moat |
| Discovery + algebraic structure | Which graphs survive data, priors, and testable constraints? | Production-third (CI scope) | Strong structural discovery moat |
| Latent representation learning | Can we propose latent confounders from multi-environment shifts? | Research lane | Potentially huge, assumption-heavy |
| Hypergraph topology | How do group interactions change interference? | Horizon lane (contracts only) | Very deep moat, very high risk |

### 6.2. Frontier uncertainty taxonomy

Each frontier family introduces its own uncertainty type.
These must remain visible to the user and to the judge stack.

```python
class FrontierUncertaintyType(str, Enum):
    COMPOSITION = "composition"          # interface mismatch, invalid gluing
    SEMANTIC = "semantic"                # measurement mismatch, ontology mismatch, proxy error
    IDENTIFICATION = "identification"    # non-ID or looseness of bounds
    DATA_QUALITY = "data_quality"        # overlap, missingness, measurement error, underpowering
    TEMPORAL = "temporal"                # discretization, solver error, path instability
    DISTRIBUTIONAL = "distributional"    # coupling ambiguity, tail instability
    STRATEGIC = "strategic"              # equilibrium multiplicity, performative shift
    ABSTRACTION = "abstraction"          # ecological mismatch, loss under aggregation
    LATENT = "latent"                    # confounder invention risk, weak assumptions
    TOPOLOGICAL = "topological"          # complex reduction error, group structure uncertainty
```

### 6.3. Initial portfolio ordering

1. `COMPOSITIONAL` (with semantic alignment)
2. `SHARP_BOUNDS`
3. `CONTINUOUS_TIME`
4. `DISTRIBUTIONAL_OT`
5. `STRATEGIC`
6. `ABSTRACTION`
7. `DISCOVERY_ALGEBRAIC`
8. `LATENT_REPRESENTATION`
9. `TOPOLOGICAL_INTERFERENCE`

### 6.4. Implementation vs. research boundary

Each frontier family has a clear scope boundary between what is engineering (this document) and what requires research (`CAUSAL_ENGINE_RESEARCH_AGENDA.md`):

| Family | Implementation scope (this document) | Research scope (see RESEARCH_AGENDA) |
|--------|--------------------------------------|--------------------------------------|
| Compositional | DAG/ADMG fragment gluing, observed interfaces, d-separation preservation checks | Identifiability under latent interfaces, cyclic composition, automatic latent bridge synthesis, category-theoretic completeness |
| Sharp bounds | Balke-Pearl LP bounds, Manski bounds, existing semiparametric bounds | Novel sharpness proofs for complex query families, automated bound tightening |
| Continuous-time | Linear SDE, piecewise ODE, standard impulse responses | Neural SDE identification theory, causal rough-path semantics |
| Distributional OT | Wasserstein computation, quantile treatment effects, justification typing | Causally justified OT couplings under partial identification |
| Strategic | Best-response/Stackelberg for simple game forms, compute budget enforcement | Complex equilibrium computation, performative prediction convergence |
| Abstraction | Exact abstraction verification for finite-state SCMs | Approximate abstraction error bounds for continuous models |
| Discovery | Algorithm portfolio (PC, GES, DAGMA, PCMCI), bootstrap stability, implied CI constraints | Algebraic constraint discovery beyond conditional independence |
| Latent | Multi-environment invariance testing as prior evidence | Latent variable cardinality identification from distributional shifts |
| Topological | Contracts and IR schemas only (F.1) | Simplicial complex identification theory, hypergraph estimators |

---

## 7. Judge Stack

Promotion cannot be decided by a single benchmark or by frontier enthusiasm.
Each family must pass a composite, typed judge stack.

### 7.1. Judge definitions with operational metrics

| Judge | What it checks | Failure is | Override | Key metrics and thresholds |
|-------|----------------|------------|----------|---------------------------|
| ProofJudge | symbolic validity, certificate completeness, theorem preconditions | fatal | no | theorem precondition coverage = 100%; proof trace is machine-verifiable; no A2-stratum proof without explicit oracle disclosure |
| AlignmentJudge | semantic alignment of interface variables, measurement comparability | fatal | only via human protocol | all interface pairs must have `alignment_type != incompatible`; `measurement_comparability_grade >= medium`; no unreviewed `LATENT_BRIDGE` alignments |
| DataJudge | data readiness for estimation, overlap, missingness, ESS | fatal | no | `ess_ratio >= 0.1`; `overlap_grade != violated`; `missingness_regime != mnar_unmodeled`; `estimation_feasible == true` |
| BoundJudge | sharpness, bound consistency, dual witness validity | fatal | no | dual witness present for all `sharp` claims; bound width benchmarked against LP oracle on sentinel cases; `upper >= lower` invariant |
| EstimationJudge | calibration, CI behavior, estimator adequacy, nuisance quality | fatal | no | calibration slope in `[0.8, 1.2]`; CI coverage `>= 0.90` on bootstrap; cross-fit RMSE within `2x` of oracle RMSE on visible gold |
| DynamicsJudge | solver stability, discretization error, path calibration | fatal | no | discretization error `<= 0.05 * effect_magnitude`; stiffness ratio within solver tolerance; replay trajectory drift `<= 1%` per re-run |
| DistributionJudge | mass conservation, coupling sanity, subgroup tail stability | fatal | no | mass conservation error `<= 1e-6`; support truncation ratio `<= 0.05`; subgroup quantile instability `<= 0.1` across bootstrap; regularization sensitivity slope `<= 0.5` |
| StrategicJudge | equilibrium existence, multiplicity disclosure, performative stability | fatal | no | equilibrium existence proof or explicit non-existence card; if multiple equilibria, all must be enumerated or bounded; performative shift magnitude reported |
| GovernanceJudge | legal, equity, privacy, policy-budget, safe use of assumptions | fatal | only via human protocol | all mandatory disclosures present; equity subgroup analysis complete; assumption audit trail attached |
| ReproducibilityJudge | replay match, seed stability, artifact lineage | fatal | no | replay match `>= 99.9%` for deterministic components; stochastic components within `3 sigma` of expected distribution; full artifact lineage traceable |
| ComputeJudge | runtime, memory, cost-to-value ratio | **fatal for strategic family**; warning for others | yes (except strategic) | wall-clock `<= budget_limit`; peak memory `<= memory_limit`; for strategic family: hard timeout triggers forced degraded mode |

### 7.2. Composition rule

```python
class SingleJudgeVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judge_name: str
    passed: bool
    is_fatal: bool
    metrics: dict[str, float]                  # actual measured values
    thresholds: dict[str, float]               # thresholds applied
    violations: list[str]                      # which thresholds were breached
    evidence_refs: list[ArtifactRef]           # supporting evidence
    escalation_level: Literal["info", "warning", "error", "fatal"]

class CausalJudgeVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    per_judge: dict[str, SingleJudgeVerdict]
    composite_decision: Literal["promote", "reject", "defer_to_human"]
    blocking_failures: list[TypedFailureCard]
    warnings: list[TypedFailureCard]
    audit_log_ref: ArtifactRef                 # full judge evaluation log

    @property
    def is_promotable(self) -> bool:
        return all(v.passed for v in self.per_judge.values() if v.is_fatal)
```

### 7.3. Judge-to-family requirements

| Family | Required judges |
|--------|------------------|
| Compositional | Proof, Alignment, Data, Governance, Reproducibility |
| Sharp bounds | Proof, Bound, Data, Reproducibility |
| Continuous-time | Proof, Data, Estimation, Dynamics, Reproducibility |
| Distributional OT | Proof, Data, Estimation, Distribution, Reproducibility |
| Strategic | Proof, Data, Estimation, Strategic, Compute, Governance, Reproducibility |
| Abstraction | Proof, Data, Strategic or Estimation, Governance, Reproducibility |
| Discovery + algebraic | Proof, Bound or Estimation, Data, Reproducibility |
| Latent representation | Proof, Data, Estimation, Governance, Reproducibility, human gate |
| Topological interference | Proof, Data, Estimation, Governance, Reproducibility, human gate |

### 7.4. Cardinal rule

No frontier family may define its own promotion rules outside this stack.
A research module may produce artifacts.
It may not self-certify those artifacts as ready.

### 7.5. Threshold governance

Judge thresholds are not hardcoded constants. They are stored in a versioned `JudgeThresholdRegistry` and can be tightened (never loosened without human approval) as the system matures. Every threshold change is audited.

**Important**: all numerical thresholds in section 7.1 are **provisional initial operating defaults**. They are calibrated to be reasonable starting points but will be refined through benchmark evidence. The `JudgeThresholdRegistry` tracks their provenance and maturity.

```python
class JudgeThresholdEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judge_name: str
    metric_name: str
    threshold_value: float
    direction: Literal["max", "min"]           # "max" = must be <= threshold; "min" = must be >= threshold
    rationale: str
    benchmark_source: str                      # which benchmark suite validates this threshold
    maturity: Literal["provisional", "benchmarked", "hardened"]
    version: int
    last_updated: str

    # Scoping: thresholds can vary by context
    scope_family: FrontierFamily | None
    scope_query_type: str | None
    scope_estimator: str | None
    scope_readiness_target: CausalReadiness | None
```

### 7.6. Scoped threshold resolution

When evaluating a judge verdict, the threshold resolution order is:

1. Look for a threshold scoped to `(family, query_type, estimator, readiness_target)`.
2. Fall back to `(family, query_type)`.
3. Fall back to `(family)`.
4. Fall back to the global default.

---

## 8. Research Economics Layer (VOI x Moat)

The roadmap itself should be scheduled by value of information, not by novelty.
This is the architectural translation of the dialogue's "what creates a moat vs what becomes a research swamp?" distinction.

### 8.1. Frontier track scoring

```python
class FrontierTrackScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: FrontierFamily
    moat_depth: float                  # how hard is this to replicate?
    theoretical_maturity: float        # how settled is the theory?
    code_adjacency: float              # how close is this to current modules?
    benchmark_leverage: float          # how much does it expand measurable capability?
    policy_relevance: float            # direct practical payoff
    compute_burden: float              # inverse score: higher = worse
    assumption_load: float             # inverse score: higher = worse
    integration_bonus: float           # value unlocked by combining with existing stack
```

### 8.2. Initial economic view

| Family | Moat depth | Maturity | Adjacency | Policy relevance | Initial verdict |
|--------|------------|----------|-----------|------------------|-----------------|
| Compositional | very high | medium | high | very high | build first |
| Sharp bounds | high | high | very high | very high | build first |
| Continuous-time | high | medium | medium-high | very high | build second |
| Distributional OT | high | medium | medium | high | build second |
| Strategic | very high | medium | medium | very high | build third (reduced scope) |
| Abstraction | high | medium | medium | high | build third (finite-state scope) |
| Discovery + algebraic | high | medium | high | medium-high | build third (CI scope) |
| Latent representation | very high | low-medium | low | medium | gated research lane |
| Topological interference | very high | low | low | medium | horizon lane only |

### 8.3. Anti-swamp rules

1. No new family gets >1 phase of investment without a benchmark proxy.
2. No family may bypass a cheap synthetic benchmark and jump directly to policy-critical claims.
3. Every family must define a fallback output before production work begins.
4. Horizon lanes must consume a capped research budget fraction.
5. If a frontier track cannot state what artifact it will emit, it is not ready to start.

### 8.4. Kill rules and exit criteria

```python
class FrontierTrackHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: FrontierFamily
    phases_invested: int
    benchmark_proxy_exists: bool
    hidden_holdout_variance: float | None
    artifact_type_stabilized: bool
    last_benchmark_improvement_phase: int | None

class TrackDecision(str, Enum):
    CONTINUE = "continue"
    DOWNGRADE_TO_RESEARCH_ONLY = "downgrade_to_research_only"
    FREEZE = "freeze"
    KILL = "kill"
```

**Automatic downgrade conditions**:
1. If a family has no benchmark proxy after **2 phases** of investment, its status drops to `research-only` and it loses production budget.
2. If hidden-holdout variance exceeds **2x the baseline family** variance, readiness ceiling cannot be raised regardless of other evidence.
3. If artifact type has not stabilized after **2 phases**, the track is frozen pending architectural review.

**Automatic freeze conditions**:
1. If no benchmark improvement is recorded for **3 consecutive phases**, the track is frozen.
2. If compute cost exceeds **10x the cost-to-value threshold** set by `ComputeJudge`, the track is frozen until compute efficiency improves.

**Kill criteria**:
1. A frozen track that remains frozen for **2 additional phases** is killed (archived, no further investment).
2. Any track where the theoretical foundation is invalidated is killed immediately.

**Decision authority**: track downgrade and freeze are automatic. Kill decisions require human review with documented rationale.

### 8.5. Integration premium

The true moat is not the sum of individual capabilities.
It is the governed integration that competitors cannot replicate piecemeal.

```text
moat = base_proof_kernel_value
     + sum(family_value[i] for each realized family i)
     + integration_premium(set of realized families)
```

The integration premium is superlinear: each additional family that passes full judge-stack certification amplifies the value of existing families. The core moat (proof kernel + sharp bounds + compositional causality) is already a strong competitive position. The roadmap must not create false pressure to pursue all directions simultaneously.

---

## 9. Causal Readiness Contract

Every promoted artifact needs a typed readiness label.
This prevents research artifacts from leaking into decision support.

```python
class CausalReadiness(str, Enum):
    PROOF_ONLY = "proof_only"
    BOUNDS_READY = "bounds_ready"
    ESTIMATION_READY = "estimation_ready"
    SIMULATION_READY = "simulation_ready"
    POLICY_PLANNING_READY = "policy_planning_ready"
    AUDIT_READY = "audit_ready"
```

```python
class DataReadinessRequirement(BaseModel):
    """Normative minimum data quality thresholds, not an observed report."""
    model_config = ConfigDict(extra="forbid")

    min_ess_ratio: float | None
    min_overlap_grade: OverlapGrade | None
    max_missingness_regime: MissingnessRegime | None
    min_nuisance_feasibility: Literal["feasible", "marginal"] | None
    min_measurement_comparability: Literal["high", "medium", "low"] | None

class CausalReadinessContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness_level: CausalReadiness
    required_judges_passed: list[str]
    required_uncertainty_bounds: dict[FrontierUncertaintyType, float]
    mandatory_disclosures: list[str]
    mandatory_benchmark_suites: list[str]
    human_gate_required: bool
    expiry_conditions: list[str]
    data_readiness_requirement: DataReadinessRequirement | None
```

### 9.1. Readiness mapping

| Readiness | What it means | Typical artifact types | Data readiness requirement |
|----------|----------------|------------------------|--------------------------|
| PROOF_ONLY | symbolic proof or impossibility result only | `ProofBundle`, `NegativeCertificate` | none |
| BOUNDS_READY | non-ID but quantitatively bounded and benchmarked | `BoundsBundle`, `SensitivityReport` | `min_overlap_grade=weak`, `min_ess_ratio=0.05` |
| ESTIMATION_READY | identified and estimated on validated static settings | ATE/CATE/path-specific estimates | `min_overlap_grade=adequate`, `min_ess_ratio=0.1`, `min_nuisance_feasibility=marginal` |
| SIMULATION_READY | can drive scenario simulation with explicit limits | temporal trajectories, transport scenarios | `min_overlap_grade=adequate`, `min_ess_ratio=0.1`, `min_nuisance_feasibility=feasible` |
| POLICY_PLANNING_READY | safe enough to enter policy design loops | policy value + harms + strategic notes | `min_overlap_grade=strong`, `min_ess_ratio=0.2`, `min_nuisance_feasibility=feasible` |
| AUDIT_READY | replayable, benchmarked, governed, externally defensible | finalized champion artifacts | POLICY_PLANNING_READY + `min_measurement_comparability=high` |

### 9.2. Cardinal readiness rule

Frontier families start with a cap:

| Family | Initial readiness cap |
|--------|------------------------|
| Compositional | ESTIMATION_READY |
| Sharp bounds | BOUNDS_READY |
| Continuous-time | SIMULATION_READY |
| Distributional OT | SIMULATION_READY |
| Strategic | SIMULATION_READY |
| Abstraction | SIMULATION_READY |
| Discovery + algebraic | ESTIMATION_READY |
| Latent representation | PROOF_ONLY |
| Topological interference | PROOF_ONLY |

Caps can only be raised by hidden benchmark evidence and judge stack approval.

---

## 10. Direction I — Compositional Causality

### 10.1. Why this is the primary moat

Current open-source causal stacks assume one static graph.
Policy reality is federated: health has one causal model; labor has another; fiscal and monetary systems have another; the real question is often about the composition.

The moat is not "support multiple graphs".
The moat is **typed graph composition with explicit identifiability preservation and semantic alignment certification**.

### 10.2. Target abstraction

```python
class SCMFragment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fragment_id: str
    graph_ref: ArtifactRef
    semantic_namespace: str
    interface_variables: list[str]
    exposed_inputs: list[str]
    exposed_outputs: list[str]
    latent_summary: dict[str, str]
    measurement_models: dict[str, ArtifactRef]
    variable_definitions: dict[str, str]
```

```python
class CompositionCertificate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["preserved", "deferred", "broken", "unknown"]
    composed_graph_ref: ArtifactRef
    interface_mapping_ref: ArtifactRef
    alignment_report_ref: ArtifactRef
    checked_queries: dict[str, Literal["preserved", "broken", "unknown"]]
    newly_required_assumptions: list[str]
    structural_assumptions: list[str]
    alignment_assumptions: list[str]
    witness_ref: ArtifactRef | None
```

### 10.3. Operational interpretation

Composition should answer five questions:

1. Can the fragments be semantically aligned? (answered by `AlignmentReport`)
2. Can they be structurally glued without contradictions?
3. Which previously supported graphical obligations remain preserved after gluing?
4. Which new cross-domain queries become possible?
5. What assumptions were introduced by alignment versus structure?

### 10.3.1. Lazy evaluation for query preservation

Exhaustively computing preservation status for all possible queries is computationally infeasible for large graphs. Instead, query preservation follows a **lazy evaluation** (JIT) strategy:

1. At composition time, the `CompositionCertificate` verifies only **structural validity** and **semantic alignment**.
2. Query-specific preservation is checked **on demand** when a concrete query arrives, and the result is cached in `checked_queries`.
3. Phase B only guarantees results for query classes reducible to known graphical obligations (conditional-independence / backdoor-style checks on DAG/ADMG structure).
4. Unsupported query classes surface explicit `unknown` rather than overclaiming preserved identifiability.
5. Before running the graphical oracle, the graph is automatically reduced to the ancestors of the query's target, treatment, and conditioning variables.
6. Cached query results are invalidated if the underlying fragments, topology selection, or alignment certificates change.

### 10.4. Implementation scope (this document)

**Phase-1 compositional scope**:

1. acyclic DAG/ADMG fragments only;
2. shared observed interfaces only;
3. no automatic latent reconciliation;
4. identifiability preservation via **d-separation checks on composed graph** — specifically: checking whether paths that were blocked in individual fragments remain blocked after gluing, using standard graphical criteria;
5. semantic alignment via `VariableAlignmentCertificate` with metadata matching and human review;
6. no global theorem claim stronger than the current certificate.

> **Research boundary**: cyclic fragment composition, automatic latent-variable bridge synthesis, identifiability preservation proofs for graphs with latent interface confounders, and category-theoretic completeness claims are all deferred to `CAUSAL_ENGINE_RESEARCH_AGENDA.md` — Research Track 1.

### 10.5. Grounding in existing code

| Existing anchor | Why it matters |
|-----------------|----------------|
| `ir/analytics/causal_graph.py` | core graph IR and metadata attachment |
| `ir/analytics/cross_graph.py` | natural home for composition contracts |
| `ir/analytics/alignment_certification.py` | existing typed alignment-certificate substrate |
| `foundry/methods/catalog/causal/graph_reconciliation.py` | current graph alignment foothold |
| `foundry/methods/catalog/causal/twin_graph.py` and `amn.py` | evidence that derived graph builders already fit the architecture |
| `scientist/cross_graph/*` | existing multi-source evidence flow |
| `scientist/nodes/builtins/causal/reconcile_causal_graph.py` | pipeline integration point |
| `datasets/knowledge/variable_alignment.py` | existing variable-match scoring and bridge substrate |
| `data/dataset_catalog/seed_variable_alignments.yaml` | existing variable alignment metadata |

### 10.6. Promotion rule

No composed graph may be promoted as a single "truth graph" without a certificate that says:

1. what was preserved,
2. what broke,
3. what remained unresolved,
4. which assumptions were injected by composition itself,
5. which assumptions were injected by semantic alignment,
6. the alignment type for every interface variable.

---

## 11. Direction II — Sharp Identification, Bounds, and Recovery

### 11.1. Core principle

Point identification is a special case.
The engine must treat partial identification as a first-class success mode.

```text
ID failed
  -> derive sharp bounds if possible
  -> derive outer or inner bounds if sharpness is unknown
  -> issue constructive counterexample or hedge
  -> emit experiment / measurement / transport rescue actions
```

### 11.2. Required artifacts

```python
class BoundsBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimand_id: str
    point_identified: bool
    lower_bound: float | None
    upper_bound: float | None
    sharpness_status: Literal["sharp", "inner_approx", "outer_approx", "unknown"]
    proof_ref: ArtifactRef
    dual_certificate_ref: ArtifactRef | None
    compatible_worlds_ref: ArtifactRef | None
    rescue_actions: list[str]
```

```python
class RecoveryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocking_reason: str
    candidate_actions: list[str]
    minimal_oracle_sets: list[list[str]]
    expected_width_reduction: float | None
```

### 11.3. Why this is high ROI

1. it upgrades every current non-ID result from a dead end into a usable artifact;
2. it fits the current symbolic orientation of the engine;
3. it is benchmarkable early;
4. it compounds directly with transportability, missing data, and policy risk reporting.

### 11.4. Implementation scope (this document)

Implement known bounds families: Balke-Pearl LP bounds, Manski bounds, existing semiparametric bounds, transport bounds, sensitivity bounds.

> **Research boundary**: novel sharpness proofs for complex query families and automated bound tightening with convergence guarantees are deferred to `CAUSAL_ENGINE_RESEARCH_AGENDA.md` — Research Track 2.

### 11.5. Grounding in existing code

| Existing anchor | Extension path |
|-----------------|----------------|
| `bounds_engine.py` | orchestrator for bounds-first fallback |
| `lp_bounds.py` | exact LP-based sharp or near-sharp intervals |
| `eif_bounds.py` | semiparametric bounds and influence-function tooling |
| `transport_bounds.py` | transport-specific bounds |
| `sensitivity_bounds.py` | explicit latent confounding sensitivity |
| `ir/analytics/partial_identification.py` | existing bounds/result IR to unify rather than replace |
| `ir/analytics/negative_certificate.py` | blocking-certificate anchor |
| `optimal_design.py` | natural source of recovery actions |

### 11.6. Cardinal rule

For supported query families, the engine must never return a bare `non_identified` without at least one of:

1. `BoundsBundle`
2. `NegativeCertificate`
3. `RecoveryPlan`

---

## 12. Direction III — Continuous-Time Causal Dynamics

### 12.1. Why scalar ATE is not enough

Policies unfold over time. Decision-makers care about:

1. delay before effect appears;
2. transient harms before long-run gains;
3. decay, overshoot, or plateau;
4. cumulative budget exposure over a horizon.

### 12.2. Required contracts

```python
class ContinuousTimeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intervention_trajectory_ref: ArtifactRef
    outcome_process: str
    horizon_start: float
    horizon_end: float
    target_functional: Literal[
        "effect_path",
        "integral_effect",
        "time_to_threshold",
        "occupancy_probability",
    ]
    sampling_scheme: str
```

```python
class EffectTrajectoryBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_ref: ArtifactRef
    trajectory_ref: ArtifactRef
    confidence_band_ref: ArtifactRef
    solver_diagnostics_ref: ArtifactRef
    discretization_error: float | None
    path_representation: Literal["linear_sde", "ode", "neural_cde", "neural_sde"]
```

### 12.3. Implementation scope (this document)

MVP build path:

1. start with linear Gaussian SDE and piecewise-constant interventions;
2. support impulse response and cumulative effect functionals;
3. discrete-time fallback always available.

> **Research boundary**: irregular sampling support via rough-path signatures and causal rough-path semantics, and neural SDE identification theory, are deferred to `CAUSAL_ENGINE_RESEARCH_AGENDA.md` — Research Track 3.

### 12.4. Anti-overclaiming rules

No temporal artifact may be promoted unless it states:

1. the time scale;
2. the solver family;
3. the discretization error or why it is unavailable;
4. the intervention interpolation policy;
5. whether strategic adaptation is absent or modeled separately.

### 12.5. Grounding in existing code

| Existing anchor | Why it matters |
|-----------------|----------------|
| `structural_time_series.py` | current foothold for time-aware causal reasoning |
| `ir/analytics/dynamic_regime.py` | natural home for temporal policy IR |
| `g_computation.py` | longitudinal estimation bridge |
| `dtr.py` | dynamic treatment regime integration |
| `scientist/nodes/builtins/simulate/run_simulation.py` | scenario execution point |
| `scientist/nodes/builtins/simulate/propagate_uncertainty.py` | uncertainty propagation anchor |

---

## 13. Direction IV — Distributional Causality via Optimal Transport

### 13.1. Core principle

Policy design should compare distributions, not only averages.
A mean-improving policy can still worsen tails, concentration, or subgroup volatility.

### 13.2. Artifact type classification

Distributional artifacts must be classified by their causal justification level.
OT produces geometrically beautiful objects that can look deeper than they are actually justified.

```python
class DistributionalJustification(str, Enum):
    IDENTIFIED = "identified"          # causally justified counterfactual distribution
    BOUNDED = "bounded"                # partially identified distributional bounds
    SCENARIO = "scenario"              # useful distributional comparison under explicit assumptions
```

```python
class DistributionalEffectBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    justification: DistributionalJustification
    baseline_distribution_ref: ArtifactRef
    counterfactual_distribution_ref: ArtifactRef
    coupling_ref: ArtifactRef | None
    wasserstein_distance: float | None
    quantile_shift_ref: ArtifactRef | None
    tail_risk_delta_ref: ArtifactRef | None
    subgroup_distribution_refs: list[ArtifactRef]
    causal_assumptions: list[str]
```

```python
class CouplingDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mass_conservation_error: float
    support_mismatch_note: str | None
    regularization_strength: float | None
    identifiability_assumptions: list[str]
```

### 13.3. Implementation scope (this document)

Implement: distributional bundle with justification typing, Wasserstein/quantile/tail outputs, coupling diagnostics, compute budget enforcement (Sinkhorn regularization mandatory; raw-data OT prohibited), subgroup distribution comparisons.

**Scope lock**: distributional artifacts start as `SCENARIO` justification unless the proof kernel explicitly supports distributional estimands. Upgrading to `BOUNDED` or `IDENTIFIED` is **research-gated**: Research Track 4.3 must first define the admissible distributional estimand class and the proof-kernel integration spec. Only after that result exists may Layer A engineering implement the extension; no speculative Layer A upgrade work is in scope here.

> **Research boundary**: proof-kernel formalization for distributional estimands, causally justified OT couplings under partial identification, and theory for bounded distributional effects under partial ID are deferred to `CAUSAL_ENGINE_RESEARCH_AGENDA.md` — Research Track 4.

### 13.4. Cardinal rules

1. Distributional OT cannot be presented as `IDENTIFIED` unless the causal query is identified or properly bounded, coupling assumptions are surfaced, and mass conservation diagnostics pass.
2. `SCENARIO`-justified artifacts are capped at `SIMULATION_READY`.
3. `BOUNDED`-justified artifacts are capped at `BOUNDS_READY`.
4. The `justification` field must be set by the proof kernel, not by the OT module itself.

### 13.5. Grounding in existing code

| Existing anchor | Extension path |
|-----------------|----------------|
| `ir/analytics/distributional.py` | natural IR for distributional outputs |
| `scientist/backtesting/distributional.py` | evaluation harness anchor |
| `scientist/nodes/builtins/simulate/run_distributional_analysis.py` | workflow integration point |
| `density_ratio.py` | current reweighting and transport foothold |
| `transport_engine.py` | natural bridge between transportability and OT outputs |

---

## 14. Direction V — Strategic and Multi-Scale Policy Causality

### 14.1. Strategic causality contract

```python
class StrategicSCM(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_graph_ref: ArtifactRef
    strategic_agents: list[str]
    utility_refs: dict[str, ArtifactRef]
    policy_rule_ref: ArtifactRef
    equilibrium_concept: Literal["nash", "stackelberg", "best_response_fixed_point"]
    compute_budget: ComputeBudget
```

```python
class StrategicResponseBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    causal_component_ref: ArtifactRef
    strategic_closure_ref: ArtifactRef
    equilibrium_selection_dependence: str
    behavioral_assumption_sensitivity_ref: ArtifactRef | None
    equilibrium_set_ref: ArtifactRef
    selected_equilibrium_ref: ArtifactRef | None
    multiplicity_note: str | None
    performative_shift_ref: ArtifactRef | None
    post_adaptation_policy_value_ref: ArtifactRef
```

### 14.2. Computational tractability and strategic fallback

Equilibrium computation is NP-hard in general. The `ComputeJudge` for the strategic family operates in `fatal` mode.

**Strategic fallback hierarchy** (in order of preference):

1. **Strategic bounds**: compute worst-case and best-case effect under maximal rational deviation.
2. **Macro-abstracted equilibrium**: solve the equilibrium on a reduced macro-graph, then project strategies back.
3. **Block with explicit flag**: if neither bounds nor abstracted equilibrium is feasible, block with `unidentified_due_to_strategic_complexity`.

```python
class StrategicFallbackMode(str, Enum):
    EXACT_EQUILIBRIUM = "exact_equilibrium"
    STRATEGIC_BOUNDS = "strategic_bounds"
    MACRO_ABSTRACTED = "macro_abstracted"
    BLOCKED = "blocked"
```

### 14.3. Abstraction contract

```python
class AbstractionCertificate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    micro_graph_ref: ArtifactRef
    macro_graph_ref: ArtifactRef
    abstraction_map_ref: ArtifactRef
    preservation_type: Literal["exact", "approximate", "policy_value_only", "invalid"]
    preserved_queries: list[str]
    error_bound: float | None
```

### 14.4. Implementation scope (this document)

**Strategic scope lock**:
- Implement best-response / Stackelberg-only equilibrium for simple game forms.
- Implement compute budget enforcement with fatal mode.
- Implement strategic bounds fallback (max/min over agent responses).
- Implement strategic decomposition (causal component + strategic closure) only as a disclosed reduced-scope output for the modeled game class; do **not** claim uniqueness of that decomposition beyond the stated assumptions.
- Do **not** implement general Nash equilibrium computation for complex multi-agent games.

**Abstraction scope lock**:
- Implement exact abstraction verification for finite-state SCMs only.
- Implement abstraction maps and certificates with `preservation_type` field.
- Do **not** implement approximate abstraction error bounds for continuous models.

> **Research boundary**: complex strategic equilibria (beyond Stackelberg), performative prediction convergence, uniqueness conditions for causal/strategic decomposition, approximate abstraction bounds for continuous models, and faithful micro-to-macro transport conditions are deferred to `CAUSAL_ENGINE_RESEARCH_AGENDA.md` — Research Tracks 5 and 6.

### 14.5. Grounding in existing code

| Existing anchor | Why it matters |
|-----------------|----------------|
| `policy_learning.py` | policy rule and value logic |
| `dtr.py` | sequential policy optimization foothold |
| `foundry/agent_sim/*` | natural place for strategic-agent simulation |
| `ir/analytics/abm_bridge.py` | bridge to agent-based macro consistency |
| `scientist/backtesting/adversarial.py` | strategic stress and gaming harness |
| `scientist/nodes/builtins/causal/run_abm_consistency.py` | abstraction consistency insertion point |

### 14.6. Cardinal rules

1. No strategic result without equilibrium existence or an explicit failure card.
2. No macro recommendation without an abstraction certificate or an explicit "heuristic aggregation" disclaimer.
3. If multiple equilibria exist, multiplicity must be surfaced, not hidden by arbitrary selection.
4. Strategic outputs must always decompose into causal component + strategic closure.
5. Compute budget for equilibrium computation is mandatory and fatal.
6. Strategic fallback must not silently drop to a static ATE.

---

## 15. Direction VI — Discovery, Latents, and Algebraic Structure

### 15.1. Discovery should stay uncertainty-honest

The engine should output:

1. high-confidence edges;
2. disputed edges;
3. algebraically violated constraints;
4. latent hypotheses with explicit assumption load.

### 15.2. Required contracts

```python
class GraphHypothesisBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_graph_ref: ArtifactRef
    edge_confidence_ref: ArtifactRef
    bootstrap_stability_ref: ArtifactRef
    prior_evidence_refs: list[ArtifactRef]
    downstream_utility_ref: ArtifactRef | None
```

```python
class AlgebraicConstraintReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    implied_constraints_ref: ArtifactRef
    violated_constraints_ref: ArtifactRef
    severity: Literal["info", "warning", "blocker"]
    suggested_repairs: list[str]
```

```python
class LatentDiscoveryBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposed_latent_nodes: list[str]
    inducing_environments: list[str]
    identification_conditions: list[str]
    falsification_tests: list[str]
    trust_level: Literal["research", "conditional", "validated"]
```

### 15.3. Implementation scope (this document)

**E.1 scope lock**: implement algebraic constraint reports for **known implied constraints** (CI-based, standard tetrad constraints, overcomplete system checks). Report violated constraints with severity tiers. Do **not** implement general algebraic constraint discovery beyond known conditional independence families.

**E.2**: discovery utility judge is full engineering — governance/ranking, not new theory.

**E.3 scope lock**: implement latent discovery gate and schemas as a **governance gate** only. This means: assumption cards, readiness caps at `PROOF_ONLY`, no-promotion rules, falsification hooks, human gate requirement. Do **not** implement latent variable proposal logic in this scope.

**E.4 scope lock**: implement baseline prior + environment audit pipeline using `literature_prior` and `invariance_tests`. Do **not** build this as a latent discovery promotion mechanism; it is evidence collection infrastructure.

> **Research boundary**: algebraic constraints beyond conditional independence, latent cardinality identification from distributional shifts, and the promotion criteria for latent artifacts are deferred to `CAUSAL_ENGINE_RESEARCH_AGENDA.md` — Research Tracks 7 and 8.

### 15.4. Why latent discovery is gated

Latent representation learning must not become a hallucination engine that inserts hidden variables whenever the fit is poor.

### 15.5. Grounding in existing code

| Existing anchor | Extension path |
|-----------------|----------------|
| `discovery_pipeline.py` | portfolio runner anchor |
| `constraint_discovery.py`, `dagma_discovery.py`, `pcmci_discovery.py` | current algorithm families |
| `literature_prior.py` | prior integration |
| `invariance_tests.py` | multi-environment anchor |
| `measurement_error.py` | latent/proxy boundary conditions |
| `ir/analytics/causal_discovery.py` | natural schema location |
| `scientist/discovery/utility_judge.py` | existing downstream-utility ranking substrate |
| `scientist/cross_graph/gatherers/academic.py` | external evidence integration |

### 15.6. Cardinal rule

Latent variables may not be promoted beyond `PROOF_ONLY` unless the artifact includes:

1. environment assumptions,
2. falsification tests,
3. a clear statement that the latent is inferred, not observed.

---

## 16. Direction VII — Hypergraph Interference and Topology

### 16.1. What this solves

Pairwise interference is often the wrong abstraction. Real policy spillovers occur in groups: households, classrooms, firm clusters, supply chains, municipal coalitions.

### 16.2. Why this is a horizon lane (and why contracts are still needed now)

The identification theory is immature, estimation cost can explode, and naive implementation would create a research sink. However, architectural space is reserved now for two reasons:

1. **Prevent retrofitting cost**: if topological reasoning is designed in later, it will require invasive changes to the interference IR, the exposure model, and the governance layer.
2. **Protect the pairwise layer**: by defining `InterferenceCertificate.fallback_mode` now, the architecture forces any future topological extension to declare its relationship to the existing pairwise layer.

### 16.3. Required contracts (F.1 — implementation scope)

```python
class InteractionComplex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[str]
    hyperedges: list[list[str]]
    simplices: list[list[str]]
    exposure_operator_ref: ArtifactRef
    reduction_policy: Literal["pairwise_projection", "cluster_projection", "full_complex"]
```

```python
class InterferenceCertificate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supported_query_family: str
    exposure_assumptions: list[str]
    reduction_error_bound: float | None
    fallback_mode: Literal["pairwise", "clustered", "unsupported"]
```

> **Research boundary**: exposure-complex estimators, pairwise/cluster fallback certificates, and the benchmark pack for hypergraph interference are deferred to `CAUSAL_ENGINE_RESEARCH_AGENDA.md` — Research Track 9. F.2–F.4 proceed only if theoretical foundations mature.

### 16.4. Grounding in existing code

| Existing anchor | Why it matters |
|-----------------|----------------|
| `interference.py` | current interference footing |
| `ir/analytics/interference.py` | schema insertion point |
| `scientist/governance/passes/sutva_check_pass.py` | explicit governance boundary |

### 16.5. Cardinal rule

Topology-aware artifacts must never silently masquerade as standard pairwise interference outputs.
If the engine reduces a complex to a simpler approximation, that reduction must be explicit.

---

## 17. Shared Infrastructure

### 17.1. Unified proof-carrying artifact model

Every advanced artifact should trace back to:

1. query ref,
2. graph ref,
3. proof or failure-certificate ref,
4. data readiness report ref,
5. alignment report ref (if composition was involved),
6. execution plan ref if estimation was involved,
7. benchmark packet ref,
8. replay bundle ref.

### 17.2. Registries

| Registry | Purpose |
|----------|---------|
| ProofRegistry | stores proof traces, hedge certificates, negative certificates |
| BoundsRegistry | stores `BoundsBundle`, dual certificates, rescue plans |
| FrontierRegistry | stores frontier-family artifacts and readiness caps |
| BenchmarkRegistry | visible, hidden, rotating, adversarial suites |
| TheoremRegistry | catalogs theorem families, preconditions, and supported query classes |
| CounterexampleRegistry | stores canonical failure graphs and challenge cases |
| ReplayRegistry | stores deterministic replay bundles for promoted artifacts |
| AlignmentRegistry | stores `VariableAlignmentCertificate` and `AlignmentReport` instances |
| DataReadinessRegistry | stores `DataReadinessReport` history for audit and trend analysis |
| JudgeThresholdRegistry | stores versioned judge thresholds with change audit trail |
| FalsificationRegistry | stores post-deployment telemetry and invalidation verdicts |
| OntologyDisputeRegistry | tracks active and resolved ontology disputes across fragments |

### 17.3. Benchmark architecture

```text
┌────────────────────┐
│ Visible Gold       │  current symbolic / transport / missing suites
├────────────────────┤
│ Frontier Gold      │  composition / bounds / temporal / OT / strategic
├────────────────────┤
│ Hidden Holdout     │  promotion gate for each family
├────────────────────┤
│ Rotating Challenge │  prevents benchmark gaming
├────────────────────┤
│ Sentinel Cases     │  known-correct stress and regression cases
├────────────────────┤
│ Adversarial Cases  │  designed to fool weak approximations
└────────────────────┘
```

### 17.4. Cold start protocol for new frontier families

Every new frontier family must begin with:

1. a minimal synthetic theorem-faithful benchmark,
2. a visible canary suite,
3. 5–10 sentinel cases,
4. a hidden holdout split,
5. a declared degraded fallback.

Only after this may it enter policy workflows.

### 17.5. Cross-run transfer isolation

What can transfer across runs:

1. theorem metadata,
2. benchmark results,
3. replay bundles,
4. low-level solver diagnostics.

What must stay scoped:

1. domain-specific surrogates,
2. latent-variable proposals,
3. equilibrium-selection heuristics,
4. topology simplification policies.

### 17.6. Grounding in existing code

| Existing anchor | Role |
|-----------------|------|
| `scientist/replay/*` | replay and diff substrate |
| `scientist/search/*` | search and benchmark routing |
| `scientist/backtesting/*` | trust scoring and holdouts |
| `scientist/engine/budget.py` | compute controls |
| `core/artifacts/*` and `.polisyos/artifacts` | CAS lineage |

---

## 18. Architectural Invariants and Failure Modes

### 18.1. Invariants

1. **No advanced artifact without a proof anchor**: every promoted result points to an identified estimand, a bounds artifact, or a negative certificate.
2. **No silent upgrade from non-ID to ID**: execution layers may not erase identification failure.
3. **No composition without semantic alignment**: graph stitching requires both structural compatibility and measurement comparability verification.
4. **No estimation without data readiness**: Layer B must verify `DataReadinessReport` before compiling any estimation plan.
5. **No temporal claim without time contract**: time scale, interpolation, and solver diagnostics are mandatory.
6. **No OT artifact without coupling diagnostics and justification level**: mass conservation is not optional; justification type is not optional.
7. **No strategic claim without equilibrium disclosure and component decomposition**: multiplicity or instability must remain visible; causal and strategic components must be reported separately.
8. **No abstraction without preservation type**: exact, approximate, policy-value-only, or invalid.
9. **No latent node without assumption card**: inferred hidden structure must carry environment assumptions.
10. **No topological artifact may degrade silently**: pairwise reductions must be explicit.
11. **No promoted artifact without replay bundle**: promotion without reproducibility is a system bug.
12. **No A2-stratum proof without oracle disclosure**: outputs from the oracle-backed proof layer must be flagged.
13. **No exported artifact without fragility index**: every `ExportedCausalArtifact` must carry a `FragilityReport`.
14. **No POLICY_PLANNING_READY artifact without falsification endpoint**: artifacts at this level must accept post-deployment telemetry.
15. **No strategic fallback to naive static ATE**: strategic degradation must use bounds, abstracted equilibrium, or block.

### 18.2. Failure modes and mitigations

| # | Failure mode | Impact | Mitigation |
|---|--------------|--------|-----------|
| 1 | Invalid graph stitching | false cross-domain claims | `CompositionCertificate`, `AlignmentReport`, hidden merge suite |
| 2 | Semantically false alignment | formally valid but meaningless cross-domain claims | `VariableAlignmentCertificate`, `AlignmentJudge`, human review |
| 3 | Bounds reported as sharp when not | false certainty | `BoundJudge`, dual witness requirement |
| 4 | Estimation on insufficient data | unreliable estimates presented as reliable | `DataReadinessReport`, `DataJudge` |
| 5 | Continuous-time solver drift | wrong trajectories | `DynamicsJudge`, stiffness diagnostics, discrete-time fallback |
| 6 | OT coupling artifacts | misleading tail stories | mass conservation checks, justification typing |
| 7 | Equilibrium multiplicity hidden | false policy ranking | `StrategicJudge`, explicit multiplicity notes |
| 8 | Abstraction leakage | ecological fallacy | `AbstractionCertificate`, micro-to-macro holdouts |
| 9 | Latent confounder hallucination | pseudo-explanations | environment audit, readiness cap at `PROOF_ONLY` |
| 10 | Algebraic model testing overfires | false graph rejection | severity tiers, benchmarked constraint tolerance |
| 11 | Hypergraph complexity explosion | unusable compute profile | fallback to cluster or pairwise mode |
| 12 | Frontier benchmark gaming | illusory SOTA | rotating hidden suites and sentinels |
| 13 | A2-stratum proof treated as A0 | false confidence | stratum labeling, `proof_stratum` field |
| 14 | Warning fatigue | analysts ignore critical risks | `FragilityReport` with ranked top drivers |
| 15 | Post-deployment artifact staleness | policy based on outdated estimates | falsification loop, expiry dates |
| 16 | Strategic fallback to naive ATE | practically misleading policy advice | strategic bounds hierarchy, blocked mode |
| 17 | Ontology dispute blocks pipeline | competing definitions create deadlock | dispute resolution protocol with forked analysis |
| 18 | Composition query explosion | attempting to check all queries on large composed graphs | lazy evaluation with Markov blanket reduction |

---

## 19. Degraded Mode and Safe Fallback

Degradation must be explicit.
When advanced modules fail, the system must fall back to a weaker but honest artifact.

### 19.1. Degradation hierarchy

| Condition | Mode | What changes | Max readiness |
|-----------|------|--------------|---------------|
| All families healthy | normal | full stack available | AUDIT_READY |
| Frontier family uncalibrated | research-only mode | artifact produced, no promotion | PROOF_ONLY |
| Alignment pending human review | reduced-readiness composition | PROXY only, human review queued | BOUNDS_READY |
| Alignment proxy-only | proxy-acknowledged composition | proxy sensitivity analysis | ESTIMATION_READY |
| Alignment blocked | composition blocked | no composition until review | N/A |
| Ontology dispute unresolved | forked analysis | both definitions computed | BOUNDS_READY |
| Data readiness blockers | bounds-only mode | estimation blocked | BOUNDS_READY |
| Continuous-time backend unavailable | discrete-time fallback | piecewise approximation only | SIMULATION_READY |
| OT diagnostics fail | scalar-only mode | means/quantiles only | ESTIMATION_READY |
| Strategic solver timeout | strategic bounds or block | bounds if tractable; else blocked | BOUNDS_READY (bounds) or N/A |
| Abstraction certificate invalid | micro-only mode | macro outputs blocked | ESTIMATION_READY |
| Latent assumptions fail | sensitivity-only mode | latent proposals disabled | BOUNDS_READY |
| Hypergraph module unavailable | pairwise-interference mode | cluster/pairwise estimators only | ESTIMATION_READY |
| Hidden benchmark missing | no-promotion mode | artifacts stored, not promoted | PROOF_ONLY |

### 19.2. Fallback rules

1. Degradation must emit a machine-readable mode switch.
2. Degradation may reduce capability; it may not increase readiness.
3. When uncertain whether a frontier artifact is trustworthy, the engine must freeze promotion and keep the proof-level output.

---

## 20. Execution Phases

Implementation note: the phases below assume the current benchmarked causal floor is already present in the repository. Unless explicitly stated otherwise, each deliverable should be implemented by **hardening, unifying, or extending existing modules**, not by rebuilding the same capability from scratch in a second location.

### Phase A — Proof-Carrying Core Closure

**Goal**: harden the current engine so every query ends in a valid proof artifact, bounds artifact, or explicit impossibility artifact. Establish data readiness gates and judge stack.

| # | Deliverable | Module | Depends on |
|---|-------------|--------|------------|
| A.1 | Unified `ProofBundle` (with stratum), `BoundsBundle`, `RecoveryPlan` schemas | `ir/analytics/causal.py`, `ir/analytics/partial_identification.py`, `ir/analytics/negative_certificate.py` | — |
| A.2 | `DataReadinessReport` contract and verification | `ir/analytics/causal.py`, `scientist/search/funnel/level2_causal.py`, `scientist/search/readiness.py` | A.1 |
| A.3 | Bounds-first fallback from negative ID results | `foundry/methods/catalog/causal/bounds_engine.py`, `id_engine.py`, `ir/analytics/negative_certificate.py` | A.1 |
| A.4 | Causal judge stack with numerical thresholds and `JudgeThresholdRegistry` | `scientist/search/judge_stack.py`, `scientist/search/readiness.py`, `scientist/search/failure_cards.py` | A.1, A.2 |
| A.5 | Hidden benchmark registry for frontier families | `scientist/search/benchmark_registry.py`, `scientist/backtesting/*` | A.4 |
| A.6 | Replay requirement for promoted causal artifacts | `runtime/replay.py`, `scientist/replay/*` | A.4 |

**Acceptance**:

1. no supported non-ID query returns a bare dead end;
2. current benchmark floor stays green: symbolic, transport, missing, discovery, policy/interference, adversarial-stress, and reproducibility suites;
3. promoted causal artifacts have replay bundles;
4. all estimation paths verify data readiness before execution;
5. judge stack produces machine-readable verdicts with numerical metrics.

**Exit criteria**: all acceptance criteria met for 2 consecutive test cycles. If not met within allocated time, scope is reduced to A.1 + A.3 + A.4 (minimum viable core) and remaining items roll to Phase A'.

---

### Phase B — Compositional Causality with Semantic Alignment

**Goal**: support stitched SCM fragments with composition certificates and semantic alignment verification.

| # | Deliverable | Module | Depends on |
|---|-------------|--------|------------|
| B.1 | `SCMFragment`, interface schemas, `VariableAlignmentCertificate`, `AlignmentReport` | `ir/analytics/cross_graph.py`, `ir/analytics/alignment_certification.py` | A.1 |
| B.2 | Alignment verification engine (metadata matching, transform checks, reviewer states, ontology warnings) | `ir/analytics/alignment_certification.py`, `datasets/knowledge/variable_alignment.py`, `scientist/cross_graph/compiler.py` | B.1 |
| B.3 | Composition engine and certificate (acyclic DAG/ADMG, observed interfaces only) | `foundry/methods/catalog/causal/graph_reconciliation.py`, `scientist/nodes/builtins/causal/reconcile_causal_graph.py` | B.1, B.2 |
| B.4a | Query preservation checker — graphical-obligation preservation on composed graph (known graphical results only; CI/backdoor-style queries only in Phase B) | `foundry/methods/catalog/causal/admg_ops.py` + companion helper adjacent to `graph_reconciliation.py` | B.3 |
| B.5 | Composition + alignment benchmark suite (curated ministry-style cases, invalid stitching, proxy/latent_bridge failure cards) | `benchmarks` + `scientist/backtesting/*` | B.3 |

> **B.4b — Research track**: preservation of identifiability under latent interface confounders and preservation of do-calculus derivations across fragments are deferred to `CAUSAL_ENGINE_RESEARCH_AGENDA.md` — Research Track 1.

**Acceptance**:

1. valid fragment composition works on curated ministry-style cases;
2. invalid stitching is rejected with explicit failure cards;
3. preservation status is surfaced per query via known graphical checks for query classes reducible to CI/backdoor-style obligations; unsupported query classes return explicit `unknown`;
4. every composition carries an `AlignmentReport` with per-variable certificates;
5. `PROXY` and `LATENT_BRIDGE` alignments inject assumptions into the composition certificate.

**Exit criteria**: B.1–B.3 + B.4a + B.5 are the minimum deliverable. For Phase B, B.4a is satisfied by known graphical-preservation results only; anything requiring general identifiability preservation, counterfactual derivation preservation, or do-calculus proof reuse is explicitly deferred to research-track work.

---

### Phase C — Continuous-Time and Temporal Compiler

**Goal**: move from static effects to effect trajectories.

| # | Deliverable | Module | Depends on |
|---|-------------|--------|------------|
| C.1 | `ContinuousTimeQuery` and `EffectTrajectoryBundle` | `ir/analytics/dynamic_regime.py` | A.1 |
| C.2 | Temporal estimand compiler (linear SDE / piecewise ODE / piecewise-constant interventions) | `foundry/methods/catalog/causal/structural_time_series.py` + temporal compiler companion in the causal catalog | C.1 |
| C.3 | Linear-SDE backend | `foundry/methods/catalog/causal/structural_time_series.py`, `g_computation.py`, `dtr.py` | C.2 |
| C.5 | Temporal benchmark suite (gold tasks, discretization diagnostics, hidden temporal suites) | `benchmarks` + `scientist/backtesting/*` | C.3 |

> **C.4 — Research track**: rough-path / irregular sampling support (future companion to `structural_time_series.py`) is deferred to `CAUSAL_ENGINE_RESEARCH_AGENDA.md` — Research Track 3. It may be deferred if irregular sampling is not yet needed for active policy cases.

**Acceptance**:

1. engine returns effect paths with confidence bands on temporal gold tasks;
2. discretization diagnostics are always surfaced;
3. fallback to discrete-time remains available.

Implementation notes:

- publication-grade Phase C execution routes through `CausalEngine.temporal_causal_effect()` only;
- `ContinuousTimeQuery` supports `fixed_intervention` and `optimal_policy_discovery` modes;
- adaptive DTR temporal execution must persist both the learned `DynamicTreatmentRegime` artifact and the derived executable schedule artifact;
- temporal benchmark gates require reloadable CAS lineage for query / intervention-or-derived-schedule / policy (when applicable) / trajectory / confidence band / diagnostics / bundle.

**Exit criteria**: C.1–C.3 + C.5 are the minimum.

---

### Phase D — Distributional, Strategic, and Abstraction Layer

**Goal**: model tails, adaptation, and micro-to-macro consistency.

| # | Deliverable | Module | Scope lock |
|---|-------------|--------|------------|
| D.1 | OT-based distributional bundle with justification typing, coupling diagnostics, Wasserstein/quantile/tail outputs | `ir/analytics/distributional.py`, `scientist/nodes/builtins/simulate/run_distributional_analysis.py`, `foundry/methods/catalog/causal/density_ratio.py` | **Scope lock**: justification defaults to `SCENARIO`; no `IDENTIFIED` without proof kernel extension |
| D.2 | Strategic SCM contracts, Stackelberg/best-response solver, compute budget enforcement, strategic fallback hierarchy | `foundry/methods/catalog/causal/policy_learning.py`, `dtr.py` + strategic companion module in the causal catalog | **Scope lock**: Stackelberg-only / simple best response; no general Nash for complex multi-agent games |
| D.3 | Exact abstraction maps and certificates for finite-state SCMs | `ir/analytics/abm_bridge.py` + abstraction companion adjacent to it, `scientist/nodes/builtins/causal/run_abm_consistency.py` | **Scope lock**: finite-state exact abstraction only; no approximate bounds for continuous models |
| D.4 | Strategic and abstraction challenge suites (strategic gaming, multiplicity disclosure, abstraction leakage) | `scientist/backtesting/adversarial.py` + new suites | D.2 |

> **Research boundary**: Track 4 governs any upgrade of D.1 beyond `SCENARIO`, including proof-kernel formalization for distributional estimands (Track 4.3), causally justified OT couplings (Track 4.1), and bounded distributional effects under partial ID (Track 4.2). Track 5 governs extension beyond reduced-scope strategic mode, including complex equilibria, performative convergence, and conditions under which the causal/strategic decomposition is well-defined. Track 6 governs approximate abstraction bounds and faithful micro-to-macro transport for continuous models.

**Acceptance**:

1. distributional outputs carry justification type and pass mass-conservation and subgroup tests;
2. strategic outputs decompose into causal + strategic closure components;
3. strategic outputs respect compute budgets with fatal enforcement;
4. macro outputs require abstraction certificates.

**Exit criteria**: D.1 and D.4 are minimum. D.2–D.3 may be delivered in reduced scope as stated above.

---

### Phase E — Discovery, Algebraic Testing, and Latent Research Gate

**Goal**: strengthen discovery without letting latent speculation corrupt the core.

| # | Deliverable | Module | Scope lock |
|---|-------------|--------|------------|
| E.1 | Algebraic constraint reports for known implied constraints (CI-based, tetrad, overcomplete systems) | `foundry/methods/catalog/causal/constraint_discovery.py`, `ir/analytics/causal_discovery.py` | **Scope lock**: known CI and standard algebraic families only |
| E.2 | Discovery utility judge | `scientist/discovery/utility_judge.py`, `foundry/methods/catalog/causal/discovery_pipeline.py` | E.1 |
| E.3 | Latent discovery gate and schemas as governance gate (assumption cards, caps, no-promotion rules, falsification hooks, human gate) | `ir/analytics/causal_discovery.py`, `foundry/methods/catalog/causal/measurement_error.py` + governance companion in `scientist/search/*` | **Scope lock**: governance scaffolding only, not a latent proposer |
| E.4 | Prior + environment audit pipeline (baseline: `literature_prior`, `invariance_tests`) | `foundry/methods/catalog/causal/literature_prior.py`, `invariance_tests.py`, `scientist/cross_graph/gatherers/academic.py`, `scientist/nodes/builtins/causal/build_literature_prior.py` | **Scope lock**: evidence collection infrastructure, not a promotion mechanism |

> **Research boundary**: algebraic constraints beyond CI → Research Track 7. Latent cardinality identification, separation of latent confounding vs proxy mismatch / measurement error, and promotion criteria above `PROOF_ONLY` → Research Track 8.

**Acceptance**:

1. discovery outputs disputed edges and violated constraints explicitly;
2. latent proposals are capped at `PROOF_ONLY` and assumption-bounded;
3. downstream utility affects graph ranking.

**Exit criteria**: E.1–E.2 are minimum. E.3–E.4 may remain at governance-scaffolding status if environment audit infrastructure is not yet mature.

---

### Phase F — Hypergraph Topology Contracts

**Goal**: define contracts for group-interaction reasoning without blocking the main roadmap. Implementation is gated.

| # | Deliverable | Module | Depends on |
|---|-------------|--------|------------|
| F.1 | `InteractionComplex` IR and `InterferenceCertificate` contracts | `ir/analytics/interference.py`, `foundry/methods/catalog/causal/interference.py` | A.1 |

> **F.2–F.4 — Research track**: exposure-complex estimators, pairwise/cluster fallback certificates, and the horizon benchmark pack are deferred to `CAUSAL_ENGINE_RESEARCH_AGENDA.md` — Research Track 9. They proceed only if theoretical foundations mature.

**Acceptance**:

1. contracts are defined and integrated into the IR layer;
2. existing interference performance does not regress.

**Exit criteria**: F.1 (contracts only) is the minimum deliverable.

---

## 21. Build Order

Based on the analysis of engineering readiness, the implementation tasks are organized into three waves.

### Wave 1 — Immediate: no research prerequisites, highest ROI

These tasks form the safest first-start block. They still obey local engineering dependencies inside the wave; "immediate" here means no original research result is needed to begin.

| Task | Rationale |
|------|-----------|
| A.1–A.6 | Minimum viable core; all subsequent phases depend on these |
| B.1–B.3 | Pure contracts and engine; no research territory |
| B.4a | Graphical-obligation preservation — known graphical results only |
| B.5 | Benchmark infrastructure; does not require B.4a to be complete |
| C.1–C.3 | Contracts and linear SDE backend; known mathematical foundations |
| C.5 | Temporal benchmarks; can start with C.3 |
| F.1 | Contract-only investment; completely decoupled from research |

**Minimum viable core**: A.1 + A.3 + A.4. Everything else in Wave 1 builds on this.

### 21.1. Recommended first implementation slices

To make the roadmap directly executable, start with mergeable slices that each leave the system in a valid state.

| Slice | Includes | Main files | Output |
|------|----------|------------|--------|
| S1 | A.1 | `ir/analytics/causal.py`, `partial_identification.py`, `negative_certificate.py` | canonical proof / bounds / recovery surface with adapters for existing artifacts |
| S2 | A.3 | `foundry/methods/catalog/causal/bounds_engine.py`, `id_engine.py`, `ir/analytics/negative_certificate.py` | no bare non-ID path for supported queries |
| S3 | A.2 + A.4 | `ir/analytics/causal.py`, `scientist/search/funnel/level2_causal.py`, `scientist/search/readiness.py`, `scientist/search/judge_stack.py` | data-readiness gate and machine-readable judge verdicts |
| S4 | A.5 + A.6 | `scientist/search/benchmark_registry.py`, `runtime/replay.py`, `scientist/replay/*` | promotion blocked unless benchmark + replay artifacts exist |
| S5 | B.1 + B.2 | `ir/analytics/cross_graph.py`, `alignment_certification.py`, `datasets/knowledge/variable_alignment.py`, `scientist/cross_graph/compiler.py` | typed alignment report and reviewer-aware interface validation |
| S6 | B.3 + B.4a | `foundry/methods/catalog/causal/graph_reconciliation.py`, `admg_ops.py`, `scientist/nodes/builtins/causal/reconcile_causal_graph.py` | composition certificates and lazy per-query preservation checks |

### Wave 2 — Immediate extensions: local prerequisites and/or formal scope lock

These tasks can begin as soon as Wave 1 core contracts or their local prerequisites are available. Several also require an explicit scope boundary agreed before implementation begins.

| Task | Local prerequisite / scope lock |
|------|------------------------------|
| D.1 | `justification` field defaults to `SCENARIO`; no `IDENTIFIED` without explicit proof kernel extension |
| D.2 | Stackelberg / simple best-response only; fatal compute budget; no general Nash |
| D.3 | Finite-state exact abstraction only; no continuous approximate bounds |
| D.4 | Adversarial challenge suites; depends on D.2 |
| E.1 | Known CI-based and standard algebraic constraints only |
| E.2 | Depends on E.1; no new theory, but not meaningful before the E.1 report contract exists |
| E.3 | Governance gate only (assumption cards, human gate, no-promotion rules) |
| E.4 | Baseline evidence collection (literature_prior + invariance_tests); not a promotion mechanism |

### Wave 3 — Research-first (not scheduled here)

All tasks that require original research are tracked in `CAUSAL_ENGINE_RESEARCH_AGENDA.md`:

- B.4b (latent interface identifiability preservation)
- C.4 (rough-path / neural SDE)
- General OT under partial ID
- Complex strategic equilibria and performative convergence
- Approximate abstraction bounds for continuous models
- Algebraic discovery beyond CI
- Full latent discovery
- F.2–F.4 (hypergraph estimators and topology)

---

## 22. Beyond-SOTA Acceptance Criteria

### 22.1. Core proof layer

1. Current benchmark floor remains green: symbolic, transport, missingness, discovery, policy/interference, adversarial-stress, and reproducibility suites.
2. Every supported non-ID query returns bounds, a constructive certificate, or a recovery plan.
3. Promotion is impossible without replay and artifact lineage.
4. `ProofBundle` carries stratum labels; A2-stratum outputs are flagged.

### 22.2. Data readiness layer

1. No estimation proceeds without a passing `DataReadinessReport`.
2. Underpowered estimates carry mandatory disclosure and capped readiness.
3. Data readiness metrics are visible to judge stack and to end users.

### 22.3. Semantic alignment layer

1. No composition proceeds without an `AlignmentReport`.
2. Alignment assumptions are reported separately from structural assumptions.
3. `INCOMPATIBLE` alignments block composition without human override.

### 22.4. Compositional layer

1. The engine can compose domain-local SCM fragments with explicit certificates.
2. Identifiability preservation is checked per query via d-separation, not assumed globally.
3. Invalid graph stitching is rejected with machine-readable reasons.

### 22.5. Temporal layer

1. The engine returns effect trajectories with uncertainty bands.
2. Discretization and solver diagnostics are surfaced on every trajectory artifact.
3. Temporal claims survive hidden temporal benchmark suites.

### 22.6. Distributional layer

1. Counterfactual distributions, not only means, can be compared.
2. Every distributional artifact carries a justification level.
3. Coupling diagnostics pass on hidden transport and distributional suites.
4. Tail-risk changes are visible for policy alternatives.

### 22.7. Strategic and abstraction layer

1. The engine can model post-policy strategic adaptation with decomposed output.
2. Macro-level recommendations carry explicit abstraction certificates.
3. Multiplicity or instability in equilibria is never hidden.
4. Compute budgets for strategic computation are enforced as fatal limits.

### 22.8. Discovery layer

1. Graph discovery outputs honest structural ambiguity.
2. Algebraic constraints (within known families) contribute to ranking.
3. Latent proposals remain gated by environment assumptions and falsification evidence.

### 22.9. Topology layer (contracts only)

1. `InteractionComplex` and `InterferenceCertificate` contracts are defined and integrated.
2. Existing interference baselines do not regress.

### 22.10. Platform-level criteria

1. Judge stack is the only promotion authority.
2. Judge verdicts include numerical metrics against versioned thresholds.
3. Hidden holdouts and rotating challenge suites exist for each active frontier family.
4. All readiness caps are enforced in code, not convention.
5. No family can self-upgrade its readiness.
6. Kill rules are enforced: frozen tracks are archived, not indefinitely funded.
7. The integrated chain — proof → data readiness → alignment → bounds/estimand → frontier artifact → hidden challenge → promotion → export — is end-to-end replayable.
8. Every exported artifact carries a fragility index with ranked drivers.
9. Falsification loop is operational.
10. Ontology disputes are resolvable via forked analysis without deadlocking the pipeline.

### 22.11. Release criteria by phase

| Criterion | Requirement |
|-----------|------------|
| Contract test coverage | all typed contracts have property-based tests |
| Benchmark count | >= 50 visible + 20 hidden cases per active frontier family |
| Latency ceiling | 60s standard, 120s composition/temporal, 300s strategic, 600s full pipeline |
| Memory ceiling | peak memory <= 8GB for standard cases |
| Artifact reproducibility | replay match >= 99.9% for deterministic components |
| Mandatory failure cases | each frontier family has >= 5 known-failure sentinel cases |

---

## 23. User-Facing Interaction Model

### 23.1. Scenario A: Single-domain policy question

**User**: "What is the effect of minimum wage increase on youth employment?"

**System response**:
1. Graph loaded from labor domain SCM.
2. `ProofBundle` (A0-stratum): query identified via backdoor criterion.
3. `DataReadinessReport`: overlap adequate, ESS = 2400, no blockers.
4. `ExecutionBundle`: ATE = -0.03, 95% CI [-0.06, -0.01].
5. `CausalReadiness`: ESTIMATION_READY.
6. Judge stack: all passed.

**What the analyst sees**: estimated effect with uncertainty, data quality summary, assumptions listed, readiness level explained in plain language.

### 23.2. Scenario B: Cross-domain composition

**User**: "How does education reform affect both health outcomes and labor productivity?"

**System response**:
1. Two SCM fragments loaded: education-health, education-labor.
2. `AlignmentReport`: "years_of_education" aligned as EXACT across fragments. "employment" (labor) vs "economic_activity" (health) aligned as PROXY with stated assumptions.
3. `CompositionCertificate`: status = "preserved" for health query, "deferred" for cross-domain labor-health interaction.
4. System presents: which questions it can answer reliably, which require additional assumptions, and which it cannot answer.

### 23.3. Scenario C: Non-identification with productive fallback

**User**: "What is the causal effect of social media use on adolescent mental health?"

**System response**:
1. `ProofBundle` (A0-stratum): query NOT identified.
2. `NegativeCertificate`: minimal blocking set = {parenting_style, peer_influence}.
3. `BoundsBundle`: sharp bounds = [-0.15, 0.08]; tighter bounds = [-0.12, 0.02] under stated sensitivity model.
4. `RecoveryPlan`: "collecting parenting_style data would reduce bound width by approximately 40%."

**What the analyst sees**: not a dead end, but quantitative guidance on what additional data would help.

### 23.4. Scenario D: Strategic response with high equilibrium dependence

**User**: "What is the effect of a new carbon tax on industrial emissions?"

**System response**:
1. `ProofBundle` (A0-stratum): causal query identified.
2. `StrategicResponseBundle`:
   - `causal_component_ref`: static ATE = -12% emissions.
   - `strategic_closure_ref`: under Stackelberg, net effect = -4%.
   - `equilibrium_selection_dependence`: HIGH.
   - `strategic_fallback_mode`: EXACT_EQUILIBRIUM.
3. `FragilityReport`: fragility_score = 0.72. Top driver: equilibrium selection assumption.

### 23.5. Fragility Index

```python
class FragilityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fragility_score: float
    fragility_grade: Literal["robust", "moderate", "fragile", "critical"]
    top_fragility_drivers: list[FragilityDriver]
    sensitivity_summary: str

class FragilityDriver(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: FrontierUncertaintyType
    description: str
    impact: float
    assumption_ref: str
```

The fragility score aggregates: structural fragility, semantic fragility, data fragility, strategic fragility, and estimation fragility.

---

## 24. Artifact Export and Integration Contract

### 24.1. Export contract

```python
class ExportedCausalArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    readiness_level: CausalReadiness
    fragility_report: FragilityReport
    summary: CausalArtifactSummary
    technical_bundle_ref: ArtifactRef
    assumptions_plain_language: list[str]
    limitations_plain_language: list[str]
    data_quality_summary: str
    judge_verdict_summary: str
    replay_ref: ArtifactRef
    export_format: Literal["api_json", "report_pdf", "audit_package"]
    expiry: str | None
    falsification_endpoint: str | None
```

### 24.2. Export targets

| Target | Format | What is included |
|--------|--------|-----------------|
| Policy analyst UI | structured JSON with plain-language summaries | estimate, uncertainty, assumptions, limitations, readiness, data quality |
| Audit trail | full artifact package | all bundles, certificates, reports, replay bundle, judge verdicts |
| External API | versioned JSON | technical results, readiness level, judge metrics, lineage refs |
| Report generation | structured data for PDF/document rendering | all of the above formatted for human consumption |

### 24.3. Export rules

1. No artifact may be exported without a readiness level.
2. PROOF_ONLY artifacts may be exported for research use but must carry a "not for decision support" warning.
3. Every exported artifact must include its assumptions in plain language.
4. Expiry dates are mandatory for POLICY_PLANNING_READY and AUDIT_READY artifacts.

---

## 25. Falsification Loop and Post-Deployment Contract

### 25.1. Why the architecture needs a feedback loop

Without a feedback mechanism, the engine is a compiler, not an operating system. If the real world shows that a promoted artifact's predictions were wrong, the architecture must invalidate the artifact and trigger re-evaluation.

### 25.2. Falsification contract

```python
class FalsificationTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    telemetry_source: str
    observed_outcome_ref: ArtifactRef
    expected_outcome_ref: ArtifactRef
    divergence_metric: float
    divergence_type: Literal[
        "point_estimate_outside_ci",
        "distribution_shift",
        "direction_reversal",
        "magnitude_deviation",
    ]
    domain_shift_detected: bool
    timestamp: str

class FalsificationVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    verdict: Literal["confirmed", "weakened", "invalidated"]
    new_readiness_cap: CausalReadiness | None
    counterexample_ref: ArtifactRef | None
    re_evaluation_required: bool
    re_evaluation_priority: Literal["routine", "urgent", "critical"]
```

### 25.3. Falsification rules

1. Every `ExportedCausalArtifact` at `POLICY_PLANNING_READY` or `AUDIT_READY` must declare a `falsification_endpoint`.
2. If `divergence_metric` exceeds a threshold, the system automatically revokes status, adds the case to `CounterexampleRegistry`, and triggers re-evaluation.
3. `direction_reversal` is always treated as `critical` priority.
4. The falsification loop does not modify the original artifact; it creates a new versioned artifact with updated evidence.

---

## 26. Computation Architecture Principles

### 26.1. Principles

| Component | Computational trap | Architectural requirement |
|-----------|-------------------|--------------------------|
| Layer A on composed graphs | ID/d-separation is exponential on large graphs | **Markov blanket reduction** before proof search; cache d-separation results per composition |
| Layer B estimation | Cross-validation and bootstrap on large datasets | `ExecutionPlan` must support **compiled execution**; plan must be translatable to vectorized/parallelized primitives |
| Distributional OT | Wasserstein computation is O(N^3) on raw data | **Coreset/sketch reduction** or Sinkhorn regularization mandatory; raw-data OT is architecturally prohibited |
| Strategic equilibrium | NP-hard in general | Compute budget with fatal enforcement + strategic fallback hierarchy (section 14.2) |
| Uncertainty propagation | Monte Carlo multiplies cost by 1000x+ | Support **analytic propagation** (delta method, influence functions) as first-class alternative; Monte Carlo is fallback, not default |
| Composition query preservation | Exhaustive query enumeration is combinatorial | Lazy evaluation with caching (section 10.3.1) |

### 26.2. Latency budgets by query type

| Query type | Latency ceiling | Notes |
|------------|----------------|-------|
| Single-domain, static | 60s | proof + estimation + judge |
| Composition (2 fragments) | 120s | includes alignment check |
| Composition (3+ fragments) | 300s | scales with fragment count |
| Temporal trajectory | 120s | includes solver |
| Strategic equilibrium | 300s | compute-budget-constrained |
| Full pipeline | 600s | async execution recommended |

---

## 27. Design Inspirations

### 27.1. Core causal substrate

1. Pearl and Bareinboim for identification, transportability, recoverability, and negative certificates.
2. Partial-identification and bounds literature for turning non-ID into quantitative output.

### 27.2. Frontier mathematics (implementation scope)

1. Compositionality for modular SCM stitching.
2. Continuous-time SCM and stochastic process work for temporal causal dynamics (linear SDE / piecewise ODE).
3. Optimal transport for full counterfactual distributions.
4. Performative prediction and causal games for strategic adaptation (simple game forms).
5. Abstraction theory for micro-to-macro faithfulness (finite-state exact).
6. Multi-environment latent identifiability work for carefully gated latent discovery.

### 27.3. Platform discipline

1. The existing Scientist blueprint for judge-stacked, VOI-aware, contract-bound promotion.
2. Hidden benchmark discipline from serious optimization systems.
3. Replay-first governance and artifact lineage as a non-negotiable trust substrate.
4. Measurement theory and psychometric reliability for semantic alignment contracts.
5. Dempster-Shafer theory and imprecise probabilities as inspiration for fragility index computation.

---

## Appendix A: Data Flow Diagram

```text
User Query
   |
   v
Semantic Alignment Check (if composition)
   - variable alignment certificates
   - measurement comparability
   |
   v
Layer A: Proof Kernel (stratified: A0/A1/A2)
   - identify / bound / fail constructively
   - stratum label on every proof
   |
   +-------------------+
   |                   |
   v                   v
Layer B: Execution     Bounds / Recovery
   - data readiness    - sharp bounds
   - compile           - recovery plan
   - estimate
   |
   v
Layer C: Frontier Reasoners (within implementation scope)
   - composition (with alignment)
   - continuous-time (linear SDE / piecewise ODE)
   - OT distribution (with justification typing)
   - strategic response (Stackelberg/bounds, with component decomposition)
   - abstraction (finite-state exact)
   - discovery/algebraic (known constraint families)
   - topology (contracts only)
   |
   v
Layer D: Certification
   - hidden benchmark
   - judge stack (with numerical thresholds)
   - readiness contract (with data readiness minimum)
   - replay gate
   - kill rule enforcement
   |
   v
Export Layer
   - promoted artifact with fragility index
   - plain-language summary
   - audit package
   - API output
   |
   v
Promoted Artifact or Rejected Artifact with Failure Cards
   |
   v (post-deployment)
Falsification Loop
   - real-world telemetry intake
   - divergence detection
   - automatic status revocation if invalidated
   - counterexample registration
   - re-evaluation trigger
```

## Appendix B: Glossary

| Term | Meaning |
|------|---------|
| `ProofBundle` | typed output of the symbolic proof kernel, with stratum label |
| `BoundsBundle` | interval or set-valued answer when point identification fails |
| `DataReadinessReport` | evidence that data quality supports the intended estimation |
| `AlignmentReport` | semantic alignment verification for cross-fragment variable matching |
| `VariableAlignmentCertificate` | per-variable-pair semantic alignment evidence |
| `CompositionCertificate` | statement of what graph stitching preserved or broke, with alignment |
| `EffectTrajectoryBundle` | continuous-time effect path with diagnostics |
| `DistributionalEffectBundle` | counterfactual distribution comparison with justification level |
| `StrategicResponseBundle` | equilibrium output decomposed into causal + strategic closure |
| `AbstractionCertificate` | statement of what micro-to-macro mapping preserved |
| `FrontierArtifact` | output of a frontier reasoner with readiness cap |
| `FrontierSketch` | research-only artifact, never promotable, auto-expiring |
| `CausalReadiness` | typed readiness level from PROOF_ONLY to AUDIT_READY |
| `FragilityReport` | ranked decomposition of uncertainty drivers |
| `FalsificationTelemetry` | post-deployment signal that an artifact's predictions diverged from reality |
| `JudgeThresholdRegistry` | versioned store of judge threshold values with provenance |
| Wave 1 | tasks that can start immediately without research prerequisites; local engineering dependencies still apply |
| Wave 2 | tasks that can start after local prerequisites and/or with an explicit scope lock |
| Wave 3 | tasks that require research results first; tracked in RESEARCH_AGENDA |
