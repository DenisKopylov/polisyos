# PolicyOS Causal Engine — Research Track Handoff Template

Owner: `@foundry-owners`
Source of truth: `docs/reference/research-track-handoff-template.md`, `docs/plans/active/CAUSAL_ENGINE_RESEARCH_AGENDA.md`, and `docs/plans/active/CAUSAL_ENGINE_IMPLEMENTATION_PLAN.md`

> **Version**: 1.0
> **Date**: 2026-04-01
> **Scope**: All research tracks in `CAUSAL_ENGINE_RESEARCH_AGENDA.md`
> **Companion documents**: `CAUSAL_ENGINE_RESEARCH_AGENDA.md`, `CAUSAL_ENGINE_IMPLEMENTATION_PLAN.md`
>
> This template is the contractual bridge between academic research and PolicyOS engineering.
> It exists because "here's a theorem" is not a deliverable — a deliverable is a theorem
> with its conditions expressed as machine-checkable contract fields, its failure mode as
> a typed `NegativeCertificate`, its uncertainty as judge-readable metrics, and its
> promotion path as a concrete checklist against the `DecisionReadinessEvaluator`.
>
> The template has two parts. **Part I** is the system contract reference — read once,
> apply everywhere. **Part II** is the per-track specification — fill in one copy per task.

---

## PART I. System Contract Reference

> This section is invariant. Every researcher working on any track must understand it
> before writing a single line of math. The system speaks in contracts, not in papers.

---

### I.1. The Proof Kernel Output Hierarchy

Every research result that enters the system must eventually produce one of three primary artifacts.
Understanding which one your track produces determines the rest of the template.

```text
ProofBundle          — "This effect IS identifiable under conditions C"
BoundsBundle         — "This effect is not point-identified but lies in [L, U]"
NegativeCertificate  — "This effect is NOT identifiable; here is why and what to do next"
```

These are not mutually exclusive. A typical non-trivial result produces all three:
`NegativeCertificate` pointing to a `BoundsBundle` with a `recovery_plan` field.

---

### I.2. ProofBundle: Fields You Must Populate

```text
ProofBundle
├─ proof_status         : "identified" | "non_identified" | "oracle_needed"
│                          ← your theorem's conclusion
├─ proof_stratum        : "A0_trusted" | "A1_extended" | "A2_oracle_backed"
│                          ← epistemic confidence tier (see I.4)
├─ theorem_family       : str  — e.g. "proximal_id", "sigma_separation", "icp_contraction"
│                          ← name of your algorithm/theorem family
├─ completeness_regime  : "complete" | "sound_incomplete" | "heuristic_backed"
│                          ← does your proof cover all AST nodes or a subset?
├─ estimand_ast         : dict — parsed query representation
├─ proof_trace          : list[str] — human-readable steps of the proof
├─ assumptions          : list[str] — every assumption your theorem requires
├─ implementation_coverage : str — honest description of what is and isn't implemented
└─ negative_certificate_summary : str — required even in "identified" case
                                         (what would make this fail)
```

**What `proof_stratum` means in practice:**

| Stratum            | Assumption set                      | Proof type                          | System use                                |
| ------------------ | ----------------------------------- | ----------------------------------- | ----------------------------------------- |
| `A0_trusted`       | Minimal — SUTVA only                | Purely graph-theoretic              | Can gate deployment decisions             |
| `A1_extended`      | Moderate — do-calculus extensions   | Algorithm-backed (ID*, IDC*, σ-sep) | Simulation-ready, analyst advisory        |
| `A2_oracle_backed` | Strong — parametric or unverifiable | Oracle queries or sensitivity       | Research artifact; blocked from promotion |

Your theorem's conditions determine the stratum. If your proof requires an
unverifiable parametric model assumption, it is `A2_oracle_backed` and you must
say so — the system will not promote it past `RESEARCH_ARTIFACT` readiness.

---

### I.3. NegativeCertificate: The Constructive Refusal Contract

When your theorem shows something is NOT identifiable or NOT computable,
you must return a `NegativeCertificate` with these fields populated:

