---
title: OPS-R5 — Monitoring Diagnosis And Governed Adaptation
status: in_progress — failure modes and response fixtures recorded
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

OPS-R5 treats a KPI as a decision-linked contract, not a number with a band. It owns the research question for the contract, diagnosis, and response semantics while integrating data collection. It absorbs OPS-R6, the adaptation ladder, and is the declared joint binding input with INT-R4 before GY-O1/O3 may close (`policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:527-531`).

The same observed movement that may invite an operational response may also be presented to a learning system as evidence. The pair therefore cannot tolerate two diagnosis vocabularies. The sole candidate shared vocabulary is derived and owned in `../int-r4-performative-effect-update-diagnosis.md` §4. This document imports that vocabulary, precedence rule, bounded exhaustiveness claim, and unresolved policy unchanged.

### 1.2 Four-way custody boundary

The ratified §6 ruling is exact: KPI control contract and diagnosis semantics are **OWN contract / INTEGRATE data collection** (`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:86-124`). PolicyOS owns construct/definition/version, lineage/basis, population/timing, uncertainty, gaming exposure, response table, update consequences, and the fail-closed record of its own claim reaction. Sensors and institutional decisions are external evidence. PolicyOS does not appoint a DSMB, regulator, airworthiness authority, metric steward, product owner, or sovereign policy decision-maker.

### 1.3 Absorbed OPS-R6 coverage

OPS-R6 is covered as a governed response state machine rather than a claimed universal linear ladder:

- observation, warning, and diagnosis: §§3–7;
- refresh, recompute, and recalibration: §§4, 7, and 9;
- implementation adjustment and scope narrowing: §§4, 7, and 9;
- partial reissue, redesign, pause, rollback, and termination: §§4, 6, 7, and 9;
- entry/exit evidence, restart gates, reversibility, and authority: §§3, 4, 7, and 9.

### 1.4 Exact controlled operation

The controlled operation is any transition that changes exposure, implementation, policy version, claim status, publication status, or model/world state because a monitored quantity moved. Detection may open review or protective containment. It must not silently establish a causal explanation or authorize effect-posterior/world-edge updating.

## 2. Current Repository Baseline

### 2.1 Pin and inspection boundary

Repository evidence is pinned to `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`. The mandatory architecture anchors and focused owner seams were read: `AGENTS.md`, contributor baseline, ratified identity, organizing rules, target architecture, operating model, honest diagnostics, north star, failure register, GY/Atlas plans, distillation ledger, DDM contracts, delayed-label monitors, FDR, monitoring/evaluation records, continuous governance, S13 attribution, value gate, world branches, and quarantine.

Ordinary Git transport could not resolve `github.com`, so no local complete `rg`/`git grep` tree census was executed. Connector search is not a P35 denominator. This document does not infer a zero from indexed search and does not claim that no adjacent implementation exists outside the inspected canonical owners. Exact-zero census standing is `not_established`.

### 2.2 Current monitoring distinguishes several signal kinds

DDM keeps calibrated shift, realized/estimated performance degradation, data-quality failures, readiness, incidents, and root-cause localization separate (`policy-engine/src/polisyos/ddm/integration/events.py:1-232`). A shift is diagnostic evidence rather than a retraining command. Realized monitors retain intervals and label-delay horizons; data-quality checks retain concrete violations; FDR records alpha spent and discoveries rather than pretending to identify why the metric moved (`policy-engine/src/polisyos/ddm/detectors/realized_performance_monitor.py:1-151`; `data_quality_monitor.py:1-142`; `calibration/multiple_testing.py:1-89`).

The Track-2.2 adapter maps local severity cutoffs `0.25` and `0.70` to `watch` and `investigate` (`policy-engine/src/polisyos/ddm/detectors/track_2_2_shift_adapter.py:44-62`). These are DDM risk-routing choices, not domain-independent policy-action or causal-diagnosis thresholds.

### 2.3 Monitoring plans and lifecycle recommendations exist

The implementation-monitoring/evaluation record requires indicators, windows, cadence, trigger thresholds, owners, estimand, comparison strategy, DDM evidence, claim links, and publication ordering (`policy-engine/src/polisyos/runtime/quality/ddm_monitoring.py:1-287`). Continuous governance types source invalidation, calibration/fairness/context drift, and incidents and can recommend monitor, stale, review, reissue, or withdrawal review (`policy-engine/src/polisyos/scientist/governance/continuous/monitors.py:1-113`).

