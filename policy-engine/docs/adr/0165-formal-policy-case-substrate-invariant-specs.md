# ADR-0165: Formal Policy Case And Substrate Invariant Specs

## Status

Accepted

## Date

2026-05-18

## Context

ADR-0155 created a production invariant registry and ownership contract for the
honest diagnostics substrate. The Policy Design Case SDD adds a stricter need:
some policy-case and substrate invariants are too important to rely on unit
tests and prose alone.

Wave 26 accepts this decision before later governance and lifecycle work
narrows implementation contracts. Formal or model-checked specifications should
not be a decorative artifact after code exists; they should identify the
authority properties that code, trace checks, and runtime gates must preserve.

The first useful target is a lightweight formal invariant spec registry under
`architecture/policy_design_case/`. It can reference TLA+/PlusCal, Alloy,
state-machine specs, property-based tests, static checks, or runtime trace
conformance, as long as each row names the invariant, owner, authority source,
and required evidence.

## Decision

1. Policy Design Case formal invariant coverage is an architecture contract,
   not an optional test-improvement backlog.
2. The canonical registry for Policy Design Case formal invariant specs is
   `architecture/policy_design_case/formal_invariant_specs.toml`.
3. Each invariant spec row names an id, owner, source ADR, informal statement,
   protected authority property, implementation scope, accepted check type,
   minimum evidence artifact, revisit trigger, and retirement or supersession
   rule.
4. The first invariant families cover production evidence authority ordering,
   phase barriers, same-input closure, CAS/event reconciliation, schema and
   effective-mode compatibility, projection-not-authority, no parallel Policy
   Design Case authority, append-only lifecycle transitions, terminal
   readiness, publication authority, and proportionality waiver boundaries.
5. Unit tests alone are not sufficient evidence for substrate-critical
   invariants unless the registry explicitly classifies the invariant as
   local and non-authority-bearing.
6. Runtime trace conformance may satisfy an invariant only when the trace
   includes CAS/event/schema/mode refs and the checker can fail closed on
   missing or contradictory evidence.
7. Formal specs do not replace runtime evidence. They constrain the allowed
   behavior of runtime records, scorecard/readiness gates, public projections,
   lifecycle transitions, and publication authority.
8. Adding, weakening, retiring, or changing the authority meaning of a
   substrate-critical or Policy Design Case-critical invariant requires ADR
   authority or an accepted supersession recorded in this registry.
9. Scorecard, readiness, or docs lifecycle checks must expose missing required
   formal invariant coverage before final governed or production closeout.

## Consequences

Positive:

- Implementation teams get explicit authority properties before code paths
  make them hard to change.
- Model checks, property checks, static checks, and runtime trace checks can be
  compared through one registry instead of scattered test comments.
- Later governance work has a clear way to prove it did not weaken substrate
  or Policy Design Case invariants.
- External reviewers can see which high-risk behaviors are formally specified
  and which remain accepted deficits.

Negative:

- Some invariants require tooling that is slower than ordinary unit tests.
- The registry needs ownership discipline so it does not become a stale list of
  aspirations.
- Teams must separate local implementation checks from authority-bearing
  invariants that need ADR-level change control.

## Concrete impact

This ADR requires future implementation work to introduce or update:

- `architecture/policy_design_case/formal_invariant_specs.toml`;
- a formal invariant validation tool and repo-quality test;
- invariant rows for authority ordering, phase barriers, CAS/event
  reconciliation, terminal readiness, projection boundaries, lifecycle
  monotonicity, publication authority, and proportionality waiver boundaries;
- links from invariant rows to ADRs 0147-0165 and owning runtime records;
- scorecard/readiness or lifecycle checks that report missing required
  invariant evidence;
- ADR or supersession workflow for weakening, retiring, or changing
  authority-critical invariants.

## Related Decisions

- Extends: ADR-0147 Production Evidence Authority Ordering.
- Extends: ADR-0148 Serious Run State Machine And Phase Barriers.
- Extends: ADR-0149 Effective Mode And Fallback Degradation Ledger.
- Extends: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
- Extends: ADR-0151 Evidence Schema Compatibility And Legacy Quarantine.
- Extends: ADR-0152 Semantic Binding, Lineage, And Claim Evidence.
- Extends: ADR-0153 Diagnostic SLOs, Assurance Case, And Attestation.
- Extends: ADR-0154 Diagnostic Event Envelope And Runtime Log Contract.
- Extends: ADR-0155 Production Invariant Registry And Ownership Contract.
- Extends: ADR-0156 Policy Design Case Runtime Quality Assurance Profile.
- Related: ADR-0162 Human Oversight, Publication, And External Audit Authority.
- Related: ADR-0163 Lifecycle, DDM, Ex-Post Outcomes, And Calibration.
- Related: ADR-0164 Run Cost, Proportionality, And Evidence Budget Governance.
