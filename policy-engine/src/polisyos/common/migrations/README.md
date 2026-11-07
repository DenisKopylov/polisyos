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
  An optional `selected_edges` mapping supplies per-call version edges, merged
  into a snapshot of the registered artifact graph, without changing the global
  registry. Callers without this option retain the existing registry behavior.
- **Manifest compatibility** - the old `dataset_manifest` import path remains
  temporarily registered without importing Fabric; the canonical callback is
  owned by `polisyos.fabric.identity.migrations`. The operational CLI supplies
  its contract-selected callback through the per-call edge.

## Public API

- `register_migration`
- `migrate_artifact`
- `LinearMigrationProfile` and `run_linear_migration` expose the shared traversal objects used
  by artifact-specific migration owners such as IR. The facade exports the same objects rather
  than copying the traversal implementation.
- `MANIFEST_CURRENT_VERSION` (deprecated compatibility export)

## Explicit adapter support (REQ-MIG-04-03)

The finite provided dataset-manifest composition is the following Python import
and registration set. Both version constants remain `1.0`; the conversion edge is
`0.9 -> 1.0`.

| Entry/import order | Effect |
| --- | --- |
| `polisyos.common.migrations` | Exports the neutral engine and compatibility constant; does not import Fabric or register the dataset edge. |
| Explicit `polisyos.common.migrations.manifest` | Retains the deprecated callback FQN and its registration side effect without importing Fabric. |
| `polisyos.fabric.identity.migrations` then `register_manifest_migration()` | Explicitly registers the schema-owner callback in Common. Merely importing that Fabric module does not register it. |
| Legacy/Fabric module imports in either order, followed by explicit Fabric registration | The tests retain the same bounded callback rename/error behavior and Common's existing replacement semantics. |
| Operational artifact CLI | Selects the contract-bound Fabric callable per call via `selected_edges`; it does not replace the process-global callback. |

[MIG-04 tests](../../../../tests/unit/remediation/test_mig_04.py)
exercise both fresh-process orders and six named payload vectors: legacy aliases,
canonical names, equal duplicate spelling, conflicting duplicate spelling, unknown
nested content, and missing fields, plus unsupported-input errors. Their separate
persisted-registry matrix checks real Fabric admission. The raw callback mutates
its supplied mapping; the Common engine deep-copies, stamps the target and keeps
its no-op copy contract. Neither callback invents missing provenance/timestamps nor
silently resolves duplicate aliases; conversion is not DTO/registry admission.

This finite set covers those named Python modules/tests and their operational TOML
and Markdown bindings, not every external import string or plugin. Those external
callers and original historical dataset manifests have not been supplied and remain
unqualified. Synthetic alias vectors are not historical production evidence.
The explicit legacy adapter and compatibility constant remain supported until a
separate approved caller/retirement window; there is no accepted sunset date.
An actual shared installed run is required to extend source/native results to the
noneditable package profile. See [release bindings and windows](../../../../tools/ops_runners/migrations/README.md)
and [callback configuration boundary](../../ir/migrations/README.md).

## Current State

- The supported compatibility profile remains `dataset_manifest` with a
  `0.9 -> 1.0` rename; the complete historical corpus is not established.
- The package does not export `POLICY_IR_CURRENT_VERSION`; IR migrations remain owned by `polisyos.ir.migrations`.
