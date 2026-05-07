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
| `packages/runtime-api-client` | `team-runtime` | `pnpm --filter @polisyos/runtime-api-client run build` | `pnpm --filter @polisyos/runtime-api-client test`, `pnpm --filter @polisyos/runtime-api-client run contracts:verify` | `pnpm --filter @polisyos/runtime-api-client run generate`, `pnpm --filter @polisyos/runtime-api-client run contracts:verify` |
| `apps/runtime-dashboard` | `team-frontend` | `pnpm --filter @polisyos/runtime-dashboard run build`, `pnpm --filter @polisyos/runtime-dashboard run typecheck` | `pnpm --filter @polisyos/runtime-dashboard run test:components`, `pnpm --filter @polisyos/runtime-dashboard run test:contracts` | `pnpm --filter @polisyos/runtime-dashboard run generate:api`, `pnpm --filter @polisyos/runtime-dashboard run contracts:verify` |
| `apps/runtime-reference-shell` | `team-runtime` | `pnpm --filter @polisyos/runtime-reference-shell run build` | `pnpm --filter @polisyos/runtime-reference-shell test` | `pnpm --filter @polisyos/runtime-reference-shell run check:architecture` |
| `packages/cli` | `team-frontend` | `pnpm --filter @polisyos/cli run build` | `pnpm --filter @polisyos/cli test` | `pnpm --filter @polisyos/cli run lint` |

Root fan-out commands:

- `pnpm build`
- `pnpm test` (all package-local `test` scripts, including the full dashboard component suite)
- `pnpm test:smoke` (workspace smoke/contract pass)
- `pnpm lint`

## Generated Outputs

Committed generated outputs are registered in
`architecture/generated_artifacts.toml`:

- `packages/runtime-api-client/runtimeApiClient.ts`
- `packages/runtime-api-client/runtimeApiClient.js`
- `apps/runtime-dashboard/src/api/types.ts`

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
