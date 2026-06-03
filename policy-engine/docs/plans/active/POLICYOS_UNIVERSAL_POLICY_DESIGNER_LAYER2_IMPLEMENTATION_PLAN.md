---
title: PolicyOS Universal Policy Designer (Layer-2, B-on-A) Implementation Plan
status: active-draft
owner: team-policyos-runtime
created: 2026-05-30
revised: 2026-05-30 (hardened: S0 readiness gate, dependency DAG, per-cell closure contract, early fail-closed blind-spots)
source_design_doc: ../../system-design-decisions/universal-policy-design-target-architecture-and-gap.md
governed_inventory: ../../../architecture/policy_design_case/cluster_ownership_map.toml
capability_ratchet: ../../../architecture/policy_design_case/capability_reality_report.json
failure_patterns: ../../reference/policy-design-case-failure-patterns.md
extends_plans:
  - ./POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md   # W0-W12 built A (the grounding backbone)
  - ./POLICYOS_POLICY_EVIDENCE_CAPABILITY_GRAPH_PLAN.md              # ADR-0174 capability graph
adr: ../../adr/0174-policy-evidence-capability-graph.md
scope:
  - layer2-generative-designer
  - vertical-slice-execution
  - b-on-a-shadow-first
  - cluster-map-burndown
  - anti-p13-gravity-well
---

# PolicyOS Universal Policy Designer (Layer-2, B-on-A) Implementation Plan

This plan implements the architecture in
`docs/system-design-decisions/universal-policy-design-target-architecture-and-gap.md`
(D0-D4 plus the Unifying Abstractions). It builds **B** (the generative
designer) on top of **A** (the grounding/authority backbone W0-W12 shipped).
Read the design doc first; this plan does not re-derive it.

## Read This Before Anything Else

Three rules shape everything below.

1. **A slice is not the system.** The first B slice is **not** "the universal
   designer." Shipping the MVP search loop and calling the ambition complete is
   the exact mistake that produced "Policy Design *Case*" instead of "Policy
   *Design*." The plan is done only when the **Ambition Map** is fully realized
   and the universality assurance battery (S14) passes per-axis. After the
   minimal slice closes, start the next, then the next, through the whole
   sequence.

2. **Do not rebuild the P13 gravity well — at runtime or in this plan.** A slice
   introduces only the artifacts it needs and prefers wiring a Unifying
   Abstraction over a new one-off. The heavy machinery (controlled vocabulary,
   artifact traceability, open-cell closure matrix, floor governance, corpus
   partition, validation matrix) lives **once in S0**; per-slice entries stay
   terse and reference S0.

3. **W12 green ≠ Layer-2 readiness.** `capability_reality_report.json` is green
   (62/63 implemented, 0 open debt). That is the **A** ratchet. Layer-2 readiness
   is a **different** ratchet: `cluster_ownership_map.toml`, currently **17 of 27
   cells open**. Plan progress is the cluster-map burn-down, never the W12 green.

## Execution Doctrine (every slice obeys these)

