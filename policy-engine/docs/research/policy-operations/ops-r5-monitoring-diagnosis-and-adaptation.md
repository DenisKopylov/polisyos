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
shared_vocabulary_location: int-r4-performative-effect-update-diagnosis.md#4-result
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

The same observed movement may invite an operational response and be offered to a learning system. The pair therefore cannot tolerate two diagnosis vocabularies. The sole candidate vocabulary is **SMDV-1**, derived and owned in [INT-R4 §4](int-r4-performative-effect-update-diagnosis.md#4-result). This document imports its classes, precedence, exhaustiveness boundary, and unresolved policy unchanged.

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

### 2.2 Existing fragments and the exact gap

DDM separates calibrated shift, realized/estimated degradation, data-quality failure, readiness, incidents, and root-cause localization (`policy-engine/src/polisyos/ddm/integration/events.py:1-232`). Realized monitors retain intervals and label-delay horizons (`policy-engine/src/polisyos/ddm/detectors/realized_performance_monitor.py:1-151`); data-quality checks retain schema/null/type/range/value/freshness violations (`data_quality_monitor.py:1-142`); FDR records alpha spending/discoveries (`calibration/multiple_testing.py:1-89`). Track-2.2's `0.25/0.70` cutoffs are local watch/investigate routing, not general policy thresholds (`track_2_2_shift_adapter.py:44-62`).

`ImplementationMonitoringEvaluationRecord` requires indicators, windows, cadence, thresholds, owners, estimand, comparison strategy, DDM evidence, claim links, and publication ordering (`policy-engine/src/polisyos/runtime/quality/ddm_monitoring.py:1-287`). Continuous governance types invalidation, calibration/fairness/context drift, and incidents and recommends monitor/stale/review/reissue/withdrawal review (`policy-engine/src/polisyos/scientist/governance/continuous/monitors.py:1-113`).

S13 has eight typed post-deployment attribution/accountability classes, but canonical fixtures supply the class rather than derive it (`policy-engine/src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py:43-58`, `:164-221`; `policy-engine/tests/fixtures/layer2/s13/s13_post_deploy_case_signals.json:4-204`). Thus the zone is not wholly greenfield; the exact joint evidence-derived movement diagnosis and authorized response chain remains absent.

GY-O2 keeps anomalies `candidate_unverified`; O1 requires cause typing; O3 requires confirmation and the observation-process negative; all are `build-new` (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:5043-5095`). Fabric supplies append-only correction/revocation/branches and generic quarantine, but neither decides cause nor appoints action authority (`policy-engine/docs/reference/fabric/time-travel.md:1-111`; `policy-engine/src/polisyos/fabric/data_plane/quarantine.py:1-106,220-463`).

No institutional signer is appointed for reissue, rollback, termination, or discretionary override. Repository owner/team strings are not appointments.

### 2.3 Baseline verdict and reuse-first path

The repository can detect, localize, retain, route, and preserve history. It cannot demonstrate:

```text
KPI contract + matured observation
→ trust/measurement checks
→ SMDV-1 diagnosis
→ typed permissible transition
→ competent authorization where required
→ append-only action/reissue/refusal record
→ separate restart gate and replay
```

Joint capability standing is `absent/unallocated`. The smallest path reuses DDM, `ddm_monitoring`, continuous governance, S13, Fabric, and Atlas. The durable Group-B control state belongs in the proposed H2 custody-runtime plan, not as a new subsystem appended to GY.

## 3. External Research Baseline

### 3.1 Source posture

OPS-R5 uses the same five `institutionally_supplied` surveys described in INT-R4 §3 and does not re-derive cause categories. S4 supplies metric-contract and gaming evidence; S3 detection/diagnosis/residue; S2 response/versioning/stopping/reversibility; S1 and S5 endogenous observation, censoring, latency, and interference.

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

### 3.3 Non-compensable roles, no universal ladder, and reversibility

S4 distinguishes objective/OEC, guardrail, diagnostic, and data-quality metrics. Benefit cannot buy safety or validity. Candidate roles here are `result`, `implementation`, `guardrail`, `leading`, `diagnostic`, `context`, and `measurement_health`; they may coexist but cannot be summed into one authority score.

Trials, aviation, nuclear operations, software delivery, circuit breakers, sandboxes, and sunset clauses control different risks. What transfers is precommitment: measure, review point, evidence, permissible action, authority, uncertainty behavior, restart, and irreversibility (S2:5-82, 84-137, 303-377). Response is therefore multi-axis. Protective action may precede diagnosis; learning and confirmatory claims may not.

Reversibility is at least:

```text
R_control   stop further exposure
R_state     restore prior system state
R_outcome   repair harm already caused
R_inference recover original information process
```

A boolean `reversible` is unsafe (S2:139-190).

### 3.4 Unknown, delayed harm, and exploratory status

“No signal = no harm” is unsupported. Gates need maturity, censoring, attrition, detection probability, and horizon evidence. Exited, rejected, never-entered, and neighboring populations require external channels or `unquantified`; aggregate benefit does not clear subgroup/spillover harm (S5:5-19, 21-131, 179-300).

Uncertainty may justify no-expansion, narrowing, or a preauthorized pause, but cannot close harm, validate a positive, authorize learning, or replace an absent signer.

Adaptive anomaly/subgroup discovery remains exploratory. Confirmatory claims require frozen estimand, outcome definition, version, population, horizon, and multiplicity plan followed by prospective evidence. Material intervention/eligibility/measurement/analysis change resets claim status unless a predeclared adaptive design covered it (S2:214-301; S5:179-203).

## 4. Result

### 4.1 Result type

**Result: `accepted_narrow_scope`.** OPS-R5 specifies a candidate `KPIControlContract` and governed response state machine, both consuming SMDV-1. They are research-only: no owner appointed, no threshold selected, no action authorized.

### 4.2 Candidate `KPIControlContract`

| Layer | Required content |
|---|---|
| Semantic | Contract/content identity; construct/claim; metric roles; definition/version; unit/basis; numerator/denominator/exclusions; aggregation/non-compensability; population/subgroup/spillover frames; baseline vintage; direction; target type/band. |
| Observation | Source/lineage; instrument; all time roles; cadence/lag/seasonality/maturity; censoring/attrition/missing channels; revision/correction/backcast/series break; uncertainty/detection capability; sentinel/negative-control/independent channels; gaming/endogenous-measurement exposure. |
| Decision | Trigger semantics; admissible evidence; identification threshold; waiting/premature-action loss; reversibility/blast radius; permitted actions; SMDV-1 requirement; claim/version consequence; restart evidence. |
| Authority/custody | Metric steward and definition-change rights; producer/integration boundary; decision/override authority; owner-unavailable/after-hours behavior; public meaning; append-only audit/supersession/replay; rule/schema/authority refs. |

Omissions are typed and scoped; absence never grants power.

### 4.3 Governed response coordinates

These internal coordinates project into the one Atlas lattice; they are not a competing status system:

```text
Epistemic:    E0 normal | E1 signal | E2 credible_anomaly |
              E3 diagnosed_mechanism | E4 confirmed_unacceptable
Exposure:     X0 full | X1 no_expansion | X2 narrowed | X3 paused | X4 terminated
Intervention: V0 unchanged | V1 recalibrated | V2 patched_or_reissued |
              V3 redesigned | V4 rolled_back
Claim:        C0 confirmatory_intact | C1 under_review |
              C2 exploratory_only | C3 withdrawn
```

### 4.4 Action families — absorbed OPS-R6

| Family | Actions | Minimum posture | Authority |
|---|---|---|---|
| `A0_observe` | retain, mature, collect denominator/follow-up | E0/immature | predeclared monitoring only |
| `A1_investigate` | validate, diagnose, acquire sentinel/implementation/context | E1 | case opening may be automatic; no substantive change |
| `A2_contain` | no expansion, degraded mode, cap, protective notice | E1/E2 + waiting-harm/guardrail | preauthorized or escalate |
| `A3_refresh` | correct/revise, bridge, recompute, recalibrate measurement | diagnosed observation/data issue | no policy-effect update |
| `A4_adjust` | repair implementation, narrow scope, partial reissue, version change | E3 + SMDV-1 + authority | competent decision required where policy changes |
| `A5_pause_or_rollback` | pause exposure, rollback future control, withdraw permission | E2/E3/E4 by risk/reversibility | preauthorized emergency or competent decision |
| `A6_terminate_or_redesign` | terminate, redesign, re-ratify, retire claim | E4 or unresolved past legal/safety clock | never from threshold alone |

`diagnosis_unresolved` may support investigation, containment, or a preauthorized pause under high waiting harm; never learning or unreviewed redesign.

### 4.5 Transition charter, restart, and learning

Every transition changing exposure/version/claim requires trigger, admissible evidence, maturity, measurement-validity test, SMDV-1 requirement, waiting/premature losses, reversibility, blast radius, VOI/next evidence, legal/governance clock, decision/override authority, restart, version consequence, claim consequence, and sealed audit record. A threshold without this is a P37/P38 proxy gate.

Restart is asymmetric: alert disappearance is not evidence. It requires identified repair/version, tests, measurement health, bounded probe, renewed authority, and historical-claim statement. A material change creates a new treatment identity unless predeclared pooling/equivalence evidence exists.

Only SMDV-1 `prediction_error`, with no blocking contributor and all INT-R4 §4.8 predicates, may enter effect-posterior proposal. Observation, delivery/version, behavior, and context route to their own lanes; unresolved freezes learning. Protective action may occur under lower causal certainty than learning.

### 4.6 No universal numbers and institutional limit

No domain-independent threshold, detection rate, horizon, false-signal rate, or reversibility value is established. DDM `0.25/0.70` remains local routing. Future numbers must name measure, population, horizon, assumptions, and authority source.

No signer is appointed for reissue, rollback, termination, or override. Research can name required authority; it cannot supply it.

## 5. Counterexamples And Failure Modes

### 5.1 Joint rider verdicts imported from INT-R4

| Rider | Correct | Complete | Operable at pin | OPS consequence |
|---|---|---|---|---|
| GY-O1 performativity | `yes_with_scope` | `no` | `no` | Threshold may open investigation/containment; only SMDV-1 `prediction_error` may enter discrepancy-driven learning. |
| GY-O3 self-confirmation | `yes` | `no` | `no` | Policy-generated observation cannot validate a world edge; permanent confirmation quarantine must survive generic reprocessing. |

The authoritative three-question audits are [INT-R4 §§5.1–5.2](int-r4-performative-effect-update-diagnosis.md#5-counterexamples-and-failure-modes).

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
| `FM-OPS-08` | Quiet short window proves no delayed harm. | Horizon/maturity/unquantified. |
| `FM-OPS-09` | Good average clears subgroup/spillover. | Separate guardrails. |
| `FM-OPS-10` | Rollback restores all dimensions. | Reversibility vector and residue. |
| `FM-OPS-11` | Alert disappearance is restart evidence. | Separate bounded probe and authority. |
| `FM-OPS-12` | Owner/team string appoints signer. | External appointment evidence. |
| `FM-OPS-13` | Duplicate irreversible transition may execute twice. | Content identity, dedupe, duplicate record. |
| `FM-OPS-14` | FDR anomaly confers cause/action authority. | Candidate only. |
| `FM-OPS-15` | `v+1` inherits `v` claim. | New version/claim status or predeclared pooling proof. |
| `FM-OPS-16` | Owner silence after hours means approval. | Declared degraded posture and escalation clock. |
| `FM-OPS-17` | OPS may define another cause vocabulary. | Import SMDV-1; fork blocks. |
| `FM-OPS-18` | Correction may overwrite original decision. | Append-only supersede/annotate/reissue. |

A serious safety signal may contain before diagnosis but cannot establish causation/learning. KPI improvement with degraded observation health remains uninterpretable. A repair altering eligibility/dose/rule creates a new version. Owner unavailability cannot manufacture authority.

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

Each packet carries contract/version; signals; maturity/uncertainty/censoring/health; SMDV-1 diagnosis or unresolved; E/X/V/C; charter; waiting/premature losses; reversibility/blast radius; authority or absence; expected/forbidden transitions; claim/version/history consequences; restart and replay.

### 6.2 Required negatives and fault injection

Required negatives include threshold without charter; FDR anomaly attempting world write; target edited after results; roles collapsed; blocked subgroup under good average; implementation failure routed to model refutation; unresolved high-harm containment with learning forbidden; unresolved low-harm investigation; owner unavailable; duplicate pause/rollback; late correction; rollback residue; restart without probe; `v+1` retaining `v`; silent rewrite; SMDV fork; authority by owner string; malicious denominator change under valid schema; exploratory subgroup alarm; and legal review clock under unresolved cause.

Fault injection repeats with provider unavailable; worker killed after partial writes; out-of-order amendments; concurrent irreversible requests; mass invalidation; conflicting evidence; absent signer; stale world consumer; branch/public projection divergence; and snapshot recovery/reconciliation.

### 6.3 Measures and acceptance proxy

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

The first twelve are separate guardrails. Prototype conformance requires zero authority/learning/write/restart/version/duplicate/rewrite escapes while preserving predeclared high-harm containment. Production latency/false-block thresholds are not set here.

## 7. Artifact Contract Sketch

### 7.1 Candidate artifacts

| Artifact | Minimum purpose | Boundary |
|---|---|---|
| `KPIControlContract` | Content ID; claim/construct; roles; definition/version; population/denominator/subgroups/spillover; baseline; observation protocol; uncertainty; gaming exposure; action charter; authority/override; time/rule/schema refs. | Governs interpretation/request; never appoints authority or proves cause. |
| `AdaptationTransitionRequest` | Contract/signal/diagnosis refs; current/requested E/X/V/C; action family; losses; reversibility/blast radius; clock; claim/version consequence; provenance. | Candidate only; cannot execute protected transition. |
| `AdaptationDecisionRecord` | Request; admitted evidence; signer/authority; allowed/denied/modified transition; reason/override; effective time; public meaning; idempotency; supersession. | Authoritative only for named transition when signer/input closure pass. |
| `RestartEvidenceRecord` | Prior decision; repair/version; tests; measurement health; bounded probe; residual harms; renewed authority; historical-claim status; expiry. | Reopening only; never inferred from signal disappearance. |
| `KPIControlStateSnapshot` | Contract version; E/X/V/C; open diagnosis/actions; clocks; owner availability; latest decision/restart/public refs. | Read model/projection; cannot mint authority. |

Signals remain existing DDM/monitoring/incident/revision artifacts. Governed identities are content/input-closure derived; retries dedupe; processing time does not define semantic identity.

### 7.2 State machine

```text
normal
→ signal_open
   → observation_invalid → refresh/correct
   → diagnosis_pending
      → unresolved_review → investigate / preauthorized contain / clock
      → diagnosed
         → transition_requested
            → awaiting_authority
               → denied
               → authorized
                  → executing
                     → partially_applied | applied | failed_safe
→ restart_pending
   → bounded_probe
      → remain_contained | restart_authorized → reopened
→ terminated_or_withdrawn
```

E/X/V/C travel through states but do not replace Atlas lifecycle status. Duplicate events append a duplicate disposition without repeating an irreversible action. Late evidence opens correction/supersession, not rewrite.

### 7.3 Time, predicate provenance, and owner map

Time roles: definition effective time; baseline vintage; observation/valid/transaction/detection time; maturity horizon; diagnosis/expiry; review/escalation/legal clock; decision/effective time; probe window; replay. Owner absence starts a declared clock/conservative posture, not approval.

Gate predicates—definition identity, denominator integrity, maturity/health, SMDV-1 diagnosis, losses, reversibility, signer competence, execution, restart—carry W4-K02 provenance labels. Only `recomputed` or `independently_reconciled` may support a protected positive.

| Function | Owner/disposition |
|---|---|
| DDM/FDR/quality | Existing `polisyos.ddm`; candidate evidence only. |
| Monitoring specification | Existing `ddm_monitoring`; extend/compose. |
| Validity/reissue/withdrawal recommendations | Continuous governance; reuse. |
| Movement diagnosis | INT-owned SMDV-1 candidate beside S13; producer absent. |
| Accountability component routing | S13; compose after diagnosis. |
| Durable state/clocks/idempotency/recovery | Proposed H2 custody runtime; currently `absent/unallocated`. |
| Learning/world consequences | GY O1/O3; do not own whole response runtime. |
| Persistence/history | CAS + Fabric. |
| Surface/status | Atlas + lifecycle projection; no authority minting. |
| Institutional signer | External; none appointed. |

## 8. Later Integration Handoff

### 8.1 Producer-to-surface chain

| Layer | Handoff |
|---|---|
| Producer | Existing DDM, quality, delayed-label, incident, revision, implementation, context, and external sensors. |
| Artifact | Existing signals plus candidate KPI contract, transition request/decision, restart, state snapshot. |
| Bridge | H2 state machine consumes admitted signals/diagnosis; GY consumes explicit learning/world consequences; continuous governance consumes validity/reissue/withdrawal. |
| Consumer | External executor applies policy/exposure change and emits execution evidence; PolicyOS changes only its own claim/custody state. |
| Verification | 24 diagnosis + 20 response cases, concurrency/idempotency, late/duplicate/contradictory events, protected-action consumer probes, recovery/replay. |
| Surface | Atlas operator/reviewer/machine/public views; one status lattice. |

### 8.2 Real operator workflow

1. Data/measurement producer emits versioned observation/health evidence; PolicyOS admits or quarantines.
2. Monitoring/on-call receives signal and opens a case; no cause implied.
3. Metric steward/diagnosis analyst checks definition, denominator, maturity, implementation, context/interference, behavior, and SMDV-1.
4. Implementation owner supplies delivery/version/exposure evidence and proposes repair.
5. Institutional authority approves/denies protected transition; PolicyOS verifies authority and records it.
6. External executor acts and emits execution evidence; PolicyOS does not substitute for execution.
7. Justification custodian updates PolicyOS claim/public state and schedules restart/review.

After hours, only explicitly preauthorized actions may execute—typically page, investigate, no-expansion, bounded degraded mode, or emergency pause. Owner absence selects the declared conservative state and escalation clock. Missing execution evidence leaves transition pending/failed-safe.

### 8.3 Engineering, institutional, absorbed-scope, and capstone handoff

Engineering blockers: contract storage; durable state/clocks; diagnosis bridge; idempotent records; execution-evidence intake; restart; replay/recovery; Atlas projection; fixtures.

Research/institutional blockers: domain thresholds/loss models; acceptable false-block trade-offs; SMDV disposition; maturity horizons; version pooling; oracle; operator studies; signer/override appointment.

All OPS-R6 action names are insufficient without authority, entry/exit evidence, restart, reversibility, version/claim consequences, and history.

OPS-R15 capstone must replay:

```text
published claim → signal → diagnosis/unresolved → transition request
→ authority decision → external execution evidence
→ claim revalidation/reissue/withdrawal → restart/terminal state
→ replay from original epoch
```

This handoff changes no policy, exposure, claim, posterior, world edge, owner, or authority.

## 9. Promotion And Kill Rules

### 9.1 Current and future promotion states

**Research-only now:** SMDV unregistered; corpus unexecuted; durable owner/bridge/consumer absent; no signer; operator/domain thresholds unknown; complete census not established.

**Prototype allowed:** one experimental SMDV ref; strict content-bound artifacts; reuse existing owners; no path to execution/protected claim/posterior/world/publication/approval; 24+20 fixtures plus concurrency/property-removal; owner absence/unresolved fail safely.

**Governed allowed:** vocabulary disposition; complete producer→H2→decision→execution-evidence→claim-reaction→surface chain; one status lattice; actual protected consumers fail closed; constructed version/maturity/subgroup/spillover/restart predicates; zero authority/learning/write/restart/version/duplicate/rewrite escapes; appointed signer or explicit preauthorization; historical replay/recovery.

**Production candidate:** named domain/population/metrics; measured operating characteristics and containment trade-offs; operator/after-hours studies; external execution integration; long-tail/no-channel harm; privacy/security/legal review; tabletop and rollback/recovery; ratified release authority.

### 9.2 Kill conditions

Kill/block if SMDV forks; threshold/FDR/owner string/completion flag authorizes action; roles become compensable; unresolved defaults to full expansion/learning/redesign; owner absence is approval; restart lacks independent evidence; `v+1` inherits `v`; duplicate irreversible action executes; correction rewrites history; O3 quarantine reaches world write; public projection mints authority; or protected transition lacks appointed signer. Gate remains `NO_GO`.

## 10. Open Questions For Consolidation

### 10.1 Questions

1. Which H2 artifact owns durable transition state, clocks, idempotency, and recovery?
2. How do E/X/V/C project into the existing Atlas lattice without adding statuses?
3. Which continuous-governance actions are reused directly and where is an authority delta required?
4. Which action families may be preauthorized, by whom, for which risk class?
5. Who is metric steward, transition signer, override signer, and after-hours substitute?
6. What domain-specific waiting/premature-action model selects containment intensity?
7. What maturity/delayed-harm horizons apply per KPI?
8. How are subgroup/spillover guardrails composed under multiplicity and unknown groups?
9. Which version changes require partial/full reissue, downgrade, or termination?
10. How is external execution evidence verified when late/contradictory?
11. How is permanent O3 quarantine protected from generic reprocessing?
12. Which Atlas/public surfaces communicate unresolved cause, protective action, and absent signer?
13. What OPS-R15 oracle adjudicates correct response and replay?

### 10.2 Classified findings and W4-K05 standing

The complete 18-row finding register is in [ops-r5/evidence-register.md](ops-r5/evidence-register.md); 0 findings are unclassified.

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

Research acceptance neither implements capability nor opens a gate.

## Operational Closure Addendum

### 1. Boundary census

| Function | Verdict | Owner mapping |
|---|---|---|
| KPI meaning/version/decision linkage and PolicyOS claim reaction | OWN | Existing partial owners; missing H2 bridge. |
| Data collection, sensor operation, policy execution | INTEGRATE | External producer/executor. |
| Institutional succession/authority status | OBSERVE/INTEGRATE evidence | External institution. |
| Administrative casework/notices/payments/enforcement | OUT_OF_SCOPE except typed evidence | External systems. |
| DDM/FDR | OWN existing diagnostic substrate | `polisyos.ddm`. |
| Durable response state/clocks/idempotency | OWN mechanical core | Proposed H2; absent. |
| Protected transition decision | INTEGRATE authority act | No appointed signer. |

### 2. Real operator workflow

Specified in §8.2, including normal, failed, owner-unavailable, and after-hours paths.

### 3. State machine

Specified in §7.2 with clocks/public meaning in §7.3, duplicate handling, terminal/reopen behavior, and one-lattice projection.

### 4. Typed artifacts

Specified in §7.1 with authority boundaries, versions/time, content identities, transition/restart semantics, and owner map.

### 5. Edge-case fixtures

Specified in §6: happy path; missing/late/duplicate/conflicting evidence; owner unavailable; malicious denominator; degraded mode; partial execution; rollback residue; version transition; replay; subgroup/spillover; O3 quarantine; vocabulary fork.

### 6. Tabletop / fault injection

Provider failure, killed worker, duplicate amendment, concurrent irreversible request, mass invalidation, conflicting evidence, absent signer, stale consumer, projection/head divergence, and snapshot recovery/reconciliation. Success means no duplicate protected action, no false completion, preserved history, conservative degraded state, and reconciliation or explicit terminal failure.

### 7. Capstone linkage

OPS-R15 must test the complete cycle in §8.3; stopping at detector or request does not close OPS-R5/OPS-R6.

## Pattern Pass

| Pattern | Risk | Result/routing |
|---|---|---|
| `P01` | Contracts called capability. | `absent/unallocated`; full chain required. |
| `P02` | Fragments without durable bridge. | Reuse-first H2 handoff. |
| `P03` | Internal-only control state. | Atlas/public handoff. |
| `P04` | Parallel status lattice. | E/X/V/C internal; one Atlas projection. |
| `P05` / `P15` | Threshold/LLM/plan/projection mints authority. | Actual authority evidence/consumer gate. |
| `P07` / `P08` | Version/time replay gap. | Separate roles and append-only transitions. |
| `P09` | Warning/unresolved lacks owner/clock. | Steward/escalation/after-hours/expiry/restart. |
| `P10` / `P29` | Markers substitute for response property. | Actual protected consumer/property-removal probes. |
| `P11` | Failure-only memory. | Normal and successful bounded-restart fixtures. |
| `P12` | Meaning resolved after emission. | Contract/version/role bind first. |
| `P13` | GY becomes operational ERP. | H2 mechanical core; external execution. |
| `P14` | Correlated metrics inflate confidence. | Role separation and shared-source checks. |
| `P24` | Target gaming becomes success. | SMDV behavior/observation routing. |
| `P25` | Exploratory anomaly drives control. | Candidate only; charter/authority. |
| `P27` | New runtime bypasses continuous governance/S13. | Compose canonical owners. |
| `P30` | Owner/provenance names overstate authority. | Separate authority act/evidence. |
| `P31` / `P40` | Per-threshold patch ladder. | General charter and bucketed failure classes. |
| `P32` / `P33` | Declared fields/taught fixtures pass. | Malicious/adjacent/holdout variants. |
| `P35` / `W4-K01` | Index settles zero. | Census `not_established`. |
| `P36` | Orientation prose substitutes for finding. | Evidence register separates facts/corrections. |
| `P37` / `P38` | Gate uses threshold/owner/success proxy. | Predicate provenance and divergent cases. |
| `P39` | Mandatory records counted as mechanism budget. | No implementation budget proposed here. |
| `P41` | Inherited red ownership unknown. | No test-suite success claim; environmental limit explicit. |

**Acceptance signal:** the package defines safe/unsafe implementation, research-only boundaries, falsifying fixtures, owner/integration map, real workflow, state machine, artifacts, fault injection, and capstone—without appointing authority or claiming implementation.
