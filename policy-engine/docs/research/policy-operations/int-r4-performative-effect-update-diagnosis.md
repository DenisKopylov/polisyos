---
title: INT-R4 — Performativity-Safe Effect Updating
status: in_progress — external baseline and result recorded
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

### 3.1 Source posture

The five commissioned surveys are treated as `institutionally_supplied` research inputs relative to this package. Their source hierarchies distinguish primary law/standards, canonical papers, empirical studies, simulations, audits and design recommendations, but this pass did not independently reproduce every underlying study. They establish what practices are possible, what they cost, where literatures disagree and what remains unidentified. They establish no repository capability and register no PolicyOS vocabulary.

The source set is:

| ID | Supplied survey | Primary contribution to this task |
|---|---|---|
| S1 | *Identification When Policy Changes Its Own Evidence* | Causal separation of latent outcome, observation, selection and behavioral response; identification strategies and self-confirmation limit. |
| S2 | *Graded Response To New Evidence: Stopping Rules, Escalation And Reversibility* | Sequential adaptation, treatment versions, exploratory/confirmatory boundary, multi-axis response and reversibility. |
| S3 | *How Mature Monitoring Regimes Decide Why A Number Moved* | Cross-domain diagnosis vocabularies, residue policies, detector-versus-diagnosis boundary and classification reliability. |
| S4 | *Metric As A Governed Contract* | KPI contract fields, Goodhart/Campbell mechanisms, role separation, decision rights and revision/version integrity. |
| S5 | *How Surveillance Finds Delayed, Unreported, Distributed And Spillover Harm* | Delayed/censored harm, absent channels, subgroups, interference, sentinel health and honest unknowns. |

### 3.2 What is well supported across the surveys

Five propositions survive the disagreements.

1. **A changed observed quantity is not self-interpreting.** S1 formalizes the observed value as a function of the latent outcome, measurement, selection, behavioral response and policy. If policy can alter observation, selection or response, the observed movement alone does not identify movement in the latent outcome (S1:5-33, 70-122, 256-383).
2. **Detector output is not a cause label.** S3 shows this across SPC, epidemiology, SRE and experimentation: control-chart alarms, SRM, out-of-range metrics and pages precede causal diagnosis. The strongest transferable rule is causal typing before learning, not causal typing before every protective action (S3:5-41, 43-79, 183-287, 330-379).
3. **The same numerical delta legitimately selects different update operators.** Official-statistics revisions, IAS 8 estimate changes versus prior-period errors, experiment trust failures and pharmacovigilance causality states all route the same numerical movement differently according to why it occurred (S3:43-130, 289-321).
4. **The observation process is part of the causal system after deployment.** Independent sensors, dual runs, selection-margin accounting, observation-intensity normalization, negative controls and policy-off/randomized probes are methods for testing whether evidence is about the target or about its production (S1:35-68, 112-122).
5. **Unknown is a legitimate terminal research result.** Where no independent sensor, randomized variation, valid proxy or structural restriction separates latent-outcome and observation-process effects, the decomposition is generally not identified. More rows from the same contaminated pipeline do not close that gap (S1:256-268; S3:89-112, 132-181; S5:253-300).

### 3.3 Disagreements preserved rather than reconciled

The surveys do not support a single universal operational doctrine.

- **Act before diagnosis or freeze?** SRE, aviation and safety monitoring may mitigate or contain before root cause is known; experimentation freezes inference; SPC warns against tampering with common-cause variation. The safe synthesis is purpose-specific: uncertainty may license protective containment, but not substantive model learning (S2:34-82, 84-137; S3:5-9, 81-130, 183-287).
- **Single cause or multiple contributors?** Epidemiology, SRE, official-statistics revisions and online experimentation commonly permit multiple mechanisms. A single routing label is defensible only if the record also retains contributors and fails unresolved when a unique primary cannot be justified (S3:15-41, 132-181, 183-287, 350-379).
- **Negative controls diagnose or identify?** The epidemiological tradition uses them mainly as falsification tools; proximal inference can identify under stronger bridge/completeness assumptions. A null negative control is not automatic proof of no bias (S1:39-68, 228-254).
- **Imputation or exploration for selective labels?** Reject-inference methods depend on modeling assumptions; controlled exploration creates missing counterfactual labels but costs exposure, money and sometimes ethical permission. The surveys do not establish one universal solution (S1:39-68, 188-194, 228-254).
- **Targets help or distort?** NHS and education evidence shows beneficial substantive effects can coexist with bunching, score inflation, selection and effort substitution. A target-linked metric is not automatically invalid, but cannot validate itself alone (S1:138-164, 228-252; S4:67-143).