```text
NegativeCertificate
├─ blocking_type : BlockingType enum — pick the most specific:
│    HEDGE_STRUCTURE         — non-id due to Pearl-Bareinboim hedge
│    S_NODE_UNRESOLVED       — selection/context shift unresolvable
│    POSITIVITY_VIOLATION    — positivity assumption near-violated
│    SUPPORT_MISMATCH        — target distribution has no overlap with source
│    MISSING_DISTRIBUTION    — required conditional distribution unavailable
│    [new types may be added by your track — document them here]
│
├─ blocking_description  : str — one sentence: what failed and why
├─ technical_detail      : str — formal statement (can reference your theorem)
├─ constructive_message  : str — REQUIRED: what the analyst should do next
│
├─ required_distributions : list[DistributionRef]
│    — what data, if added, would enable identification
│
├─ suggested_experiments : list[SuggestedExperiment]
│    each has: required_variables, design_type, domain, description
│
├─ partial_bounds         : PartialIdentificationResult (optional)
│    — if you can't identify but CAN bound, attach bounds here
│
├─ recovery_plan          : RecoveryPlan — auto-populated from fallback chain;
│    your algorithm must feed the fallback chain correctly
│
└─ quantitative_diagnostics : dict[str, Any]
     — machine-readable metrics for the judge stack (see I.5)
     — every new metric your theorem introduces goes here
```

**The rule**: a `NegativeCertificate` without a `constructive_message` and without
`recovery_plan` is incomplete. Refusal is not a result — _constructive refusal_ is.

---

### I.4. BoundsBundle: Sharp vs. Approximate

```text
BoundsBundle
├─ estimand_type    : str — e.g. "ate", "att", "path_specific"
├─ lower_bound, upper_bound : float — the interval
├─ sharpness_status : "sharp" | "inner_approx" | "outer_approx" | "unknown"
│                      ← Track 2 exists precisely because most bounds are "unknown" here
├─ dual_certificate_ref : str | None
│                      ← if you prove sharpness, your dual witness goes here
├─ method_summaries : list[BoundsMethodSummary]
│    — one entry per bounds method your algorithm runs
└─ rescue_actions   : list[str] — what to try next when bounds are too wide
```

**Currently implemented bounds methods** (for reference, do not duplicate):
`MANSKI`, `LP_BALKE_PEARL`, `MTR_BOUNDS`, `MIV_BOUNDS`, `MTS_BOUNDS`,
`COPULA_BOUNDS`, `TAN_BOUNDS`, `INTERSECTION_BOUNDS`, `ROSENBAUM_SHARP`.

Your new bounds family must be added to this registry. Document its sharpness
conditions explicitly — `sharpness_status = "unknown"` is honest but weakens value.

---

### I.5. The Six Judges and What They Consume

The `JudgeStack` has six judges. Your algorithm's `quantitative_diagnostics` dict
must feed the relevant judges with machine-readable metrics.

| Judge             | Metrics it consumes from `quantitative_diagnostics`                                                            |
| ----------------- | -------------------------------------------------------------------------------------------------------------- |
| `structural`      | `graph_has_cycles`, `backdoor_count`, `confounder_coverage_fraction`, `hedge_forest_size`, `blocking_set_size` |
| `statistical`     | `confidence_interval_width`, `standard_error_estimate`, `effective_sample_size`, `n_obs`, `overlap_score`      |
| `robustness`      | `refutation_p_value_min`, `sensitivity_bounds_ratio`, `specification_sweep_variance`                           |
| `governance`      | `pii_flagged`, `equity_violation_count`, `fairness_gap`                                                        |
| `reproducibility` | `determinism_tier_value`, `seed_reproducible`, `code_review_passed`                                            |
| `compute`         | `estimated_runtime_seconds`, `memory_gb`, `parallelizable`                                                     |

**For new metrics your theorem introduces**: name them in the format
`{track_family}_{metric_name}` (e.g., `proximal_bridge_existence_score`,
`dp_noise_inflation_factor`, `regime_shift_mec_contraction_ratio`).
Add them to `JudgeThresholdRegistry` with maturity `"provisional"` and a
benchmark source reference.

---

### I.6. DataReadinessReport: The Execution Gate

Before your algorithm runs, the system executes a readiness preflight. Your
integration must declare what it needs:

```text
DataReadinessReport
├─ decision : "pass" | "warn" | "block" | "unknown"
│              ← your algorithm sets this based on its preconditions
├─ can_compile_estimation : bool
├─ can_run_estimation     : bool   ← if False, estimation is skipped entirely
├─ measurement_quality    : "known_good" | "proxy_only" | "unknown"
├─ positivity             : PositivityDiagnosticReport (if relevant)
└─ blocking_reasons       : list[str] — why blocked (if decision == "block")
```

