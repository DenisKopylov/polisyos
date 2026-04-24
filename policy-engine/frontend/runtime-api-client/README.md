# Runtime API Client

## Purpose

`runtime-api-client` stores the generated JavaScript and TypeScript client for
Runtime API v1. It is the lightest consumer surface in the frontend tree: a
thin wrapper over the OpenAPI contract that exposes read and batch-read runtime
operations without React, Vite, or dashboard-specific state management.

Do not edit `runtimeApiClient.ts` or `runtimeApiClient.js` by hand. The source
of truth is the runtime OpenAPI schema and the generator scripts in
`tools/runtime/`.

## Where to Start

- Generated TypeScript source:
  [`runtimeApiClient.ts`](runtimeApiClient.ts)

- Generated JavaScript output:
  [`runtimeApiClient.js`](runtimeApiClient.js)

- Generator:
  [`../../tools/runtime/generate_runtime_client.py`](../../tools/runtime/generate_runtime_client.py)

- Contract checker:
  [`../../tools/runtime/check_runtime_api_contract.py`](../../tools/runtime/check_runtime_api_contract.py)

- Upstream OpenAPI source:
  [`../../schemas/runtime_api_v1.openapi.json`](../../schemas/runtime_api_v1.openapi.json)

## Public Entrypoints

- `RuntimeApiClient` class in [`runtimeApiClient.ts`](runtimeApiClient.ts)
- Constructor options: `baseUrl`, `headers`, `fetchImpl`
- Generated method groups for health, runs, debug, artifacts, and control read
  paths in [`runtimeApiClient.ts`](runtimeApiClient.ts)

- ESM import surface for the reference shell:
  [`runtimeApiClient.js`](runtimeApiClient.js)

## Dependencies

- Depends on:
  [`../../schemas/runtime_api_v1.openapi.json`](../../schemas/runtime_api_v1.openapi.json),
  [`../../tools/runtime/export_runtime_openapi.py`](../../tools/runtime/export_runtime_openapi.py),
  [`../../tools/runtime/generate_runtime_client.py`](../../tools/runtime/generate_runtime_client.py),
  and the runtime HTTP contract in
  [`../../src/polisyos/runtime/http/`](../../src/polisyos/runtime/http/)

- Depended on by:
  [`../runtime-reference-shell/app.js`](../runtime-reference-shell/app.js),
  ad hoc JS/TS API consumers, and frontend contract drift verification

## Common Commands

- `cd frontend/runtime-api-client && npm run lint`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-api-client && npm run format:check`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-api-client && npm run typecheck`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-api-client && npm run check:architecture`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-api-client && npm test`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-api-client && npm run contracts:verify`
  `smoke-tested 2026-04-23`

- `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json`
  `conceptual/manual; rewrites the checked-in OpenAPI snapshot`

- `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/generate_runtime_client.py --openapi schemas/runtime_api_v1.openapi.json --out-ts frontend/runtime-api-client/runtimeApiClient.ts --out-js frontend/runtime-api-client/runtimeApiClient.js`
  `conceptual/manual; regenerates the committed client artifacts`

## Test And Verification

- `cd frontend/runtime-api-client && npm run lint`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-api-client && npm run format:check`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-api-client && npm run typecheck`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-api-client && npm run check:architecture`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-api-client && npm test`
  `smoke-tested 2026-04-23`

- `cd frontend/runtime-api-client && npm run contracts:verify`
  `smoke-tested 2026-04-23`

- `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py`
  `smoke-tested 2026-04-17`

- `cd frontend/runtime-dashboard && npm run generate:api`
  `smoke-tested 2026-04-17; verifies downstream dashboard type generation still works`

## Reference Docs

- [`../README.md`](../README.md)
- [`../runtime-reference-shell/README.md`](../runtime-reference-shell/README.md)
- [`../../docs/reference/api/index.md`](../../docs/reference/api/index.md)
- [`../../docs/reference/api/runs.md`](../../docs/reference/api/runs.md)
- [`../../docs/reference/api/artifacts.md`](../../docs/reference/api/artifacts.md)
- [`../../src/polisyos/runtime/http/README.md`](../../src/polisyos/runtime/http/README.md)

Last updated: 2026-04-23