### 3.4 Sequential adaptation, interference and delayed harm

S2 establishes that after `A0 → A1 → A2`, “the effect of the intervention” is not a single estimand unless the relevant object is fixed: a specific version, a declared distribution over versions, or a dynamic policy rule. Version assignment may be endogenous to prior outcomes; unplanned versions do not inherit confirmatory status from an earlier design. Intervention artifact, eligibility/scope, decision rule, outcome definition, exposure history, measurement pipeline, adaptation trigger, concurrent interventions and the causal claim attached to release all require version identity (S2:214-301).

Interference changes the unit and denominator: outcomes can depend on others' assignments, controls can be contaminated and displacement can make local improvement overstate system benefit. Exposure mapping and cluster/network designs help only when the exposure structure is declared and sufficiently observed; an endogenously changing network remains an identification gap (S1:41-48, 58-66, 256-283; S5:179-251).

Delayed, censored and distributed harm also limits update safety. Absence of recorded harm is informative only relative to a latency horizon and non-trivial detection probability. Exited, rejected, never-entered and neighboring populations may have zero inclusion probability in the production channel. Honest reporting must distinguish observed harm, model-estimated missing harm and unquantified exposure (S5:5-19, 21-131, 133-251, 253-300).

### 3.5 Evidence-grade conclusion

The literature supports a **research-level routing discipline**, not a validated universal classifier. No surveyed regime supplies the exact vocabulary required here, no cross-domain base rate for the unresolved class exists, and cause-label reliability is rarely measured. Where measured in pharmacovigilance, agreement is useful but not deterministic. The result below is therefore a bounded candidate vocabulary with explicit operational tests and an unresolved terminal, not a registered standard or proven automated adjudicator.

## 4. Result

### 4.1 Result type and name

**Result: `accepted_narrow_scope`.** This deliverable defines one candidate **Shared Movement Diagnosis Vocabulary (SMDV-1)** for INT-R4 and OPS-R5. This section is its sole derivation and owner. OPS-R5 imports SMDV-1 by reference; it does not define another vocabulary.

SMDV-1 is a research rulebook for deciding whether an observed movement is admissible evidence about a predictive mechanism and for routing non-model explanations. It is not a registered vocabulary, production schema, automated classifier or authority grant.

### 4.2 The comparison object precedes the category

A diagnosis is void unless a `MovementComparison` identifies at least:

```text
prediction/effect carrier and content identity
estimand and target construct
predicted distribution, interval or set — not only a point
intervention artifact and rule version
intended and realized eligibility, dose, exposure and implementation trace
population and subgroup frame
observation definition, instrument, schema and pipeline versions
observation, valid, transaction and decision times
follow-up maturity, censoring and missingness posture
context/concurrent-policy version and interference/exposure map
behavioral-response hypothesis
calibration, identification and uncertainty basis
```

The delta is therefore a typed relation between conditioned objects. `realized - predicted` is only one projection and may be undefined for interval-, set- or distribution-valued carriers. An implementation that coerces every carrier to one scalar has not implemented this result.

### 4.3 The seven terminal primary classes