**Your algorithm must declare its blockers**: if your theorem requires positivity,
a specific proxy structure, or a minimum number of regime shifts, you must
emit `decision = "block"` with a `blocking_reason` string explaining
the failed precondition. Never silently proceed on bad data.

---

### I.7. The Degradation Ladder

From highest confidence to lowest, the system uses:

```text
DecisionReadiness (6 tiers, descending):
┌─ DEPLOYMENT_READY     — all 6 judges pass; CI width ≤ 0.10σ; replicated evidence; senior human gate
├─ RECOMMENDATION_READY — all 6 judges pass; CI width ≤ 0.20σ; meta-analytic evidence; human gate
├─ SIMULATION_READY     — 4 judges (structural, statistical, robustness, reproducibility); CI ≤ 0.30σ
├─ EXTERNAL_BRIEFING    — 5 judges; CI width ≤ 0.50σ; human gate required
├─ ANALYST_ADVISORY     — 3 judges; CI ≤ 1.00σ; no human gate required
└─ RESEARCH_ARTIFACT    — 2 judges (structural, reproducibility); no CI requirement
```

Research-first items always start at `RESEARCH_ARTIFACT`.

Promotion to higher tiers is governed by `DecisionReadinessEvaluator`. Your
integration spec must declare the minimum tier it claims to support and the
specific judge+metric conditions that must pass to reach it.

**Hardcoded caps** — your artifact stays at `RESEARCH_ARTIFACT` if:

- `degradation_mode = "research_only"` is set in evidence metadata
- `not_for_decision_support = True` is set in `latent_governance`
- Your theorem operates at stratum `A2_oracle_backed`

---

### I.8. The Artifact Persistence Chain

```text
IdentificationResult
     ↓  materialize_to_proof_bundle()
ProofBundle  ──────────────────────────────→  persist_proof_bundle(store, bundle)
     ↓  compile_estimand(estimand_ast, ...)
ExecutorGraph
     ↓  estimate(executor_graph, data_dict)
CausalEffectReport (or None if data blocks)
     ↓  audit()
EvidenceBundle  ────────────────────────────→  persisted to artifact store
     │
     ├─ ProofBundle ref
     ├─ CausalEffectReport ref (or None)
     ├─ BoundsBundle ref (if fallback path)
     ├─ NegativeCertificate ref (if non-id)
     └─ DataReadinessReport ref
```

Your algorithm produces an `IdentificationResult`. The engine converts it to
a `ProofBundle` and feeds the rest of the chain. You are responsible only for
the `IdentificationResult` and for populating `quantitative_diagnostics` correctly.

---

---

## PART II. Research Task Specification

> Fill one copy of this section per Research Track (or per open problem within a track).
> Every field marked **[REQUIRED]** must be filled before work begins.
> Fields marked [on delivery] must be filled when submitting the result.

---

### II.0. Header Card

| Field                              | Value                                                                                  |
| ---------------------------------- | -------------------------------------------------------------------------------------- |
| **Track ID**                       | **[REQUIRED]** e.g. `T10.1` — Track 10, Problem 1                                      |
| **Track Name**                     | **[REQUIRED]** Full name from research agenda                                          |
| **Researcher(s)**                  | **[REQUIRED]**                                                                         |
| **Start date**                     |                                                                                        |
| **TTL (phases)**                   | **[REQUIRED]** Default: 3 phases. After TTL with no benchmark proxy → archived         |
| **Companion agenda section**       | **[REQUIRED]** Link to section in `CAUSAL_ENGINE_RESEARCH_AGENDA.md`                   |
| **Engineering integration target** | **[REQUIRED]** e.g. `B.4b`, `ProofBundle query language`, `Foundry discovery pipeline` |

---

### II.1. Layer Target Card

**[REQUIRED]** — Declare which layer(s) your result lives in.

| Layer                      | What it means                                                  | Typical artifacts                                                       |
| -------------------------- | -------------------------------------------------------------- | ----------------------------------------------------------------------- |
| **A — Proof Kernel**       | Identification conditions; certificates; graphical criteria    | `ProofBundle`, `NegativeCertificate`, new `BlockingType` variants       |
| **B — Execution**          | Estimators, compilers, readiness preflight, strategy selection | `CausalEffectReport`, `DataReadinessReport`, `ExecutorGraph` extensions |
| **C — Frontier Reasoners** | Novel numeric kernels; specialised inference engines           | New method entries in `CausalMethod` enum + estimator implementation    |

