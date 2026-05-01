# ADR-0129: Scientist Claim Ledger Boundary

## Status

Accepted

## Date

2026-04-28

## Context

Wave 1 added a typed claim/evidence/readiness spine under
`src/polisyos/scientist/claims/**`. Decision packets can now carry `claims_ref`
and render `claim_ledger_status = "legacy_missing"` for old packets that were
created before claim sidecars existed.

Wave 2 will add an append-only Claim Ledger lifecycle, but the repository needs
the operating contract before that implementation begins. Without a boundary
ADR, later phases could split claim state across governance reports, decision
packets, review queues and compiler exports in incompatible ways.

## Decision

`src/polisyos/scientist/claims/**` remains the canonical Scientist package for
claim identity, support status, publishability, evidence refs, counterevidence
refs, claim-ledger persistence, claim projection and claim publication
validators.

The Wave 1 `ClaimRecord` and `ClaimLedger` contracts remain readable. Wave 2
may add lifecycle, diff, export and audit artifacts, but those additions are
append-only. New packet fields must be sidecar refs such as
`claim_ledger_v2_ref`, `claim_ledger_diff_ref`, `claim_export_ref` or
`blocked_claim_summary_ref`; existing packet fields such as `claims_ref`,
`claim_ledger_status`, `policy_answer`, `simulation_results`, `governance` and
`artifacts` must not be removed or renamed in the Wave 2 rollout.

The Claim Ledger is the authority for decision-bearing claim lifecycle. It is
not the authority for source acquisition, benchmark approval, human-review
signatures or VOI scheduling; those surfaces remain in their dedicated packages
and link back to claims by claim id and `ArtifactRef`.

## Compatibility

- Old decision packets without `claims_ref` remain loadable and render
  `claim_ledger_status = "legacy_missing"`.
- Wave 2 claim artifacts must be additive sidecars. They may deprecate public
  fields only by documenting the replacement and dual-reading both shapes.
- Claim ids generated in Phase 1.1 remain valid identifiers for Wave 2
  lifecycle transitions.
- Hidden benchmark refs and private review notes must not be copied into public
  claim exports.

## Rollout

Phase 2.0 is documentation and gate only. Phase 2.1 may add append-only
lifecycle artifacts behind `scientist.best_in_class.wave2.phase2_1.claim_ledger_v2`.
The production default for new Wave 2 claim lifecycle behavior is off until a
later gate explicitly promotes it.

## Rollback

Disable the Wave 2 claim-ledger feature flag and continue producing the Wave 1
`claims_ref` sidecar. Old packets and Wave 1 claim ledgers continue to load
because the runtime keeps the additive `legacy_missing` rendering path.

## Consequences

- Claim lifecycle work has a single package boundary.
- Decision-packet compatibility can be checked mechanically.
- Later phases cannot make claim lifecycle state implicit in prose reports.
- Some duplicate fields may remain visible during dual-read migration.

## Concrete impact

- Phase 2.1 owns lifecycle events, audit, diff and export helpers under the
  existing claims package.
- Publication gates may require claim sidecars for selected workflows, but they
  must not break legacy packet rendering.
- Docs and CI gates must reject any proposed change that removes old public
  decision-packet fields during Wave 2.

## Related Decisions

- [ADR-0009: DecisionPacket Replay Protocol](0009-decision-packet-replay-protocol.md)
- [ADR-0058: Only additive schema changes](0058-compatibility-policy-additive-changes-only.md)
- [ADR-0100: Runtime API Versioning and Deprecation Policy](0100-runtime-api-versioning-and-deprecation-policy.md)
- [ADR-0123: ArtifactRef Governance Metadata](0123-artifact-ref-governance.md)
