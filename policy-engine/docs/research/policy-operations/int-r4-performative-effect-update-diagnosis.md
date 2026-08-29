---
title: INT-R4 — Performativity-Safe Effect Updating
status: in_progress — rider audit and fixture proposal recorded
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

The pair has one substantive object: a typed explanation of why an observed quantity moved. INT-R4 owns the single derivation of that candidate vocabulary. OPS-R5 cites this document rather than restating, forking, or independently amending the categories, precedence rule, exhaustiveness boundary, or unresolved residue.

### 1.2 Four-way custody boundary

The ratified identity makes the post-deployment learning loop OWN-core: an unsafe learning update can silently invalidate a PolicyOS-signed justification. Deployment execution, field data collection, adjudication, and institutional sign-off remain external. PolicyOS owns the typed integrate-evidence contract, fail-closed admission, update refusal, provenance, historical replay, and the validity consequences for its own claims. It does not acquire sovereign power to deploy, investigate people, adjudicate legal rights, or appoint a decision authority (`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:23-124`).

### 1.3 Exact controlled operation

The controlled operation is not merely “observe a residual.” It is:

> admit a realized-versus-predicted comparison as evidence that may change a substantive effect posterior or a world-model edge.

The comparison is meaningful only when it names the prediction, effect/outcome carrier, intervention version, population, exposure history, observation definition and version, horizon, uncertainty basis, and interference assumptions. A scalar delta without those conditionals is not an admissible delta.

### 1.4 Absorbed OPS-R7 coverage

OPS-R7 is covered here as follows:

- treatment and policy-rule version identity: §§3.4, 4.2–4.8, 5.3, 7 and 9;
- sequential adaptation and endogenous version assignment: §§3.4, 4.3–4.8, 5.3 and 9;
- interference and exposure mapping: §§3.4, 4.2–4.8, 5.3 and 7;
- stopping, repeated looks, exploratory-to-confirmatory promotion, and claim reset: §§3.3–3.5, 4.8, 6 and 9;
- carryover, delayed labels, censoring and distributed harm: §§3.4, 4.2–4.8, 5.3, 6 and 7.

Absorption is coverage only. It does not move capability or appoint an owner.

## 2. Current Repository Baseline

### 2.1 Pin and inspection method

Repository evidence is pinned to `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`. The mandatory architecture anchors were read: `AGENTS.md`, `policy-engine/CONTRIBUTING.md`, the ratified identity decision, organizing rules, target architecture, operating model, honest-diagnostics substrate, causal-OS north star, failure-pattern register, GY and Atlas plans, and the distillation ledger. The focused owner walk then covered GY-O1/O2/O3, N8 value carriers, S13 post-deploy accountability, DDM detectors and FDR, `WorldModelRecord`, Fabric world/time-travel, and Fabric quarantine.

A GitHub recursive-tree endpoint was invoked at the pinned tree and canonical directories were enumerated through the Contents API. Ordinary Git transport could not resolve `github.com`, so this environment did not execute a local `rg`/`git grep` complete scripted census. Connector search is not a P35 denominator. This package therefore makes no repository-wide zero claim; any unexecuted census is `not_established`. Positive baseline findings come from exact canonical files.

### 2.2 The zone is not wholly greenfield at this pin

The repository already contains a typed post-deployment attribution surface. `DivergenceAttributionClass` has eight values — `design_error`, `evidence_error`, `regime_error`, `coupling_error`, `world_change`, `strategic_response`, `implementation_failure`, and `unattributable` — and `DivergenceRecord` carries that class, attribution status, evidence refs, learning eligibility, authority boundary, and accountability fields (`policy-engine/src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py:43-58`, `:164-221`). Canonical S13 fixtures supply `attribution_class` and `attribution_status` (`policy-engine/tests/fixtures/layer2/s13/s13_post_deploy_case_signals.json:4-204`).

Therefore the global sentence “there is no typed diagnosis anywhere” would be false. The narrower task-relevant sentence is supported: the inspected S13 producer validates a supplied accountability/model-lane label; it does not derive the joint INT-R4/OPS-R5 movement diagnosis from a concrete realized-versus-predicted comparison. The prompt's “truly greenfield” orientation is corrected to the exact admitted diagnosis-and-update chain, not every adjacent post-deployment primitive.

