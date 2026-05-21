# ADR-0155: Production Invariant Registry And Ownership Contract

## Status

Accepted

## Date

2026-05-14

## Context

The honest diagnostics substrate depends on production invariants being known,
owned, enforceable, and explainable. Diagnostics found that some Minimum
Closeout Gate and PQL items can be treated as satisfied by code presence, test
presence, bundle files, or static inventory declarations without proving the
runtime event, CAS artifact, scorecard reader, readiness check, and final owner
that close the invariant.

If the invariant registry is left as an implementation detail, each subsystem
will define its own owner, gate name, override policy, projection rule, and
failure code. That recreates the same ambiguity that the substrate is meant to
remove.

## Decision

1. PolicyOS has a production invariant registry. It is the canonical authority
   map for Minimum Closeout Gate and PQL invariants.
2. Every serious closeout invariant must have exactly one final owner. It may
   have multiple producer owners, but only one owner is accountable for final
   enforcement semantics.
3. Every invariant registry entry declares:
   `invariant_id`, `minimum_closeout_gate`, `pql_id`, `final_owner`,
   `producer_owners`, `runtime_event_names`, `required_artifact_kinds`,
   `required_ref_keys`, `evidence_classes`, `allowed_provenance_kinds`,
   `required_schema_contracts`, `scorecard_gate_names`, `readiness_check`,
   `approval_policy`, `override_policy`, `non_overridable_blockers`,
   `dashboard_projection_policy`, `public_artifact_policy`, `conflict_policy`,
   `failure_code`, `diagnostic_owner`, `dependencies`, `consumers`, and
   `next_diagnostic_command`.
4. Readiness closeout must fail when an invariant that applies to the active
   profile lacks final owner, enforcement function, required refs/artifacts,
   allowed provenance, schema contract, override policy, projection policy,
   conflict policy, or failure code.
5. Static inventory can describe expected producers and consumers, but serious
   closeout depends on runtime-emitted evidence matching the registry.
6. Registry entries must distinguish enforcement role from observation role. A
   dashboard, report bundle, canary packaging step, or static inventory may
   observe or project an invariant but cannot be its final authority unless the
   registry explicitly says so.
7. Invariant conflicts fail closed. When two components disagree about status,
   owner, ref identity, provenance, schema, mode, or phase order, the registry's
   conflict policy chooses the authoritative source or produces a typed
   conflict blocker.
8. Overrides are registry-scoped. An override may accept residual policy risk
   only when the registry marks the blocker overridable for the active profile.
   Missing authority, unverifiable scorecard identity, cross-tenant conflict,
   and disallowed provenance are non-overridable unless a later ADR supersedes
   this rule.
9. Every invariant must name a diagnostic owner and next diagnostic command so
   operators can move from failure to root-cause investigation without reading
   unrelated code.

## Consequences

Positive:

- Minimum Closeout Gate and PQL coverage becomes an enforceable ownership map,
  not prose spread across plans, tests, and canary files.
- Scorecard, readiness, approval, dashboard, and public artifact semantics can
  share the same invariant definitions.
- Missing owner, missing enforcement, and contradictory subsystem authority
  become closeout blockers.
- Future domain fixes can be validated against the same registry rather than
  adding one-off pass criteria.

Negative:

- The registry becomes critical architecture and must be reviewed like code.
- Some currently passing checks will fail because they have no final owner or
  runtime evidence contract.
- Registry evolution needs migration discipline to avoid breaking historical
  evidence unexpectedly.

## Concrete impact

This ADR does not define an implementation plan. It requires future
implementation work to introduce or update:

- production invariant registry schema;
- registry storage location and review workflow;
- scorecard/readiness consumers of registry entries;
- static inventory alignment with registry semantics;
- override and projection policy fields;
- failure-code taxonomy tied to invariant ids;
- owner and next-diagnostic-command checks;
- negative tests for invariant without owner, invariant without enforcement,
  static-only proof, bundle-only proof, unknown override policy, projection-only
  approval, and conflicting subsystem authority.

## Related Decisions

- Extends: ADR-0147 Production Evidence Authority Ordering.
- Extends: ADR-0148 Serious Run State Machine And Phase Barriers.
- Extends: ADR-0149 Effective Mode And Fallback Degradation Ledger.
- Extends: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
- Extends: ADR-0151 Evidence Schema Compatibility And Legacy Quarantine.
- Related: ADR-0152 Semantic Binding, Lineage, And Claim Evidence.
- Related: ADR-0153 Diagnostic SLOs, Assurance Case, And Attestation.
- Related: ADR-0154 Diagnostic Event Envelope And Runtime Log Contract.

