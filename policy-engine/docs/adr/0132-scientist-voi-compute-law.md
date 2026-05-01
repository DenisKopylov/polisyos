# ADR-0132: Scientist VOI Compute Law

## Status

Accepted

## Date

2026-04-28

## Context

Scientist already has VOI-related and learning-loop primitives in search,
failure cards, lessons, autotune and agent packages. Wave 2 will make VOI a
first-class scheduler for additional research, compute, review and reissue
actions. That scheduler needs a compute law before code expands: what VOI may
choose, what it may not override, and how it records cost, uncertainty and
regret.

## Decision

VOI scheduling belongs to `src/polisyos/scientist/search/voi_scheduler.py` and
adjacent Scientist search/compute helpers. VOI reports must be explicit
artifacts, with future packet refs such as `voi_report_ref`,
`source_voi_ref`, `human_review_voi_ref` and `compute_budget_decision_ref`.

VOI is a prioritization and budget signal. It cannot override benchmark
authority, human-review requirements, safety gates, claim publishability blocks
or hidden-eval leakage controls. VOI may recommend additional source fetches,
reruns, challenge packs, human escalation or no-op decisions, but every
recommendation must record expected value, expected cost, uncertainty and the
reason an action was chosen or skipped.

## Compatibility

- Existing search/autotune workflows keep their current behavior until an
  explicit Wave 2 flag enables VOI scheduling.
- Decision packets may gain VOI refs only as additive sidecars.
- Old packets without VOI refs remain loadable and are rendered as
  `legacy_missing` or `not_applicable` depending on the consumer.
- VOI report schema versions must not regress below their documented baseline.

## Rollout

Phase 2.0 freezes the law. Phase 2.3 may add scheduler reports behind
`scientist.best_in_class.wave2.phase2_3.voi_scheduler`. The initial production
default is off; staging can run in shadow mode to measure calibration, regret
and budget impact.

## Rollback

Disable the VOI scheduler flag and keep existing search/autotune routing.
Persisted VOI sidecars remain optional explanatory artifacts and are ignored by
legacy packet consumers.

## Consequences

- VOI has a single runtime vocabulary before it becomes a control plane.
- Future learning loops cannot silently spend budget or escalate reviewers
  without a reportable expected-value rationale.
- VOI remains subordinate to benchmark, human-review and safety gates.

## Concrete impact

- Phase 2.3 owns candidate/source/human-escalation VOI reports.
- Phase 2.4 and Phase 2.5 may feed lessons and challenge outcomes into VOI, but
  contamination controls remain mandatory.
- Phase 2.6 reissue logic may use VOI to prioritize reissue work, but cannot use
  VOI to suppress required incident or withdrawal handling.

## Related Decisions

- [ADR-0058: Only additive schema changes](0058-compatibility-policy-additive-changes-only.md)
- [ADR-0100: Runtime API Versioning and Deprecation Policy](0100-runtime-api-versioning-and-deprecation-policy.md)
- [ADR-0123: ArtifactRef Governance Metadata](0123-artifact-ref-governance.md)
- [ADR-0131: Scientist Readiness Ladder Boundary](0131-scientist-readiness-ladder.md)
