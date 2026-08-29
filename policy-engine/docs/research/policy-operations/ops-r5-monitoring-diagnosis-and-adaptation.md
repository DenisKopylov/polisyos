---
title: OPS-R5 — Monitoring Diagnosis And Governed Adaptation
status: stage_1_research_complete
kind: deep-research
research_task: OPS-R5
joint_with: INT-R4
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r4-ops-r5-research
repository_baseline: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
inspection_date: 2026-08-29
research_only: true
shared_vocabulary_owner: false
shared_vocabulary: SMDV-1
shared_vocabulary_location: ../int-r4-performative-effect-update-diagnosis.md#4-result
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

OPS-R5 treats a KPI as a decision-linked contract, not a number with a band. It owns the research question for contract, diagnosis, and response semantics while integrating data collection. It absorbs OPS-R6, the adaptation ladder, and is the declared joint binding input with INT-R4 (`policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:527-531`).

The same observed movement may invite an operational response and be offered to a learning system. The pair therefore cannot tolerate two diagnosis vocabularies. The sole candidate vocabulary is **SMDV-1**, derived and owned in [INT-R4 §4](../int-r4-performative-effect-update-diagnosis.md#4-result). This document imports its classes, precedence, exhaustiveness boundary, and unresolved policy unchanged.

### 1.2 Four-way custody boundary

The ratified §6 ruling is exact: KPI control contract and diagnosis semantics are **OWN contract / INTEGRATE data collection** (`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:86-124`). PolicyOS owns construct/definition/version, lineage/basis, population/timing, uncertainty, gaming exposure, response table, and its own claim reaction. Sensors and institutional decisions are external typed evidence. PolicyOS does not appoint a DSMB, regulator, airworthiness authority, metric steward, product owner, or sovereign policy decision-maker.

### 1.3 Exact controlled operation and false claim prevented

The controlled operation is any transition changing exposure, implementation, policy version, claim status, publication status, or model/world state because a monitored quantity moved.

This task prevents:

> “The KPI crossed a threshold, therefore the cause is known and the system may automatically adjust, pause, roll back, terminate, or learn.”

Detection may open review or protective containment. It must not silently establish cause or authority.

### 1.4 Absorbed OPS-R6 coverage

OPS-R6 is covered as a governed response state machine, not an asserted universal linear ladder:

- observation, warning, diagnosis: §§3–7;
- refresh, recompute, recalibration: §§4, 7, 9;
- implementation adjustment, scope narrowing: §§4, 7, 9;
- partial reissue, redesign, pause, rollback, termination: §§4, 6, 7, 9;
- entry/exit evidence, restart, reversibility, authority: §§3, 4, 7, 9.

Absorption is coverage only; it moves no capability.

## 2. Current Repo Baseline

### 2.1 Pin and inspection boundary

Repository evidence is pinned to `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`. Mandatory architecture anchors and focused owners were inspected: `AGENTS.md`; contributor baseline; ratified identity; organizing rules; target architecture; operating model; honest diagnostics; north star; failure register; GY/Atlas plans; distillation ledger; DDM/FDR; delayed-label monitors; monitoring/evaluation; continuous governance; S13; N8 value gate; world branches; and quarantine.

Ordinary Git transport could not resolve `github.com`, so no local P35-compliant complete `rg`/`git grep` census was executed. Connector search is not a denominator. No repository-wide zero is claimed; census standing is `not_established`. Details are in [ops-r5/evidence-register.md](ops-r5/evidence-register.md).

### 2.2 Current monitoring distinguishes signal kinds

DDM separates calibrated shift, realized/estimated degradation, data-quality failure, readiness, incidents, and root-cause localization (`policy-engine/src/polisyos/ddm/integration/events.py:1-232`). Realized monitors retain intervals and label-delay horizons (`policy-engine/src/polisyos/ddm/detectors/realized_performance_monitor.py:1-151`); data-quality checks retain schema/null/type/range/value/freshness violations (`data_quality_monitor.py:1-142`); FDR records alpha spending/discoveries (`calibration/multiple_testing.py:1-89`).

Track-2.2 maps local severity cutoffs `0.25` and `0.70` to `watch`/`investigate` (`policy-engine/src/polisyos/ddm/detectors/track_2_2_shift_adapter.py:44-62`). These are local DDM risk-routing choices, not general policy thresholds or cause tests.

### 2.3 Monitoring and lifecycle primitives exist

`ImplementationMonitoringEvaluationRecord` requires indicators, windows, cadence, thresholds, owners, estimand, comparison strategy, DDM evidence, claim links, and publication ordering (`policy-engine/src/polisyos/runtime/quality/ddm_monitoring.py:1-287`). Continuous governance types invalidation, calibration/fairness/context drift, and incidents and recommends monitor/stale/review/reissue/withdrawal review (`policy-engine/src/polisyos/scientist/governance/continuous/monitors.py:1-113`).

They do not bind construct semantics, definition version, baseline vintage, KPI role, gaming exposure, observation health, SMDV-1 diagnosis, permissible response, restart evidence, and institutional authority into one admitted contract.

### 2.4 Adjacent S13 attribution exists

S13 has an eight-class post-deployment attribution/accountability vocabulary, but fixtures supply the class directly (`policy-engine/src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py:43-58`, `:164-221`; `policy-engine/tests/fixtures/layer2/s13/s13_post_deploy_case_signals.json:4-204`). Thus the zone is not wholly greenfield. The exact joint evidence-derived movement diagnosis controlling both adaptation and learning remains unallocated.

### 2.5 GY preserves signal/authority separation but is build-new

GY-O2 keeps DDM/FDR anomalies `candidate_unverified`; O1 requires cause typing; O3 requires confirmation and an observation-process negative (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:5043-5095`). This is the right plan boundary, not implementation evidence.

### 2.6 World and quarantine substrates exist

Fabric supplies append-only correction/revocation, bitemporal snapshots, governed branches, and branch evidence (`policy-engine/docs/reference/fabric/time-travel.md:1-111`). Generic quarantine persists record/payload/reprocess lineage (`policy-engine/src/polisyos/fabric/data_plane/quarantine.py:1-106`, `:220-463`). These can carry response records but cannot decide causal usability or erase O3's permanent confirmation ban.

### 2.7 Institutional authority is absent

No institutional signer is appointed for reissue, rollback, termination, or discretionary override. Repository owner/team strings are not appointments. Those rungs remain `absent/unallocated`.

### 2.8 Current capability and reuse-first path

The repository can detect, localize, retain, and route signals and preserve history. It cannot demonstrate:

```text
KPI contract + matured observation
→ trust/measurement checks
→ SMDV-1 diagnosis
→ typed permissible transition
→ competent authorization where required
→ append-only action/reissue/refusal record
→ separate restart gate and replay
```

Joint capability standing is `absent/unallocated`. The smallest path reuses DDM events, `ddm_monitoring`, continuous governance, S13, Fabric, and Atlas; the durable Group-B control state belongs in the proposed H2 custody-runtime plan, not as a new subsystem appended to GY.

## 3. External Research Baseline

### 3.1 Source posture and dependency on INT-R4

OPS-R5 uses the same five `institutionally_supplied` surveys described in INT-R4 §3. It does not re-derive cause categories. S4 supplies metric-contract and gaming evidence; S3 detection/diagnosis/residue; S2 response/versioning/stopping/reversibility; S1 and S5 endogenous observation, censoring, latency, and interference.

### 3.2 A KPI contract is more than a threshold

No surveyed domain has one universal “metric contract” standard. Recurring fields are construct, definition/version, lineage/instrument, unit/basis, aggregation, population/denominator/exclusions, subgroups, baseline vintage, target type/band, role, lag/window, revision policy, uncertainty, gaming exposure, owner, decision rights, response semantics, and immutable history (S4:5-64, 146-243, 248-365).

The transferable pattern is:

```text
predeclared meaning
→ qualified observation
→ permitted decision type
→ authorized actor
→ required record and escalation
```

A threshold may open investigation without deciding cause or legality.

### 3.3 Metric roles are non-compensable

S4 distinguishes objective/OEC, guardrail, diagnostic, and data-quality metrics. They answer different questions; benefit cannot buy safety or validity. Candidate roles here are `result`, `implementation`, `guardrail`, `leading`, `diagnostic`, `context`, and `measurement_health`. This is a candidate adaptation, not a registered external taxonomy. Roles may coexist but cannot be summed into one authority score.

### 3.4 No universal linear ladder

Trials, aviation, nuclear operations, software delivery, circuit breakers, sandboxes, and sunset clauses control different risks. What transfers is precommitment: measure, review point, sufficient evidence, permitted action, authority, uncertainty behavior, restart, and irreversibility (S2:5-82, 84-137, 303-377). Therefore response is multi-axis. Protective action may precede diagnosis; learning and confirmatory claims may not.

### 3.5 Reversibility is a vector

```text
R_control      stop further exposure
R_state        restore prior system state
R_outcome      repair harm already caused
R_inference    recover original information process
```

Software rollback may restore control but not state; trial stopping cannot undo treatment; legal repeal cannot restore prior behavior. A boolean `reversible` is unsafe (S2:139-190).

### 3.6 Unknown, delayed harm, and missing channels

“No signal = no harm” is unsupported. Gates need maturity, censoring, attrition, detection probability, and horizon evidence. Exited, rejected, never-entered, and neighboring populations require external channels or `unquantified`; aggregate benefit does not clear subgroup/spillover harm (S5:5-19, 21-131, 179-300).

Uncertainty may justify no-expansion, narrowing, or preauthorized pause, but cannot close harm, validate a positive, authorize learning, or replace an absent signer.

### 3.7 Exploratory versus confirmatory

Adaptive anomaly/subgroup discovery remains exploratory. Confirmatory claims require frozen estimand, outcome definition, version, population, horizon, and multiplicity plan followed by prospective evidence. A canary or FDR-controlled anomaly is not efficacy evidence. Material intervention/eligibility/measurement/analysis change resets claim status unless a predeclared adaptive design covered it (S2:214-301; S5:179-203).

## 4. Result

### 4.1 Result type

**Result: `accepted_narrow_scope`.** OPS-R5 specifies a candidate `KPIControlContract` and governed response state machine, both consuming SMDV-1. They are research-only: no owner appointed, no threshold selected, no action authorized.

### 4.2 Candidate `KPIControlContract`

#### Semantic layer

```text
contract/content identity; construct/claim; metric roles
definition/version; unit/basis; numerator/denominator/exclusions
aggregation/non-compensability; population/subgroup/spillover frames
baseline value/vintage; direction; target type/band
```

#### Observation layer

```text
source/lineage; instrument/implementation
observation/valid/transaction/decision times
cadence/lag/seasonality/maturity
censoring/attrition/missing channels
revision/correction/backcast/series break
uncertainty/detection-capability statement
sentinel/negative-control/independent-channel refs
gaming/endogenous-measurement exposure register
```

#### Decision layer

```text
trigger semantics; admissible evidence; identification threshold
waiting loss; premature-action loss; reversibility vector; blast radius
permitted protective/substantive actions; SMDV-1 requirement
claim/version consequence; restart/de-escalation evidence
```

#### Authority/custody layer

```text
metric steward and definition-change rights
data producer/integration boundary; decision/override authority
owner-unavailable/after-hours behavior
public meaning during review/pause/reissue/withdrawal
append-only audit/supersession/replay; rule/schema/authority refs
```

Omissions are typed and scoped; absence never grants power.

### 4.3 Governed response coordinates

These are internal evidence/permission coordinates projected into the one Atlas lattice, not a competing status system:

```text
Epistemic:   E0 normal | E1 signal | E2 credible_anomaly |
             E3 diagnosed_mechanism | E4 confirmed_unacceptable
Exposure:    X0 full | X1 no_expansion | X2 narrowed | X3 paused | X4 terminated
Intervention: V0 unchanged | V1 recalibrated | V2 patched_or_reissued |
              V3 redesigned | V4 rolled_back
Claim:       C0 confirmatory_intact | C1 under_review |
             C2 exploratory_only | C3 withdrawn
```

### 4.4 Action families — absorbed OPS-R6

| Family | Actions | Minimum posture | Automatic authority? |
|---|---|---|---|
| `A0_observe` | retain, mature, collect denominator/follow-up | E0 or immature signal | only inside predeclared monitoring contract |
| `A1_investigate` | validate data, open diagnosis, acquire sentinel/implementation/context | E1 | case creation may be automatic; no substantive change |
| `A2_contain` | no expansion, degraded mode, scope cap, protective notice | E1/E2 plus waiting-harm/guardrail basis | only preauthorized; otherwise escalate |
| `A3_refresh` | correct/revise data, bridge series, recompute, recalibrate measurement | diagnosed observation/data issue | no policy-effect update; preserve revision provenance |
| `A4_adjust` | repair implementation, narrow scope, partial reissue, version-specific change | E3 plus SMDV-1 class and authority | human/institutional where policy changes |
| `A5_pause_or_rollback` | pause exposure, rollback future control, withdraw operational permission | E2/E3/E4 by risk/reversibility | only preauthorized emergency rule or competent decision |
| `A6_terminate_or_redesign` | terminate, redesign, re-ratify, retire claim | E4 or unresolved beyond legal/safety clock | never from threshold alone |

Diagnosis and action are separate. `diagnosis_unresolved` may support investigation, containment, or a preauthorized pause under high waiting harm; never learning or unreviewed redesign.

### 4.5 Transition charter

Every transition changing exposure/version/claim status requires trigger, admissible evidence, information maturity, measurement-validity test, SMDV-1 requirement, waiting/premature-action loss, reversibility vector, blast radius, VOI/next evidence, legal/governance clock, decision and override authority, restart criteria, version consequence, claim consequence, and audit record. A threshold without this charter is a P37/P38 proxy gate.

### 4.6 Restart and version rules

Escalation and restart are asymmetric. Alert disappearance does not restore full exposure. Restart requires identified repair/version, tests, measurement health, bounded probe/half-open exposure, renewed authority, and historical-claim statement. A material change creates a new treatment identity unless a predeclared equivalence/pooling rule exists.

### 4.7 Relationship to learning

Only SMDV-1 `prediction_error`, with no blocking contributor and all INT-R4 §4.8 predicates, may enter effect-posterior proposal. Observation change updates measurement epoch; delivery/version updates implementation/version evaluation; behavioral response updates response model; context/interference updates coupling/context; unresolved freezes learning. Protective action may occur under lower causal certainty than learning.

### 4.8 No universal numbers and institutional limit

No defensible domain-independent threshold, detection rate, follow-up horizon, false-signal rate, or reversibility value is supplied. DDM `0.25/0.70` remains local routing. Future numbers must name measure, population, horizon, assumptions, and authority source.

No signer is appointed for reissue, rollback, termination, or override. The state machine can name required authority; it cannot supply it.

## 5. Counterexamples And Failure Modes

### 5.1 Joint rider verdicts imported from INT-R4

| Rider | Correct | Complete | Operable at pin | OPS consequence |
|---|---|---|---|---|
| GY-O1 performativity | `yes_with_scope` | `no` | `no` | Threshold may open investigation/containment; only SMDV-1 `prediction_error` may enter discrepancy-driven learning. |
| GY-O3 self-confirmation | `yes` | `no` | `no` | Policy-generated observation cannot validate a world edge; permanent confirmation quarantine must survive generic reprocessing. |

The authoritative three-question audits are INT-R4 §§5.1–5.2; this document does not re-derive them.

### 5.2 Failure register

| ID | Unsafe conclusion | Required safe behavior |
|---|---|---|
| `FM-OPS-01` | Threshold is action authority. | Typed request + charter + diagnosis/protective basis + authority. |
| `FM-OPS-02` | Benefit compensates guardrail/validity failure. | Non-compensable roles. |
| `FM-OPS-03` | Ex post metric edit preserves confirmation. | New semantic epoch and confirmatory reset. |
| `FM-OPS-04` | Data revision is policy effect. | Observation-change revision channel. |
| `FM-OPS-05` | Implementation failure refutes theory. | Delivery/version route. |
| `FM-OPS-06` | Unresolved cause forbids protection under high waiting harm. | Preauthorized contain/pause; learning frozen. |
| `FM-OPS-07` | Unresolved cause licenses redesign. | Investigate/contain until diagnosis/authority. |
| `FM-OPS-08` | Quiet short window proves no delayed harm. | Horizon/maturity/unquantified state. |
| `FM-OPS-09` | Good average clears subgroup/spillover. | Separate guardrails. |
| `FM-OPS-10` | Rollback restores control/state/outcome/inference. | Reversibility vector and residue. |
| `FM-OPS-11` | Alert disappearance is restart evidence. | Separate bounded probe and authority. |
| `FM-OPS-12` | Owner/team string appoints signer. | External appointment evidence. |
| `FM-OPS-13` | Duplicate irreversible transition may execute twice. | Content identity, dedupe, duplicate record. |
| `FM-OPS-14` | FDR anomaly confers causal/operational authority. | Candidate only. |
| `FM-OPS-15` | `v+1` inherits `v` claim. | New version/claim status or predeclared pooling proof. |
| `FM-OPS-16` | Owner silence after hours means approval/full continuation. | Predeclared degraded posture and escalation clock. |
| `FM-OPS-17` | OPS may define another cause vocabulary. | Import SMDV-1; fork is blocking. |
| `FM-OPS-18` | Later correction may overwrite original decision. | Append-only supersede/annotate/reissue. |

### 5.3 Hard boundary cases

A serious safety signal may block expansion or invoke a preauthorized pause before cause is settled, but cannot establish causation or learning. A KPI improvement with degraded observation health remains uninterpretable. An implementation repair that changes eligibility/dose/rule creates a new version. Owner unavailability cannot manufacture emergency authority.

## 6. Benchmark Or Fixture Proposal

### 6.1 Fixed two-layer benchmark

OPS-R5 consumes INT-R4's **24-case** movement corpus and adds a **20-scenario** response corpus:

| Family | Scenarios |
|---|---:|
| `A0_observe` | 2 |
| `A1_investigate` | 3 |
| `A2_contain` | 3 |
| `A3_refresh` | 3 |
| `A4_adjust` | 3 |
| `A5_pause_or_rollback` | 3 |
| `A6_terminate_or_redesign` | 3 |
| **Total** | **20** |

This is a test denominator, not prevalence.

### 6.2 Scenario packet and negative cases

Each packet carries contract/version; DDM/report/revision/incident signals; maturity/uncertainty/censoring/health; SMDV-1 diagnosis or unresolved; current E/X/V/C; charter; waiting/premature losses; reversibility/blast radius; authority or absence; expected/forbidden transitions; claim/version/public-history consequences; restart and replay.

Required negatives include threshold without charter; FDR anomaly attempting world write; target edited after results; role vector collapsed; blocked subgroup under good average; implementation failure routed to model refutation; unresolved high-harm containment with learning forbidden; unresolved low-harm investigation; owner unavailable; duplicate pause/rollback; late correction; rollback residue; restart without probe; `v+1` retaining `v` claim; silent rewrite; SMDV fork; authority by owner string; malicious denominator change under valid schema; multiplicity-controlled exploratory subgroup alarm; and legal review clock under unresolved cause.

### 6.3 Fault-injection variants

Replay with provider unavailable; worker killed after partial writes; duplicate/out-of-order amendments; concurrent irreversible requests; mass invalidation; conflicting implementation/measurement evidence; signer unavailable through deadline; quarantine available while world consumer is stale; branch/public projection divergence; and retained-snapshot recovery/reconciliation.

### 6.4 Non-compensable measures

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
time_signal_to_safe_containment
time_evidence_complete_to_correct_transition
```

The first twelve counts are separate guardrails. Prototype conformance requires zero authority/learning/write/restart/version/duplicate/rewrite escapes while still containing predeclared high-waiting-harm unresolved cases. Production latency/false-block thresholds are not set here.

## 7. Artifact Contract Sketch

### 7.1 Candidate artifacts

| Artifact | Minimum fields/purpose | Boundary |
|---|---|---|
| `KPIControlContract` | Content ID; claim/construct; roles; definitions/versions; population/denominator/subgroups/spillover; baseline vintage; observation protocol; uncertainty; gaming exposure; action charter; authority/override; time/rule/schema refs. | Governs interpretation and requested response for this metric; never appoints authority or proves a cause. |
| `AdaptationTransitionRequest` | Contract/signal/diagnosis refs; current and requested E/X/V/C; action family; waiting/premature loss; reversibility/blast radius; clock; proposed claim/version consequence; requester provenance. | Candidate request only; cannot execute protected transition. |
| `AdaptationDecisionRecord` | Request ref; admitted evidence; signer/authority evidence; allowed/denied/modified transition; reason; override; effective time; public meaning; idempotency key; supersession. | Authoritative only for the named transition if signer and input closure pass. |
| `RestartEvidenceRecord` | Prior decision; repair/version; tests; measurement health; bounded probe; residual harms; renewed authority; historical-claim status; expiry. | Only for reopening/de-escalation; never inferred from signal disappearance. |
| `KPIControlStateSnapshot` | Current contract version; E/X/V/C coordinates; open diagnosis/actions; clocks; owner availability; latest decision/restart refs; public projection refs. | A read model/projection; cannot mint transition authority. |

Signals remain existing DDM/monitoring/incident/revision artifacts referenced by identity. Do not create a parallel `MonitoringSignalRecord` unless an owner-gap analysis proves one is required.

All governed IDs are content/input-closure derived; retries and duplicates resolve to one transition identity. Processing timestamps do not define semantic identity.

### 7.2 State machine — Operational addendum step 3

```text
normal
  → signal_open
       → observation_invalid       refresh/correct; no substantive action
       → diagnosis_pending
            → unresolved_review    investigate / preauthorized contain / clock
            → diagnosed
                 → transition_requested
                      → awaiting_authority
                           → denied
                           → authorized
                                → executing
                                     → partially_applied
                                     → applied
                                     → failed_safe
  → restart_pending
       → bounded_probe
            → remain_contained
            → restart_authorized
                 → reopened
  → terminated_or_withdrawn
```

E/X/V/C coordinates are carried through states; they do not replace Atlas lifecycle status. Duplicate events append a duplicate disposition without repeating an irreversible action. Late evidence may open correction/supersession, not rewrite.

### 7.3 Time, clocks, expiry, and public meaning

Load-bearing roles: metric-definition effective time; baseline vintage; observation/valid/transaction time; detection time; maturity horizon; diagnosis time/expiry; review/escalation/legal clock; decision time; transition effective time; restart-probe window; replay time. Owner absence starts the declared escalation/degraded-mode clock; it does not approve a transition.

Public meaning must distinguish `monitoring`, `under_review`, `no_expansion`, `narrowed`, `paused`, `reissued`, `superseded`, and `withdrawn` through the existing Atlas/lifecycle vocabulary. E/X/V/C are internal evidence coordinates only.

### 7.4 Predicate provenance and proxy divergence

Gate predicates include metric-definition identity; denominator/population integrity; observation maturity/health; SMDV-1 diagnosis; waiting and premature-action evidence; reversibility; signer competence; successful execution; and restart evidence. Each receives W4-K02's registered provenance label. Only `recomputed` or `independently_reconciled` may carry a positive protected-action gate. An owner field, threshold flag, completion status, or successful API call is a proxy unless it constructs the required property.

### 7.5 Canonical-owner map

| Function | Existing/likely owner | Disposition |
|---|---|---|
| Shift/degradation/quality/FDR | `polisyos.ddm` | Reuse; candidate evidence only. |
| Monitoring/evaluation specification | `runtime/quality/ddm_monitoring.py` | Extend/compose; no parallel plan. |
| Post-publication validity/reissue/withdrawal recommendation | continuous governance | Reuse lifecycle links; do not duplicate. |
| Movement diagnosis | INT-R4 SMDV-1 candidate beside S13 | Consume one vocabulary; producer absent. |
| Accountability/component update routing | S13 | Compose after diagnosis; no owner bypass. |
| Durable Group-B transition state, clocks, idempotency | proposed H2 custody-runtime plan | Correct implementation home; currently `absent/unallocated`. |
| GY O1/O3 | GY | Supplies/consumes learning/world consequences; must not own whole response runtime. |
| Persistence/history | CAS + Fabric branches/time-travel | Reuse append-only substrate. |
| Surface/status projection | Atlas + continuous-governance public surfaces | Projection only; no authority minting. |
| Institutional decision/override signer | external institution; none appointed | `absent/unallocated`. |

## 8. Later Integration Handoff

### 8.1 Producer-to-surface chain

| Layer | Handoff |
|---|---|
| Producer | Existing DDM, data quality, delayed-label, incident, revision, implementation, context, and external sensor producers. |
| Persisted artifact/event | Existing signal artifacts plus candidate KPI contract, transition request, decision, restart, and state snapshot. |
| Bridge | H2 custody-runtime state machine consumes admitted signals/diagnosis; GY consumes only explicit learning/world consequences; continuous governance consumes validity/reissue/withdrawal consequences. |
| Consumer | Policy/exposure executor is external; PolicyOS consumes execution evidence and changes only its own claim/custody state. Posterior/world consumers remain GY O1/O3. |
| Verification | 24 diagnosis + 20 response cases, idempotency/concurrency, delayed/duplicate/contradictory events, actual protected-action consumer probes, recovery/replay. |
| Surface | Atlas operator/reviewer/machine/public projections; status derived from the one lattice, with contract version, diagnosis, authority, clocks, and restart evidence. |

### 8.2 Real operator workflow — Operational addendum step 2

1. **Data/measurement producer** emits versioned observation and health evidence; PolicyOS verifies/adopts or quarantines it.
2. **Monitoring service/on-call operator** receives DDM/report/incident signal and opens a case; no cause is implied.
3. **Metric steward/diagnosis analyst** checks definition, denominator, maturity, implementation, context/interference, behavior, and SMDV-1 evidence.
4. **Implementation owner** supplies delivery/version/exposure evidence and proposes repair where applicable.
5. **Institutional decision authority** approves/denies protected transition; PolicyOS verifies authority and records the decision.
6. **External executor** applies operational change and emits execution evidence; PolicyOS never substitutes itself for execution.
7. **Justification custodian** updates PolicyOS claim/public state, preserves history, and schedules restart/review.

After hours, only actions explicitly preauthorized by the contract may execute—typically page, open investigation, no-expansion, bounded degraded mode, or emergency pause. If the owner is unavailable, the contract selects the conservative declared state and escalation clock. Silence is never approval. Failure to receive execution evidence leaves the transition pending/failed-safe, not successful.

### 8.3 Engineering versus research/institutional blockers

**Engineering:** contract storage; durable state/clocks; diagnosis bridge; idempotent transition records; execution-evidence ingestion; restart; replay/recovery; Atlas projection; fixtures.

**Research/institutional:** domain thresholds and consequence models; acceptable false-block/containment trade-offs; SMDV disposition; detection/maturity horizons; treatment-version pooling; independent oracle; operator studies; signer/override appointment.

### 8.4 Absorbed OPS-R6 handoff

All ladder actions are represented by `A0`–`A6`, but authority, entry/exit evidence, restart, reversibility, version consequences, and public meaning are mandatory. Implementing only a list of action names would silently lose the absorbed task.

### 8.5 OPS-R15 capstone linkage

The custody-cycle capstone should replay:

```text
published claim
→ monitored signal
→ diagnosis / unresolved
→ protective or substantive transition request
→ authority decision
→ external execution evidence
→ claim revalidation/reissue/withdrawal
→ restart or terminal state
→ historical replay from the original epoch
```

A capstone that stops at detector output or transition request does not close OPS-R5/OPS-R6.

### 8.6 Non-effect

This handoff does not change policy, exposure, posterior, world edge, public claim, capability label, owner, or authority.

## 9. Promotion And Kill Rules

### 9.1 Research-only — current state

Required because SMDV-1 is unregistered; response corpus unexecuted; durable state-machine owner/bridge/consumer absent; no signer; operator performance and domain thresholds unknown; complete repository census not established.

### 9.2 Prototype allowed

Shadow prototype only when:

- one experimental SMDV-1 ref is shared with INT;
- KPI/transition/restart artifacts are strict and content-bound;
- DDM, monitoring, continuous governance, S13, Fabric, and Atlas owners are extended rather than duplicated;
- no prototype path reaches external execution, protected claim change, posterior/world write, publication, or approval;
- 24+20 public fixtures, concurrency/idempotency, and property-removal probes run;
- owner absence and unresolved diagnosis fail safely.

### 9.3 Governed allowed

Requires:

- vocabulary/governance disposition;
- complete producer→artifact→H2 bridge→decision consumer→execution-evidence intake→claim reaction→surface chain;
- one Atlas/lifecycle status composition;
- actual protected-action consumers fail closed on absent diagnosis/authority;
- content-bound versions, maturity, subgroup/spillover, and restart predicates;
- zero threshold-auto-action, diagnosis bypass, unauthorized transition, learning/world bypass, duplicate irreversible action, silent version reuse, historical rewrite, and owner-absence-as-approval escapes;
- appointed competent signer or explicit preauthorization for each automated transition;
- historical replay and failure recovery.

### 9.4 Production candidate

Additionally requires named domain/population/metrics; measured operating characteristics and containment trade-offs; operator/after-hours studies; external execution integration; long-tail and no-channel harm monitoring; privacy/security/legal review; tabletop/fault injection; rollback/recovery drills; and ratified release authority. Benchmark passage remains bounded to revision, corpus, environment, oracle, and rule version.

### 9.5 Block/kill conditions

Block or withdraw if:

- an OPS diagnosis vocabulary differs from SMDV-1;
- threshold, detector, FDR discovery, owner string, or completion flag authorizes action;
- guardrail/validity roles become compensable;
- unresolved defaults to full expansion, learning, or redesign without charter/authority;
- owner absence is approval;
- restart occurs without independent evidence/probe;
- `v+1` silently inherits `v` claim;
- duplicate irreversible action executes;
- correction overwrites history;
- an O3-quarantined confirmation reaches world write;
- public projection mints authority;
- no appointed signer exists for a protected transition.

Gate standing remains `NO_GO`.

## 10. Open Questions For Consolidation

### 10.1 Questions

1. Which H2 custody-runtime artifact owns durable transition state, clocks, idempotency, and recovery?
2. How should E/X/V/C coordinates project into the existing Atlas lattice without adding statuses?
3. Which continuous-governance recommendation types are reused directly, and where is an authority delta required?
4. Which action families may be preauthorized automatically, by which institution, for which risk class?
5. Who is the metric-definition steward, transition signer, override signer, and after-hours substitute?
6. What domain-specific waiting/premature-action loss model selects containment intensity?
7. What observation maturity and delayed-harm horizons are required per KPI?
8. How are subgroup/spillover guardrails composed without uncontrolled multiplicity or hiding unmeasured groups?
9. Which version changes require full reissue, partial reissue, claim downgrade, or termination?
10. How is external execution evidence verified and what happens when it is late/contradictory?
11. How is permanent O3 confirmation quarantine protected from generic reprocessing?
12. Which Atlas/public surfaces communicate unresolved cause, protective action, and absent signer without overstating certainty?
13. What OPS-R15 capstone oracle adjudicates correct response and historical replay?

### 10.2 Classified finding summary

| Finding | Classification | Disposition |
|---|---|---|
| DDM/monitoring/lifecycle/world fragments exist. | `confirmed` | Reuse; no authority promotion. |
| Exact KPI-contract→diagnosis→authorized-response chain is absent. | `confirmed` | `absent/unallocated`; route to H2 + GY/Atlas consumers. |
| Governed metric needs semantic, observation, decision, authority layers. | `accepted_narrow_scope` | Candidate contract for consolidation. |
| Universal linear ladder is refuted by domain differences. | `refuted` | Use multi-axis coordinates + action families. |
| Protective action may precede diagnosis while learning freezes. | `confirmed` | Preserve purpose/authority separation. |
| Universal thresholds and detection rates do not exist. | `deferred_open_problem` | Domain-specific evidence required. |
| No institutional signer exists. | `blocked` | Institutional appointment required. |
| Complete repository-wide census was not executed. | `deferred_open_problem` | `not_established`; no zero claim. |

### 10.3 W4-K05 standing

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

Research acceptance neither implements capability nor opens a gate.

## Operational Closure Addendum

### 1. Boundary census

| Function | Four-way verdict | Owner mapping |
|---|---|---|
| KPI meaning/version/decision linkage and PolicyOS claim reaction | OWN | Existing partial owners; missing H2 bridge. |
| Data collection, sensor operation, execution of policy change | INTEGRATE | External producer/executor. |
| Institutional succession/availability/authority status | OBSERVE/INTEGRATE evidence | External institution. |
| Administrative casework, notices, payments, enforcement | OUT_OF_SCOPE except typed evidence | External sovereign/commodity systems. |
| DDM detection/FDR | OWN existing diagnostic substrate | `polisyos.ddm`. |
| Durable response state/clocks/idempotency | OWN mechanical custody core | Missing; proposed H2 owner. |
| Protected transition decision | INTEGRATE authority act | No appointed signer. |

### 2. Real operator workflow

Specified in §8.2, including normal flow, external execution evidence, failure, owner unavailable, and after-hours behavior.

### 3. State machine

Specified in §7.2 with clocks/expiry/public meaning in §7.3, terminal/reopen behavior, duplicate handling, and one-lattice projection.

### 4. Typed artifacts

Specified in §7.1 with authority boundaries, provenance, versions/time, content identities, transition/restart semantics, and owner map.

### 5. Edge-case fixtures

Specified in §6: happy path; missing/late/duplicate/conflicting evidence; owner unavailable; malicious denominator; degraded mode; partial execution; rollback residue; version transition; historical replay; subgroup/spillover; O3 quarantine; vocabulary fork.

### 6. Tabletop / fault injection

Specified in §6.3: provider failure, killed worker, duplicate amendment, concurrent irreversible request, mass invalidation, conflicting evidence, absent signer, stale consumer, projection/head divergence, snapshot recovery/reconciliation. Success requires no duplicate protected action, no false completion, preserved history, conservative degraded state, and eventual reconciliation or explicit terminal failure.

### 7. Capstone linkage

Specified in §8.5. OPS-R15 must test the complete custody cycle from published claim through signal, diagnosis, transition authority, external execution evidence, claim reaction, restart/termination, and historical replay.

## Pattern Pass

| Pattern | Risk found | Result/routing |
|---|---|---|
| `P01` | KPI/transition contracts could be called capability. | Standing `absent/unallocated`; full chain required. |
| `P02` | DDM/S13/lifecycle fragments lack durable bridge. | Reuse-first H2 handoff. |
| `P03` | Control state could stay internal. | Atlas/public surfaces named; not implemented. |
| `P04` | E/X/V/C could become parallel status lattice. | Internal coordinates only; one Atlas projection. |
| `P05` / `P15` | Threshold/LLM/plan/projection could mint authority. | Actual authority evidence and consumer gate required. |
| `P07` / `P08` | Rule/version/time replay gaps. | Contract/version/time roles and append-only transitions. |
| `P09` | Warning/unresolved could lack owner, clock, closure. | Steward, escalation, after-hours, expiry, restart required. |
| `P10` / `P29` | Marker/constructor tests instead of response property. | Actual protected-action and remove-property probes. |
| `P11` | Only failures remembered. | Normal/expected and successful bounded restart fixtures retained. |
| `P12` | Meaning resolved after signal emission. | Contract/version/role bind before interpretation. |
| `P13` | GY could become an operational ERP. | Mechanical core routes to H2; external execution stays external. |
| `P14` | Correlated metrics/sensors inflate confidence. | Role separation and ancestry/shared-source checks. |
| `P24` | Target gaming becomes apparent success. | SMDV behavior/observation routing and gaming register. |
| `P25` | Exploratory anomaly drives control. | Candidate signal only; charter/authority required. |
| `P27` | New response runtime bypasses continuous governance/S13. | Canonical-owner map; compose, do not replace. |
| `P30` | Owner/provenance names overstate authority. | Authority act and evidence separate. |
| `P31` / `P40` | Per-threshold fixes create an endless ladder. | General transition charter and bucketed failure classes. |
| `P32` / `P33` | Declared fields or taught fixtures pass. | Malicious/adjacent/metamorphic/holdout variants. |
| `P35` / `W4-K01` | Indexed search could settle zero. | Census limitation `not_established`. |
| `P36` | Orientation prose could substitute for findings. | Evidence register separates repository facts/corrections. |
| `P37` / `P38` | Gate turns on threshold, owner string, success flag, or action name rather than property. | Predicate provenance and divergent cases; fail closed. |
| `P39` | Mechanism budget could count mandatory records. | No implementation path budget proposed in research. |
| `P41` | Inherited red ownership unknown. | No test-suite success claim; environmental limit stated. |

**Acceptance signal:** the package defines safe/unsafe implementation, research-only boundaries, falsifying fixtures, owner/integration map, real workflow, state machine, typed artifacts, fault injection, and capstone—without appointing authority or claiming implementation.
