---
title: INT-R4 — Performativity-Safe Effect Updating
status: in_progress — repository baseline recorded
kind: deep-research
research_task: INT-R4
joint_with: OPS-R5
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r4-ops-r5-research
repository_baseline: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
inspection_date: 2026-08-29
research_only: true
authoritative_for:
  - research findings about post-deployment effect-update safety
  - candidate shared movement-diagnosis vocabulary for INT-R4 and OPS-R5
  - audit of the written GY-O1 and GY-O3 riders
  - research contract for absorbed OPS-R7 scope
may_not_use_for:
  - capability claim
  - production implementation authorization
  - registered vocabulary claim
  - canonical owner appointment
  - authority grant
  - automatic posterior update
  - automatic world-model write-back
  - benchmark passage
---

# INT-R4 — Performativity-Safe Effect Updating

## 1. Task And Project Fit

### 1.1 Commission and joint ownership

INT-R4 asks what causal-safety case is required before post-deployment evidence may update an effect posterior when the deployed policy can change behavior, selection, measurement, reporting, data availability, or interference. It absorbs OPS-R7: causal validity under sequential policy adaptations, including treatment versions, interference, and stopping rules. The task is the binding research input for GY-O1 and GY-O3 and is explicitly joint with OPS-R5 (`policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:485-492`).

The pair has one substantive object: a typed explanation of why an observed quantity moved. INT-R4 owns the single derivation of that candidate vocabulary. OPS-R5 must cite this document rather than restate, fork, or independently amend the categories, precedence rule, exhaustiveness boundary, or unresolved residue.

### 1.2 Custody boundary

The deployed-outcome learning loop is OWN-core because an unsafe update can make a PolicyOS-signed justification silently false. Deployment execution, field data collection, clinical or administrative adjudication, and institutional sign-off remain external functions. PolicyOS owns the typed integrate-evidence contract, fail-closed admission, update refusal, provenance, and historical replay; it does not acquire sovereign power to deploy or adjudicate.

### 1.3 Exact controlled claim

The controlled operation is not “observe a residual.” It is:

> admit a realized-versus-predicted comparison as evidence that may change a substantive effect posterior or a world-model edge.

The comparison is meaningful only when it names the prediction, effect or outcome carrier, intervention version, population, exposure history, observation definition and version, time horizon, uncertainty basis, and interference assumptions. A scalar delta without those conditionals is not an admissible delta.

### 1.4 Absorbed OPS-R7 coverage

OPS-R7 is covered in this deliverable as follows:

- treatment and policy-rule version identity: §§4, 5, 7 and 9;
- sequential adaptation and endogenous version assignment: §§3, 4, 5 and 9;
- interference and exposure mapping: §§3, 4, 5 and 7;
- stopping, repeated looks, exploratory-to-confirmatory promotion, and claim reset: §§3, 4, 6 and 9;
- carryover, delayed labels, censoring and distributed harm: §§3, 5, 6 and 7.

Absorption is coverage only. It does not move capability or appoint an owner.

## 2. Current Repository Baseline

### 2.1 Pin and inspection method

Repository evidence is pinned to `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`. The inspection followed the canonical seams named by the commission: the Wave-8 backlog and pipeline, GY-O1/O2/O3, the N8 value-carrier path, S13 post-deploy accountability, DDM detectors and FDR, `WorldModelRecord`, Fabric append-only branch/provenance behavior, and Fabric quarantine.

A GitHub recursive-tree endpoint was invoked at the pinned tree and canonical directories were enumerated through the Contents API. This environment could not execute a local `git grep` or complete scripted tree census because ordinary Git transport could not resolve `github.com`. Therefore this package makes no repository-wide zero claim and labels any unexecuted census `not_established`, as required by P35/W4-K01. The baseline instead establishes positive facts from exact canonical files and identifies missing links in the named owner chain.

### 2.2 The prompt's “entirely greenfield” orientation is too broad at this pin

