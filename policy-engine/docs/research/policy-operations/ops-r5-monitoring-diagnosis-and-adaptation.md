---
title: OPS-R5 — Monitoring Diagnosis And Governed Adaptation
status: in_progress — external baseline and result recorded
kind: deep-research
research_task: OPS-R5
joint_with: INT-R4
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r4-ops-r5-research
repository_baseline: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
inspection_date: 2026-08-29
research_only: true
authoritative_for:
  - research findings about KPI control and adaptation-mode governance
  - research contract for absorbed OPS-R6 adaptation scope
  - application of the INT-R4-owned shared movement-diagnosis vocabulary to operational response
may_not_use_for:
  - capability claim
  - production implementation authorization
  - registered vocabulary claim
  - canonical owner appointment
  - authority grant
  - automatic policy adaptation
  - institutional signer appointment
  - benchmark passage
---

# OPS-R5 — Monitoring Diagnosis And Governed Adaptation

## 1. Task And Project Fit

### 1.1 Commission and joint dependency

OPS-R5 treats a KPI as a decision-linked contract, not a number with a band. It owns the research question for the contract, diagnosis and response semantics while integrating data collection. It absorbs OPS-R6, the adaptation ladder, and is the declared joint binding input with INT-R4 before GY-O1/O3 may close (`policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:527-531`).

The same observed movement that may invite an operational response may also be presented to a learning system as evidence. The pair therefore cannot tolerate two diagnosis vocabularies. The sole candidate shared vocabulary is derived and owned in `../int-r4-performative-effect-update-diagnosis.md` §4. This document imports that vocabulary, precedence rule, bounded exhaustiveness claim and unresolved policy unchanged.

### 1.2 Custody boundary

PolicyOS owns the KPI contract attached to its own signed justification: construct and definition, versions, lineage, basis, population, timing, uncertainty, gaming exposure, response table, update consequences and the fail-closed record of what it did. It integrates measurements and institutional decisions produced by external actors. It may recommend or block within an admitted authority boundary; it cannot appoint the decision-maker or assume that a DSMB, regulator, airworthiness authority, product owner or public body exists here.

### 1.3 Absorbed OPS-R6 coverage

OPS-R6 is covered as a governed response state machine rather than an asserted universal linear ladder:

- observation, warning and diagnosis: §§3-7;
- refresh, recompute and recalibration: §§4, 7 and 9;
- implementation adjustment and scope narrowing: §§4, 7 and 9;
- partial reissue, redesign, pause, rollback and termination: §§4, 6, 7 and 9;
- entry/exit evidence, restart gates, reversibility and authority: §§3, 4, 7 and 9.

### 1.4 Exact controlled operation

The controlled operation is any transition that changes exposure, implementation, policy version, claim status, publication status or the model/world state because a monitored quantity moved. Detection may open review or protective containment. It must not silently establish a causal explanation or authorize an effect-posterior/world-edge update.

## 2. Current Repository Baseline

### 2.1 Pin and inspection boundary

Repository evidence is pinned to `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`. The same canonical seams inspected for INT-R4 were inspected here: DDM detector contracts, delayed-label monitors, FDR, monitoring/evaluation records, continuous-governance recommendations, S13 attribution, the value gate, GY-O1/O2/O3, world branches and quarantine.

The environment could not execute a local complete tree walk because ordinary Git transport could not resolve `github.com`. Connector search is not a P35 denominator. This document therefore does not infer a zero from indexed search and does not claim that no adjacent implementation exists outside the inspected canonical owners. The positive canonical evidence is sufficient to establish the architectural seam and the missing joint chain.

### 2.2 Current monitoring distinguishes several signal kinds

DDM already keeps calibrated shift, realized/estimated performance degradation, data-quality failures, readiness, incidents and a root-cause localization bundle separate (`policy-engine/src/polisyos/ddm/integration/events.py:1-232`). This is a strong baseline because a shift event is explicitly diagnostic evidence rather than a retraining command. Realized monitors retain confidence intervals and label-delay horizons; data-quality checks retain concrete violations; FDR records alpha spent and discoveries rather than pretending to identify why the metric moved (`policy-engine/src/polisyos/ddm/detectors/realized_performance_monitor.py:1-151`; `data_quality_monitor.py:1-142`; `calibration/multiple_testing.py:1-89`).

