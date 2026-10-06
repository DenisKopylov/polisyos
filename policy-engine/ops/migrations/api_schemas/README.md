# API Schema Migrations

Owner: `team-runtime`

This directory owns operator guidance for Runtime API schema, generated client,
and common persisted artifact schema migrations that affect supported
consumers.

## Covered Surfaces

- `schemas/runtime_api_v1.openapi.json`
- `packages/runtime-api-client/types.ts`
- `packages/runtime-api-client/canonicalRuntimeApiClient.ts`
- `packages/runtime-api-client/canonicalRuntimeApiClient.js`
- dashboard API types derived from Runtime OpenAPI
- common persisted manifests migrated through `polisyos.common.migrations`

The `dataset_manifest` converter is owned by `polisyos.fabric.identity` and
is registered with Common's neutral engine by the canonical migration CLI.
Renaming legacy aliases does not resolve conflicting aliases, fill missing
fields, validate every converted payload, or establish provenance/admission.
Consumers that require the current Fabric shape must still use the strict
`DatasetManifest` DTO.

## Compatibility Classes

- Additive: existing consumers keep working and generated clients can be
  refreshed after the OpenAPI snapshot lands.
- Compatible-breaking: readers keep dual-read or fallback behavior during the
  migration window, and release notes name the operator action.
- Breaking: release promotion requires migration-guide/runbook evidence before
  staging can advance to production.

## Operator Checks

- Run the Runtime API contract check before release promotion.
- Regenerate clients from the committed OpenAPI snapshot when the schema
  changes.
- Classify the OpenAPI diff in release evidence as additive,
  compatible-breaking, or breaking.
- For persisted artifact manifests, bind the Python helper to this class in
  `ops/migrations/migration-contracts.toml`.

## Release Gate

`ops/release/promotion-gates.toml#api_schema_compatibility` blocks schema
promotion without current OpenAPI/client evidence and migration/runbook docs for
breaking changes.
