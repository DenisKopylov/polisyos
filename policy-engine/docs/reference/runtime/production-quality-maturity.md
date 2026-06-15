# Production Quality Maturity

Owner: `@runtime-owners`
Source of truth: `tools/ci/check_policyos_production_quality_best_in_class.py`,
`tools/ops_runners/runtime/run_canary_matrix.py`,
`tools/ops_runners/runtime/canary_evidence.py`,
`src/polisyos/runtime/quality/scorecard.py`, and archived acceptance reports.

This page defines how PolicyOS evaluates production-quality maturity after the
best-in-class remediation work. Maturity is evidence-based: a system advances
only when the corresponding evidence bundle, scorecard, assurance reports, and
approval packet behavior can be reproduced.

## Levels

| Level | Name | Requirement |
| --- | --- | --- |
| L0 | Unproven | No deterministic matrix, readiness JSON, or assurance bundle exists. |
| L1 | Deterministic evidence | CI-safe simulated lanes run without live LLM calls, emit sanitized bundles, and include scorecard, replay, resilience, and assurance files. |
| L2 | Serious-profile gate | Research, governed, or production profiles fail closed on missing runtime-owned refs, fixture-like production data, compliance gaps, security gaps, replay drift, or approval gaps. |
| L3 | Quarantined live evidence | At least one live-provider lane with production data is run under quarantine and either passes or fails with a clear non-code provider/data reason and sanitized bundle. |
| L4 | Continuous acceptance | Deterministic burn-in, live canaries, provider drift ledgers, reviewer calibration, resilience/soak evidence, and residual-risk reviews run on a fixed cadence. |

## Current Maturity Snapshot

Snapshot date: 2026-05-13.

| Area | Current level | Evidence |
| --- | --- | --- |
| Readiness aggregation | L2 | `_build/.tmp/production-quality/phase6_3/readiness_aggregator.json` reports `passes_all: false`, `passes_required: false`, 7 failed findings, and one attached live-provider bundle. The aggregate gate is now strict and blocks closeout on unresolved serious-profile refs. |
| Deterministic canary matrix | L3 | Three Phase 6.3 deterministic matrix runs passed with scorecard `warn` and no blocking failures. |
| Production data quality | L2 | Dev fixture data is warning-only for CI burn-in; serious profiles still fail closed until non-fixture production diagnostics pass. |
| Causal/statistical validity | L3 | Causal validity report passes known-answer, placebo, negative-control, missingness-stress, and uncertainty-calibration coverage. |
| Security assurance | L3 | Security assurance report is emitted in deterministic bundles and passes runtime abuse-surface checks. |
| Privacy/compliance | L3 | Privacy compliance report is emitted and passes the deterministic burn-in bundle. |
| Replay and drift explanation | L3 | Replay manifest is emitted and drift explanation reports `match` with no differences. |
| Resilience | L2 | Deterministic resilience matrix exists and fail-closes unsafe stress scenarios; successful production soak/load proof is still a follow-up. |
| Human review | L2 | Calibration report is emitted, but Phase 6.3 burn-in has no real reviewer events. |
| Provider/model drift | L1 | Live-provider preflight and failure bundle exist, but provider quality ledger could not be generated because no model variant completed. |
| Decision artifact quality | L3 | Decision artifact quality report is emitted and passes required-section checks for the deterministic bundle. |
| Approval packets | L2 | Packet samples are generated and correctly block warning/failure lanes; no approval-ready production packet was produced in Phase 6.3. |

## Evidence Required By Domain

| Domain | Required evidence | Promotion condition |
| --- | --- | --- |
| Data quality | `quality_evidence/production_data_quality.json` plus materialization refs | Serious-profile report status `pass`, non-fixture bundle versions, row coverage, data dictionary, recency, leakage, unit, label, and construct-validity diagnostics. |
| Causal validity | `quality_evidence/causal_statistical_validity.json` | Known-answer, placebo, negative-control, power/sample, sensitivity, and uncertainty checks pass. |
| Security | `quality_evidence/security_assurance_report.json` | Prompt/tool/data/provider/artifact abuse gates pass or fail closed with sanitized details. |
| Privacy | `quality_evidence/privacy_compliance_report.json` | PII, licensing, retention, jurisdiction, and public-export checks pass before approval. |
| Replay | `quality_evidence/replay_manifest.json` and `quality_evidence/drift_explanation.json` | Replay is comparable or every difference has typed accepted drift. |
| Resilience | `quality_evidence/resilience_matrix.json` or `_build/.tmp/production-quality/*/resilience_matrix.json` | Load, soak, retry storm, brownout, CAS pressure, queue saturation, run-index, and dashboard degradation scenarios are recorded and unsafe paths fail closed. |
| Human review | `quality_evidence/human_review_calibration_report.json` | Reviewer agreement, override correctness, reviewer burden, and escalation metrics have nonzero denominators for serious approvals. |
| Provider drift | `quality_evidence/provider_model_quality_ledger.json` or a generated provider ledger | Schema failure, grounding failure, disagreement, latency, cost, quality, and default-model freshness are tracked per provider/model. |
| Decision artifact | `quality_evidence/decision_artifact_quality.json` | Final artifacts include uncertainty, tradeoffs, distributional impacts, feasibility, budget, stakeholder impacts, implementation risk, and residual uncertainty. |
| Approval | `production_approval_packet.json` or persisted CAS approval packet | Packet decision is `approved` or `approved_with_override`; blocked packets must expose reasons and evidence refs. |

## Operating Cadence

| Cadence | Gate |
| --- | --- |
| Every PR touching runtime quality, canary evidence, scorecards, or contracts | Deterministic matrix and runtime API contract check. |
| Nightly | Deterministic matrix burn-in, readiness aggregator JSON, docs gate, local integration smoke, and dashboard smoke journey. |
| Weekly | At least one quarantined live-provider canary with production data and sanitized bundle. |
| Biweekly | Residual-risk review for provider drift, human review calibration, serious-profile production data, and resilience/soak coverage. |
| Monthly | Scenario pack authority review, hidden/rotating contamination guard review, and maturity level reassessment. |

## Residual-Risk Policy

Acceptance reports must list every non-L4 area with:

- risk statement;
- owning team;
- next review date;
- evidence path or trigger;
- whether the risk blocks production approval.

Phase 6.3 known residuals are archived in
`docs/archive/reports/POLICYOS_PRODUCTION_QUALITY_BEST_IN_CLASS_ACCEPTANCE.md`.
