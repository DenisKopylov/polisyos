# Common Migrations (`polisyos.common.migrations`)

`polisyos.common.migrations` owns the local migration registry for artifacts whose schema is managed
by `polisyos.common`.

## Role in System

- **Depends on:** the local migration registry and artifact-specific migration handlers.
- **Used by:** bootstrap and migration tooling that needs to rewrite common-owned artifact payloads.
- **Boundary function:** keeps common-owned migration logic separate from `polisyos.ir.migrations`.

## Key Concepts

- **Registry** - migrations are registered per artifact and chained by version.
- **Executor** - `migrate_artifact()` applies the chain to a target version.
- **Manifest migration** - the current packaged migration handles `dataset_manifest`.

## Public API

- `register_migration`
- `migrate_artifact`
- `MANIFEST_CURRENT_VERSION`

## Current State

- Last updated: 2026-04-03
- Coverage still centers on `dataset_manifest` with a `0.9 -> 1.0` migration.
- The package does not export `POLICY_IR_CURRENT_VERSION`; IR migrations remain owned by `polisyos.ir.migrations`.