The repository already contains a typed post-deployment attribution surface. `DivergenceAttributionClass` has eight values — `design_error`, `evidence_error`, `regime_error`, `coupling_error`, `world_change`, `strategic_response`, `implementation_failure`, and `unattributable` — and `DivergenceRecord` carries that class, attribution status, evidence refs, learning eligibility, authority boundary, and accountability fields (`policy-engine/src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py:43-58`, `:164-221`). Canonical S13 fixtures directly supply `attribution_class` and `attribution_status` (`policy-engine/tests/fixtures/layer2/s13/s13_post_deploy_case_signals.json:4-204`).

This means the global statement “there is no typed diagnosis anywhere” is false. The narrower, task-relevant statement is supported: the inspected S13 producer validates a supplied attribution label; it does not derive the joint INT-R4/OPS-R5 movement diagnosis from a concrete realized-versus-predicted comparison. The S13 taxonomy also answers a different question — which post-deployment accountability/model lane is implicated — and is not identical to the O1 cause classes. The exact shared movement-diagnosis capability remains unallocated.

This is an orientation correction, not a capability promotion. The S13 manifest may call its own bounded chain implemented; it does not establish the GY-O1/O3 chain requested here.

### 2.3 GY plan status and the written riders

The active GY plan labels O1, O2 and O3 `build-new`. O1 requires a cause-typed realized-versus-predicted delta before posterior updating; O2 routes anomalies through DDM/FDR as low-authority hypotheses; O3 writes only confirmed findings into a versioned world branch and carries the self-confirmation red fixture (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:5043-5095`). The same plan states that the O-block must not close while INT-R4 is undelivered unless the riders are independently satisfied and recorded (`:5020-5033`).

The plan is an implementation intention and a written gate, not evidence that the gate is implemented.

### 2.4 Value-gate carriers are typed and generic enough to be inputs

The generation-cycle value path already has strict typed carriers:

- `ValueGateReceipt` binds candidate, evaluation mode, selected method, identification status, `ValueOuterSet`, transport and calibration receipts, world-model content hash, value ref and timing (`policy-engine/src/polisyos/runtime/quality/generation_cycle.py:416-499`);
- `ValuePortObservation` represents pending, ready and blocked value states and cannot carry a receipt while blocked or pending (`:500-568`);
- `ValueOuterSet` and its metrics carry interval, subgroup, provenance, uncertainty, observation-time and validity structure (`policy-engine/src/polisyos/core/contracts/value_outer_set.py:1-300`).

These surfaces satisfy the commission's “generic over typed effect/outcome carriers” starting point better than a panel-scalar-only design would. They do not yet bind a later realized observation to the exact predicted carrier, treatment history, measurement schema, exposure mapping and diagnosis record. That comparison contract is missing from the inspected chain.

### 2.5 DDM detects and localizes; it does not establish the movement cause

The DDM substrate is substantial:

- `ShiftDetectedEvent` requires calibrated evidence, stationarity regime and empirical false-positive information; `ShiftRiskEvent` normalizes it into `low`, `watch`, or `investigate` (`policy-engine/src/polisyos/ddm/integration/events.py:43-119`);
- realized binary and regression monitors join delayed labels, compute metric estimates and 95% intervals, and record p50/p90 label delays (`policy-engine/src/polisyos/ddm/detectors/realized_performance_monitor.py:1-151`);
- deterministic data-quality checks cover schema, null, type, range, allowed values and freshness (`policy-engine/src/polisyos/ddm/detectors/data_quality_monitor.py:1-142`);
- the Track-2.2 adapter preserves calibrated p-value/e-value/ERT evidence and maps a shift score into a risk level (`policy-engine/src/polisyos/ddm/detectors/track_2_2_shift_adapter.py:1-62`);
- `MultipleTestingPlan` and `OnlineFDRController` implement Bonferroni/union-bound allocation and an alpha-wealth stream (`policy-engine/src/polisyos/ddm/calibration/multiple_testing.py:1-89`);
- `RootCauseBundle` groups shift/degradation IDs, affected features/slices, upstream versions, data-quality violations, stationarity regimes and calibration IDs (`policy-engine/src/polisyos/ddm/integration/events.py:213-232`).

The module-level contract explicitly keeps drift, degradation, data quality and readiness separate so drift is not silently treated as a retraining trigger (`events.py:1-7`). That is an important reuse seam and a strong negative precedent against detector-to-cause collapse. But the `RootCauseBundle` is a localization bundle, not the shared causal diagnosis: it contains no predicate proving `prediction_error`, observation-process causation, implementation/version divergence, behavioral response, context/interference or unresolved decomposition.

### 2.6 Monitoring and lifecycle responses exist, but their semantics are adjacent

`ImplementationMonitoringEvaluationRecord` requires an implementation contract, monitoring plan, evaluation design, publication ordering, DDM shift/degradation/readiness/incident/root-cause evidence, claim links and runtime refs (`policy-engine/src/polisyos/runtime/quality/ddm_monitoring.py:1-287`). Continuous governance separately types source invalidation, calibration drift, fairness drift, policy-context drift and incident signals and maps them to monitoring, stale, review, reissue or withdrawal-review recommendations (`policy-engine/src/polisyos/scientist/governance/continuous/monitors.py:1-113`).

These are usable signal and lifecycle inputs. They do not provide one shared cause vocabulary governing both OPS-R5 policy response and INT-R4 posterior update.

### 2.7 World storage can preserve a safe result, but does not decide admissibility

The world package describes itself as an append-only fact store and materialization layer with fact/event persistence, snapshots, branches, merge conflicts and provenance (`policy-engine/src/polisyos/fabric/world/README.md:1-63`). Time-travel semantics preserve append-only assertion, correction, revocation, branch assertion and scenario assertion; corrections and revocations carry actor, reason, evidence and lineage instead of overwriting history (`policy-engine/docs/reference/fabric/time-travel.md:1-78`).

`WorldModelRecord` has an explicit `deployment_update` branch mode. Its `DeploymentUpdateRefs` are forward hooks only, and the class documentation says the record binds existing substrates rather than storing facts or executing mechanisms (`policy-engine/src/polisyos/runtime/quality/world_model_record.py:1-7`, `:58-68`, `:185-239`). This is a suitable write destination after admission, not an admission mechanism.

Fabric quarantine is CAS-backed and persists an immutable quarantine record plus raw-payload lineage and deterministic reprocess results (`policy-engine/src/polisyos/fabric/data_plane/quarantine.py:1-106`, `:220-463`). Its generic default is reprocessable dead-letter handling. It does not encode the O3-specific permanent rule “this confirmation may never write the candidate edge,” does not prove causal ancestry through the observation process, and generates `record_id` with a UUID rather than a content-derived diagnosis identity. O3 therefore needs a typed semantic quarantine record or profile over this substrate, not merely reuse of the generic DLQ label.

### 2.8 Baseline verdict

The repository has strong fragments: typed value carriers, calibrated detectors, delayed-label metrics, FDR, supplied post-deploy attribution labels, lifecycle recommendations, append-only world branches, provenance and generic quarantine. The missing capability is the **admitted shared movement diagnosis chain**:

```text
conditioned prediction + realized observation
→ comparison validity
→ evidence-derived cause diagnosis
→ update/response routing
→ independent authority decision where required
→ append-only posterior/world write or frozen/quarantined refusal
→ semantic replay and adversarial verification
```

No canonical owner or institutional signer is appointed for that chain. The capability standing for the joint INT-R4/OPS-R5 mechanism is therefore `absent/unallocated`; the adjacent components retain their own narrower standings.

Supporting baseline and finding coordinates are maintained in [the INT-R4 evidence register](int-r4/evidence-register.md).

## 3. External Research Baseline

## 4. Result

## 5. Counterexamples And Failure Modes

## 6. Benchmark Or Fixture Proposal

## 7. Artifact Contract Sketch

## 8. Later Integration Handoff

## 9. Promotion And Kill Rules

## 10. Open Questions For Consolidation