**My result lives in**: `[  ] Layer A   [  ] Layer B   [  ] Layer C   [  ] A+B   [  ] A+B+C`

**Rationale**: _(one sentence — why this layer and not another)_

---

### II.2. Current System Behavior (Baseline)

**[REQUIRED]** — What does the system do TODAY when it encounters this query/case?

```text
Current behavior:
  [ ] Blocks with NegativeCertificate(blocking_type=_______________)
  [ ] Falls back to BoundsBundle with sharpness_status="unknown"
  [ ] Returns RESEARCH_ARTIFACT with degradation_mode="research_only"
  [ ] Raises NotImplementedError → caught as NegativeCertificate(MISSING_DISTRIBUTION)
  [ ] Uses a weaker/conservative substitute: ___________________________
  [ ] Is not reached (query type not yet supported)
  [ ] Other: ___________________________

Current proof_stratum ceiling: A0 / A1 / A2 / not applicable

Current readiness ceiling: DEPLOYMENT_READY / RECOMMENDATION_READY / SIMULATION_READY /
                           EXTERNAL_BRIEFING / ANALYST_ADVISORY / RESEARCH_ARTIFACT / blocked
```

---

### II.3. The Gap: Why Research First

**[REQUIRED]** — Three mandatory sub-fields. Do not conflate them.

**3a. Theoretical gap** — What mathematical result does not yet exist or is not known to apply here?

> _Avoid "we don't have an implementation". The gap is always in the mathematics,
> not in the code. Describe exactly which theorem, characterization, or reduction is missing._

```text
Theoretical gap:
[Fill in]
```

**3b. Naive implementation risk** — Why can't we use a heuristic or approximation right now?

> _Name the specific failure mode. "It might not work" is not acceptable. The risk must be
> a concrete class of inputs on which the naive approach produces a false guarantee._

```text
Naive implementation would produce [false identified / false bounds / invalid certificate / ...]
on the following class of inputs: [describe the class]
Example: [provide a minimal 3-node graph or formula that illustrates the failure]
```

**3c. Scope lock** — What is OUT of scope for this track?

> _Explicitly list what adjacent problems are NOT being solved here._

```text
This track does NOT:
-
-
```

---

### II.4. Definition of Done: Deliverables Matrix

**[REQUIRED before work begins]** — Engineering cannot take unspecified deliverables.

#### Deliverable A: Mathematical Artifact

```text
Form: [ ] Theorem with conditions  [ ] Impossibility result + counterexample class
      [ ] Reduction to known problem  [ ] Algorithm with soundness proof

Statement form: [Fill in — use the form from the research agenda section]

Conditions must be:
  [ ] Machine-checkable (can be evaluated in polynomial time from the graph + data)
  [ ] Stated as sufficient conditions (not just necessary)
  [ ] Accompanied by a counterexample class for when they fail

If the result is an impossibility:
  Counterexample class: [describe the class; this goes to CounterexampleRegistry]
  What the system must do on inputs in this class: [block / fallback to bounds / ...]
```

#### Deliverable B: Contract Population Spec

> Specify EXACTLY which contract fields your theorem populates and with what values.
> Engineering will build the integration based on this specification.

**Target contract(s)**: _(pick from `ProofBundle`, `BoundsBundle`, `NegativeCertificate`,
`DataReadinessReport`, or name a new contract if needed)_

```python
# Fill in each field your result populates:

ProofBundle(
    proof_status        = "identified" | "non_identified",   # [your result determines this]
    proof_stratum       = "A0_trusted" | "A1_extended" | "A2_oracle_backed",
    theorem_family      = "[YOUR_THEOREM_NAME]",             # e.g. "proximal_id_v1"
    completeness_regime = "complete" | "sound_incomplete",
    proof_trace         = ["step 1: ...", "step 2: ..."],    # algorithm steps
    assumptions         = ["assumption 1", "assumption 2"],
    quantitative_diagnostics = {
        "[your_metric_1]": float,   # feeds judge_name=______
        "[your_metric_2]": float,   # feeds judge_name=______
    }
)

# If NegativeCertificate path:
NegativeCertificate(
    blocking_type       = BlockingType.[EXISTING | NEW_TYPE],
    blocking_description = "[one sentence]",
    constructive_message = "[what analyst should do]",
    quantitative_diagnostics = {
        "[your_metric]": ...,
    }
)

# If BoundsBundle path:
BoundsBundle(
    sharpness_status    = "sharp" | "inner_approx" | "outer_approx",
    dual_certificate_ref = "[path if sharp proof exists]",
    method_summaries    = [...],
)
```

