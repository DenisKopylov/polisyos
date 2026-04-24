# Runtime Dashboard

## Purpose

`runtime-dashboard` is the main operator-facing React/Vite application for
Runtime API v1. Its job is to turn the runtime OpenAPI contract into a typed UI
for runs, artifacts, evidence, Lex/knowledge, platform posture, and control
flows without bypassing backend boundaries.

This package is the canonical frontend surface in the repository. If you are
changing dashboard behavior, start here before looking at the static reference
shell.

## Where to Start

- Browser bootstrap:
  [`src/main.tsx`](src/main.tsx)

- App shell and providers:
  [`src/app/App.tsx`](src/app/App.tsx),
  [`src/app/providers/AppProviders.tsx`](src/app/providers/AppProviders.tsx)

- Router and route manifest:
  [`src/app/routes/AppRouter.tsx`](src/app/routes/AppRouter.tsx),
  [`src/app/routes/routes.tsx`](src/app/routes/routes.tsx)

- Workspace registry and bootstrap queries:
  [`src/app/workspaces.ts`](src/app/workspaces.ts)

- API transport and generated types:
  [`src/api/client.ts`](src/api/client.ts),
  [`src/api/http.ts`](src/api/http.ts),
  [`src/api/types.ts`](src/api/types.ts)

- Source-level module map:
  [`src/README.md`](src/README.md)

## Public Entrypoints

- Browser entry: [`src/main.tsx`](src/main.tsx)
- App shell: [`src/app/App.tsx`](src/app/App.tsx)
- Route tree: [`src/app/routes/routes.tsx`](src/app/routes/routes.tsx)
- Workspace definitions: [`src/app/workspaces.ts`](src/app/workspaces.ts)
- Runtime HTTP transport:
  [`src/api/client.ts`](src/api/client.ts),
  [`src/api/http.ts`](src/api/http.ts)

- Generated API types:
  [`src/api/types.ts`](src/api/types.ts)

- API type generation:
  [`scripts/generate-api-client.sh`](scripts/generate-api-client.sh)

## Dependencies

- Depends on:
  [`../../schemas/runtime_api_v1.openapi.json`](../../schemas/runtime_api_v1.openapi.json),
  [`../../src/polisyos/runtime/http/`](../../src/polisyos/runtime/http/),
  Node.js 22, npm, Playwright/Vitest toolchain, and the Runtime API availability
  model documented in the API reference

- Depended on by:
  operator workflows, frontend onboarding, Playwright journeys under
  [`e2e/`](e2e/), Vitest suites under [`src/test/`](src/test/), and frontend API
  drift checks

## Common Commands

- `npm ci --ignore-scripts`
  `conceptual/manual; use on a clean checkout to install dependencies`

- `npm run generate:api`
  `smoke-tested 2026-04-17`

- `npm run dev`
  `conceptual/manual; requires Runtime API at 127.0.0.1:8000 or VITE_RUNTIME_API_URL`

- `npm run preview`
  `conceptual/manual; use after npm run build`

- `npm run build`
  `conceptual/manual; production build plus postbuild security artifacts`

- `npm run lint`
  `conceptual/manual; local editing loop`

## Test And Verification

- `npm run typecheck`
  `smoke-tested 2026-04-17`

- `npm run test:contracts`
  `smoke-tested 2026-04-17`

- `npm run check:architecture`
  `smoke-tested 2026-04-17; currently fails on existing layer-boundary violations in app/shared -> features imports`

- `npm run test:components`
  `conceptual/manual; broader Vitest component coverage`

- `npm run test:journeys:smoke`
  `conceptual/manual; requires Playwright browsers and a running app/runtime stack`

- `npm run test:visual`
  `conceptual/manual; heavier visual regression pass`

## Reference Docs

- [`src/README.md`](src/README.md)
- [`../../docs/how-to/onboarding/frontend-engineer.md`](../../docs/how-to/onboarding/frontend-engineer.md)
- [`../../docs/reference/api/index.md`](../../docs/reference/api/index.md)
- [`../../docs/reference/api/control.md`](../../docs/reference/api/control.md)
- [`../../docs/reference/api/runs.md`](../../docs/reference/api/runs.md)
- [`../../docs/reference/api/artifacts.md`](../../docs/reference/api/artifacts.md)
- [`../../docs/reference/operations/observability-topology.md`](../../docs/reference/operations/observability-topology.md)

Last updated: 2026-04-17
