# Frontend Workspace Contract

Freshness: 2026-05-03
Owner: `team-frontend`
Source of truth: `architecture/frontend_workspaces.toml`

Workspace manager: `pnpm` via root `pnpm-workspace.yaml` and one root
`pnpm-lock.yaml`.

The JavaScript workspace is contract-first. Runtime consumers use HTTP,
OpenAPI snapshots, and generated clients/types rather than importing runtime
internals or reading runtime filesystem state.

## Workspaces

| Workspace | Owner | Build | Test | Drift |
| --- | --- | --- | --- | --- |
| `packages/runtime-api-client` | `team-runtime` | `corepack pnpm --filter @polisyos/runtime-api-client run build` | `corepack pnpm --filter @polisyos/runtime-api-client test`, `corepack pnpm --filter @polisyos/runtime-api-client run contracts:verify` | `corepack pnpm --filter @polisyos/runtime-api-client run generate -- --openapi schemas/runtime_api_v1.openapi.json`, `corepack pnpm --filter @polisyos/runtime-api-client run contracts:verify` |
| `apps/runtime-dashboard` | `team-frontend` | `corepack pnpm --filter @polisyos/runtime-dashboard run build`, `corepack pnpm --filter @polisyos/runtime-dashboard run typecheck` | `corepack pnpm --filter @polisyos/runtime-dashboard run test:components`, `corepack pnpm --filter @polisyos/runtime-dashboard run test:contracts` | `corepack pnpm --filter @polisyos/runtime-dashboard run generate:api -- --openapi schemas/runtime_api_v1.openapi.json`, `corepack pnpm --filter @polisyos/runtime-dashboard run contracts:verify` |
| `apps/runtime-reference-shell` | `team-runtime` | `corepack pnpm --filter @polisyos/runtime-reference-shell run build` | `corepack pnpm --filter @polisyos/runtime-reference-shell test` | `corepack pnpm --filter @polisyos/runtime-reference-shell run check:architecture` |
| `packages/cli` | `team-frontend` | `corepack pnpm --filter @polisyos/cli run build` | `corepack pnpm --filter @polisyos/cli test` | `corepack pnpm --filter @polisyos/cli run lint` |

Root fan-out commands:

- `corepack pnpm build`
- `corepack pnpm test` (all package-local `test` scripts, including the full dashboard component suite)
- `corepack pnpm test:smoke` (workspace smoke/contract pass)
- `corepack pnpm lint`

## Generated Outputs

Committed generated outputs are registered in
`architecture/generated_artifacts.toml`:

- `packages/runtime-api-client/types.ts`
- `packages/runtime-api-client/runtimeApiClient.ts` (raw compatibility output)
- `packages/runtime-api-client/runtimeApiClient.js` (raw compatibility output)
- `packages/runtime-api-client/canonicalRuntimeApiClient.ts` (public entrypoint)
- `packages/runtime-api-client/canonicalRuntimeApiClient.js` (public entrypoint)
- `apps/runtime-dashboard/src/api/types.ts`

The runtime client package owns the pinned `openapi-typescript` `7.13.0`
resolver. Both client generators accept the explicit `--openapi` input and
write to an isolated `--output-root` when one is supplied; dashboard output
keeps its downstream normalization and formatting profile.

Local outputs stay ignored under workspace-local `node_modules/`, product
`_build/{apps,packages}/...`, and product `_cache/{apps,packages}/...`.
Runtime dashboard outputs use `_build/apps/runtime-dashboard/{coverage,dist,output,playwright-report,storybook-static,test-results}`.
A local output can become committed only after it is promoted to a reviewed
baseline and registered as a generated artifact.

## Runtime Dashboard Subtree Contracts

| Subtree | Contract | Placement rule |
| --- | --- | --- |
| `apps/runtime-dashboard/src/app/` | App shell, providers, route registry, auth/session, offline/realtime, app-wide state | Feature routes register here; feature internals do not become app shell dependencies. |
| `apps/runtime-dashboard/src/features/` | Vertical feature modules | New features use `domain/`, `components/`, `routes/` or `route.tsx`, `hooks/`, optional `api/`, `state/`, tests/stories, and a public `index.ts`. |
| `apps/runtime-dashboard/src/shared/ui/` | Feature-agnostic UI primitives and patterns | Shared UI never imports from `features` or `app`; feature-specific UI stays under its feature. |
| `apps/runtime-dashboard/src/shared/charts/` | Shared charts, chart tokens, uncertainty renderers, and retained stories | Reusable chart primitives export through `index.ts`; feature-specific visualizations stay under features. |
| `apps/runtime-dashboard/src/api/` | HTTP transport, generated types, query keys, hooks, validators, streams | `types.ts` is generated from OpenAPI; features consume hooks and must not call backend internals directly. |
| `apps/runtime-dashboard/src/test/` | Test helpers, MSW handlers, accessibility helpers, contract fixtures | Production source must not import this subtree; API payload fixtures live under `contracts/fixtures/`. |

Local README/AUTHORING files in each subtree are the source of truth for
allowed file categories, generated-file policy, fixture placement, extension
points, and deprecation/shim handling.
