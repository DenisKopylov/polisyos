---
title: Human Review Calibration
status: active
owner: team-governance
last_verified: 2026-05-13
stability: active
related:
  - ../../plans/active/POLICYOS_BEST_IN_CLASS_PRODUCTION_QUALITY_REMEDIATION_PLAN.md
  - ../../../src/polisyos/runtime/quality/human_review.py
  - ../../../src/polisyos/runtime/quality/approval.py
---

# Human Review Calibration

Human-review calibration is the runtime-owned evidence layer for production
approval, override, escalation, reissue, and withdrawal review flows. It emits
`human_review_calibration_report_ref` so approval packets and dashboard
surfaces can prove that reviewer behavior was measured without requiring live
reviewers in deterministic CI.

## Runtime Contract

Use `build_human_review_calibration_report(...)` from
`polisyos.runtime.quality.human_review` with reviewer-attributed review events.
The report schema version is
`policyos.human_review_calibration_report.v1`.

Required event fields:

- `flow`: `approval`, `override`, `escalation`, `reissue`, or `withdrawal`.
- `outcome`: `approve`, `reject`, `escalate`, `override`, `reissue`, or
  `withdraw`.
- `reviewer_identity`: stable reviewer attribution for accountable decisions.
- `decision_ref` or `packet_ref`: evidence link for the reviewed decision.
- `burden_minutes`: reviewer effort used for burden and capacity monitoring.

Recommended event fields:

- `expected_outcome` or `agreement`: used to calculate reviewer agreement.
- `disagreement_reason_code`: typed reason for disagreement analysis.
- `override_correct`: correctness label for accepted overrides.
- `escalation_threshold`: threshold or rule that triggered escalation.
- `unresolved`: marks disagreements still blocking approval readiness.

Private reviewer notes can be present in source fixtures, but the runtime report
only publishes aggregate privacy metadata. Public exports are built with
`human_review_public_export(...)` and strip private-note fields recursively.

## Quality Signals

The report status is `pass`, `warn`, or `fail` based on these deterministic
signals:

- low reviewer agreement;
- high override rate;
- low override correctness;
- unresolved disagreement count;
- reviewer burden above configured thresholds.

`fail` signals are blocking quality evidence for serious production approval.
Approval failures can only move to `approved_with_override` when the override
packet is reviewer-attributed, scoped to the reviewed run or job, expiring,
signed, evidence-backed, and has a strong rationale.

## Approval Packet Integration

`build_production_approval_packet(...)` accepts
`human_review_calibration_report_ref`. The ref is copied into
`packet.evidence_refs["human_review_calibration_report"]`.

When a non-eligible scorecard is submitted with an override request, the
approval builder evaluates the resulting override packet with
`evaluate_review_packet(...)`. Failed checks add deterministic eligibility
reasons such as:

- `override_reviewer_attribution_missing`;
- `override_packet_incomplete`;
- `override_expired`;
- `override_scope_mismatch`;
- `override_rationale_weak`.

This prevents blocking quality failures from being silently overridden by a weak
or unscoped packet.

## CI Fixtures

`deterministic_review_fixtures(...)` returns six stable events covering:

- approve;
- reject;
- escalate;
- override;
- reissue;
- withdraw.

These fixtures allow unit tests and dashboard journeys to exercise calibration
behavior without live human reviewers.

## Dashboard Surface

The runtime dashboard reads `progress.quality_scorecard.human_review_calibration`
and shows:

- human-review status;
- reviewer agreement;
- override rate;
- reviewer burden;
- unresolved disagreement count;
- sanitized `human_review_calibration_report_ref`.

The dashboard renders aggregate public fields only. It intentionally ignores
`private_notes` and strips query-string secrets from displayed refs.
