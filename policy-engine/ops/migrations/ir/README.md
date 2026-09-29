# IR Schema Migrations

Owner: `team-ir`

This directory owns operator guidance for canonical Policy IR, Trinity bundle,
IR snapshot, and persisted IR artifact migrations. Implementation code remains
in `src/polisyos/ir/migrations/**`; this directory is the operational contract
that release promotion reads.

## Covered Surfaces

- `src/polisyos/ir/migrations/**`
- `schemas/snapshots/ir/**`
- `docs/reference/ir/schema-catalog.md`
- persisted IR artifacts referenced by runtime, Foundry, or Scientist flows

## Operator Checks

- Migrations must be deterministic and version stamped with `schema_version`.
- Major version transitions require explicit owner approval and compatibility
  fixture evidence.
- Legacy non-Trinity payloads must fail closed unless a reviewed migration
  contract explicitly reintroduces them.
- Runtime and data-plane consumers must either read N-1 payloads directly or
  invoke a declared migration helper before promotion.

## Release Gate

`ops/release/promotion-gates.toml#ir_migration_review` blocks IR schema
promotion unless the migration helper, schema catalog, compatibility fixtures,
and runbook evidence are all present.

## Scientist Frontier Artifact v3 (B111)

This migration-class guidance also covers the persisted Scientist policy-design
artifacts `polisyos.scientist.policy_design.PolicyFrontierReport` and
`polisyos.scientist.policy_design.RejectedAlternativesSummary`. The Scientist
artifact owner defines their payload semantics; the `ir_migration_review`
class gate governs persisted-schema compatibility evidence. This section does
not cover or claim closure of `ParetoRegistrySnapshot` serialization.

The default ordinary new-producer path emits schema `3.0`. Payloads explicitly
versioned as `1.0` or `2.0` remain persistable through their historical
serializers for replay. Each v3 Pareto projection carries
`eligible_candidate_hashes`, the complete identity denominator used to bind
assessment status to omitted candidates. The shared projection contract checks
the denominator count and status-specific omission identities before either
persisted artifact can be accepted. Artifact kinds and reference types are
unchanged.

Updated readers accept v1, v2, and v3, preserving historical bytes through
version-specific projections; v2 replay is bounded because v2 never stored the
complete eligible identity denominator. Do not infer or backfill identities
that are absent from historical bytes, and do not rewrite, restamp, or reissue
those records. A strict reader from before this change rejects the v3
schema/field and cannot safely consume newly written artifacts.

### Rollout sequence

1. Upgrade every consumer that reads either artifact kind to a reader that
   accepts v1, v2, and v3. Keep existing v1/v2 records unchanged.
2. Verify the public loaders, report and summary consumers, and hierarchy
   producer against the compatibility fixtures and semantic tests listed in
   `release-fragments/unreleased/2026-09-29-e02-r2-b111-frontier-v3.toml`.
3. The B111 code slice adds no separate writer-disable switch. Do not assume
   readers can be upgraded independently while the v3 writer stays active.
   Before deploying this writer build, either stage a reader-only compatible
   release or coordinate the rollout so no artifact is written until every
   consumer can read v3. If neither sequence can be established, hold release.
4. Record the `ir_migration_review` evidence and owner approval before
   production promotion. This documentation and a passing focused test run do
   not by themselves constitute promotion approval.

### Rollback and recovery

- Before any v3 artifact is written, hold the rollout and keep the previous
  writer active while remaining readers are upgraded.
- Once v3 bytes exist, do not downgrade a consumer to a strict v1/v2-only
  reader. There is no safe downgrade claim for that reader. Keep a
  v1/v2/v3-capable reader available; if that cannot be maintained, stop the
  affected consumers and hold promotion until a compatible reader is restored.
- If the v3 writer itself must be stopped, keep readers capable of replaying
  already-written v3 artifacts and repair the writer or consumer path forward.
  Do not delete, rewrite, restamp, or reissue v3 or historical records as a
  rollback substitute.

This B111 slice remains partial. The persisted non-finite registry snapshot,
source-bound objective basis, and fully served registry path remain separate
residuals; no authoritative complete-frontier claim follows from this schema
change.
