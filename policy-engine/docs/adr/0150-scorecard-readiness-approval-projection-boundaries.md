# ADR-0150: Scorecard, Readiness, Approval, And Projection Boundaries

## Status

Accepted

## Date

2026-05-14

## Context

Production diagnostics showed that scorecard, readiness, approval, dashboard,
and canary-bundle surfaces can blur into each other. A bundle can create a
pass-like scorecard after runtime failure. A dashboard can project
approval-like readiness. Approval can consume inline or projected values rather
than persisted scorecard identity. Public artifacts can look final before the
runtime evidence chain closes.

These are boundary failures, not UI copy issues. The system needs accepted
architecture rules for which surfaces produce authority, which read authority,
which project authority, and which must fail closed.

## Decision

1. The scorecard is a reader and enforcer over declared evidence. It does not
   produce authority.
2. Scorecard gates must verify required evidence existence, required CAS refs,
   payload identity, producer and owner identity, provenance kind,
   fallback/degradation allowance, schema compatibility, phase-barrier order,
   semantic binding to final claims, redaction-preserved diagnostic semantics,
   and negative-control behavior.
3. The readiness aggregator is the final closeout authority over the evidence
   contract. It consumes persisted scorecard identity and the authority graph.
4. Readiness must fail closed when required authority is missing, mismatched,
   projected, stale, cross-run, cross-tenant, disallowed by provenance, or
   blocked by non-overridable policy.
5. Approval consumes persisted readiness and scorecard identity. It must not
   consume inline scorecard objects, dashboard projections, bundle-local
   summaries, or unverified control progress as approval truth.
6. Overrides may accept residual policy risk, but they cannot turn missing
   authority into authority.
7. Non-overridable serious blockers include missing runtime authority for
   required evidence, disallowed fallback-produced evidence, fixture-only
   production evidence, simulated evidence in a live-required lane,
   cross-tenant ownership conflicts, missing legal conflict blocker, public
   artifact compiled before required barriers, secret/hidden-answer/unsafe
   rendering/path-traversal exposure, and unverifiable scorecard ref identity.
8. Dashboard and readiness UI surfaces are projections. They must label source
   surface, authority level, first blocking cause, upstream owner, and next
   diagnostic command.
9. Public decision artifacts may publish only after readiness has closed with
   publishable authority. Otherwise they remain draft or `published_blocked`
   with typed cause.
10. Forbidden serious-profile interpretations include: missing status means
    pass; `present` means pass; completed run means missing workflow report
    passed; optional runtime ref means non-blocking without registry permission;
    bundle-local path means runtime ref; fixture overlay means runtime
    evidence; simulated provider preflight means live provider readiness;
    dashboard projection means approval packet truth; data presence means data
    relevance; model output means grounded claim; no-norm retrieval means no
    applicable law; no-data result means no data is required.

## Consequences

Positive:

- Approval, readiness, and dashboard states become explainable rather than
  merely reassuring.
- Public artifacts cannot claim production authority before the evidence chain
  closes.
- Operators can see the difference between approved, projected
  approval-ready, blocked with override possible, and non-overridable authority
  gap.
- Scorecard failures become root-causeable through authority identity, not only
  report status.

Negative:

- Existing dashboards and canary bundles may lose convenient pass-like states.
- Approval workflows must persist and verify scorecard/readiness identity.
- Some reports that previously counted as evidence will become diagnostic-only
  until their refs and provenance are verified.

## Concrete impact

This ADR does not define an implementation plan. It requires future
implementation work to introduce or update:

- scorecard identity verification;
- readiness authority graph checks;
- approval packet identity checks;
- dashboard projection labels;
- public artifact publishability checks;
- non-overridable blocker registry;
- negative tests for projected approval, inline scorecard approval,
  bundle-local refs, missing status pass, report presence pass, no-norm pass,
  and premature public artifact publication.

## Related Decisions

- Extends: ADR-0007 Human Gate Protocol in IR.
- Extends: ADR-0099 Runtime Lifecycle and Dependency-Injection Container.
- Extends: ADR-0100 Runtime API Versioning and Deprecation Policy.
- Extends: ADR-0101 Runtime Audit Trail Model.
- Extends: ADR-043 Provenance Law Through QuantityValue.
- Extends: ADR-044 Time as a UI Primitive.
- Related: ADR-0147 Production Evidence Authority Ordering.
- Related: ADR-0148 Serious Run State Machine And Phase Barriers.
- Related: ADR-0149 Effective Mode And Fallback Degradation Ledger.
