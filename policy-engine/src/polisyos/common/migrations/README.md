# Common Migrations (`polisyos.common.migrations`)

`polisyos.common.migrations` owns the neutral local migration registry.  The
`dataset_manifest` schema is owned by Fabric identity; Common retains only a
deprecated compatibility callback for callers that still import the old
manifest module.

## Role in System

- **Depends on:** the local migration registry and artifact-specific migration handlers.
- **Used by:** bootstrap and migration tooling that needs to rewrite common-owned artifact payloads.
- **Boundary function:** keeps common-owned migration logic separate from `polisyos.ir.migrations`.

## Key Concepts

- **Registry** - migrations are registered per artifact and chained by version.
- **Executor** - `migrate_artifact()` applies the chain to a target version.
- **Manifest compatibility** - the old `dataset_manifest` import path remains
  temporarily registered without importing Fabric; the canonical callback and
  CLI registration live under `polisyos.fabric.identity.migrations`.

## Public API

- `register_migration`
- `migrate_artifact`
- `LinearMigrationProfile` and `run_linear_migration` expose the shared traversal objects used
  by artifact-specific migration owners such as IR. The facade exports the same objects rather
  than copying the traversal implementation.
- `MANIFEST_CURRENT_VERSION` (deprecated compatibility export)

## Current State

- Last updated: 2026-04-03
- The supported compatibility profile remains `dataset_manifest` with a
  `0.9 -> 1.0` rename; the complete historical corpus is not established.
- The package does not export `POLICY_IR_CURRENT_VERSION`; IR migrations remain owned by `polisyos.ir.migrations`.
