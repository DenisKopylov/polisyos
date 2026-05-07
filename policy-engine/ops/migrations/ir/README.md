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
