# Runtime API Client

## Purpose

`runtime-api-client` stores the generated JavaScript and TypeScript client for
Runtime API v1. It is the lightest consumer surface in the frontend tree: a
thin wrapper over the OpenAPI contract that exposes read and batch-read runtime
operations without React, Vite, or dashboard-specific state management.

This package is the canonical generated-client home selected by Atlas DS3.
Do not edit `types.ts`, `runtimeApiClient.ts`, `runtimeApiClient.js`,
`canonicalRuntimeApiClient.ts`, or `canonicalRuntimeApiClient.js` by hand. Their
shared source of truth is the runtime OpenAPI schema. The package-root export is
the canonical twin: its DTO aliases point directly at the discriminated schema
types in `types.ts`. The raw `runtimeApiClient.*` pair remains a generated
compatibility artifact for the repository's existing contract-drift checker;
it is not the package's public entrypoint. The dashboard-local generated type
file is a downstream compatibility surface, not a second owner.

## Where to Start

- Public generated TypeScript client:
  [`canonicalRuntimeApiClient.ts`](canonicalRuntimeApiClient.ts)

- Generated OpenAPI schema types:
  [`types.ts`](types.ts)

- Canonical permission vocabulary for authority consumers:
  `components["schemas"]["RuntimePermission"]` in [`types.ts`](types.ts).
  This union is generated from the server-owned OpenAPI enum; consumers must
  not maintain a parallel permission-key list.

- Public generated JavaScript client:
  [`canonicalRuntimeApiClient.js`](canonicalRuntimeApiClient.js)

- Raw compatibility generator output:
  [`runtimeApiClient.ts`](runtimeApiClient.ts) and
  [`runtimeApiClient.js`](runtimeApiClient.js)

- Generator:
  [`scripts/generate-runtime-api-client.sh`](scripts/generate-runtime-api-client.sh),
  which composes the schema-type generator, raw client generator, and
  canonicalizer through one output-root-aware entrypoint.

- Canonicalizer:
  [`scripts/canonicalize-runtime-client.mjs`](scripts/canonicalize-runtime-client.mjs)

- Contract checker:
  [`../../tools/ops_runners/runtime/check_runtime_api_contract.py`](../../tools/ops_runners/runtime/check_runtime_api_contract.py)

- Upstream OpenAPI source:
  [`../../schemas/runtime_api_v1.openapi.json`](../../schemas/runtime_api_v1.openapi.json)

## Public Entrypoints

- `RuntimeApiClient` class in
  [`canonicalRuntimeApiClient.ts`](canonicalRuntimeApiClient.ts)
- OpenAPI `paths`, `components`, and `operations` in [`types.ts`](types.ts)
- Constructor options: `baseUrl`, `headers`, `fetchImpl`
- Generated method groups for health, runs, debug, artifacts, and control read
  paths in [`canonicalRuntimeApiClient.ts`](canonicalRuntimeApiClient.ts)

- ESM import surface for the reference shell:
  [`canonicalRuntimeApiClient.js`](canonicalRuntimeApiClient.js)

## Dependencies

- Depends on:
  [`../../schemas/runtime_api_v1.openapi.json`](../../schemas/runtime_api_v1.openapi.json),
  [`../../tools/ops_runners/runtime/export_runtime_openapi.py`](../../tools/ops_runners/runtime/export_runtime_openapi.py),
  [`../../tools/ops_runners/runtime/generate_runtime_client.py`](../../tools/ops_runners/runtime/generate_runtime_client.py),
  and the runtime HTTP contract in
  [`../../src/polisyos/runtime/http/`](../../src/polisyos/runtime/http/)

- Depended on by:
  [`../../apps/runtime-reference-shell/app.js`](../../apps/runtime-reference-shell/app.js),
  ad hoc JS/TS API consumers, and frontend contract drift verification

## Common Commands

- `pnpm --filter @polisyos/runtime-api-client run lint`
  `smoke-tested 2026-04-23`

- `pnpm --filter @polisyos/runtime-api-client run format:check`
  `smoke-tested 2026-04-23`

- `pnpm --filter @polisyos/runtime-api-client run typecheck`
  `smoke-tested 2026-04-23`

- `pnpm --filter @polisyos/runtime-api-client run check:architecture`
  `smoke-tested 2026-04-23`

- `pnpm --filter @polisyos/runtime-api-client test`
  `smoke-tested 2026-04-23`

- `pnpm --filter @polisyos/runtime-api-client run contracts:verify`
  `smoke-tested 2026-04-23`

- `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json`
  `conceptual/manual; rewrites the checked-in OpenAPI snapshot`

- `corepack pnpm --dir packages/runtime-api-client run generate`
  Replays schema types, the raw compatibility artifacts, and the public
  canonical twin in one command after exporting the OpenAPI schema.

- `npx --yes openapi-typescript@7.13.0 schemas/runtime_api_v1.openapi.json -o packages/runtime-api-client/types.ts`
  Canonical schema-type generation; the exact tool pin is owned by this shared
  package and does not depend on a dashboard-local installation.

## Test And Verification

- `pnpm --filter @polisyos/runtime-api-client run lint`
  `smoke-tested 2026-04-23`

- `pnpm --filter @polisyos/runtime-api-client run format:check`
  `smoke-tested 2026-04-23`

- `pnpm --filter @polisyos/runtime-api-client run typecheck`
  `smoke-tested 2026-04-23`

- `pnpm --filter @polisyos/runtime-api-client run check:architecture`
  `smoke-tested 2026-04-23`

- `pnpm --filter @polisyos/runtime-api-client test`
  `smoke-tested 2026-04-23`

- `pnpm --filter @polisyos/runtime-api-client run contracts:verify`
  `smoke-tested 2026-04-23`

- `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py`
  `smoke-tested 2026-04-17`

- `pnpm --filter @polisyos/runtime-dashboard run generate:api`
  `smoke-tested 2026-04-17; verifies downstream dashboard type generation still works`

## Reference Docs

- [`../README.md`](../README.md)
- [`../../apps/runtime-reference-shell/README.md`](../../apps/runtime-reference-shell/README.md)
- [`../../docs/reference/api/index.md`](../../docs/reference/api/index.md)
- [`../../docs/reference/api/runs.md`](../../docs/reference/api/runs.md)
- [`../../docs/reference/api/artifacts.md`](../../docs/reference/api/artifacts.md)
- [`../../src/polisyos/runtime/http/README.md`](../../src/polisyos/runtime/http/README.md)

Last updated: 2026-07-18
