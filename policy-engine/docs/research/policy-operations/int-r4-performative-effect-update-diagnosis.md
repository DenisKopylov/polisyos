---
title: INT-R4 — Performativity-Safe Effect Updating
status: stage_1_research_complete
kind: deep-research
research_task: INT-R4
joint_with: OPS-R5
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r4-ops-r5-research
repository_baseline: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
inspection_date: 2026-08-29
research_only: true
shared_vocabulary_owner: true
shared_vocabulary: SMDV-1
shared_vocabulary_location: section_4
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

INT-R4 asks what causal-safety case is required before post-deployment evidence may update an effect posterior when the deployed policy can change behavior, selection, measurement, reporting, data availability, or interference. It absorbs OPS-R7: causal validity under sequential policy adaptations, including treatment versions, interference, and stopping rules. It is the binding research input for GY-O1 and GY-O3 and is explicitly joint with OPS-R5 (`policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:485-492`).

The pair has one substantive object: a typed explanation of why an observed quantity moved. This document owns the sole derivation of the candidate vocabulary. OPS-R5 cites §4; it does not restate, fork, or independently alter the classes, precedence, exhaustiveness boundary, or unresolved residue.

### 1.2 Four-way custody boundary

The ratified identity makes the post-deployment learning loop OWN-core because an unsafe update can silently invalidate a PolicyOS-signed justification. Deployment execution, field data collection, adjudication, and institutional sign-off remain external. PolicyOS owns the typed integrate-evidence contract, fail-closed admission, update refusal, provenance, historical replay, and consequences for its own claims. It does not become an administrator, executor, court, case-management system, or sovereign decision-maker (`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:23-124`).

### 1.3 Exact controlled operation

The controlled operation is not “observe a residual.” It is:

> admit a realized-versus-predicted comparison as evidence that may change a substantive effect posterior or a world-model edge.

The comparison is meaningful only when it names the prediction/effect carrier, estimand, intervention version, population, exposure history, observation definition/version, horizon, uncertainty basis, and interference assumptions. A scalar delta without those conditionals is not admissible.

### 1.4 False production claim prevented

This task prevents the claim:

> “The observed number moved after deployment, therefore the policy's predicted effect was wrong or a new causal edge was confirmed.”

That statement is unsafe whenever deployment changed who was observed, how the outcome was measured, which intervention version was delivered, how actors responded, or which other units/policies affected the outcome.

### 1.5 Absorbed OPS-R7 coverage

OPS-R7 is covered as follows:

- treatment and decision-rule versions: §§3.4, 4, 5, 7, 9;
- endogenous sequential adaptation: §§3.4, 4, 5, 9;
- interference and exposure mapping: §§3.4, 4, 5, 7;
- stopping, repeated looks, exploratory-to-confirmatory promotion: §§3.3–3.5, 4.8, 6, 9;
- carryover, delayed/censored/distributed harm: §§3.4, 4, 5, 6, 7.

Absorption is coverage only; it moves no capability and appoints no owner.

## 2. Current Repo Baseline

### 2.1 Pin and inspection boundary

Repository evidence is pinned to `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`. The mandatory architecture anchors were inspected: `AGENTS.md`; `policy-engine/CONTRIBUTING.md`; the ratified identity decision; organizing rules; target architecture; operating model; honest-diagnostics substrate; causal-OS north star; failure-pattern register; GY and Atlas plans; distillation ledger; and focused owner paths for N8 value carriers, S13, DDM/FDR, monitoring/evaluation, world records, Fabric time-travel, and quarantine.

A GitHub recursive-tree endpoint and canonical directory listings were used. Ordinary Git transport could not resolve `github.com`, so no local P35-compliant complete `rg`/`git grep` census was executed. Connector search is not a denominator. This package therefore makes no repository-wide zero claim; the unexecuted census is `not_established`. Positive findings use exact canonical file coordinates. The detailed baseline ledger is [int-r4/evidence-register.md](int-r4/evidence-register.md).

### 2.2 Orientation correction: adjacent typed attribution exists

The repository already has a typed post-deployment attribution surface. `DivergenceAttributionClass` contains `design_error`, `evidence_error`, `regime_error`, `coupling_error`, `world_change`, `strategic_response`, `implementation_failure`, and `unattributable`; `DivergenceRecord` carries class, attribution status, evidence refs, learning eligibility, authority boundary, and accountability fields (`policy-engine/src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py:43-58`, `:164-221`). Canonical fixtures supply `attribution_class` and `attribution_status` (`policy-engine/tests/fixtures/layer2/s13/s13_post_deploy_case_signals.json:4-204`).

Therefore “no typed diagnosis anywhere” is false at this pin. The narrower task-relevant statement is supported: the inspected S13 path validates a supplied accountability/model-lane label; it does not derive the joint INT-R4/OPS-R5 movement diagnosis from a concrete conditioned comparison. The prompt's “truly greenfield” statement is narrowed to the exact admitted diagnosis/update chain.

### 2.3 GY riders are written, not implemented