**New contract fields (if any)**: _(list any fields that do not yet exist and must be added)_

| Contract | Field name | Type | Description |
| -------- | ---------- | ---- | ----------- |
|          |            |      |             |

**New BlockingType variants (if any)**:

| Name | Description | Recovery path |
| ---- | ----------- | ------------- |
|      |             |               |

**New JudgeThresholdRegistry entries**:

| Metric name | Judge | Direction | Provisional threshold | Rationale |
| ----------- | ----- | --------- | --------------------- | --------- |
|             |       |           |                       |           |

#### Deliverable C: Benchmark Proxy Kit

> **This is not optional.** A track with no benchmark proxy after 2 phases is archived.
> The proxy must exist before the theorem — it is how you know your theorem is worth proving.

**Gold Suite** — 2–3 synthetic cases where your theorem gives the exact correct answer:

```text
Case 1: [Name]
  Graph: [describe or ASCII-diagram]
  Query: [e.g., P(Y | do(X=1))]
  Expected output: [ProofBundle.proof_status=?, stratum=?, assumptions=?]
  Why this is the canonical positive case: [one sentence]

Case 2: [Name]
  Graph: [describe]
  Query: [...]
  Expected output: [NegativeCertificate with blocking_type=?, constructive_message=?]
  Why this is the canonical negative case (your theorem correctly blocks): [one sentence]

Case 3 (optional — edge case / stress test):
  Graph: [...]
  Query: [...]
  Expected output: [...]
```

**Counterexample class** — inputs on which your method MUST fail constructively:

```text
Class description: [e.g., "graphs where the bridge function does not satisfy completeness"]
Example instance: [one concrete graph]
Required system behavior: [must emit NegativeCertificate with blocking_type=X]
This is NOT acceptable: [the naive behavior you are replacing — e.g., "returning a ProofBundle
                          with proof_status=identified when conditions are not met"]
```

**Sentinel test** — one minimal case that would falsify a wrong implementation:

```text
If my theorem is correctly implemented, then on input [X], the system outputs [Y].
If instead the system outputs [Z], my implementation is wrong.
```

---

### II.5. Promotion Criteria

**[REQUIRED]** — Fill in before starting. This is the graduation contract with engineering.

```text
Initial state: FrontierSketch, max_readiness = PROOF_ONLY
               degradation_mode = "research_only"
               not_for_decision_support = True
```

#### Promotion to `RESEARCH_ARTIFACT` (minimum graduation)

Conditions:

```text
[ ] Theorem proved with all conditions stated in machine-checkable form
[ ] Gold Suite (Deliverable C) passes on reference implementation
[ ] CounterexampleRegistry entry created (if impossibility result)
[ ] All new contract fields added to Pydantic schemas
[ ] proof_stratum declared and justified
```

**Promotion to `ANALYST_ADVISORY`** (first real-world use)

Additional conditions:

```text
[ ] judge.structural passes on Gold Suite graphs
[ ] judge.reproducibility passes (seed-reproducible algorithm)
[ ] Benchmark proxy evaluated on _____ real-world instances
[ ] Human peer review from team: _____________________
```

**Promotion to `SIMULATION_READY`** (integration with simulation layer)

Additional conditions:

```text
[ ] judge.statistical passes: CI width ≤ 0.30σ on test suite
[ ] judge.robustness passes: refutation_p_value_min > 0.05
[ ] Hidden holdout suite passes: _____ instances without regression
[ ] Integration test with [Layer A / B / C target] passes
```

**Maximum claimed tier**: _(circle one — be honest)_
`DEPLOYMENT_READY / RECOMMENDATION_READY / SIMULATION_READY / EXTERNAL_BRIEFING / ANALYST_ADVISORY / RESEARCH_ARTIFACT`

**Justification for ceiling**: _(why it cannot go higher with current assumptions)_

---

### II.6. Fallback Specification

**[REQUIRED]** — The system must always have a defined behavior when your method fails.

