# ADR-0147: Production Evidence Authority Ordering

## Status

Accepted

## Date

2026-05-14

## Context

Production-quality diagnostics found that PolicyOS can hold many useful
validators while still failing to prove which evidence is authoritative. A
runtime can fail, a canary bundle can later synthesize or normalize reports, and
a scorecard can see pass-shaped files without proving runtime ownership, CAS
identity, same-input closure, or provenance.

Plans and backlog entries are not strong enough for this boundary. The
authority order must be an accepted architecture decision because downstream
Lex, Fabric, Foundry, Scientist, scorecard, readiness, approval, dashboard, and
public artifact work all depend on the same definition of truth.

## Decision

1. Production authority flows in this order:
   runtime producer event, runtime CAS artifact, runtime ref envelope, scorecard
   verification, readiness closeout, approval or public artifact, dashboard or
   readiness projection.
2. Lower-authority surfaces may reference higher-authority surfaces, but they
   must not override, upgrade, or synthesize them.
3. Every authority-bearing artifact requires an evidence authority envelope
   with artifact ref, artifact kind, authority role, provenance kind, producer,
   producer version, owner, run id, job id, tenant id, cell id, requested and
   effective profile, input refs, schema name/version, generated time, as-of
   time, governance classification, fallback/degradation refs, validation
   status, and blocking status.
4. Evidence classes are authoritative architecture vocabulary:
   `authority_bearing`, `diagnostic_supporting`, `debug_only`,
   `public_exported`, `redacted_derived`, and `legacy_quarantined`.
5. Serious gates may consume only `authority_bearing` evidence, explicitly
   permitted `runtime_blocker` evidence, or a narrower registry-scoped
   exception. Debug, diagnostic-supporting, public, redacted, and legacy
   artifacts cannot satisfy gates by shape alone.
6. Provenance vocabulary is fail-closed in serious profiles. Unknown,
   missing, disallowed, contradictory, fixture-only, bundle-synthesized,
   simulated, stale, or owner-conflicted provenance blocks production closeout
   unless an accepted ADR and invariant registry entry permit a bounded
   exception.
7. Serious gates require same-input closure across policy intent, run id, job
   id, tenant/cell, time context, production-data manifest, legal snapshot,
   method plan, model/provider mode, fallback ledger, and evidence refs.
8. Runtime event logs and CAS artifacts must reconcile before evidence becomes
   authority:
   - event exists and CAS is missing: block with `authority_cas_missing`;
   - CAS exists and event is missing: quarantine as orphan artifact;
   - envelope exists and payload hash mismatches: block with
     `authority_payload_mismatch`;
   - required CAS ref points to bundle-local path: block with
     `authority_ref_not_cas`;
   - duplicate event with same id and same payload hash: idempotent duplicate;
   - duplicate event with same id and different payload hash: block with
     `authority_event_collision`;
   - unexplained replay drift: block with
     `authority_replay_drift_unexplained`;
   - tenant/cell conflict: block with `authority_tenant_conflict`.
9. Scorecards, readiness aggregators, approval packets, dashboards, and public
   artifacts are consumers of authority. They are not producers of authority.

## Consequences

Positive:

- Evidence can no longer become production-authoritative merely because a JSON
  file exists or reports `pass`.
- Canary bundles become packaging surfaces instead of authority-upgrade
  surfaces.
- Runtime fixes in Lex, Fabric, Foundry, and Scientist become measurable only
  when their evidence reaches the authoritative reader chain.
- Cross-run, cross-tenant, stale, fixture, and bundle-local evidence failures
  receive typed blocker semantics.

Negative:

- Existing reports that lack envelopes become legacy/quarantined until migrated
  or explicitly exempted.
- Serious profiles will initially fail more often.
- Writers and readers must carry more metadata and verify payload identity.
- Some convenience fixtures and bundle assemblers must lose authority.

## Concrete impact

This ADR does not define an implementation plan. It requires future
implementation work to introduce or update:

- evidence authority envelope schemas;
- evidence class vocabulary;
- provenance vocabulary and registry policy;
- CAS/event reconciliation checks;
- scorecard ref-identity checks;
- readiness closeout checks that reject missing or mismatched authority;
- negative tests for bundle upgrade, fixture theater, stale refs, cross-run
  refs, cross-tenant refs, missing CAS, orphan CAS, payload mismatch, and
  replay drift.

## Related Decisions

- Extends: ADR-0010 CAS Artifact Signing.
- Extends: ADR-0098 CAS Abstraction Boundary for Runtime Services.
- Extends: ADR-0101 Runtime Audit Trail Model.
- Extends: ADR-0104 IR Canonical JSON and CAS Hash Policy.
- Extends: ADR-0123 ArtifactRef Governance Metadata.
- Extends: ADR-043 Provenance Law Through QuantityValue.
- Related: ADR-0148 Serious Run State Machine And Phase Barriers.
- Related: ADR-0149 Effective Mode And Fallback Degradation Ledger.
- Related: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