The existing Track-2.2 adapter nevertheless maps fixed severity cutoffs `0.25` and `0.70` to `watch` and `investigate` (`policy-engine/src/polisyos/ddm/detectors/track_2_2_shift_adapter.py:44-62`). Those values are local DDM risk routing, not general policy-action or causal-diagnosis thresholds.

### 2.3 Monitoring plans and lifecycle recommendations exist

The implementation-monitoring/evaluation record requires indicators, observation windows, review cadence, trigger thresholds, owners, estimand, comparison strategy, DDM evidence, claim links and publication ordering (`policy-engine/src/polisyos/runtime/quality/ddm_monitoring.py:1-287`). Continuous governance types source invalidation, calibration drift, fairness drift, policy-context drift and incidents, with recommendations including continue monitoring, mark stale, human review, reissue and withdrawal review (`policy-engine/src/polisyos/scientist/governance/continuous/monitors.py:1-113`).

These contracts are useful inputs to a KPI control plane. They do not yet bind construct semantics, definition version, baseline vintage, KPI role, gaming exposure, observation-health tests, diagnosis class, permitted response, restart evidence and institutional authority into one admitted contract.

### 2.4 S13 is adjacent, not the joint diagnosis

S13 supplies an eight-class post-deployment attribution vocabulary and a learning gate, but canonical fixtures provide the attribution class directly. The inspected runtime verifies shape and routing; it does not evidence a classifier that derives the class from a monitored movement (`policy-engine/src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py:43-58`, `:164-221`; `policy-engine/tests/fixtures/layer2/s13/s13_post_deploy_case_signals.json:4-204`).

Accordingly, the “only truly greenfield” orientation is too broad. A bounded attribution/accountability capability exists. The exact joint function — one operationally testable movement diagnosis controlling both adaptation and posterior/world learning — remains greenfield and unallocated.

### 2.5 GY makes the signal/authority boundary explicit but has not built it

