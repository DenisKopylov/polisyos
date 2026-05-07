# Scientist Continuous Governance

Related references: [Scientist](index.md), [Claim Ledger](claim-ledger.md), [Research DAG replay](research-dag-replay.md), [Human oversight](human-oversight.md), [Wave 2 runtime contracts](wave2-runtime-contracts.md).

Owner: `@scientist-owners`  
Backup owner: `@platform-owners`  
Source of truth: `src/polisyos/scientist/governance/continuous/**`, `src/polisyos/scientist/methods/research_dag/invalidation.py`, `src/polisyos/scientist/evidence/claims/lifecycle.py`, `src/polisyos/scientist/governance/report.py`, `src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py`, `tests/unit/scientist/governance/continuous/**`, `tools/ci/check_scientist_best_in_class_phase2_6.py`, and `tests/repo_quality/tools/test_scientist_best_in_class_phase2_6.py`.

Continuous governance is the Phase 2.6 control plane for living decision
artifacts. A decision packet can remain valid, enter monitoring, become stale,
require review, be reissued, or be withdrawn. The layer is additive: old
decision packets still load, and new validity state is carried in CAS-persisted
sidecars and governance links.

## Runtime Contracts

| Contract | Module | Role |
| --- | --- | --- |
| `DecisionValidityStatus` | `governance.continuous.monitors` | Public lifecycle status: `valid`, `monitoring`, `stale`, `review_required`, `reissued`, `withdrawn`. |
| `GovernanceMonitorEvent` | `governance.continuous.monitors` | Typed source invalidation, calibration drift, fairness drift, policy-context drift or incident signal. |
| `GovernanceMonitorRecommendation` | `governance.continuous.monitors` | Deterministic action recommendation: continue monitoring, mark stale, human review, reissue or withdrawal review. |
| `ContinuousInvalidationResult` | `governance.continuous.invalidation` | Bridge result tying Research DAG invalidation to Claim Ledger lifecycle events and monitor recommendations. |
| `ReissuePacket` | `governance.continuous.reissue` | Old/new decision-packet and Claim Ledger linkage for review-required or reissued artifacts. |
| `IncidentReport` and `WithdrawalRecord` | `governance.continuous.incident` | Incident posture and explicit audited withdrawal action. |
| `DecisionValidityReport` | `governance.continuous.reports` | Internal validity report plus public redaction export. |

`persist_validity_report`, `persist_reissue_packet`,
`persist_incident_report` and `persist_withdrawal_record` write these sidecars
with typed schema metadata and CAS lineage inputs.

## Status Semantics

| Status | Meaning | Required evidence |
| --- | --- | --- |
| `valid` | No active monitor event requires action. | No open warnings or blockers. |
| `monitoring` | Watch signal exists, but no review/reissue action is required. | Informational `GovernanceMonitorEvent`. |
| `stale` | A dependency changed and dependent claims were marked stale. | Source invalidation with claim or DAG lineage and Claim Ledger lifecycle event. |
| `review_required` | Reviewer triage is required before public posture changes. | Drift/blocker event plus `GovernanceMonitorRecommendation`. |
| `reissued` | A replacement decision packet and Claim Ledger are linked. | `ReissuePacket` with original and new decision/ledger refs. |
| `withdrawn` | Public artifact is explicitly withdrawn. | `WithdrawalRecord` with actor, reason, audit event and monitor/review lineage. |

Continuous governance cannot directly withdraw an artifact from a monitor event.
Withdrawal is always an explicit governance action with an actor, reason and
audit event.

## Source Invalidation Bridge

Phase 2.2 owns Research DAG source invalidation. Phase 2.6 consumes its
`SourceInvalidationImpact`:

1. `propagate_source_invalidation(...)` identifies affected DAG nodes and claim ids.
2. `mark_dependent_claims_stale(...)` appends `MARKED_STALE` or `INVALIDATED`
   `ClaimLifecycleEvent` records to the append-only Claim Ledger.
3. `governance_event_from_source_invalidation(...)` creates a
   `GovernanceMonitorEvent` with affected claim and DAG lineage.
4. `recommend_validity_action(...)` returns `mark_stale` for stale sources and
   `reissue` for withdrawn or contradicted sources.

An invalidation with no affected claim or DAG lineage fails validation. This
prevents source freshness noise from silently passing as a meaningful decision
validity update.

## Drift And Incident Policy

Calibration drift, fairness drift and policy-context drift are advisory until
the monitor severity requires action:

| Event type | Warning | Block |
| --- | --- | --- |
| `calibration_drift` | `human_review` | `reissue` |
| `fairness_drift` | `human_review` | `reissue` |
| `policy_context_drift` | `human_review` | `reissue` |
| `incident` | `human_review` | `withdrawal_review` |

Thresholds are domain-specific and not standardized in this phase. The Phase
2.6 contract only records the event, severity, affected claim ids, reason and
recommendation.

## Reissue And Withdrawal

`ReissuePacket` is the reviewer-visible bridge between the old and new artifact:

- `original_decision_packet_ref` and `original_claim_ledger_ref` are required;
- `new_decision_packet_ref` and `new_claim_ledger_ref` are required when status
  is `reissued`;
- non-valid statuses require `monitor_event_refs`;
- withdrawn reissue packets require human-review lineage.

`WithdrawalRecord` is stricter: it requires `actor_id`, `reason`,
`audit_event_ref`, and monitor or human-review lineage. Public exports only
surface the status and action posture; hidden benchmark refs and internal
monitor refs are removed.

## Decision Packet And Governance Links

Decision packets remain backward compatible. When sidecars exist,
`build_decision_packet` projects:

- `continuous_governance_report_ref`;
- `reissue_packet_ref`;
- `withdrawal_record_ref`;
- `continuous_governance.status`;
- event and recommendation counts;
- affected claim ids;
- recommended actions.

`GovernanceReportLinks` also carries
`continuous_governance_report_ref`, `reissue_packet_ref` and
`withdrawal_record_ref` so governance reports can reference the same validity
loop without owning reissue semantics.

## Feature Flags

```text
scientist.best_in_class.wave2.phase2_6.continuous_governance
scientist.best_in_class.wave2.phase2_6.enable_reissue_workflow
scientist.best_in_class.wave2.phase2_6.enable_withdrawal_status
```

Default rollout is shadow/off. Validity reports may be emitted as sidecars, but
review/reissue/withdrawal effects remain governance controlled until the Wave 2
closeout gate accepts them.

## Public Redaction

`export_public_validity_report(...)` omits internal refs and rejects hidden or
internal ref tokens. Public reports must not expose hidden benchmark answers,
hidden holdout refs, private eval ids or internal monitor identifiers.

## Validation

```bash
uv run pytest tests/unit/scientist/governance/continuous -q
uv run python tools/ci/check_scientist_best_in_class_phase2_6.py --repo-root . --output-format json --require-passing
uv run pytest tests/unit/scientist/evidence/claims tests/unit/scientist/methods/research_dag tests/unit/scientist/governance/human_review -q
uv run pytest tests/unit/scientist/governance -q
```