GY labels O1, O2, and O3 `build-new`. O1 requires cause typing before posterior updating; O2 keeps DDM/FDR anomalies low-authority; O3 writes only confirmed findings and carries the self-confirmation negative (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:5043-5095`). The O-block must not close while INT-R4 is undelivered unless its riders are independently satisfied and recorded (`:5020-5033`). Plan text is an intended gate, not capability evidence.

### 2.4 Typed value/effect carriers exist

`ValueGateReceipt` binds candidate, evaluation mode, method, identification, `ValueOuterSet`, transport/calibration receipts, world-model hash, value ref, and time; `ValuePortObservation` preserves ready/pending/blocked states (`policy-engine/src/polisyos/runtime/quality/generation_cycle.py:416-568`). `ValueOuterSet` metrics retain intervals, subgroups, provenance, uncertainty, observation time, and validity (`policy-engine/src/polisyos/core/contracts/value_outer_set.py:1-300`).

These are suitable generic inputs. They do not bind a later realized observation to the exact prediction, treatment history, measurement schema, exposure map, and diagnosis record. Scalar-only comparison would be unusable for these carriers.

### 2.5 DDM detects and localizes; it does not establish cause

DDM separately represents calibrated shift, realized/estimated degradation, data-quality failure, readiness, incidents, and root-cause localization (`policy-engine/src/polisyos/ddm/integration/events.py:1-232`). Realized monitors retain 95% intervals and p50/p90 label delays (`policy-engine/src/polisyos/ddm/detectors/realized_performance_monitor.py:1-151`); data-quality checks cover schema/null/type/range/value/freshness (`data_quality_monitor.py:1-142`); online FDR and conservative allocation exist (`calibration/multiple_testing.py:1-89`).

`RootCauseBundle` localizes features, slices, versions, quality violations, stationarity regimes, and calibration refs. It does not prove `prediction_error`, policy-caused observation, intervention/version mismatch, behavioral response, context/interference, or nonidentifiability. The module's own separation of drift from retraining is a strong reuse seam and an explicit warning against detector-to-cause collapse.

### 2.6 Monitoring, world storage, and quarantine are reusable fragments

`ImplementationMonitoringEvaluationRecord` binds implementation, monitoring, evaluation, DDM evidence, claim links, and publication ordering (`policy-engine/src/polisyos/runtime/quality/ddm_monitoring.py:1-287`). Continuous governance types source invalidation, calibration/fairness/context drift, and incidents and maps them to monitoring/stale/review/reissue/withdrawal-review recommendations (`policy-engine/src/polisyos/scientist/governance/continuous/monitors.py:1-113`).

Fabric preserves append-only assertion/correction/revocation and governed branches (`policy-engine/docs/reference/fabric/time-travel.md:1-78`). `WorldModelRecord.deployment_update_refs` are forward hooks rather than an update executor (`policy-engine/src/polisyos/runtime/quality/world_model_record.py:58-68`, `:185-239`). Generic CAS quarantine persists record/payload/reprocess lineage (`policy-engine/src/polisyos/fabric/data_plane/quarantine.py:1-106`, `:220-463`) but does not prove causal ancestry or encode O3's permanent “never write this confirmation claim” invariant.

### 2.7 Current capability label and reuse-first path

The repository has strong fragments, but no admitted chain:

```text
conditioned prediction + realized observation
→ comparison validity
→ evidence-derived movement diagnosis
→ update/response routing
→ competent authority where required
→ append-only posterior/world write or frozen/quarantined refusal
→ replay and adversarial verification
```

No appointed institutional signer exists. Joint capability standing is `absent/unallocated`. The smallest visible reuse path is N8 carriers + DDM evidence + monitoring record → a narrow movement-diagnosis producer beside S13 → GY-O1 admission → GY-O3/Fabric write consumer, with Atlas projection. It must extend existing owners rather than create a parallel post-deployment platform.

## 3. External Research Baseline

### 3.1 Source posture

Five commissioned surveys are `institutionally_supplied` to this researcher. They distinguish standards/law, canonical papers, empirical studies, simulations, audits, and recommendations, but this pass did not independently reproduce every underlying study. They establish possible mechanisms, costs, disagreements, and identification limits—not repository capability, registered vocabulary, or authority.

| ID | Survey | Contribution |
|---|---|---|
| S1 | *Identification When Policy Changes Its Own Evidence* | Latent outcome versus observation/selection/response; self-confirmation; identification strategies. |
| S2 | *Graded Response To New Evidence* | Versions, sequential adaptation, stopping, promotion, and reversibility. |
| S3 | *How Mature Monitoring Regimes Decide Why A Number Moved* | Cross-domain vocabularies, residue policies, detector/diagnosis boundary, reliability. |
| S4 | *Metric As A Governed Contract* | Metric-contract fields, Goodhart/Campbell mechanisms, role and decision rights. |
| S5 | *Delayed, Unreported, Distributed And Spillover Harm* | Censoring, absent channels, latency, subgroups, spillover, sentinel health. |

### 3.2 Stable findings

1. **Observed movement is not self-interpreting.** S1 formalizes recorded outcome as a function of latent outcome, measurement, selection, response, and policy. Policy-caused observation/selection means recorded movement alone does not identify latent movement (S1:5-33, 70-122, 256-383).
2. **Detector output is not cause.** SPC, epidemiology, SRE, and experimentation separate signal from cause. Causal typing before learning is well supported; causal typing before every protective action is not (S3:5-41, 43-79, 183-287, 330-379).
3. **Same number, different operator.** Official-statistics revisions, accounting estimate/error distinctions, experiment trust failures, and pharmacovigilance causality route similar deltas differently (S3:43-130, 289-321).
4. **Observation becomes causal after deployment.** Independent sensors, dual runs, selection margins, observation intensity, negative controls, and randomized probes distinguish target movement from evidence-production movement (S1:35-68, 112-122).
5. **Unknown is legitimate.** Without independent measurement, randomized variation, valid proxy, or structural restriction, latent-outcome and observation-process effects may be nonidentified; more contaminated rows do not solve this (S1:256-268; S3:89-112, 132-181; S5:253-300).

### 3.3 Disagreements retained

- SRE/aviation/safety may contain before root cause; experimentation freezes inference; SPC warns against tampering. This package separates protective action from learning.
- Epidemiology, SRE, revisions, and experimentation permit multiple contributors. A primary routing class is acceptable only with retained contributors and unresolved fallback.
- Negative controls diagnose in one tradition and identify only under stronger bridge/completeness conditions in another.
- Selective-label imputation and controlled exploration trade modeling assumptions against exposure/ethical cost.
- Target regimes can create real benefit and gaming simultaneously; a target-linked metric cannot validate itself alone.

### 3.4 OPS-R7: versions, interference, stopping, delayed harm

After `A0 → A1 → A2`, “effect of the intervention” is undefined unless the estimand names a version, a distribution over versions, or a dynamic rule. Endogenous version assignment and unplanned adaptation do not inherit confirmatory status. Intervention artifact, eligibility/scope, rule, outcome definition, exposure history, measurement pipeline, adaptation trigger, concurrent interventions, and claim version must be retained (S2:214-301).

Interference changes the unit and denominator; controls can be contaminated and local gains can be displacement. Exposure mapping helps only when network/geographic exposure is declared and observed (S1:41-48, 58-66; S5:179-251).

No recorded harm is informative only relative to latency and detection probability. Exited, rejected, never-entered, and neighboring people may have zero inclusion probability. Honest evidence separates observed, model-estimated missing, and unquantified exposure (S5:5-19, 21-131, 133-251, 253-300).

### 3.5 Evidence-grade conclusion

The literature supports a bounded routing discipline, not a validated cross-domain classifier. No surveyed regime supplies this exact vocabulary; unresolved prevalence is unknown; cause-label reliability is rarely measured. The result is therefore `accepted_narrow_scope`, research-only, and explicitly falsifiable.

## 4. Result

### 4.1 Shared Movement Diagnosis Vocabulary (SMDV-1)

This section is the sole derivation and owner of **SMDV-1**. OPS-R5 imports it by reference. SMDV-1 is a candidate rulebook for whether movement may inform a predictive mechanism and where non-model explanations route. It is not registered, implemented, or authoritative.

### 4.2 `MovementComparison` minimum

A diagnosis is void unless the comparison binds:

```text
prediction/effect carrier and content identity
estimand and target construct
predicted distribution, interval, or set
intervention artifact/rule version
intended and realized eligibility, dose, exposure, implementation
population and subgroup frame
observation definition, instrument, schema, pipeline versions
observation, valid, transaction, decision times
follow-up maturity, censoring, missingness
context/concurrent-policy version and exposure map
behavioral-response hypothesis
calibration, identification, uncertainty basis
```

`realized - predicted` is only one projection and may be undefined for interval-, set-, or distribution-valued carriers.

### 4.3 Seven terminal primary classes

| Class | Meaning | Operational assignment test | Learning consequence |
|---|---|---|---|
| `expected_variation` | Model-compatible realization under declared predictive/measurement envelope; no material observation, version, context/interference, or behavior divergence established. | Comparison evaluable; measurement health passes; intervention matches version; context/exposure in envelope; predeclared predictive check remains compatible. | No discrepancy-driven repair. May enter only a separately predeclared routine likelihood/calibration schedule. |
| `observation_process_change` | Mapping from latent target to recorded evidence changed: definition, instrument, coding, reporting/testing intensity, selection, denominator, attrition/censoring, join, revision, or availability. | Version/change evidence, dual run, bridge, sentinel divergence, selection/intensity shift, negative-control failure, or equivalent establishes material observation-path change. | Freeze substantive update unless an independent bridge identifies the latent estimand; route to measurement/semantic epoch. |
| `intervention_delivery_or_version` | Compared intervention is not predicted intervention: delivery/fidelity failure, eligibility/scope/dose/exposure change, planned version, or altered adaptive rule. | Content-bound intended-versus-delivered and exposure history establish mismatch. | No old-version update from mixed delta; route to delivery/version evaluation or new estimand. |
| `behavioral_response` | Actors adapt, game, avoid, substitute, or strategically respond in a way that changes substantive outcome or uptake. | Independently supported `policy → response → latent outcome/exposure`, not only reporting/inclusion. | Route to response/mechanism model; update only if estimand includes response and identification survives. |
| `context_or_interference` | External world/regime/concurrent policy/network spillover/equilibrium/control contamination or other-unit exposure absent from prediction materially contributes. | Context/version, concurrent-intervention, exposure-map, neighbor/saturation, or transport/regime evidence establishes divergence. | Route to context/coupling/regime/interference; no clean unit-level prediction-error update. |
| `prediction_error` | After prior gates, remaining movement is admissible model-relevant innovation about predictive mechanism/effect parameter. | Observation stable/bridged; intended version/exposure established; context/interference and behavior absent, modeled, or identified; outcome mature; identification valid; residual remains. | Eligible for predeclared update proposal, still subject to provenance, calibration, maturity, authority, and human-decision gates. |
| `diagnosis_unresolved` | Evidence missing, contradictory, immature, or compatible with materially different explanations that cannot be ordered. | Decisive predicate not established; no unique primary survives; or decomposition nonidentified. | Freeze posterior and edge write. Investigation, acquisition, annotation, downgrade, or authorized containment may proceed separately. |

### 4.4 Precedence, contributors, and disjointness

```text
0 establish comparison identity, maturity, admissible evidence
1 test observation-process invariance and comparability
2 test intended-versus-delivered intervention/version
3 test context, concurrent policy, interference/exposure
4 test behavioral paths and whether they reach outcome or observation
5 split expected variation from remaining model-relevant prediction error
6 no unique supported primary → diagnosis_unresolved
```

One `primary_class` routes the record; `contributing_classes` preserve multi-causality. A blocking contributor blocks learning even if not primary. Incompatible unresolved routes produce `diagnosis_unresolved`. Disjointness belongs to assignment precedence, not to an assertion that the world has one physical cause.

### 4.5 Observation-process versus behavior

- `policy → behavior → latent outcome` = `behavioral_response`;
- `policy → behavior → reporting/testing/selection/coding → evidence`, without independently identified latent change = `observation_process_change` with behavioral contributor;
- both established = behavioral primary only with independent outcome identification; observation contributor remains blocking until contamination is removed;
- plausible but inseparable = `diagnosis_unresolved`.

### 4.6 Bounded exhaustiveness and residue

SMDV-1 is exhaustive only relative to a declared comparison graph with departure locations at observation, intervention/version, behavior, context/interference, predictive mechanism, plus compatible variation. It is not an ontology of every cause. The unresolved terminal freezes learning, names competitors and missing discriminator, identifies next evidence, has a clock, and has false-pass/false-block falsifiers.

No defensible production proportion for unresolved cases exists; it is `not_established`. The benchmark deliberately assigns 8/24 cases (33⅓% of its synthetic population) to unresolved/compound conditions as a stress composition, not prevalence.

### 4.7 Mapping to S13 without duplicate ownership

| SMDV-1 | Nearest S13 lane | Required non-collapse |
|---|---|---|
| `expected_variation` | no learning divergence | S13 lacks explicit compatible terminal. |
| `observation_process_change` | nearest `evidence_error` | Preserve policy-caused ascertainment/selection versus ordinary evidence defect. |
| `intervention_delivery_or_version` | nearest `implementation_failure` | Planned version change is not necessarily failure. |
| `behavioral_response` | `strategic_response` | Preserve non-adversarial and intended mediation. |
| `context_or_interference` | `world_change` / `regime_error` / `coupling_error` | One movement class may route to several accountable components. |
| `prediction_error` | later S13 component attribution | S13 destination taxonomy is not movement-source diagnosis. |
| `diagnosis_unresolved` | `unattributable` / pending | Preserve resolvability and missing discriminator. |

SMDV-1 first decides whether movement may inform the predictive mechanism; S13 then routes admitted model-relevant divergence to an accountable component.

### 4.8 Update rule

```text
primary_class == prediction_error
AND no blocking contributor
AND comparison/identification positive
AND maturity/censoring/interference predicates pass
AND evidence provenance ∈ {recomputed, independently_reconciled}
AND update is predeclared and version-specific
AND required authority is established
```

`expected_variation` may enter only a separately predeclared routine update/calibration schedule. All other classes route elsewhere. Unresolved freezes learning, not necessarily protective action.

## 5. Counterexamples And Failure Modes

### 5.1 GY-O1 rider audit

| Question | Verdict | Finding |
|---|---|---|
| Correct? | **Yes, for discrepancy-driven learning, with scope clarification.** | Causal typing before learning and unresolved freeze are strongly supported. “Only prediction_error may update” must not be read as banning a separately predeclared routine update under `expected_variation`; protective containment is outside the learning freeze. |
| Complete? | **No.** | Missing expected variation; observation/selection/reporting beyond “measurement”; planned versions; context/interference; delayed/censored/distributed harm; contributors; comparison maturity; and update authority. |
| Operable? | **No at the pin.** | Needs content-bound comparison, version/exposure/observation evidence, tests, admitted producer, and signer. S13 fixtures supply class rather than derive it. |

**O1 verdict:** `correct = yes_with_scope`; `complete = no`; `operable = no`.

This does not contradict the rider's safety direction, so research continues. Architect clarification is required before implementation on whether “posterior update” means discrepancy repair only or also routine predeclared assimilation.

### 5.2 GY-O3 rider audit

| Question | Verdict | Finding |
|---|---|---|
| Correct? | **Yes.** | Evidence produced only through policy-caused observation/selection/reporting is not independent confirmation of an outcome edge and must not be written. |
| Complete? | **No.** | Missing mixed paths; selection/missingness/intensity; behavior reaching outcome and reporting; policy/measurement versions; spillover-contaminated controls; independent sentinels/holdouts; unresolved ancestry; permanent semantic quarantine. |
| Operable? | **No at the pin.** | Provenance is not causal ancestry; no admitted ancestry producer exists; generic quarantine lacks a never-write consumer invariant. Some cases require new experimental or independent measurement design and otherwise remain nonidentified. |

**O3 verdict:** `correct = yes`; `complete = no`; `operable = no`.

Required test graph:

```text
A(v) ─→ Y* ─→ D
  ├──→ O(s) ─→ D
  └──→ R ─→ Y* and/or O(s)
```

If every admissible confirming path passes through policy-caused `O(s)` and no independently identified `Y*` path exists, result is `self_confirmation_observation_only`: quarantine and never write. Mixed unseparated paths produce `observation_ancestry_unresolved`: quarantine and freeze. An independent substantive path merely survives this negative; it still passes every other gate. A differently named sensor sharing the same source/selection mechanism is the P38 divergent case.

### 5.3 Failure register

| ID | Unsafe conclusion | Safe result |
|---|---|---|
| `FM-01` | Scalar subtraction makes any typed carriers comparable. | Carrier-specific comparison or refusal. |
| `FM-02` | Shift/FDR/degradation/localization proves model error. | Candidate signal; diagnose. |
| `FM-03` | Every compatible realization requires tuning. | `expected_variation`; no discrepancy repair. |
| `FM-04` | Same policy name makes `v` and `v+1` one treatment. | Version diagnosis/new estimand. |
| `FM-05` | More policy-induced reporting means more latent outcome. | Observation change/contributor/unresolved. |
| `FM-06` | Reporting change means no substantive behavior effect. | Independent outcome channel or unresolved. |
| `FM-07` | Local residual ignores spillover/concurrent policy. | Context/interference. |
| `FM-08` | Quiet short window or complete cases prove no harm. | Immature/unquantified. |
| `FM-09` | Unobserved denied/exited population has zero harm. | External-frame acquisition/unquantified exposure. |
| `FM-10` | Policy-created event density confirms candidate edge. | Permanent confirmation quarantine; no write. |
| `FM-11` | Generic reprocessing restores semantic admissibility. | Consumer-side never-write invariant. |
| `FM-12` | One cause must be chosen despite incompatible evidence. | `diagnosis_unresolved`. |
| `FM-13` | Declared class/owner/independence satisfies gate. | Recompute/reconcile property or fail closed. |
| `FM-14` | Protective action proves causal theory. | Separate protection, diagnosis, learning. |

## 6. Benchmark Or Fixture Proposal

### 6.1 Fixed 24-case movement corpus

| Terminal | Cases | Purpose |
|---|---:|---|
| `expected_variation` | 3 | Tampering control. |
| `observation_process_change` | 3 | Definition, selection, intensity. |
| `intervention_delivery_or_version` | 3 | Delivery, planned version, adaptive rule. |
| `behavioral_response` | 3 | Adaptation, gaming, substitution. |
| `context_or_interference` | 2 | Spillover, concurrent world. |
| `prediction_error` | 2 | Positive model-relevant controls. |
| `diagnosis_unresolved` | 8 | Missing discriminator, mixed path, immature/zero-inclusion. |
| **Total** | **24** | Synthetic fixture denominator, not prevalence. |

Each packet binds prediction, estimand, typed carrier, treatment/exposure/version, population/subgroups, all time roles, measurement versions, implementation, context/exposure map, behavioral hypotheses, maturity/censoring/missingness, independent channels, causal-edge evidence, sealed expected primary/contributors, missing discriminator, and permitted/forbidden actions.

### 6.2 Fixture families

The set includes target/sentinel divergence; discovered events versus observation intensity; schema break with/without bridge; partial delivery; planned eligibility change; endogenous adaptive versions; effort substitution; behavior changing reporting only versus outcome plus reporting; spillover/control contamination; concurrent policy; clean prediction error; model-compatible realization; immature delayed harm; informative exit; zero-inclusion denied population; duplicate/out-of-order correction; conflicting sensors; falsely “independent” shared-source sensor; and remove-property/keep-markers probes.

### 6.3 Frozen O3 red fixture

```text
candidate edge: targeted enforcement intensity → latent incidence
policy: target patrol/inspection using candidate edge
post-policy: observation intensity and discovered-event logging rise
observed: discovered events rise in targeted area
independent channel: absent or unchanged
required:
  diagnosis = observation_process_change
  observation_ancestry = self_confirmation_observation_only
  effect_update_allowed = false
  world_edge_write_allowed = false
  quarantine = permanent_for_this_confirmation_claim
```

The test exercises the actual write consumer. Removing the prohibition while retaining markers must make it fail. Later independent evidence creates a new record; it never rewrites the historical quarantine.

### 6.4 Measures and acceptance proxy

Over 24 cases and generated variants:

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
independent-rater agreement
```

Unsafe update/write/self-confirmation counts are non-compensable and must be zero for prototype conformance. Both prediction-error controls must reach an update **proposal**; compatible controls must refuse discrepancy tuning; unresolved packets name competing classes and discriminator; property-removal probes go red. Production thresholds for accuracy/agreement/latency are not set here.

## 7. Artifact Contract Sketch

### 7.1 Candidate artifacts

These are research sketches and do not establish a canonical owner or production schema.

| Artifact | Minimum purpose and fields | Authority boundary |
|---|---|---|
| `MovementComparisonRecord` | Content-derived ID; case/claim/prediction refs; predicted and realized typed carriers; estimand; intervention/exposure/version; population/subgroups; observation definitions/versions; context/exposure map; maturity/censoring; all time roles; rule/schema refs. | Authoritative only for the identity and evaluability of this comparison; never for causal diagnosis or update. |
| `MovementDiagnosisRecord` | Comparison ref; SMDV-1 version; primary class; contributors; eliminated classes with tests/evidence; unresolved discriminator; next-evidence route; predicate-provenance labels; diagnosis time/expiry; human disagreement refs. | Authoritative only for a scoped diagnosis proposal after admitted evidence; never for policy execution or automatic update. |
| `ObservationAncestryAssessment` | Candidate edge/evidence refs; versioned policy-to-outcome and policy-to-observation paths; independent-channel tests; selection/intensity evidence; path status `substantive_independent`, `observation_only`, `mixed_unresolved`, or `not_established`. | Only for the O3 negative; it cannot positively establish the edge by itself. |
| `EffectUpdateAdmissionRecord` | Diagnosis ref; update target; prior/posterior or edge proposal refs; update-rule version; maturity/identification/provenance/authority gates; allowed/denied disposition; signer ref where required. | May authorize only the named update operation when all owner and authority predicates are independently admitted. |
| `SelfConfirmationQuarantineRecord` | Original comparison/edge/evidence refs; ancestry assessment; permanent reason; prohibited consumer operations; supersession relation; public/accountability projection; no mutation of original disposition. | Authoritative only for refusal of this confirmation claim; cannot be reprocessed into admission without a new independent evidence record. |

All governed identities should be derived from canonical content and input closure, not random UUIDs. Raw processing time does not enter semantic identity.

### 7.2 Local state machine — Operational addendum step 3

```text
comparison_pending
  → comparison_invalid                 missing/non-comparable identity; terminal until new input
  → diagnosis_pending
       → diagnosed_nonlearning          expected/observation/version/behavior/context
       → diagnosis_unresolved           frozen; acquire/reopen on discriminator or clock
       → self_confirmation_quarantined  permanent for this confirmation claim
       → prediction_error_admissible
            → update_proposed
                 → update_denied        terminal for this proposal; history retained
                 → update_authorized
                      → update_committed append-only posterior/edge version
                      → update_failed    retry only if idempotent; never infer success
```

Correction, revocation, new independent evidence, treatment/measurement version change, or rule change opens a new record or superseding transition; it does not overwrite historical meaning.

### 7.3 Time and expiry

Load-bearing roles: prediction time; intervention-rule effective time; exposure start/end; observation time; valid/transaction time of evidence; detection time; diagnosis time; diagnosis expiry/review clock; admission/authorization time; update-effective time; replay time. Delayed outcomes remain immature until a named horizon/event count; diagnosis and authority may expire independently.

### 7.4 Predicate provenance — P37/W4-K01

Every gate predicate is frozen at admission with one registered label:

- comparison identity and content closure;
- observation-process invariance/bridge validity;
- intended-versus-delivered version match;
- context/interference adequacy;
- behavioral-path evidence;
- outcome maturity/censoring adequacy;
- self-confirmation ancestry;
- signer competence/authority.

Only `recomputed` or `independently_reconciled` may carry a positive authority gate. `consumer_asserted`, `institutionally_supplied`, and `not_established` fail closed. A declaration that a sensor is independent is not the property.

### 7.5 Canonical-owner map

| Function | Existing/likely owner | Disposition |
|---|---|---|
| Typed predicted value/effect carriers | N8 generation-cycle/value contracts | Extend/consume; do not replace. |
| Shift/degradation/quality/FDR evidence | `polisyos.ddm` | Consume as candidate evidence; never let it assign cause. |
| Monitoring/evaluation binding | `runtime/quality/ddm_monitoring.py` | Extend with refs; avoid parallel monitoring plan. |
| Post-deploy accountability/component attribution | S13 `post_deploy_accountability.py` | Compose after SMDV-1; do not fork S13 ownership. |
| Diagnosis/admission producer | No admitted owner chain | `absent/unallocated`; candidate placement beside S13 in `runtime/quality`. |
| Posterior update and O1 bridge | GY-O1 plan | Build-new consumer; not supplied by this research. |
| World-edge admission/write | GY-O3 + Fabric world | Extend guarded consumer; Fabric stays storage owner. |
| Semantic confirmation quarantine | Fabric quarantine substrate + missing O3 profile/consumer invariant | Reuse storage; semantic bridge/verification missing. |
| Institutional signer/adjudicator | External institution; none appointed | `absent/unallocated`; research cannot appoint. |
| Atlas/public projection | Atlas DS13/DS14/DS18 candidates | Surface only; projection cannot mint authority. |

## 8. Later Integration Handoff

### 8.1 Producer-to-surface chain

| Layer | Handoff |
|---|---|
| Producer | Reuse N8 typed carriers, DDM events, implementation monitoring, exposure/version/context evidence, and independent sensor evidence. Candidate narrow producer belongs beside S13 in `runtime/quality`, subject to architecture review. |
| Persisted artifacts/events | CAS-backed comparison, diagnosis, ancestry, update-admission, and quarantine records; append-only correction/supersession. |
| Bridge | GY-O1 consumes only admitted `prediction_error`; S13 consumes the resulting component-attribution question; GY-O3 consumes ancestry/confirmation admission before Fabric write. |
| Consumer | Versioned posterior owner and Fabric world-edge writer. Neither may infer admission from class-name presence. |
| Verification | 24-case corpus, O3 frozen red, metamorphic variants, actual consumer false-pass probes, clean replay, and independent oracle/adjudication later. |
| Surface | Atlas reviewer/machine views show diagnosis, contributors, discriminator, maturity, update refusal/authorization, and quarantine. Public view shows bounded accountability without exposing protected internals. |

### 8.2 Engineering versus research blockers

**Engineering blockers:** comparison producer, SMDV-1 bridge, content-derived IDs, consumer gating, CAS persistence, replay, Atlas projection, and fixtures.

**Research/institutional blockers:** registration or revision of SMDV-1; domain validation and inter-rater behavior; evidence standard for causal observation ancestry; acceptable unresolved rates by consequence class; version-pooling rules; independent oracle; and appointed signer/override authority.

### 8.3 OPS-R7 handoff

Sequential treatment/version, interference, stopping, and claim reset are not separate future topics: they are mandatory fields/gates in comparison, diagnosis, admission, and benchmark packets. Any implementation omitting them silently loses the absorbed task.

### 8.4 Non-effect

This handoff does not change a posterior, world edge, policy, public claim, capability label, owner, or authority. Only later ratification and implementation may do so.

## 9. Promotion And Kill Rules

### 9.1 Research-only — current state

Required now because SMDV-1 is unregistered; corpus is proposed, not executed; producer/bridge/consumer verification is absent; full census is not established; and no institutional signer exists.

### 9.2 Prototype allowed

A shadow-only prototype may be allowed when:

- one immutable experimental SMDV-1 definition is referenced by both tasks;
- comparison and diagnosis artifacts are strict and content-bound;
- DDM/S13/Fabric owners are extended rather than duplicated;
- no prototype output can reach posterior, world write, policy action, publication, or approval;
- all 24 public regression fixtures and property-removal probes run;
- unresolved is first-class and cannot default to prediction error.

### 9.3 Governed allowed

Requires all of:

- vocabulary disposition/registration by the proper governance stage;
- independent oracle/adjudication and sealed holdout;
- complete producer→artifact→bridge→consumer→verification chain;
- actual posterior/world consumers fail closed on non-admitted records;
- version, interference, maturity, observation ancestry, and authority gates are constructed—not declared;
- zero unsafe update/write/self-confirmation escapes on the controlled corpus and adjacent variants;
- appointed competent signer or explicit preauthorization for every protected operation;
- historical replay and correction/supersession pass.

### 9.4 Production candidate

Additionally requires a named domain/population/outcome; measured operating characteristics and unresolved behavior there; operator comprehension and incident exercises; observation channels for delayed/censored/spillover harm; privacy/security/legal review; rollback/recovery drills; and ratified release authority. Benchmark passage remains bounded to named revision, environment, corpus, oracle, and rules.

### 9.5 Block/kill conditions

Block or withdraw the positive if any occurs:

- SMDV-1 forks between INT and OPS or is silently changed after outcomes;
- a detector or supplied class reaches learning/write authority;
- unsafe posterior update, unsafe edge write, or self-confirmation escape is non-zero;
- remove-property/keep-markers probe stays green;
- treatment/measurement versions or exposure map are missing;
- unresolved defaults to prediction error or permanent full exposure without a charter;
- expected variation triggers adaptive tampering;
- generic quarantine can later write the prohibited edge;
- historical meaning is overwritten;
- claimed authority has no appointed signer;
- the exact comparison/ancestry property remains `not_established`.

Gate standing remains `NO_GO` until all governed conditions are independently evidenced.

## 10. Open Questions For Consolidation

### 10.1 Questions requiring architect/governance disposition

1. Does O1's “posterior update” mean only discrepancy-driven repair, or also routine predeclared assimilation under `expected_variation`?
2. Should SMDV-1 be registered as a new vocabulary, or encoded as a narrow movement-source axis beside S13's destination attribution?
3. What exact mapping between SMDV-1 and S13 is loss-tolerable, and which losses must block?
4. What evidence constructs observation-process causal ancestry rather than merely declaring a DAG/provenance path?
5. When mixed outcome and observation paths exist, which domains can identify their separate contributions and which must remain unresolved?
6. What domain/consequence-specific unresolved rate is acceptable before a system remains accountability-only?
7. Which treatment-version changes may be pooled, under what predeclared theorem or equivalence evidence?
8. Who owns the independent oracle and who is competent to adjudicate high-stakes diagnosis disagreements?
9. Who is the institutional signer for posterior/world updates, reissue, override, or withdrawal?
10. Which independent observation channels are mandatory for people with zero production-channel inclusion probability?
11. How are privacy and minimization preserved when observation ancestry and interference require richer linkage?
12. Which Atlas projections show unresolved/compound diagnosis without presenting it as a settled cause?

### 10.2 Classified finding summary

| Finding | Classification | Disposition |
|---|---|---|
| Adjacent S13 typed attribution exists. | `confirmed` | Corrects broad greenfield orientation; no capability promotion. |
| Exact evidence-derived joint diagnosis chain is absent. | `confirmed` | `absent/unallocated`; route to later architecture/implementation. |
| SMDV-1 is a defensible bounded research vocabulary. | `accepted_narrow_scope` | Candidate for consolidation/ratification, not registered. |
| Cross-domain automated classification reliability is unknown. | `deferred_open_problem` | Require domain benchmark/oracle; do not invent a threshold. |
| O1 safety direction is correct but incomplete/inoperable. | `accepted_narrow_scope` | Architect clarification + implementation prerequisites. |
| O3 safety direction is correct but incomplete/inoperable. | `accepted_narrow_scope` | Fund observation-ancestry method and consumer invariant. |
| No appointed signer exists. | `blocked` | Institutional action required; research cannot close. |
| Complete repository-wide diagnosis census was not executed. | `deferred_open_problem` | `not_established`; no zero claim. |

### 10.3 W4-K05 standing — separate axes

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

No axis is inferred from another. Research acceptance does not implement the capability or open the gate.

## Operational Closure Addendum — Group-A Required Steps 3–5

### 3. State machine

Specified in §7.2 with pending, invalid, non-learning, unresolved, self-confirmation quarantine, admissible prediction error, proposal, denial, authorization, commit, failure, correction, and supersession behavior. Clocks and reopening are in §7.3.

### 4. Typed artifacts

Specified in §7.1 with authority boundaries, provenance, rule/schema/version refs, content-derived identities, and no parallel status lattice.

### 5. Edge-case fixtures

Specified in §6: happy path, model-compatible variation, missing evidence, late/duplicate/corrected events, conflicting sensors, version mismatch, owner unavailable, malicious declared independence, delayed/censored/zero-inclusion harm, spillover, partial success, rollback residue, historical replay, and O3 permanent quarantine.

## Pattern Pass

| Pattern | Risk found | Result/routing |
|---|---|---|
| `P01` | Research contracts could be mistaken for capability. | Standing remains `absent/unallocated`; chain named explicitly. |
| `P02` | Mature fragments exist without diagnosis bridge. | Reuse-first owner map; bridge remains missing. |
| `P03` | Rich diagnosis could remain internal. | Atlas/public projection handoff named, not implemented. |
| `P04` | Local diagnosis/response states could become another global lattice. | Internal coordinates only; project into the one Atlas lattice. |
| `P05` / `P15` | Plan, LLM, fixture label, or projection could mint authority. | All are candidate evidence; actual consumer admission required. |
| `P07` / `P08` | Rule/version/time roles could be unreplayable or conflated. | Separate versions and nine time roles; append-only history. |
| `P09` | Unresolved diagnosis could have no owner/clock/reopen path. | Discriminator, next evidence, expiry, escalation required. |
| `P10` / `P29` | Constructor/marker tests could substitute for semantic behavior. | Actual posterior/world consumer and remove-property probes required. |
| `P11` | Learning loop could remember only anomalies. | `expected_variation` and positive/negative controls retained. |
| `P12` | Producer could resolve meaning after emission. | Comparison and diagnosis bind source versions before admission. |
| `P13` | New post-deploy governance platform could duplicate S13/DDM/Fabric. | Extend existing owners; institutional functions remain external. |
| `P14` | Many correlated sensors could inflate independence. | Observation ancestry and shared-source negatives required. |
| `P24` | Strategic/performative response could be learned as stable evidence. | Behavioral and observation paths separated; self-confirmation quarantine. |
| `P25` | Exploratory search could become control/authority. | O2 anomalies remain candidate; O1 admission required. |
| `P27` | SMDV-1 could bypass S13 owner. | Two-stage mapping; no replacement owner. |
| `P30` | Provenance labels could overstate actual source/authority. | Evidence refs and predicate-provenance labels kept separate. |
| `P31` / `P40` | Fixing one self-confirmation instance could leave the class. | General ancestry/write invariant and bucket rule. |
| `P32` / `P33` | Presence or taught fixtures could pass. | Adjacent/metamorphic/holdout and false-declaration variants. |
| `P35` / `W4-K01` | Indexed search could settle a repository zero. | Census limitation recorded as `not_established`; executing party named. |
| `P36` | Orientation prose could be treated as finding. | Evidence register classifies direct repository facts and correction. |
| `P37` / `P38` | Declared independence, owner, or version could green a proxy gate. | Predicate labels + divergent cases; last three labels fail closed. |
| `P41` | An inherited red could be misassigned. | No test-suite claim made; execution limitation kept environmental. |

**Acceptance signal:** the package says what is safe to prototype, what remains research-only, what is blocked, which fixture falsifies an overclaim, and what PolicyOS owns versus integrates—without moving capability or authority.