These are strong inputs. They do not bind construct semantics, definition version, baseline vintage, KPI role, gaming exposure, observation-health tests, SMDV-1 diagnosis, permitted response, restart evidence, and institutional authority into one admitted contract.

### 2.4 S13 is adjacent, not the joint diagnosis

S13 has an eight-class post-deployment attribution vocabulary and a learning gate, but canonical fixtures provide the attribution class directly. The runtime verifies shape and routing; it does not demonstrate a classifier deriving the shared movement diagnosis from a monitored movement (`policy-engine/src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py:43-58`, `:164-221`; `policy-engine/tests/fixtures/layer2/s13/s13_post_deploy_case_signals.json:4-204`).

Thus the zone is not wholly greenfield: bounded post-deploy attribution/accountability exists. The exact joint function — one operationally testable diagnosis governing both adaptation and learning — remains greenfield and unallocated.

### 2.5 GY preserves the signal/authority boundary but has not built it

GY-O2 reuses DDM/FDR and keeps anomaly output `candidate_unverified`; it may reach a world edge only through O1. O1 requires typed cause; O3 requires confirmation and the observation-process self-confirmation negative (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:5043-5095`). All three are `build-new`. This is the right plan boundary: signal is not diagnosis and diagnosis is not authority. It is not implementation evidence.

### 2.6 Storage and quarantine can carry later records

Fabric supplies append-only corrections/revocations, bitemporal snapshots, governed branches, and branch-audit evidence (`policy-engine/docs/reference/fabric/time-travel.md:1-111`). Generic CAS quarantine persists record, payload, and replay lineage (`policy-engine/src/polisyos/fabric/data_plane/quarantine.py:1-106`, `:220-463`). These are suitable substrates for rejected, stale, contradictory, out-of-order, and quarantined monitoring evidence.

Generic quarantine does not decide causal usability and does not prevent a reprocessor from later admitting an O3-prohibited confirmation. That semantic invariant must be verified at the world-write consumer.

### 2.7 Institutional authority is absent

No institutional signer is appointed for this mechanism. Repository owner/team strings are not an appointment. Therefore discretionary policy change, reissue, rollback, termination, and override remain `absent/unallocated` even if research can define their evidence requirements.

### 2.8 Baseline verdict

The repository can detect, localize, retain, and route signals and preserve history. It cannot demonstrate:

```text
KPI contract + matured observation
→ trust/measurement checks
→ SMDV-1 diagnosis
→ typed permissible response
→ competent authorization where required
→ append-only action/reissue/refusal record
→ separate restart gate and replay
```

The shared vocabulary is not registered, its producer is absent, no signer exists, and no end-to-end semantic fixture proves that threshold crossing cannot auto-change policy. Joint capability standing is `absent/unallocated`. Coordinates and findings are in [the OPS-R5 evidence register](ops-r5/evidence-register.md).

## 3. External Research Baseline

### 3.1 Source posture and dependency on INT-R4

OPS-R5 uses the same five `institutionally_supplied` surveys described in INT-R4 §3. It does not re-derive categories. The sole diagnosis vocabulary is SMDV-1 in INT-R4 §4.

- S4 supplies governed-metric fields and Goodhart/Campbell failure mechanisms;
- S3 distinguishes detection, diagnosis, and residue routing;
- S2 supplies response, versioning, stopping, restart, and reversibility;
- S1 and S5 constrain inference under endogenous observation, censoring, delayed harm, and interference.

### 3.2 A KPI contract is more than a threshold

No supplied domain has one universal “metric contract” standard. Across official statistics, clinical measures, trial registration, DSMB practice, SRE error budgets, experimentation platforms, and semantic layers, recurring fields include construct, definition/version, lineage/instrument, unit/basis, aggregation, population/denominator/exclusions, subgroups, baseline vintage, target type/band, role, lag/window, revision policy, uncertainty, gaming exposure, owner, decision rights, response semantics, and immutable history (S4:5-64, 146-243, 248-365).

The transferable pattern is:

```text
predeclared meaning
→ qualified observation
→ permitted decision type
→ authorized actor
→ required record and escalation
```

A threshold may open investigation without deciding cause or legality. Response semantics are load-bearing.

### 3.3 Metric roles are non-compensable

S4 distinguishes objective/OEC, guardrail, diagnostic, and data-quality metrics. They answer different logical questions and cannot be safely summed. An objective gain cannot buy a guardrail violation; measurement health decides interpretability, not value; a diagnostic explains mechanism rather than adding utility (S4:195-243).

Candidate role set for this research:

- `result` — realized target outcome;
- `implementation` — intended delivery status;
- `guardrail` — non-compensable harm/constraint;
- `leading` — early predictor, not realized outcome;
- `diagnostic` — mechanism/localization evidence;
- `context` — demand, regime, concurrent world;
- `measurement_health` — right to interpret the metric.

This is an adaptation, not an externally registered taxonomy. Several roles may coexist but cannot be collapsed into one authority score.

### 3.4 No universal linear ladder

S2 finds no single mature sequence across trials, aviation, nuclear operations, software delivery, circuit breakers, sandboxes, and sunset clauses. The domains control different risks. What transfers is precommitment: what is measured, review timing, sufficient evidence, permissible action, authorization, uncertainty behavior, restart, and irreversibility (S2:5-82, 84-137, 303-377).

Therefore the result uses a multi-axis state machine. Protective action may precede diagnosis when waiting is dangerous; model learning and confirmatory claims may not.

### 3.5 Reversibility is a vector

```text
R_control      can further exposure be stopped?
R_state        can prior system state be restored?
R_outcome      can harm already caused be repaired?
R_inference    can the original information process be recovered?
```

A software rollback may restore control but not state; stopping a trial prevents future exposure but cannot undo treatment; legal reversal cannot restore prior market behavior. Response and authorization must use the vector, not a boolean (S2:139-190).

### 3.6 Unknown, delayed harm, and missing channels

The surveys reject “no signal = no harm.” Gates need maturity, censoring, attrition, detection probability, and horizon evidence. Exited, rejected, never-entered, and neighboring populations need external channels or explicit `unquantified` status; aggregate improvement does not clear subgroup or spillover harm (S5:5-19, 21-131, 179-300).

Thus uncertainty may prohibit expansion, narrow exposure, or pause a reversible system, but cannot close harm, validate a positive, authorize learning, or replace an absent signer.

### 3.7 Exploratory versus confirmatory

Data-adaptive anomaly or subgroup discovery remains exploratory. Confirmatory claims require frozen estimand, outcome definition, version, population, horizon, and multiplicity policy followed by prospective evidence. A safe canary or FDR-controlled anomaly is not efficacy evidence. Material intervention, eligibility, measurement, or analysis change resets claim status unless a predeclared adaptive design covered it (S2:214-301; S5:179-203).

## 4. Result

### 4.1 Result type

**Result: `accepted_narrow_scope`.** OPS-R5 specifies a candidate `KPIControlContract` and governed response state machine. Both consume SMDV-1 from INT-R4 §4. They are research contracts only: no owner is appointed, no threshold selected, and no policy action authorized.

### 4.2 Candidate KPIControlContract

#### Semantic layer

```text
contract/content identity
construct and claim ref
metric roles
definition/version
unit, basis, numerator/denominator, exclusions
aggregation and non-compensability
population, subgroup, spillover frames
baseline value/vintage
direction, target type, acceptable band
```

#### Observation layer

```text
source/lineage refs
instrument and measurement implementation
observation, valid, transaction, decision times
cadence, lag, seasonality, maturity
censoring, attrition, missing channels
revision/correction/backcast/series-break policy
uncertainty and detection-capability statement
sentinel, negative-control, independent-channel refs
gaming/endogenous-measurement exposure register
```

#### Decision layer

```text
trigger semantics: alarm, investigation, guardrail, decision, or clock
admissible evidence and identification threshold
harm of waiting and premature action
reversibility vector and blast radius
permitted protective/substantive actions
SMDV-1 requirement for each action
claim/version consequence
restart/de-escalation evidence
```

#### Authority and custody layer

```text
metric steward and definition-change rights
data producer and integration boundary
decision and override authority
owner unavailable / after-hours behavior
public meaning during review, pause, reissue, withdrawal
append-only audit, supersession, replay
rule/schema/authority-boundary refs
```

Omissions are typed and purpose-scoped. A metric lacking an observation or authority field cannot silently acquire that power.

### 4.3 Governed response coordinates

These are internal evidence/permission coordinates projecting into existing lifecycle/public states, not another Atlas lattice.

```text
Epistemic:
E0 normal
E1 signal
E2 credible_anomaly
E3 diagnosed_mechanism
E4 confirmed_unacceptable

Exposure:
X0 full
X1 no_expansion
X2 narrowed
X3 paused
X4 terminated

Intervention:
V0 unchanged
V1 recalibrated
V2 patched_or_reissued
V3 redesigned
V4 rolled_back

Claim:
C0 confirmatory_intact
C1 under_review
C2 exploratory_only
C3 withdrawn
```

Valid combinations include `E1/X1/V0/C1`, `E2/X3/V0/C2`, `E3/X2/V2/C1`, and `E4/X4/V3/C3`.

### 4.4 Action families — absorbed OPS-R6

| Family | Actions | Minimum posture | Automatic authority? |
|---|---|---|---|
| `A0_observe` | retain, mature, collect denominator/follow-up | E0 or immature signal | only inside predeclared monitoring contract |
| `A1_investigate` | validate data, open diagnosis, acquire sentinel/implementation/context evidence | E1 | automatic case creation may be allowed; no substantive change |
| `A2_contain` | no expansion, degraded mode, scope cap, protective notice | E1/E2 plus waiting-harm/guardrail basis | only if preauthorized; otherwise escalate |
| `A3_refresh` | correct/revise data, bridge series, recompute, recalibrate measurement | diagnosed observation/data issue | no policy-effect update; retain revision provenance |
| `A4_adjust` | repair implementation, narrow scope, partial reissue, version-specific change | E3 plus appropriate SMDV-1 class and authority | human/institutional where policy changes |
| `A5_pause_or_rollback` | pause exposure, rollback future control, withdraw operational permission | E2/E3/E4 according to risk/reversibility | only preauthorized emergency rule or competent decision |
| `A6_terminate_or_redesign` | terminate, redesign, re-ratify, retire claim | E4 or unresolved beyond legal/safety clock | never from threshold alone |

Action family and diagnosis are separate. `diagnosis_unresolved` may support investigation, containment, or a preauthorized pause when waiting harm is high; it cannot support learning or unreviewed redesign.

### 4.5 Transition charter

Every transition changing exposure, version, or claim status requires:

| Field | Question |
|---|---|
| trigger | What opens review? |
| evidence source | Which records are admissible and for what purpose? |
| information maturity | Which count, follow-up, latency, or window is required? |
| measurement-validity test | Is the metric interpretable? |
| diagnosis requirement | Which SMDV-1 classes are allowed/prohibited? |
| waiting loss | What harm accrues before next review? |
| premature-action loss | What does false alarm destroy? |
| reversibility vector | Which control/state/outcome/inference can be restored? |
| blast radius | How much new exposure is allowed? |
| VOI / next evidence | What evidence could change the decision? |
| legal/governance clock | When is review/action mandatory? |
| decision authority | Who may choose? |
| override authority | Who may deviate and why? |
| restart criteria | What separate evidence permits de-escalation? |
| version consequence | Does this create `A(v+1)` or a new adaptive rule? |
| claim consequence | Confirmatory, under review, exploratory, or withdrawn? |
| audit record | What is sealed before later outcomes? |

A threshold without this charter is a P37/P38 proxy gate.

### 4.6 Entry, exit, restart, and version rules

Escalation and restart are asymmetric. A paused policy cannot return to full exposure because the alert disappeared. Restart requires a separate `RestartEvidenceRecord`: identified repair/version, tests, measurement health, bounded probe/half-open exposure, renewed authority, and historical-claim statement.

A material change creates a new treatment identity unless a predeclared equivalence/pooling rule exists. Proof for `v` does not flow to `v+1` by naming continuity.

### 4.7 Relationship to learning

Only SMDV-1 `prediction_error`, with no blocking contributor and all INT-R4 §4.8 predicates, may enter an effect-posterior proposal. Exploratory signal remains candidate-only even when it triggers containment. Observation change updates measurement epoch; delivery/version updates implementation/version evaluation; behavioral response updates response model; context/interference updates context/coupling; unresolved freezes learning.

Protective action may therefore occur under lower causal certainty than learning. This is deliberate.

### 4.8 No universal numbers and institutional limit

The surveys provide no defensible domain-independent thresholds, detection rates, follow-up horizons, false-signal rates, or reversibility values. Existing DDM `0.25/0.70` cutoffs remain local risk routing. Every future number must name measure, population, horizon, assumptions, and authority source.

The state machine specifies evidence and authority required; it cannot supply authority. At this pin no appointed signer exists for reissue, rollback, termination, or override. Those rungs remain `absent/unallocated`; automation may execute only externally preauthorized transitions represented by admitted evidence.

## 5. Counterexamples And Failure Modes

### 5.1 Joint rider verdicts imported from INT-R4

The authoritative audits are in INT-R4 §§5.1–5.2. OPS-R5 applies them without restating or revising the riders:

| Rider | Correct | Complete | Operable at pin | OPS-R5 consequence |
|---|---|---|---|---|
| GY-O1 performativity | `yes_with_scope` | `no` | `no` | A threshold may open investigation/containment, but only SMDV-1 `prediction_error` can enter discrepancy-driven effect learning. Add expected variation, observation process, version, context/interference, contributors, and unresolved handling. |
| GY-O3 self-confirmation | `yes` | `no` | `no` | A KPI generated through policy-caused observation cannot validate a world edge. Response handling must preserve permanent confirmation quarantine and cannot let generic reprocessing erase it. |

### 5.2 Named failure modes

| ID | Unsafe implementation | Incorrect conclusion | Required behavior |
|---|---|---|---|
| `FM-OPS-01` | Threshold directly changes policy/exposure. | Detector is action authority. | Typed transition request; contract, diagnosis/protective basis, authority. |
| `FM-OPS-02` | Sum result, implementation, guardrail, diagnostic, context, and health metrics. | Benefit compensates safety/validity failure. | Preserve roles; guardrails/validity non-compensable. |
| `FM-OPS-03` | Edit target/outcome/denominator/plan after results without version. | Ex post success is ex ante confirmation. | New semantic epoch and confirmatory reset. |
| `FM-OPS-04` | Treat data revision/definition change as policy effect. | Revised history means historical world changed. | Observation change; correction/revision channel. |
| `FM-OPS-05` | Treat implementation failure as theory failure. | Delivered-zero exposure refutes mechanism. | Delivery/version route. |
| `FM-OPS-06` | Continue full expansion under unresolved high waiting harm. | No causal certainty means no protection. | Preauthorized no-expansion/narrow/pause; learning frozen. |
| `FM-OPS-07` | Auto-redesign on unresolved cause. | Protective uncertainty licenses invention. | Investigation/containment until diagnosis/authority. |
| `FM-OPS-08` | Close monitoring at deployment end/first quiet window. | No short-run signal means no delayed harm. | Horizon registry and maturity. |
| `FM-OPS-09` | Good average clears subgroups/neighbors. | Aggregate proves no distributional/spillover harm. | Separate guardrails. |
| `FM-OPS-10` | Boolean rollback. | Reverting control restores state/outcome/inference. | Reversibility vector and residue. |
| `FM-OPS-11` | Restart when alert disappears. | De-escalation mirrors escalation. | Restart evidence, bounded probe, authority. |
| `FM-OPS-12` | Owner/team string satisfies authority. | Metadata appoints signer. | External appointment evidence; fail absent. |
| `FM-OPS-13` | Retry duplicate transition without idempotency. | Pause/reissue/rollback may execute twice. | Stable identity, dedupe, duplicate record. |
| `FM-OPS-14` | FDR anomaly writes policy/world state. | FDR confers causal/operational authority. | Candidate only; diagnosis/charter mandatory. |
| `FM-OPS-15` | Carry claim across `v → v+1`. | Same label means same treatment. | New version and claim status. |
| `FM-OPS-16` | Owner unavailable after hours. | Silence is approval/full continuation. | Predeclared degraded/containment posture and clock. |
| `FM-OPS-17` | Maintain separate OPS cause vocabulary. | Learning and operations disagree on same movement. | Import SMDV-1; fork is blocking. |
| `FM-OPS-18` | Correction overwrites original decision. | History can be silently repaired. | Append-only supersede/annotate/reissue. |

### 5.3 Hard boundary cases

**Safety signal without diagnosis.** A serious event may open investigation, block expansion, or invoke a preauthorized pause because waiting harm is high. It may not label causation, update effect, or terminate under unappointed discretion.

**Metric improves while observation health degrades.** The primary KPI remains uninterpretable for substantive adaptation. `measurement_health` blocks result interpretation; it is not averaged with benefit.

**Implementation repair changes treatment.** A necessary repair altering eligibility, dose, or rule creates a new version. The old claim becomes under review/exploratory unless predeclared adaptive design covered it.

**Owner unavailable during a fast incident.** The contract must already state whether automation may hold, narrow, pause, or only page. Urgency cannot manufacture authority.

## 6. Benchmark Or Fixture Proposal

### 6.1 Two-layer benchmark and fixed response denominator

OPS-R5 consumes INT-R4's fixed 24-case diagnosis corpus and adds a **20-scenario governed-response corpus**. The response corpus tests whether the same diagnosis/evidence state produces the correct permitted action without authority leakage.

| Action family | Scenarios | Examples |
|---|---:|---|
| `A0_observe` | 2 | Model-compatible movement; immature delayed outcome. |
| `A1_investigate` | 3 | Calibrated anomaly; conflicting sensors; unknown subgroup signal. |
| `A2_contain` | 3 | No-expansion under unresolved high waiting harm; narrowed geography; protective notice. |
| `A3_refresh` | 3 | Routine revision; series bridge; measurement recalibration. |
| `A4_adjust` | 3 | Delivery repair; version-specific narrowing; partial reissue. |
| `A5_pause_or_rollback` | 3 | Reversible control; irreversible residue; emergency pause then probe. |
| `A6_terminate_or_redesign` | 3 | Confirmed harm; failed legal clock; retired claim/redesign. |
| **Total** | **20** | Fixed response denominator. |

This is benchmark composition, not a frequency estimate.

### 6.2 Scenario packet

```text
KPIControlContract and version
DDM/report/revision/incident signals
maturity, uncertainty, censoring, observation health
SMDV-1 diagnosis or unresolved state
current E/X/V/C coordinates
transition charter
waiting and premature-action evidence
reversibility vector and blast radius
authority evidence or explicit absence
expected and forbidden transitions
claim/version/public-history consequences
restart conditions and replay expectation
```

### 6.3 Required negative fixtures

The response corpus includes threshold with no diagnosis/emergency charter; FDR anomaly attempting world write; definition edited after results; KPI roles collapsed to score; good average with blocked subgroup; implementation failure routed to model refutation; unresolved high-waiting-harm case where containment is allowed and learning forbidden; unresolved low-waiting-harm investigation; owner unavailable; duplicate pause/rollback; late correction after reissue; rollback restoring control but not state/outcome/inference; restart without probe; `v+1` retaining `v` claim; silent historical rewrite; SMDV-1 fork; authority by owner string; malicious denominator change under valid schema; multiplicity-controlled subgroup anomaly without confirmatory claim; and legal review clock under unresolved cause.

### 6.4 Tabletop and fault-injection variants

Replay with signal provider unavailable; diagnosis worker killed after partial writes; duplicate/out-of-order amendments; two workers attempting one irreversible transition; mass KPI invalidation; conflicting implementation/measurement evidence; signer unavailable through deadline; quarantine available while world-write consumer is stale; branch advanced while public projection points to old claim; and retained-snapshot recovery followed by reconciliation.

### 6.5 Non-compensable measures

Over the fixed 20 scenarios:

```text
threshold_auto_action_escape_count
diagnosis_bypass_count
unauthorized_transition_count
protective_action_missed_count
posterior_learning_bypass_count
world_write_bypass_count
restart_without_evidence_count
silent_version_reuse_count
duplicate_irreversible_action_count
historical_rewrite_count
subgroup_or_spillover_mask_count
owner_absence_treated_as_approval_count
time_from_signal_to_safe_containment
time_from_evidence_completion_to_correct_transition
```

The first twelve counts are separate guardrails. Speed cannot compensate unauthorized action or historical rewrite.

### 6.6 Research acceptance proxy

A later prototype may claim only benchmark conformance when all 24 diagnosis cases and 20 response scenarios are processed; SMDV-1 has one registered location and no OPS fork; thresholds without charters open at most investigation; threshold-auto-action, diagnosis bypass, unauthorized transition, posterior/world bypass, restart-without-evidence, silent-version-reuse, duplicate irreversible action, and historical rewrite counts are zero; protective containment still occurs in predeclared high-waiting-harm unresolved cases; and remove-the-property/keep-the-markers probes turn red.

No production threshold for latency or false-block rate is set here. A domain consequence model, operator study, and appointed authority are prerequisites.

## 7. Artifact Contract Sketch

## 8. Later Integration Handoff

## 9. Promotion And Kill Rules

## 10. Open Questions For Consolidation
