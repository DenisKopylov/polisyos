# Repository SOTA Phase 1 Data Forge Foundation

- Date: 2026-05-02
- Scope: Phase 1 implementation evidence for
  `docs/plans/accepted/REPOSITORY_SOTA_PLAN.md`
- Execution posture: additive contracts, no structural source moves

## Foundation Surface

`polisyos.data_forge` now lazily exposes the build-time foundation contracts
needed by later repository moves:

- asset contracts: `AssetKey`, `AssetSpec`, `AssetGroup`, `asset`,
  `plan_asset_specs`
- artifact governance: `ArtifactRef`, `ProducerVersion`, `PIILevel`,
  `RetentionClass`
- schema registry: `SchemaRegistry`, `SchemaVersion`, `CompatibilityMode`
- snapshot semantics: `SnapshotTransaction`, `SnapshotTransactionStatus`,
  `merkle_root`
- quality contracts: `QCCheck`, `QCReport`, `evaluate_fail_fast`
- migration evidence helpers: golden and differential comparison helpers
- runtime-safe consumption: `read_api`

The package remains split by intent: top-level `polisyos.data_forge` is a lazy
build-time facade; runtime consumers are constrained to
`polisyos.data_forge.read_api`, and importing that read API does not load
`kernel/` or `domains/` internals.

## Artifact Metadata

`ArtifactRef` requires the Phase 1 governance set:

| Field | Evidence |
| --- | --- |
| `owner` | Pydantic model and JSON Schema required field |
| `producer_version` | Pydantic model and JSON Schema required field |
| `schema_id`, `schema_version` | Pydantic model and JSON Schema required fields |
| `freshness_sla_seconds` | Pydantic model and JSON Schema required field |
| `retention_class` | Pydantic model and JSON Schema required field |
| `pii_level` | Pydantic model and JSON Schema required field |
| `license` | Pydantic model and JSON Schema required field |
| `regeneration_command` | Pydantic model and JSON Schema required field |

The contract schema lives at
`schemas/artifacts/data_forge_artifact_ref_v1.schema.json`.

## Boundary Evidence

- `architecture/imports/contracts.toml` blocks runtime/fabric/IR/domain
  consumers from importing `polisyos.data_forge`,
  `polisyos.data_forge.kernel`, or `polisyos.data_forge.domains`, while
  allowing `polisyos.data_forge.read_api`.
- `architecture/packages/boundaries.toml` keeps
  `runtime_allowed_submodules = ["polisyos.data_forge.read_api"]` on the Data
  Forge package boundary.
- `architecture/public_surface/contract.toml` documents the top-level Data Forge facade
  as lazy build-time only and `read_api` as the runtime import surface.

## Baselines

- Contract schemas are registered under the `data-forge-contract-schemas`
  generated-artifact family.
- Golden, shadow, replay, and differential fixtures are registered under
  `data-forge-migration-fixture-baselines`.
- Focused Phase 1 tests cover public facade compatibility, artifact identity,
  schema lookup, snapshot semantics, quality contracts, golden/differential
  helpers, runtime import boundaries, and read API import lightness.

## Acceptance

| Requirement | Status |
| --- | --- |
| Build-time producers and runtime readers are separated by tests and import contracts. | Implemented |
| Existing consumers continue through compatibility facades. | Implemented via `read_api` boundary checks |
| ArtifactRef and schema registry have focused tests. | Implemented |
| Snapshot/read API compatibility evidence exists. | Implemented |
| Registered generated artifacts and fixture contracts exist. | Implemented |
