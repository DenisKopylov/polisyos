# Topology Contract Schemas

JSON Schemas in this directory validate `architecture/*.toml` topology,
package-boundary, generated-artifact, and migration-shim contracts after TOML is
decoded to JSON.

The initial schemas are intentionally small. Phase 0 should tighten enums,
required fields, and cross-reference checks as guardrails become active.

Current schema set:

- `topology.schema.json`
- `package_boundaries.schema.json`
- `generated_artifacts.schema.json`
- `migration_shims.schema.json`
- `complexity_exceptions.schema.json`
- `import_contracts.schema.json`
- `public_surface.schema.json`
- `conservative_overlay.schema.json`
