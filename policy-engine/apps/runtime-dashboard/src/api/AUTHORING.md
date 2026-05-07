# Dashboard API Authoring Contract

Owner: `team-frontend`
Backup owner: `team-runtime`
Applies to: `apps/runtime-dashboard/src/api/**`
Last updated: 2026-05-05

## Purpose

This subtree is the only frontend boundary for Runtime API transport,
generated types, React Query hooks, cache keys, validators, and streams.

## Allowed File Categories

- TypeScript source, generated `types.ts`, React Query hooks, validators,
  colocated tests, and local docs.
- No feature components, route shells, raw fixtures, or build output.

## Public/Private Boundary

Feature modules consume exported hooks/types. API code may depend on generated
OpenAPI types and shared low-level utilities, but must not import feature code.

## Naming Convention

Use `use<Domain><Action>.ts` for hooks, `*.test.ts(x)` for colocated tests, and
stable query-key names in `queryKeys.ts`.

## Test Location

Use colocated API tests and `src/test/contracts/` for fixture-backed contract
verification.

## Fixture/Data Policy

Runtime payload fixtures live in `src/test/contracts/fixtures/`. Do not place
JSON payload fixtures directly under `src/api/`.

## Generated File Policy

`types.ts` is generated from `schemas/runtime_api_v1.openapi.json` by
`pnpm --filter @polisyos/runtime-dashboard run generate:api`. Do not edit it by
hand.

## Extension Points

New API surface starts at backend route/OpenAPI, then generated types, then
hooks and query keys. Shared fetch behavior belongs in `http.ts`.

## Deprecation And Shim Policy

Hook renames and response-shape changes require compatibility wrappers or
release notes until feature consumers and contract fixtures are updated.