```text
Timeout (algorithm exceeds compute budget):
  → System falls back to: [e.g., "BoundsBundle with sharpness_status='unknown'
     using MANSKI bounds as outer approximation"]
  → NegativeCertificate.constructive_message: [what analyst is told]

Preconditions not met (DataReadinessReport.decision = "block"):
  → blocking_reason emitted: "[precise reason string]"
  → System falls back to: [e.g., "standard identification on observed graph ignoring proxies"]
  → Analyst is told: [...]

Conditions of your theorem fail (neither proof nor hard block):
  → System returns: [ ] NegativeCertificate only
                    [ ] NegativeCertificate + BoundsBundle
                    [ ] NegativeCertificate + RecoveryPlan
  → Lowest valid stratum in this case: A0 / A1 / A2
  → Readiness ceiling in this case: [...]

Parallel track failure (a track this depends on is archived):
  → This track [  ] can continue independently
                [  ] must be paused — depends on: [track ID]
```

---

### II.7. Integration Surface Checklist

> Check every item that applies. Engineering will verify each checked item at handoff.

**Schema changes:**

```text
[ ] New Pydantic model added (name: _________________________)
[ ] New field added to existing model (model: _______, field: _______)
[ ] New enum value in BlockingType (value: _________________________)
[ ] New enum value in CausalMethod (value: ________________________)
[ ] New entry in JudgeThresholdRegistry (metric: ___________________)
[ ] New schema snapshot in schemas/snapshots/ir/ (file: ____________)
```

**Algorithm changes:**

```text
[ ] New identification algorithm (class/function: ___________________)
[ ] Extension to existing algorithm (algorithm: _____________________)
[ ] New bounds method (name: _____________________________________)
[ ] New estimator backend (name: __________________________________)
[ ] New pre-flight check in DataReadinessReport builder (check: _____)
```

**Test coverage:**

```text
[ ] Gold Suite cases added to tests/unit/foundry/methods/catalog/causal/
[ ] Counterexample cases added to counterexample library
[ ] Sentinel test added (file: ______________________________________)
[ ] Readiness promotion test added (tests/unit/scientist/search/)
[ ] Integration test with [target layer] (file: _____________________)
```

**Documentation:**

```text
[ ] Research agenda entry updated with result status
[ ] proof_stratum and completeness_regime justified in inline comments
[ ] Assumptions list matches the theorem's stated conditions exactly
[ ] FrontierSketch metadata block added to implementation file
```

---

### II.8. Research Economics Self-Assessment

> Fill in before starting. Used for budget allocation decisions.

| Dimension                                | Self-assessment                         | Justification |
| ---------------------------------------- | --------------------------------------- | ------------- |
| **Moat depth**                           | very high / high / medium-high / medium |               |
| **Policy relevance**                     | very high / high / medium               |               |
| **Research difficulty**                  | very high / high / medium               |               |
| **Dependency on other tracks**           | none / soft / hard                      | list tracks:  |
| **Unblocks other tracks**                | list track IDs                          |               |
| **Estimate: phases to benchmark proxy**  |                                         |               |
| **Estimate: phases to ANALYST_ADVISORY** |                                         |               |

**Kill condition**: _(describe the mathematical result or empirical finding that would
cause you to close this track — what would you need to discover to stop working on it?)_

```text
This track should be killed if: [describe]
The counterexample that would trigger closure looks like: [describe]
```

---

### II.9. Parallel Track Interaction Map

> Required if your track interacts with other open tracks.

```text
This track USES results from:
  Track ___: [what result is needed and at what promotion tier]
  Track ___: [...]

This track FEEDS results to:
  Track ___: [what your result enables for that track]
  Track ___: [...]

Compound effect (if both this and Track ___ complete):
  [describe the emergent capability that neither track can produce alone]
```

---

### II.10. Submission Checklist

> Complete before handing off to engineering for integration review.

```text
MATHEMATICAL ARTIFACTS
  [ ] Theorem statement with all conditions in machine-checkable form
  [ ] Proof (or proof sketch if full proof is in external paper)
  [ ] Counterexample class for failure mode
  [ ] Reference(s): paper, preprint, or internal document ID

ENGINEERING ARTIFACTS
  [ ] Contract Population Spec (II.4.B) fully filled
  [ ] All new schema fields defined and typed
  [ ] Benchmark Proxy Kit (II.4.C) implemented and passing
  [ ] Fallback specification (II.6) implemented

GOVERNANCE ARTIFACTS
  [ ] Research agenda entry updated (status: proved / partial / archived)
  [ ] FrontierSketch metadata block in implementation:
        max_readiness = PROOF_ONLY
        ttl_phases = [number]
        required_for_promotion = [list from II.5]
  [ ] Kill condition documented in II.8

REVIEW GATES
  [ ] Self-review against Gold Suite and Counterexamples
  [ ] Peer review: [name]
  [ ] Engineering review: [name]
  [ ] Readiness sign-off: [name]
```

