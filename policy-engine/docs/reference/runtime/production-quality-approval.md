# Production Quality Approval

Related runbook: [Production quality canary](../../runbooks/production-quality-canary.md).
Related triage: [Production quality triage](../../runbooks/production-quality-triage.md).
Related references: [Runtime quality scorecard](quality-scorecard.md),
[Human review calibration](human-review-calibration.md),
[Deterministic replay](deterministic-replay.md), and
[Privacy compliance evidence](privacy-compliance-evidence.md).

Owner: `@runtime-owners` and `@platform-owners`
Source of truth: `src/polisyos/runtime/quality/approval.py`,
`src/polisyos/core/contracts/control.py`,
`src/polisyos/runtime/http/routes/runs.py`, and
`src/polisyos/runtime/http/services/control/run_lifecycle.py`.

Production quality approval converts one persisted runtime quality scorecard
into an immutable approval packet. The packet records whether the run can be
approved, blocked, or approved with an explicit reviewer override.

## Public Contract

The runtime endpoint is:

```text
POST /api/v1/runs/{run_id}/production-approval
```

The request body is `ProductionApprovalRequest`:

| Field | Required | Meaning |
| --- | --- | --- |
| `quality_scorecard_ref` | conditional | Persisted scorecard artifact ref. Preferred for production review. |
| `quality_scorecard` | conditional | Inline scorecard overlay. It must still point at a persisted scorecard ref. |
| `override` | no | Reviewer-attributed exceptional override request. |

If neither a persisted scorecard ref nor persisted control progress is
available, the endpoint fails with `quality_scorecard_required`. If an inline
scorecard is not backed by a persisted ref, it fails with
`quality_scorecard_not_persisted`.

The response is `ProductionApprovalResponse`:

| Field | Meaning |
| --- | --- |
| `run_id` | Reviewed run id. |
| `decision` | `approved`, `approved_with_override`, or `blocked`. |
| `packet` | Full `policyos.production_approval_packet.v1` payload. |
| `approval_packet_ref` | CAS ref for the immutable approval packet. |
| `evidence_bundle_packet_path` | Bundle-local packet path when the scorecard names a bundle. |

## Packet Fields

`ProductionApprovalPacket` contains:

| Field | Meaning |
| --- | --- |
| `generated_at` | UTC packet creation time. |
| `run_id` and `job_id` | Runtime/control-plane identifiers copied from the scorecard. |
| `canary_kind` | `dev`, `research`, `governed`, `production`, or `staging`. |
| `decision` | Final approval decision. |
| `eligibility` | Machine-readable reason projection. |
| `scorecard_ref` | Persisted scorecard ref when present. |
| `scorecard_digest` | Canonical digest of the reviewed scorecard. |
| `scorecard_generated_at` | Source scorecard timestamp. |
| `evidence_refs` | Sanitized refs copied from the scorecard plus ownership refs. |
| `override` | Persisted override packet when accepted. |

The packet is additive. It does not rewrite the scorecard, erase failures, or
remove the need to preserve the canary evidence bundle.

## Eligibility Logic

The approval builder computes these booleans from the scorecard:

| Eligibility field | Source |
| --- | --- |
| `execution_completed` | `execution_status == completed` |
| `quality_passed` | `quality_status` is `pass`, `passed`, `ok`, or `success` |
| `blocking_failure_count` | Count of `blocking_quality_failures` |
| `performance_blocking` | `performance_status` is missing, warn, fail, timeout, over budget, or degraded |
| `conflict_blocking` | conflict gate/status is fail, blocked, incompatible, or error |

The packet is eligible only when all blockers are absent. Otherwise
`eligibility.reasons` explains the block:

| Reason | Operator action |
| --- | --- |
| `execution_not_completed` | Inspect the control job state and failure envelope before quality review. |
| `quality_not_passing` | Open `quality_gates` and the named assurance report refs. |
| `blocking_quality_failures` | Use each failure `layer`, `phase`, `evidence_ref`, and `next_action`. |
| `performance_budget_blocking` | Review resilience/performance evidence and decide whether an override is valid. |
| `conflict_blocking` | Review Lex/norm conflict evidence before any public approval. |

## Decisions

| Decision | Meaning |
| --- | --- |
| `approved` | The scorecard is eligible without an override. |
| `approved_with_override` | The scorecard is not eligible, but an override packet passed guardrails. |
| `blocked` | The scorecard is not eligible and no valid override applies. |

Approval consumers should require both:

- `decision` is `approved` or `approved_with_override`;
- `packet.eligibility.reasons` is understood and linked to evidence when an
  override exists.

## Override Requirements

`ProductionApprovalOverrideRequest` requires:

| Field | Requirement |
| --- | --- |
| `reviewer_identity` | Stable reviewer attribution. |
| `reason` | Specific rationale for accepting the exception. |
| `scope` | Exact `run:<run_id>` or `job:<job_id>` scope. |
| `expires_at` | Future UTC expiry. |
| `evidence_refs` | At least one non-empty evidence ref. |
| `signature` | Optional caller-supplied signature; otherwise a deterministic packet signature is derived. |
| `metadata` | Optional sanitized metadata. |

Override guardrails can add these blocking reasons:

