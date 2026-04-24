# Update Runtime Dashboard API Client

> Проведите runtime contract change через всю consumer chain:
> FastAPI/OpenAPI -> generated JS/TS client -> dashboard API types.

## Inputs

- intentional runtime route/DTO/OpenAPI change;
- понимание, должен ли endpoint быть публичным OpenAPI surface;
- готовность обновить committed generated artifacts в том же change set.

## Output

- синхронизированы `schemas/runtime_api_v1.openapi.json`,
  `frontend/runtime-api-client/runtimeApiClient.{ts,js}`,
  `frontend/runtime-dashboard/src/api/types.ts`;

- runtime and frontend contract checks снова green.

## Commands

```bash
cd policy-engine
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/generate_runtime_client.py --openapi schemas/runtime_api_v1.openapi.json --out-ts frontend/runtime-api-client/runtimeApiClient.ts --out-js frontend/runtime-api-client/runtimeApiClient.js
cd frontend/runtime-dashboard && npm run generate:api
```

Verification:

```bash
cd policy-engine
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py
cd frontend/runtime-dashboard && npm run contracts:verify && npm run typecheck
```

## 1. Update the runtime source of truth

The chain starts at:

- `src/polisyos/runtime/http/**`;
- `src/polisyos/runtime/http/openapi_contract.py`;
- request/response DTOs and route wiring in the runtime app.

If the endpoint is route-only, stop here and document it manually in API docs.
Do not force route-only endpoints into generated clients.

## 2. Export the committed OpenAPI snapshot

Run:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
```

This file is the committed source of truth for runtime consumers.

## 3. Regenerate the JS/TS runtime API client

Run:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/generate_runtime_client.py --openapi schemas/runtime_api_v1.openapi.json --out-ts frontend/runtime-api-client/runtimeApiClient.ts --out-js frontend/runtime-api-client/runtimeApiClient.js
```

This updates the lightweight frontend consumer surface used by the reference
shell and other non-dashboard consumers.

## 4. Regenerate dashboard API types

Run from `frontend/runtime-dashboard/`:

```bash
npm run generate:api
```

This updates `src/api/types.ts` from the same committed OpenAPI snapshot.

## 5. Verify the whole contract chain

Backend-side drift and invariants:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py
```

Frontend-side drift:

```bash
cd frontend/runtime-dashboard
npm run contracts:verify
npm run typecheck
```

## Rollback

- if the runtime change was not intentional, revert the OpenAPI snapshot first,
  then the generated client and dashboard types;

- if the endpoint should be route-only, remove it from OpenAPI generation and
  leave the client artifacts unchanged;

- do not land only part of the chain unless you are explicitly parking a broken
  intermediate branch.

## Troubleshooting

- `check_runtime_api_contract.py` fails: snapshot, generated client and runtime
  code are out of sync;

- `npm run generate:api` changes only dashboard types, not the shared JS/TS
  runtime client;

- `contracts:verify` fails after a valid backend change: the dashboard fixtures
  or expectations need an intentional follow-up update, not a blind revert.
