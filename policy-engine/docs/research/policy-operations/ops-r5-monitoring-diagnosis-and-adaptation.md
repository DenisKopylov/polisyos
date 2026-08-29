---
title: OPS-R5 — Monitoring Diagnosis And Governed Adaptation
status: in_progress — repository baseline recorded
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

## 4. Result

## 5. Counterexamples And Failure Modes

## 6. Benchmark Or Fixture Proposal

## 7. Artifact Contract Sketch

## 8. Later Integration Handoff

## 9. Promotion And Kill Rules

## 10. Open Questions For Consolidation
