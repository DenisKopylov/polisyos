# Frontend (`frontend/`)

## Purpose

`frontend/` is the Runtime API consumer layer for PolicyOS. It keeps UI work
contract-first: frontend packages talk to `polisyos.runtime.http` over HTTP and
generated OpenAPI artifacts, not by reading CAS, local databases, or runtime
filesystem state directly.

The directory contains three surfaces:

- [`runtime-dashboard/`](runtime-dashboard/README.md) — the main React/Vite
  operator UI.

- [`runtime-reference-shell/`](runtime-reference-shell/README.md) — a static
  diagnostics shell for fast manual checks.

- [`runtime-api-client/`](runtime-api-client/README.md) — the generated JS/TS
  client consumed by the reference shell and other lightweight integrations.

## Where to Start

- Start here for contributor workflow:
  [`../docs/how-to/onboarding/frontend-engineer.md`](../docs/how-to/onboarding/frontend-engineer.md)

- Start here for the main app:
  [`runtime-dashboard/README.md`](runtime-dashboard/README.md)

- Start here for the generated contract surfaces:
  [`runtime-api-client/README.md`](runtime-api-client/README.md)

- Start here for the canonical backend contract:
  [`../schemas/runtime_api_v1.openapi.json`](../schemas/runtime_api_v1.openapi.json)

- Start here for the backend implementation boundary:
  [`../src/polisyos/runtime/http/README.md`](../src/polisyos/runtime/http/README.md)

## Public Entrypoints

- Dashboard browser entry:
  [`runtime-dashboard/src/main.tsx`](runtime-dashboard/src/main.tsx)

- Dashboard route tree:
  [`runtime-dashboard/src/app/routes/routes.tsx`](runtime-dashboard/src/app/routes/routes.tsx)

- Dashboard generated API types:
  [`runtime-dashboard/src/api/types.ts`](runtime-dashboard/src/api/types.ts)

- Static reference shell:
  [`runtime-reference-shell/index.html`](runtime-reference-shell/index.html)

- Generated runtime client:
  [`runtime-api-client/runtimeApiClient.ts`](runtime-api-client/runtimeApiClient.ts)

## Dependencies

- Depends on:
  [`../schemas/runtime_api_v1.openapi.json`](../schemas/runtime_api_v1.openapi.json),
  [`../src/polisyos/runtime/http/`](../src/polisyos/runtime/http/),
  [`../tools/ops/runtime/export_runtime_openapi.py`](../tools/ops/runtime/export_runtime_openapi.py),
  [`../tools/ops/runtime/generate_runtime_client.py`](../tools/ops/runtime/generate_runtime_client.py)

- Depended on by:
  frontend onboarding, runtime operator flows, frontend contract checks, and
  manual API diagnostics without opening the docs site

## Common Commands

- `pnpm --filter @polisyos/runtime-dashboard run generate:api`
  `smoke-tested 2026-04-17`

- `pnpm --filter @polisyos/runtime-dashboard run dev`
  `conceptual/manual; requires a running Runtime API or VITE_RUNTIME_API_URL`

- `pnpm --filter @polisyos/runtime-dashboard run preview`
  `conceptual/manual; run after pnpm --filter @polisyos/runtime-dashboard run build`

- `cd frontend/runtime-reference-shell && python3 -m http.server 4173`
  `smoke-tested 2026-04-17`

## Test And Verification

- `pnpm --filter @polisyos/runtime-dashboard run typecheck`
  `smoke-tested 2026-04-17`

- `pnpm --filter @polisyos/runtime-dashboard run test:contracts`
  `smoke-tested 2026-04-17`

- `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops/runtime/check_runtime_api_contract.py`
  `smoke-tested 2026-04-17`

- `curl -I http://127.0.0.1:4173/index.html`
  `smoke-tested 2026-04-17 while serving runtime-reference-shell locally`

## Reference Docs

- [`../docs/how-to/onboarding/frontend-engineer.md`](../docs/how-to/onboarding/frontend-engineer.md)
- [`../docs/reference/api/index.md`](../docs/reference/api/index.md)
- [`../docs/reference/api/control.md`](../docs/reference/api/control.md)
- [`../docs/reference/api/runs.md`](../docs/reference/api/runs.md)
- [`../docs/reference/api/artifacts.md`](../docs/reference/api/artifacts.md)
- [`runtime-dashboard/src/README.md`](runtime-dashboard/src/README.md)

Last updated: 2026-04-17
