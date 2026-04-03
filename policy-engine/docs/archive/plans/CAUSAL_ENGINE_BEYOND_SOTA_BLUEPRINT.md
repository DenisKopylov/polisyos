> **Archived:** This document reflects plans as of 2026-03-24.
> See [current docs](../../explanation/index.md) for up-to-date information.

# PolicyOS Causal Engine - Beyond-SOTA Mathematical Moat Blueprint

> **Version**: 2.1
> **Date**: 2026-03-24
> **Status**: implementation-grade research architecture specification
> **Complements**: `CAUSAL_ENGINE_ARCHITECTURE.md`, `CAUSAL_ENGINE_SOTA_PLAN.md`, `SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT.md`
>
> This document is a **typed, layered, research-prioritized architectural specification**
> for turning the existing Pearl-Bareinboim causal engine into a proof-carrying,
> beyond-SOTA platform for causal policy reasoning. It translates the dialogue's ten
> moat directions into an execution architecture, contract system, promotion regime,
> and phased build order.
>
> It does not replace the current phase plan. It defines the target state that the
> current phase plan should converge to.
>
> **v2.0 changes**: added semantic alignment contract layer, data readiness contract,
> internal stratification of Layer A, numerical operationalization of judge stack,
> kill rules for research economics, user-facing interaction model, artifact export
> contract, and phase exit criteria.
>
> **v2.1 changes**: strategic fallback via bounds (not static ATE), lazy evaluation
> for composition queries, fragility index for warning aggregation, falsification
> loop for post-deployment invalidation, scoped judge thresholds, ontology dispute
> resolution protocol, alignment review workflow, computation architecture principles,
> strategic cap lowered to SIMULATION_READY, FrontierSketch anti-leak hardening.

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
10. [Direction I - Compositional Causality](#10-direction-i-compositional-causality)
11. [Direction II - Sharp Identification, Bounds, and Recovery](#11-direction-ii-sharp-identification-bounds-and-recovery)
12. [Direction III - Continuous-Time Causal Dynamics](#12-direction-iii-continuous-time-causal-dynamics)
13. [Direction IV - Distributional Causality via Optimal Transport](#13-direction-iv-distributional-causality-via-optimal-transport)
14. [Direction V - Strategic and Multi-Scale Policy Causality](#14-direction-v-strategic-and-multi-scale-policy-causality)
15. [Direction VI - Discovery, Latents, and Algebraic Structure](#15-direction-vi-discovery-latents-and-algebraic-structure)
16. [Direction VII - Hypergraph Interference and Topology](#16-direction-vii-hypergraph-interference-and-topology)
17. [Shared Infrastructure](#17-shared-infrastructure)
18. [Architectural Invariants and Failure Modes](#18-architectural-invariants-and-failure-modes)
19. [Degraded Mode and Safe Fallback](#19-degraded-mode-and-safe-fallback)
20. [Execution Phases](#20-execution-phases)
21. [Beyond-SOTA Acceptance Criteria](#21-beyond-sota-acceptance-criteria)
22. [User-Facing Interaction Model](#22-user-facing-interaction-model)
23. [Artifact Export and Integration Contract](#23-artifact-export-and-integration-contract)
24. [Falsification Loop and Post-Deployment Contract](#24-falsification-loop-and-post-deployment-contract)
25. [Computation Architecture Principles](#25-computation-architecture-principles)
26. [Design Inspirations](#26-design-inspirations)

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

The proof kernel guarantees theorem validity. But between a valid estimand and a policy-grade estimate, the most common failure is not mathematical - it is empirical. The engine must not allow a valid theorem to produce an estimate on data that cannot support it.

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

The `DataJudge` (new, see section 7) consumes the `DataReadinessReport` and enforces numerical thresholds before any estimation artifact can be promoted.

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
| Strategic causality | How do agents adapt to policy strategically? | Production-third | Lucas-critique moat for policy realism |
| Causal abstraction | Is macro reasoning faithful to micro structure? | Production-third | Micro-to-macro credibility moat |
| Discovery + algebraic structure | Which graphs survive data, priors, and testable constraints? | Production-third | Strong structural discovery moat |
| Latent representation learning | Can we propose latent confounders from multi-environment shifts? | Research lane | Potentially huge, assumption-heavy |
| Hypergraph topology | How do group interactions change interference? | Horizon lane | Very deep moat, very high risk |

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

The dialogue implies a clear build order:

1. `COMPOSITIONAL` (with semantic alignment)
2. `SHARP_BOUNDS`
3. `CONTINUOUS_TIME`
4. `DISTRIBUTIONAL_OT`
5. `STRATEGIC`
6. `ABSTRACTION`
7. `DISCOVERY_ALGEBRAIC`
8. `LATENT_REPRESENTATION`
9. `TOPOLOGICAL_INTERFERENCE`

This ordering is deliberate:

1. it maximizes leverage on the current symbolic core;
2. it yields useful artifacts before the hardest research tracks are attempted;
3. it prevents the roadmap from collapsing into long, unbenchmarkable research branches.

### 6.4. Research maturity classification

Each frontier family must declare where it sits on the boundary between implementation and original research:

| Family | "Implement known results" scope | "Original research required" scope |
|--------|---|----|
| Compositional | DAG/ADMG fragment gluing with observed interfaces, d-separation preservation checks | Identifiability preservation under latent interface variables, category-theoretic completeness proofs |
| Sharp bounds | Balke-Pearl LP bounds, Manski bounds, existing semiparametric bounds | Novel sharpness proofs for complex query families, automated bound tightening |
| Continuous-time | Linear SDE, piecewise ODE, standard impulse responses | Neural SDE identification theory, causal rough-path semantics |
| Distributional OT | Wasserstein distance computation, quantile treatment effects | Causally justified OT couplings under partial identification |
| Strategic | Best-response computation for simple game forms | Equilibrium computation for complex games (NP-hard in general), performative prediction convergence |
| Abstraction | Exact abstraction verification for finite-state SCMs | Approximate abstraction error bounds for continuous models |
| Discovery | Algorithm portfolio (PC, GES, DAGMA, PCMCI), bootstrap stability | Algebraic constraint discovery beyond conditional independence |
| Latent | Multi-environment invariance testing | Latent variable cardinality identification from distributional shifts |
| Topological | Clustered interference with known cluster structure | Simplicial complex identification theory |

This classification determines realistic phase timelines and prevents open mathematical problems from being disguised as implementation tasks.

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
    maturity: Literal["provisional", "benchmarked", "hardened"]  # provisional = initial guess; benchmarked = validated on suites; hardened = stable across releases
    version: int
    last_updated: str

    # Scoping: thresholds can vary by context
    scope_family: FrontierFamily | None        # None = applies to all families
    scope_query_type: str | None               # None = applies to all query types
    scope_estimator: str | None                # None = applies to all estimators
    scope_readiness_target: CausalReadiness | None  # None = applies to all readiness levels
```

### 7.6. Scoped threshold resolution

When evaluating a judge verdict, the threshold resolution order is:

1. Look for a threshold scoped to `(family, query_type, estimator, readiness_target)`.
2. Fall back to `(family, query_type)`.
3. Fall back to `(family)`.
4. Fall back to the global default.

This allows thresholds to be progressively tightened for specific contexts without imposing unrealistic requirements globally. For example, `CI coverage >= 0.95` may apply to `AUDIT_READY` targets while `CI coverage >= 0.90` (provisional) applies to `ESTIMATION_READY`.

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
| Strategic | very high | medium | medium | very high | build third |
| Abstraction | high | medium | medium | high | build third |
| Discovery + algebraic | high | medium | high | medium-high | build third |
| Latent representation | very high | low-medium | low | medium | gated research lane |
| Topological interference | very high | low | low | medium | horizon lane only |

### 8.3. Anti-swamp rules

1. No new family gets >1 phase of investment without a benchmark proxy.
2. No family may bypass a cheap synthetic benchmark and jump directly to policy-critical claims.
3. Every family must define a fallback output before production work begins.
4. Horizon lanes must consume a capped research budget fraction.
5. If a frontier track cannot state what artifact it will emit, it is not ready to start.

### 8.4. Kill rules and exit criteria

Anti-swamp rules are necessary but insufficient without concrete stop conditions.
Without kill rules, the roadmap will expand indefinitely.

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
3. If artifact type has not stabilized after **2 phases** (i.e., the family keeps changing what it produces), the track is frozen pending architectural review.

**Automatic freeze conditions**:
1. If no benchmark improvement is recorded for **3 consecutive phases**, the track is frozen.
2. If compute cost exceeds **10x the cost-to-value threshold** set by `ComputeJudge`, the track is frozen until compute efficiency improves.

**Kill criteria**:
1. A frozen track that remains frozen for **2 additional phases** is killed (archived, no further investment).
2. Any track where the theoretical foundation is invalidated (e.g., a key theorem is retracted) is killed immediately.

**Decision authority**: track downgrade and freeze are automatic. Kill decisions require human review with documented rationale.

### 8.5. Integration premium

The true moat is not the sum of individual capabilities.
It is the governed integration that competitors cannot replicate piecemeal.

The moat grows with each integrated capability, but a missing capability does not zero out the whole:

```text
moat = base_proof_kernel_value
     + sum(family_value[i] for each realized family i)
     + integration_premium(set of realized families)
```

The integration premium is superlinear: each additional family that passes full judge-stack certification amplifies the value of existing families. For example, sharp bounds + compositional causality together are worth more than their individual sum because bounds can now apply across composed graphs.

However, the core moat (proof kernel + sharp bounds + compositional causality) is already a strong competitive position. The roadmap must not create false pressure to pursue all directions simultaneously.

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
    max_missingness_regime: MissingnessRegime | None     # worst acceptable regime
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
    data_readiness_requirement: DataReadinessRequirement | None  # normative minimum, not observed report
```

### 9.1. Readiness mapping

| Readiness | What it means | Typical artifact types | Data readiness requirement |
|----------|----------------|------------------------|--------------------------|
| PROOF_ONLY | symbolic proof or impossibility result only | `ProofBundle`, `NegativeCertificate` | none (no data needed) |
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

## 10. Direction I - Compositional Causality

### 10.1. Why this is the primary moat

Current open-source causal stacks assume one static graph.
Policy reality is federated:

1. health has one causal model;
2. labor has another;
3. fiscal and monetary systems have another;
4. the real question is often about the composition.

The moat is not "support multiple graphs".
The moat is **typed graph composition with explicit identifiability preservation and semantic alignment certification**.

### 10.2. Target abstraction

The engine must support domain-local SCM fragments that can be stitched through explicit interfaces.
The key output is not just a merged graph, but a `CompositionCertificate` backed by an `AlignmentReport`.

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
    measurement_models: dict[str, ArtifactRef]     # per-variable measurement model refs
    variable_definitions: dict[str, str]           # human-readable semantic definitions
```

```python
class CompositionCertificate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["preserved", "deferred", "broken", "unknown"]
    composed_graph_ref: ArtifactRef
    interface_mapping_ref: ArtifactRef
    alignment_report_ref: ArtifactRef              # mandatory link to semantic alignment
    # Query preservation uses lazy evaluation (see 10.3.1)
    # These lists are populated on-demand, not exhaustively at composition time
    checked_queries: dict[str, Literal["preserved", "broken", "unknown"]]
    newly_required_assumptions: list[str]           # includes both structural and alignment assumptions
    structural_assumptions: list[str]               # assumptions from graph gluing
    alignment_assumptions: list[str]                # assumptions from semantic alignment
    witness_ref: ArtifactRef | None
```

### 10.3. Operational interpretation

Composition should answer five questions:

1. Can the fragments be semantically aligned? (answered by `AlignmentReport`)
2. Can they be structurally glued without contradictions?
3. Which previously identifiable queries remain identifiable after gluing?
4. Which new cross-domain queries become possible?
5. What assumptions were introduced by alignment versus structure?

### 10.3.1. Lazy evaluation for query preservation

Exhaustively computing identifiability status for all possible queries on a composed graph is computationally infeasible for large graphs (hundreds of nodes). Instead, query preservation follows a **lazy evaluation** (JIT) strategy:

1. At composition time, the `CompositionCertificate` verifies only **structural validity** (no contradictions, interface consistency) and **semantic alignment** (all interface variables have alignment certificates).
2. Query-specific identifiability is checked **on demand** when a concrete query arrives, and the result is cached in `checked_queries`.
3. Before running the ID algorithm on the full composed graph, the graph is automatically **reduced to the Markov blanket** of the query's target, treatment, and conditioning variables. This prevents the symbolic engine from operating on unnecessarily large graphs.
4. Cached query results are invalidated if the underlying fragments or alignment certificates change.

This design avoids the combinatorial explosion of precomputing all possible queries while maintaining the guarantee that every answered query has a verified identifiability status.

### 10.4. Build scope and research boundary

**Phase-1 compositional scope** (implementing known results):

1. acyclic DAG/ADMG fragments only;
2. shared observed interfaces only;
3. no automatic latent reconciliation;
4. identifiability preservation via **d-separation checks on composed graph** - specifically: checking whether paths that were blocked in individual fragments remain blocked after gluing, using standard graphical criteria. This is a known, implementable result. Anything beyond this (e.g., preservation of do-calculus derivations across fragments, or preservation under latent interface confounders) is deferred to research scope;
5. semantic alignment via `VariableAlignmentCertificate` with metadata matching and human review;
6. no global theorem claim stronger than the current certificate.

**Deferred scope** (original research required):

1. cyclic fragment composition;
2. automatic latent-variable bridge synthesis;
3. identifiability preservation proofs for graphs with latent interface confounders;
4. category-theoretic completeness claims beyond implemented subcases.

The boundary is important: Phase-1 deliverables are engineering tasks with known mathematical foundations. Deferred scope items are open research problems and must not be scheduled as if they were implementation tasks.

### 10.5. Grounding in existing code

| Existing anchor | Why it matters |
|-----------------|----------------|
| `ir/analytics/causal_graph.py` | core graph IR and metadata attachment |
| `ir/analytics/cross_graph.py` | natural home for composition contracts |
| `foundry/methods/catalog/causal/graph_reconciliation.py` | current graph alignment foothold |
| `foundry/methods/catalog/causal/twin_graph.py` and `amn.py` | evidence that derived graph builders already fit the architecture |
| `scientist/cross_graph/*` | existing multi-source evidence flow for cross-domain integration |
| `scientist/nodes/builtins/causal/reconcile_causal_graph.py` | pipeline integration point |
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

## 11. Direction II - Sharp Identification, Bounds, and Recovery

### 11.1. Core principle

Point identification is a special case.
The engine must treat partial identification as a first-class success mode.

Wrong:

```text
ID failed -> stop
```

Right:

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
    candidate_actions: list[str]            # collect Z, intervene on W, measure M better, etc.
    minimal_oracle_sets: list[list[str]]
    expected_width_reduction: float | None
```

### 11.3. Why this is high ROI

1. it upgrades every current non-ID result from a dead end into a usable artifact;
2. it fits the current symbolic orientation of the engine;
3. it is benchmarkable early;
4. it compounds directly with transportability, missing data, and policy risk reporting.

### 11.4. Grounding in existing code

| Existing anchor | Extension path |
|-----------------|----------------|
| `bounds_engine.py` | orchestrator for bounds-first fallback |
| `lp_bounds.py` | exact LP-based sharp or near-sharp intervals |
| `eif_bounds.py` | semiparametric bounds and influence-function tooling |
| `transport_bounds.py` | transport-specific bounds |
| `sensitivity_bounds.py` | explicit latent confounding sensitivity |
| `ir/analytics/negative_certificate.py` | blocking-certificate anchor |
| `optimal_design.py` | natural source of recovery actions |

### 11.5. Cardinal rule

For supported query families, the engine must never return a bare `non_identified` without at least one of:

1. `BoundsBundle`
2. `NegativeCertificate`
3. `RecoveryPlan`

That rule alone materially changes the usefulness of the platform.

---

## 12. Direction III - Continuous-Time Causal Dynamics

### 12.1. Why scalar ATE is not enough

Policies unfold over time.
Decision-makers care about:

1. delay before effect appears;
2. transient harms before long-run gains;
3. decay, overshoot, or plateau;
4. cumulative budget exposure over a horizon.

The engine needs a continuous-time layer that can answer:

```text
What is the effect path over [t0, t1], under intervention trajectory u(t)?
```

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

### 12.3. Minimal viable path

1. start with linear Gaussian SDE and piecewise-constant interventions;
2. support impulse response and cumulative effect functionals;
3. add irregular sampling support via rough-path signatures and CDE-style representations;
4. only then expand to neural SDEs.

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

### 12.6. Why this is a moat

Continuous-time itself is copyable.
The moat is the end-to-end chain:

```text
symbolic query
  -> temporal estimand
  -> solver-backed trajectory
  -> confidence band
  -> policy budgeting and stress-testing
```

---

## 13. Direction IV - Distributional Causality via Optimal Transport

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
    causal_assumptions: list[str]              # assumptions supporting the justification level
```

```python
class CouplingDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mass_conservation_error: float
    support_mismatch_note: str | None
    regularization_strength: float | None
    identifiability_assumptions: list[str]
```

### 13.3. Why this matters for policy

The engine should be able to answer:

1. who gains in the upper tail vs lower tail;
2. whether a policy compresses or widens a distribution;
3. how subgroup distributions shift, not only subgroup means;
4. how two policy options differ in Wasserstein geometry.

### 13.4. Grounding in existing code

| Existing anchor | Extension path |
|-----------------|----------------|
| `ir/analytics/distributional.py` | natural IR for distributional outputs |
| `scientist/backtesting/distributional.py` | evaluation harness anchor |
| `scientist/nodes/builtins/simulate/run_distributional_analysis.py` | workflow integration point |
| `density_ratio.py` | current reweighting and transport foothold |
| `transport_engine.py` | natural bridge between transportability and OT outputs |

### 13.5. Cardinal rules

1. Distributional OT cannot be presented as `IDENTIFIED` unless the causal query is identified or properly bounded, coupling assumptions are surfaced, and mass conservation diagnostics pass.
2. `SCENARIO`-justified artifacts are capped at `SIMULATION_READY` regardless of other judge verdicts.
3. `BOUNDED`-justified artifacts are capped at `BOUNDS_READY`.
4. The `justification` field must be set by the proof kernel, not by the OT module itself. This requires extending Layer A to support distributional estimands (e.g., "identify the counterfactual distribution of Y under do(X=x)"), which is a Phase D deliverable. Until this extension exists, all distributional artifacts default to `SCENARIO` justification.

---

## 14. Direction V - Strategic and Multi-Scale Policy Causality

This direction bundles two closely related moats:

1. strategic response to policy;
2. abstraction from micro to macro.

The reason to bundle them is practical:
policy systems fail not only because treatment effects are misestimated,
but because agents adapt and because analysts aggregate badly.

### 14.1. Strategic causality contract

```python
class StrategicSCM(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_graph_ref: ArtifactRef
    strategic_agents: list[str]
    utility_refs: dict[str, ArtifactRef]
    policy_rule_ref: ArtifactRef
    equilibrium_concept: Literal["nash", "stackelberg", "best_response_fixed_point"]
    compute_budget: ComputeBudget              # hard limit on equilibrium computation
```

```python
class StrategicResponseBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Decomposed output: causal substrate + strategic closure
    causal_component_ref: ArtifactRef          # the identified causal effect before strategic adaptation
    strategic_closure_ref: ArtifactRef         # the equilibrium/adaptation layer
    equilibrium_selection_dependence: str       # how sensitive is the result to equilibrium choice?
    behavioral_assumption_sensitivity_ref: ArtifactRef | None

    # Standard fields
    equilibrium_set_ref: ArtifactRef
    selected_equilibrium_ref: ArtifactRef | None
    multiplicity_note: str | None
    performative_shift_ref: ArtifactRef | None
    post_adaptation_policy_value_ref: ArtifactRef
```

### 14.2. Computational tractability and strategic fallback

Equilibrium computation is NP-hard in general. The `ComputeJudge` for the strategic family operates in `fatal` mode, not `warning`:

1. Every `StrategicSCM` must declare a `compute_budget` before execution.
2. If equilibrium computation exceeds the budget, the system enters degraded mode immediately - it does not wait for a warning.

**Critical design decision**: the strategic fallback must **not** simply drop to a static ATE. For many policy domains (taxation, subsidies, market regulation), agent response is the substance of the effect, not an add-on. Returning a naive ATE without strategic adaptation can be mathematically precise but fatally misleading (Lucas critique).

**Strategic fallback hierarchy** (in order of preference):

1. **Strategic bounds**: compute worst-case and best-case effect under maximal rational deviation. This is often tractable even when exact equilibrium is not, because it requires solving a simpler optimization problem (max/min over agent responses) rather than finding a fixed point.
2. **Macro-abstracted equilibrium**: if the full game is intractable, use `causal_abstraction.py` to solve the equilibrium on a reduced macro-graph (where agents are grouped), then project strategies back to micro level as constants. This trades precision for tractability explicitly.
3. **Block with explicit flag**: if neither bounds nor abstracted equilibrium is feasible, the system must **block** the strategic output entirely with `unidentified_due_to_strategic_complexity`. It must not silently fall back to a static estimate for policy domains where strategic response is the dominant causal channel.

```python
class StrategicFallbackMode(str, Enum):
    EXACT_EQUILIBRIUM = "exact_equilibrium"
    STRATEGIC_BOUNDS = "strategic_bounds"
    MACRO_ABSTRACTED = "macro_abstracted"
    BLOCKED = "blocked"
```

The fallback mode is recorded in `StrategicResponseBundle` and is visible to the judge stack and to the user.

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

### 14.4. Why this is policy-critical

Without strategic reasoning, the engine will recommend policies that look good on passive data and collapse after adaptation.
Without abstraction certificates, the engine will produce macro recommendations that are not actually supported by micro structure.

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
4. Strategic outputs must always decompose into causal component + strategic closure. The final artifact must never present "post-adaptation policy value" as if it were a simple causal effect.
5. Compute budget for equilibrium computation is mandatory and fatal.

---

## 15. Direction VI - Discovery, Latents, and Algebraic Structure

This direction combines:

1. algorithm portfolio discovery,
2. algebraic model testing,
3. carefully gated latent-variable proposals.

### 15.1. Discovery should stay uncertainty-honest

The engine should not output a single confident graph when the data only supports an equivalence class.
It should output:

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

### 15.3. Portfolio ordering inside discovery

1. strengthen algorithm portfolio and bootstrap stability first;
2. add algebraic constraints and dormant-constraint style model testing second;
3. add latent representation proposals only after environment audits exist.

### 15.4. Why latent discovery is gated

Latent representation learning has moat potential, but it is assumption-heavy.
It must not become a hallucination engine that inserts hidden variables whenever the fit is poor.

### 15.5. Grounding in existing code

| Existing anchor | Extension path |
|-----------------|----------------|
| `discovery_pipeline.py` | portfolio runner anchor |
| `constraint_discovery.py`, `dagma_discovery.py`, `pcmci_discovery.py` | current algorithm families |
| `literature_prior.py` | prior integration |
| `invariance_tests.py` | multi-environment anchor |
| `measurement_error.py` | latent/proxy boundary conditions |
| `ir/analytics/causal_discovery.py` | natural schema location |
| `scientist/cross_graph/gatherers/academic.py` | external evidence integration |

### 15.6. Cardinal rule

Latent variables may not be promoted beyond `PROOF_ONLY` unless the artifact includes:

1. environment assumptions,
2. falsification tests,
3. a clear statement that the latent is inferred, not observed.

---

## 16. Direction VII - Hypergraph Interference and Topology

### 16.1. What this solves

Pairwise interference is often the wrong abstraction.
Real policy spillovers occur in groups:

1. households,
2. classrooms,
3. firm clusters,
4. supply chains,
5. municipal coalitions.

### 16.2. Why this is a horizon lane (and why it still needs architectural space)

The identification theory is immature, estimation cost can explode, and naive implementation would create a research sink. However, architectural space is reserved now for two reasons:

1. **Prevent retrofitting cost**: if topological reasoning is designed in later, it will require invasive changes to the interference IR, the exposure model, and the governance layer. Defining contracts now (even if implementations are empty) makes future integration cheaper.
2. **Protect the pairwise layer**: by defining `InterferenceCertificate.fallback_mode` now, the architecture forces any future topological extension to declare its relationship to the existing pairwise layer, preventing silent replacement.

This is contract-level investment, not implementation-level. The contracts are inexpensive and the protection is valuable.

### 16.3. Required contracts

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

### 16.4. Grounding in existing code

| Existing anchor | Why it matters |
|-----------------|----------------|
| `interference.py` | current interference footing |
| `ir/analytics/interference.py` | schema insertion point |
| `scientist/governance/passes/sutva_check_pass.py` | explicit governance boundary |
| `scientist/backtesting/distributional.py` | subgroup and tail-evaluation hooks |

### 16.5. Cardinal rule

Topology-aware artifacts must never silently masquerade as standard pairwise interference outputs.
If the engine reduces a complex to a simpler approximation, that reduction must be explicit.

---

## 17. Shared Infrastructure

The moat directions share a common substrate.
Without shared infrastructure, the system becomes a bag of disconnected clever modules.

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
3. 5-10 sentinel cases,
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
6. **No OT artifact without coupling diagnostics and justification level**: mass conservation is not optional; justification type (identified/bounded/scenario) is not optional.
7. **No strategic claim without equilibrium disclosure and component decomposition**: multiplicity or instability must remain visible; causal and strategic components must be reported separately.
8. **No abstraction without preservation type**: exact, approximate, policy-value-only, or invalid.
9. **No latent node without assumption card**: inferred hidden structure must carry environment assumptions.
10. **No topological artifact may degrade silently**: pairwise reductions must be explicit.
11. **No promoted artifact without replay bundle**: promotion without reproducibility is a system bug.
12. **No A2-stratum proof without oracle disclosure**: outputs from the oracle-backed proof layer must be flagged.
13. **No exported artifact without fragility index**: every `ExportedCausalArtifact` must carry a `FragilityReport`.
14. **No POLICY_PLANNING_READY artifact without falsification endpoint**: artifacts at this level must accept post-deployment telemetry.
15. **No strategic fallback to naive static ATE**: strategic degradation must use bounds, abstracted equilibrium, or block. Silent drop to static estimate is prohibited for policy domains where strategic response is the dominant causal channel.

### 18.2. Failure modes and mitigations

| # | Failure mode | Impact | Mitigation |
|---|--------------|--------|-----------|
| 1 | Invalid graph stitching | false cross-domain claims | `CompositionCertificate`, `AlignmentReport`, semantic interface schema, hidden merge suite |
| 2 | Semantically false alignment | formally valid but meaningless cross-domain claims | `VariableAlignmentCertificate`, `AlignmentJudge`, human review for ambiguous cases |
| 3 | Bounds reported as sharp when they are not | false certainty | `BoundJudge`, dual witness requirement, sharpness labels |
| 4 | Estimation on insufficient data | unreliable estimates presented as reliable | `DataReadinessReport`, `DataJudge`, mandatory ESS/overlap checks |
| 5 | Continuous-time solver drift | wrong trajectories | `DynamicsJudge`, stiffness diagnostics, discrete-time fallback |
| 6 | OT coupling artifacts | misleading tail stories | mass conservation checks, justification typing, subgroup stability tests |
| 7 | Equilibrium multiplicity hidden | false policy ranking | `StrategicJudge`, explicit multiplicity notes, component decomposition |
| 8 | Abstraction leakage | ecological fallacy | `AbstractionCertificate`, micro-to-macro holdouts |
| 9 | Latent confounder hallucination | pseudo-explanations | environment audit, readiness cap at `PROOF_ONLY` |
| 10 | Algebraic model testing overfires | false graph rejection | severity tiers, benchmarked constraint tolerance |
| 11 | Hypergraph complexity explosion | unusable compute profile | fallback to cluster or pairwise mode |
| 12 | Frontier benchmark gaming | illusory SOTA | rotating hidden suites and sentinels |
| 13 | A2-stratum proof treated as A0 | false confidence in theorem validity | stratum labeling, `proof_stratum` field in `ProofBundle` |
| 14 | Warning fatigue / assumption blindness | analysts ignore critical risks buried in long lists | `FragilityReport` with ranked top drivers; fragility grade on every export |
| 15 | Post-deployment artifact staleness | policy based on outdated causal estimates | falsification loop, expiry dates, telemetry-triggered re-evaluation |
| 16 | Strategic fallback to naive ATE | mathematically precise but practically misleading policy advice | strategic bounds hierarchy, blocked mode for dominant strategic channels |
| 17 | Ontology dispute blocks pipeline | competing definitions create deadlock | dispute resolution protocol with forked analysis and sensitivity reporting |
| 18 | Composition query explosion | attempting to check all queries on large composed graphs | lazy evaluation with Markov blanket reduction and caching |

---

## 19. Degraded Mode and Safe Fallback

Degradation must be explicit.
When advanced modules fail, the system must fall back to a weaker but honest artifact.

### 19.1. Degradation hierarchy

| Condition | Mode | What changes | Max readiness |
|-----------|------|--------------|---------------|
| All families healthy | normal | full stack available | AUDIT_READY |
| Frontier family uncalibrated | research-only mode | artifact produced, no promotion | PROOF_ONLY |
| Alignment pending human review | reduced-readiness composition | composition proceeds for PROXY alignments only, human review queued | BOUNDS_READY |
| Alignment proxy-only (no EXACT) | proxy-acknowledged composition | composition proceeds with proxy sensitivity analysis | ESTIMATION_READY |
| Alignment blocked (LATENT_BRIDGE pending or INCOMPATIBLE) | composition blocked | no composition until review completes or dispute is resolved | N/A |
| Ontology dispute unresolved | forked analysis | both definitions computed, divergence reported | BOUNDS_READY |
| Data readiness blockers present | bounds-only mode | estimation blocked, bounds-only fallback | BOUNDS_READY |
| Continuous-time backend unavailable | discrete-time fallback | piecewise approximation only | SIMULATION_READY |
| OT diagnostics fail | scalar-only mode | means/quantiles only, no coupling claims | ESTIMATION_READY |
| Strategic solver timeout | strategic bounds or block | strategic bounds if tractable; else blocked with `unidentified_due_to_strategic_complexity` | BOUNDS_READY (bounds) or N/A (blocked) |
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

The build order should follow the dialogue's priority logic and the current code adjacency.
Each phase has explicit acceptance criteria and exit conditions.

### Phase A - Proof-Carrying Core Closure

**Goal**: harden the current engine so every query ends in a valid proof artifact, bounds artifact, or explicit impossibility artifact. Establish data readiness gates and judge stack.

| # | Deliverable | Module | Depends on |
|---|-------------|--------|------------|
| A.1 | Unified `ProofBundle` (with stratum), `BoundsBundle`, `RecoveryPlan` schemas | `ir/analytics/*` | - |
| A.2 | `DataReadinessReport` contract and verification | `execution/*` | A.1 |
| A.3 | Bounds-first fallback from negative ID results | `bounds_engine.py`, `id_engine.py` | A.1 |
| A.4 | Causal judge stack with numerical thresholds and `JudgeThresholdRegistry` | `scientist/governance/*`, `scientist/search/*` | A.1, A.2 |
| A.5 | Hidden benchmark registry for frontier families | `scientist/backtesting/*` | A.4 |
| A.6 | Replay requirement for promoted causal artifacts | `scientist/replay/*` | A.4 |

**Acceptance**:

1. no supported non-ID query returns a bare dead end;
2. current symbolic, transport, missing, and counterfactual suites stay green;
3. promoted causal artifacts have replay bundles;
4. all estimation paths verify data readiness before execution;
5. judge stack produces machine-readable verdicts with numerical metrics.

**Exit criteria**: all acceptance criteria met for 2 consecutive test cycles. If not met within allocated time, scope is reduced to A.1 + A.3 + A.4 (minimum viable core) and remaining items roll to Phase A'.

### Phase B - Compositional Causality with Semantic Alignment

**Goal**: support stitched SCM fragments with composition certificates and semantic alignment verification.

| # | Deliverable | Module | Depends on |
|---|-------------|--------|------------|
| B.1 | `SCMFragment`, interface schemas, `VariableAlignmentCertificate`, `AlignmentReport` | `ir/analytics/cross_graph.py` | A.1 |
| B.2 | Alignment verification engine | new `causal/semantic_alignment.py` | B.1 |
| B.3 | Composition engine and certificate | new `causal/compositional.py` | B.1, B.2 |
| B.4 | Query preservation checker (implementing known d-separation results) | new `causal/compositional_id.py` | B.3 |
| B.5 | Composition + alignment benchmark suite | `benchmarks` + `scientist/backtesting/*` | B.3 |

**Acceptance**:

1. valid fragment composition works on curated ministry-style cases;
2. invalid stitching is rejected with explicit failure cards;
3. identifiability preservation status is surfaced per query;
4. every composition carries an `AlignmentReport` with per-variable certificates;
5. `PROXY` and `LATENT_BRIDGE` alignments inject assumptions into the composition certificate.

**Exit criteria**: all acceptance criteria met. If B.4 (query preservation) proves to require original research beyond known results, it is explicitly reclassified as a research task and Phase B is closed with B.1-B.3 + B.5 as the deliverable. B.4 continues as a research track under anti-swamp rules.

### Phase C - Continuous-Time and Temporal Compiler

**Goal**: move from static effects to effect trajectories.

| # | Deliverable | Module | Depends on |
|---|-------------|--------|------------|
| C.1 | `ContinuousTimeQuery` and `EffectTrajectoryBundle` | `ir/analytics/dynamic_regime.py` | A.1 |
| C.2 | Temporal estimand compiler | new `causal/temporal_compiler.py` | C.1 |
| C.3 | Linear-SDE backend | new `causal/continuous_time.py` | C.2 |
| C.4 | Rough-path / irregular sampling support | new `causal/rough_path.py` | C.3 |
| C.5 | Temporal benchmark suite | `benchmarks` + `scientist/backtesting/*` | C.3 |

**Acceptance**:

1. engine returns effect paths with confidence bands on temporal gold tasks;
2. discretization diagnostics are always surfaced;
3. fallback to discrete-time remains available.

**Exit criteria**: C.1-C.3 + C.5 are the minimum. C.4 (rough-path) may be deferred if irregular sampling is not yet needed for active policy cases.

### Phase D - Distributional, Strategic, and Abstraction Layer

**Goal**: model tails, adaptation, and micro-to-macro consistency.

| # | Deliverable | Module | Depends on |
|---|-------------|--------|------------|
| D.1 | OT-based distributional bundle with justification typing | new `causal/causal_ot.py` | A.1 |
| D.2 | Strategic SCM contracts, solver, and compute budget enforcement | new `causal/strategic_causality.py` | A.1 |
| D.3 | Abstraction maps and certificates | new `causal/causal_abstraction.py` | D.2 |
| D.4 | Strategic and abstraction challenge suites | `scientist/backtesting/adversarial.py` + new suites | D.2 |

**Acceptance**:

1. distributional outputs carry justification type and pass mass-conservation and subgroup tests;
2. strategic outputs decompose into causal + strategic closure components;
3. strategic outputs respect compute budgets with fatal enforcement;
4. macro outputs require abstraction certificates.

**Exit criteria**: D.1 and D.4 are minimum. D.2-D.3 may be delivered in reduced scope (e.g., Stackelberg-only equilibrium) if general equilibrium computation proves intractable within budget. Reduced scope must be documented explicitly.

### Phase E - Discovery, Algebraic Testing, and Latent Research Gate

**Goal**: strengthen discovery without letting latent speculation corrupt the core.

| # | Deliverable | Module | Depends on |
|---|-------------|--------|------------|
| E.1 | Algebraic constraint reports | new `causal/algebraic_constraints.py` | A.1 |
| E.2 | Discovery utility judge | `discovery_pipeline.py` + new judge layer | E.1 |
| E.3 | Latent discovery gate and schemas | new `causal/latent_discovery.py` | E.2 |
| E.4 | Prior + environment audit pipeline | `literature_prior.py`, `invariance_tests.py` | E.3 |

**Acceptance**:

1. discovery outputs disputed edges and violated constraints explicitly;
2. latent proposals are capped and assumption-bounded;
3. downstream utility affects graph ranking.

**Exit criteria**: E.1-E.2 are minimum. E.3-E.4 (latent discovery) may remain in research-only status if environment audit infrastructure is not yet mature.

### Phase F - Hypergraph Topology Research Lane

**Goal**: define contracts for group-interaction reasoning without blocking the main roadmap. Implementation is gated.

| # | Deliverable | Module | Depends on |
|---|-------------|--------|------------|
| F.1 | `InteractionComplex` IR and `InterferenceCertificate` contracts | `ir/analytics/interference.py` | A.1 |
| F.2 | Exposure-complex estimators (if theory permits) | new `causal/hypergraph_interference.py` | F.1 |
| F.3 | Pairwise and cluster fallback certificates | same | F.2 |
| F.4 | Horizon benchmark pack | new synthetic suite | F.2 |

**Acceptance**:

1. contracts are defined and integrated into the IR layer;
2. if estimators exist: hypergraph results never silently replace pairwise outputs;
3. fallback behavior is explicit;
4. existing interference performance does not regress.

**Exit criteria**: F.1 (contracts only) is the minimum deliverable. F.2-F.4 proceed only if theoretical foundations mature during the phase. If not, F.1 is archived as architectural scaffolding and the phase is closed.

---

## 21. Beyond-SOTA Acceptance Criteria

The engine is beyond SOTA only when the following hold simultaneously.

### 21.1. Core proof layer

1. Current symbolic identification suites remain complete and green.
2. Every supported non-ID query returns bounds, a constructive certificate, or a recovery plan.
3. Promotion is impossible without replay and artifact lineage.
4. `ProofBundle` carries stratum labels; A2-stratum outputs are flagged.

### 21.2. Data readiness layer

1. No estimation proceeds without a passing `DataReadinessReport`.
2. Underpowered estimates carry mandatory disclosure and capped readiness.
3. Data readiness metrics are visible to judge stack and to end users.

### 21.3. Semantic alignment layer

1. No composition proceeds without an `AlignmentReport`.
2. Alignment assumptions are reported separately from structural assumptions.
3. `INCOMPATIBLE` alignments block composition without human override.

### 21.4. Compositional layer

1. The engine can compose domain-local SCM fragments with explicit certificates.
2. Identifiability preservation is checked per query, not assumed globally.
3. Invalid graph stitching is rejected with machine-readable reasons.

### 21.5. Temporal layer

1. The engine returns effect trajectories with uncertainty bands.
2. Discretization and solver diagnostics are surfaced on every trajectory artifact.
3. Temporal claims survive hidden temporal benchmark suites.

### 21.6. Distributional layer

1. Counterfactual distributions, not only means, can be compared.
2. Every distributional artifact carries a justification level (identified/bounded/scenario).
3. Coupling diagnostics pass on hidden transport and distributional suites.
4. Tail-risk changes are visible for policy alternatives.

### 21.7. Strategic and abstraction layer

1. The engine can model post-policy strategic adaptation with decomposed output.
2. Macro-level recommendations carry explicit abstraction certificates.
3. Multiplicity or instability in equilibria is never hidden.
4. Compute budgets for strategic computation are enforced as fatal limits.

### 21.8. Discovery layer

1. Graph discovery outputs honest structural ambiguity.
2. Algebraic constraints contribute to ranking, not just graph similarity.
3. Latent proposals remain gated by environment assumptions and falsification evidence.

### 21.9. Topology layer

1. Group-interaction reasoning works on benchmarked synthetic tasks (if theory permits).
2. Pairwise and cluster fallbacks remain explicit and safe.
3. Hypergraph support does not regress existing interference baselines.

### 21.10. Platform-level criteria

1. Judge stack is the only promotion authority.
2. Judge verdicts include numerical metrics against versioned thresholds.
3. Hidden holdouts and rotating challenge suites exist for each frontier family.
4. All readiness caps are enforced in code, not convention.
5. No family can self-upgrade its readiness.
6. Kill rules are enforced: frozen tracks are archived, not indefinitely funded.
7. The integrated chain - proof -> data readiness -> alignment -> bounds/estimand -> frontier artifact -> hidden challenge -> promotion -> export - is end-to-end replayable.
8. Every exported artifact carries a fragility index with ranked drivers.
9. Falsification loop is operational: post-deployment telemetry can trigger automatic artifact invalidation.
10. Ontology disputes are resolvable via forked analysis without deadlocking the pipeline.

### 21.11. Release criteria by phase

Beyond the per-phase acceptance criteria in section 20, the following apply to any release:

| Criterion | Requirement |
|-----------|------------|
| Contract test coverage | all typed contracts have property-based tests |
| Benchmark count | >= 50 visible + 20 hidden cases per active frontier family |
| Latency ceiling | end-to-end query response per query type budget (section 25.2): 60s standard, 120s composition/temporal, 300s strategic, 600s full pipeline |
| Memory ceiling | peak memory <= 8GB for standard cases |
| Artifact reproducibility | replay match >= 99.9% for deterministic components |
| Mandatory failure cases | each frontier family has >= 5 known-failure sentinel cases that must produce correct rejections |

---

## 22. User-Facing Interaction Model

The architecture serves policy analysts, not only engineers.
Without a user-facing story, the system risks being architecturally perfect but unusable.

### 22.1. Scenario A: Single-domain policy question

**User**: "What is the effect of minimum wage increase on youth employment?"

**System response**:
1. Graph loaded from labor domain SCM.
2. `ProofBundle` (A0-stratum): query identified via backdoor criterion.
3. `DataReadinessReport`: overlap adequate, ESS = 2400, no blockers.
4. `ExecutionBundle`: ATE = -0.03, 95% CI [-0.06, -0.01].
5. `CausalReadiness`: ESTIMATION_READY.
6. Judge stack: all passed.

**What the analyst sees**: estimated effect with uncertainty, data quality summary, assumptions listed, readiness level explained in plain language.

### 22.2. Scenario B: Cross-domain composition

**User**: "How does education reform affect both health outcomes and labor productivity?"

**System response**:
1. Two SCM fragments loaded: education-health, education-labor.
2. `AlignmentReport`: "years_of_education" aligned as EXACT across fragments. "employment" (labor) vs "economic_activity" (health) aligned as PROXY with stated assumptions.
3. `CompositionCertificate`: status = "preserved" for health query, "deferred" for cross-domain labor-health interaction.
4. System presents: which questions it can answer reliably, which require additional assumptions, and which it cannot answer with current evidence.

**What the analyst sees**: clear separation of what is known, what is estimated under assumptions, and what remains unresolved. The PROXY alignment is highlighted as a key assumption the analyst should evaluate.

### 22.3. Scenario C: Non-identification with productive fallback

**User**: "What is the causal effect of social media use on adolescent mental health?"

**System response**:
1. `ProofBundle` (A0-stratum): query NOT identified. Unmeasured confounders block identification.
2. `NegativeCertificate`: minimal blocking set = {parenting_style, peer_influence}.
3. `BoundsBundle`: sharp bounds = [-0.15, 0.08] under no-assumptions analysis; tighter bounds = [-0.12, 0.02] under stated sensitivity model.
4. `RecoveryPlan`: "collecting parenting_style data would reduce bound width by approximately 40%."

**What the analyst sees**: not a dead end, but a quantitative answer about what is possible given current evidence, plus actionable guidance on what additional data would help. The readiness level is BOUNDS_READY, clearly labeled as not suitable for point-estimate-based policy decisions.

### 22.4. Scenario D: Strategic response with high equilibrium dependence

**User**: "What is the effect of a new carbon tax on industrial emissions?"

**System response**:
1. `ProofBundle` (A0-stratum): causal query identified.
2. `DataReadinessReport`: overlap strong, ESS = 5200.
3. `StrategicResponseBundle`:
   - `causal_component_ref`: static ATE = -12% emissions (without behavioral adaptation).
   - `strategic_closure_ref`: under Stackelberg equilibrium, firms relocate production; net effect = -4% emissions.
   - `equilibrium_selection_dependence`: HIGH. Under Nash assumption, net effect = -8%.
   - `strategic_fallback_mode`: EXACT_EQUILIBRIUM.
4. `FragilityReport`: fragility_score = 0.72 (fragile). Top fragility driver: equilibrium selection assumption.

**What the analyst sees**: "The carbon tax reduces emissions by 4-12% depending on how firms respond strategically. The result is sensitive to the assumed game structure. If firms behave as Stackelberg followers, the effect is -4%. If they respond independently (Nash), the effect is -8%. Without strategic modeling, the naive estimate is -12%, but this is likely overestimated. **Key risk: the result changes substantially depending on strategic assumptions.**"

### 22.5. Fragility Index

The architecture generates many warnings, assumptions, and uncertainty flags across different layers. Without aggregation, analysts face "warning fatigue" and ignore everything except the final number. The **Fragility Index** solves this by compressing heterogeneous uncertainties into a single interpretable metric.

```python
class FragilityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fragility_score: float                     # 0.0 = robust, 1.0 = maximally fragile
    fragility_grade: Literal["robust", "moderate", "fragile", "critical"]
    top_fragility_drivers: list[FragilityDriver]  # ranked by impact
    sensitivity_summary: str                   # plain-language summary

class FragilityDriver(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: FrontierUncertaintyType            # which uncertainty type
    description: str                           # plain language
    impact: float                              # how much does the estimate change if this assumption fails?
    assumption_ref: str                        # which specific assumption
```

**Computation**: the fragility score aggregates across uncertainty sources:
1. **Structural fragility**: how many assumptions does the proof depend on? Are they testable?
2. **Semantic fragility**: are alignments EXACT or PROXY? How sensitive is the estimate to alignment choice?
3. **Data fragility**: ESS ratio, overlap grade, missingness severity.
4. **Strategic fragility**: equilibrium multiplicity, selection dependence.
5. **Estimation fragility**: bootstrap instability, cross-fit variance.

The score is not a probability. It answers: "how many independent ways could this result be wrong, and how much would it change?"

The analyst sees the fragility grade and the top 2-3 drivers in the summary view. The full decomposition is available on drill-down.

---

## 23. Artifact Export and Integration Contract

When the judge stack promotes an artifact, it must be consumable by downstream systems.
A promoted artifact that cannot be exported is architecturally incomplete.

### 23.1. Export contract

```python
class ExportedCausalArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    readiness_level: CausalReadiness
    fragility_report: FragilityReport              # aggregated robustness assessment
    summary: CausalArtifactSummary                 # human-readable summary for non-technical consumers
    technical_bundle_ref: ArtifactRef               # full technical artifact for audit
    assumptions_plain_language: list[str]           # assumptions in plain language
    limitations_plain_language: list[str]           # limitations in plain language
    data_quality_summary: str                       # human-readable data quality assessment
    judge_verdict_summary: str                      # human-readable judge outcome
    replay_ref: ArtifactRef                         # for reproducibility verification
    export_format: Literal["api_json", "report_pdf", "audit_package"]
    expiry: str | None                              # when this artifact should be re-evaluated
    falsification_endpoint: str | None              # where to send post-deployment telemetry
```

### 23.2. Export targets

| Target | Format | What is included |
|--------|--------|-----------------|
| Policy analyst UI | structured JSON with plain-language summaries | estimate, uncertainty, assumptions, limitations, readiness, data quality |
| Audit trail | full artifact package | all bundles, certificates, reports, replay bundle, judge verdicts |
| External API | versioned JSON | technical results, readiness level, judge metrics, lineage refs |
| Report generation | structured data for PDF/document rendering | all of the above formatted for human consumption |

### 23.3. Export rules

1. No artifact may be exported without a readiness level.
2. PROOF_ONLY artifacts may be exported for research use but must carry a "not for decision support" warning.
3. Every exported artifact must include its assumptions in plain language, not only as technical identifiers.
4. Expiry dates are mandatory for POLICY_PLANNING_READY and AUDIT_READY artifacts. Stale artifacts must be re-evaluated.

---

## 24. Falsification Loop and Post-Deployment Contract

### 24.1. Why the architecture needs a feedback loop

The causal engine as described in sections 1-23 is a one-directional pipeline: query enters, artifact exits. But policy is a continuous process. If the real world shows that a promoted artifact's predictions were wrong, the architecture must have a mechanism to invalidate the artifact and trigger re-evaluation. Without this, the engine is a compiler, not an operating system.

### 24.2. Falsification contract

```python
class FalsificationTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str                           # the ExportedCausalArtifact being checked
    telemetry_source: str                      # e.g., "fabric_outcome_monitor", "manual_audit"
    observed_outcome_ref: ArtifactRef          # real-world outcome data
    expected_outcome_ref: ArtifactRef          # what the artifact predicted
    divergence_metric: float                   # how far is reality from prediction?
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
    new_readiness_cap: CausalReadiness | None  # if weakened or invalidated
    counterexample_ref: ArtifactRef | None     # added to CounterexampleRegistry
    re_evaluation_required: bool
    re_evaluation_priority: Literal["routine", "urgent", "critical"]
```

### 24.3. Falsification rules

1. Every `ExportedCausalArtifact` at `POLICY_PLANNING_READY` or `AUDIT_READY` must declare a `falsification_endpoint` - a contract for receiving post-deployment telemetry.
2. If `FalsificationTelemetry.divergence_metric` exceeds a threshold (scoped by query type and readiness level), the system automatically:
   - revokes the artifact's `AUDIT_READY` or `POLICY_PLANNING_READY` status;
   - adds the case to `CounterexampleRegistry`;
   - triggers re-evaluation with the new data included.
3. `direction_reversal` is always treated as `critical` priority regardless of magnitude.
4. Falsification verdicts are audited and visible to governance.
5. The falsification loop does not modify the original artifact; it creates a new versioned artifact with updated evidence.

### 24.4. Integration with existing architecture

The falsification loop connects to:
- `CounterexampleRegistry` (section 17): invalidated artifacts become sentinel cases.
- `ReplayRegistry` (section 17): re-evaluation uses the same replay infrastructure.
- `CausalReadinessContract` (section 9): `expiry_conditions` can include falsification-based triggers.
- `DataReadinessReport` (section 5): new telemetry data feeds into updated data readiness checks.

---

## 25. Computation Architecture Principles

The architecture must not be agnostic to computational feasibility. Several components have known computational traps that must be addressed at the architectural level, not left to implementation chance.

### 25.1. Principles (not framework prescriptions)

These are architectural constraints, not technology choices. Specific frameworks (JAX, etc.) are implementation decisions.

| Component | Computational trap | Architectural requirement |
|-----------|-------------------|--------------------------|
| Layer A on composed graphs | ID/d-separation is exponential on large graphs | **Markov blanket reduction** before proof search; cache d-separation results per composition |
| Layer B estimation | Cross-validation and bootstrap on large datasets (millions of rows) | `ExecutionPlan` must support **compiled execution** (not interpreted Python loops); plan must be translatable to vectorized/parallelized primitives |
| Distributional OT | Wasserstein computation is O(N^3) on raw data | **Coreset/sketch reduction** or entropic regularization (Sinkhorn) as mandatory preprocessing step in OT pipeline; raw-data OT is architecturally prohibited |
| Strategic equilibrium | NP-hard in general | Already addressed: compute budget with fatal enforcement + strategic fallback hierarchy (section 14.2) |
| Uncertainty propagation | Monte Carlo multiplies cost by 1000x+ | Support **analytic propagation** (delta method, influence functions) as first-class alternative; Monte Carlo is fallback, not default |
| Composition query preservation | Exhaustive query enumeration is combinatorial | Already addressed: lazy evaluation with caching (section 10.3.1) |

### 25.2. Latency budgets by query type

The 60-second latency ceiling (section 21.11) applies to **standard single-domain queries**. Complex queries have differentiated budgets:

| Query type | Latency ceiling | Notes |
|------------|----------------|-------|
| Single-domain, static | 60s | proof + estimation + judge |
| Composition (2 fragments) | 120s | includes alignment check |
| Composition (3+ fragments) | 300s | scales with fragment count |
| Temporal trajectory | 120s | includes solver |
| Strategic equilibrium | 300s | compute-budget-constrained |
| Full pipeline (composition + temporal + strategic) | 600s | async execution recommended |

Queries exceeding their ceiling enter an **async execution model**: the system returns an immediate acknowledgment with a job ID, and the result is delivered asynchronously. The analyst UI shows progress indicators for long-running queries.

---

## 26. Design Inspirations

These are architectural patterns, not brand dependencies.

### 26.1. Core causal substrate

1. Pearl and Bareinboim for identification, transportability, recoverability, and negative certificates.
2. Partial-identification and bounds literature for turning non-ID into quantitative output.

### 26.2. Frontier mathematics

1. Compositionality and category-theoretic probability for graph stitching and modular semantics.
2. Continuous-time SCM and stochastic process work for temporal causal dynamics.
3. Optimal transport and distributional treatment-effect work for full counterfactual distributions.
4. Performative prediction and causal games for strategic adaptation.
5. Abstraction theory for micro-to-macro faithfulness.
6. Algebraic statistics for model constraints beyond conditional independence.
7. Multi-environment latent identifiability work for carefully gated latent discovery.
8. Topological and hypergraph interference work for group-level spillovers.

### 26.3. Platform discipline

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
Layer C: Frontier Reasoners
   - composition (with alignment)
   - continuous-time
   - OT distribution (with justification typing)
   - strategic response (with component decomposition)
   - abstraction
   - discovery/algebraic
   - topology
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
   |
   v
Back to Layer A (re-evaluation) or CounterexampleRegistry
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
| `DistributionalEffectBundle` | distribution-level counterfactual effect artifact with justification type |
| `StrategicResponseBundle` | equilibrium-adjusted policy response artifact with causal/strategic decomposition |
| `AbstractionCertificate` | statement about micro-to-macro preservation |
| `LatentDiscoveryBundle` | assumption-bounded latent proposal artifact |
| `InterferenceCertificate` | statement about supported group-interaction semantics |
| `CausalReadinessContract` | typed declaration of safe downstream use |
| `FrontierSketch` | lightweight research-stage artifact, not promotable |
| `ExportedCausalArtifact` | downstream-consumable artifact with plain-language summaries |
| `JudgeThresholdEntry` | versioned numerical threshold for a specific judge metric |
| `FrontierTrackHealth` | health status of a frontier family for kill-rule evaluation |
| `FragilityReport` | aggregated robustness assessment compressing heterogeneous uncertainties into a single index |
| `FragilityDriver` | single ranked source of fragility with impact estimate |
| `OntologyDispute` | record of competing variable definitions across fragments with forked analysis |
| `FalsificationTelemetry` | post-deployment real-world data for validating exported artifacts |
| `FalsificationVerdict` | system decision on whether an artifact is confirmed, weakened, or invalidated |
| `DataReadinessRequirement` | normative minimum data quality thresholds for a readiness level |
| `StrategicFallbackMode` | which strategic computation was actually used (exact, bounds, abstracted, blocked) |

## Appendix C: Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-24 | Initial specification |
| 2.0 | 2026-03-24 | Added semantic alignment contract layer (section 4); added data readiness contract (section 5); stratified Layer A into A0/A1/A2 with ProofBundle stratum field; added DataJudge and AlignmentJudge to judge stack; operationalized all judges with numerical metrics and thresholds; added kill rules with automatic downgrade/freeze/kill conditions (section 8.4); replaced multiplicative moat formula with additive + superlinear integration premium (section 8.5); added research maturity classification per frontier family (section 6.4); added FrontierSketch lightweight entry contract (section 3.4); added distributional justification typing (section 13.2); added strategic component decomposition and compute budget enforcement (section 14.1-14.2); added user-facing interaction model with three scenarios (section 22); added artifact export contract (section 23); added phase exit criteria and scope reduction rules (section 20); added release criteria table (section 21.11); justified hypergraph architectural placeholder (section 16.2); expanded invariants to 12 (section 18.1); added failure modes for alignment and data readiness (section 18.2); expanded registries (section 17.2); added AlignmentRegistry, DataReadinessRegistry, JudgeThresholdRegistry |
| 2.1 | 2026-03-24 | Strategic fallback via bounds hierarchy instead of static ATE drop (section 14.2); lazy evaluation for composition queries (section 10.3.1); fragility index for warning aggregation (section 22.5); falsification loop for post-deployment invalidation (section 24); ontology dispute resolution protocol (section 4.6); alignment review workflow with SLA (section 4.5); scoped and provisional judge thresholds (sections 7.5-7.6); computation architecture principles (section 25); differentiated latency budgets by query type (section 25.2); strategic cap lowered to SIMULATION_READY; DataReadinessRequirement replaces DataReadinessReport in CausalReadinessContract; FrontierSketch anti-leak hardening; degraded alignment modes refined into four cases; strategic high-dependence user scenario (section 22.4) |
