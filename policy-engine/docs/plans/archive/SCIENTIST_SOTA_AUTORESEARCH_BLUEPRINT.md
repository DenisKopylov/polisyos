> **Archived:** This document reflects plans as of 2026-03-23.
> See [current docs](../../explanation/index.md) for up-to-date information.

# PolicyOS Scientist — Autoresearch Execution Blueprint

> **Version**: 2.1
> **Date**: 2026-03-23
> **Status**: implementation-grade architectural specification
> **Supersedes**: v1.0 vision blueprint, v2.0 execution blueprint
>
> This document is a **typed, layered, contract-bound architectural specification**
> for building PolicyOS Scientist into a governed multi-fidelity search platform for causal policy artifacts.
> It is not yet a full delivery-spec: acceptance thresholds are initial operational defaults
> subject to empirical recalibration, and some artifacts require greenfield implementation.
> It is, however, sufficient to begin Phase A construction and to guide all subsequent phases.

---

## Содержание

1. [Central Thesis](#1-central-thesis)
2. [Architecture: Three Layers, Not One System](#2-architecture-three-layers-not-one-system)
3. [Layer Contracts](#3-layer-contracts)
4. [Uncertainty Taxonomy](#4-uncertainty-taxonomy)
5. [Judge Stack](#5-judge-stack)
6. [Compute Economics Layer (VOI)](#6-compute-economics-layer-voi)
7. [Decision Readiness Contract](#7-decision-readiness-contract)
8. [Direction I — Multi-Fidelity Funnel](#8-direction-i-multi-fidelity-funnel)
9. [Direction II — Automated Policy Design](#9-direction-ii-automated-policy-design)
10. [Direction III — Causal Discovery](#10-direction-iii-causal-discovery)
11. [Shared Infrastructure](#11-shared-infrastructure)
12. [Architectural Invariants](#12-architectural-invariants)
13. [Artifact Minimality Rule](#13-artifact-minimality-rule)
14. [Platform Failure Modes and Mitigations](#14-platform-failure-modes-and-mitigations)
15. [Degraded Mode and Safe Fallback](#15-degraded-mode-and-safe-fallback)
16. [Cold Start Protocol](#16-cold-start-protocol)
17. [Cross-Run Transfer Isolation](#17-cross-run-transfer-isolation)
18. [Execution Phases](#18-execution-phases)
19. [SOTA Acceptance Criteria](#19-sota-acceptance-criteria)
20. [Design Inspirations](#20-design-inspirations)

---

## 1. Central Thesis

PolicyOS Scientist is not an autonomous researcher.
It is a **governed multi-fidelity search platform for causal policy artifacts**,
where proposals are cheap, evaluation is hard, uncertainty is explicit,
and promotion is contract-bound.

```text
propose
  → cheap reject          (ms,   deterministic)
  → medium-fidelity rank  (sec,  surrogate + reduced data)
  → full causal evaluate  (min,  flagship estimators)
  → refute + stress       (min,  adversarial + holdout)
  → judge stack verdict   (sec,  composite typed judges)
  → promote only if contract-bound gates pass
```

### 1.1. What this means operationally

1. **Evaluation-first**: every improvement must survive benchmark harness, hidden holdouts, reproducibility and audit.
2. **Trace-aware**: the loop learns from full execution traces, failure cards, profiler output — not just scalar rewards.
3. **Pareto-aware**: the system preserves multi-objective frontiers and hard constraints; never scalarizes.
4. **Uncertainty-typed**: every confidence claim carries a typed uncertainty envelope (see [§4](#4-uncertainty-taxonomy)).
5. **Judge-stacked**: no single arbiter; promotion requires AND-composition of typed judges (see [§5](#5-judge-stack)).
6. **Compute-economic**: scheduling is VOI-driven, not heuristic (see [§6](#6-compute-economics-layer-voi)).
7. **Contract-bound**: every promoted artifact carries a typed Decision Readiness Contract (see [§7](#7-decision-readiness-contract)).
8. **Governed by design**: legal/compliance/human-gate are loop participants, not post-hoc decorators.
9. **Reproducible by construction**: CAS lineage, dataset lineage, seed lineage, deterministic replay path.

---

## 2. Architecture: Three Layers, Not One System

The previous blueprint mixed three distinct systems. This version separates them explicitly
to prevent god-object risk and to enable independent evolution.

```text
┌──────────────────────────────────────────────────────────────┐
│                  Layer C — Discovery App                      │
│   Graph hypothesis generation, stability, active disambig.   │
│   Upstream of Layer B (provides graph priors to policy       │
│   design).                                                    │
├──────────────────────────────────────────────────────────────┤
│                  Layer B — Policy Design App                  │
│   Policy candidate schema, dossier, equity/legal/budget      │
│   constraints, frontier logic, translator.                   │
│   Consumes Layer A for evaluation. Consumes Layer C for      │
│   graph priors.                                               │
├──────────────────────────────────────────────────────────────┤
│                  Layer A — Scientist Core Platform            │
│   Ask/tell search, multi-fidelity funnel, judge stack,       │
│   registries, hidden benchmarks, replay, lineage,            │
│   promotion policy, compute economics, lesson memory.        │
│   Pure platform — no policy-specific or discovery-specific   │
│   logic.                                                      │
└──────────────────────────────────────────────────────────────┘
```

### 2.1. Dependency graph

```text
Layer C (Discovery) ──provides graph_priors──▶ Layer B (Policy Design)
Layer B (Policy Design) ──uses evaluation──▶ Layer A (Core Platform)
Layer C (Discovery) ──uses evaluation──▶ Layer A (Core Platform)
```

Layer A knows only **task-generic evaluation contracts**, not domain business logic.
(In practice, VOI routing and uncertainty propagation may differ by task family —
policy vs. discovery — but this variation is expressed through configuration,
not through domain-specific code inside Layer A.)
Layer B knows nothing about graph discovery algorithms.
Layer C knows nothing about policy design.

### 2.2. Grounding in existing code

| Layer | Existing modules | Key interfaces |
|-------|-----------------|----------------|
| A — Core | `scientist.search.controller`, `scientist.search.stages`, `scientist.search.strategies.*`, `scientist.autotune.models`, `scientist.autotune.registry`, `scientist.engine.*`, `scientist.kernel.fsm` | `SearchController`, `SearchStage`, `SearchStrategy`, `ChampionRegistry`, `PromotionPolicy`, `BenchmarkEvaluation`, `Phase` FSM |
| A — Core | `scientist.governance.pipeline`, `scientist.governance.passes.*` | `ValidationPipeline`, `ValidatorPass`, `ComplianceIssue` |
| A — Core | `scientist.engine.budget`, `scientist.engine.checkpoint`, `scientist.engine.retry` | `BudgetState`, `CASCheckpointHook`, `RetryPolicy` |
| B — Policy | `scientist.agent.*` (PI, Drafter, Critic, Formalizer), `scientist.workflows.*`, `scientist.doe.*` | `AgentRole`, `ProblemFrame`, `WorkflowSpec`, `SensitivityPlan` |
| B — Policy | `scientist.backtesting.*`, `scientist.cross_graph.*` | `HistoricalValidationPlan`, `EvidenceGatherer` |
| C — Discovery | `scientist.search.strategies.bayesian`, causal engine symbolic/discovery circuits | `SearchStrategy`, benchmark harness circuits (SYMBOLIC, DISCOVERY) |

---

## 3. Layer Contracts

Each layer exposes typed contracts. These contracts are the **only** way layers communicate.
No layer may reach into another's internals.

### 3.1. Layer A → consumers (B, C)

```python
# --- Core Search Contract ---
class SearchService(Protocol):
    """Ask/Tell interface for any optimization loop."""

    def ask(
        self,
        goal: SearchGoal,
        search_space: SearchSpaceSpec,
        context: SearchContext,
    ) -> list[CandidateProposal]: ...

    def tell(
        self,
        candidate_id: str,
        evaluation: EvaluationBundle,
    ) -> TellResult: ...
    # TellResult includes: registry_update, lesson_cards, frontier_delta

# --- Multi-Fidelity Funnel Contract ---
class FunnelService(Protocol):
    """Routes candidates through N fidelity levels."""

    def submit(self, candidate: CandidateProposal) -> FunnelTicket: ...
    def get_result(self, ticket: FunnelTicket) -> FunnelOutcome: ...
    # FunnelOutcome includes: stage_trace, metric_vectors, failure_cards,
    #   promotion_decision, compute_spend, confidence_profile, audit_explanation

# --- Judge Stack Contract ---
class JudgeStack(Protocol):
    """Composite typed judge — promotion requires AND over all."""

    def evaluate(self, candidate: CandidateProposal, evaluation: EvaluationBundle) -> JudgeVerdict: ...
    # JudgeVerdict includes: per_judge_verdicts, composite_decision, typed_failure_cards

# --- Registry Contracts ---
class ChampionRegistryContract(Protocol):
    def get_champion(self, loop_id: str) -> ChampionPointer | None: ...
    def consider_promotion(self, candidate: CandidateProposal, evaluation: BenchmarkEvaluation) -> PromotionDecision: ...

class ParetoRegistryContract(Protocol):
    def get_frontier(self, loop_id: str) -> ParetoSnapshot: ...
    def update(self, candidate: CandidateProposal, objectives: list[ObjectiveValue]) -> FrontierDelta: ...

class LessonRegistryContract(Protocol):
    def record(self, card: LessonCard) -> None: ...
    def query(self, context: LessonQuery) -> list[LessonCard]: ...
```

### 3.2. Layer B → Layer A

```python
# Policy Design submits candidates to Core via SearchService and FunnelService.
# Policy Design reads from ChampionRegistry, ParetoRegistry, LessonRegistry.
# Policy Design never touches funnel internals, stage implementations, or judge internals.

# --- Policy-specific extensions Layer B owns ---
class PolicyCandidateSchema:
    """Layer B's candidate schema — passed to Layer A as opaque payload."""
    interventions: list[InterventionSpec]
    rollout_plan: RolloutPlan
    target_population: TargetSpec
    parameter_schedule: ParameterSchedule
    budget_allocation: BudgetAllocation
    evidence_assumptions: list[AssumptionSpec]
    transport_assumptions: list[TransportAssumptionSpec]
    expected_harm_envelope: HarmEnvelope
```

### 3.3. Layer C → Layer A

```python
# Discovery submits graph hypotheses to Core via SearchService.
# Discovery's "candidate" is a GraphHypothesis, opaque to Layer A.

class GraphHypothesis:
    """Layer C's candidate schema."""
    adjacency: AdjacencySpec           # CPDAG/PAG or DAG
    edge_confidence: dict[EdgeId, float]
    assumptions: list[str]
    algorithm_family: str
    compute_footprint: ComputeFootprint
    failure_reasons: list[str]
```

### 3.4. Layer C → Layer B

```python
# Discovery provides graph priors to Policy Design.
class GraphPriorBundle:
    """Read-only contract from Discovery to Policy Design."""
    high_confidence_edges: list[Edge]
    disputed_edges: list[DisputedEdge]
    forbidden_edges: list[Edge]
    required_edges: list[Edge]
    equivalence_class_summary: str
    downstream_utility_scores: dict[str, float]
```

#### 3.4.1. Contract versioning and CAS pinning

Because Layer B and Layer C evolve independently, Layer B must **pin** the
`GraphPriorBundle` by its CAS hash at the start of each search run.

If Layer C updates the graph (discovers a new edge) while Layer B is iterating
over the Pareto frontier, the running search must NOT silently consume the new bundle.

**Rule**: at search-run start, Layer B records `graph_prior_bundle_ref: ArtifactRef`
in `ExperimentState.inputs`. This ref is immutable for the duration of the run.
After the run completes, Layer B may choose to re-run with the updated bundle,
but never mid-flight.

This applies symmetrically: any cross-layer contract artifact consumed during a run
must be CAS-pinned at run start. This is enforced by the `SearchService.ask()` contract,
which snapshots all input refs.

---

## 4. Uncertainty Taxonomy

Every confidence claim in the system must carry a **typed uncertainty** object.
"Low confidence" must never be ambiguous — different uncertainty types require
different responses.

### 4.1. Formal types

```python
class UncertaintyType(str, Enum):
    STATISTICAL    = "statistical"       # finite sample, bootstrap CI, power
    STRUCTURAL     = "structural"        # graph equivalence class, unobserved confounders
    TRANSPORT      = "transport"         # population shift, context mismatch, external validity
    MEASUREMENT    = "measurement"       # missingness, proxy variables, measurement error
    MODEL          = "model"             # simulator fidelity, SCM misspecification, functional form
    OPTIMIZATION   = "optimization"      # search incompleteness, surrogate drift, local optima


class UncertaintyEnvelope(BaseModel):
    """Typed uncertainty attached to any confidence claim."""
    model_config = ConfigDict(extra="forbid")

    uncertainties: dict[UncertaintyType, UncertaintyEstimate]


class UncertaintyEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: float                         # 0.0 = fully certain, 1.0 = fully uncertain
    source: str                          # human-readable provenance
    quantification_method: str           # "bootstrap_ci", "equivalence_class_count", "holdout_variance", etc.
    is_reducible: bool                   # can more data/compute reduce this?
    recommended_action: str | None       # "collect more data", "try intervention X", "increase sample", etc.
```

### 4.2. How each funnel level interacts with uncertainty types

| Funnel Level | Uncertainty types it CAN assess | Types it MUST propagate upward |
|--------------|-------------------------------|-------------------------------|
| Level 0 — Static Validity | none (deterministic) | none |
| Level 1 — Cheap Heuristics | OPTIMIZATION (surrogate confidence) | all other types as "unknown" |
| Level 2 — Causal Plausibility | STRUCTURAL, MEASUREMENT (partial) | STATISTICAL, TRANSPORT, MODEL |
| Level 3 — Medium Fidelity | STATISTICAL (partial), MODEL (partial) | TRANSPORT, full STATISTICAL |
| Level 4 — Full Fidelity | STATISTICAL, TRANSPORT, MODEL, MEASUREMENT | STRUCTURAL (graph uncertainty) |
| Level 5 — Refutation/Stress | all types explicitly tested | residual uncertainty envelope |

### 4.3. Uncertainty propagation rule

Every stage must output an `UncertaintyEnvelope`. If a stage cannot assess a particular
uncertainty type, it MUST propagate `level=1.0, source="not assessed at this fidelity"`.
This prevents downstream consumers from treating absence of information as certainty.

---

## 5. Judge Stack

Promotion is not decided by a single judge. It is decided by the **AND-composition**
of typed, independent judges. Each judge can independently fail with a typed failure card.

### 5.1. Judge definitions

| Judge | What it checks | Failure is | Override possible? |
|-------|---------------|------------|-------------------|
| **StructuralJudge** | identifiability, graph validity, adjustment set existence, positivity | fatal | no |
| **StatisticalJudge** | CI coverage, calibration, power, sample adequacy, bootstrap stability | fatal | no |
| **RobustnessJudge** | refutation survival, sensitivity analysis, scenario shift stability, adversarial holdout | fatal | no |
| **GovernanceJudge** | legal compliance, equity impact, privacy, human gate status, **policy-budget** ceiling (the candidate's fiscal cost) | fatal | only via HumanGateProtocol |
| **ReproducibilityJudge** | deterministic replay match, seed stability, artifact completeness, lineage integrity | fatal | no |
| **ComputeJudge** | **compute-budget** compliance (CPU/GPU spend), timeout absence, cost efficiency vs. improvement, replay cost | warning | yes, with explicit override |

> **Terminology note — two kinds of "budget"**:
> - **policy-budget**: the fiscal cost of the candidate policy itself (e.g. "$2B subsidy program").
>   Checked by GovernanceJudge via `budget_pass`.
> - **compute-budget**: the computational cost of evaluating the candidate (e.g. "15 min TMLE run").
>   Checked by ComputeJudge via `BudgetState`.
> These must never be conflated in code or configuration.

### 5.2. Composition rule

```python
class JudgeVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    per_judge: dict[str, SingleJudgeVerdict]
    composite_decision: Literal["promote", "reject", "defer_to_human"]
    blocking_failures: list[TypedFailureCard]
    warnings: list[TypedFailureCard]

    @property
    def is_promotable(self) -> bool:
        return all(v.passed for v in self.per_judge.values() if v.is_fatal)


class SingleJudgeVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judge_name: str
    passed: bool
    is_fatal: bool
    failure_card: TypedFailureCard | None
    uncertainty_assessed: list[UncertaintyType]
    evidence_refs: list[ArtifactRef]


class TypedFailureCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judge_name: str
    failure_type: str                   # e.g. "positivity_violation", "budget_exceeded"
    severity: Literal["blocker", "warning", "info"]
    description: str
    uncertainty_type: UncertaintyType | None
    remediation_hint: str | None
    evidence_ref: ArtifactRef | None
```

### 5.3. Grounding in existing code

The existing `ValidationPipeline` in `scientist.governance.pipeline` already implements
chain-of-responsibility with short-circuit on blocker. The judge stack extends this:

- Each existing `ValidatorPass` (budget, confidence, equity, legal, privacy, refutation,
  transportability, etc.) maps to a specific judge.
- The `ComplianceIssue` with `IssueSeverity` maps to `TypedFailureCard`.
- New: judges are **grouped** (structural, statistical, robustness, governance, reproducibility, compute)
  rather than flat-listed. This prevents a single miscalibrated pass from silently misleading the loop.

### 5.4. Judge-to-existing-pass mapping

| Judge | Existing passes it wraps |
|-------|-------------------------|
| StructuralJudge | (new — symbolic identification check, adjustment set validator) |
| StatisticalJudge | `confidence_pass`, `quality_gate_pass` |
| RobustnessJudge | `refutation_pass`, `transportability_required_pass`, `sutva_check_pass` |
| GovernanceJudge | `legal_pass`, `equity_pass`, `privacy_pass`, `human_review_pass`, `budget_pass` (policy-budget), `pii_check_pass` |
| ReproducibilityJudge | `checkpoint_pass`, `citation_validator_pass`, `freshness_pass` |
| ComputeJudge | (new — wraps `BudgetState` checks (compute-budget), timeout tracking, cost/improvement ratio) |

---

## 6. Compute Economics Layer (VOI)

The funnel scheduler must not route candidates by heuristic. It must reason over
**expected value of information per unit compute**.

### 6.1. Core economics model

```python
class ComputeEconomicsDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    recommended_action: Literal["advance", "defer", "reject", "retry_cheaper"]
    expected_improvement_per_usd: float       # EI / estimated_cost
    expected_falsification_value: float       # how much would a negative result teach us?
    expected_governance_value: float          # does this fill a Pareto gap or constraint gap?
    timeout_risk: float                       # P(timeout) estimated from runtime predictor
    replay_cost_usd: float                    # cost to reproduce for audit
    calibration_debt: float                   # how many expensive runs needed to recalibrate surrogates?
    current_pareto_position: str              # "dominated", "frontier", "near_frontier", "unknown"


class VOIScheduler(Protocol):
    """Value-of-Information scheduler for funnel routing."""

    def prioritize(
        self,
        candidates: list[FunnelTicket],
        budget_remaining: BudgetState,
        frontier: ParetoSnapshot,
    ) -> list[SchedulingDecision]: ...
```

### 6.2. Internal predictive models

The VOI scheduler relies on four lightweight internal models, trained on funnel history:

| Model | Input | Output | Training signal |
|-------|-------|--------|----------------|
| **Cheap causal surrogate** | policy features + graph features | predicted expensive-stage metric vector | Level 4 outcomes |
| **Runtime/timeout predictor** | candidate complexity features | P(timeout), estimated wall-time, estimated cost | actual Level 3/4 runtimes |
| **Uncertainty proxy** | candidate features + stage trace | predicted surrogate disagreement | Level 2 vs Level 4 divergence |
| **Promotion likelihood model** | candidate features + current frontier | P(promotion) | actual promotion decisions |

### 6.3. Integration with existing BudgetState

The existing `BudgetState` in `scientist.engine.budget` tracks `limits`, `spent`, `reserved`
with thread-safety and per-provider keys. The VOI scheduler extends this:

- Before routing a candidate to Level N, VOI checks `budget_remaining.would_exceed(estimated_cost)`.
- If timeout risk > threshold, VOI may route to Level 3 (medium fidelity) instead of Level 4.
- After each evaluation, `BudgetState.record_spend()` updates, and VOI re-prioritizes remaining candidates.

### 6.4. Exploration-exploitation balance

Pure `expected_improvement_per_usd` can make the scheduler too greedy — it will exploit
near-frontier candidates and ignore innovative but uncertain policy structures.

**Mitigation**: the scheduler uses a **UCB-style composite score**:

```python
priority = (1 - exploration_weight) * expected_improvement_per_usd
         + exploration_weight * expected_information_gain
```

Where `exploration_weight` is:
- **High** (0.3-0.5) during cold start and early search (< 30% of budget spent).
- **Medium** (0.1-0.2) during mid-search (30-70% of budget).
- **Low** (0.0-0.1) during late search (> 70% of budget, focus on exploitation).

This ensures the system occasionally "buys" expensive Level 4 evaluations purely
to explore unknown policy space regions, preventing premature convergence.

### 6.5. Anti-waste rules

1. Never advance a dominated candidate to Level 4 if a dominating candidate exists on the frontier.
2. Never advance if `expected_improvement_per_usd < min_roi_threshold` (configurable).
3. Reserve a compute budget fraction (default 15%) for calibration runs (sentinel candidates, see [§16](#16-cold-start-protocol)).
4. Track `calibration_debt` — when cheap surrogate accuracy drops, force recalibration before new promotions.

---

## 7. Decision Readiness Contract

A promoted artifact is not automatically usable for all downstream purposes.
Every promoted artifact carries a **typed readiness classification**.

### 7.1. Readiness levels

```python
class DecisionReadiness(str, Enum):
    RESEARCH_ARTIFACT    = "research_artifact"       # internal analysis only
    ANALYST_ADVISORY     = "analyst_advisory"         # can inform analyst recommendations
    EXTERNAL_BRIEFING    = "external_briefing"        # can appear in policy brief
    SIMULATION_READY     = "simulation_ready"         # can drive simulated rollout planning
    RECOMMENDATION_READY = "recommendation_ready"     # can be shown to decision-maker
    DEPLOYMENT_READY     = "deployment_ready"         # can inform actual policy deployment


class DecisionReadinessContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness_level: DecisionReadiness
    required_judges_passed: list[str]            # which judges must pass for this level
    required_uncertainty_bounds: dict[UncertaintyType, float]  # max uncertainty per type
    mandatory_human_gate: bool
    assumptions_must_be_surfaced: list[str]      # verbatim assumptions that must appear in output
    expiry_conditions: list[str]                 # when does this readiness expire?
    evidence_depth_required: str                 # "single_study", "meta_analytic", "replicated"
```

### 7.2. Level-to-requirement mapping

> **Note**: uncertainty thresholds below are **initial operational defaults**.
> They are normative starting points, not empirically calibrated values.
> Each threshold is subject to recalibration by domain, task family, benchmark regime,
> and accumulated operational experience. Phase A burn-in (§16) will produce the first
> empirical calibration data.

| Readiness Level | Required Judges | Max Statistical Uncertainty | Max Structural Uncertainty | Human Gate Required? |
|-----------------|----------------|---------------------------|--------------------------|---------------------|
| RESEARCH_ARTIFACT | Structural, Reproducibility | 1.0 (any) | 1.0 (any) | no |
| ANALYST_ADVISORY | Structural, Statistical, Reproducibility | 0.5 | 0.7 | no |
| EXTERNAL_BRIEFING | all except Compute | 0.3 | 0.5 | yes |
| SIMULATION_READY | Structural, Statistical, Robustness, Reproducibility | 0.3 | 0.4 | no |
| RECOMMENDATION_READY | all judges | 0.2 | 0.3 | yes |
| DEPLOYMENT_READY | all judges, replicated evidence | 0.1 | 0.2 | yes (senior) |

### 7.3. Policy Translator Agent

The `ChampionPolicyDossier` is a technical artifact containing ATE, HTE, SHD, DAG metrics.
For readiness levels `EXTERNAL_BRIEFING` and above, a **Policy Translator** must convert
causal artifacts into standard policy brief language.

The translator is a bounded worker (not autonomous agent) whose output is:
1. Executive summary in non-technical language.
2. Key trade-offs table (Pareto frontier in plain words).
3. Assumptions listed in natural language with confidence qualifiers.
4. Risk section mapping each `UncertaintyType` to operational risk.
5. Recommended next steps for the decision-maker.

This output is an artifact type `PolicyBrief`, separate from `ChampionPolicyDossier`,
and is subject to the same governance pipeline (legal pass, equity pass).

#### 7.3.1. Anti-spin contract

The translator is a simplification layer, not a marketing layer. It is bound by the
following invariants:

1. **May not remove blocker assumptions** — every assumption surfaced in `DecisionReadinessContract.assumptions_must_be_surfaced` must appear verbatim or with equivalent meaning.
2. **May not collapse uncertainty types** — "low confidence" must specify *which* uncertainty type is low; collapsing six types into one confidence phrase is forbidden.
3. **May not omit subgroup harm notes** — if `SubgroupImpactReport` contains negative effects for any subgroup, the brief must surface them.
4. **May not promote readiness level** — the brief must display the assigned `DecisionReadiness` level from the contract, not a higher one.
5. **May not omit constraint status** — if a hard constraint is binding (near violation), this must be visible.

These rules are enforced by a dedicated `TranslatorCompliancePass` in the governance pipeline,
which compares the `PolicyBrief` against the source `ChampionPolicyDossier` and `DecisionReadinessContract`.

---

## 8. Direction I — Multi-Fidelity Funnel

### 8.1. Why funnel is the first build priority

Without the funnel, policy design burns compute on structural nonsense,
discovery swarm drowns in mismatch noise, and the system hits the timeout wall
observed in ACIC/LBIDD benchmarks (2026-03-23 benchmark run).

### 8.2. Six-level adaptive fidelity ladder

#### Level 0 — Static Legality and Structural Validity

**Cost**: < 1ms. **Deterministic**.

Checks:
1. Schema-valid IR (Pydantic `ConfigDict(extra="forbid")` validation).
2. Parameter domain validity (rates in [0,1], no NaN/Inf — extends existing `CheapStage._check_parameters`).
3. Forbidden policy combinations (static rule set).
4. Unit/dimension consistency.
5. Policy-budget envelope sanity (does candidate's fiscal cost fit within policy fiscal constraints? — this is **policy-budget**, not compute-budget; `BudgetState` is not used here).
6. Legal red flags detectable by static rules (extends `legal_pass` AST backend).
7. Mechanism completeness (at least one intervention with one objective).

**Grounding**: extends existing `CheapStage._check_structure` and `_check_parameters`.

#### Level 1 — Cheap Domain Heuristics and Prior-Based Screening

**Cost**: 1-100ms. **Mostly deterministic, some learned components**.

Signal sources:
1. Historic failure patterns from `LessonRegistry`.
2. Domain priors from `academic` graph and `cross_graph.gatherers`.
3. Policy conflict rules.
4. Overlap risk heuristics (fast covariate overlap check).
5. Prior transportability impossibility flags.
6. Rough feasibility models (extends `agent.feasibility`).
7. Cheap nuisance diagnostics.

**Key question this level answers**: "Is it worth spending causal budget on this candidate?"

**Output**: `CheapSignalVector` (see §8.5).

#### Level 2 — Fast Causal Plausibility

**Cost**: 100ms - 5s. **Uses symbolic engine**.

Checks:
1. Symbolic identifiability / non-identifiability (existing symbolic circuit).
2. Existence of admissible adjustment sets.
3. Positivity / overlap risk score (fast, on reduced sample).
4. Fast proxy estimation on subsample.
5. Transport/missingness compatibility flags.
6. Refutation susceptibility heuristics.

**This level does NOT produce welfare estimates.** It produces causal plausibility rank.

**Grounding**: wraps existing `benchmarks.harness.BenchmarkCircuit.SYMBOLIC` and
`MISSING` / `TRANSPORT` circuits in a lightweight evaluation mode.

#### Level 3 — Medium-Fidelity Evaluation

**Cost**: 5s - 2min. **The critical neglected middle layer.**

Runs:
1. Reduced data slices (subsample).
2. Cheaper estimators (linear, simple matching).
3. Simplified SCM variants.
4. Fewer bootstrap draws (e.g. 50 instead of 500).
5. Coarser scenario sets.
6. Top-k subgroup evaluation (not full HTE matrix).

**Purpose**: produce *comparable* intermediate metrics for ASHA/Successive-Halving pruning.

**Grounding**: uses existing `SearchStage` interface with a new `MediumFidelityStage`
that wraps `ExpensiveStage` with reduced-data and reduced-bootstrap configurations.
Integrates with `multi_fidelity.py` strategy in search.

##### Level 3 causal distortion warning

In standard ML, medium fidelity means "fewer epochs" or "smaller batch". In causal/policy
settings, reduced data **changes the causal signal itself**:
- Different overlap structure (positivity violations appear/disappear).
- Different subgroup composition (rare vulnerable groups may vanish from subsample).
- Different transport difficulty.
- Unstable HTE estimates.
- Masked rare harms.

**Therefore**:

> **Cardinal rule**: Medium-fidelity metrics are **routing signals**, never promotion evidence.
> No candidate may be promoted based solely on Level 3 results.

**Operational safeguards for Level 3**:

1. **Stratified subsampling**: subsamples must preserve representation of all policy-relevant
   subgroups. Use stratified sampling keyed on treatment assignment and top-k subgroup indicators.
   Otherwise, ASHA pruning will systematically kill policies targeting narrow vulnerable groups
   because the target population vanishes from the subsample.
2. **Metrics safe for cross-fidelity comparison** (allowed for pruning):
   - ATE point estimate direction and order-of-magnitude.
   - Budget feasibility (cost scales linearly with data size).
   - Structural validity (identifiability does not change with sample size).
   - Compliance/legal status (deterministic, data-independent).
3. **Metrics forbidden for pruning** (change meaning at reduced fidelity):
   - CI width (artificially wide on subsample — not indicative of full-data CI).
   - HTE heterogeneity (unstable on small slices).
   - Subgroup harm magnitude (biased when subgroup is underrepresented).
   - Bootstrap stability (fewer draws = noisier stability estimate).
4. **Fidelity gap audit**: after each Phase A cycle, compute Level 3 vs Level 4 metric
   divergence on the same candidates. If divergence exceeds threshold for "safe" metrics,
   recalibrate Level 3 configuration (increase subsample size, add stratification keys).

#### Level 4 — Full-Fidelity Causal Evaluation

**Cost**: 2-30min. **Crown jewel — reserved for top candidates.**

Only here:
1. Flagship estimators (TMLE, forest-based, ensemble).
2. Full bootstrap uncertainty (500+ draws).
3. Transport and missingness robustness.
4. Full HTE slicing.
5. Counterfactual stress.
6. Policy value estimation.
7. Audit-ready reporting.

**Grounding**: existing `ExpensiveStage` wrapping full `WorkflowEngine.run()`.

Only a small fraction (target: < 10%) of candidates reach this level.

#### Level 5 — Refutation, Stress, Adversarial, Governance

**Cost**: 2-15min. **Mandatory for any candidate that passes Level 4.**

1. DoWhy-style refuters (placebo, subset, random cause).
2. Perturbation tests (parameter sensitivity via existing `doe.analysis`).
3. Adversarial scenario shifts (existing `backtesting.adversarial`).
4. Hidden holdout slices (not seen during Levels 1-4).
5. Proxy-hacking tests (sentinel candidates, see §8.7).
6. Fairness and distributional harm checks (existing `equity_pass`).
7. Compliance gate (existing `legal_pass`).
8. Human escalation for high-stakes (existing `HumanGateProtocol`).

#### Level 6 — Champion/Challenger Promotion

Promotion requires:
1. Judge Stack verdict is `promote` (see [§5](#5-judge-stack)).
2. Candidate dominates or improves over champion on Pareto frontier.
3. Hidden holdout shows no degradation.
4. Reproducibility is stable (replay match or bounded seed variance).
5. Audit bundle is complete (all artifact refs populated in `ExperimentState`).
6. Decision Readiness Contract is typed (see [§7](#7-decision-readiness-contract)).

**Grounding**: extends existing `ChampionRegistry.consider_promotion()` with Judge Stack
and Decision Readiness Contract.

### 8.3. Funnel cardinal rule: optimize recall, not reject rate

The cheap stage's primary KPI is **near-zero false-negative rate** on eventually-good candidates.

Metrics:
1. False-negative rate on eventual top-tier candidates: target < 1-2%.
2. Expensive-stage load reduction: target > 60%.
3. Stage disagreement: continuously monitored via existing `CorrelationTracker`.
4. Calibration drift: threshold-triggered recalibration.

### 8.4. Funnel algorithmic flow

```text
candidate_generator.generate()
    │
    ▼
Level 0: static validator ──reject──▶ failure_card + lesson
    │ pass
    ▼
Level 1: cheap heuristics + lesson_registry ──reject──▶ failure_card + lesson
    │ pass
    ▼
Level 2: symbolic causal plausibility ──reject──▶ failure_card + lesson
    │ pass (produces CheapSignalVector)
    ▼
VOI Scheduler: prioritize by expected_improvement_per_usd
    │
    ▼
Level 3: medium-fidelity (ASHA pruning) ──prune──▶ failure_card + lesson
    │ survive
    ▼
VOI Scheduler: re-prioritize survivors
    │
    ▼
Level 4: full-fidelity ──fail──▶ failure_card + lesson
    │ pass
    ▼
Level 5: refutation + governance ──fail──▶ failure_card + lesson
    │ pass
    ▼
Level 6: Judge Stack → promote / reject / defer_to_human
    │ promote
    ▼
ChampionRegistry.consider_promotion()
ParetoRegistry.update()
LessonRegistry.record(success_card)
```

### 8.5. CheapSignalVector

```python
class CheapSignalVector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    structural_validity: float          # 0=invalid, 1=fully valid
    causal_identifiability: float       # 0=non-identifiable, 1=fully identified
    positivity_risk: float              # 0=no risk, 1=severe violation
    transportability_risk: float        # 0=no risk, 1=untransportable
    uncertainty_prior: float            # 0=low, 1=high prior uncertainty
    policy_conflict: float              # 0=no conflicts, 1=severe conflicts
    feasibility: float                  # 0=infeasible, 1=fully feasible
    expected_value_proxy: float         # surrogate-predicted value
    expected_harm_proxy: float          # surrogate-predicted harm
    expected_information_gain: float    # how much would evaluating this teach us?

    def routing_decision(self) -> Literal["reject", "defer", "advance", "fast_track"]:
        """Deterministic routing based on vector thresholds."""
        if self.structural_validity < 0.5 or self.causal_identifiability < 0.2:
            return "reject"
        if self.positivity_risk > 0.8 or self.policy_conflict > 0.8:
            return "reject"
        if (self.expected_value_proxy > 0.9
                and self.feasibility > 0.8
                and self.expected_harm_proxy < 0.1
                and self.positivity_risk < 0.2
                and self.uncertainty_prior < 0.3):
            return "fast_track"  # skip Level 3, go directly to Level 4 (rare)
        return "advance"
```

### 8.6. SearchController generalization

The existing `SearchController` has binary cheap/expensive split.
The funnel extends this to N stages:

```python
# Target interface — extends existing SearchStage
class FunnelStage(SearchStage):
    """Stage within the multi-fidelity funnel."""

    @property
    @abstractmethod
    def fidelity_level(self) -> int: ...

    @property
    @abstractmethod
    def estimated_cost_usd(self) -> float: ...

    @abstractmethod
    def evaluate(self, candidate: dict, context: dict) -> FunnelStageResult: ...
    # FunnelStageResult extends StageResult with:
    #   uncertainty_envelope: UncertaintyEnvelope
    #   cheap_signal: CheapSignalVector | None
    #   failure_cards: list[TypedFailureCard]
    #   compute_actual_usd: float
```

### 8.7. Anti-reward-hacking architecture

1. **Hidden holdout scenario packs**: Level 5 uses scenario packs not seen during Levels 1-4.
   Managed via `BenchmarkSplitManifest` with rotating `holdout_ids`.
2. **Rotating benchmark slices**: holdout composition changes periodically.
3. **Sentinel candidates**: known-good candidates with small mutations. If cheap stage
   kills them, surrogate is miscalibrated → trigger recalibration. (See [§16.3](#16-3-sentinel-candidates).)
4. **Cheap-to-expensive disagreement monitors**: existing `CorrelationTracker` extended
   to trigger alerts when Spearman correlation drops below threshold.
5. **Adversarial candidates**: intentionally constructed to fool cheap stage.
6. **Promotion ban on calibration drift**: if `CorrelationTracker.compute_metrics()["spearman_correlation"]`
   < 0.5, block all promotions until recalibration completes.

---

## 9. Direction II — Automated Policy Design

### 9.1. Problem statement

Wrong: "Agent maximizes welfare score."

Right: "System designs, compares, and verifies policy programs under hard causal,
budgetary, legal, robustness, and equity constraints. Output is a Pareto frontier
with typed readiness contracts, not a single winner."

### 9.2. Policy program as optimization object

A policy candidate in Layer B is not a scalar. It is a structured program:

1. Set of interventions.
2. Rollout order and timing.
3. Target population logic.
4. Parameter schedule over time.
5. Budget allocation.
6. Fallback / contingency variants.
7. Monitoring plan.
8. Evidence assumptions and transport assumptions.
9. Expected harm envelope.
10. Implementation notes for operators.

### 9.3. Objective stack

#### Primary objectives
1. Welfare / utility uplift.
2. Poverty reduction.
3. Employment or growth gains.
4. Distribution-sensitive benefit.
5. Policy value under learned targeting rule.

#### Hard constraints (violation = fatal rejection)
1. Budget ceiling.
2. Inequality ceiling (Gini, Atkinson).
3. Minimum transportability validity.
4. Minimum overlap quality.
5. Minimum compliance score (legal_pass).
6. Maximum acceptable uncertainty per type (from UncertaintyEnvelope).
7. No forbidden legal mechanisms.

#### Secondary objectives
1. Robustness under scenario shifts.
2. Implementation simplicity.
3. Political/administrative feasibility.
4. Interpretability.
5. Evidence depth.
6. Subgroup fairness.

#### Penalty channels
1. Estimation fragility (bootstrap instability).
2. Graph sensitivity (sign flip under adjacent graphs).
3. Heavy reliance on implausible assumptions.
4. Narrow targeting that overfits to sample artifacts.
5. Large variance in subgroup outcomes.

### 9.4. Hierarchical search

#### Level A — Structure search
What: which interventions, combinations, rollout order, target populations, policy families.
Algorithms: tree search, portfolio sweep (existing `run_portfolio_search`), guided combinatorial search.

#### Level B — Parameter search
What: rates, subsidy magnitudes, caps, schedules, thresholds, targeting cutoffs.
Algorithms: Bayesian optimization (existing `strategies.bayesian`), evolutionary mutation,
ask/tell with batched proposals.

#### Level C — Narrative and rationale search
What: explanation quality, implementation framing, evidence synthesis wording.
This does NOT substitute causal evaluation. It improves the final dossier.

### 9.5. Worker roles (bounded, not autonomous)

| Role | What it does | LLM? | Can promote? |
|------|-------------|------|-------------|
| **Policy Proposer** | generates structural and parametric candidates | yes | no |
| **Causal Compiler** | converts candidate to executable causal plan | no | no |
| **Constraint Critic** | checks budgets, overlap, transport, legality | no | no |
| **Scenario Adversary** | constructs unfavorable counter-scenarios | yes (bounded) | no |
| **Evidence Synthesizer** | pulls literature priors and mechanism support | yes (bounded) | no |
| **Equity Auditor** | checks subgroup harms | no | no |
| **Policy Translator** | converts technical dossier to policy brief (see §7.3) | yes (bounded) | no |
| **Governance Agent** | prepares gate package | no | no |
| **Judge Stack** | deterministic benchmark/governance harness | no | **yes — only entity that can** |

**Cardinal rule**: LLMs may propose, critique, synthesize, prioritize, explain.
Only the deterministic Judge Stack may decide promotion.

### 9.6. GEPA-style trace-aware learning

Policy loops must learn from full execution traces, not just scalar rewards.

Traces consumed:
1. Why candidate failed legal gate (from `legal_pass` `ComplianceIssue`).
2. Which subgroup was harmed (from `equity_pass`).
3. Which assumption was fragile (from `refutation_pass`).
4. Which estimator timed out (from `BudgetState` / runtime predictor).
5. Which mechanisms lacked literature support (from `cross_graph.gatherers.academic`).
6. Where transportability broke (from `transportability_required_pass`).
7. Which budget component drove rejection (from `budget_pass`).

These traces convert to `LessonCard` artifacts in `LessonRegistry` and feed back
into Level 1 screening and Policy Proposer context.

### 9.7. Pareto frontier as central object

The system stores:
1. **Global Pareto frontier** for all feasible candidates.
2. **Policy family frontiers** by intervention class.
3. **Equity-aware frontier** (Pareto over welfare + Gini).
4. **Low-risk frontier** (Pareto over value + robustness).
5. **Implementation-simple frontier** (Pareto over value + simplicity).

Each frontier is managed via `ParetoRegistryContract`. Final output is champion + frontier
showing what is sacrificed or gained. Extends existing `SearchController._update_pareto_front()`.

### 9.8. Output artifact bundle

1. `PolicyFrontierReport` — full Pareto frontier with trade-off visualization.
2. `ChampionPolicyDossier` — detailed champion analysis.
3. `PolicyBrief` — translator output for non-technical consumers (§7.3).
4. `ConstraintSatisfactionReport` — which constraints bind, which are slack.
5. `SubgroupImpactReport` — distributional effects.
6. `UncertaintyReport` — typed uncertainty envelope (§4) for champion and frontier.
7. `TransportabilityReport` — external validity analysis.
8. `GovernanceGatePacket` — complete governance pipeline trace.
9. `ImplementationPlan` — rollout sequence and monitoring plan.
10. `RejectedAlternativesSummary` — why alternatives were dominated or rejected.
11. `ReplayableAuditBundle` — everything needed for deterministic replay.
12. `DecisionReadinessContract` — typed readiness level (§7).

---

## 10. Direction III — Causal Discovery

### 10.1. Fundamental rule

> Swarm does not decide the graph.
> Swarm proposes graph hypotheses, priors, edge constraints, and experiment ideas.
> Deterministic judge evaluates them.

### 10.2. Phased approach (not premature multi-agentization)

Discovery must be built in three phases, NOT starting with a 10-role swarm:

**Phase 1 (with Phase A of funnel)**: Algorithm portfolio + shared judge.
- 3-4 algorithmic families (constraint-based, score-based, functional, time-series).
- Each runs independently, produces `GraphHypothesis`.
- Shared judge evaluates all hypotheses using downstream causal utility.
- Stability layer (bootstrap + subsample) for all candidates.

**Phase 2 (with Phase B)**: Prior integration + active disambiguation.
- Prior miner from `academic` stack.
- Forbidden/required edge constraints.
- Active disambiguation planner.

**Phase 3 (with Phase C/D)**: Bounded agent workers.
- Skeptic/Refuter worker.
- Data Profiler worker.
- Evidence Synthesizer worker.
- Only added when signal quality from Phases 1-2 is proven sufficient.

### 10.3. Ideal output

The system does not produce a single brittle graph. It produces a **structured uncertainty object**:

1. High-confidence core graph.
2. Uncertainty-preserving PAG/CPDAG layer.
3. Edge-level confidence and provenance.
4. Competing graph hypotheses.
5. Downstream effect-estimation utility scores.
6. Recommended next measurements or interventions to disambiguate uncertainty.
7. `UncertaintyEnvelope` with `STRUCTURAL` type prominently featured.

### 10.4. Algorithm portfolio (Phase 1)

| Family | Representative methods | Strengths | When to use |
|--------|----------------------|-----------|-------------|
| Constraint-based | PC, FCI, FCI+ | Handles latent confounders (FCI), fast | Default for observational data |
| Score-based | GES, GIES, DAGMA | Handles interventional data (GIES), smooth opt | When interventional data exists |
| Functional | ANM, pairwise heuristics | Orientation from functional form | Small graphs, bivariate |
| Time-series | PCMCI, PCMCI+ | Lag-aware discovery | When temporal structure exists |

Each algorithm produces a `GraphHypothesis` (§3.3) and feeds it to Layer A's `SearchService.tell()`.

### 10.5. Downstream causal utility judge

Graph candidates are judged NOT only by SHD/edge metrics, but by downstream tasks:

1. Can the graph identify the target estimand? (identifiability test)
2. Are adjustment sets stable across bootstrap? (stability)
3. Does effect estimation quality improve when using this graph? (on benchmark tasks)
4. Does the graph enable useful transport reasoning? (transportability check)
5. Is the graph reproducible under seed variation? (reproducibility)

**A graph that is slightly worse by SHD but far better for identification
is the practically superior graph.** This is PolicyOS's key differentiator.

### 10.6. Consensus must be evidence-weighted, not conversational

Wrong: "five algorithms vote, majority wins."

Right:
1. Workers submit structured `GraphHypothesis` proposals.
2. Judge evaluates each on stability + downstream utility + prior consistency.
3. Aggregator computes edge-level confidence from evidence-weighted scores.
4. Output preserves honest uncertainty (disputed edges, equivalence classes).

### 10.7. Active discovery (end-state, not Phase 1)

When the system has sufficient confidence infrastructure:
1. What variable to measure better?
2. Which intervention would maximally reduce graph uncertainty?
3. Which dataset slice is most informative?
4. Which natural experiment would orient the disputed edge?

Output includes acquisition/experiment plan alongside graph hypothesis.

### 10.8. Discovery output bundle

1. `DiscoveryTaskProfile` — framing decisions.
2. `PriorKnowledgeBundle` — all priors used.
3. `GraphHypothesisSet` — all candidate graphs with metadata.
4. `EdgeConfidenceMatrix` — per-edge confidence.
5. `BootstrapStabilityReport` — stability metrics.
6. `DownstreamUtilityReport` — identification and estimation utility.
7. `RefutationReport` — skeptic findings.
8. `ReproducibilityReport` — seed/subsample stability.
9. `ActiveDisambiguationPlan` — recommended next steps (Phase 2+).
10. `DiscoveryAuditBundle` — full replay material.
11. `GraphPriorBundle` — contract output to Layer B (§3.4).

---

## 11. Shared Infrastructure

### 11.1. Ask/Tell search service

All three layers (funnel, policy design, discovery) share one search substrate:

```python
# ask(goal, space, context) → candidates
# tell(candidate_id, evaluation) → registry_update + lessons
```

Benefits:
- Async evaluation (human gates, external compute) naturally fits ask/tell.
- Batched evaluation and multi-agent coordination become simpler.
- Existing `SearchController` already implements the loop; ask/tell is a thin wrapper.

### 11.2. Registries

| Registry | Semantics | Existing base |
|----------|----------|---------------|
| **ChampionRegistry** | Current production-best feasible artifact | `autotune.registry.ChampionRegistry` |
| **ParetoRegistry** | Non-dominated feasible frontier | `autotune.pareto` (extends) |
| **LessonRegistry** | Reusable failure modes, mutation hints, anti-patterns | new — backed by CAS artifacts |
| **BenchmarkRegistry** | Canonical suites, hidden holdouts, scorecards | `autotune.models.BenchmarkSuite` + `BenchmarkSplitManifest` |
| **DiscoveryHypothesisRegistry** | Graph candidates and confidence snapshots | new — backed by CAS artifacts |

### 11.3. Actionable Side Information

Formalized as a canonical artifact (not just log lines):

```python
class ActionableSideInformation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    profiler_output: dict[str, Any]       # timing, memory peaks
    timeout_diagnostics: dict[str, Any]   # which stage, why
    identifiability_blockers: list[str]   # which estimands couldn't be identified
    sensitivity_failures: list[str]       # which refutation tests failed
    subgroup_harm_notes: list[str]        # which subgroups were negatively affected
    legality_failures: list[str]          # which legal rules were violated
    transport_failures: list[str]         # which transport conditions broke
    discovery_ambiguity_notes: list[str]  # which edges are disputed
    policy_budget_explanation: dict[str, float]   # fiscal cost breakdown (policy-budget)
    compute_budget_explanation: dict[str, float]  # evaluation cost breakdown (compute-budget)
```

### 11.4. Hidden benchmark architecture

```text
┌────────────────────┐
│ Visible Selection   │ ← used for Level 1-4 evaluation
├────────────────────┤
│ Hidden Holdout      │ ← used ONLY at Level 5 (refutation)
├────────────────────┤
│ Rotating Challenge  │ ← composition changes every N runs
├────────────────────┤
│ Adversarial Set     │ ← designed to fool cheap stages
├────────────────────┤
│ Sentinel Set        │ ← known-good candidates for calibration (§16.3)
└────────────────────┘
```

Managed via `BenchmarkSplitManifest` with extended split types.

### 11.5. Cross-loop optimization contracts

Loops may optimize each other, but only through stable contracts:

| Optimizing loop | What it improves | Via contract |
|----------------|-----------------|-------------|
| Cheap-stage loop | funnel thresholds | `CheapSignalVector` calibration against Level 4 outcomes |
| Estimator loop | runtime/accuracy | `BenchmarkEvaluation` on canonical suites |
| Policy loop | reuses calibrated cheap models | `LessonRegistry` + surrogate model artifacts |
| Discovery loop | improves priors for policy loop | `GraphPriorBundle` (§3.4) |

No loop may reach into another's internal state.

---

## 12. Architectural Invariants

These rules must hold **always**, regardless of domain, task family, or deployment context.
They are not guidelines — they are structural constraints enforced by code.

1. **No promoted artifact without replay bundle**: every artifact in `ChampionRegistry`
   must have a complete `ReplayableAuditBundle` (seed, dataset fingerprint, code revision,
   dependency environment, artifact refs, replay command). Promotion without replay = system bug.

2. **Absence of assessment is never low uncertainty**: if a funnel stage cannot assess
   an `UncertaintyType`, it MUST emit `level=1.0, source="not assessed"`. The system
   must never serialize missing assessment as low uncertainty. This is enforced by
   `UncertaintyEnvelope` validation: all six types must be present.

3. **Human override never suppresses failure cards**: when `HumanGateProtocol` overrides
   a judge decision, it appends an `OverrideRationale` to the failure card — it does not
   delete the original card. The audit trail always shows both the machine judgment and
   the human override with reasoning.

4. **Discovery priors without provenance are forbidden**: every `required_edge` in
   `GraphPriorBundle` must carry a provenance ref (literature, domain rule, or intervention data).
   Hard required edges without provenance are rejected at contract validation.

5. **Cheap-stage rejection always emits machine-readable reason**: every Level 0-2 rejection
   produces a `TypedFailureCard` with `failure_type` from a controlled vocabulary and
   `remediation_hint`. Silent rejections are forbidden — they prevent trace-aware learning.

6. **Cross-layer contracts are CAS-pinned at run start**: any artifact consumed from
   another layer during a search run is immutably referenced by `ArtifactRef` at run
   initialization. Mid-run updates to upstream artifacts never propagate into a running search.

7. **Pareto frontier is externally immutable within a run**: only the active search run
   may mutate its own frontier (add non-dominated points, remove dominated points).
   No external process — including other concurrent runs, operators, or Layer C updates —
   may modify a running frontier. Cross-run frontier merging is an explicit post-run
   operation with provenance.

8. **Sentinel injection rate is mandatory**: the funnel must inject sentinel candidates
   at a minimum rate (default: 1 per 20 candidates). Disabling sentinels requires
   explicit configuration override with logged rationale.

---

## 13. Artifact Minimality Rule

The system defines many artifact types. To prevent protocol inflation — where the platform
produces paperwork about work instead of actual work — every artifact must justify its
existence by serving at least one of four functions:

| Function | Description | Example |
|----------|------------|---------|
| **Routing** | Artifact is consumed by funnel/scheduler to make a decision | `CheapSignalVector`, `ComputeEconomicsDecision` |
| **Promotion/Gating** | Artifact is required for Judge Stack evaluation or promotion | `JudgeVerdict`, `BenchmarkEvaluation`, `DecisionReadinessContract` |
| **Replay/Audit** | Artifact is required to reproduce a result or satisfy regulatory audit | `ReplayableAuditBundle`, `ExperimentState`, `ActionableSideInformation` |
| **Cross-run Learning** | Artifact is consumed by `LessonRegistry` or surrogate training | `LessonCard`, `TypedFailureCard`, `CorrelationRecord` |

**Rule**: if an artifact does not serve at least one of these four functions,
it must be either:
1. Merged into an existing artifact that does, or
2. Removed entirely.

This rule applies retroactively to all artifacts defined in this document.
During Phase A implementation, each artifact should be tagged with its function(s)
in the schema definition.

### 13.1. Artifact audit for output bundles

The policy design output bundle (§9.8) defines 12 artifacts. The discovery output bundle
(§10.8) defines 11 artifacts. Before implementation, each artifact must pass the minimality
test. Artifacts that serve only "nice to have" reporting with no routing, gating, replay,
or learning function should be consolidated.

---

## 14. Platform Failure Modes and Mitigations

The platform itself can fail. This section catalogs known risks.

| # | Failure Mode | Impact | Mitigation |
|---|-------------|--------|-----------|
| 1 | **Surrogate catastrophically wrong** | Cheap stage kills good candidates (false negatives) | Sentinel candidates (§16.3), `CorrelationTracker` drift alerts, calibration budget reserve |
| 2 | **Hidden holdout biased** | Level 5 gives false confidence | Rotating holdout composition, stratified splits, periodic holdout quality audit |
| 3 | **Lesson Registry poisoned** | Bad lessons contaminate Level 1 screening | Lesson expiry TTL, lesson confidence scores, lesson source tracing (§17) |
| 4 | **Single judge miscalibrated** | One pass silently blocks good candidates or passes bad ones | Judge Stack (§5) — no single point of failure; per-judge disagreement monitoring |
| 5 | **Simulator fidelity gap** | System optimizes for simulator, not reality | MODEL uncertainty type in envelope, mandatory disclosure in Decision Readiness Contract |
| 6 | **Compute budget exhausted mid-run** | Partial evaluation with no useful output | `BudgetState.would_exceed()` pre-check, graceful degradation (§15) |
| 7 | **Pareto frontier stagnation** | System finds no improvement for many iterations | VOI exploration weight (§6.4), diversity tracking (existing `DiversityTracker`), search space expansion trigger |
| 8 | **Adversarial candidate gaming** | Optimizer learns to fool cheap stage without improving real outcome | Anti-reward-hacking architecture (§8.7), promotion ban on calibration drift |
| 9 | **Human gate bottleneck** | Decisions queue behind slow human review | Decision Readiness levels (§7) — only high-stakes need human gate; async ask/tell; degraded mode (§15) |
| 10 | **Graph prior contamination** | Discovery provides biased priors to policy design | Discovery outputs disputed edges explicitly; policy design treats priors as soft constraints; CAS pinning (§3.4.1) |
| 11 | **Medium-fidelity causal distortion** | ASHA prunes good policies targeting rare subgroups | Stratified subsampling, forbidden pruning metrics, fidelity gap audit (§8 Level 3) |
| 12 | **VOI scheduler too greedy** | Ignores innovative policies in unexplored regions | UCB-style exploration weight, mandatory exploration budget fraction (§6.4) |
| 13 | **Policy Translator spin** | Brief misrepresents uncertainty or omits harms | Anti-spin contract (§7.3.1), `TranslatorCompliancePass` |
| 14 | **Cross-layer contract version mismatch** | Policy Design consumes stale graph priors mid-run | CAS pinning at run start (§3.4.1, invariant #6) |

---

## 15. Degraded Mode and Safe Fallback

The system must define what happens when components are unavailable or unreliable.
Degradation must be **explicit and observable**, never silent.

### 15.1. Degradation hierarchy

| Condition | System mode | What changes | Logged as |
|-----------|------------|-------------|-----------|
| All systems nominal | **Normal** | Full funnel + Judge Stack + VOI | — |
| Judge Stack partially unavailable (1-2 judges down) | **Reduced-judge mode** | Missing judges treated as `passed=False, is_fatal=True` → no promotions; search continues for learning | WARNING |
| VOI surrogate drifted (correlation < threshold) | **Conservative-routing mode** | VOI disabled; all Level 2 survivors route to Level 3 sequentially; calibration burn-in triggered | WARNING |
| Hidden holdout registry corrupted or empty | **No-promotion mode** | Level 5 refutation skipped; candidates capped at RESEARCH_ARTIFACT readiness; human alert | CRITICAL |
| Discovery priors absent (Layer C offline) | **Prior-free mode** | Layer B operates without graph priors; structural search uses analyst-provided priors only | INFO |
| Human gate backlog > threshold | **Auto-cap mode** | New candidates automatically capped at SIMULATION_READY; queue alert sent | WARNING |
| Reproducibility check fails due to infra (not science) | **Infra-retry mode** | Replay retried 2x; if still failing, flagged `reproducibility=infra_failure`; not promoted but not lost | WARNING |
| Compute budget exhausted | **Freeze-frontier mode** | No new evaluations; existing frontier preserved; system reports budget exhaustion | CRITICAL |

### 15.2. Fallback rules

1. **No silent degradation**: every mode transition emits a structured event to telemetry.
   The calibration report surfaces current degradation state.
2. **Degradation cannot promote**: in any degraded mode, the maximum achievable
   `DecisionReadiness` is capped. The system never produces higher-readiness artifacts
   during degradation.
3. **Recovery policy**: automatic recovery where safe and verifiable (e.g. surrogate
   recalibrates, judge comes back online). For conditions that may involve data
   corruption (holdout registry corrupted, lesson registry poisoned, tenant
   contamination), explicit operator intervention is required before returning
   to normal mode. Every recovery — automatic or manual — is logged with rationale.
4. **Freeze > corrupt**: if the system cannot determine whether results are reliable,
   it freezes the frontier rather than risks corrupting it with unreliable evaluations.

---

## 16. Cold Start Protocol

On first deployment, registries are empty, surrogates are untrained, and the lesson
base has no content. This section defines how to bootstrap.

### 16.1. Calibration burn-in (Phase A prerequisite)

Before the funnel can route candidates intelligently, the cheap surrogate models
(Level 1-2) need training signal from expensive evaluations.

**Protocol**:
1. Generate N=50-100 diverse candidates using random + structured variation.
2. Run ALL of them through full pipeline (Level 0 → Level 4), bypassing cheap-stage rejection.
3. Record complete traces, including failures.
4. Use these traces to:
   - Train initial cheap causal surrogate.
   - Train initial runtime/timeout predictor.
   - Seed the `LessonRegistry` with first failure patterns.
   - Establish initial `CorrelationTracker` baseline.
5. Only after burn-in: enable Level 1/2 rejection.

**Cost**: significant upfront compute investment. This is not waste —
it is the training data that makes the funnel possible.

### 16.2. Synthetic "dumb search" for lesson seeding

Complement burn-in with intentionally bad candidates:
1. Generate candidates with obvious flaws (budget violations, missing interventions, extreme parameters).
2. Run through pipeline to populate `LessonRegistry` with canonical failure patterns.
3. These become Level 1 screening rules immediately.

### 16.3. Sentinel candidates

Sentinel candidates serve two purposes:
1. **Calibration monitoring**: known-good candidates with small mutations, periodically
   injected into the funnel. If cheap stage kills them → surrogate drift → recalibration trigger.
2. **Regression detection**: known champions re-evaluated periodically. If scores degrade →
   data drift or infrastructure issue.

**Implementation**:
- Maintain a `SentinelSet` in `BenchmarkRegistry` (10-20 candidates).
- Inject 1-2 sentinels per every 20 regular candidates.
- Track sentinel pass rate as a meta-metric.
- Alert when sentinel pass rate drops below 90%.

---

## 17. Cross-Run Transfer Isolation

Phase D enables cross-run and cross-domain transfer of lessons, priors, and frontier
knowledge. This is powerful but dangerous — without isolation, transferred knowledge
becomes a source of silent contamination.

### 17.1. Isolation rules

| Transfer type | Isolation requirement |
|--------------|---------------------|
| **Lessons across runs (same domain)** | Allowed. Lesson cards carry `source_run_id` and `created_at`. Lessons older than TTL (configurable, default 90 days) are demoted to `low_confidence`. |
| **Lessons across domains** | Allowed only if domains share a common task family. Transferred lessons are tagged `trust_level=transferred` and carry lower weight in Level 1 screening. |
| **Lessons across tenants** | Forbidden by default. Requires explicit tenant-level opt-in. Transferred lessons are anonymized (no tenant-specific data). |
| **Priors across runs** | Allowed. Graph priors are CAS-pinned (§3.4.1) and carry provenance. |
| **Frontier reuse across domains** | Read-only. Cross-domain frontiers are used for seeding only, not for dominance comparison. |
| **Surrogate models across domains** | Forbidden. Surrogates are domain-specific. Cross-domain transfer requires full recalibration (cold start). |

### 17.2. Contamination prevention

1. **Provenance weighting**: lessons and priors from external sources carry a
   `provenance_weight` (0.0-1.0) that decays with distance from the current context
   (different domain, different tenant, older timestamp).
2. **Revalidation on transfer**: when a lesson is transferred to a new domain,
   it must pass a lightweight consistency check against the new domain's Level 0-1
   validators before entering the registry.
3. **Expiry and garbage collection**: lessons not accessed for > 2x TTL are archived.
   Lessons that have been contradicted by subsequent evidence are marked `invalidated`.
4. **Audit trail**: every lesson and prior carries full transfer chain
   (`origin_domain → current_domain`, `origin_tenant → current_tenant`).

---

## 18. Execution Phases

### Phase A — Funnel First (Foundation)

**Goal**: make expensive evaluation rare and valuable.

**Deliverables**:

| # | Deliverable | Module | Depends on |
|---|------------|--------|-----------|
| A.1 | `FunnelStage` interface extending `SearchStage` | `scientist.search.funnel` | — |
| A.2 | Level 0 static validator | `scientist.search.funnel` | A.1 |
| A.3 | Level 1 cheap heuristic stage + `CheapSignalVector` | `scientist.search.funnel` | A.1 |
| A.4 | Level 2 causal plausibility stage (wraps symbolic engine) | `scientist.search.funnel` | A.1 |
| A.5 | Level 3 medium-fidelity stage | `scientist.search.funnel` | A.1 |
| A.6 | `FunnelOrchestrator` (routes through Levels 0-6) | `scientist.search.funnel` | A.1-A.5 |
| A.7 | `UncertaintyEnvelope` and `UncertaintyType` data models | `scientist.search.uncertainty` | — |
| A.8 | `TypedFailureCard` data model | `scientist.search.failure_cards` | — |
| A.9 | `VOIScheduler` (initially simple: EI/cost ratio) | `scientist.search.voi_scheduler` | A.7 |
| A.10 | Extended `CorrelationTracker` with drift alerts | `scientist.search.stages` | — |
| A.11 | `LessonRegistry` (CAS-backed) | `scientist.search.lessons` | — |
| A.12 | `SentinelSet` and injection protocol | `scientist.search.sentinels` | A.11 |
| A.13 | Cold start burn-in script | `scientist.search.cold_start` | A.1-A.6 |
| A.14 | Calibration report (funnel health dashboard) | `scientist.search.calibration_report` | A.10-A.12 |

**Acceptance criteria**:
- False-negative rate on burn-in top candidates < 2%.
- Expensive-stage (Level 4) load reduced > 50% vs. no-funnel baseline.
- `CorrelationTracker` Spearman > 0.6 between Level 2 and Level 4 rankings.
- Sentinel pass rate > 95%.

**Expected outcome**: search becomes economically viable; timeout wall from benchmarks resolved.

### Phase B — Policy Design on Funnel

**Goal**: real multi-objective constrained policy optimization.

**Deliverables**:

| # | Deliverable | Module | Depends on |
|---|------------|--------|-----------|
| B.1 | `PolicyCandidateSchema` (rich IR) | `scientist.policy_design.schema` | — |
| B.2 | Objective stack (primary, hard constraints, secondary, penalties) | `scientist.policy_design.objectives` | — |
| B.3 | `ParetoRegistry` (extends existing `autotune.pareto`) | `scientist.search.pareto_registry` | — |
| B.4 | Judge Stack implementation (§5) | `scientist.search.judge_stack` | A.7, A.8 |
| B.5 | `DecisionReadinessContract` data model and evaluator | `scientist.search.readiness` | B.4 |
| B.6 | Policy Translator worker | `scientist.policy_design.translator` | B.5 |
| B.7 | Constraint Critic (wraps governance passes) | `scientist.policy_design.critic` | B.4 |
| B.8 | Scenario Adversary (bounded LLM worker) | `scientist.policy_design.adversary` | — |
| B.9 | Full output artifact bundle (§9.8, 12 artifacts) | `scientist.policy_design.output` | B.1-B.8 |
| B.10 | Hierarchical search (structure + parameter + narrative) | `scientist.policy_design.search` | B.1, B.2 |

**Acceptance criteria**:
- System finds policy improvements that survive hidden holdouts.
- Recommendations are multi-objective with visible frontier.
- Legal/equity gates fire correctly on adversarial test cases.
- Policy Brief is readable by non-technical reviewer.
- Decision Readiness Contract is correctly typed for all promoted artifacts.

### Phase C — Discovery (Algorithm Portfolio First)

**Goal**: robust graph learning that feeds useful priors to policy design.

**Deliverables**:

| # | Deliverable | Module | Depends on |
|---|------------|--------|-----------|
| C.1 | `GraphHypothesis` schema | `scientist.discovery.schema` | — |
| C.2 | Algorithm portfolio runner (3-4 families) | `scientist.discovery.portfolio` | C.1 |
| C.3 | Bootstrap stability layer | `scientist.discovery.stability` | C.1 |
| C.4 | Downstream causal utility judge | `scientist.discovery.utility_judge` | C.1, C.3 |
| C.5 | Evidence-weighted aggregator | `scientist.discovery.aggregator` | C.1-C.4 |
| C.6 | `GraphPriorBundle` output (contract to Layer B) | `scientist.discovery.priors` | C.5 |
| C.7 | Prior miner from `academic` stack | `scientist.discovery.prior_miner` | C.6 |
| C.8 | Discovery output bundle (§10.8, 11 artifacts) | `scientist.discovery.output` | C.1-C.7 |

**Acceptance criteria**:
- Multiple algorithmic families produce diverse hypotheses.
- Stability metrics computed for every edge.
- Downstream utility demonstrably affects graph ranking (SHD-worse but identification-better graph wins).
- Output preserves uncertainty honestly (disputed edges visible).
- `GraphPriorBundle` successfully consumed by Layer B.

### Phase D — Self-Improving Loops

**Goal**: loops learn across runs, domains, and tenants.

**Deliverables**:

| # | Deliverable | Module | Depends on |
|---|------------|--------|-----------|
| D.1 | Cross-run lesson transfer | `scientist.search.lessons` | A.11 |
| D.2 | Cross-domain frontier reuse | `scientist.search.pareto_registry` | B.3 |
| D.3 | Active disambiguation planner | `scientist.discovery.active` | C.5 |
| D.4 | Bounded discovery agent workers (Skeptic, Data Profiler) | `scientist.discovery.workers` | C.1-C.8 |
| D.5 | Adversarial meta-evaluation (platform attacks itself) | `scientist.search.adversarial` | all |
| D.6 | Full VOI scheduler with all four predictive models | `scientist.search.voi_scheduler` | A.9 |

**Acceptance criteria**:
- Lessons from Domain X measurably improve search speed in Domain Y.
- Active disambiguation planner recommends useful next experiments.
- Platform-level adversarial tests pass (sentinel injection, hidden holdout rotation, calibration drift detection).

---

## 19. SOTA Acceptance Criteria

The system achieves SOTA when ALL of the following hold simultaneously:

### 19.1. Funnel
1. False-negative rate on eventual top candidates < 2%, continuously measured.
2. Expensive-stage load reduced > 60%.
3. Medium-fidelity stage is production-grade with ASHA pruning.
4. Cheap-stage calibration drift is detected within 20 evaluations.
5. Sentinel candidates maintain > 95% pass rate.

### 19.2. Policy Design
1. Search is multi-objective and constraint-aware.
2. Pareto frontier preserved (never scalarized).
3. Recommendations survive hidden holdouts, scenario shifts, and refuters.
4. Legal/compliance gate is first-class (existing passes integrated into Judge Stack).
5. Final output includes Decision Readiness Contract and Policy Brief.
6. System explains why champion beats alternatives.

### 19.3. Discovery
1. Multiple algorithmic families orchestrated.
2. Priors explicit and auditable.
3. Confidence is bootstrapped and stability-based.
4. Judge uses downstream causal utility, not just graph similarity.
5. Outputs preserve ambiguity honestly.
6. `GraphPriorBundle` successfully feeds policy design.

### 19.4. Platform
1. Full artifact lineage via CAS.
2. Deterministic replay for promoted artifacts.
3. Champion/challenger governance with Judge Stack.
4. Hidden benchmarks with rotation.
5. Typed uncertainty envelopes on all confidence claims.
6. VOI-driven scheduling with exploration-exploitation balance.
7. Lesson memory with cross-run transfer and isolation rules.
8. Bounded compute budgets with observability.
9. Decision Readiness Contracts on all promoted artifacts.
10. No single-judge point of failure.
11. All architectural invariants (§12) enforced by code, not convention.
12. Artifact minimality rule (§13) applied — no unused artifact types.
13. Degraded mode hierarchy (§15) implemented and tested.
14. Cross-run transfer isolation (§17) enforced for multi-tenant deployments.
15. Anti-spin contract (§7.3.1) enforced by `TranslatorCompliancePass`.

---

## 20. Design Inspirations

These are **transferable architectural patterns**, not established best practices.
Many originate from recent research at arXiv/repository stage. Use the pattern, not the brand.

### Autonomous research patterns
1. **AI Scientist v2** — progressive agentic tree search + experiment manager. Pattern: tree search over structural decisions, not just parameter BO.
2. **GEPA** — full trace reflection + Pareto frontier + targeted mutations. Pattern: trace-aware learning > scalar reward learning.
3. **ADAS** — automated design of agentic systems. Pattern: meta-optimization of the search itself.
4. **Agent Laboratory** — LLM agents as research assistants. Pattern: bounded worker roles with clear division of labor.
5. **AI-Researcher / AgentRxiv / ClawTeam** — multi-agent collaboration. Pattern: shared memory, orthogonal research directions, benchmarked evaluator > social consensus.

### Benchmark discipline
6. **MLE-bench** — operational environment + grading scripts + hidden holdouts. Pattern: hidden evaluation is mandatory for any optimization loop.
7. **MLAgentBench** — benchmarking agents on real ML tasks. Pattern: agent capability measured on operational, not toy, environments.

### Causal methods
8. **CausalTune** — out-of-sample causal scoring + policy-value estimation. Pattern: causal estimators must be scored out-of-sample, not just in-sample.
9. **DoWhy** — refutation as part of causal workflow. Pattern: refutation is mandatory, not cosmetic.
10. **ETIA** — automated causal discovery pipeline. Pattern: automation of method selection with downstream utility.
11. **CausalAI / GIES** — priors + targeted discovery + interventional data. Pattern: prior knowledge is first-class input to discovery.

### Optimization infrastructure
12. **Optuna** — ask/tell + pruning + multi-objective. Pattern: async ask/tell interface for human-in-the-loop optimization.
13. **ASHA / HyperBand** — early stopping by fidelity. Pattern: multi-fidelity scheduling with principled promotion.
14. **Ray Tune** — distributed scheduling. Pattern: distributed execution backend for expensive evaluations.

### Safety
15. **MaMa** — game-theoretic adversarial safety. Pattern: system must defend against worst-case, not just average-case.

---

## Appendix A: Data Flow Diagram

```text
                    ┌──────────────┐
                    │ User Request │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Layer B:     │
                    │  Policy       │──────────────────────┐
                    │  Proposer     │                      │
                    └──────┬───────┘                      │
                           │ PolicyCandidateSchema        │ reads GraphPriorBundle
                    ┌──────▼───────┐               ┌─────▼──────┐
                    │  Layer A:     │               │  Layer C:   │
                    │  Funnel       │               │  Discovery  │
                    │  Orchestrator │               │  Portfolio  │
                    └──────┬───────┘               └─────┬──────┘
                           │                             │
              ┌────────────┼────────────┐                │ GraphHypothesis
              │            │            │                │
        ┌─────▼─┐    ┌────▼───┐  ┌────▼────┐     ┌────▼─────┐
        │ L0-L2 │    │ VOI    │  │  L3-L4  │     │ Stability│
        │ Cheap │    │Schedule│  │ Expensive│     │ + Utility│
        │ Stages│    │   r    │  │  Stages  │     │  Judge   │
        └───┬───┘    └────┬───┘  └────┬────┘     └────┬─────┘
            │             │           │                │
            │      ┌──────▼───────────▼──┐             │
            │      │    Level 5:          │             │
            │      │    Refutation +      │             │
            │      │    Governance        │             │
            │      └──────────┬──────────┘             │
            │                 │                         │
            │          ┌──────▼───────┐                │
            │          │  Judge Stack  │◄───────────────┘
            │          └──────┬───────┘
            │                 │ JudgeVerdict
            │          ┌──────▼───────┐
            │          │  Registries:  │
            └─────────▶│  Champion     │
      failure_cards    │  Pareto       │
      + lessons        │  Lesson       │
                       │  Benchmark    │
                       │  Discovery    │
                       └──────┬───────┘
                              │
                    ┌─────────▼─────────┐
                    │  Output Bundle:    │
                    │  Dossier + Brief + │
                    │  Readiness Contract│
                    └───────────────────┘
```

## Appendix B: Glossary

| Term | Definition |
|------|-----------|
| **Ask/Tell** | Async search interface where `ask()` proposes candidates and `tell()` receives evaluation results |
| **CAS** | Content-Addressable Store — immutable artifact storage with hash-based addressing |
| **CheapSignalVector** | Structured 10-dimensional evaluation from Level 1-2 stages |
| **Decision Readiness Contract** | Typed classification of what a promoted artifact may be used for |
| **Judge Stack** | Composite of 6 typed judges; promotion requires AND-composition |
| **Lesson Card** | Reusable failure pattern or success pattern stored in LessonRegistry |
| **Pareto Frontier** | Set of non-dominated candidates under multi-objective evaluation |
| **Sentinel Candidate** | Known-good candidate used to detect surrogate calibration drift |
| **UncertaintyEnvelope** | Typed uncertainty object with 6 dimensions (statistical, structural, transport, measurement, model, optimization) |
| **VOI** | Value of Information — expected reduction in uncertainty per unit compute |
