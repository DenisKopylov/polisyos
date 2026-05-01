# ADR-0131: Scientist Readiness Ladder Boundary

## Status

Accepted

## Date

2026-04-28

## Context

Scientist now has several readiness-like concepts: public decision readiness in
`src/polisyos/scientist/search/readiness.py`, claim support/publishability in
`src/polisyos/scientist/claims/**`, benchmark authority verdicts in
`src/polisyos/scientist/evals/**`, agent promotion reports and human-review
statuses.

Wave 2 needs these signals to agree without replacing the existing public
readiness ladder used by promoted policy artifacts.

## Decision

`src/polisyos/scientist/search/readiness.py` remains the source of truth for
public `DecisionReadiness` levels and `DecisionReadinessContract`. Claim
support status, claim publishability, benchmark authority, human review and
agent promotion are supporting gates; they do not rename, remove or fork the
public readiness ladder.

Wave 2 may add transition evidence and readiness explanations as additive refs,
for example `readiness_transition_ref`, `benchmark_authority_ref`,
`human_review_packet_ref` and `claim_ledger_v2_ref`. Any readiness advancement
for selected public/high-risk workflows must be explainable through claim
projection, evidence, benchmark authority and human-review status when those
gates apply.

## Compatibility

- Existing `DecisionReadiness` values remain valid and readable.
- Old decision packets without Wave 2 transition refs remain loadable.
- A packet cannot claim a stronger readiness by deleting old fields or by
  replacing existing readiness levels with a new enum.
- `human_reviewed` posture cannot be claimed without a review ref when the
  human-review gate requires one.

## Rollout

Phase 2.0 freezes the vocabulary. Later phases may add richer transition
records behind Wave 2 feature flags, but production defaults remain off until
the relevant phase gate and Wave 2 closeout gate pass.

## Rollback

Disable Wave 2 transition refs and continue using the current
`DecisionReadinessContract` plus the Wave 1 claim/research/human-review sidecar
status fields. Legacy packets continue to render `legacy_missing` where sidecar
refs are absent.

## Consequences

- Existing promotion and policy artifact consumers keep one public readiness
  vocabulary.
- Supporting gates can grow independently without fragmenting readiness names.
- Some readiness explanations may be duplicated during the dual-read period.

## Concrete impact

- Phase 2.0 gates must reject schema regressions for public readiness artifacts.
- Phase 2.7 compiler output must project readiness from the shared ladder, not a
  compiler-local enum.
- Frontier and agent default-enable gates must not bypass benchmark authority or
  human-review controls by emitting a readiness label directly.

## Related Decisions

- [ADR-0058: Only additive schema changes](0058-compatibility-policy-additive-changes-only.md)
- [ADR-0100: Runtime API Versioning and Deprecation Policy](0100-runtime-api-versioning-and-deprecation-policy.md)
- [ADR-0123: ArtifactRef Governance Metadata](0123-artifact-ref-governance.md)
- [ADR-0129: Scientist Claim Ledger Boundary](0129-scientist-claim-ledger.md)