---

## Appendix A: FrontierSketch Metadata Block Template

Add this block to the top of every implementation file for a research-first feature:

```python
# ============================================================
# FRONTIER SKETCH — RESEARCH-FIRST FEATURE
# ============================================================
# Track ID       : [e.g., T10.1]
# Track name     : [full name]
# max_readiness  : PROOF_ONLY
# ttl_phases     : [number]
# proof_stratum  : [A0_trusted | A1_extended | A2_oracle_backed]
# theorem_family : [theorem name]
# Theorem        : [one-sentence statement of the key result]
# Conditions     : [list the machine-checkable conditions]
# Assumptions    : [list the assumptions your theorem requires]
# Fallback       : [what this returns when conditions fail]
# Promotion gate : [what must pass before this becomes ANALYST_ADVISORY]
# References     : [paper DOI or internal doc]
# ============================================================
# NOT FOR DECISION SUPPORT — degradation_mode="research_only"
# This artifact does not influence production recommendations
# until required_for_promotion checklist is complete.
# ============================================================
```

---

## Appendix B: Common Failure Modes in Research Integration

> These are the most common mistakes in past track handoffs. Check against them.

**1. Stratum inflation** — claiming `A0_trusted` for a result that requires parametric
assumptions. The system will not promote it, and the false claim wastes integration budget.
_Check_: does your theorem work with SUTVA only? If not, it is not `A0`.

**2. Missing constructive message** — returning `NegativeCertificate` without a
`constructive_message`. The system accepts it but the analyst is blocked with no guidance.
_Check_: every code path that produces a NegativeCertificate must have a non-empty
`constructive_message` that names the specific data or assumption that would resolve it.

**3. Condition mismatch** — the theorem conditions in the paper differ from the conditions
checked in `DataReadinessReport`. The proof is valid but the implementation applies it to
inputs that don't satisfy its conditions.
_Check_: print `assumptions` from your `ProofBundle` and verify each one maps to a
specific check in the DataReadiness preflight.

**4. Sharpness overclaim** — setting `sharpness_status = "sharp"` without a dual certificate.
The downstream `BoundJudge` will degrade this to `"unknown"` automatically, but the
discrepancy creates a confusing audit trail.
_Check_: if you claim sharp, store the dual witness in `dual_certificate_ref`.

**5. No fallback for compute timeout** — the algorithm runs indefinitely on adversarial inputs.
The compute judge will kill it and the system returns an untyped error.
_Check_: every algorithm must have an explicit `max_runtime_seconds` parameter and a
defined fallback BoundsBundle when the budget is exceeded.

**6. Benchmark proxy invented post-hoc** — the Gold Suite is designed to make the
implementation look good, not to test it. The Hidden Holdout evaluation will catch this.
_Check_: the Gold Suite should be designed from the theorem's conditions, not from the
implementation's behavior.

---

## Appendix C: Layer Placement Decision Tree

```text
Is your result about WHEN an effect is identifiable (new conditions, new certificates)?
  └─ YES → Layer A (Proof Kernel)

Is your result about HOW WELL an effect can be estimated (new estimator, new efficiency bound)?
  └─ YES → Layer B (Execution) or Layer C (Frontier Reasoners)

Does it require a new numeric kernel (JAX, GPU-accelerated, specialized solver)?
  └─ YES → Layer C (Frontier Reasoners)

Does it extend the QUERY LANGUAGE (new intervention types, new estimand classes)?
  └─ YES → Layer A + Layer B (both need updating)

Does it change the FALLBACK BEHAVIOR of an existing mechanism?
  └─ YES → Layer A (certificate) + Layer B (strategy selection)

Does it add a new GOVERNANCE CHECK or readiness gate?
  └─ YES → Layer B (DataReadinessReport builder) + judge stack entry
```

---

End of template. Questions about system contracts: refer to `CAUSAL_ENGINE_ARCHITECTURE.md`.
Questions about implementation scope: refer to `CAUSAL_ENGINE_IMPLEMENTATION_PLAN.md`.
Questions about open problems: refer to `CAUSAL_ENGINE_RESEARCH_AGENDA.md`.
