# Runtime HTTP Authoring Contract

Owner: `team-runtime`
Applies to: `src/polisyos/runtime/http/**`
Last updated: 2026-05-05

## Purpose

This subtree owns Runtime API v1 app assembly, middleware, route/service
composition, OpenAPI generation, and the runtime middleware extension host.

## Allowed File Categories

- Product Python HTTP source, route/service subpackages, middleware modules,
  OpenAPI helpers, local docs, and package-local tests only when colocated by
  existing convention.
- No generated OpenAPI snapshots, frontend clients, runtime state, or local
  server output.

## Public/Private Boundary

Public API is the HTTP contract and generated OpenAPI. Direct imports from
route/service internals are private unless documented by the runtime facade.

## Naming Convention

Use snake_case modules by HTTP concern. Middleware modules should include
`middleware` in the filename when they implement middleware behavior.

## Test Location

Tests live in `tests/unit/runtime/http/`, with frontend contract fixtures under
`apps/runtime-dashboard/src/test/contracts/`.

## Fixture/Data Policy

Use test fixtures under `tests/_data/` or dashboard contract fixtures. Do not
commit live runtime payloads or CAS state here.

## Generated File Policy

Generated OpenAPI belongs in `schemas/runtime_api_v1.openapi.json`; generated
clients/types belong under `packages/runtime-api-client/` and
`apps/runtime-dashboard/src/api/types.ts`.

## Extension Points

External middleware uses `polisyos.runtime_middlewares` and must prove
deterministic order with a TestClient smoke test.

## Deprecation And Shim Policy

Route, middleware, or response-shape changes require API versioning docs,
generated-client compatibility checks, and migration notes when breaking.