GY-O2 reuses DDM and FDR to emit an anomaly only as `candidate_unverified`; it may reach a world edge only through O1. O1 requires a typed cause before posterior update. O3 requires confirmation and an observation-process self-confirmation negative before write-back (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:5043-5095`). All three are labelled `build-new`.

This is the correct control boundary at plan level: signal detection is not diagnosis, and diagnosis is not authority. The repository baseline does not yet demonstrate its implementation.

### 2.6 Storage and quarantine can carry an operational record

Fabric provides append-only corrections/revocations, bitemporal snapshots, governed branches and branch-audit evidence (`policy-engine/docs/reference/fabric/time-travel.md:1-111`). Generic CAS quarantine persists record, payload and replay lineage (`policy-engine/src/polisyos/fabric/data_plane/quarantine.py:1-106`, `:220-463`). These are appropriate substrates for rejected, stale, contradictory, out-of-order and quarantined monitoring evidence.

Generic quarantine does not decide whether a KPI movement is causally unusable, nor does it prevent a reprocessor from later admitting an O3-prohibited self-confirming edge. That semantic invariant must belong to the joint diagnosis/admission owner and be verified at the world-write consumer.

### 2.7 Institutional authority is absent

External regimes often rely on a DSMB, regulator, airworthiness authority, metric steward or product/SRE owner. No such institutional signer is appointed for this mechanism. Repository strings naming owners or governance roles are not an appointment. Therefore response rungs requiring discretionary policy change, reissue, rollback, termination or exception remain `absent/unallocated` even if a contract sketch can define their evidence requirements.

### 2.8 Baseline verdict

The repository can detect, localize, retain and route signals and can preserve historical world state. It cannot yet demonstrate the admitted operation:

```text
metric contract + matured observation
→ trust/measurement checks
→ shared movement diagnosis
→ typed permissible response
→ competent authorization where required
→ append-only action/reissue/refusal record
→ separate restart gate and replay
```

The shared vocabulary is not registered, its producer is absent, no canonical institutional signer exists, and no end-to-end semantic fixture proves that a threshold crossing cannot auto-change policy. Joint capability standing is `absent/unallocated`.

Supporting baseline and finding coordinates are maintained in [the OPS-R5 evidence register](ops-r5/evidence-register.md).

## 3. External Research Baseline

### 3.1 Source posture and dependency on INT-R4

OPS-R5 uses the same five commissioned surveys and the same `institutionally_supplied` posture described in INT-R4 §3. It does not re-derive the cause categories. The sole diagnosis vocabulary is SMDV-1 in `../int-r4-performative-effect-update-diagnosis.md` §4.

The external record contributes three distinct layers:

- S4 describes the parts of a governed metric contract and the Goodhart/Campbell failure record;
- S3 distinguishes detection, diagnosis and purpose-specific residue routing;
- S2 describes evidence-gated response, versioning, stopping and reversibility;
- S1 and S5 constrain what monitoring can infer under endogenous observation, censoring, delayed harm and interference.

### 3.2 A KPI contract is more than a threshold

No supplied domain has one universal “metric contract” standard. Across official statistics, clinical quality measures, trial registration, DSMB practice, SRE error budgets, experimentation platforms and semantic layers, the recurring fields are nevertheless stable: construct, definition and version; lineage and instrument; unit/basis; aggregation; population, denominator and exclusions; subgroups; baseline vintage; target type/band; metric role; lag/window; revision policy; uncertainty; gaming exposure; owner; decision rights; response semantics; and immutable change history (S4:5-64, 146-243, 248-365).

The strongest transferable pattern is not “number crosses threshold.” It is:

```text
predeclared meaning
→ qualified observation
→ permitted decision type
→ actor authorized for that decision
→ required record and escalation
```

A threshold may open investigation without deciding causation or legality. The same numeric cutoff can therefore have different semantics; the response table is load-bearing.

### 3.3 Metric roles are non-compensable

S4 preserves the experimentation distinction among objective/OEC, guardrail, diagnostic and data-quality metrics. These answer different logical questions and cannot safely be summed into one score. An objective gain cannot buy a guardrail violation; a data-quality metric determines whether interpretation is allowed, not whether the intervention is valuable; a diagnostic explains mechanism rather than contributing utility (S4:195-243).

For this task the minimum role set is:

- `result` — realized target outcome;
- `implementation` — whether intended delivery occurred;
- `guardrail` — non-compensable harm or constraint;
- `leading` — early predictor, not a realized outcome;
- `diagnostic` — mechanism/localization evidence;
- `context` — demand, regime or concurrent-world condition;
- `measurement_health` — whether the metric can be interpreted.

The set is a candidate adaptation of surveyed practice, not an externally registered taxonomy. A contract may use several roles, but it cannot add them into one authority score.

### 3.4 No universal linear adaptation ladder

S2 finds no single mature sequence valid across trials, aviation, nuclear operations, software delivery, circuit breakers, sandboxes and sunset clauses. The domains control different risks: inferential error, ongoing exposure, distance to an operating envelope, blast radius, request permission or legal duration. What transfers is precommitment: what is measured, when reviewed, what evidence is sufficient, which action is permitted, who authorizes it, what happens under uncertainty, how restart works and what is irreversible (S2:5-82, 84-137, 303-377).

The literature therefore supports a multi-axis state machine rather than one scalar rung. Protective action may precede diagnosis when waiting is dangerous; model learning and confirmatory claims may not.

### 3.5 Reversibility is a vector

S2 distinguishes:

```text
R_control      can further exposure be stopped?
R_state        can prior system state be restored?
R_outcome      can harm already caused be repaired?
R_inference    can the original experiment/information process be recovered?
```

A software rollback may restore control but not data or user state; stopping a trial prevents future exposure but cannot undo treatment; revoking a legal rule cannot restore prior market behavior. Response selection and authorization must therefore use the vector, not a boolean `reversible` (S2:139-190).

### 3.6 Unknown, delayed harm and missing channels

The surveys reject the equation “no signal = no harm.” Response gates need outcome maturity, censoring, attrition, detection probability and observation-horizon evidence. Exited, rejected, never-entered and neighboring populations require external channels or explicit `unquantified` status; aggregate improvement does not clear subgroup or spillover harm (S5:5-19, 21-131, 179-300).

This yields a crucial asymmetry:

- uncertainty may prohibit expansion, narrow exposure or pause a reversible system;
- uncertainty cannot silently close harm, validate a positive, or authorize model/world learning;
- the absence of a signer cannot be replaced by an automatic threshold.

### 3.7 Exploratory versus confirmatory

S2 and S5 support two tracks. Data-adaptive anomaly or subgroup discovery remains exploratory; confirmatory claims require a frozen estimand, outcome definition, version, population, horizon and multiplicity policy, followed by prospective evidence. A safe canary or an FDR-controlled anomaly is not an efficacy claim. Any material intervention, eligibility, measurement or analysis change resets the relevant confirmatory status unless a predeclared adaptive design already covered it (S2:214-301; S5:179-203).

## 4. Result

### 4.1 Result type

**Result: `accepted_narrow_scope`.** OPS-R5 specifies a candidate `KPIControlContract` and a governed response state machine. Both consume SMDV-1 from INT-R4 §4. They are research contracts only: no response owner is appointed, no thresholds are selected and no policy action is authorized.

### 4.2 Candidate KPIControlContract

A decision-linked metric contract needs four layers.

#### Semantic layer

```text
contract_id / content identity
construct and claim ref
metric role(s)
definition and definition version
unit, basis, numerator/denominator, exclusions
aggregation and non-compensability rules
population, subgroup and spillover frames
baseline value and baseline vintage
desired direction, target type and acceptable band
```

#### Observation layer

```text
source and lineage refs
measurement instrument / implementation
observation, valid, transaction and decision times
cadence, lag, seasonality and maturity window
censoring, attrition and missing-channel posture
revision / correction / backcast / series-break policy
uncertainty and detection-capability statement
sentinel, negative-control and independent-channel refs
gaming and endogenous-measurement exposure register
```

#### Decision layer

```text
trigger semantics: alarm, investigation, guardrail, decision or clock
admissible evidence and identification threshold
harm of waiting and harm of premature action
reversibility vector and blast radius
permitted protective and substantive actions
SMDV-1 diagnosis requirement for each action
claim and version consequence
restart / de-escalation evidence
```

#### Authority and custody layer

```text
metric steward and definition-change rights
data producer and integration boundary
decision authority and override authority
owner unavailable / after-hours behavior
public meaning during review, pause, reissue or withdrawal
append-only audit, supersession and historical replay
rule/schema/authority-boundary refs
```

The contract does not make all fields mandatory for every metric. It makes omissions typed and purpose-scoped. A metric lacking an observation or authority field cannot silently acquire that power.

### 4.3 The governed response state machine

The result uses four orthogonal axes derived from S2. They are not another Atlas status lattice; they are internal evidence/permission coordinates that project into existing lifecycle and public states.

#### Epistemic state

```text
E0 normal                 no material signal under the contract
E1 signal                 detector or report opens review
E2 credible_anomaly       trust checks pass; movement is material, cause not established
E3 diagnosed_mechanism    SMDV-1 record identifies a primary class with admissible evidence
E4 confirmed_unacceptable harm/failure/invalidity meets the predeclared action standard
```

#### Exposure permission

```text
X0 full
X1 no_expansion
X2 narrowed
X3 paused
X4 terminated
```

#### Intervention state

```text
V0 unchanged
V1 recalibrated
V2 patched_or_reissued
V3 redesigned
V4 rolled_back
```

#### Claim state

```text
C0 confirmatory_intact
C1 under_review
C2 exploratory_only
C3 withdrawn
```

These axes allow real combinations: `E1/X1/V0/C1` during investigation; `E2/X3/V0/C2` when a high-harm signal is not yet diagnosed; `E3/X2/V2/C1` for an implementation-version repair; `E4/X4/V3/C3` for termination and withdrawn claim.

### 4.4 Action families — the absorbed OPS-R6 ladder

For operator readability, the original ladder is retained as **action families**, not as one monotone state variable:

| Family | Actions | Minimum evidence posture | Automatic authority? |
|---|---|---|---|
| `A0_observe` | retain, mature window, collect denominator/follow-up | E0 or immature signal | allowed only inside predeclared monitoring contract |
| `A1_investigate` | validate data, open diagnosis, acquire sentinel/implementation/context evidence | E1 | may be automatic as case creation; no substantive change |
| `A2_contain` | no expansion, degraded mode, scope cap, protective notice | E1/E2 plus waiting-harm or guardrail basis | only if preauthorized; otherwise human escalation |
| `A3_refresh` | correct/revise data, bridge series, recompute, recalibrate measurement | diagnosed observation/data issue | no policy-effect update; preserve revision provenance |
| `A4_adjust` | repair implementation, narrow scope, partial reissue, version-specific change | E3 plus appropriate SMDV-1 class and authority | human/institutional where policy changes |
| `A5_pause_or_rollback` | pause exposure, rollback future control, withdraw current operational permission | E2/E3/E4 according to risk and reversibility | only if preauthorized emergency rule or competent decision |
| `A6_terminate_or_redesign` | terminate, redesign, re-ratify, retire claim | E4 or unresolved beyond legal/safety clock | never inferred from threshold alone |

The action family and the causal diagnosis are separate objects. `diagnosis_unresolved` may still support `A1`, `A2` or a preauthorized `A5` when harm of waiting is high; it cannot support posterior/world learning or an unreviewed substantive redesign.

### 4.5 Transition charter

Every transition that can change exposure, version or claim status must have a predeclared charter:

| Field | Required question |
|---|---|
| trigger | What observation opens the transition? |
| evidence source | Which records are admissible, and for what purpose? |
| information maturity | Which count, follow-up horizon, latency or window is required? |
| measurement-validity test | Is the metric itself interpretable? |
| diagnosis requirement | Which SMDV-1 classes are allowed or prohibited? |
| waiting loss | What harm accrues before the next review point? |
| premature-action loss | What does a false alarm destroy? |
| reversibility vector | Which of control, state, outcome and inference can be restored? |
| blast radius | How much new exposure is allowed while deciding? |
| VOI / next evidence | What evidence could actually change the decision? |
| legal or governance clock | When does action/review become mandatory? |
| decision authority | Who may choose this transition? |
| override authority | Who may deviate, under what recorded reason? |
| restart criteria | What separate evidence permits de-escalation? |
| version consequence | Does this create `A(v+1)` or a new adaptive rule? |
| claim consequence | Does the old claim remain confirmatory, become exploratory, or withdraw? |
| audit record | What must be sealed before later outcomes are seen? |

A threshold without this charter is a proxy gate under P37/P38.

### 4.6 Entry, exit and restart rules

Escalation and restart are asymmetric. A pause caused by a safety signal cannot return directly to full exposure because the signal disappeared. Restart requires an independent `RestartEvidenceRecord`: identified repair/version, tests of the repaired mechanism, measurement health, bounded probe/half-open exposure, renewed authority and a statement of which historical claim remains valid.

A version change creates a new treatment identity unless the contract contains a predeclared equivalence/pooling rule. Proof for `v` does not flow to `v+1` by naming continuity.

### 4.7 Relationship to learning

Only SMDV-1 `prediction_error`, with no blocking contributor and all INT-R4 §4.8 predicates, may enter an effect-posterior proposal. An exploratory signal remains candidate-only even if it triggers containment. `observation_process_change` updates a measurement/semantic epoch; `intervention_delivery_or_version` updates delivery/version evaluation; `behavioral_response` updates a response mechanism; `context_or_interference` updates context/coupling; unresolved freezes learning.

The response engine may therefore act protectively under lower causal certainty than the learning engine. This is deliberate and supported by the cross-domain record.

### 4.8 No universal numbers

The surveys provide no defensible domain-independent trigger thresholds, detection rates, follow-up horizons, false-signal rates or reversibility values. Existing DDM `0.25/0.70` cutoffs remain local risk-routing choices and are not imported as OPS-R5 policy thresholds. Each number in a future contract must name population, horizon, measure, conditional assumptions and authority source.

### 4.9 Institutional limit

The state machine can specify what evidence and authority a transition would require. It cannot supply the missing authority. At this pin no appointed signer exists for policy reissue, rollback, termination or discretionary override. Those rungs remain `absent/unallocated`; automation may only execute transitions explicitly preauthorized by an external competent authority and represented by admitted evidence.

## 5. Counterexamples And Failure Modes

## 6. Benchmark Or Fixture Proposal

## 7. Artifact Contract Sketch

## 8. Later Integration Handoff

## 9. Promotion And Kill Rules

## 10. Open Questions For Consolidation