| Class | Meaning | Operational assignment test | Permitted effect-posterior consequence |
|---|---|---|---|
| `expected_variation` | The realized observation is model-compatible under the declared predictive and measurement envelope, and no material divergence in observation, intervention, context/interference or behavior is established. It is an operational “common variation” result, not proof that no harm exists. | Comparison is evaluable; measurement-health predicates pass; realized intervention matches the declared version; relevant context and exposure remain inside the declared envelope; posterior-predictive or equivalent predeclared check does not reject model compatibility. | No discrepancy-driven model repair. It may enter only a separately predeclared routine likelihood/calibration schedule; it cannot trigger adaptive re-estimation, policy change or world-edge creation by itself. |
| `observation_process_change` | The mapping from latent outcome to recorded evidence changed: definition, instrument, coding, reporting/testing intensity, selection, inclusion, denominator, attrition/censoring, join/logging pipeline, revision or data availability. | A version/change record, dual run, bridge/backcast, independent sensor divergence, selection-margin shift, observation-intensity change, negative-control failure or equivalent evidence establishes a material observation-path change. | Freeze substantive effect update unless an independent identification bridge recovers the latent-outcome estimand. Route to measurement/semantic-epoch and data-quality lanes. |
| `intervention_delivery_or_version` | The intervention compared is not the intervention predicted: delivery failure, fidelity change, eligibility/scope change, dose/exposure change, deliberate version change or altered adaptive decision rule. | Content-bound intended-versus-delivered comparison, exposure history and implementation evidence establish a material mismatch. Deliberate and failed changes use subcodes; neither is silently pooled. | Do not update the old-version effect posterior from the mixed delta. Route to delivery evidence, version-specific evaluation, partial reissue or new estimand. |
| `behavioral_response` | Actors respond to the policy, target or disclosure in a way that changes the substantive outcome or treatment uptake: adaptation, gaming, avoidance, substitution or strategic response. | A predeclared or newly supported response path `policy → actor response → latent outcome/exposure` is evidenced independently of mere reporting/inclusion change. | Route to mechanism/strategic-response model. The old effect posterior updates only under a model whose estimand includes that response and whose identification basis remains valid. |
| `context_or_interference` | The movement is materially attributable to external world change, concurrent policy, regime change, network/geographic spillover, equilibrium effect, control contamination or other-unit exposure not represented by the prediction. | Context/version comparison, concurrent-intervention ledger, exposure mapping, untreated-neighbor/saturation evidence or a transport/regime check establishes the divergence. | Route to context, coupling, regime or interference model. Do not treat as a clean unit-level prediction error. |
| `prediction_error` | After the preceding gates pass, the remaining movement is admissible evidence about the predictive mechanism or its effect parameters. The term means a **model-relevant innovation**, not automatically model misspecification or an out-of-band alarm. | Observation process is stable or bridged; the intended version and exposure are established; context/interference and behavioral paths are absent, already modeled or separately identified; the outcome is mature enough; the identification basis remains valid; a residual remains. | Eligible for the predeclared effect-posterior update. Eligibility is not authorization: provenance, calibration, power/maturity, authority boundary and any required human decision must still pass. |
| `diagnosis_unresolved` | Available evidence is missing, contradictory, too immature or compatible with multiple materially different primary explanations that cannot be ordered. | One or more decisive predicates are `consumer_asserted`, `institutionally_supplied` without independent admission, or `not_established`; no unique primary class survives falsification; or the latent-outcome/observation decomposition is nonidentified. | Freeze substantive posterior and world-edge update. Protective containment, investigation, acquisition, annotation or publication downgrade may still proceed under separate authority. Never default to `prediction_error`. |

### 4.4 Precedence and multi-causality rule

The procedure is an **admission precedence**, not a claim that causes occur in this order:

```text
0  establish comparison identity, maturity and admissible evidence
1  test observation-process invariance and series comparability
2  test intended-versus-delivered intervention and version identity
3  test context, concurrent policy and interference/exposure assumptions
4  test behavioral-response paths and whether they reach outcome or only observation
5  split model-compatible expected variation from remaining model-relevant prediction error
6  if no unique supported primary survives, diagnosis_unresolved
```

One `primary_class` is emitted for routing, but the record also carries `contributing_classes`. A class that blocks learning remains blocking even when it is not primary. If two contributors require incompatible primary routes and their relative contribution cannot be identified, the primary result is `diagnosis_unresolved`; the system does not manufacture exclusivity.

This makes the classes operationally disjoint without erasing multi-causality: disjointness belongs to the **assignment procedure**, while the causal record retains all supported contributors.

### 4.5 The measurement-change / behavioral-response boundary

The hard overlap is resolved by the path that is actually established:

- `policy → behavior → latent outcome` is `behavioral_response`;
- `policy → behavior → reporting/testing/selection/coding → recorded evidence`, without an independently identified latent-outcome change, is `observation_process_change` with behavioral response recorded as a contributor;
- both paths established: choose `behavioral_response` only if an independent outcome channel identifies the substantive path, retain `observation_process_change` as a blocking contributor, and freeze any update that cannot remove its contamination;
- paths plausible but not separable: `diagnosis_unresolved`.

