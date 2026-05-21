# ADR-0157: Policy Intent Envelope, Capability Ledger, And Authority Profile Mapping

## Status

Accepted

## Date

2026-05-16

## Context

Pass 1A diagnostics found that policy meaning is currently carried through
request text, nested params, router behavior, and component-local assumptions.
That makes it possible for Lex, Fabric, Scholar, Foundry, Scientist, and the
claim compiler to interpret the same request differently.

The same diagnostics found that capability selection is not ledgered. A run can
skip legal retrieval, academic evidence retrieval, source selection, method
selection, or final claim compilation without a durable serious-run duty record.

The repository already has execution and governance profile machinery in
`src/polisyos/core/contracts/control.py`, `src/polisyos/core/governance`, and
`src/polisyos/runtime/quality/effective_mode.py`. Policy-domain authority
levels must map to those surfaces instead of inventing a parallel profile
system.

## Decision

1. Every serious policy run must materialize a canonical policy intent envelope
   before domain routing.
2. The intent envelope records policy problem, desired outcome, proposed
   intervention, requester-preferred conclusion when present, separation
   between requester preference and independent analysis, target population,
   jurisdiction, policy time, data time, affected stakeholders, constraints,
   objectives, assumptions, requested authority level, evidence expectations,
   tenant, authoring provenance, and requester-capture risk.
3. Every serious policy run must materialize a capability selection ledger
   before or during routing.
4. The capability ledger records required, selected, skipped, blocked, and
   fallback duties for Lex, Fabric, Scholar, Foundry, Scientist, compiler,
   publication, review, and external audit surfaces.
5. A skipped duty requires either an allowed-profile fallback/degradation
   record or a typed blocker. Silent skips cannot satisfy serious closeout.
6. Research, governed, and production policy authority levels must map to
   existing execution profiles, core governance validation profiles, and
   runtime effective-mode checks.
7. A second authority-profile taxonomy is prohibited unless a later ADR records
   why the existing profile surfaces cannot express the needed policy states.
8. Scorecard and readiness gates must fail when the intent envelope,
   capability ledger, or profile/effective-mode closure is missing,
   contradictory, stale, or cross-run.

## Consequences

Positive:

- Policy meaning becomes a runtime-owned input to all producers.
- Requester-capture risk can be separated from independent analysis before any
  producer executes.
- Missing Lex, Fabric, Scholar, Foundry, Scientist, or compiler duties become
  visible blockers instead of hidden absence.
- Policy-domain modes reuse existing runtime governance machinery.

Negative:

- Vague requests will block or require clarification earlier.
- Existing convenience routes that bypass capability ledgers lose serious-run
  authority.
- Profile mapping requires careful migration so old dev/research fixtures do
  not look governed or production-ready.

## Concrete impact

This ADR requires future implementation work to introduce or update:

- policy intent envelope schema and runtime materialization;
- requester-capture fields and challenge-depth policy;
- capability selection ledger schema;
- Scholar duty entries in routing and scorecard surfaces;
- mapping between policy authority levels, execution profiles, core governance
  profiles, and runtime effective mode;
- scorecard/readiness checks for missing intent, missing duty, disallowed skip,
  fallback leakage, and profile mismatch;
- tests for cross-run, stale, and contradictory intent/capability evidence.

## Related Decisions

- Extends: ADR-0149 Effective Mode And Fallback Degradation Ledger.
- Extends: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
- Extends: ADR-0152 Semantic Binding, Lineage, And Claim Evidence.
- Related: ADR-0129 Scientist Claim Ledger.
- Related: ADR-0131 Scientist Readiness Ladder.
- Related: ADR-0156 Policy Design Case Runtime Quality Assurance Profile.
- Related: ADR-0158 Concept Spine And Multi-Jurisdiction Reconciliation.