| Reason | Meaning |
| --- | --- |
| `override_reviewer_attribution_missing` | Reviewer identity is absent or unusable. |
| `override_packet_incomplete` | Required override fields or evidence refs are incomplete. |
| `override_expired` | Expiry is not in the future at packet generation time. |
| `override_scope_mismatch` | Override scope does not match the reviewed run or job. |
| `override_rationale_weak` | Rationale is too weak for an exceptional production decision. |

Overrides are for exceptional review only. They are not a way to silence
missing scorecards, missing persisted refs, security failures, privacy failures,
or public-export leaks.

## Runtime Progress Projection

After a packet is persisted, `RunLifecycleService.record_production_approval_packet`
projects these fields into latest control progress:

| Progress field | Meaning |
| --- | --- |
| `approval_packet_ref` | Persisted packet artifact id. |
| `approval_decision` | Packet decision. |
| `approval_ready` | True for `approved` or `approved_with_override`. |
| `approval_state` | `approval_ready` or `approval_blocked`. |
| `quality_scorecard.approval_packet` | Sanitized packet payload for operator display. |
| `quality_scorecard.approval_eligibility` | Eligibility payload copied from the packet. |
| `quality_scorecard.approval_reasons` | Eligibility reason list. |

The dashboard should display the ref and decision, but should not expose raw
reviewer-private notes, credentials, raw request bodies, or hidden benchmark
material.

## Reissue Semantics

Reissue is a replacement workflow for a decision that became stale, invalid, or
review-required after publication or approval. The runtime control endpoint is:

```text
POST /api/v1/control/runs/{run_id}/reissue
```

The response includes:

| Field | Meaning |
| --- | --- |
| `monitoring_report_ref` | Monitoring evidence that triggered review. |
| `compare_report_ref` | Old/new comparison evidence. |
| `reissue_plan_ref` | Human-gated reissue plan. |
| `reissued_run_id` | Replacement run id queued for durable execution. |

The original scorecard and approval packet remain part of the audit trail. The
new run must produce its own evidence bundle, scorecard, replay refs, and
approval packet.

## Withdrawal Semantics

Withdrawal is an explicit continuous-governance action, not deletion and not a
retry. The sidecar kind is `scientist.withdrawal_record`.

Required withdrawal evidence:

| Field | Requirement |
| --- | --- |
| `decision_packet_ref` | Original decision artifact. |
| `actor_id` | Accountable actor. |
| `reason` | Human-readable withdrawal reason. |
| `audit_event_ref` | Audit trail event. |
| `monitor_event_refs` or `human_review_ref` | At least one lineage path proving why withdrawal was required. |

Public exports may surface the withdrawn status and action posture, but must
redact internal monitor ids, private reviewer notes, hidden benchmark refs, and
raw sensitive data.

## Assurance Refs Expected In Review

Serious profiles should make these refs easy to locate before approval:

| Evidence | Scorecard or bundle ref |
| --- | --- |
| Quality scorecard | `quality_evidence/quality_scorecard.json` |
| Golden scenario contract | `quality_evidence/golden_scenario_contract.json` |
| Normative applicability | `quality_evidence/normative_evidence.json` |
| Fabric retrieval trace | `quality_evidence/fabric_retrieval_trace.json` |
| Foundry method report | `quality_evidence/foundry_method_report.json` |
| Policy grounding matrix | `quality_evidence/policy_grounding_matrix.json` |
| Conflict check | `quality_evidence/conflict_check.json` |
| Production data quality | `production_data_quality_report_ref` |
| Causal/statistical validity | `causal_statistical_validity_report_ref` |
| Security assurance | `security_assurance_report_ref` |
| Privacy compliance | `privacy_compliance_report_ref` |
| Replay manifest | `replay_manifest_ref` |
| Drift explanation | `drift_explanation_ref` |
| Resilience matrix | `resilience_report_ref` |
| Human review calibration | `human_review_calibration_report_ref` |
| Provider/model drift ledger | `provider_model_quality_ledger_ref` |
| Decision artifact quality | `decision_artifact_quality_report_ref` |

If a serious-profile approval cannot locate these refs or an explicit
not-applicable reason, it should block and route to the owning layer.

## Security And Privacy Rules

- Approval packets contain refs and summaries, not raw report payloads.
- Override metadata must be sanitized before persistence.
- Reviewer-private notes stay out of public exports and dashboard fixtures.
- API keys, bearer tokens, passwords, raw prompts, raw transcripts, hidden
  answers, and raw sensitive records must never appear in packet JSON.
- Query-string secrets in refs must be stripped before display.

## Minimal Review Checklist

1. Confirm the bundle and scorecard paths are immutable.
2. Confirm `execution_status`, `quality_status`, `performance_status`, and
   `approval_state`.
3. Confirm every blocking failure has `layer`, `phase`, `evidence_ref`, and
   `next_action`.
4. Confirm assurance refs are present or explicitly not applicable.
5. Confirm replay drift is either absent or accepted with typed source and
   bounded impact.
6. Confirm security/privacy/public-export reports pass.
7. Confirm override packets, if any, are scoped, expiring, reviewer-attributed,
   and evidence-backed.
8. Persist the approval packet and link its ref from the release or review
   record.