### 2.3 GY status and the written riders

The active GY plan labels O1, O2 and O3 `build-new`. O1 requires a cause-typed realized-versus-predicted delta before posterior updating; O2 routes anomalies through DDM/FDR as low-authority hypotheses; O3 writes only confirmed findings into a versioned world branch and carries the self-confirmation red fixture (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:5043-5095`). The same plan states that the O-block must not close while INT-R4 is undelivered unless its riders are independently satisfied and recorded (`:5020-5033`). Plan text is a gate intention, not implementation evidence.

### 2.4 Typed effect/outcome carriers exist

The generation-cycle value path has strict typed carriers:

- `ValueGateReceipt` binds candidate, evaluation mode, selected method, identification status, `ValueOuterSet`, transport and calibration receipts, world-model content hash, value ref and timing (`policy-engine/src/polisyos/runtime/quality/generation_cycle.py:416-499`);
- `ValuePortObservation` represents pending, ready and blocked value states and cannot carry a receipt while blocked or pending (`:500-568`);
- `ValueOuterSet` metrics retain interval, subgroup, provenance, uncertainty, observation-time and validity structure (`policy-engine/src/polisyos/core/contracts/value_outer_set.py:1-300`).

These are suitable inputs for a generic comparison. They do not yet bind a later realized observation to the exact predicted carrier, treatment history, measurement schema, exposure mapping, and diagnosis record.

### 2.5 DDM detects and localizes; it does not establish the cause

The DDM substrate is substantial:

- `ShiftDetectedEvent` requires calibrated evidence and stationarity information; `ShiftRiskEvent` maps it to local risk posture (`policy-engine/src/polisyos/ddm/integration/events.py:43-119`);
- realized binary/regression monitors compute estimates, 95% intervals, and p50/p90 label delays (`policy-engine/src/polisyos/ddm/detectors/realized_performance_monitor.py:1-151`);
- data-quality checks cover schema, null, type, range, allowed values, and freshness (`policy-engine/src/polisyos/ddm/detectors/data_quality_monitor.py:1-142`);
- the Track-2.2 adapter retains calibrated p-value/e-value/ERT evidence (`policy-engine/src/polisyos/ddm/detectors/track_2_2_shift_adapter.py:1-62`);
- `MultipleTestingPlan` and `OnlineFDRController` implement conservative family allocation and alpha-wealth (`policy-engine/src/polisyos/ddm/calibration/multiple_testing.py:1-89`);
- `RootCauseBundle` groups shift/degradation IDs, features/slices, upstream versions, quality violations, stationarity regimes, and calibration IDs (`policy-engine/src/polisyos/ddm/integration/events.py:213-232`).

The module explicitly keeps drift, degradation, data quality, and readiness separate so drift is not silently treated as a retraining trigger (`events.py:1-7`). This is a strong reuse seam. But `RootCauseBundle` localizes evidence; it does not prove `prediction_error`, observation-process causation, implementation/version divergence, behavioral response, context/interference, or an unresolved decomposition.

### 2.6 Monitoring, world storage, and quarantine are adjacent substrates

`ImplementationMonitoringEvaluationRecord` binds implementation, monitoring, evaluation, DDM evidence, claim links, and publication ordering (`policy-engine/src/polisyos/runtime/quality/ddm_monitoring.py:1-287`). Continuous governance types source invalidation, calibration/fairness/context drift, and incidents and maps them to monitoring, stale, review, reissue, or withdrawal-review recommendations (`policy-engine/src/polisyos/scientist/governance/continuous/monitors.py:1-113`).

Fabric world facts use append-only assertion/correction/revocation and governed branches (`policy-engine/docs/reference/fabric/time-travel.md:1-78`). `WorldModelRecord` has `deployment_update`, but its update refs are forward hooks; the record binds existing substrates rather than executing updates (`policy-engine/src/polisyos/runtime/quality/world_model_record.py:1-7`, `:58-68`, `:185-239`). Fabric quarantine persists an immutable record, payload lineage, and deterministic reprocessing (`policy-engine/src/polisyos/fabric/data_plane/quarantine.py:1-106`, `:220-463`). Generic quarantine does not encode O3's permanent “never write this confirmation claim” rule or prove causal observation ancestry.

### 2.7 Baseline verdict

The repository has typed value carriers, calibrated detectors, delayed-label metrics, FDR, supplied S13 attribution labels, lifecycle recommendations, append-only world branches, provenance, and generic quarantine. The missing capability is the admitted chain:

```text
conditioned prediction + realized observation
→ comparison validity
→ evidence-derived movement diagnosis
→ update/response routing
→ competent authority where required
→ append-only posterior/world write or frozen/quarantined refusal
→ semantic replay and adversarial verification
```

No appointed institutional signer exists for that chain. The joint capability standing is `absent/unallocated`; adjacent components retain their own narrower standings. Coordinates and classified baseline findings are in [the INT-R4 evidence register](int-r4/evidence-register.md).

## 3. External Research Baseline

### 3.1 Source posture

The five commissioned surveys are `institutionally_supplied` research inputs relative to this package. Their source hierarchies distinguish primary standards/law, canonical papers, empirical studies, simulations, audits, and design recommendations, but this pass did not independently reproduce every underlying study. They establish possible mechanisms, costs, disagreements, and identification limits. They establish no repository capability and register no PolicyOS vocabulary.

| ID | Supplied survey | Primary contribution |
|---|---|---|
| S1 | *Identification When Policy Changes Its Own Evidence* | Latent outcome versus observation, selection, and response; self-confirmation; identification strategies. |
| S2 | *Graded Response To New Evidence* | Sequential adaptation, versions, stopping, reversibility, and exploratory/confirmatory boundaries. |
| S3 | *How Mature Monitoring Regimes Decide Why A Number Moved* | Cross-domain vocabularies, residue policies, detector-versus-diagnosis, and classification reliability. |
| S4 | *Metric As A Governed Contract* | KPI contract fields, Goodhart/Campbell mechanisms, role separation, and decision rights. |
| S5 | *Delayed, Unreported, Distributed And Spillover Harm* | Delayed/censored harm, absent channels, subgroups, interference, and sentinel health. |

### 3.2 Findings stable across the surveys

1. **A changed observed quantity is not self-interpreting.** S1 models the recorded value as a function of latent outcome, measurement, selection, behavioral response, and policy. Policy-caused observation/selection/response means movement in the recorded value alone does not identify movement in the latent target (S1:5-33, 70-122, 256-383).
2. **Detector output is not a cause label.** SPC, epidemiology, SRE, and experimentation distinguish signal from cause. The strongest transferable rule is causal typing before learning, not causal typing before every protective action (S3:5-41, 43-79, 183-287, 330-379).
3. **The same numeric delta selects different operators according to cause.** Official-statistics revisions, accounting estimate/error distinctions, experiment trust failures, and pharmacovigilance causality states all route similar numerical changes differently (S3:43-130, 289-321).
4. **The observation process becomes part of the causal system after deployment.** Independent sensors, dual runs, selection-margin accounting, observation-intensity normalization, negative controls, and randomized probes test whether evidence concerns the target or its production (S1:35-68, 112-122).
5. **Unknown is a legitimate terminal.** Without independent measurement, randomized variation, valid proxy, or structural restriction, latent-outcome and observation-process effects are generally not separable; more rows from the same contaminated pipeline do not close the gap (S1:256-268; S3:89-112, 132-181; S5:253-300).

### 3.3 Disagreements preserved

- SRE, aviation, and safety monitoring may contain harm before root cause; experimentation freezes inference; SPC warns against tampering. The purpose-specific rule is: uncertainty can license protective containment under authority, but not substantive model learning.
- Epidemiology, SRE, official-statistics revisions, and experimentation often permit multiple contributors. A single routing label is defensible only when contributors are retained and incompatible unresolved routes fail closed.
- Negative controls are mainly diagnostics in one tradition and can identify effects only under stronger bridge/completeness assumptions in another. Null success is not automatic proof of no bias.
- Reject inference relies on modeling assumptions; controlled exploration creates missing labels but costs exposure, money, and sometimes ethical permission.
- NHS and education evidence shows beneficial target effects can coexist with bunching, score inflation, selection, and effort substitution. A target-linked metric is not automatically invalid, but cannot validate itself alone.

### 3.4 Sequential adaptation, interference, and delayed harm

After `A0 → A1 → A2`, “the effect of the intervention” is not one estimand unless the object is fixed: a specific version, a declared distribution over versions, or a dynamic policy rule. Version assignment may be endogenous to prior outcomes; unplanned versions do not inherit confirmatory status. Intervention artifact, eligibility/scope, decision rule, outcome definition, exposure history, measurement pipeline, adaptation trigger, concurrent interventions, and the claim attached to release all require version identity (S2:214-301).

Interference changes the unit and denominator. Controls can be contaminated and displacement can make local improvement overstate system benefit. Exposure mapping and cluster/network designs help only when exposure structure is declared and sufficiently observed (S1:41-48, 58-66; S5:179-251).

Absence of recorded harm is informative only relative to latency and detection probability. Exited, rejected, never-entered, and neighboring populations may have zero inclusion probability. Honest reporting distinguishes observed harm, model-estimated missing harm, and unquantified exposure (S5:5-19, 21-131, 133-251, 253-300).

### 3.5 Evidence-grade conclusion

The surveys support a research-level routing discipline, not a validated universal classifier. No surveyed regime supplies the exact vocabulary required here, no cross-domain base rate for the unresolved class exists, and cause-label reliability is rarely measured. The result below is a bounded candidate vocabulary with operational tests and an unresolved terminal, not a registered standard or proven automated adjudicator.

## 4. Result

### 4.1 Result type and vocabulary ownership

**Result: `accepted_narrow_scope`.** This deliverable defines one candidate **Shared Movement Diagnosis Vocabulary (SMDV-1)** for INT-R4 and OPS-R5. This section is its sole derivation and owner. OPS-R5 imports SMDV-1 by reference; it does not define another vocabulary.

SMDV-1 decides whether an observed movement is admissible evidence about a predictive mechanism and routes non-model explanations. It is not a registered vocabulary, production schema, automated classifier, or authority grant.

### 4.2 A comparison object precedes the category

A diagnosis is void unless a `MovementComparison` identifies at least:

```text
prediction/effect carrier and content identity
estimand and target construct
predicted distribution, interval, or set
intervention artifact and rule version
intended and realized eligibility, dose, exposure, and implementation trace
population and subgroup frame
observation definition, instrument, schema, and pipeline versions
observation, valid, transaction, and decision times
follow-up maturity, censoring, and missingness posture
context/concurrent-policy version and interference/exposure map
behavioral-response hypothesis
calibration, identification, and uncertainty basis
```

`realized - predicted` is only one projection and may be undefined for interval-, set-, or distribution-valued carriers. Scalar coercion is not conformance.

### 4.3 Seven terminal primary classes

| Class | Meaning | Operational assignment test | Effect-posterior consequence |
|---|---|---|---|
| `expected_variation` | Realized observation is model-compatible under the declared predictive and measurement envelope; no material observation, intervention, context/interference, or behavior divergence is established. | Comparison evaluable; measurement health passes; realized intervention matches version; context/exposure inside envelope; predeclared posterior-predictive or equivalent check remains compatible. | No discrepancy-driven repair. It may enter only a separately predeclared routine likelihood/calibration schedule. |
| `observation_process_change` | The mapping from latent outcome to recorded evidence changed: definition, instrument, coding, reporting/testing intensity, selection, denominator, attrition/censoring, joins, revision, or data availability. | Version/change record, dual run, bridge/backcast, sentinel divergence, selection-margin or intensity change, negative-control failure, or equivalent evidence establishes a material observation-path change. | Freeze substantive effect update unless an independent identification bridge recovers the latent-outcome estimand; route to measurement/semantic epoch. |
| `intervention_delivery_or_version` | The compared intervention is not the predicted intervention: delivery/fidelity failure, eligibility/scope/dose/exposure change, deliberate version change, or altered adaptive rule. | Content-bound intended-versus-delivered comparison and exposure history establish material mismatch. | Do not update the old-version posterior from the mixed delta; route to delivery/version evaluation or new estimand. |
| `behavioral_response` | Actors respond to policy, target, or disclosure in a way that changes substantive outcome or treatment uptake: adaptation, gaming, avoidance, substitution, or strategy. | Independently supported path `policy → response → latent outcome/exposure`, not merely reporting/inclusion change. | Route to response/mechanism model. Old posterior updates only if its estimand includes the response and identification remains valid. |
| `context_or_interference` | Movement is materially attributable to external world change, concurrent policy, regime shift, network/geographic spillover, equilibrium effect, control contamination, or other-unit exposure absent from the prediction. | Context/version comparison, concurrent-intervention ledger, exposure mapping, neighbor/saturation evidence, or transport/regime test establishes divergence. | Route to context/coupling/regime/interference model; no clean unit-level prediction-error update. |
| `prediction_error` | After preceding gates pass, the remaining movement is admissible evidence about the predictive mechanism or effect parameters. It is a model-relevant innovation, not automatically misspecification. | Observation stable/bridged; intended version/exposure established; context/interference and behavior absent, modeled, or identified; outcome mature; identification valid; residual remains. | Eligible for the predeclared effect-posterior proposal, still subject to provenance, calibration, power/maturity, authority, and human-decision gates. |
| `diagnosis_unresolved` | Evidence is missing, contradictory, immature, or compatible with multiple materially different primary explanations that cannot be ordered. | A decisive predicate is not established; no unique primary survives falsification; or latent-outcome/observation decomposition is nonidentified. | Freeze substantive posterior and edge update. Protective containment, investigation, acquisition, annotation, or publication downgrade may proceed separately. |

### 4.4 Precedence and multi-causality

The assignment precedence is:

```text
0 establish comparison identity, maturity, and admissible evidence
1 test observation-process invariance and series comparability
2 test intended-versus-delivered intervention and version identity
3 test context, concurrent policy, and interference/exposure assumptions
4 test behavioral-response paths and whether they reach outcome or only observation
5 split model-compatible expected variation from remaining model-relevant prediction error
6 if no unique supported primary survives, diagnosis_unresolved
```

One `primary_class` is emitted for routing, with `contributing_classes`. A contributor that blocks learning remains blocking even when not primary. If contributors require incompatible routes and their relative contribution cannot be identified, primary is `diagnosis_unresolved`. Disjointness belongs to the assignment procedure; the causal record retains multi-causality.

### 4.5 Observation-process versus behavioral-response boundary

- `policy → behavior → latent outcome` is `behavioral_response`;
- `policy → behavior → reporting/testing/selection/coding → recorded evidence`, without independently identified latent-outcome change, is `observation_process_change` with behavioral contributor;
- both paths established: use `behavioral_response` as primary only when an independent outcome channel identifies the substantive path; retain observation change as blocking contributor and remove its contamination before learning;
- paths plausible but inseparable: `diagnosis_unresolved`.

Thus more reporting cannot become more underlying events, while a real behavioral effect is not dismissed merely because reporting also changed.

### 4.6 Bounded exhaustiveness and residue

SMDV-1 is exhaustive only relative to a declared comparison graph with material departure locations at observation process, intervention/delivery/version, behavior, context/interference, predictive mechanism, plus model-compatible variation. It is not an ontology of every physical cause.

The unresolved terminal is not a vacuous catch-all because it freezes learning, names competing classes and the missing discriminator, identifies next evidence, carries a clock, and has both false-pass and false-block falsifiers. No defensible cross-domain production proportion is available; production prevalence is `not_established`, not zero. The 24-case benchmark below deliberately assigns 8/24 cases (33⅓% of that test population) to unresolved/compound conditions; that is a stress composition, not a prevalence estimate.

### 4.7 Mapping to S13 without duplicate ownership

| SMDV-1 | Nearest S13 lane | Mapping loss to retain |
|---|---|---|
| `expected_variation` | no learning divergence/accountability observation | S13 has no explicit model-compatible terminal. |
| `observation_process_change` | nearest `evidence_error` | Does not explicitly separate policy-caused ascertainment/selection from ordinary defects. |
| `intervention_delivery_or_version` | nearest `implementation_failure` | Planned version/rule/eligibility change is not necessarily failure. |
| `behavioral_response` | `strategic_response` | Non-adversarial adaptation and intended mediation may also belong. |
| `context_or_interference` | `world_change`, `regime_error`, or `coupling_error` | One movement class routes to several accountable model components. |
| `prediction_error` | later S13 component attribution | S13 is finer about destination component, not source of observed movement. |
| `diagnosis_unresolved` | `unattributable` / pending | Preserve resolvability and missing discriminator. |

Safe integration is two-stage: SMDV-1 establishes whether movement may inform the predictive mechanism; S13 routes an admitted model-relevant divergence to the accountable component.

### 4.8 Update rule

A substantive effect-posterior or candidate world edge may be proposed only when:

```text
primary_class == prediction_error
AND no blocking contributing class exists
AND comparison and identification statuses are positive
AND maturity / censoring / interference predicates pass
AND evidence provenance is recomputed or independently reconciled
AND update is inside a predeclared version-specific rule
AND required decision authority is established
```

`expected_variation` may feed only a separately predeclared routine update/calibration schedule; it does not license discrepancy-driven repair. All other classes route elsewhere. `diagnosis_unresolved` freezes learning but not necessarily protective action.

## 5. Counterexamples And Failure Modes

### 5.1 Audit of GY-O1's performativity rider

The rider remains unchanged in the GY plan; this package audits it.

| Question | Verdict | Evidence and consequence |
|---|---|---|
| **Is it correct?** | **Yes, for discrepancy-driven substantive learning, with one scope clarification.** | The surveys strongly support causal typing before learning: observation, selection, delivery/version, behavior, context/interference, and model error can produce the same residual. `diagnosis_unresolved` must not default to the effect. The clarification is that “only `prediction_error` may update the posterior” is correct for residual-triggered repair; it must not be read as banning a separately predeclared routine likelihood/calibration update under `expected_variation`. Protective containment is outside the learning freeze. |
| **Is it complete?** | **No.** | It omits `expected_variation`; observation/selection/reporting beyond the narrower word `measurement`; deliberate intervention, eligibility, and adaptive-rule versions; context/interference; delayed/censored/distributed harm; multiple contributors; comparison identity/maturity; and update authority. The four written classes are a useful safety minimum, not an exhaustive operational diagnosis. |
| **Is it operable?** | **No, not at the repository pin.** | Assignment needs content-bound prediction/realization, intervention/exposure/version evidence, observation schema/lineage, maturity/censoring, context/interference, response hypotheses, operational tests, and an admitted diagnosis producer. S13 fixtures supply their class rather than derive it. No appointed signer exists for governed updating. |

**O1 verdict:** `correct = yes_with_scope`; `complete = no`; `operable = no`.

This does not contradict the safety direction and does not trigger the early-stop rule. It does require an architect clarification before coding: whether “posterior update” names only discrepancy-driven repair or also routine predeclared assimilation. Under either meaning, a non-`prediction_error` residual must not be silently attributed to the effect.

### 5.2 Audit of GY-O3's self-confirmation negative

| Question | Verdict | Evidence and consequence |
|---|---|---|
| **Is it correct?** | **Yes.** | When policy changes observation, selection, reporting, coding, testing, or data availability, evidence produced only through that path is not independent confirmation of an outcome edge. The causal-feedback, selective-label, predictive-policing, coding, testing, and recommender evidence supports quarantine rather than write-back. |
| **Is it complete?** | **No.** | It omits mixed outcome-and-observation paths, policy-caused selection/missingness and intensity, behavior reaching both outcome and reporting, policy/measurement versions, spillover-contaminated controls, independent sentinels/holdouts, unresolved ancestry, and the permanent semantic difference between “never write this confirmation claim” and a generic dead-letter record that may later be reprocessed. |
| **Is it operable?** | **No, not at the repository pin.** | Fabric provenance shows origin but does not establish causal ancestry. No admitted producer determines whether policy caused the observation process that produced evidence, and generic quarantine lacks a consumer invariant preventing later edge admission. In some cases no method can separate the paths without new experimental or independent measurement design. |

**O3 verdict:** `correct = yes`; `complete = no`; `operable = no`.

The required determination graph is:

```text
policy / decision rule A(v)
  ├─→ latent outcome Y* ─→ confirming evidence D
  ├─→ observation / selection / reporting process O(s) ─→ D
  └─→ actor response R ─→ Y* and/or O(s)
```

Procedure:

1. bind candidate edge, target construct, policy version, outcome definition, and evidence artifact;
2. enumerate admissible policy-to-evidence paths under a versioned causal model and independent evidence;
3. test material observation/selection/reporting change using version records, independent sensors, dual runs, intensity, selection margins, controls, or randomized probes;
4. test whether any confirming path reaches the latent outcome through an identification basis not downstream of policy-caused observation;
5. if every admissible confirming path passes through policy-caused `O(s)` and no independent outcome path exists, mark `self_confirmation_observation_only`, quarantine, and prohibit edge write;
6. if substantive and observation paths coexist but cannot be separated, mark `observation_ancestry_unresolved`, quarantine, and freeze;
7. if an independent substantive path survives and observation invariance/bridge assumptions pass, this negative does not reject it, but every other O1/O3 gate still applies.

A declared DAG, field name, or producer assertion of independence is not evidence of the causal property. The P38 divergent case is a sensor with a different identifier but the same policy-caused source/selection mechanism.

### 5.3 Named failure modes

| ID | Unsafe implementation | Incorrect conclusion | Required safe result |
|---|---|---|---|
| `FM-01` | Coerce interval, set, subgroup vector, or distribution to one scalar delta. | Typed carriers are comparable because subtraction returned a number. | Carrier-specific comparison or typed refusal. |
| `FM-02` | Treat calibrated shift, FDR discovery, degradation, or `RootCauseBundle` as cause. | Detector proves `prediction_error`. | Candidate signal; open diagnosis. |
| `FM-03` | Tune after every model-compatible realization. | Normal variation is a mechanism defect. | `expected_variation`; no discrepancy repair. |
| `FM-04` | Pool `A(v)` and `A(v+1)` under one policy name. | Later outcomes validate the earlier treatment. | Version diagnosis and new/prespecified pooled estimand. |
| `FM-05` | Read behavior-induced reporting as substantive outcome. | More reports mean more latent events. | Observation change, contributor, or unresolved. |
| `FM-06` | Dismiss genuine behavioral outcome effect because reporting also changed. | No substantive response occurred. | Independent outcome channel; retain both contributors or unresolved. |
| `FM-07` | Ignore neighbors, concurrent policy, or changing exposure network. | Local residual is clean unit-level model error. | Context/interference or unresolved. |
| `FM-08` | Close safety after a short window or complete cases only. | No recorded harm means no delayed/censored harm. | Immature/unquantified posture. |
| `FM-09` | Treat denied/exited/never-entered people as zero harm. | Production denominator equals population at risk. | External-frame acquisition or unquantified exposure. |
| `FM-10` | Accept policy-created field/event density as confirmation. | The model predicted what deployment caused the database to record. | Permanent confirmation quarantine; no edge write. |
| `FM-11` | Reprocess generic quarantine after code repair without semantic re-admission. | Parseability restores admissibility. | Consumer-side never-write invariant. |
| `FM-12` | Force one cause when incompatible routes remain plausible. | Taxonomic neatness substitutes for identification. | `diagnosis_unresolved` plus missing discriminator. |
| `FM-13` | Let supplied class, owner string, or declared independence satisfy gate. | Presence establishes causal property. | Recompute/independently reconcile or fail closed. |
| `FM-14` | Let emergency response become effect evidence. | Correct protection proves hypothesized mechanism. | Separate protection, diagnosis, and learning records. |

## 6. Benchmark Or Fixture Proposal

### 6.1 Joint benchmark structure and fixed denominator

The proposal has two linked layers:

1. movement-diagnosis corpus — owned here and consumed by OPS-R5;
2. response/write-back corpus — applies each diagnosis to OPS-R5 transitions and O1/O3 admission.

The movement corpus contains **24 synthetic cases**. This is an adversarial test population, not a prevalence study:

| Expected primary terminal | Cases | Purpose |
|---|---:|---|
| `expected_variation` | 3 | Positive control against tampering. |
| `observation_process_change` | 3 | Definition, selection, and intensity changes. |
| `intervention_delivery_or_version` | 3 | Failed delivery, planned version, adaptive-rule change. |
| `behavioral_response` | 3 | Adaptation, gaming, substitution. |
| `context_or_interference` | 2 | Spillover and concurrent-world change. |
| `prediction_error` | 2 | Positive controls for admitted model-relevant residuals. |
| `diagnosis_unresolved` | 8 | Missing discriminator, mixed path, immature harm, zero-inclusion. |
| **Total** | **24** | Fixed fixture denominator. |

The 8/24 unresolved share is a stress choice, not a production estimate.

### 6.2 Required case packet

Every fixture carries:

```text
case identity and frozen semantic description
prediction/effect carrier and content identity
predicted distribution, interval, or set
estimand, construct, population
intervention, eligibility, rule, and exposure versions
realized observation and all relevant time roles
measurement definition, instrument, schema, and pipeline versions
implementation/fidelity evidence
context, concurrent-policy, and exposure-map evidence
behavioral hypotheses and intermediates
maturity, latency, censoring, attrition, and missing-channel posture
sentinel / negative-control / holdout evidence
causal graph plus evidence for decisive edges
sealed expected primary and contributing classes
missing discriminator and next evidence for unresolved cases
permitted and forbidden update/write actions
```

Expected result is an admissibility judgment, not metaphysical truth.

### 6.3 Core fixture families

The corpus includes:

- high-stakes metric improves while independent low-stakes sentinel does not;
- recorded incidents rise with patrol/inspection hours while independent victimization is flat;
- definition/schema change creates a historical jump, with and without a bridge;
- delivery reaches only half the intended population;
- planned eligibility change is mislabelled implementation failure;
- adaptive rule assigns later versions based on prior bad outcomes;
- actors substitute effort from unmeasured outcome to targeted proxy;
- behavior changes reporting only, and a paired case changes outcome plus reporting;
- spillover contaminates controls and displaces harm;
- concurrent policy changes the same target;
- mature independently measured residual with stable delivery/context yields `prediction_error`;
- model-compatible realization must not trigger tuning;
- delayed harm before latency horizon;
- informative exit and denied population with zero observation probability;
- duplicate/out-of-order corrections and conflicting sensors;
- owner-supplied “independent” sensor sharing the same policy-caused source;
- independence markers retained while the real property is removed.

### 6.4 Frozen O3 red fixture

```text
candidate edge: targeted enforcement intensity → latent incidence
policy: allocate inspection/patrol according to the candidate edge
post-policy change: observation intensity and discovered-event logging increase
observed result: discovered events rise in targeted areas
independent channel: absent or unchanged
unsafe path: treats denser discovered-event stream as confirmation
required result:
  diagnosis = observation_process_change
  observation_ancestry = self_confirmation_observation_only
  effect_update_allowed = false
  world_edge_write_allowed = false
  quarantine_semantics = permanent_for_this_confirmation_claim
```

The test must exercise the actual world-write consumer. Removing the prohibition while retaining names, refs, and quarantine markers must turn it red. Later independent evidence creates a new confirmation record; it must not rewrite the historical quarantine.

### 6.5 Metamorphic and operational variants

Each base case produces variants with changed IDs/wording, false declared premise, exchanged version times, duplicate event, correction-before-original, owner unavailable/after-hours, valid schema hiding policy-caused selection, “independent” sensor sharing upstream source, new subgroup/neighbor, retained old claim ref on a new treatment, and false `prediction_error` declaration.

### 6.6 Measures and non-compensable guardrails

Over the fixed 24-case population and generated variants:

```text
unsafe_posterior_update_count
unsafe_world_edge_write_count
false_freeze_count
primary_class_accuracy
blocking_contributor_recall
unresolved_false_pass_count
unresolved_false_block_count
self_confirmation_escape_count
version_laundering_count
measurement_behavior_boundary_error_count
historical_rewrite_count
time_to_correct_diagnosis
rater_agreement on independently adjudicated packets
```

Unsafe update/write counts are non-compensable.

### 6.7 Research acceptance proxy

A later prototype may claim only benchmark conformance when all 24 packets and adjacent variants are processed; unsafe posterior/world writes and self-confirmation escapes are zero; unresolved cases name competing classes and missing discriminator; both prediction-error controls reach an update **proposal**; expected-variation controls refuse discrepancy tuning; remove-the-property/keep-the-markers probes go red; and rater disagreements are retained/adjudicated. Production thresholds for accuracy, agreement, or latency are not set here; they require a domain, consequence model, independent oracle, and appointed authority.

## 7. Artifact Contract Sketch

## 8. Later Integration Handoff

## 9. Promotion And Kill Rules

## 10. Open Questions For Consolidation