- **Vertical, with a full closure contract.** Each slice carries one capability
  end-to-end and must satisfy the per-cell closure contract, not just "a visible
  effect":
  - **Producer artifact** (the typed thing produced),
  - **Persisted artifact/event** (what is stored/emitted),
  - **Bridge + consumer** (who consumes it in the design loop),
  - **Surface** (PUBLIC/REVIEWER/EXPERT/MACHINE projection — P03; "internal
    effect" is not a surface),
  - **Semantic test** (P10 adequacy, not field presence),
  - **Negative control** (the laundering the cell must block),
  - **Acceptance signal** (the map cell's `acceptance_signal`),
  - **Ratchet/map delta** (which cell moved to which state).
- **Shadow until A.** Every B output is `shadow`/`advisory` with no rollout
  authority until A grounds it and the promotion gate (D3.8) passes. Generation
  never satisfies an authority slot (ADR-0174, P15).
- **A leads B.** Verifier/firewall completeness for an envelope region is
  repaired before B is promoted there. Adversarial-against-A is a standing
  obligation; new search power (S2/S4/S5/S10) raises it.
- **Reuse the status lattice.** No parallel status system (anti-P04). New
  statuses define mixed-outcome composition with the existing lattice (D3.7).
- **Replay integrity.** Index/acquisition/learning deltas never mutate
  closed-case replay (ADR-0174 C2).
- **Honest objective.** Optimize calibration/honesty/reuse/validated envelope
  revision, never `useful_design_rate`. The envelope may shrink.

**Dependency gate (not a linear gate).** Slices advance on a **dependency DAG**,
not "finish N before N+1." A slice may start once its named prerequisites close
their cells and pass their tests. The critical path is sequential; off-path
slices parallelize. (See S0 for the DAG.) A slice "closes" only when its full
closure contract holds and the cluster-map validator stays green.

**Execution granularity (roadmap vs task plans).** This document is the
**roadmap**: strategy, sequencing, doctrine, gates, and the per-slice *closure
contract*. It is **not** the coding spec. When a slice reaches the front of the
DAG, expand its closure contract into a separate **executable task plan**
(`docs/plans/active/layer2-slices/S{N}-*.md`) with exact files, typed
artifacts/modules, exact test files + names (semantic and negative-control,
written **red-first**), exact validation commands + expected output, and the
precise cell -> state delta. Write task plans **just-in-time** (when prereqs
close), not upfront; shared contracts are defined once in S0 and referenced,
never redefined. Keeping the two altitudes separate is itself the anti-P13
discipline — detailing everything here would balloon past ~10k lines and rot on
contact with code.

## Controlled Vocabulary (fixes label drift)

| Kind | Examples | Rule |
| --- | --- | --- |
| Runtime enum | `publish_with_limitation`, `selected_proxy_with_limitation`, `blocked_construct_not_observed` | machine status; use underscores |
| Expert/adjudication label | `publish-with-limitation`, `semantic_pass`, `false_pass` | corpus gold label; use hyphens |
| Ratchet state | `implemented`, `implemented_but_not_orchestrated`, `bridge_missing`, `producer_missing`, `contract_only`, `surface_missing`, `surface_out_of_scope` | only these in cells |
| Maturity transition | e.g. `implemented_but_not_orchestrated + bridge_missing -> implemented` | never invent shorthand like "impl-not-closed" |

## Proving Ground

The 13 W12 real_producer cases are the standing proving ground
(`runtime_useful_design_rate = 0/13`; 9 expert `publish-with-limitation`, 3
`semantic_pass`, 1 `false_pass`). The honest target is to convert these into
typed counterexamples, valid refinement decisions, robust/limited designs,
acquisition plans, or honest abstentions — **without weakening floors**.

---

## S0 — D5 Readiness / Narrow Waist (gate before any B slice)

S0 is not a feature; it is the readiness gate the design doc requires before a
Layer-2 implementation plan executes (continue cluster-ownership SOP, freeze the
seed envelope, fix the narrow waist). No B slice (S2+) starts until S0's
artifacts are frozen and owned.

S0 freezes, as committed artifacts under `architecture/policy_design_case/`:

1. **`MinimalSeedManifest`** — the algebra *generators*, not products: governed
   facet primitives, instrument-modality primitives, projection primitives, and
   the launch A-firewalls. Plus the budgets (compute/acquisition/expert-time/
   human-attention/legal-access) and the principal-set explore/exploit dial.
2. **`DesignRecord` v0 schema** — the narrow-waist, replay-frozen,
   authority-bearing object that S2 starts writing immediately (candidate,
   counterexample, refinement, ledger refs, axis-position vector, authority
   boundary, projection status). S9 matures projection/lowering over it; it is
   **not** introduced late. Its canonical code home is neutral `polisyos.pdc`,
   not B-side `scientist.policy_design`, because A-side grounding and Runtime
   closeout consume the matured record.
3. **Dependency DAG** — the slice graph below, marking critical path and each
   off-path slice's prerequisites.
4. **Slice -> open-cell matrix** — every one of the 17 open cells assigned to a
   slice, so none is dropped or hidden in a too-broad slice.
5. **Floor governance table** — for every `above floor` metric: metric -> floor
   owner -> floor artifact (governed config) -> revision rule. "Above floor"
   without this is not acceptable for promotion.
6. **Artifact traceability table** — D2.2 artifact -> slice -> maturity, so the
   architecture's named artifacts (AxisPositionDeclaration, AxisFirewallStatus,
   CertifiedOperationEnvelope, HonestAbstentionReceipt,
   ComputationalTractabilityBudget, KnowledgeGovernanceThroughputLedger,
   SubstrateCoverageSnapshot, etc.) are all accounted for.
7. **Corpus partition** — `dev_regression_corpus` (extensible) vs
   `sealed_universality_battery` (frozen, separate fixture path, freeze hash, CI
   access check, owner; the system never sees it in development — S14 integrity).
8. **First proving case** — pinned to the **Ukrainian MSME credit constructs**
   (`credit_program_enrollment`, `firm_survival`, `regional_displacement_pressure`,
   `credit_access`, `fiscal_burden_per_beneficiary`; D2.10), so S3 repairs the
   real W12 failure mode instead of demonstrating a convenient case.
9. **Shared cross-cutting contracts (skeletons, not mid-sequence births).**
   Establish the Unifying Abstractions here so later slices consume, not birth,
   them: `ValueOfInformationEstimate` (one currency for S2 refinement, S3
   acquisition, S7 attention, S12 allocation), the `GovernanceDecisionClass`
   registry (`a_spec_gap` already needs it in S2; populated per slice), and the
   envelope contracts `AxisPositionDeclaration` / `AxisFirewallStatus` /
   `CertifiedOperationEnvelope` carried by every `DesignRecord` from S2.
10. **Cell maturity qualifier.** Define `maturity in {fail_closed, predictive}`
   as a documented cell qualification — **not** a new ratchet state (anti-P04).
   A blind-spot cell is `implemented (maturity=fail_closed)` in S6 and
   `implemented (maturity=predictive)` in S11.
11. **Cell vs layer + full cell coverage.** The 27 `CLUSTER.axis` cells are the
   burn-down units; cross-cluster D1 capabilities (graded outcomes, control
   plane, acquisition loop, delegation, canonical record, prediction,
   post-deploy, battery) are *layers* with no single cell, tracked separately.
   The slice->open-cell matrix must assign **all 17 open cells** to a slice,
   including the easily-missed `KNOWLEDGE.calibration`,
   `KNOWLEDGE.ir_proof_carrying_analytics`,
   `CROSS_CUTTING.scientist_orchestration`, `INTERVENTION.scale_composition`,
   and `ACTOR.mandate_legitimacy`. `CROSS_CUTTING.method_infrastructure` is
   already `implemented` substrate and may be advanced by S11, but is not part
   of the open-17 closure matrix.

**Dependency DAG (critical path bold):**

```text
S0 ──▶ **S2** ──▶ **S3** ──▶ **S4** ──▶ **S5** ──▶ **S6** ──▶ **S7**
 │       │                                   │        │         │
 └▶ S1   └▶ S9(DesignRecord matures) ◀───────┘        │         └▶ S8
   (A-side prelude, parallel)                          └▶ S10 ◀──┘
S6 ──▶ S10(prediction) ; S6 ──▶ S11(rich blind-spot) ; S7+ ──▶ S12 ──▶ S13
S1.. ──▶ S14(battery, growing track; gates any "universal" claim)
```

- **Cells closed:** none yet (readiness artifacts only); sets the baseline
  `open_cell_count = 17`.
- **Done when:** all 11 S0 readiness items above are committed, owned, and
  referenced by the validator; the slice->cell matrix covers all 17 open cells.

### S0 deliverable — Artifact traceability (summary)

The committed S0 table carries `artifact -> slice -> maturity`. Summary index so
no named contract is lost at execution:

| Artifact(s) | Slice |
| --- | --- |
| `MinimalSeedManifest`, `ValueOfInformationEstimate`, `GovernanceDecisionClass`, `AxisPositionDeclaration`, `AxisFirewallStatus`, `CertifiedOperationEnvelope`, `DesignRecord` v0 schema | S0 |
| `DesignGrammarExpansion`, `ConstraintStoreSnapshot`, `CounterexampleRecord`, `RefinementDecision`, `SearchLedger`, `ClusterInterfaceContract`, `ClusterHandoffRecord` | S2 |
| `FacetPrimitiveRegistry`, `ConstructExpression`, `ConstructDemandLedger`, `ConstructOntologyDelta`, `CapabilityBindingResult`, `SubstrateCoverageSnapshot`, `AcquisitionTaskRecord`, `SourceContract`, `RerunClosureReceipt`, `HonestAbstentionReceipt` | S3 |
| `EpistemicRegimeClaim`, `CommitmentProfileRecord` (reversibility/stakes) | S4 |
| `CouplingGraph`, `CouplingRegimeClassification`, `DecompositionResult`, `RecursiveDesignGraph`, `DesignInterfaceContract`, `SystemDynamicsRequirement`, `CompositionReceipt`, `ComputationalTractabilityBudget` | S5 |
| `CapacityFeasibilityRecord`, `MandateLegitimacyRecord`, `MeasurabilityAdequacyRecord`, `AggregationValidityRecord`, `StrategicResponseRecord`, `ClusterAuthorityDimensionRecord` | S6 |
| `DelegationContract`, `DecisionRightsMatrix`, `HumanDecisionRequest`, `HumanDecisionRecord` | S7 |
| `ParetoArchive`, value-choice provenance | S8 |
| projection grammar, faithfulness verifier, `DesignRecord` (mature) | S9 |
| `ForecastSupport`, `ForecastCalibrationRecord` | S10 |
| `ProofCarryingAnalyticsRecord`, calibration upgrades | S11 |
| `KnowledgeGovernanceThroughputLedger`, envelope-growth ledger | S12 |
| `DeploymentDossier`, `DivergenceRecord`, `LearningUpdateProposal`, `EnvelopeRevision`, `CertifiedEnvelopeDelta`, `AssuranceCaseDelta` | S13 |
| universality battery, per-axis scorecard, skeptic defeaters | S14 |

---

## Slice Sequence (overview)

Cells use **exact `CLUSTER.axis` IDs from `cluster_ownership_map.toml`** (27
total). Some D1 capabilities are cross-cluster *layers* with no single cell
(marked *layer:*); the S0 slice->open-cell matrix is the authoritative mapping
and per-cell ratchet_state comes from the map validator, not from this table.

| # | Slice | Cells closed (exact) + *layer* | Unifying abstraction | Path |
| --- | --- | --- | --- | --- |
| S1 | Graded outcomes (**A-side prelude**) | *layer:* graded-outcomes + status composition (no own cell) | composed status lattice | parallel A-side |
| S2 | Grammar + candidate + search loop + **DesignRecord v0** | `INTERVENTION.design_grammar`, `INTERVENTION.design_candidate`; *layer:* design-search control plane (non-acq) | `TypedDiagnosticRecord`, `SearchLedger`, narrow waist | critical |
| S3 | Concrete substrate + closed acquisition (**UA-MSME**) | *layer:* facet substrate + acquisition loop (advances already-`implemented` `KNOWLEDGE.substrate_coverage`) | ascending-cost + VOI | critical |
| S4 | Epistemic-regime classifier (A-owned) | `KNOWLEDGE.epistemic_regime`, `INTERVENTION.reversibility_lifecycle_stakes` | regime-as-claim, P16 | critical |
| S5 | Coupling + design-composition | `SYSTEM.connectivity_modularity`, `SYSTEM.dynamics_feedback`, `INTERVENTION.scale_composition` | prove-decompose-before-compose, P17 | critical |
| S6 | **Thin fail-closed blind-spot producers** | `OTHER_AGENTS.strategic_response`, `ACTOR.state_capacity_feasibility`, `ACTOR.mandate_legitimacy`, `SYSTEM.measurability`, `SYSTEM.subject_granularity` (`maturity=fail_closed`) | P18/P19/P21/P22/P24 | critical |
| S7 | Operating model / delegation (mandate-backed) | *layer:* delegation (no own cell; consumes `ACTOR.mandate_legitimacy`) | `GovernanceDecisionClass` + `DecisionRightsMatrix` | critical |
| S8 | Normative firewall + value-choice + Pareto | `ACTOR.value_choice_provenance` | normative firewall, P20 | off-path |
| S9 | Canonical DesignRecord matured + projection/lowering | `DESIGNER_ITSELF.closeout_projection_ratchet`; *layer:* canonical record + projection algebra | faithfulness verifier reuse | off-path |
| S10 | Outcome prediction + welfare comparison | *layer:* outcome prediction (B; no own cell) | `ForecastSupport` | off-path (after S6) |
| S11 | Rich blind-spot models + knowledge cells | `KNOWLEDGE.calibration`, `KNOWLEDGE.ir_proof_carrying_analytics`; advances already-`implemented` `CROSS_CUTTING.method_infrastructure`; S6 cells `maturity=predictive` | — | off-path |
| S12 | Cold-start + resource economics | `DESIGNER_ITSELF.envelope_growth` | one VOI currency, reflexive self-design | off-path |
| S13 | Post-deploy accountability + learning | `DESIGNER_ITSELF.envelope_growth` (shrink/expand); *layer:* post-deploy accountability | `TypedDiagnosticRecord` (post-deploy), `AssuranceCaseDelta` | off-path |
| S14 | Universality assurance battery | `DESIGNER_ITSELF.evaluation_corpus`; *layer:* universality battery | faithfulness verifier reuse | gate to "universal" |

`CROSS_CUTTING.scientist_orchestration` is split across S2 (generation handoff)
and S7 (orchestration), never assigned wholesale (P12). Cells already at
`implemented` (e.g. `SYSTEM.domain_data`, `KNOWLEDGE.substrate_coverage`,
`DESIGNER_ITSELF.evaluation_corpus`) are *advanced as layers* by their slice, not
re-closed.

---

## Per-Slice Detail

Template fields: Goal · Prereqs · Adds (minimal) · Not yet (fence) · Closure
contract (producer/persisted/bridge+consumer/**surface**/semantic/negative) ·
Firewalls · Cells · Promotion · Floor (owner/artifact) · Done when.

### S1 — Graded Outcomes (A-side prelude, not the start of B)
- **Goal:** route partial/proxy evidence to `publish_with_limitation` instead of
  hard `typed_blocker` at research/governed; production stays strict. This is an
  **A-side** improvement and may run in parallel; it does not start B-D5.
- **Prereqs:** none.
- **Adds:** composition policy + closeout downgrade routing; D3.7 mixed-status.
- **Not yet:** no generation, substrate, or regime classifier.
- **Closure:** producer = composition policy; persisted = closeout downgrade;
  bridge/consumer = closeout reader -> projection; **surface** = limitation
  visible in PUBLIC/REVIEWER/EXPERT projections; semantic = the 9 expert
  `publish-with-limitation` cases route to limitation; negative = fabricated
  limitation with no proxy evidence is rejected; production blocks all 13.
- **Firewalls:** ADR-0174 production strictness; no proxy-as-production leakage.
- **Cells:** `graded outcomes` (🟡 -> implemented).
- **Promotion:** governed only.
- **Floor:** none (behavioral, not thresholded).
- **Done when:** governed posture shows limitations for the 9 cases;
  closeout_honesty stays 1.0; production rate unchanged.

### S2 — Grammar + Candidate + Search Loop + DesignRecord v0  (true start of B)
- **Goal:** prove "designer, not evaluator" on **one** case in shadow:
  grammar-derived candidate -> A-verify -> `CounterexampleRecord` -> valid
  `RefinementDecision`, written into a minimal `DesignRecord` v0 and a replayable
  `SearchLedger`.
- **Prereqs:** S0.
- **Adds (minimal):** `DesignGrammarExpansion` + grammar-derivation ledger
  feeding `DesignCandidate` (grammar **before** candidate — anti-P15);
  `ConstraintStoreSnapshot`; `CounterexampleRecord` (six classes, design-time
  `TypedDiagnosticRecord`); simple `RefinementPolicy`; `SearchLedger`;
  `DesignRecord` v0 as the audit/projection home.
- **Not yet:** no Pareto, multi-fidelity, DAPP, or real substrate. **Acquisition
  branch is explicitly `bridge_missing` until S3** — S2 closes the
  *non-acquisition shadow path only*; do not mark the acquire branch
  implemented.
- **Closure:** producer = grammar+candidate+counterexample+refinement; persisted
  = `DesignRecord` v0 + `SearchLedger`; bridge/consumer = refinement policy
  consumes counterexamples; **surface** = MACHINE replay + REVIEWER search-trace
  projection; semantic = one case runs the full loop, replay deterministic;
  negative = `a_spec_gap` cannot be self-classified by the loop (routes to
  governance), a blocked candidate cannot be retried into a pass.
- **Firewalls:** P15 (LLM stays candidate), P25 (search-control laundering),
  governance-owned `a_spec_gap`, P12 (scientist generation handoff typed).
- **Cells:** `INTERVENTION.design_grammar`, `INTERVENTION.design_candidate`;
  *layer:* design-search control plane (non-acquisition path). The control plane
  **reuses the cluster-map handshake edges** (`publishes`/`consumes`) as its
  blackboard read/write contracts — not a parallel B architecture (design doc
  D3.2). Generation handoff is typed via `ClusterHandoffRecord` (P12).
- **Promotion:** shadow only.
- **Floor:** counterexample-conversion = 100% of failed candidates typed (owner:
  runtime-quality; artifact: governed config).
- **Done when:** one case runs the full loop with deterministic replay; the
  `a_spec_gap` and no-retry negative controls fail closed; `DesignRecord` v0
  exists and projects to MACHINE/REVIEWER.

### S3 — Concrete Substrate + Closed Acquisition Loop (Ukrainian MSME)
- **Goal:** repair the real W12 failure mode: ground the **Ukrainian MSME credit
  constructs** (D2.10) by closing the acquisition loop, making S2's acquire
  branch real.
- **Prereqs:** S0, S2.
- **Adds:** `FacetPrimitiveRegistry`, `ConstructExpression`,
  `ConstructDemandLedger`, resolver over compositional expressions; the explicit
  **D2.8 state machine**: `gap_detected -> eligibility_checked -> ranked_by_voi
  -> task_opened -> source_acquired -> source_contract_validated ->
  capability_index_updated -> rerun_started -> rerun_consumed_delta ->
  closed_as_binding | closed_as_limitation | closed_as_still_blocked`; automated
  `SourceDiscoveryCandidate` (Fabric connectors) with human fallback;
  `SourceContract` + index delta + `RerunClosureReceipt`; `SubstrateCoverageSnapshot`
  and bounded-abstention reporting (D2.7).
- **Not yet:** no scale/composition; coverage denominator is facet-space for the
  pinned constructs, not "any policy"; no new measure primitives beyond the
  pinned slice without governance.
- **Closure:** producer = source contract + index delta; persisted =
  capability-index delta + coverage snapshot; bridge/consumer = rerun grounding;
  **surface** = coverage/abstention dashboard (EXPERT/MACHINE); semantic = a
  pinned UA-MSME construct moves `construct_not_observed -> binding` via the loop;
  negative = scenario-family string cannot act as authority selector (C1);
  "task done" without rerun is not closure.
- **Firewalls:** P01/P06 (no scenario-family authority), P07/C2 (replay).
- **Cells:** `universal substrate` (partial), `acquisition loop`
  (`implemented_but_not_orchestrated + bridge_missing -> implemented`).
- **Promotion:** governed for the pinned constructs that ground.
- **Floor:** acquisition-closure-rate floor (owner: integration-spine; artifact:
  governed config).
- **Done when:** ≥1 pinned UA-MSME construct grounds through the full state
  machine with replay-safe deltas and a coverage snapshot — this proves the
  **acquisition/facet-governance loop closes** (the mechanism), not the whole
  UA-MSME set. Grounding the remaining pinned constructs is a **staged
  follow-up** tracked in the slice->cell matrix, not required for S3 done.

### S4 — Epistemic-Regime Classifier (A-owned)
- **Goal:** per-claim risk/uncertainty/ambiguity/ignorance as an A-owned claim;
  regime selects design strategy and evidence rules. Also lands the thin
  `reversibility/lifecycle/stakes` axis fields used by regime strategy.
- **Prereqs:** S3 (needs substrate-coverage signal).
- **Adds:** `EpistemicRegimeClaim` over Scholar contested/boundary seeds + S3
  coverage; P16; regime-conditional search strategy; minimal
  reversibility/stakes declaration on `DesignCandidate`.
- **Not yet:** regime is per-claim, not yet composed across a portfolio (S5).
- **Closure:** producer = regime claim; persisted = per-claim regime on the
  `DesignRecord`; bridge/consumer = S2 loop strategy selection; **surface** =
  regime declared in every audience projection; semantic = **classifier output
  is compared against expert regime labels; the W12 over-blocking hypothesis is
  confirmed or revised** (not assumed); negative = `false_risk_probe` and
  `false_precaution_probe` both fail.
- **Firewalls:** P16 (both directions); B may not regime-shop.
- **Cells:** `KNOWLEDGE.epistemic_regime`,
  `INTERVENTION.reversibility_lifecycle_stakes` (partial).
- **Promotion:** governed; ignorance outputs carry no outcome claims.
- **Floor:** regime accuracy + asymmetric false-risk penalty (owner:
  team-policy-design-research; artifact: governed config).
- **Done when:** regime accuracy ≥ floor vs expert labels; the 13-case regime
  result is recorded (confirmed/revised), not pre-assumed.

### S5 — Coupling Classifier + Design-Composition Algebra
- **Goal:** represent multi-part policies; compose authority only across
  modular/near-decomposable boundaries; entangled routes to system-level
  evidence or downgrade.
- **Prereqs:** S4.
- **Adds:** `CouplingGraph`, `CouplingRegimeClassification`, `DecompositionResult`;
  recursive `DesignCandidate`/`PolicyProgram`/`PolicyPortfolio`; cross-level
  authority (critical-path, not min-over-all, not average); `SystemDynamicsRequirement`;
  `ForecastSupport` system-effect scope; modularization-as-design-move (candidate
  only).
- **Not yet:** equilibrium prediction `simulation_only`/contested by default at
  large scale.
- **Closure:** producer = coupling classification + decomposition result;
  persisted = composition record on `DesignRecord`; bridge/consumer =
  compose-or-downgrade gate; **surface** = downgraded/contested nodes visible in
  audit/public projections; semantic = scale-composition corpus passes;
  negative = `false_modular_probe` (portfolio ignoring cross-module feedback)
  blocked; syntactic decomposition without coupling proof cannot compose.
- **Firewalls:** P17; A classifies coupling; default to more coupling.
- **Cells:** `SYSTEM.connectivity_modularity`, `SYSTEM.dynamics_feedback`,
  `INTERVENTION.scale_composition`. Named artifacts: `CompositionReceipt`,
  `DecompositionResult`, `CouplingGraph`.
- **Promotion:** governed modular/near-decomposable; entangled advisory/limited.
- **Floor:** coupling accuracy + asymmetric false-modular penalty (owner:
  runtime-quality; artifact: governed config).
- **Done when:** scale-composition corpus passes, including a refused entangled
  negative control.

### S6 — Thin Fail-Closed Blind-Spot Producers (A-completeness before B recommends)
- **Goal:** close the architecture's blind spots **as fail-closed firewalls
  before** B recommends (S8) or predicts (S10), so B cannot search inside an
  incomplete A-spec. Thin producers that **limit/block**, not rich models yet.
- **Prereqs:** S5.
- **Adds (thin, fail-closed):** ACTOR state-capacity/feasibility (P21), ACTOR
  minimal **mandate/legitimacy** (P22 — prerequisite for S7 non-shadow
  delegation), SYSTEM measurability-adequacy (P18), SYSTEM
  subject-granularity/aggregation (P19), OTHER_AGENTS strategic-response
  limiter (P24). Each emits its authority dimension into the C3 envelope and the
  S2 constraint store. Named records: `CapacityFeasibilityRecord`,
  `MandateLegitimacyRecord`, `MeasurabilityAdequacyRecord`,
  `AggregationValidityRecord`, `StrategicResponseRecord`.
- **Not yet:** rich predictive models for these axes are S11; here they only
  **fail closed** (block/limit when the axis is unmodeled).
- **Closure:** producer = each thin axis producer; persisted = axis firewall
  status on `DesignRecord`; bridge/consumer = constraint store + C3 composition;
  **surface** = per-axis firewall status in EXPERT/MACHINE projection; semantic =
  design assuming absent capacity is blocked/limited; unmeasured value surfaced
  as ignorance (P18), not omitted; negative = per-axis probe (P18/P19/P21/P22/P24)
  fails closed; reflexive edge `OTHER_AGENTS -> SYSTEM` is consumed, not dangling.
- **Firewalls:** P18, P19, P21, P22, P24.
- **Cells:** `OTHER_AGENTS.strategic_response`, `ACTOR.state_capacity_feasibility`,
  `ACTOR.mandate_legitimacy`, `SYSTEM.measurability`, `SYSTEM.subject_granularity`
  (each -> implemented (`maturity=fail_closed`)).
- **Promotion:** these gate other slices; not a user-facing posture themselves.
- **Floor:** per-axis fail-closed coverage (owner: runtime-quality).
- **Done when:** every blind-spot cell is implemented (`maturity=fail_closed`)
  with a passing per-axis negative control.

### S7 — Operating Model / Delegation Layer (mandate-backed)
- **Goal:** typed human-in-the-loop; autonomy = `capable ∩ permitted ∩
  within-bounds`; the system is an instrument of an accountable principal.
- **Prereqs:** S2, S6 (mandate producer exists).
- **Adds:** `DelegationContract`, `GovernanceDecisionClass` registry +
  `DecisionRightsMatrix` (decision-class -> role), `HumanDecisionRequest`
  (five-rights), `HumanDecisionRecord`, interaction modes
  (AI-first/AI-follow/request-driven/delegated-autonomous; default not AI-first
  for high-stakes/value-laden/out-of-envelope), responsibility-integrity (P26 +
  `oversight_theater`).
- **Not yet:** minimal attention ledger; full OversightEffectivenessReport is S13.
- **Closure:** producer = delegation/decision artifacts; persisted = mandate-checked
  `HumanDecisionRecord` in ledger/closeout; bridge/consumer = loop pauses ->
  request -> record; **surface** = decision-shaped, pull-first, VOI-ranked
  surface (the system-level P03); semantic = value-laden/high-stakes/out-of-envelope
  surface a request, low-VOI actions do not interrupt; negative = `oversight_theater`
  and wrong-role approval both invalidate the record.
- **Firewalls:** P26 (+ subtype), P20/P22 (mandate), principal-bounded-by-mandate.
- **Cells:** `operational delegation layer`.
- **Promotion:** unlocks **governed-pilot** posture for grounded cases (requires
  S6 mandate).
- **Floor:** delegation precision/recall + responsibility-integrity pass rate
  (owner: governance-board; artifact: governed config).
- **Done when:** delegation precision/recall ≥ floor; theater and wrong-role
  negative controls fail closed.

### S8 — Normative Firewall + Value-Choice + Pareto Frontier
- **Goal:** surface tradeoffs; require authorized value input; never invent
  social weights; expose (not solve) multi-principal conflict.
- **Prereqs:** S7 (value authorization is a delegation decision).
- **Adds:** value-choice provenance, `ParetoArchive` indexed by authorized value
  schedules, Arrow/multi-principal handling.
- **Not yet:** no automated preference learning (anti-learning firewall).
- **Closure:** producer = frontier + value-choice provenance; persisted =
  provenance on recommendation; bridge/consumer = ranking consumes authorized
  weights; **surface** = frontier + contested conflict projected, not a hidden
  scalar; semantic = scalar ranking without authorized provenance rejected;
  negative = LLM/corpus-derived weights cannot satisfy authority (P20).
- **Firewalls:** P20, P22; normative firewall.
- **Cells:** `ACTOR.value_choice_provenance`.
- **Promotion:** governed.
- **Floor:** value-provenance completeness = 100% of ranked recs (owner:
  governance-board).
- **Done when:** every ranked recommendation carries authorized value provenance.

### S9 — Canonical DesignRecord Matured + Projection/Lowering Algebra
- **Goal:** mature the S2 `DesignRecord` into the full narrow waist; faithful
  projections out, governed lowering in; output depth is a per-request parameter.
- **Prereqs:** S2 (record v0), S5 (composite records), S8 (value records).
- **Adds:** projection grammar (`audience x aspect x depth x redaction x
  format`), faithfulness verifier, projection-vs-lowering typing,
  depth-raises-authority, post-closeout lowering = re-open/reissue.
- **Not yet:** executable law/budget lowering only where authorized.
- **Closure:** producer = projection/lowering; persisted = appended lowering
  artifacts (re-verified); bridge/consumer = projection request -> faithful
  render or lowering; **surface** = all four audiences; semantic = public
  projection dropping a load-bearing limitation fails faithfulness; legal-diff
  lowering without grounding blocked while shallow projection allowed; negative =
  prose adding a claim absent from the record rejected.
- **Firewalls:** P03, P05 (projection carries no authority), faithfulness.
- **Cells:** `DESIGNER_ITSELF.closeout_projection_ratchet`; *layer:* canonical
  record + projection algebra.
- **Promotion:** governed.
- **Floor:** projection-faithfulness pass rate (owner: runtime-quality).
- **Done when:** projection/lowering corpus passes incl. faithfulness and
  blocked-lowering negative controls.

### S10 — Outcome Prediction + Welfare Comparison
- **Goal:** `DesignGraph + context -> outcome distributions + uncertainty +
  welfare comparison + authority envelope`, with `ForecastSupport` tiers — only
  **after** S6 blind-spot firewalls exist.
- **Prereqs:** S5, S6, S8.
- **Adds:** prediction contract over Foundry causal/optimization/bayesian;
  welfare comparison with value-choice provenance; calibration on observable
  subset only.
- **Not yet:** realized regret only where credible counterfactual exists; most
  large-scale predictions `simulation_only`/contested.
- **Closure:** producer = tiered prediction + welfare; persisted = forecast on
  record; bridge/consumer = recommendation inherits weakest boundary; **surface**
  = forecast tier + uncertainty in projections; semantic = calibration on
  backtestable subset; `equilibrium_contested` refuses single forecast; negative
  = `simulation_only` projected as evidence blocked.
- **Firewalls:** prediction authority envelope; regime ⟂ forecast tier.
- **Cells:** *layer:* outcome prediction + welfare comparison (B; no own cell).
  Named: `ForecastSupport`, `ForecastCalibrationRecord`.
- **Promotion:** governed where calibrated; large-scale/contested forecasts stay
  `simulation_only`/advisory.
- **Floor:** calibration floor on observable subset (owner: research).
- **Done when:** calibration passes on observable subset; non-observable cases
  honestly downgraded.

### S11 — Rich Blind-Spot Models + Remaining Knowledge Producers
- **Goal:** upgrade S6's thin fail-closed producers to predictive models where
  evidence supports it; close the remaining knowledge cells.
- **Prereqs:** S6, S10.
- **Adds:** rich strategic-response/Goodhart-Lucas + capacity-feasibility models
  (`maturity=predictive`); `KNOWLEDGE.calibration` orchestration;
  `KNOWLEDGE.ir_proof_carrying_analytics` wired into claim/comparison consumers;
  advances already-`implemented` `CROSS_CUTTING.method_infrastructure`
  Foundry-method orchestration without counting it as an open-cell closure.
- **Not yet:** a rich model never exceeds its evidence; where calibration/validity
  fail it stays at the S6 fail-closed limit.
- **Closure:** producer = predictive axis models + calibration; persisted =
  upgraded axis records (`maturity=predictive`); bridge/consumer = constraint
  store + S10 prediction; **surface** = upgraded confidence + residual limitation
  in EXPERT/MACHINE; semantic = a model relaxes the fail-closed limit only where
  calibration passes; negative = a model exceeding its evidence reverts to the S6
  fail-closed limit.
- **Firewalls:** keeps S6 P18/P19/P21/P24 as floor; calibration-before-relaxation.
- **Cells:** `KNOWLEDGE.calibration`, `KNOWLEDGE.ir_proof_carrying_analytics`;
  advances already-`implemented` `CROSS_CUTTING.method_infrastructure`; S6 cells
  -> `maturity=predictive`.
- **Promotion:** governed where calibrated.
- **Floor:** per-axis calibration floor (owner: research; artifact: governed config).
- **Done when:** each upgraded cell is calibrated or reverts to fail-closed;
  calibration/ir/method cells implemented.

### S12 — Cold-Start + Resource Economics (Reflexive Self-Design)
- **Goal:** the designer designs its own growth: demand-pulled bootstrap from the
  easy-corner real-demand case; robust multi-budget explore/exploit.
- **Prereqs:** S3, S7.
- **Adds:** consumption of the **S0** `ValueOfInformationEstimate` currency across
  acquisition/refinement/attention/oracle/allocation; bootstrap thermometers
  (override-rate, reuse-rate, held-out); principal-set explore/exploit dial;
  envelope-growth ledger.
- **Not yet:** no falsely precise MDP/bandit optimizer; allocation is
  robust/governed; meta-regress stops at the principal.
- **Closure:** producer = allocation policy + thermometers; persisted =
  envelope-growth ledger; bridge/consumer = allocation drives slice/acquisition
  priorities; **surface** = explore/exploit posture + thermometers in
  EXPERT/MACHINE; semantic = new cases reuse primitives (reuse-rate up,
  override-rate down); negative = bespoke one-off growth flagged and not counted
  as mechanism growth; allocation gaming internal metrics blocked.
- **Firewalls:** anti-learning/resource firewalls; principal as regress-stopper.
- **Cells:** `DESIGNER_ITSELF.envelope_growth`.
- **Promotion:** governed.
- **Floor:** reuse-rate / override-rate trend floors (owner: principal/governance).
- **Done when:** the S0 VOI currency is consumed at ≥3 sites; thermometers live;
  envelope-growth ledger updates.

### S13 — Post-Deploy Accountability + Learning
- **Goal:** accountable for deployed designs over time; learn only from
  attributable divergence; never rewrite closed-case authority.
- **Prereqs:** S9 (records to monitor), S7 (governance), S12 (envelope-growth ledger).
- **Adds:** design-time accountability gate (no deploy without monitoring design;
  monitorability floor / learnability ceiling / `accountability_only`);
  `DeploymentDossier`, `DivergenceRecord` (post-deploy `TypedDiagnosticRecord`),
  attribution-gated `LearningUpdateProposal` (change-control class),
  `EnvelopeRevision` (expand and **shrink**), `AssuranceCaseDelta`, MAPE-K.
- **Not yet:** no naive predict/observe/loss/update; outcome learning only on the
  sparse observable subset.
- **Closure:** producer = divergence + learning proposal + envelope revision;
  persisted = `DeploymentDossier` + `AssuranceCaseDelta`; bridge/consumer =
  attribution -> governed update -> knowledge ledger; **surface** = public
  accountability note + revision in PUBLIC/EXPERT; semantic = a seeded
  disconfirmation **shrinks** the envelope; negative = post-policy data as
  pre-policy evidence (Lucas) blocked, learned prior in a current evidence slot
  blocked (C41), `unattributable` records accountability without training.
- **Firewalls:** anti-learning, C41, A-leads-B, replay integrity.
- **Cells:** `DESIGNER_ITSELF.envelope_growth` (shrink/expand); *layer:*
  post-deploy accountability.
- **Promotion:** governed.
- **Floor:** `A_before_B_ratio`, attribution-resolution floors (owner: governance).
- **Done when:** the bidirectional envelope test passes (expand on validated
  reuse, shrink on seeded disconfirmation).

### S14 — Evaluation Redesign + Universality Assurance Battery
- **Goal:** the contestable, falsifiable definition of "universal" and the gate
  on ever claiming it.
- **Prereqs:** grows from S1; consolidates after S6+ axes exist.
- **Adds:** D4 corpus tracks, expert-oracle bootstrap, breadth target, **sealed**
  held-out frozen-system battery (S0 corpus partition; freeze hash; CI access
  check; owner), per-axis + hard-corner scorecard, reuse-rate, six skeptic
  defeaters, universality-claim assurance case + faithfulness check on the claim.
- **Not yet:** no aggregate "universal" number; untested axis combinations
  out-of-envelope by default; the system never sees the sealed battery in
  development.
- **Closure:** producer = battery results + assurance case; persisted = per-axis
  scorecard + assurance case; bridge/consumer = scorecard gates any "universal"
  claim; **surface** = per-axis scorecard + envelope in PUBLIC/EXPERT/MACHINE;
  semantic = mechanism-generality on held-out cases with sublinear marginal
  bespoke cost and every skeptic attack passing; negative = a bare "universal"
  claim without envelope+battery rejected by the faithfulness verifier; the
  system touching the sealed battery in dev fails CI.
- **Firewalls:** universality-claim firewall; held-out integrity (sealed path +
  freeze hash + CI check).
- **Cells:** `DESIGNER_ITSELF.evaluation_corpus`; *layer:* universality battery.
- **Promotion:** the **only** gate that authorizes external use of "universal."
- **Floor:** per-axis posture thresholds + breadth floor (owner: governance;
  artifact: governed config).
- **Done when:** the battery passes per-axis at the declared posture and the
  assurance case survives all six skeptic defeaters.

---

## Cross-Cutting Tracks

- **T0 — Ratchet & map burn-down ledger.** Every slice updates
  `capability_reality_report.json` and `cluster_ownership_map.toml`; CI runs the
  ownership-map validator and reports `open_cell_count` trend (baseline 17/27).
  Single progress meter. **W12 green is not this meter.**
- **T1 — Sealed universality battery (S14).** Grows from S1 in the
  `sealed_universality_battery` fixture path only; never edited during
  development; access-checked in CI.
- **T2 — Adversarial-against-A.** Standing red-team for designs that pass A but
  are bad. Raised by S2/S4/S5/S10.
- **T3 — Replay/CI invariants.** Frozen-ref replay, no-new-status-lattice,
  no-scenario-family-authority guards on every slice.

## Ambition Map — So The MVP Is Never Mistaken For The System

Complete only when every row is realized **and** S14's battery holds at the
declared posture. Any external "universal designer" claim before that is a
laundering move.

| Design-doc commitment | Realized by | Done? |
| --- | --- | --- |
| D0 B-on-A shadow-first, two roles | doctrine + S7 promotion gates | ☑ |
| D0 operational universality definition | S14 | ☑ |
| D1 binding constraint (substrate) | S3 | ☑ |
| D2.2 named artifacts traced | S0 artifact table + slices | ☑ |
| D2.3 facet algebra / compositional constructs | S3 | ☑ |
| D2.4 axis declaration + irregular envelope | S4-S6 + T0 | ☑ |
| D2.5 epistemic-regime architecture | S4 | ☑ |
| D2.6 coupling + design-composition + dynamics | S5 | ☑ |
| D2.7 coverage machinery + bounded abstention | S3 | ☑ |
| D2.8 closed acquisition loop (state machine) | S3 | ☑ |
| D3.1 grammar-first candidate (anti-P15) | S2 | ☑ |
| D3.2 counterexample-guided search control plane | S2 (+ S4/S5 conditioning) | ☑ |
| D3.3 operating/delegation model | S7 | ☑ |
| D3.4 normative firewall | S8 | ☑ |
| D3.5 prediction/forecast boundary | S10 | ☑ |
| D3.9 canonical design record + projection algebra | S2 (v0) + S9 (mature) | ☑ |
| D3.10 cold-start + reflexive resource economics | S12 | ☑ |
| D4.1-D4.5 evaluation redesign | S14 (+ each slice corpus) | ☑ v1; D4.4 re-basing follow-up tracked below |
| D4.6 post-deploy accountability + learning | S13 | ☑ |
| Blind-spot producers (capacity/strategic/measurability/mandate/aggregation) | S6 (thin) + S11 (rich) | ☑ |
| Unifying Abstractions wired (not one-off) | all slices + doctrine | ☑ |
| Graded outcomes (A-side near-term win) | S1 | ☑ |

### Post-S14 Governance Follow-Ups

- **D4.4 Corpus Re-Basing Rule** remains a post-S14 governance procedure, not a
  hidden runtime claim. S14 v1 freezes and verifies the sealed battery, but it
  does not yet persist a `re_basing` / `frozen_system_status` record for corpus
  aging, re-annotation, and post-freeze retraining controls. Until that
  follow-up lands, D4.4 must be cited as a limitation on future re-certification,
  not as production, recommendation, claim, closeout, preference-learning, or
  automated value-learning authority.

## Validation

Run with `cwd = policy-engine`. Expected results in parentheses.

```bash
cd policy-engine

# Every slice (burn-down + map + ratchet integrity):
uv run pytest tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py -q        # (pass)
uv run python tools/quality/validation/check_policy_design_case_cluster_ownership_map.py           # (exit 0; open_cell_count decreased)
uv run pytest tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py -q             # (pass)

# Architecture guardrails + runtime contract (every slice):
uv run pytest tests/repo_quality/architecture -q                                                    # (pass)
PYTHONPATH=src:. uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract  # (OpenAPI + generated client contract pass)

# Proving ground (S1,S2,S3,S4,S5): honest behavior change, floors intact:
uv run python tools/quality/validation/run_universal_outcome_corpus.py --mode real_producer         # (slice-specific: limitations/bindings, closeout_honesty=1.0)
```

Per-slice command rows (targeted tests + expected pass/fail) are added to each
slice's design step when it is opened; a slice is not "done" until its targeted
semantic and negative-control tests pass and the map validator stays green.

Plan-level done: the Ambition Map is fully checked **and** the S14 sealed
universality battery passes per-axis at the declared posture, with the assurance
case surviving all six skeptic defeaters.

## Relationship To The Existing Plans

- W0-W12 (`POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md`) built
  **A**; this plan consumes it as the release gate. **W12 ratchet green ≠
  Layer-2 readiness** (the cluster map, not the W12 report, is the meter).
- The capability-graph plan (ADR-0174) is the substrate authority spine S3
  extends. Scenario-family strings remain compatibility projections only.
