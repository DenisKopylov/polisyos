# ADR-0151: Evidence Schema Compatibility And Legacy Quarantine

## Status

Accepted

## Date

2026-05-14

## Context

Production diagnostics showed that evidence can look pass-shaped while its
schema is unknown, stale, partial, renamed, migrated, or incompatible with the
reader that consumes it. This is especially dangerous for scorecard and
readiness because a report can preserve familiar top-level keys while dropping
authority fields such as producer identity, runtime refs, provenance, status,
tenant, time context, input refs, or blocker semantics.

Unknown schema is not a neutral condition in a production-quality evidence
chain. Without a producer-reader compatibility policy, implementation work will
recreate the same weakness under a different name: legacy reports, stale
bundles, and migration shims will keep passing because they are present.

## Decision

1. Every authority-bearing evidence artifact must declare producer schema name,
   producer schema version, producer component, reader contract, and authority
   role.
2. Every authority-consuming reader must declare accepted schema names,
   accepted version ranges, required semantic fields, migration policy, and
   fail-closed behavior.
3. Unknown schema, missing schema, unknown status semantics, stale schema,
   incompatible producer-reader version, or lossy adapter migration blocks
   serious closeout unless an accepted ADR and invariant registry entry permit a
   bounded exception.
4. Schema compatibility is semantic, not only structural. A migration that
   preserves keys but drops owner, provenance, status, input refs, tenant/cell,
   time context, lineage, blocker semantics, or authority role is incompatible.
5. Legacy evidence classes are explicit:
   - `legacy_supported`: old evidence with declared compatibility and bounded
     reader support;
   - `legacy_quarantined`: old evidence that can be inspected but cannot
     satisfy serious gates;
   - `legacy_rejected`: old evidence that must not be consumed because it is
     unsafe, unverifiable, or known misleading.
6. A bundle or runtime ref can be stale even when its content hash is valid.
   Freshness must be evaluated against legal snapshot, production-data
   manifest, model/provider mode, schema version, and invariant registry time.
7. Schema migration must produce migration evidence that records source schema,
   target schema, migration version, semantic losses, compatibility decision,
   input refs, output refs, and reviewer or automated validator identity.
8. Scorecard, readiness, approval, and public artifact publication must reject
   authority-bearing evidence when producer-reader compatibility is unknown.

## Consequences

Positive:

- Passing evidence can no longer rely on "looks like the old shape" behavior.
- Legacy bundles become inspectable without becoming production authority.
- Schema changes become safe to stage because reader compatibility is explicit.
- Adapter loss becomes a blocker rather than a hidden runtime convenience.

Negative:

- Existing historical evidence will need classification before it can be used
  in serious closeout.
- Migration code must record semantic losses instead of only transforming JSON.
- Readers must carry version and compatibility logic.

## Concrete impact

This ADR does not define an implementation plan. It requires future
implementation work to introduce or update:

- producer schema and reader contract fields on authority envelopes;
- schema compatibility registry entries;
- legacy evidence classification;
- migration evidence records;
- stale bundle and stale schema checks;
- scorecard/readiness gates for unknown, stale, or incompatible schemas;
- negative tests for unknown schema pass, partial schema pass, lossy adapter
  migration, stale bundle acceptance, and legacy evidence satisfying serious
  gates.

## Related Decisions

- Extends: ADR-0005 ABI Versioning Gate via JSON Schema Snapshots.
- Extends: ADR-0108 IR Schema Catalog and Reflection API.
- Extends: ADR-0114 Schema Registry and Evolution Rules.
- Extends: ADR-0123 ArtifactRef Governance Metadata.
- Related: ADR-0147 Production Evidence Authority Ordering.
- Related: ADR-0148 Serious Run State Machine And Phase Barriers.
- Related: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.