Thus “people reported more because the rule rewarded reporting” is not allowed to become “the underlying outcome increased.” Conversely, a real behavioral effect is not downgraded to mere instrumentation simply because it also changes reporting.

### 4.6 Bounded exhaustiveness and the residue

SMDV-1 is exhaustive only relative to a declared comparison graph with five possible material departure locations: observation process; intervention/delivery/version; behavior; context/interference; predictive mechanism — plus model-compatible variation. It is **not** an exhaustive ontology of every physical cause in public policy.

The unresolved terminal does not make the claim vacuously exhaustive because it has a cost and a falsifier:

- it freezes substantive learning;
- it names the competing classes and missing discriminator;
- it identifies the next evidence that could separate them;
- it expires or reopens on a declared clock;
- a case that contains sufficient distinguishing evidence but still lands unresolved is a false block;
- a case that lacks distinguishing evidence but lands in a substantive class is a false pass.

No defensible cross-domain production proportion for `diagnosis_unresolved` is available in the supplied surveys. The expected production share is therefore `not_established`, not zero. It is likely non-trivial and may be high in feedback-heavy, newly deployed or weakly observed policies. The proposed 24-case benchmark deliberately assigns 8/24 cases (33⅓% of the test population) to unresolved or inseparable-compound conditions; that is a stress-test composition, **not** a prevalence estimate. A high realized unresolved rate is acceptable as honest refusal but prevents governed promotion and should fund better observation/design rather than be normalized away.

### 4.7 Mapping to existing S13 without owner duplication

SMDV-1 does not replace S13's `DivergenceAttributionClass`; the two axes answer different questions.

| SMDV-1 result | Nearest S13 lane | Mapping loss that must remain explicit |
|---|---|---|
| `expected_variation` | no learning divergence / accountability observation | S13 has no explicit model-compatible terminal. |
| `observation_process_change` | `evidence_error` is nearest | `evidence_error` does not explicitly distinguish policy-caused ascertainment/selection from ordinary evidence defects. |
| `intervention_delivery_or_version` | `implementation_failure` is nearest | Planned version/eligibility/rule change is not necessarily failure. |
| `behavioral_response` | `strategic_response` | Non-adversarial adaptation and intended mediation may also belong here. |
| `context_or_interference` | `world_change`, `regime_error`, or `coupling_error` | One shared class may route to several S13 model components. |
| `prediction_error` | `design_error`, `evidence_error`, `regime_error` or `coupling_error` after diagnosis | S13's destination taxonomy is finer about the model component, not the source of observed movement. |
| `diagnosis_unresolved` | `unattributable` / pending | Preserve whether more evidence can resolve the case and which discriminator is missing. |

The safe integration is two-stage: SMDV-1 establishes why the observed movement may or may not inform the predictive mechanism; S13 then routes an admitted model-relevant divergence to the accountable component. Collapsing them would reintroduce the failure this joint pair exists to prevent.

### 4.8 Update rule

A substantive effect-posterior or candidate world edge may be proposed only when all of the following hold:

```text
primary_class == prediction_error
AND no blocking contributing class exists
AND comparison and identification statuses are positive
AND outcome maturity / censoring / interference predicates pass
AND evidence provenance is recomputed or independently reconciled
AND the update is inside a predeclared version-specific update rule
AND required decision authority is established
```

`expected_variation` can feed only a separately predeclared routine update/calibration schedule; it does not license a discrepancy-driven repair. All other classes route elsewhere. `diagnosis_unresolved` freezes learning but not necessarily protective action.

### 4.9 What this result does not settle

SMDV-1 does not provide a universal statistical test, inter-rater reliability threshold, causal-discovery method, signer, default observation horizon or domain-independent action threshold. It does not prove that the latent outcome is observed. It does not turn a DAG declaration into causal ancestry evidence. Those are explicit later obligations, and some may remain open or institutional rather than engineering work.

## 5. Counterexamples And Failure Modes

## 6. Benchmark Or Fixture Proposal

## 7. Artifact Contract Sketch

## 8. Later Integration Handoff

## 9. Promotion And Kill Rules

## 10. Open Questions For Consolidation
